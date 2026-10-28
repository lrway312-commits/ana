# -*- coding: utf-8 -*-
"""
Walk-Forward 500-Snapshot Institutional Engine — Phase 16.0 Sovereign Master
Implements Directional Symmetry (LONG & SHORT Engines) and the Hexagonal Immunization Rulebook (V-16.5A - V-16.5F).
Processes 3 snapshots at a time sequentially.
Stops immediately upon encountering a loss OR reaching Snapshot 500.
"""

import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

SNAPSHOT_DIR = 'price_analysis/بيانات'
JOURNAL_PATH = 'price_analysis/HISTORICAL_WALKFORWARD_RESEARCH_JOURNAL.md'

all_files = sorted(glob.glob(os.path.join(SNAPSHOT_DIR, 'BTCUSDT_snapshot_*.json')))
print(f"Total snapshot files available: {len(all_files)}")

# We have already processed Batches 1-131 (indices 0 to 392, i.e., Snapshots 1 to 393).
# Starting index for Batch 132 is index 393 (Snapshot 394).
START_INDEX = 393
END_INDEX = min(500, len(all_files))

print(f"Engine running sequentially from index {START_INDEX} (Snapshot {START_INDEX+1}) to index {END_INDEX} (Snapshot {END_INDEX})...")

def load_snapshot(fpath):
    with open(fpath, 'r', encoding='utf-8') as f:
        d = json.load(f)
    
    curr = d.get('current', {})
    price = curr.get('current_price') or d.get('current_price')
    spot = curr.get('spot_price') or d.get('spot_price')
    basis = (spot - price) if (spot is not None and price is not None) else 0.0
    
    ob = d.get('order_book', {})
    bids = ob.get('bids', [])
    asks = ob.get('asks', [])
    
    analysis = d.get('analysis', {})
    smc_data = analysis.get('smc_structures', {})
    avwap = smc_data.get('avwap', {})
    liq = analysis.get('liquidation_clusters', {})
    
    # Klines / Candles
    series = d.get('series', {})
    klines = series.get('klines_15m', [])
    last_candle = None
    prev_candle = None
    if len(klines) >= 2:
        k_prev = klines[-2]
        prev_candle = {'open': float(k_prev[1]), 'high': float(k_prev[2]), 'low': float(k_prev[3]), 'close': float(k_prev[4]), 'volume': float(k_prev[5])}
    if klines:
        k = klines[-1]
        ts, o, h, l, c, v = float(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])
        clv = (c - l) / (h - l) if (h - l) > 0 else 0.5
        last_candle = {'ts': ts, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v, 'range': h - l, 'clv': clv}
        
    return {
        'fpath': fpath,
        'fname': os.path.basename(fpath),
        'price': price,
        'spot': spot,
        'basis': basis,
        'oi': curr.get('open_interest', 0.0),
        'oi_z': curr.get('oi_z_score', 0.0),
        'cvd_vel': curr.get('futures_cvd_velocity', 0.0),
        'spot_cvd': curr.get('spot_cvd_now', 0.0),
        'long_pct': curr.get('long_percent', 50.0),
        'short_pct': curr.get('short_percent', 50.0),
        'evr': curr.get('wyckoff_effort_vs_result_ratio', 0.0),
        'micro_bps': curr.get('micro_price_bps', 0.0),
        'bids': bids,
        'asks': asks,
        'avwap_mean': avwap.get('avwap', price),
        'avwap_upper1': avwap.get('upper_1s', price + 400),
        'avwap_lower1': avwap.get('lower_1s', price - 400),
        'range_high': liq.get('recent_range_high', price + 200),
        'range_low': liq.get('recent_range_low', price - 200),
        'candle': last_candle,
        'prev_candle': prev_candle
    }

# Running state
active_position = None
completed_trades = []
current_batch_num = 132
stopped_on_loss = False
stop_reason = ""

# Track cumulative net pnl starting from Batches 1-131 (+628.20 USD)
cumulative_pnl = 628.20
trade_counter = 5

batch_reports = []

