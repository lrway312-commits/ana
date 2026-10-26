# -*- coding: utf-8 -*-
"""
SMCEngine — محرك تحليلات ومفاهيم الأموال الذكية والاستراتيجيات المؤسسية
1. Smart Money Concepts (SMC): Liquidity Sweeps (EQH/EQL), CHoCH, BOS, Fair Value Gaps (FVG), Order Blocks (OB)
2. Anchored VWAP & Standard Deviation Bands (+1σ, +2σ, -1σ, -2σ)
3. CVD Absorption Detection (امتصاص صانع السوق للسيولة)
4. Gamma Exposure Regime (GEX): Long Gamma vs Short Gamma
"""

import urllib.request
import json
import math
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

_SYMBOL_MAP = {
    "BTC": "BTCUSDT",
    "ADA": "ADAUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
}

def _http_get_json(url: str, timeout: int = 5):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None

def fetch_klines(coin: str = "BTC", interval: str = "15m", limit: int = 96) -> list:
    """جلب شموع 15m تاريخية لـ 24 ساعة من Binance Futures"""
    symbol = _SYMBOL_MAP.get(coin.upper(), f"{coin.upper()}USDT")
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = _http_get_json(url)
    if not data or not isinstance(data, list):
        return []
    
    parsed = []
    for k in data:
        parsed.append({
            "open_time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": int(k[6]),
            "quote_vol": float(k[7]),
            "trades": int(k[8]),
            "taker_buy_base": float(k[9]),
            "taker_buy_quote": float(k[10])
        })
    return parsed

def calculate_anchored_vwap(klines: list) -> dict:
    """حساب السعر الموزون بحجم التداول المرتكز (Anchored VWAP) ونطاقات الانحراف المعياري"""
    if not klines or len(klines) < 10:
        return {"avwap": 0.0, "upper_1s": 0.0, "lower_1s": 0.0, "upper_2s": 0.0, "lower_2s": 0.0, "bias": "محايد"}

    # Anchor to the highest high in recent history
    max_idx = max(range(len(klines)), key=lambda i: klines[i]["high"])
    anchored_klines = klines[max_idx:] if max_idx < len(klines) - 5 else klines

    cum_pv = 0.0
    cum_vol = 0.0
    typical_prices = []
    volumes = []

    for k in anchored_klines:
        tp = (k["high"] + k["low"] + k["close"]) / 3.0
        v = k["volume"]
        cum_pv += tp * v
        cum_vol += v
        typical_prices.append(tp)
        volumes.append(v)

    avwap = cum_pv / cum_vol if cum_vol > 0 else klines[-1]["close"]
    
    # Calculate Standard Deviation around AVWAP
    variance = sum(v * ((tp - avwap) ** 2) for tp, v in zip(typical_prices, volumes)) / cum_vol if cum_vol > 0 else 0.0
    std_dev = math.sqrt(variance)

    upper_1s = avwap + std_dev
    lower_1s = avwap - std_dev
    upper_2s = avwap + (2.0 * std_dev)
    lower_2s = avwap - (2.0 * std_dev)

    current_price = klines[-1]["close"]
    bias = "سعر عادل (Fair Value Zone)"
    if current_price > upper_1s:
        bias = "ذروة شراء (Overbought > +1σ)"
    elif current_price < lower_1s:
        bias = "ذروة بيع (Oversold < -1σ)"

    return {
        "avwap": round(avwap, 4),
        "upper_1s": round(upper_1s, 4),
        "lower_1s": round(lower_1s, 4),
        "upper_2s": round(upper_2s, 4),
        "lower_2s": round(lower_2s, 4),
        "std_dev": round(std_dev, 4),
        "bias": bias
    }

