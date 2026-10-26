import time
import json
import os
import websocket
import logging
from pathlib import Path
from datetime import datetime, timedelta

# إعداد التسجيل
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join("logs", "liquidation_websocket.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("liquidation_collector")

DATA_FILE = Path("liquidation_data.json")

def clean_old_records(records, max_age_minutes=60):
    """حذف السجلات الأقدم من 60 دقيقة لتجنب تضخم الملف"""
    cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
    cutoff_timestamp = int(cutoff_time.timestamp() * 1000)
    return [r for r in records if r.get("timestamp", 0) > cutoff_timestamp]

def save_records(records):
    """حفظ السجلات بشكل آمن عبر استبدال ذري للملف"""
    try:
        temp_file = DATA_FILE.with_suffix(".json.tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=4)
        # استبدال ذري للملف لتجنب القراءة الجزئية أثناء التحديث
        temp_file.replace(DATA_FILE)
    except Exception as e:
        logger.error(f"Error saving liquidation records: {e}")

def load_records():
    """تحميل السجلات الحالية من الملف"""
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading liquidation records, starting fresh: {e}")
        return []

def on_message(ws, message):
    try:
        data = json.loads(message)
        event_type = data.get("e")
        
        if event_type == "forceOrder":
            order_data = data.get("o", {})
            symbol = order_data.get("s")
            
            # نحن مهتمون فقط بصفقات تصفية البيتكوين
            if symbol == "BTCUSDT":
                side = order_data.get("S")
                order_type = order_data.get("o")
                quantity = float(order_data.get("q", 0.0))
                price = float(order_data.get("p", 0.0))
                avg_price = float(order_data.get("ap", 0.0))
                status = order_data.get("X")
                filled_qty = float(order_data.get("z", 0.0))
                timestamp = order_data.get("T")
                
                record = {
                    "symbol": symbol,
                    "side": side,
                    "order_type": order_type,
                    "quantity": quantity,
                    "price": price,
                    "average_price": avg_price,
                    "status": status,
                    "filled_quantity": filled_qty,
                    "timestamp": timestamp
                }
                
                logger.info(f"⚡ Liquidation Captured: {side} {quantity} BTC @ {price}")
                
                # تحميل وتحديث وحفظ
                records = load_records()
                records.append(record)
                records = clean_old_records(records)
                save_records(records)
                
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def on_error(ws, error):
    logger.error(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    logger.info("WebSocket connection closed, reconnecting...")

def on_open(ws):
    logger.info("🔌 Connected to Binance Futures Liquidation stream successfully.")

LOCK_FILE = Path("scheduler_liquidation.lock")

def acquire_lock():
    """التحقق من عدم وجود نسخة أخرى تعمل وتأمين القفل"""
    if LOCK_FILE.exists():
        try:
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            import subprocess
            result = subprocess.run(f'tasklist /FI "PID eq {pid}"', capture_output=True, text=True, shell=True)
            if str(pid) in result.stdout:
                logger.error(f"Liquidation collector is already running (PID: {pid}). Exiting.")
                sys.exit(1)
            else:
                logger.warning(f"Found stale lock file for PID {pid}. Taking over.")
        except Exception as e:
            logger.warning(f"Lock check warning: {e}. Taking over.")
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Could not write lock file: {e}")
        sys.exit(1)

def release_lock():
    """تحرير ملف القفل عند الإغلاق"""
    if LOCK_FILE.exists():
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass

def main():
    acquire_lock()
    websocket_url = "wss://fstream.binance.com/ws/!forceOrder@arr"
    logger.info(f"Starting Liquidation WebSocket Collector to {websocket_url}...")
    
    # تهيئة الملف إذا لم يكن موجوداً
    if not DATA_FILE.exists():
        save_records([])

    try:
        while True:
            try:
                ws = websocket.WebSocketApp(
                    websocket_url,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close,
                    on_open=on_open
                )
                # إرسال Ping دوري كل 20 ثانية لتجنب قطع الاتصال التلقائي وإعادة الاتصال التلقائي
                ws.run_forever(ping_interval=20, ping_timeout=10, reconnect=5)
            except KeyboardInterrupt:
                logger.info("Stopping WebSocket collector.")
                break
            except Exception as e:
                logger.error(f"Connection loop crashed: {e}, restarting in 5 seconds...")
                time.sleep(5)
    finally:
        release_lock()

if __name__ == "__main__":
    main()
