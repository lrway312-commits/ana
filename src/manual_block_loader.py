import os
import json
import time
from typing import List, Dict, Any
from datetime import datetime
from .config import SYMBOL

def _safe_get(d: Dict[str, Any], path: List[str], default=None):
    cur = d
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

def _last(arr: List[Any]):
    if not arr:
        return None
    return arr[-1]

def _prev(arr: List[Any]):
    if not arr or len(arr) < 2:
        return None
    return arr[-2]

def _compute_snapshot_metrics(snap: Dict[str, Any]) -> Dict[str, Any]:
    series = snap.get("series", {})
    oi_series = series.get("open_interest", [])
    ls_series = series.get("long_short_ratio", [])
    buy_series = series.get("taker_buy_volume", [])
    sell_series = series.get("taker_sell_volume", [])
    kl_series = series.get("klines_15m", [])

    oi_last = _last(oi_series) or 0.0
    oi_prev = _prev(oi_series) or oi_last
    ls_last = _last(ls_series) or 0.0
    ls_prev = _prev(ls_series) or ls_last
    buy_last = float(_last(buy_series) or 0.0)
    sell_last = float(_last(sell_series) or 0.0)
    net_taker = buy_last - sell_last
    total_taker = buy_last + sell_last
    buy_pct = (100.0 * buy_last / total_taker) if total_taker > 0 else 0.0
    oi_delta = float(oi_last) - float(oi_prev)
    ls_delta = float(ls_last) - float(ls_prev)

    # kline: [open_time, open, high, low, close, volume, close_time, quote_volume, trades, taker_buy_base, taker_buy_quote, ignore]
    kl_last = _last(kl_series) or []
    price_close = float(kl_last[4]) if len(kl_last) >= 5 else None
    close_ts = int(kl_last[6]) if len(kl_last) >= 7 else None
    kl_first = kl_series[0] if kl_series else []
    price_open = float(kl_first[1]) if len(kl_first) >= 2 else price_close
    open_ts = int(kl_first[0]) if len(kl_first) >= 1 else None
    price_trend = None
    if price_close is not None and price_open is not None:
        price_trend = price_close - price_open

    cvd_now = _safe_get(snap, ["analysis", "cvd", "cvd_now"], None)
    cvd_before = _safe_get(snap, ["analysis", "cvd", "cvd_before_5m"], None)
    ob_imbalance = _safe_get(snap, ["analysis", "order_book_detailed", "imbalance"], snap.get("analysis", {}).get("order_book_imbalance"))
    imbalance_before_300s = None
    for item in _safe_get(snap, ["analysis", "order_book_pressure", "imbalance_trend"], []):
        if item.get("period") == "before_300s":
            imbalance_before_300s = item.get("imbalance")
            break

    cvd_5m_change = None
    if cvd_now is not None and cvd_before is not None:
        cvd_5m_change = cvd_now - cvd_before

    ob_imbalance_5m_change = None
    if ob_imbalance is not None and imbalance_before_300s is not None:
        ob_imbalance_5m_change = ob_imbalance - imbalance_before_300s

    return {
        "timestamp": snap.get("timestamp"),
        "oi": oi_last,
        "oiDelta": oi_delta,
        "ls": ls_last,
        "lsDelta": ls_delta,
        "buyVol": buy_last,
        "sellVol": sell_last,
        "netTaker": net_taker,
        "buyPct": round(buy_pct, 2),
        "priceClose": price_close,
        "priceTrend4x5m": price_trend,
        "klineOpenTime": open_ts,
        "klineCloseTime": close_ts,
        "cvdNow": cvd_now,
        "cvdBefore5m": cvd_before,
        "cvd5mChange": cvd_5m_change,
        "orderBookImbalance": ob_imbalance,
        "obImbalance5mChange": ob_imbalance_5m_change,
    }

def _extract_price_from_snap(snap: Dict[str, Any]) -> float:
    """
    استخراج السعر الموحد من اللقطة بأفضل دقة ممكنة وبشكل متسق
    """
    price = None
    # 1. المحاولة من current.current_price
    if isinstance(snap.get("current"), dict):
        price = snap.get("current", {}).get("current_price")
    
    # 2. المحاولة من current_price مباشرة
    if price is None:
        price = snap.get("current_price")
    
    # 3. المحاولة من آخر شمعة
    if price is None:
        kl_series = snap.get("series", {}).get("klines_15m", [])
        last_k = kl_series[-1] if kl_series else []
        if len(last_k) >= 5:
            try:
                price = float(last_k[4])
            except (ValueError, TypeError):
                pass
            
    try:
        return float(price) if price is not None else 0.0
    except (ValueError, TypeError):
        return 0.0