curr_idx = START_INDEX
while curr_idx < END_INDEX:
    batch_files = all_files[curr_idx : min(curr_idx + 3, END_INDEX)]
    snaps = [load_snapshot(fp) for fp in batch_files]
    snap_indices = [curr_idx + i + 1 for i in range(len(snaps))]
    
    batch_title = f"📦 الدفعة {current_batch_num} (Batch {current_batch_num}: Snapshots {snap_indices[0]} - {snap_indices[-1]})"
    
    # 1. Evaluate Active Position if any
    trade_events = []
    if active_position is not None:
        pos = active_position
        for s in snaps:
            c = s['candle']
            h = c['high'] if c else s['price']
            l = c['low'] if c else s['price']
            
            if pos['type'] == 'LONG':
                # Check Hard SL
                if l <= pos['hard_sl']:
                    loss_pnl = pos['hard_sl'] - pos['entry']
                    total_trade_pnl = (pos['tp1_pnl'] + loss_pnl) / 2.0 if pos['tp1_hit'] else loss_pnl
                    pos['exit_price'] = pos['hard_sl']
                    pos['pnl'] = total_trade_pnl
                    pos['status'] = 'LOSS' if total_trade_pnl < 0 else 'BE'
                    completed_trades.append(pos)
                    cumulative_pnl += total_trade_pnl
                    trade_events.append(f"🔴 ضرب وقف الخسارة الصارم عند ${pos['hard_sl']:.2f} (النتيجة: {total_trade_pnl:+.2f}$)")
                    
                    if total_trade_pnl < 0:
                        stopped_on_loss = True
                        stop_reason = f"ضرب وقف الخسارة لـ {pos['id']} عند ${pos['hard_sl']:.2f} بخسارة {total_trade_pnl:+.2f}$"
                        active_position = None
                        break
                    else:
                        active_position = None
                        break
                        
                # Check Breakeven Trigger (+100$)
                if not pos['be_locked'] and h >= pos['entry'] + 100.0:
                    pos['hard_sl'] = pos['entry']
                    pos['be_locked'] = True
                    trade_events.append(f"⚪ تفعيل محطة التعادل ورفع الوقف لسعر الدخول ${pos['entry']:.2f} ($0.00 Risk)")
                    
                # Check TP1 (+170$)
                if not pos['tp1_hit'] and h >= pos['tp1']:
                    pos['tp1_hit'] = True
                    pos['tp1_pnl'] = pos['tp1'] - pos['entry']
                    pos['hard_sl'] = max(pos['hard_sl'], pos['entry'] + 50.0)
                    trade_events.append(f"🟢 تحقيق الهدف الأول TP1 عند ${pos['tp1']:.2f} (+{pos['tp1_pnl']:.2f}$ محققة بنصف المركز)")
                    
                # Check TP2 (+380$)
                if pos['tp1_hit'] and h >= pos['tp2']:
                    tp2_pnl = pos['tp2'] - pos['entry']
                    total_trade_pnl = (pos['tp1_pnl'] + tp2_pnl) / 2.0
                    pos['exit_price'] = pos['tp2']
                    pos['pnl'] = total_trade_pnl
                    pos['status'] = 'WIN'
                    completed_trades.append(pos)
                    cumulative_pnl += total_trade_pnl
                    trade_events.append(f"🟢 سحق الهدف الثاني TP2 عند ${pos['tp2']:.2f} بالكامل (الربح الإجمالي للصفقة: +{total_trade_pnl:.2f}$)")
                    active_position = None
                    break
                    
            elif pos['type'] == 'SHORT':
                # Check Hard SL
                if h >= pos['hard_sl']:
                    loss_pnl = pos['entry'] - pos['hard_sl']
                    total_trade_pnl = (pos['tp1_pnl'] + loss_pnl) / 2.0 if pos['tp1_hit'] else loss_pnl
                    pos['exit_price'] = pos['hard_sl']
                    pos['pnl'] = total_trade_pnl
                    pos['status'] = 'LOSS' if total_trade_pnl < 0 else 'BE'
                    completed_trades.append(pos)
                    cumulative_pnl += total_trade_pnl
                    trade_events.append(f"🔴 ضرب وقف الخسارة الصارم عند ${pos['hard_sl']:.2f} (النتيجة: {total_trade_pnl:+.2f}$)")
                    
                    if total_trade_pnl < 0:
                        stopped_on_loss = True
                        stop_reason = f"ضرب وقف الخسارة لـ {pos['id']} عند ${pos['hard_sl']:.2f} بخسارة {total_trade_pnl:+.2f}$"
                        active_position = None
                        break
                    else:
                        active_position = None
                        break
                        
                # Check Breakeven Trigger (+100$)
                if not pos['be_locked'] and l <= pos['entry'] - 100.0:
                    pos['hard_sl'] = pos['entry']
                    pos['be_locked'] = True
                    trade_events.append(f"⚪ تفعيل محطة التعادل ورفع الوقف لسعر الدخول ${pos['entry']:.2f} ($0.00 Risk)")
                    
                # Check TP1 (+170$)
                if not pos['tp1_hit'] and l <= pos['tp1']:
                    pos['tp1_hit'] = True
                    pos['tp1_pnl'] = pos['entry'] - pos['tp1']
                    pos['hard_sl'] = min(pos['hard_sl'], pos['entry'] - 50.0)
                    trade_events.append(f"🟢 تحقيق الهدف الأول TP1 عند ${pos['tp1']:.2f} (+{pos['tp1_pnl']:.2f}$ محققة بنصف المركز)")
                    
                # Check TP2 (+380$)
                if pos['tp1_hit'] and l <= pos['tp2']:
                    tp2_pnl = pos['entry'] - pos['tp2']
                    total_trade_pnl = (pos['tp1_pnl'] + tp2_pnl) / 2.0
                    pos['exit_price'] = pos['tp2']
                    pos['pnl'] = total_trade_pnl
                    pos['status'] = 'WIN'
                    completed_trades.append(pos)
                    cumulative_pnl += total_trade_pnl
                    trade_events.append(f"🟢 سحق الهدف الثاني TP2 عند ${pos['tp2']:.2f} بالكامل (الربح الإجمالي للصفقة: +{total_trade_pnl:.2f}$)")
                    active_position = None
                    break
                    
        if stopped_on_loss:
            pass

    # 2. Entry Signals Evaluation
    new_trade_signal = None
    if active_position is None and not stopped_on_loss:
        last_s = snaps[-1]
        c = last_s['candle']
        pc = last_s['prev_candle']
        if c:
            # Check LONG conditions (Engine 1 & Support Bounce)
            is_spring_reclaim = (c['low'] <= last_s['range_low'] and c['clv'] >= 0.50)
            is_support_bounce = (c['clv'] >= 0.70 and last_s['basis'] >= 5.0 and last_s['price'] > last_s['avwap_lower1'])
            
            if is_spring_reclaim or is_support_bounce:
                dense_ask_price = 999999.0
                for a in last_s['asks']:
                    price_level, vol = float(a[0]), float(a[1])
                    if vol >= 15.0 and price_level > c['close']:
                        dense_ask_price = min(dense_ask_price, price_level)
                        break
                        
                # Rule V-16.5B & V-16.5F: Overhead ceiling includes AVWAP Mean if price < AVWAP Mean
                avwap_overhead = last_s['avwap_mean'] if c['close'] < last_s['avwap_mean'] else last_s['avwap_upper1']
                overhead_ceiling = min(last_s['range_high'], avwap_overhead, dense_ask_price)
                runway = overhead_ceiling - c['close']
                
                # Rule V-16.5C (Breakout quality)
                breakout_ok = not (c['clv'] < 0.40 and c['volume'] < 120.0)
                
                # Rule V-16.5F (Anemic volume & negative CVD filter)
                anemic_filter_veto = (c['volume'] < 100.0 and last_s['cvd_vel'] <= 0.0)
                
                # Rule V-16.5E (The AVWAP Band Vacuum & Anemic Volume Long Veto)
                sweep_low = c['low']
                hard_sl = sweep_low - 35.0
                risk = c['close'] - hard_sl
                
                avwap_vacuum_veto = False
                if c['volume'] < 120.0:
                    if hard_sl > last_s['avwap_lower1'] and (c['close'] - last_s['avwap_lower1']) < 180.0:
                        anchored_sl = last_s['avwap_lower1'] - 25.0
                        if (c['close'] - anchored_sl) > 160.0:
                            avwap_vacuum_veto = True
                        else:
                            hard_sl = anchored_sl
                            risk = c['close'] - hard_sl
                
                if runway >= 100.0 and breakout_ok and not avwap_vacuum_veto and not anemic_filter_veto:
                    if risk <= 180.0:
                        trade_id = f"Trade {trade_counter}"
                        trade_counter += 1
                        new_trade_signal = {
                            'id': trade_id,
                            'type': 'LONG',
                            'batch': current_batch_num,
                            'entry': c['close'],
                            'hard_sl': hard_sl,
                            'tp1': c['close'] + 170.0,
                            'tp2': c['close'] + 380.0,
                            'be_locked': False,
                            'tp1_hit': False,
                            'tp1_pnl': 0.0,
                            'status': 'ACTIVE'
                        }
                        active_position = new_trade_signal
                        trade_events.append(f"🟢 تفعيل صفقة شراء مؤسسية ({trade_id}) عند ${c['close']:.2f} (وقف: ${hard_sl:.2f} | هدف 1: ${new_trade_signal['tp1']:.2f} | هدف 2: ${new_trade_signal['tp2']:.2f})")

            # Check SHORT conditions (Engine 2 & Engine 4 with Rule V-16.5G)
            if active_position is None and pc:
                # Engine 2: Breakdown below previous candle low with strong volume & low CLV
                is_breakdown = (c['close'] < pc['low'] and c['clv'] <= 0.25 and c['volume'] >= 200.0)
                # Engine 4: UTAD sweep of previous high with rejection wick & strong volume
                is_utad = (c['high'] >= pc['high'] and c['clv'] <= 0.20 and (c['high'] - c['close']) >= 60.0 and c['volume'] >= 200.0)
                
                # Rule V-16.5A: Veto SHORT only if price is at/below AVWAP Lower 1s with extreme positive basis
                exhaustion_bottom_veto = (last_s['price'] <= last_s['avwap_lower1'] and last_s['basis'] > 25.0)
                
                # Rule V-16.5G: Floor Runway Mandate towards AVWAP Lower 1s must be >= 120$!
                # Strictly veto any short if price is already below AVWAP Lower 1s OR distance to Lower 1s < 120$!
                sub_lower_band_veto = (last_s['price'] <= last_s['avwap_lower1'] or (last_s['price'] - last_s['avwap_lower1']) < 120.0)
                
                if (is_breakdown or is_utad) and not exhaustion_bottom_veto and not sub_lower_band_veto:
                    sweep_high = c['high']
                    hard_sl = sweep_high + 35.0
                    risk = hard_sl - c['close']
                    if risk <= 180.0:
                        trade_id = f"Trade {trade_counter}"
                        trade_counter += 1
                        new_trade_signal = {
                            'id': trade_id,
                            'type': 'SHORT',
                            'batch': current_batch_num,
                            'entry': c['close'],
                            'hard_sl': hard_sl,
                            'tp1': c['close'] - 170.0,
                            'tp2': c['close'] - 380.0,
                            'be_locked': False,
                            'tp1_hit': False,
                            'tp1_pnl': 0.0,
                            'status': 'ACTIVE'
                        }
                        active_position = new_trade_signal
                        trade_events.append(f"🔴 تفعيل صفقة بيع شورت مؤسسية ({trade_id}) عند ${c['close']:.2f} (وقف: ${hard_sl:.2f} | هدف 1: ${new_trade_signal['tp1']:.2f} | هدف 2: ${new_trade_signal['tp2']:.2f})")

    # Generate batch markdown section
    s1, s2, s3 = snaps[0], snaps[1], snaps[-1]
    clv1 = s1['candle']['clv'] if s1['candle'] else 0.5
    clv2 = s2['candle']['clv'] if s2['candle'] else 0.5
    clv3 = s3['candle']['clv'] if s3['candle'] else 0.5
    vol1 = s1['candle']['volume'] if s1['candle'] else 0.0
    vol2 = s2['candle']['volume'] if s2['candle'] else 0.0
    vol3 = s3['candle']['volume'] if s3['candle'] else 0.0
    
    events_str = chr(10).join(trade_events) if trade_events else "لا توجد ضربات أهداف أو أوقاف، استمرار المراقبة النشطة."
    status_str = '🔴 توقف فوري لتشريح الخسارة' if stopped_on_loss else ('🟢 صفقة فعالة: ' + active_position['id'] if active_position else '🛡️ CASH ARMOR (100% حياد نقدي)')

    batch_md = f"""
---

## 📦 الدفعة {current_batch_num} (Batch {current_batch_num}: Snapshots {snap_indices[0]} - {snap_indices[-1]})
* **الملفات المفحوصة:**
  1. `{s1['fname']}` (Snap {snap_indices[0]})
  2. `{s2['fname']}` (Snap {snap_indices[1]})
  3. `{s3['fname']}` (Snap {snap_indices[-1]})
* **النطاق السعري للدفعة:** `${min(s['price'] for s in snaps):.2f} - ${max(s['price'] for s in snaps):.2f} USD`.

### 📊 جدول التليمترية الجنائية المقارنة:
| المعيار التليميتري | اللقطة {snap_indices[0]} | اللقطة {snap_indices[1]} | اللقطة {snap_indices[-1]} |
| :--- | :---: | :---: | :---: |
| **سعر الفيوتشرز (Futures Price)** | ${s1['price']:.2f} | ${s2['price']:.2f} | ${s3['price']:.2f} |
| **سعر السبوت (Spot Price)** | ${s1['spot']:.2f} | ${s2['spot']:.2f} | ${s3['spot']:.2f} |
| **علاوة السبوت (Spot Basis)** | {s1['basis']:+.2f} USD | {s2['basis']:+.2f} USD | {s3['basis']:+.2f} USD |
| **تسارع دلتا العقود (Futures CVD Velocity)** | {s1['cvd_vel']:+.2f} | {s2['cvd_vel']:+.2f} | {s3['cvd_vel']:+.2f} |
| **الفايدة المفتوحة (OI)** | {s1['oi']:.1f} BTC | {s2['oi']:.1f} BTC | {s3['oi']:.1f} BTC |
| **موقع شمعة 15m (CLV)** | {clv1:.4f} | {clv2:.4f} | {clv3:.4f} |
| **حجم الشمعة (Volume)** | {vol1:.2f} BTC | {vol2:.2f} BTC | {vol3:.2f} BTC |
| **الرصيد التراكمي المحقق** | — | — | **${cumulative_pnl:+.2f} USD** |

### ⚖️ التحكيم وقرار المنظومة (Phase 16.0 Enforcement):
* **أحداث الصفقات الميدانية:**
  - {events_str}
* **الموقف الميداني الصارم:**
  - **القرار:** `{status_str}`.
"""
    batch_reports.append(batch_md)
    
    print(f"[{batch_title}] Price: ${s3['price']:.2f} | Basis: {s3['basis']:+.2f}$ | Cumulative PnL: ${cumulative_pnl:+.2f} | Status: {'STOPPED ON LOSS' if stopped_on_loss else ('Active: ' + active_position['id'] if active_position else 'Cash Armor')}")
    if trade_events:
        for ev in trade_events:
            print(f"   -> {ev}")
            
    if stopped_on_loss:
        print(f"\n🚨 STOPPED ON LOSS: {stop_reason}")
        break
        
    current_batch_num += 1
    curr_idx += 3

# Append all batch reports to the journal
with open(JOURNAL_PATH, 'a', encoding='utf-8') as jf:
    for rep in batch_reports:
        jf.write(rep)

print(f"\nEngine completed {len(batch_reports)} batches.")
print(f"Final Cumulative Net PnL: ${cumulative_pnl:+.2f} USD")
print(f"Completed Trades in Run: {len(completed_trades)}")
for t in completed_trades:
    print(f" - {t['id']}: {t['type']} Entry ${t['entry']:.2f} -> Exit ${t.get('exit_price', 0):.2f} = {t.get('pnl', 0):+.2f}$ ({t['status']})")
if active_position:
    print(f"Still Active: {active_position['id']} ({active_position['type']} Entry ${active_position['entry']:.2f})")
print(f"Stopped on loss? {stopped_on_loss}")
