import json
import httpx
import os
import time
import random
import logging
from typing import Dict, Any, Optional, List
from .config import GEMINI_API_KEY_PRIMARY, GEMINI_API_KEY_SECONDARY, GEMINI_API_KEY_TERTIARY, GEMINI_API_KEY_QUATERNARY, GEMINI_API_KEY_QUINARY, GEMINI_MODEL, SYMBOL

import base64

# خطأ مخصص لمحدودية المعدّل من Gemini
class RateLimitedGeminiError(Exception):
    pass

def api_url_for(model: str) -> str:
    # Use environment variable if it exists, otherwise use the passed model name
    effective_model = os.environ.get("GEMINI_MODEL", model)
    return f"https://generativelanguage.googleapis.com/v1beta/models/{effective_model}:generateContent"

def choose_key() -> str:
    # Get keys from environment variables directly to reflect runtime overrides
    from .config import GEMINI_API_KEY_PRIMARY, GEMINI_API_KEY_SECONDARY, GEMINI_API_KEY_TERTIARY, GEMINI_API_KEY_QUATERNARY, GEMINI_API_KEY_QUINARY
    
    # Priority check for Primary key if it was explicitly overridden in os.environ (like in ADA scheduler)
    primary_override = os.environ.get("GEMINI_API_KEY_PRIMARY")
    
    keys = []
    if primary_override:
        keys.append(primary_override)
    
    # Add other keys if they are not the same as the override
    for k in [GEMINI_API_KEY_PRIMARY, GEMINI_API_KEY_SECONDARY, GEMINI_API_KEY_TERTIARY, GEMINI_API_KEY_QUATERNARY, GEMINI_API_KEY_QUINARY]:
        if k and k not in keys:
            keys.append(k)
            
    if not keys:
        return ""
    os.makedirs("state", exist_ok=True)
    idx_path = os.path.join("state", "gemini_key_index.json")
    idx = 0
    if os.path.exists(idx_path):
        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                st = json.load(f)
                idx = int(st.get("idx", 0)) % len(keys)
        except Exception:
            idx = 0
    # آلية ذكية: اختر أول مفتاح لم يُستخدم مؤخراً (أقل عدد مرات استخدام)
    usage_log_path = os.path.join("state", "gemini_key_usage.json")
    usage_data = {}
    if os.path.exists(usage_log_path):
        try:
            with open(usage_log_path, "r", encoding="utf-8") as f:
                usage_data = json.load(f)
        except Exception:
            usage_data = {}
    # ابحث عن المفتاح الأقل استخداماً
    min_usage = float('inf')
    best_idx = idx
    for i, k in enumerate(keys):
        key_prefix = k[:8]
        usage = usage_data.get(key_prefix, 0)
        if usage < min_usage:
            min_usage = usage
            best_idx = i
    selected = keys[best_idx]
    # حدّث المؤشر للدورة التالية دائماً حتى لو حدث خطأ لاحقاً
    next_idx = (best_idx + 1) % len(keys)
    try:
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump({"idx": next_idx, "last_used": selected[:8] + "...", "timestamp": time.time()}, f, ensure_ascii=False)
    except Exception:
        pass
    logging.info(f"Gemini key selected: {selected[:8]}... (index {best_idx}, next will be {keys[next_idx][:8]}...)")
    return selected