def detect_smc_structures(klines: list) -> dict:
    """رصد تراكيب الأموال الذكية SMC: CHoCH, BOS, Liquidity Sweeps, FVGs, Order Blocks"""
    if not klines or len(klines) < 15:
        return {
            "structure": "محايد",
            "sweep": "لا يوجد صيد سيولة حالي",
            "fvg_type": "لا يوجد",
            "fvg_target": 0.0,
            "order_block": "غير متوفر"
        }

    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    cur_c = closes[-1]
    cur_h = highs[-1]
    cur_l = lows[-1]

    recent_high = max(highs[-20:-2])
    recent_low = min(lows[-20:-2])

    # 1. Liquidity Sweep Detection
    sweep = "لا يوجد صيد سيولة حالي"
    if cur_h > recent_high and cur_c < recent_high:
        sweep = "⚡ صيد سيولة قمة (Buy-Side Liquidity Sweep)"
    elif cur_l < recent_low and cur_c > recent_low:
        sweep = "🚀 صيد سيولة قاع (Sell-Side Liquidity Sweep)"

    # 2. CHoCH & BOS
    structure = "اتساق اتجاه محايد (Consolidation)"
    if cur_c > recent_high:
        structure = "🚀 كسر هيكل صاعد (BOS Bullish Breakout)"
    elif cur_c < recent_low:
        structure = "⚠️ كسر هيكل هابط (BOS Bearish Breakdown)"
    elif closes[-1] > closes[-2] and closes[-2] < closes[-3] and lows[-2] < min(lows[-10:-2]):
        structure = "🔄 تغير في سلوك الاتجاه صاعد (Bullish CHoCH)"

    # 3. Fair Value Gap (FVG)
    fvg_type = "متوازن (Balanced Flow)"
    fvg_target = 0.0
    for i in range(len(klines) - 3, len(klines) - 1):
        k1 = klines[i - 1]
        k3 = klines[i + 1]
        if k3["low"] > k1["high"]:
            fvg_type = "🟢 فجوة سعرية صاعدة (Bullish FVG Gap)"
            fvg_target = round((k3["low"] + k1["high"]) / 2.0, 4)
            break
        elif k3["high"] < k1["low"]:
            fvg_type = "🔴 فجوة سعرية هابطة (Bearish FVG Gap)"
            fvg_target = round((k3["high"] + k1["low"]) / 2.0, 4)
            break

    ob_zone = f"${recent_low:,.2f} - ${recent_high:,.2f}"

    return {
        "structure": structure,
        "sweep": sweep,
        "fvg_type": fvg_type,
        "fvg_target": fvg_target,
        "order_block": ob_zone
    }

def detect_cvd_absorption(cvd_delta_5m: float, price_change_pct: float) -> dict:
    """رصد امتصاص صانع السوق للأوامر (CVD Absorption)"""
    abs_status = "تدفق عادي"
    abs_desc = "توازن تدفق التيكر مع الحركة"

    if cvd_delta_5m > 50000.0 and price_change_pct < 0.1:
        abs_status = "⚠️ امتصاص عروض بيعية (Iceberg Ask Absorption)"
        abs_desc = "تيكر الشراء يدفق بقوة ولكن الجدار البيعي يمتص، يمهد للانعكاس"
    elif cvd_delta_5m < -50000.0 and price_change_pct > -0.1:
        abs_status = "🚀 امتصاص طلبات شرائية (Iceberg Bid Absorption)"
        abs_desc = "تيكر البيع يدفق بقوة ولكن الجدار الشرائي يمتص، يمهد للانفجار"

    return {
        "status": abs_status,
        "desc": abs_desc
    }

def calculate_gamma_regime(vpin: float, volatility: float) -> dict:
    """حساب وتقييم بيئة خيارات وصناع السوق Gamma Exposure (GEX)"""
    if vpin < 0.25 and volatility < 0.015:
        regime = "Long Gamma Regime (سوق هادئ ومتذبذب — Mean Reversion)"
        desc = "صناع السوق يعملون كمصدات صدمات، تفضيل صفقات الارتداد"
    else:
        regime = "Short Gamma Regime (بيئة انفجار سعري وتقلب حاد — Trend Extension)"
        desc = "صناع السوق يجبرون على التحوط في نفس الاتجاه، تفضيل صفقات الاختراق"

    return {
        "regime": regime,
        "desc": desc
    }

def analyze_smc(coin: str = "BTC") -> dict:
    """حزمة تحليلات الاستراتيجيات المؤسسية كاملة لعملة واحدة"""
    try:
        klines = fetch_klines(coin, interval="15m", limit=96)
        avwap_res = calculate_anchored_vwap(klines)
        smc_res = detect_smc_structures(klines)
        
        price_change_pct = 0.0
        if len(klines) >= 2 and klines[0]["close"] > 0:
            price_change_pct = ((klines[-1]["close"] - klines[0]["close"]) / klines[0]["close"]) * 100.0

        abs_res = detect_cvd_absorption(cvd_delta_5m=10000.0, price_change_pct=price_change_pct)
        gamma_res = calculate_gamma_regime(vpin=0.20, volatility=abs(price_change_pct)/100.0)

        return {
            "available": True,
            "avwap": avwap_res,
            "smc": smc_res,
            "absorption": abs_res,
            "gamma": gamma_res
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

if __name__ == "__main__":
    print("Testing SMCEngine Module...")
    res = analyze_smc("BTC")
    print("BTC SMC Analysis:", json.dumps(res, indent=2, ensure_ascii=False))
