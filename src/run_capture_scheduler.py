import os
import sys

# إعادة تفعيل تحميل المكتبات من Lib_311 حصراً للتوافق مع بايثون 3.11
local_lib = os.path.join(os.getcwd(), "Lib_311")
if os.path.exists(local_lib):
    # if local_lib not in sys.path:
    #     sys.path.insert(0, local_lib)
    # إضافة مسار الـ DLL لنظام ويندوز
    os.environ["PATH"] = local_lib + os.pathsep + os.environ["PATH"]
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(local_lib)
        greenlet_path = os.path.join(local_lib, "greenlet")
        if os.path.exists(greenlet_path):
            os.add_dll_directory(greenlet_path)

sys.path.append(os.getcwd())
import time
import logging
import asyncio
from datetime import datetime, timedelta

# إعداد التسجيل
if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/app_capture.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CaptureScheduler")

def cleanup_old_charts():
    CHARTS_DIR = os.path.join("price_analysis", "charts")
    if not os.path.exists(CHARTS_DIR):
        return
    
    # قائمة الملفات المتوقع حذفها
    # ملاحظة: يجب أن تتطابق مع ما ينتجه capture_all_charts
    # سنحاول حذف الملفات التي تبدأ بـ heatmap_ أو tradingview_ أو coinglass_ وتنتهي بـ .png
    # لضمان شمولية الحذف لأي عملة
    try:
        for fname in os.listdir(CHARTS_DIR):
            if fname.endswith(".png") and (
                fname.startswith("coinglass_") or 
                fname.startswith("heatmap_") or 
                fname.startswith("tradingview_")
            ):
                fpath = os.path.join(CHARTS_DIR, fname)
                try:
                    os.remove(fpath)
                    logger.info(f"Deleted old chart: {fname}")
                except Exception as e:
                    logger.error(f"Failed to delete {fname}: {e}")
    except Exception as e:
        logger.error(f"Error listing directory for cleanup: {e}")

def get_next_run_time():
    now = datetime.now()
    # الدقائق المستهدفة: 5, 35
    targets = [5, 35]
    next_run = None
    
    for t in targets:
        if now.minute < t:
            next_run = now.replace(minute=t, second=0, microsecond=0)
            break
            
    if next_run is None:
        # الانتقال للساعة التالية والدقيقة 13
        next_run = (now + timedelta(hours=1)).replace(minute=targets[0], second=0, microsecond=0)
        
    return next_run

def main():
    logger.info("Capture Scheduler started. Target minutes: 5, 35")
    
    # تشغيل فوري عند البدء للتأكد من وجود صور (إذا لم تكن موجودة)
    # لكن المستخدم طلب "حذف واستبدال"، لذا سنقوم بدورة كاملة
    try:
        logger.info("Performing initial immediate capture...")
        cleanup_old_charts()
        try:
            from src.capture_charts import capture_all_charts
            asyncio.run(capture_all_charts())
        except Exception as e:
            logger.error(f"Import or runtime error while capturing charts: {e}")
            raise
        logger.info("Initial capture completed.")
    except Exception as e:
        logger.error(f"Error in initial capture: {e}")

    while True:
        next_run = get_next_run_time()
        now = datetime.now()
        
        # إذا كان الوقت المتبقي قليل جداً (أقل من 5 ثواني)، قد نكون في نفس الدقيقة، ننتظر للدورة التالية
        # لكن get_next_run_time يعالج ذلك بالبحث عن الدقيقة التالية > الحالية
        
        sleep_seconds = (next_run - now).total_seconds()
        
        logger.info(f"Next capture scheduled at {next_run} (in {sleep_seconds:.1f} seconds)")
        
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
            
        logger.info("Starting scheduled capture cycle...")
        try:
            cleanup_old_charts()
            try:
                from src.capture_charts import capture_all_charts
                asyncio.run(capture_all_charts())
            except Exception as e:
                logger.error(f"Import or runtime error while capturing charts: {e}")
                time.sleep(2)
                continue
            logger.info("Capture cycle completed successfully.")
        except Exception as e:
            logger.error(f"Error in capture cycle: {e}")
            
        # الانتظار قليلاً للتأكد من أننا خرجنا من الدقيقة الحالية لتجنب التكرار المزدوج
        # (رغم أن المنطق يعتمد على >)
        time.sleep(2)

if __name__ == "__main__":
    main()