# تعليمات بديلة: نهج 16+4 اليدوي لتوقع الساعة القادمة (قواعد مطوّرة)\n# مُنشئ تعليمات مزدوج: يُبقي النظام القديم كما هو ويضيف نظامًا تسلسليًا متطورًا لكل لقطة
def build_instruction_dual(instruction_text: str) -> str:
    legacy_rules = """
أنت نظام تحليل تداول متقدم يهدف إلى تتبع سلوك المؤسسات والحيتان وصناع السوق من خلال تحليل مجموعة كبيرة من البيانات المختلفة. الهدف الوحيد للنظام هو تحليل حركة السعر في آخر 15 دقيقة (آخر لقطة) وتحديد ما إذا كان من المتوقع أن تستمر هذه الحركة في الشمعة التالية لمدة 15 دقيقة فقط. النظام لا يهدف إلى التنبؤ باتجاه السوق لساعات أو أيام ولا يهتم بالاتجاه العام بعيد المدى، بل يركز فقط على الحركة الفورية التالية.

البيانات المقدمة تتكون من مجموعة لقطات تمثل تطور السوق خلال فترة قصيرة. كل لقطة تمثل 15 دقيقة من البيانات ويتم تحليلها بشكل مستقل ولكن ضمن سياق تحليلي متسلسل لفهم تطور حركة السعر. الهدف النهائي هو فهم آخر حركة حدثت في آخر لقطة ومعرفة ما إذا كانت البيانات الحالية تشير إلى استمرار هذه الحركة في الشمعة التالية أم لا.

البيانات المتاحة قد تشمل معلومات مثل CVD و Open Interest و Large Trades و Order Book و Liquidity Maps و Long/Short Ratio و Inflow/Outflow إضافة إلى بيانات مستخرجة من صور الشارتات وخرائط السيولة. يجب تحليل هذه البيانات بعمق شديد لمحاولة فهم سلوك المؤسسات والحيتان في السوق.

مهم جداً: الصور الأصلية لا يتم تحليلها كصور. جميع الصور يتم تحويلها مسبقاً إلى بيانات مستخرجة (extracted data). لذلك يجب تفسير هذه البيانات وفق معناها الحقيقي فقط وليس وفق توقعات الحركة الحالية. لا يجوز تغيير معنى البيانات لتوافق التوقع بل يجب الحفاظ على تفسيرها الحقيقي دائماً.

استمرارية الإشارة تعتمد على فهم ما إذا كانت الحركة الأخيرة تمتلك دعماً حقيقياً من البيانات يسمح لها بالاستمرار أم لا. لذلك يجب تقسيم جميع البيانات التي يتم تحليلها إلى فئتين أساسيتين:
البيانات الداعمة للحركة الأخيرة.
البيانات المناقضة للحركة الأخيرة.

الخطوة الأولى هي تحديد اتجاه الحركة الأخيرة في آخر 15 دقيقة. بعد تحديد الاتجاه يتم تحليل البيانات لمعرفة ما إذا كانت تدعم استمرار هذه الحركة أو تعارضها.

أولاً يتم تحليل البيانات الداعمة للحركة. الهدف من هذا التحليل هو معرفة ما إذا كانت هذه البيانات هي السبب الحقيقي للحركة السابقة وما إذا كانت تمتلك القدرة على الاستمرار في دفع السعر في نفس الاتجاه. يجب دراسة هذه البيانات لمعرفة ما إذا كانت لا تزال في مرحلة تدفق طبيعي وقادرة على الاستمرار أو إذا كانت قد وصلت إلى مرحلة استنزاف أو تنفيذ كامل للطاقة. إذا كانت البيانات الداعمة قد نفذت طاقتها أو وصلت إلى مرحلة لا يمكنها الاستمرار في التدفق فإن احتمال استمرار الحركة يصبح ضعيفاً. أما إذا كانت البيانات الداعمة لا تزال قوية ولم تصل إلى مرحلة الإنهاك أو الاستنزاف فمن المنطقي أن تستمر الحركة في الشمعة التالية. في هذه الحالة يتم اعتبار البيانات الداعمة صالحة لدعم الاستمرار.

بعد ذلك يتم تحليل البيانات المناقضة للحركة. يجب دراسة هذه البيانات بدقة لمعرفة سياق ظهورها. أول سؤال يجب الإجابة عليه هو: هل هذه البيانات المناقضة ظهرت بشكل حديث فقط في آخر 15 دقيقة أم أنها موجودة منذ لقطات سابقة؟

إذا كانت البيانات المناقضة ظهرت حديثاً داخل آخر 15 دقيقة فقط ولم يكن لها وجود سابق في اللقطات السابقة فإن هذا يعتبر حالة خطرة لأن تأثير هذه البيانات على السعر لم يظهر بعد. في هذه الحالة يجب البحث في اللقطات السابقة عن حالات مشابهة لظهور هذه البيانات المناقضة وقياس تأثيرها التاريخي. إذا كانت هذه البيانات عند ظهورها المفاجئ في الماضي تؤدي غالباً إلى انعكاس السعر أو إلى تقليص امتداد الحركة في الشمعة التالية فإن هذا يشير إلى خطر حقيقي ويجب إصدار إشارة محايدة بسبب عدم اليقين الناتج عن دخول بيانات مناقضة جديدة.

أما إذا كانت البيانات المناقضة موجودة سابقاً قبل آخر 15 دقيقة، مثلاً خلال ثلاث لقطات سابقة، فيجب تحليل تأثيرها التاريخي على حركة السعر. إذا كانت هذه البيانات موجودة سابقاً لكنها لم تكن تؤثر على حركة السعر بشكل سلبي واضح ولم تكن قادرة على إيقاف الحركة أو عكسها، وكان تأثيرها ضعيفاً أو يتناقص تدريجياً مع استمرار الحركة، ففي هذه الحالة يمكن اعتبار أن هذه البيانات المناقضة لا تمتلك قوة كافية لعكس الحركة في المدى القصير. إذا كانت البيانات الداعمة قوية والبيانات المناقضة ضعيفة أو غير مؤثرة تاريخياً في هذا النطاق الزمني القصير فيمكن إصدار إشارة باتجاه الحركة رغم وجود هذا التناقض.

بمعنى آخر يجب تقييم البيانات بشكل تاريخي ضمن نفس السياق الزمني القصير لمعرفة أي أنواع البيانات تدعم الاستمرار وأي أنواعها تؤدي عادة إلى إيقاف الحركة أو عكسها. القرار النهائي يعتمد على هذا التقييم التاريخي للسلوك الفعلي للبيانات وتأثيرها على السعر.
قاعدة أساسية في التحليل: البيانات لا تقود السوق وحدها. السعر هو الحكم النهائي. لذلك أي بيانات تشير إلى اتجاه معين ولكن لا يظهر لها أي استجابة سعرية حقيقية لا يجب الاعتماد عليها في إصدار الإشارة. وجود تنفيذ عدواني مثل Large Trades أو ارتفاع كبير في CVD بدون استجابة سعرية متناسبة يعني أن هذا التنفيذ قد يكون مجرد امتصاص سيولة أو نشاط غير اتجاهي. في هذه الحالة لا يجوز اعتباره بداية اتجاه أو استمرارية.

يجب أيضاً تحليل خرائط السيولة بعناية. خرائط السيولة تمثل أماكن تجمع الأوامر الكبيرة في السوق. المناطق ذات الكثافة الأعلى تمثل سيولة أكبر وقد تكون جذابة للسعر إذا كانت قريبة منه. لكن السيولة ليست دائماً المحرك الوحيد للسوق. في بعض الحالات قد يرتد السعر قبل الوصول إلى السيولة أو يتجاهلها حسب سلوك المؤسسات. لذلك يجب تحليل موقع السعر بالنسبة للسيولة مع مراعاة سلوك البيانات الأخرى.

مهم جداً: تفسير البيانات المختلفة يجب أن يتم بشكل مستقل أولاً. لا يجوز تغيير معنى البيانات أو تفسيرها فقط لتوافق التوقع الحالي. على سبيل المثال إذا كانت بيانات السيولة تشير إلى وجود سيولة قوية فوق السعر فلا يجوز اعتبار السيولة أسفل السعر أقوى فقط لأن التوقع هو الهبوط. البيانات يجب تفسيرها وفق معناها الحقيقي ثم يتم دمج التحليلات معاً في المرحلة النهائية لاتخاذ القرار.

الهدف النهائي للنظام هو التقاط الحركات المستمرة فقط وتجنب الدخول في التذبذبات أو الحركات التلاعبية قصيرة العمر. لذلك يجب إصدار الإشارة فقط عندما تظهر أدلة واضحة على أن حركة آخر 15 دقيقة تمتلك دعماً حقيقياً يسمح لها بالاستمرار في الشمعة التالية.

القرار النهائي يمكن أن يكون واحداً من ثلاثة:
BUY إذا كانت الحركة الأخيرة صعوداً والبيانات الداعمة تشير إلى استمرار الصعود في الشمعة التالية.
SELL إذا كانت الحركة الأخيرة هبوطاً والبيانات الداعمة تشير إلى استمرار الهبوط في الشمعة التالية.
WAIT إذا كانت البيانات المناقضة قوية أو ظهرت بشكل مفاجئ أو إذا لم يكن هناك دليل كافٍ على أن الحركة ستستمر.
"""

    seq_answer_fmt = """
أول سطر: إشارة واضحة: شراء أو بيع أو انتظار
بيع او شراء اذ كنت تتوقع ام 15 دقيق تالية سوف تكون استمرارية اي نفس حركة اخر ملف احر شمعة انتظار اذ منت تظن انها انعكاسية او لدي اي شبه بحصول ذلك 

النظام الحالة العامة والاشارة الاكثر احتمالية له هي انتظار يتم تغير هذا القرار باضافة ثقة للاشارة وفق تحقيقها الشروط السابقة التي قمنا بتحديدها في التعليمات كلها واحدة واحدة 
اولا يتم  تجديد شروط وفلاتر اقتراحات الاشارة جميعهاالتي حددتها ثم يتم اضافت توزيع الثقة عليها كلها ووفق تحقيق لبيانات يتم اضافت الثقة الى الاشارة المتوقعة العلامة الكاملة تعني لا مجال للشكل ابدا في الاشارة
ولا يجوز الخروج من وضع الحماية اشارة انتظار الا اذ تم تحقيق علامة شبه كاملة بشرط توقع ان تعدل البيانات المخالفة ولا مجال للشروط او البيانات التي تخالفهاان تجعل السعر والاشارة المصدرة خاطئة اي لا مجال للشك في الاشارة
واذ ما كان من الممكن تفسير الحالة الحالية للنظام بتفسير اخر مرجح ايضا يجب اصدار اشارة محايدة
لا مكان للاشارات الترجحية بين بيانات  متناقضة 
غندما تكون البيانات للشمعة الاخيرة بها اندفاع في بعض البيانات او حتى اغلبها مثل cvd or large trades فان لا يحب اصدار اشارة معاكسة استنادا على بيانات لقطة واحدة مالم تكن البيانات للقطة السابقة تدل على هذا الانعكاس ولا يمكن تفسير هذا القطتين بشكل اخر اي انه يحب تاكيد الاشارة من داخل لقطتين 
الاشارة تكون بيع او شراء فقط عندما تتوقع استمرار لاخر شمعة ول 15 دقيقة تالية فقط نحن لا نطمح الى حركة طويلة بل فقط معرفة حركة السعر ل 15 دقيقة تالية لا غير 
أعد بعده كائن JSON فقط بالحقول التالية:
{
  "signal": "شراء|بيع|انتظار",
  "last_snapshot_ts": رقم الطابع الزمني لآخر لقطة كما هو في البيانات,
  "confidence": 0-100,
  "extracted_data_status": "نعم|لا", 

  "last_15m_reason": "تحليل لآخر شمعة ولماذا يتوقع استمرارها أو التحايد (15 دقيقة القادمة).",
  "resources_used": {
    "extracted_image_analysis": "تحليل مفصل ودقيق للبيانات المستخرجة من الصور الموفرة في وسم <image_analysis_data>، مع ذكر أهم النقاط التي أثرت على القرار.",
   
   
  },
  "decision_rationale": "...",
  "index": 16,
  "validated": true|false
}
لا تُرسل أي نص إضافي خارج السطر الأول وكائن JSON.
"""
    # أعد فقط النص المدخل + تنسيق الإجابة التسلسلي
    return instruction_text + "\n\n" + legacy_rules + "\n\n" + seq_answer_fmt

