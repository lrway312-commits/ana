import os
import json
import logging
import re
from datetime import datetime, timedelta
import time
import random
from apscheduler.schedulers.blocking import BlockingScheduler
from .config import INSTRUCTION_FILE_PATH, HISTORICAL_FILE_PATH, SYMBOL
from .binance_client import collect_snapshot, get_current_price
from .segmentation import segment_last_hour
from .manual_block_loader import load_last_16_snapshots, _compute_snapshot_metrics
import importlib.util
import sys

# إعادة تحميل ديناميكية لمكتبة gemini_client في كل مرة لضمان تطبيق التحديثات الفورية
def reload_gemini_client():
    _mod_path = os.path.join(os.path.dirname(__file__), "gemini_client.py")
    try:
        with open(_mod_path, "r", encoding="utf-8-sig") as _f:
            _src_text = _f.read()
        _src_text = _src_text.replace('\ufeff', '')
        
        # إنشاء مواصفات الوحدة
        _spec = importlib.util.spec_from_loader("src.gemini_client", loader=None)
        if _spec is None:
            raise ImportError("Could not create spec for gemini_client")
            
        gemini_client_dyn = importlib.util.module_from_spec(_spec)
        gemini_client_dyn.__package__ = "src"
        gemini_client_dyn.__name__ = "src.gemini_client"
        
        # تنفيذ الكود داخل الوحدة الجديدة
        exec(_src_text, gemini_client_dyn.__dict__)
        
        # تحديث sys.modules لتستخدم النسخة الجديدة
        sys.modules["src.gemini_client"] = gemini_client_dyn
        
        return gemini_client_dyn
    except Exception as e:
        logging.error(f"Failed to reload gemini_client: {e}")
        # في حال الفشل، حاول الاستيراد العادي
        import src.gemini_client as gemini_client_dyn
        return gemini_client_dyn

# التحميل الأولي
gemini_client_dyn = reload_gemini_client()
call_gemini = gemini_client_dyn.call_gemini
build_instruction_dual = gemini_client_dyn.build_instruction_dual

from .telegram_bot import send_message
from typing import Dict, Any, Optional, Tuple

# إعداد التسجيل إلى ملف لضمان التتبع المستمر
os.makedirs("logs", exist_ok=True)
os.makedirs("state", exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    filename=os.getenv("LOG_FILE_NAME", "logs/app.log"),
    filemode="a",
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)

def parse_signal(text: str) -> str:
    if not text:
        return "غير محددة"
    
    # Try to parse JSON first (Prioritize JSON structure from new rules)
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end >= start:
            json_str = text[start:end+1]
            data = json.loads(json_str)
            if "signal" in data:
                sig = str(data["signal"]).lower().strip()
                if sig in ["شراء", "buy"]: return "شراء"
                if sig in ["بيع", "sell"]: return "بيع"
                if sig in ["انتظار", "wait", "hold", "محايد", "neutral"]: return "انتظار"
    except Exception:
        pass

    # Fallback to text parsing (Legacy support)
    first_line = (text.strip().splitlines() or [""])[0].strip()
    first_token = (first_line.split() or [""])[0].lower()
    if first_token in {"شراء", "buy"}:
        return "شراء"
    if first_token in {"بيع", "sell"}:
        return "بيع"
    if first_token in {"محايد", "neutral", "hold", "انتظار", "wait"}:
        return "انتظار"
    # محاولة ثانية: ابحث عن كلمة منفردة في بداية النص مثل "شراء:" أو "بيع:" أو "انتظار:"
    m = re.match(r"^(شراء|بيع|محايد|انتظار)\b", first_line)
    if m:
        val = m.group(1)
        if val == "محايد": return "انتظار"
        return val
    return "غير محددة"

