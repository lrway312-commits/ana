import sys
sys.path.append('price_analysis')
sys.stdout.reconfigure(encoding='utf-8')
from directional_parser import parse_snap

print("Caching snapshots 1455 to 1690...")
cached_snaps = {}
for idx in range(1455, 1690):
    s = parse_snap(idx)
    if s:
        cached_snaps[idx] = s

print(f"Cached {len(cached_snaps)} snapshots.")

active_trade = None
closed_trades = []
trade_counter = 37 # Continuing from Trade D-36

last_tp2_snap = -999

for idx in range(1469, 1680):
    s = cached_snaps.get(idx)
    s_prev = cached_snaps.get(idx - 1)
    s_prev2 = cached_snaps.get(idx - 2)
    s_prev3 = cached_snaps.get(idx - 3)
    if not s or not s_prev:
        continue
    
    p = s['price']
    cvd = s['cvd_velocity']
    basis = s['basis']
    clv = s['clv']
    ratio = s['bid_depth_15'] / (s['ask_depth_15'] or 1.0)
    avwap = s['avwap_mean']
    bids15 = s['bid_depth_15']
    asks15 = s['ask_depth_15']
    has_bid_wall = len(s['bid_walls']) > 0
    move_from_prev = p - s_prev['close']
    k_range = s['high'] - s['low']
    
    recent_high = max(cached_snaps[k]['high'] for k in range(max(1455, idx-10), idx))
    recent_low = min(cached_snaps[k]['low'] for k in range(max(1455, idx-10), idx))
    
    # Trade management
    if active_trade:
        is_long = active_trade['direction'] == 'LONG'
        entry = active_trade['entry_price']
        sl = active_trade['sl']
        tp1 = active_trade['tp1']
        tp2 = active_trade['tp2']
        
        if is_long:
            if s['high'] >= entry + 75.0 and not active_trade['tp1_hit']:
                if active_trade['sl'] < entry + 20.0:
                    active_trade['sl'] = entry + 20.0
            
            if s['low'] <= sl:
                loss = sl - entry
                active_trade['exit_price'] = sl
                active_trade['pnl'] = loss
                active_trade['status'] = 'STOP_LOSS' if loss < 0 else 'BE_EXIT'
                active_trade['exit_snap'] = s['idx']
                closed_trades.append(dict(active_trade))
                active_trade = None
            elif s['high'] >= tp2 and active_trade['tp1_hit']:
                active_trade['exit_price'] = tp2
                pnl_gain = (tp1 - entry)*0.5 + (tp2 - entry)*0.5
                active_trade['pnl'] = pnl_gain
                active_trade['status'] = 'TP2_HIT'
                active_trade['exit_snap'] = s['idx']
                last_tp2_snap = s['idx']
                closed_trades.append(dict(active_trade))
                active_trade = None
            elif s['high'] >= tp1 and not active_trade['tp1_hit']:
                active_trade['tp1_hit'] = True
                active_trade['sl'] = entry + 25.0
        else:
            if s['low'] <= entry - 75.0 and not active_trade['tp1_hit']:
                if active_trade['sl'] > entry - 20.0:
                    active_trade['sl'] = entry - 20.0
            if s['high'] >= sl:
                loss = entry - sl
                active_trade['exit_price'] = sl
                active_trade['pnl'] = loss
                active_trade['status'] = 'STOP_LOSS' if loss < 0 else 'BE_EXIT'
                active_trade['exit_snap'] = s['idx']
                closed_trades.append(dict(active_trade))
                active_trade = None
            elif s['low'] <= tp2 and active_trade['tp1_hit']:
                active_trade['exit_price'] = tp2
                pnl_gain = (entry - tp1)*0.5 + (entry - tp2)*0.5
                active_trade['pnl'] = pnl_gain
                active_trade['status'] = 'TP2_HIT'
                active_trade['exit_snap'] = s['idx']
                last_tp2_snap = s['idx']
                closed_trades.append(dict(active_trade))
                active_trade = None
            elif s['low'] <= tp1 and not active_trade['tp1_hit']:
                active_trade['tp1_hit'] = True
                active_trade['sl'] = entry - 25.0
    
    if not active_trade:
        # Applying Laws 1 to 9
        has_passive_cushion = (bids15 >= 7.5) # Law 1
        spoof_bid_wall = (has_bid_wall and cvd < 0.0 and (s_prev['clv'] <= 0.05 or s_prev['cvd_velocity'] <= -40.0)) # Law 2
        bid_wall_harmonious = not spoof_bid_wall
        ceiling_friction = (recent_high - p <= 30.0 and p <= recent_high) # Law 3
        clear_runway = not ceiling_friction
        is_waterfall = (s_prev2 and (s_prev2['high'] - p > 400.0) and s_prev['close'] < s_prev2['low'])
        sweep_completed = not (is_waterfall and p > recent_low) # Law 4
        
        descending_highs = (s_prev3 and s_prev['high'] < s_prev2['high'] < s_prev3['high'])
        law6_ok = not (descending_highs and p < max(s_prev['high'], s_prev2['high'], s_prev3['high'])) # Law 6
        law7_ok = not (s_prev['cvd_velocity'] <= -100.0) # Law 7
        law8_ok = not (s['idx'] <= last_tp2_snap + 1) # Law 8: Climax TP2 Re-entry Prohibition
        law9_ok = (k_range >= 35.0) # Law 9: Minimum Spring Volatility Mandate
        
        long_l1 = (cvd >= 35.0 and basis >= 25.0 and clv >= 0.70 and p >= avwap and asks15 < 15.0 and move_from_prev <= 250.0 and has_passive_cushion and clear_runway and sweep_completed and law6_ok and law8_ok)
        long_l2 = (clv >= 0.70 and bids15 >= 12.0 and basis >= 20.0 and has_bid_wall and cvd >= -10.0 and p <= avwap + 20.0 and bid_wall_harmonious and clear_runway and law9_ok)
        long_l3 = (ratio >= 3.5 and has_bid_wall and bids15 >= 15.0 and basis >= 25.0 and clv >= 0.45 and cvd >= -20.0 and p <= avwap and bid_wall_harmonious and law7_ok)
        
        short_s1 = (basis <= 5.0 and cvd <= 5.0 and p >= avwap and clv <= 0.40)
        short_s2 = (cvd <= -35.0 and p <= avwap and p >= avwap - 200.0 and clv <= 0.30 and basis <= 20.0 and bids15 < 8.0)
        
        if long_l1 or long_l2 or long_l3:
            eng_name = 'L1_ABSORPTION' if long_l1 else ('L2_SPRING_RECLAIM' if long_l2 else 'L3_ICEBERG_FLOOR')
            t_id = f'Trade D-{trade_counter}'
            trade_counter += 1
            sl_val = s['low'] - 40.0
            tp1_val = p + 120.0
            tp2_val = p + 250.0
            active_trade = {
                'id': t_id,
                'direction': 'LONG',
                'engine': eng_name,
                'entry_snap': s['idx'],
                'entry_price': p,
                'sl': sl_val,
                'tp1': tp1_val,
                'tp2': tp2_val,
                'tp1_hit': False
            }
        elif short_s1 or short_s2:
            eng_name = 'S1_UPTHRUST_EXHAUSTION' if short_s1 else 'S2_BREAKDOWN_CASCADE'
            t_id = f'Trade D-{trade_counter}'
            trade_counter += 1
            sl_val = s['high'] + 40.0
            tp1_val = p - 120.0
            tp2_val = p - 250.0
            active_trade = {
                'id': t_id,
                'direction': 'SHORT',
                'engine': eng_name,
                'entry_snap': s['idx'],
                'entry_price': p,
                'sl': sl_val,
                'tp1': tp1_val,
                'tp2': tp2_val,
                'tp1_hit': False
            }

print(f"Total closed trades in 1470-1680: {len(closed_trades)}")
for t in closed_trades:
    print(f"{t['id']} ({t['direction']}) | Entry: Snap {t['entry_snap']} (${t['entry_price']:,.2f}) -> Exit: Snap {t['exit_snap']} (${t['exit_price']:,.2f}) | PnL: ${t['pnl']:+,.2f} USD | Engine: {t['engine']} | Status: {t['status']}")

pnl_tot = sum(t['pnl'] for t in closed_trades)
wins = len([t for t in closed_trades if t['pnl'] > 0])
wr = (wins / len(closed_trades) * 100) if closed_trades else 0
print(f"\nRealized PnL: ${pnl_tot:+,.2f} USD/BTC | Win Rate: {wr:.1f}% ({wins}/{len(closed_trades)})")
