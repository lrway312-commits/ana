import os
import sys
import time
import logging
import json
import argparse
from datetime import datetime, timedelta

# إضافة مسار الكود المصدري
sys.path.append(r"c:\Users\Public")
from src.binance_client import collect_snapshot

LOCK_FILE = "scheduler_live_fetch.lock"

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def save_live_json(data, out_dir, symbol):
    # حفظ في ملف واحد ثابت واستبدال السابقة كما طلب المستخدم
    file_path = os.path.join(out_dir, f"{symbol}_live.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return file_path

def acquire_lock(logger):
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            
            import subprocess
            result = subprocess.run(f'tasklist /FI "PID eq {pid}"', capture_output=True, text=True)
            
            if str(pid) in result.stdout:
                logger.error(f"Live Fetcher is already running (PID: {pid}). Exiting.")
                print(f"Live Fetcher is already running with PID {pid}. Exiting.")
                sys.exit(1)
            else:
                logger.warning(f"Found stale lock file for PID {pid}. Taking over.")
        except Exception as e:
            logger.warning(f"Lock file check error: {e}. Taking over.")

    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Could not write lock file: {e}")
        sys.exit(1)

def release_lock():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass

def setup_logger(log_path: str) -> logging.Logger:
    ensure_dir(os.path.dirname(log_path))
    logger = logging.getLogger("live_fetcher")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def run_once(symbol: str, out_dir: str, logger: logging.Logger) -> None:
    try:
        snapshot = collect_snapshot(symbol)
        json_path = save_live_json(snapshot, out_dir, symbol)
        logger.info(f"Updated live JSON: {json_path}")
    except Exception as e:
        logger.error(f"Failed to fetch live data for {symbol}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Run live fetcher every 1 minute")
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol to fetch")
    parser.add_argument("--out-dir", default=os.path.join("price_analysis", "بيانات"), help="Output directory")
    args = parser.parse_args()

    ensure_dir(args.out_dir)
    logger = setup_logger(os.path.join("logs", "live_fetch.log"))
    
    acquire_lock(logger)
    logger.info(f"Live fetcher starting for {args.symbol}")

    try:
        while True:
            now = datetime.now()
            # الحساب للدقيقة القادمة (ثانية 0)
            next_run = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
            
            # تنفيذ فوري لأول مرة
            run_once(args.symbol, args.out_dir, logger)
            
            sleep_seconds = (next_run - datetime.now()).total_seconds()
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("Live fetcher stopped.")
    finally:
        release_lock()

if __name__ == "__main__":
    main()
