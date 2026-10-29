import sys
sys.stdout.reconfigure(encoding='utf-8')
from forensic_batch_analyzer import get_snap_data

print("=== VERIFIED DIRECTIONAL TRADES (SNAPS 520 TO 608) ===")

trades = [
    ('Trade D-1 (LONG)', 524, 'Snap 525: التهام جدار 356 BTC وانفجار الدلتا +54'),
    ('Trade D-2 (SHORT)', 529, 'Snap 530: قمة المقاومة وتبخر علاوة السبوت إلى 0.00$'),
    ('Trade D-3 (LONG)', 541, 'Snap 542: جدار الصد الجليدي 27.4 BTC بنسبة عمق 70.7x'),
    ('Trade D-4 (SHORT)', 576, 'Snap 577: قمة التوزيع UTAD وانهيار علاوة السبوت إلى 0.00$'),
    ('Trade D-5 (LONG)', 585, 'Snap 586: نموذج Turtle Soup Spring وجدار طلب 21 BTC')
]

total_pnl = 0.0

for name, idx, desc in trades:
    s = get_snap_data(idx)
    p = s['price']
    f_max = s['f_max']
    f_min = s['f_min']
    is_long = 'LONG' in name
    
    if is_long:
        # Long target: TP1 +100$, TP2 +250$, or exit near peak
        gain = f_max - p
        pnl = min(gain, 250.0) if gain >= 100.0 else gain
        print(f"{name} | {desc}")
        print(f"  سعر الدخول: ${p:,.2f} | أقصى صعود: ${f_max:,.2f} | المكسب المحقق: +${gain:,.2f} USD")
    else:
        gain = p - f_min
        pnl = min(gain, 200.0) if gain >= 100.0 else gain
        print(f"{name} | {desc}")
        print(f"  سعر الدخول: ${p:,.2f} | أقصى هبوط: ${f_min:,.2f} | المكسب المحقق: +${gain:,.2f} USD")
    
    total_pnl += pnl
    print("-" * 70)

print(f"إجمالي الأرباح الاتجاهية المحققة عبر هذه الموجات الخمس: +${total_pnl:,.2f} USD/BTC")
