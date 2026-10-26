import os
import sys

# إضافة المسار المحلي للمكتبات (بايثون 3.11)
local_lib = os.path.join(os.getcwd(), "Lib_311")
if os.path.exists(local_lib) and local_lib not in sys.path:
    pass # sys.path.insert(0, local_lib)

sys.path.append(os.getcwd())
import time
import logging
from datetime import datetime, timedelta
import argparse

import json

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def save_json(data, out_dir, symbol):
    timestamp = int(time.time() * 1000)
    file_path = os.path.join(out_dir, f"{symbol}_snapshot_{timestamp}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return file_path

from binance_client import collect_snapshot

LOCK_FILE = "scheduler_fetch.lock"

def acquire_lock(logger):
    """
    Ensures only one instance of the fetch scheduler is running.
    """
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            
            import subprocess
            result = subprocess.run(f'tasklist /FI "PID eq {pid}"', capture_output=True, text=True)
            
            if str(pid) in result.stdout:
                logger.error(f"Fetch Scheduler is already running (PID: {pid}). Exiting new instance.")
                print(f"Fetch Scheduler is already running with PID {pid}. Exiting.")
                sys.exit(1)
            else:
                logger.warning(f"Found stale lock file for PID {pid}. Taking over.")
        except ValueError:
            logger.warning("Corrupt lock file found. Taking over.")
        except Exception as e:
            logger.error(f"Error checking lock file: {e}")

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

def align_next_quarter(now: datetime) -> datetime:
    minute = (now.minute // 15 + 1) * 15
    next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minute)
    return next_run


def setup_logger(log_path: str) -> logging.Logger:
    ensure_dir(os.path.dirname(log_path))
    logger = logging.getLogger("fetch_scheduler")
    logger.setLevel(logging.INFO)
    # Avoid duplicate handlers if re-imported
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def run_once(symbol: str, out_dir: str, logger: logging.Logger) -> None:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            snapshot = collect_snapshot(symbol)
            json_path = save_json(snapshot, out_dir, symbol)
            logger.info(f"Saved JSON: {json_path}")
            return # نجاح
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                logger.warning(f"Attempt {attempt + 1} failed for {symbol}: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to fetch {symbol} after {max_retries} attempts: {e}")


def main():
    parser = argparse.ArgumentParser(description="Run standalone fetcher every 15 minutes")
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol to fetch, e.g., BTCUSDT")
    parser.add_argument("--out-dir", default=os.path.join("price_analysis", "بيانات"), help="Output directory")
    parser.add_argument("--align", action="store_false", dest="align", help="Align runs to wall-clock 00/15/30/45 minutes (Default: True)")
    parser.set_defaults(align=True)
    parser.add_argument(
        "--align-offset-minutes",
        type=int,
        default=-1,
        help="Offset minutes applied to aligned runs (Default: -1 => run at 14/29/44/59)"
    )
    args = parser.parse_args()

    ensure_dir(args.out_dir)
    logger = setup_logger(os.path.join("logs", "app_fetch.log"))
    
    acquire_lock(logger)
    
    logger.info(f"Fetch scheduler starting for {args.symbol}; out_dir={args.out_dir}")

    # تحديد أول وقت تشغيل: محاذاة مرة واحدة فقط عند البدء، ثم فواصل ثابتة 15 دقيقة
    base_run = align_next_quarter(datetime.now()) if args.align else datetime.now()
    next_run = base_run + (timedelta(minutes=args.align_offset_minutes) if args.align else timedelta())
    logger.info(f"Initial next_run={next_run}; align={args.align}; offset={args.align_offset_minutes}")

    try:
        while True:
            now = datetime.now()
            sleep_seconds = (next_run - now).total_seconds()
            if sleep_seconds > 0:
                logger.info(f"Current time={now}; next run={next_run}; sleeping {int(sleep_seconds)}s")
                time.sleep(max(1, int(sleep_seconds)))
            else:
                # إذا تأخرنا عن الوقت المجدول، لا ننام وننفذ فوراً
                logger.info(f"Current time={now}; next run={next_run}; overdue by {int(-sleep_seconds)}s — running immediately")

            logger.info(f"Running fetch at {datetime.now()} (scheduled {next_run})")
            run_once(args.symbol, args.out_dir, logger)

            # جدولة التشغيل التالي بعد 15 دقيقة من الوقت المجدول السابق مع الحفاظ على الإزاحة
            next_run = next_run + timedelta(minutes=15)
            logger.info(f"Next run scheduled at {next_run}")
    except KeyboardInterrupt:
        logger.info("Fetch scheduler stopped by user.")
    finally:
        release_lock()


if __name__ == "__main__":
    main()