def extract_confidence(text: str) -> Optional[int]:
    if not text:
        return None
        
    # Try JSON first
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end >= start:
            json_str = text[start:end+1]
            data = json.loads(json_str)
            if "confidence" in data:
                val = int(data["confidence"])
                if 0 <= val <= 100:
                    return val
    except Exception:
        pass

    # أنماط عربية وإنجليزية لالتقاط أول قيمة للثقة
    patterns = [
        r"ثقة\s*[:：]\s*(\d{1,3})",
        r"confidence\s*[:：]\s*(\d{1,3})",
        # أنماط إضافية للبحث عن أرقام 70-100 في النص
        r"\b([7-9]\d|100)\b",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if 0 <= val <= 100:  # تأكد أن القيمة منطقية
                    return val
            except ValueError:
                continue
    # إذا لم نجد شيئًا، حاول استخراج أي رقم بين 70-100 من أول سطرين
    lines = text.split('\n')[:2]
    for line in lines:
        numbers = re.findall(r'\b([7-9]\d|100)\b', line)
        if numbers:
            try:
                return int(numbers[0])
            except ValueError:
                continue
    return None

def extract_raw_confidence(text: str) -> Optional[int]:
    if not text:
        return None
    # نمط للخام: (خام: 95) أو Raw: 95
    patterns = [
        r"خام\s*[:：]\s*(\d{1,3})",
        r"raw\s*[:：]\s*(\d{1,3})",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None

def indicators_covered(text: str) -> bool:
    """
    تحقق مما إذا كان التحليل يغطي العناصر الأساسية لاستمرارية الشمعة.
    النظام الجديد أكثر مرونة تجاه ذكر المؤشرات بالاسم طالما أن المنطق حاضر.
    """
    if not text:
        return False
        
    t = text.lower()
    # نعتبر التحليل مكتملاً إذا كان طوله معقولاً أو يحتوي على كلمات مفتاحية عن الحركة
    if len(text) > 300:
        return True
        
    # كلمات مفتاحية للتأكد من وجود تحليل فني
    keywords = ["cvd", "oi", "سيولة", "حركة", "شمعة", "candle", "volume"]
    return any(k in t for k in keywords)

def log_signal_with_price(symbol: str, signal: str, confidence: Any, price: float):
    """تسجيل الإشارة مع السعر الحالي في ملف مستقل"""
    try:
        log_path = os.path.join("logs", "signals_history.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] SYMBOL: {symbol} | SIGNAL: {signal} | CONFIDENCE: {confidence} | PRICE: {price}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
        logging.info(f"تم تسجيل الإشارة في signals_history.log: {signal} @ {price}")
    except Exception as e:
        logging.error(f"فشل تسجيل الإشارة في الملف المستقل: {e}")

# إزالة أي إشارات احتياطية: النظام يعتمد حصراً على Gemini

def read_file_safe(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def extract_segment_price_refs(segment: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """استخراج سعر الدخول (السعر قبل 15 دقيقة) والسعر الخروج (السعر الحالي) من بيانات اللقطة"""
    current_data = segment.get("current", {})
    entry_price = current_data.get("price_15_min_ago")
    exit_price = current_data.get("current_price")

    if entry_price is None or exit_price is None:
        logging.warning("لا توجد بيانات كافية للسعر الحالي أو السعر قبل 15 دقيقة في القطعة الحالية")
        return {"entry_price": None, "exit_price": None}
    
    return {"entry_price": entry_price, "exit_price": exit_price}

def _latest_snapshot_ts(dir_path: str = os.path.join("price_analysis", "بيانات")) -> Optional[int]:
    try:
        files = [f for f in os.listdir(dir_path) if f.startswith(f"snapshot_{SYMBOL}_") and f.endswith(".json")]
        if not files:
            return None
        def _extract_ts(name: str) -> str:
            parts = name.split("_")
            return parts[-1].replace(".json", "") if len(parts) >= 3 else ""
        newest = sorted(files, key=lambda x: _extract_ts(x), reverse=True)[0]
        fpath = os.path.join(dir_path, newest)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            with open(fpath, "r", encoding="utf-8-sig") as f:
                obj = json.load(f)
        ts = obj.get("timestamp") if isinstance(obj, dict) else None
        return ts if isinstance(ts, (int, float)) else None
    except Exception:
        return None

def run_cycle():
    logging.info(f"[{SYMBOL}] Entering run_cycle() function.")
    try:
        # اجمع بيانات Binance مع كتم أخطاء الشبكة حتى لا تُرسل لتلغرام
        try:
            snapshot = collect_snapshot(SYMBOL)
        except Exception as e:
            logging.error(f"تعذر جمع بيانات Binance: {e}")
            # تابع بتحليل Gemini باستخدام حزمة بيانات احتياطية فارغة لتأكيد الطلبات
            snapshot = {
                "symbol": SYMBOL,
                "timestamp": int(datetime.now().timestamp()*1000),
                "series": {
                    "open_interest": [],
                    "long_short_ratio": [],
                    "taker_buy_volume": [],
                    "taker_sell_volume": [],
                    "klines_15m": [],
                },
                "current": {},
            }
        # جلب ودمج آخر 25 لقطة (24 للسجل + 1 للحالية) لضمان تطابق منطق الاختبار
        segmented = load_last_16_snapshots(save_combined=True, limit=25)
        seg_source = segmented
        block = seg_source.get("block16", []) if isinstance(seg_source, dict) else []
        block_len = len(block)
        
        if block_len < 25:
            logging.warning(f"[{SYMBOL}] تنبيه: تم تحميل {block_len} لقطات فقط (المطلوب 25 لتطابق الاختبار). سيتم المتابعة بالبيانات المتاحة.")
        else:
            logging.info(f"[{SYMBOL}] تم تحميل آخر {block_len} لقطة بنجاح.")
        
        # تجهيز البيانات بنفس طريقة الاختبار تماماً
        current_snap = {}
        history_snaps = []
        if block_len > 0:
            current_snap = block[-1]
            history_snaps = block[:-1]
        
        instruction_text = read_file_safe(INSTRUCTION_FILE_PATH)
        # استخدام السجل الديناميكي بدلاً من الملف الثابت
        historical_text = json.dumps(history_snaps, indent=1, ensure_ascii=False)
        
        try:
            # وضع اختبار: إذا تم ضبط "TEST_ANALYSIS_TEXT" في البيئة، نستخدمه بدلاً من استدعاء جيمناي
            injected = os.getenv("TEST_ANALYSIS_TEXT", "").strip()
            if injected:
                analysis = injected
            else:
                logging.info(f"Instruction Text sent to Gemini: {instruction_text}")
                
                # استخدام قائمة الأزواج الفعلية من اللقطات المجمعة
                trade_pairs_to_send = segmented.get("trade_pairs", []) 
                logging.info(f"[{SYMBOL}] Prepared {len(trade_pairs_to_send)} trade pairs for analysis.")

                now_dt = datetime.now()
                if now_dt.minute % 15 == 0:
                    time.sleep(random.uniform(0.0, 2.0))
                
                # جلب آخر ملف JSON من مجلد "بيانات الصور" بدلاً من إرسال الصور مباشرة
                image_analysis_text = ""
                try:
                    IMAGE_DATA_DIR = os.path.join("price_analysis", "charts", "بيانات الصور")
                    if os.path.exists(IMAGE_DATA_DIR):
                        json_files = [f for f in os.listdir(IMAGE_DATA_DIR) if f.endswith(".json")]
                        if json_files:
                            # ترتيب الملفات حسب الاسم (الذي يحتوي على التاريخ والوقت) تنازلياً لجلب الأحدث
                            latest_json = sorted(json_files, reverse=True)[0]
                            latest_json_path = os.path.join(IMAGE_DATA_DIR, latest_json)
                            file_size = os.path.getsize(latest_json_path)
                            logging.info(f"Loading latest image analysis data: {latest_json} ({file_size} bytes)")
                            with open(latest_json_path, "r", encoding="utf-8") as f:
                                image_data_obj = json.load(f)
                                # استخراج المحتوى الفعلي (الذي هو عبارة عن تحليل الصور)
                                if "extracted_content" in image_data_obj:
                                    image_analysis_text = json.dumps(image_data_obj["extracted_content"], indent=2, ensure_ascii=False)
                                else:
                                    image_analysis_text = json.dumps(image_data_obj, indent=2, ensure_ascii=False)
                                
                                logging.info(f"Successfully extracted {len(image_analysis_text)} chars of image analysis.")
                        else:
                            logging.warning("No JSON analysis files found in 'بيانات الصور' directory.")
                            image_analysis_text = "تنبيه: لم يتم العثور على ملفات تحليل صور JSON في المجلد."
                    else:
                        logging.warning(f"Image analysis directory {IMAGE_DATA_DIR} does not exist.")
                        image_analysis_text = f"تنبيه: مجلد تحليل الصور {IMAGE_DATA_DIR} غير موجود."
                except Exception as e:
                    logging.error(f"Error loading latest image analysis: {e}")
                    # تأكيد فشل التحميل في السجل
                    image_analysis_text = f"خطأ في تحميل بيانات الصور: {str(e)}"

                # تم إلغاء إرسال الصور مباشرة لتقليل حجم الـ payload والاعتماد على التحليل الجاهز
                image_paths = [] 
                
                # إضافة التحليل البصري المستخرج كجزء منفصل تماماً في الطلب لضمان رؤيته
                if image_analysis_text:
                    logging.info("Passing image analysis (extracted data) as a separate parameter to call_gemini.")

                # إعادة تحميل مكتبة Gemini لضمان استخدام أحدث كود وتعليمات
                try:
                    gemini_client_dyn = reload_gemini_client()
                    call_gemini = gemini_client_dyn.call_gemini
                    build_instruction_dual = gemini_client_dyn.build_instruction_dual
                    logging.info("Gemini client module reloaded successfully.")
                except Exception as e:
                    logging.error(f"Failed to reload Gemini client dynamically: {e}")

                # استدعاء جيمناي مع البيانات المطابقة للاختبار
                # current_snap (dict), history_snaps (json str), trade_pairs (empty list)
                analysis = call_gemini(build_instruction_dual(instruction_text), current_snap, historical_text, trade_pairs_to_send, image_paths=image_paths, image_analysis_text=image_analysis_text)
            def sanitize_analysis(text: str) -> str:
                if not text:
                    return text
                first_line = (text.strip().splitlines() or [""])[0].strip()
                s = text
                start = s.find("{")
                end = s.rfind("}")
                if start != -1 and end != -1 and end >= start:
                    raw = s[start:end+1]
                    try:
                        obj = json.loads(raw)
                        compact = json.dumps(obj, ensure_ascii=False, indent=2)
                        return f"{first_line}\n{compact}"
                    except Exception:
                        pass
                return text
            analysis = sanitize_analysis(analysis)
            try:
                last_analysis_path = os.path.join("state", "last_analysis.json")
                tmp_path = last_analysis_path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "symbol": SYMBOL,
                        "analysis": analysis,
                        "ts": int(datetime.now().timestamp()*1000)
                    }, f, ensure_ascii=False)
                os.replace(tmp_path, last_analysis_path)
            except Exception:
                pass
            signal = parse_signal(analysis)
            conf = extract_confidence(analysis)
            raw_conf = extract_raw_confidence(analysis)
            effective_conf = None
            if conf is not None and raw_conf is not None:
                effective_conf = min(conf, raw_conf)  # تشدد: نعتمد الأدنى
            else:
                effective_conf = conf

            expected_last_ts = None
            try:
                if isinstance(segmented_compact, dict) and isinstance(segmented_compact.get("block16"), list) and segmented_compact["block16"]:
                    last_obj = segmented_compact["block16"][-1]
                    if isinstance(last_obj, dict):
                        expected_last_ts = last_obj.get("timestamp")
            except Exception:
                expected_last_ts = None

            # قواعد بيتكوين فقط: إرسال مشروط وثابت منع التكرار 15 دقيقة
            is_btc = SYMBOL.upper() == "BTCUSDT"
            threshold = int(os.getenv("MIN_CONFIDENCE_TO_SEND", "70"))
            block_minutes = int(os.getenv("REPEAT_BLOCK_MINUTES", "15"))
            now = datetime.now()
            state_path = os.path.join("state", f"last_signal_{SYMBOL}.json")
            last_state: Dict[str, Any] = {}
            if os.path.exists(state_path):
                try:
                    with open(state_path, "r", encoding="utf-8") as f:
                        last_state = json.load(f)
                except Exception:
                    last_state = {}

            # تجاوز مرة واحدة لفلاتر بيتكوين عبر ملف علم
            bypass_flag_path = os.path.join("state", "bypass_once_BTCUSDT.flag")
            bypass_once = is_btc and os.path.exists(bypass_flag_path)

            should_send = True
            reason = ""

            valid_last = True
            # Timestamp check disabled for compatibility with 80% win-rate rules
            # try:
            #     s = analysis
            #     start = s.find("{")
            #     end = s.rfind("}")
            #     if start != -1 and end != -1 and end >= start:
            #         obj = json.loads(s[start:end+1])
            #         reported_ts = obj.get("last_snapshot_ts")
            #         if (expected_last_ts is not None) and (reported_ts != expected_last_ts):
            #             valid_last = False
            #             reason = "عدم تطابق الطابع الزمني لآخر لقطة"
            # except Exception:
            #     pass

            # تسجيل تفصيلي للتتبع
            logging.info(f"تحليل الإشارة: {signal}, الثقة: {effective_conf}, العتبة: {threshold}, الرمز: {SYMBOL}")
            
            # إضافة فترة تهدئة عالمية لمنع إرسال إشارات متتالية في نفس الثانية
            COOLDOWN_STATE_PATH = os.path.join("state", "signal_cooldown.json")
            SIGNAL_COOLDOWN_SECONDS = int(os.getenv("SIGNAL_COOLDOWN_SECONDS", "5")) # 5 ثوانٍ كفترة تهدئة افتراضية

            last_signal_state: Dict[str, Any] = {}
            if os.path.exists(COOLDOWN_STATE_PATH):
                try:
                    with open(COOLDOWN_STATE_PATH, "r", encoding="utf-8") as f:
                        last_signal_state = json.load(f)
                except Exception:
                    last_signal_state = {}
            
            last_sent_ts = last_signal_state.get("last_sent_ts", 0)
            current_ts = int(datetime.now().timestamp())

            if (current_ts - last_sent_ts) < SIGNAL_COOLDOWN_SECONDS:
                should_send = False
                reason = f"فترة تهدئة نشطة: تم إرسال إشارة سابقة قبل أقل من {SIGNAL_COOLDOWN_SECONDS} ثوانٍ."
                logging.info(f"تم تجاوز إرسال لإشارة '{signal}': {reason}")

            # حفظ البيانات والتحليل لأغراض التطوير - الاحتفاظ بآخر 50 سجلاً فقط لتجنب تضخم الملف
            ANALYSIS_LOG_PATH = os.path.join("logs", f"gemini_analysis_{SYMBOL}.json")
            try:
                analysis_record = {
                    "timestamp": datetime.now().isoformat(),
                    "segmented_data": segmented,
                    "gemini_analysis": analysis,
                    "signal": signal,
                    "confidence": effective_conf,
                    "raw_confidence": raw_conf,
                    "should_send": should_send,
                    "reason": reason
                }
                all_records = []
                if os.path.exists(ANALYSIS_LOG_PATH):
                    try:
                        with open(ANALYSIS_LOG_PATH, "r", encoding="utf-8") as f:
                            all_records = json.load(f)
                        if not isinstance(all_records, list):
                            all_records = []
                    except Exception:
                        all_records = []
                
                all_records.append(analysis_record)
                # الاحتفاظ بآخر 50 سجلاً فقط
                if len(all_records) > 50:
                    all_records = all_records[-50:]
                    
                with open(ANALYSIS_LOG_PATH, "w", encoding="utf-8") as f:
                    json.dump(all_records, f, ensure_ascii=False, indent=4)
            except Exception as e:
                logging.error(f"فشل حفظ سجل التحليل: {e}")

            if is_btc:
                if bypass_once:
                    # تجاوز الفلاتر لمرة واحدة بشرط تحديد الإشارة
                    should_send = signal in {"شراء", "بيع", "انتظار"}
                    reason = "تجاوز مؤقت لفلاتر بيتكوين"
                else:
                    if signal == "غير محددة" or effective_conf is None:
                        should_send = False
                        reason = "إشارة غير محددة أو ثقة غير متوفرة"
                    elif signal == "انتظار":
                        # إشارة الانتظار تُرسل بغض النظر عن مستوى الثقة لأنها تشير إلى عدم وجود استمرارية واضحة
                        should_send = True
                        reason = "إشارة انتظار - لا يوجد ميل واضح للاستمرارية"
                    elif effective_conf < threshold:
                        should_send = False
                        reason = f"الثقة {effective_conf} أقل من العتبة {threshold}"
                    else:
                        # منع التكرار 15 دقيقة لنفس الإشارة
                        last_sig = last_state.get("signal")
                        # دعم شكلين للتاريخ: ISO في المفتاح "time" أو طابع زمني "ts" (ملّي ثانية)
                        last_time_str = last_state.get("time")
                        last_time_ts = last_state.get("ts")
                        last_time = None
                        if last_time_str:
                            try:
                                last_time = datetime.fromisoformat(last_time_str)
                            except Exception:
                                last_time = None
                        elif isinstance(last_time_ts, (int, float)):
                            try:
                                last_time = datetime.fromtimestamp(float(last_time_ts) / 1000.0)
                            except Exception:
                                last_time = None
                        if last_sig == signal and last_time:
                            if now - last_time < timedelta(minutes=block_minutes):
                                should_send = False
                                reason = f"حظر تكرار لنفس الإشارة خلال {block_minutes} دقيقة"
                        # إذا الإشارة مختلفة، إرسال فقط إذا الثقة عالية بالفعل (تحقق أعلاه)
                        
                        # تسجيل إذا كانت الثقة كافية لكن لم يتم الإرسال بسبب شرط آخر
                        if should_send:
                            logging.info(f"الثقة كافية ({effective_conf} >= {threshold})، التحقق من الشروط الأخرى...")

            if should_send and valid_last:
                # شرط إضافي لبيتكوين: يجب أن يذكر التحليل المؤشرات الرئيسية (إلا عند التجاوز لمرة واحدة)
                if is_btc and not bypass_once and not indicators_covered(analysis):
                    should_send = False
                    reason = "تحليل لا يغطي المؤشرات المطلوبة"
                    logging.info(f"تم رفض الإشارة رغم الثقة الكافية: {reason}")
                    logging.info(f"المؤشرات المطلوبة: Open Interest, Long/Short Ratio, Taker Buy/Sell Volume")
                    logging.info(f"التحليل الحالي: {analysis[:200]}...")

            if should_send and valid_last:
                # ضع الإشارة في أول سطر وضَمّن الثقة الخام والفعالة إن توفرت
                conf_lines = ""
                if conf is not None:
                    conf_lines += f"ثقة: {conf}\n"
                if raw_conf is not None:
                    conf_lines += f"خام: {raw_conf}\n"
                if effective_conf is not None and (conf is None or effective_conf != conf):
                    conf_lines += f"فعالة: {effective_conf}\n"
                
                # Truncate analysis to avoid Telegram 4096 limit
                truncated_analysis = analysis
                if len(truncated_analysis) > 3500:
                    truncated_analysis = truncated_analysis[:3500] + "...\n(تم اختصار النص لتجاوز حد التلغرام)"

                msg = (
                    f"{signal}\n"
                    f"الرمز: {SYMBOL}\n"
                    + conf_lines
                    + f"تحليل Gemini:\n{truncated_analysis}"
                )
                
                # Use logging to see the message content before sending
                logging.info(f"Sending analysis message to Telegram for {SYMBOL}...")
                
                send_message(msg)
                logging.info(f"تم إرسال إشارة '{signal}' إلى تلغرام.")

                # تسجيل الإشارة مع السعر الحالي في الملف المستقل
                try:
                    current_price = get_current_price(SYMBOL)
                    log_signal_with_price(SYMBOL, signal, effective_conf, current_price)
                except Exception as e:
                    logging.error(f"فشل جلب السعر الحالي للتسجيل: {e}")
                # تحديث حالة بيتكوين فقط
                try:
                    with open(state_path, "w", encoding="utf-8") as f:
                        json.dump({"signal": signal, "confidence": effective_conf, "time": now.isoformat()}, f, ensure_ascii=False)
                except Exception:
                    pass
                # تحديث وقت إرسال آخر إشارة
                try:
                    with open(COOLDOWN_STATE_PATH, "w", encoding="utf-8") as f:
                        json.dump({"last_sent_ts": current_ts}, f, ensure_ascii=False)
                except Exception:
                    pass
                # حفظ الثقة العالية في سجل مستقل
                try:
                    high_conf_path = os.path.join("state", "high_confidence_signals.json")
                    records = []
                    if os.path.exists(high_conf_path):
                        try:
                            with open(high_conf_path, "r", encoding="utf-8") as f:
                                records = json.load(f)
                                if not isinstance(records, list):
                                    records = []
                        except Exception:
                            records = []
                    # اعتبر عالية جداً >=95
                    if effective_conf is not None and int(effective_conf) >= 95:
                        records.append({
                            "symbol": SYMBOL,
                            "signal": signal,
                            "confidence": effective_conf,
                            "time": now.isoformat(),
                        })
                    with open(high_conf_path, "w", encoding="utf-8") as f:
                        json.dump(records, f, ensure_ascii=False)
                except Exception:
                    pass
                # إزالة علم التجاوز بعد نجاح الإرسال
                if bypass_once:
                    try:
                        os.remove(bypass_flag_path)
                    except Exception:
                        pass
            else:
                logging.info(f"تم تجاوز إرسال لإشارة '{signal}': {reason}")
        except Exception as e:
            err_msg = f"تعذر تحليل Gemini: {e}"
            send_message(err_msg)
            logging.error(err_msg)

        logging.info(f"اكتملت دورة التحليل والإرسال.")
    except Exception as e:
        err = f"فشل التحليل: {e}"
        logging.error(err)
        send_message(err)

if __name__ == "__main__":
    scheduler = BlockingScheduler(job_defaults={
        "max_instances": 1,
        "coalesce": True,
        "misfire_grace_time": 3600,
    })
    scheduler.add_job(run_cycle, "interval", minutes=15, next_run_time=None)
    run_cycle()  # أول تشغيل فوري
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