# مُنشئ تعليمات تقدمية: يستخدم البنية المزدوجة لضمان الاتساق مع النظام المطوّر
def build_instruction_progressive(instruction_text: str) -> str:
    return build_instruction_dual(instruction_text)

def call_gemini(instruction_text: str, current_data: Dict[str, Any], historical_attachment_text: str, trade_pairs: List[Dict[str, Any]], image_paths: Optional[List[str]] = None, image_analysis_text: str = "") -> str:
    os.makedirs("state", exist_ok=True)
    THROTTLE_STATE_PATH = os.path.join("state", f"gemini_throttle_{SYMBOL}.json")
    LOCK_PATH = os.path.join("state", f"gemini_lock_{SYMBOL}")
    MIN_INTERVAL_SEC = int(os.getenv("GEMINI_MIN_INTERVAL_SEC", "60"))
    MAX_WAIT_BEFORE_FAIL_SEC = int(os.getenv("GEMINI_MAX_WAIT_SEC", "180"))

    def _now_ts() -> int:
        return int(time.time())

    def _read_state() -> Dict[str, Any]:
        try:
            if os.path.exists(THROTTLE_STATE_PATH):
                with open(THROTTLE_STATE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            return {}
        return {}

    def _write_state(st: Dict[str, Any]) -> None:
        try:
            with open(THROTTLE_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(st, f, ensure_ascii=False)
        except Exception:
            pass

    def _set_next_allowed(after_sec: int) -> None:
        st = _read_state()
        st["next_allowed_ts"] = _now_ts() + max(0, int(after_sec))
        _write_state(st)

    def _acquire_lock() -> bool:
        try:
            if os.path.exists(LOCK_PATH):
                # تحقق من عمر القفل - إذا كان أكثر من 10 دقائق، احذفه
                try:
                    lock_age = time.time() - os.path.getmtime(LOCK_PATH)
                    if lock_age > 600:  # 10 دقائق
                        os.remove(LOCK_PATH)
                        logging.warning(f"Removed stale lock file (age: {lock_age:.1f}s)")
                    else:
                        # قيد قيد التنفيذ من عملية أخرى
                        return False
                except Exception:
                    return False
            with open(LOCK_PATH, "w") as f:
                f.write("1")
            return True
        except Exception:
            return False

    def _release_lock() -> None:
        try:
            if os.path.exists(LOCK_PATH):
                os.remove(LOCK_PATH)
        except Exception:
            pass

    def _wait_until_allowed() -> None:
        state = _read_state()
        next_allowed = int(state.get("next_allowed_ts", 0))
        now_ts = _now_ts()
        consecutive_429 = int(state.get("consecutive_429", 0))
        if consecutive_429 >= 2 and now_ts < next_allowed:
            reduced_wait = max(30, (next_allowed - now_ts) // 2)
            logging.info(f"Reducing wait time from {next_allowed - now_ts}s to {reduced_wait}s due to consecutive 429s")
            time.sleep(reduced_wait)
        elif now_ts < next_allowed:
            sleep_sec = (next_allowed - now_ts) + random.uniform(0.1, 0.5)
            time.sleep(max(0.0, sleep_sec))
    
    # سجل وقت البدء لاستخدامه في حساب مدة الانتظار الإجمالي
    st_init = _read_state()
    st_init["last_start_ts"] = _now_ts()
    _write_state(st_init)
    api_key = choose_key()
    headers = {"Content-Type": "application/json"}
    current_data = json.dumps(current_data, indent=2, ensure_ascii=False)
    trade_pairs_data = json.dumps(trade_pairs, indent=2, ensure_ascii=False)
    try:
        _ = int(os.getenv("GEMINI_CURR_MAX_CHARS", "4000"))
    except Exception:
        pass
    try:
        tp_max = int(os.getenv("GEMINI_TRADEPAIRS_MAX_ITEMS", "8"))
        if isinstance(trade_pairs, list) and len(trade_pairs) > tp_max:
            trade_pairs_data = json.dumps(trade_pairs[:tp_max], indent=2, ensure_ascii=False)
    except Exception:
        pass
    try:
        hist_max = int(os.getenv("GEMINI_HIST_MAX_CHARS", "6000"))
        if isinstance(historical_attachment_text, str) and len(historical_attachment_text) > hist_max:
            historical_attachment_text = historical_attachment_text[:hist_max]
    except Exception:
        pass

    blacklist_path = os.path.join("state", "gemini_key_blacklist.json")
    BLACKLIST_EXPIRY_SEC = int(os.getenv("GEMINI_BLACKLIST_EXPIRY_SEC", "3600"))

    def _read_blacklist() -> List[str]:
        try:
            if os.path.exists(blacklist_path):
                try:
                    mtime = os.path.getmtime(blacklist_path)
                    age = time.time() - mtime
                    if age > max(60, BLACKLIST_EXPIRY_SEC):
                        # Expire entire blacklist after cooldown window
                        logging.info(f"Expiring Gemini key blacklist (age: {age:.1f}s > {BLACKLIST_EXPIRY_SEC}s)")
                        _write_blacklist([])
                        return []
                except Exception:
                    pass
                with open(blacklist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [str(x) for x in data]
        except Exception:
            return []
        return []

    def _write_blacklist(items: List[str]) -> None:
        try:
            with open(blacklist_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False)
        except Exception:
            pass

    def _add_to_blacklist(prefix: str) -> None:
        bl = _read_blacklist()
        if prefix not in bl:
            bl.append(prefix)
            _write_blacklist(bl)

    # تمت إزالة التحليل السابق لضمان عدم تأثر النموذج بالأنماط القديمة
    prev_analysis_text = ""

    parts = [
        {"text": f"<current_data>\n{current_data}\n</current_data>"},
        {"text": f"\n\n<trade_pairs>\n{trade_pairs_data}\n</trade_pairs>"},
        {"text": f"\n\n<historical_data>\n{historical_attachment_text}\n</historical_data>"}
    ]
    
    if image_analysis_text:
        parts.append({"text": f"\n\n<image_analysis_data>\n{image_analysis_text}\n</image_analysis_data>"})
    
    # إضافة تذكير قوي بالتنسيق المطلوب في نهاية الموجه لضمان عدم تأثر النموذج بالتحليلات السابقة
    format_reminder = """
تذكير هام جداً: يجب أن تلتزم بالتنسيق التالي في إجابتك حصراً:
السطر الأول: إشارة واضحة (شراء أو بيع أو انتظار)
بقية الإجابة: كائن JSON فقط كما هو موضح في التعليمات السابقة.
لا تتبع تنسيق التحليل السابق إذا كان مختلفاً. ابدأ بالسطر الأول ثم الـ JSON مباشرة.

ملاحظة هامة: تم تضمين بيانات مستخرجة من أحدث صور الشارتات والسيولة داخل وسم <image_analysis_data>. 
يجب عليك استخدام هذه البيانات في تحليلك وتأكيد استلامها في حقل "extracted_data_status" بـ "نعم".
"""
    parts.append({"text": format_reminder})

    # إضافة الصور إذا وجدت
    if image_paths:
        for img_path in image_paths:
            if os.path.exists(img_path):
                try:
                    with open(img_path, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                    
                    # تحديد نوع MIME بناءً على الامتداد
                    mime_type = "image/png"
                    if img_path.lower().endswith(".jpg") or img_path.lower().endswith(".jpeg"):
                        mime_type = "image/jpeg"
                    elif img_path.lower().endswith(".webp"):
                        mime_type = "image/webp"
                        
                    parts.append({
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": encoded_string
                        }
                    })
                    logging.info(f"Attached image to Gemini payload: {os.path.basename(img_path)}")
                except Exception as e:
                    logging.error(f"Failed to attach image {img_path}: {e}")

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "system_instruction": {
            "parts": [
                {"text": instruction_text}
            ]
        }
    }
    try:
        if not isinstance(instruction_text, str):
            instruction_text = "" if instruction_text is None else str(instruction_text)
        if historical_attachment_text is None:
            historical_attachment_text = ""
        logging.info(f"حجم نص التعليمات: {len(instruction_text or '')}")
        logging.info(f"حجم current_data: {len(current_data or '')}")
        logging.info(f"حجم historical_attachment: {len(historical_attachment_text or '')}")
    except Exception:
        pass
    # حضّر قائمة المفاتيح للدوران مع استبعاد المفاتيح في القائمة السوداء
    keys_base = [k for k in [GEMINI_API_KEY_PRIMARY, GEMINI_API_KEY_SECONDARY, GEMINI_API_KEY_TERTIARY, GEMINI_API_KEY_QUATERNARY, GEMINI_API_KEY_QUINARY] if k]
    blacklist = _read_blacklist()
    if api_key and (api_key[:8] in blacklist):
        replacement = ""
        for k in keys_base:
            if k and (k[:8] not in blacklist):
                replacement = k
                break
        api_key = replacement
    key_ring = [k for k in keys_base if k and (k[:8] not in blacklist)]
    
    if not key_ring:
        logging.error("No valid Gemini API keys available after filtering blacklist.")
        raise RuntimeError("No valid Gemini API keys available")

    if api_key and api_key in key_ring:
        start_idx = key_ring.index(api_key)
    else:
        start_idx = 0
    params = {"key": key_ring[start_idx]}
    last_error = None
    # سجل المفتاح المستخدم لأغراض التحقق
    logging.info(f"Using Gemini key: {params['key'][:8]}...")
    # سجل استخدام المفتاح في ملف مراقبة
    try:
        usage_log_path = os.path.join("state", "gemini_key_usage.json")
        usage_data = {}
        if os.path.exists(usage_log_path):
            try:
                with open(usage_log_path, "r", encoding="utf-8") as f:
                    usage_data = json.load(f)
            except Exception:
                usage_data = {}
        key_prefix = params['key'][:8]
        usage_data[key_prefix] = usage_data.get(key_prefix, 0) + 1
        with open(usage_log_path, "w", encoding="utf-8") as f:
            json.dump(usage_data, f, ensure_ascii=False)
    except Exception:
        pass
    # تأخير عشوائي قصير عند تبديل المفاتيح لضمان التوزيع العادل
    time.sleep(random.uniform(0.2, 0.6))

    try:
        READ_T = int(os.getenv("GEMINI_HTTP_READ_TIMEOUT_SEC", os.getenv("GEMINI_MAX_WAIT_SEC", "180")))
    except Exception:
        READ_T = 180
    try:
        CONN_T = int(os.getenv("GEMINI_HTTP_CONNECT_TIMEOUT_SEC", "20"))
    except Exception:
        CONN_T = 20
    try:
        WRITE_T = int(os.getenv("GEMINI_HTTP_WRITE_TIMEOUT_SEC", "20"))
    except Exception:
        WRITE_T = 20
    try:
        POOL_T = int(os.getenv("GEMINI_HTTP_POOL_TIMEOUT_SEC", "20"))
    except Exception:
        POOL_T = 20
    timeout = httpx.Timeout(connect=CONN_T, read=READ_T, write=WRITE_T, pool=POOL_T)

    # Retry logic setup
    max_attempts = max(1, len(key_ring)) * 3  # Try each key up to 3 times
    attempt = 0
    current_key_idx = start_idx
    last_exception = None

    while attempt < max_attempts:
        current_key = key_ring[current_key_idx]
        params["key"] = current_key
        
        lock_acquired = False
        try:
            # Only wait if it's the first attempt or we are sticking to the same key (unlikely with this logic)
            # We want to try keys rapidly if one fails
            if attempt == 0:
                 _wait_until_allowed()
            
            lock_acquired = _acquire_lock()
            
            logging.info(f"Gemini Request Attempt {attempt+1}/{max_attempts} using key {current_key[:8]}...")
            
            with httpx.Client(timeout=timeout) as client:
                r = client.post(api_url_for(GEMINI_MODEL), params={"key": current_key}, json=payload, timeout=timeout)
                r.raise_for_status()
                data = r.json()
                
                # Success handling
                try:
                    # Reset rate limit state only on success
                    _set_next_allowed(MIN_INTERVAL_SEC)
                    st = _read_state()
                    st["consecutive_429"] = 0
                    _write_state(st)
                except Exception:
                    pass
                
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    return json.dumps(data, ensure_ascii=False)

        except httpx.HTTPStatusError as e:
            last_exception = e
            status = e.response.status_code if e.response is not None else 0
            
            if status == 429:
                logging.warning(f"Gemini 429 Rate Limit with key {current_key[:8]}. Switching key...")
                # Do NOT set global wait time here, just switch key
                time.sleep(2) # Short pause before next key
                
            elif status in (400, 401, 403):
                logging.error(f"Gemini Auth/Bad Request Error {status} with key {current_key[:8]}. Body: {e.response.text}")
                try:
                    _add_to_blacklist(current_key[:8])
                    # Remove from local ring to avoid retrying this bad key
                    if current_key in key_ring:
                        key_ring.remove(current_key)
                        if not key_ring:
                            raise RuntimeError("All Gemini keys have been blacklisted/exhausted.")
                        current_key_idx = current_key_idx % len(key_ring) # Adjust index
                        continue # Skip the normal index increment
                except Exception:
                    pass
            else:
                logging.error(f"Gemini HTTP {status} Error. Retrying...")
                time.sleep(5)
                
        except Exception as e:
            last_exception = e
            logging.error(f"Gemini Network/Other Error: {e}. Retrying...")
            time.sleep(5)
            
        finally:
            if lock_acquired:
                _release_lock()
        
        # Move to next key
        if key_ring:
            current_key_idx = (current_key_idx + 1) % len(key_ring)
        attempt += 1

    # If we exit loop, we failed
    logging.error("All Gemini retry attempts failed.")
    if last_exception:
        raise last_exception
    raise RuntimeError("Failed to generate content after multiple attempts with all available keys.")