def load_last_16_snapshots(dir_path: str = os.path.join("price_analysis", "بيانات"), save_combined: bool = False, use_last_snapshot_ts_name: bool = True, limit: int = 16) -> Dict[str, Any]:
    # اجمع آخر N ملف لقطة بناءً على الاسم (limit)
    if not os.path.isdir(dir_path):
        return {"block16": [], "last_snapshot": {}, "last_two": [], "trade_pairs": []}
    # اجلب اللقطات الخاصة بالرمز الحالي فقط
    files = [f for f in os.listdir(dir_path) if f.startswith(f"snapshot_{SYMBOL}_") and f.endswith(".json")]
    
    # فرز تنازليًا بوقت منسحب من الاسم أو وقت تعديل الملف لضمان الحداثة
    def _extract_ts(name: str) -> int:
        parts = name.split("_")
        if len(parts) >= 3:
            ts_str = parts[-1].replace(".json", "")
            try:
                # محاولة تحويل الاسم (YYYYMMDDHHMMSS) إلى رقم للمقارنة
                return int(ts_str)
            except ValueError:
                return 0
        return 0
    
    # فرز جميع الملفات أولاً بناءً على الاسم (الذي يحتوي على التاريخ) تنازلياً
    files_sorted = sorted(files, key=_extract_ts, reverse=True)
    
    # فحص الملفات وقراءة التوقيت الداخلي لضمان دقة الفرز
    valid_snaps = []
    # سنفحص 3 أضعاف العدد المطلوب لضمان الحصول على أحدث لقطات حقيقية وتجاوز أي ملفات تالفة
    scan_limit = limit * 3
    for fname in files_sorted[:scan_limit]:
        fpath = os.path.join(dir_path, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                snap = json.load(f)
            if snap and "timestamp" in snap:
                ts = snap.get("timestamp", 0)
                # استبعاد التواريخ غير المنطقية (مثل 0 أو تواريخ قديمة جداً خطأ)
                if ts > 1000000000000: # يجب أن يكون بالمللي ثانية وحديث نسبياً (بعد 2001)
                    # إضافة اسم الملف للقطة للمساعدة في التتبع
                    snap["_filename"] = fname
                    valid_snaps.append(snap)
        except Exception:
            continue
    
    # الفرز بناءً على التوقيت الداخلي الفعلي (الأقدم أولاً للدمج في block)
    # التأكد من عدم وجود بيانات مكررة أو قديمة جداً
    unique_snaps = {}
    for s in valid_snaps:
        unique_snaps[s.get("timestamp", 0)] = s
    
    # تحويل القيم إلى قائمة وفرزها زمنياً (من الأقدم للأحدث)
    sorted_snaps = sorted(unique_snaps.values(), key=lambda x: x.get("timestamp", 0))
    
    # أخذ آخر limit لقطة فقط لضمان التسلسل الصحيح
    block = []
    if len(sorted_snaps) > 0:
        # نأخذ آخر N عنصر
        start_idx = max(0, len(sorted_snaps) - limit)
        block = sorted_snaps[start_idx:]

    # التحقق من أن اللقطة الأخيرة في المصفوفة هي بالفعل الأحدث زمنياً
    if block:
        last_ts = block[-1].get("timestamp", 0)
        # طباعة معلومات للديبيج (ستظهر في السجلات)
        dt_last = datetime.fromtimestamp(last_ts/1000.0).strftime('%Y-%m-%d %H:%M:%S')
        print(f"DEBUG: Latest snapshot in block is {block[-1].get('_filename')} with internal TS: {dt_last}")

    # التأكد من وجود العدد المطلوب بالضبط
    if len(block) < limit:
        print(f"Warning: Only found {len(block)} valid snapshots (requested {limit}).")
    
    # اشتقاق أزواج دخول/خروج: الدخول عند سعر اللقطة السابقة، والخروج عند سعر اللقطة الحالية
    trade_pairs = []
    if len(block) >= 2:
        for i in range(len(block) - 1):
            entry_snap = block[i]
            exit_snap = block[i+1]

            entry_price = _extract_price_from_snap(entry_snap)
            exit_price = _extract_price_from_snap(exit_snap)

            # التأكد من أن الأسعار ليست صفرية
            if entry_price > 0 and exit_price > 0:
                trade_pairs.append(create_trade_pair(entry_price, exit_price))

    last_snapshot = block[-1] if block else {}
    last_two_snapshots = block[-2:] if len(block) >= 2 else []

    result = {"block16": block, "last_snapshot": last_snapshot, "last_two": last_two_snapshots, "trade_pairs": trade_pairs}


    # حفظ البيانات المدمجة في ملف JSON اختياريًا فقط
    if save_combined:
        try:
            snap_ts = None
            try:
                if isinstance(last_snapshot, dict):
                    snap_ts = last_snapshot.get("timestamp")
            except Exception:
                snap_ts = None
            if use_last_snapshot_ts_name and isinstance(snap_ts, (int, float)):
                dt = datetime.fromtimestamp(float(snap_ts) / 1000.0)
                timestamp = dt.strftime("%Y%m%d%H%M%S")
            else:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            output_filename = f"combined_snapshots_{SYMBOL}_{timestamp}.json"
            output_filepath = os.path.join(dir_path, output_filename)
            tmp_filepath = output_filepath + ".tmp"
            with open(tmp_filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4, ensure_ascii=False)
            try:
                os.replace(tmp_filepath, output_filepath)
            except Exception:
                pass
            result["combined_path"] = output_filepath
            print(f"Combined snapshots saved to {output_filepath}")
        except Exception as e:
            print(f"Error saving combined snapshots: {e}")

    return result


def create_trade_pair(entry_price: float, exit_price: float) -> dict:
    return {
        "entry_price": entry_price,
        "exit_price": exit_price
    }
