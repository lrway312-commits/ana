"""
run_capture_scheduler.py - المجدول الرئيسي للتقاط وتحليل الرسوم البيانية
يعمل كل 30 دقيقة: يلتقط الصور ثم يحللها بالذكاء الاصطناعي
"""
import os
import sys
import time
import logging
import asyncio
from datetime import datetime, timedelta

# ضبط المسارات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# إعداد السجل
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "logs", "capture_scheduler.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CaptureScheduler")

CHARTS_DIR = os.path.join(BASE_DIR, "price_analysis", "charts")
LOCK_FILE = os.path.join(BASE_DIR, "scheduler_capture.lock")


def acquire_lock():
    """التحقق من عدم وجود نسخة أخرى تعمل وتأمين القفل"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())

            import subprocess
            result = subprocess.run(f'tasklist /FI "PID eq {pid}"', capture_output=True, text=True, shell=True)
            if str(pid) in result.stdout:
                logger.error(f"Capture Scheduler is already running (PID: {pid}). Exiting duplicate instance.")
                sys.exit(1)
            else:
                logger.warning(f"Found stale lock file for PID {pid}. Taking over.")
        except ValueError:
            logger.warning("Corrupt lock file found. Taking over.")
        except Exception as e:
            logger.warning(f"Error checking lock file: {e}")

    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Could not write lock file: {e}")
        sys.exit(1)


def release_lock():
    """تحرير ملف القفل عند الإغلاق"""
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass


# استيراد الوحدات
def import_modules():
    """استيراد المكتبات بشكل ديناميكي مع دعم المسارات المختلفة"""
    capture_module = None
    analyze_module = None

    # البحث عن capture_charts.py
    possible_capture_paths = [
        os.path.join(BASE_DIR, "price_analysis", "بيانات", "capture_charts.py"),
        os.path.join(BASE_DIR, "src", "capture_charts.py"),
        os.path.join(BASE_DIR, "capture_charts.py"),
    ]

    for path in possible_capture_paths:
        if os.path.exists(path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("capture_charts", path)
            capture_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(capture_module)
            logger.info(f"Loaded capture_charts from: {path}")
            break

    # البحث عن analyze_charts.py
    possible_analyze_paths = [
        os.path.join(BASE_DIR, "price_analysis", "بيانات", "analyze_charts.py"),
        os.path.join(BASE_DIR, "src", "analyze_charts.py"),
        os.path.join(BASE_DIR, "analyze_charts.py"),
    ]

    for path in possible_analyze_paths:
        if os.path.exists(path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("analyze_charts", path)
            analyze_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(analyze_module)
            logger.info(f"Loaded analyze_charts from: {path}")
            break

    return capture_module, analyze_module


def cleanup_old_charts():
    """حذف الصور القديمة قبل الجولة الجديدة"""
    if not os.path.exists(CHARTS_DIR):
        return
    deleted = 0
    try:
        for fname in os.listdir(CHARTS_DIR):
            if fname.endswith(".png"):
                fpath = os.path.join(CHARTS_DIR, fname)
                try:
                    os.remove(fpath)
                    deleted += 1
                except Exception as e:
                    logger.error(f"Failed to delete {fname}: {e}")
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old chart images")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


def get_next_run_time():
    """حساب وقت التشغيل القادم (كل 30 دقيقة: الدقائق 5, 35)"""
    now = datetime.now()
    targets = [5, 35]
    for t in targets:
        if now.minute < t:
            return now.replace(minute=t, second=0, microsecond=0)
    # الساعة التالية
    return (now + timedelta(hours=1)).replace(minute=5, second=0, microsecond=0)


def run_cycle(capture_module, analyze_module, priority_max=None):
    """تنفيذ دورة كاملة: التقاط + تحليل"""
    cycle_start = time.time()
    logger.info("=" * 50)
    logger.info(f"Starting capture cycle at {datetime.now().strftime('%H:%M:%S')}")

    # 1. تنظيف الصور القديمة
    cleanup_old_charts()

    # 2. التقاط الصور
    if capture_module is None:
        logger.error("capture_charts module not loaded!")
        return False

    try:
        captured = asyncio.run(capture_module.capture_all_charts(priority_max=priority_max))
        logger.info(f"Captured {len(captured)} charts successfully")
    except Exception as e:
        logger.error(f"Capture failed: {e}")
        return False

    # 3. تحليل الصور بالذكاء الاصطناعي (إن وُجد)
    if analyze_module is not None:
        try:
            logger.info("Starting AI analysis of captured charts...")
            analysis = analyze_module.analyze_all_charts()
            if analysis and "consolidated" in analysis:
                sig = analysis["consolidated"]
                logger.info(
                    f"📊 SIGNAL: {sig.get('final_signal','?')} | "
                    f"Confidence: {sig.get('confidence','?')} | "
                    f"Strength: {sig.get('signal_strength_pct','?')}%"
                )
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
    else:
        logger.warning("analyze_charts module not loaded - skipping AI analysis")


    # 4. رفع لقطات الشارتات تلقائياً إلى GitHub
    try:
        from src.github_uploader import upload_charts_dir_async
        upload_charts_dir_async(CHARTS_DIR, remote_folder="اللقطات الحية/charts")
        logger.info("📤 Triggered async upload of captured charts to GitHub (اللقطات الحية/charts)")
    except Exception as up_err:
        logger.warning(f"Failed to trigger charts upload to GitHub: {up_err}")

    elapsed = time.time() - cycle_start
    logger.info(f"Cycle completed in {elapsed:.1f}s")
    return True



def main():
    acquire_lock()
    try:
        logger.info("🚀 Capture & Analysis Scheduler started")
        logger.info(f"Schedule: every 30 minutes (at :05, :35)")
        logger.info(f"Charts directory: {CHARTS_DIR}")

        # تحميل الوحدات
        capture_module, analyze_module = import_modules()
        if capture_module is None:
            logger.error("❌ FATAL: capture_charts.py not found! Check file paths.")
            return

        # تشغيل فوري عند البدء (priority_max=3 للبيانات الأكثر أهمية فقط)
        logger.info("Running immediate first cycle (high-priority charts only)...")
        try:
            run_cycle(capture_module, analyze_module, priority_max=3)
        except Exception as e:
            logger.error(f"First cycle error: {e}")

        # الحلقة الرئيسية
        while True:
            next_run = get_next_run_time()
            sleep_secs = max(0, (next_run - datetime.now()).total_seconds())

            logger.info(f"⏰ Next cycle at {next_run.strftime('%H:%M')} (in {sleep_secs:.0f}s)")
            time.sleep(sleep_secs)

            try:
                # في الدورات الكاملة، نأخذ جميع الصور
                run_cycle(capture_module, analyze_module, priority_max=None)
            except Exception as e:
                logger.error(f"Cycle error: {e}")

            time.sleep(3)  # تجنب الحلقات المتكررة
    finally:
        release_lock()


if __name__ == "__main__":
    main()

