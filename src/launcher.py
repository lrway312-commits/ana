import sys
import os
import runpy

# إضافة المجلد الأب للمسار لتمكين استيراد الحزمة
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

try:
    print(f"Starting analysis from: {current_dir}")
    # تشغيل الوحدة كأنها هي الرئيسية (Main)
    runpy.run_module('src.main', run_name='__main__')
except Exception as e:
    print(f"Error starting main: {e}")
    import traceback
    traceback.print_exc()
