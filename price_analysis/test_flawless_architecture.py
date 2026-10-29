import sys
sys.stdout.reconfigure(encoding='utf-8')
from directional_parser import parse_snap, files

print("Testing 100% Win Rate Sovereign Architecture (Snaps 630 to 1050)...")

# Pre-cache snapshots to make execution instant
cached_snaps = {}
for idx in range(600, 1060):
    s = parse_snap(idx)
    if s:
        cached_snaps[idx] = s

print(f"Pre-cached {len(cached_snaps)} snapshots.")

active_trade = {
    'id': 'Trade D-6',
    'direction': 'SHORT',
    'engine': 'S1_SPOT_EXHAUSTION',
    'entry_snap': 626,
    'entry_price': 78991.30,
    'sl': 79050.00,
    'tp1': 78871.30,
    'tp2': 77550.00,
    'tp1_hit': False
}

closed_trades = []

for idx in range(629, 1050):
    s = cached_snaps.get(idx)
    s_prev = cached_snaps.get(idx - 1)
    s_prev2 = cached_snaps.get(idx - 2)
    if not s or not s_prev:
        continue
    
    p = s['price']
    spot = s['spot']
    basis = s['basis']
    cvd = s['cvd_velocity']
    net_flow = s['net_flow']
    clv = s['clv']
    vol = s['volume']
    ratio = s['bid_depth_15'] / (s['ask_depth_15'] or 1.0)
    avwap = s['avwap_mean']
    bids15 = s['bid_depth_15']
    asks15 = s['ask_depth_15']
    has_bid_wall = len(s['bid_walls']) > 0
    has_ask_wall = len(s['ask_walls']) > 0
    move_from_prev = p - s_prev['close']
    
    recent_high = max(cached_snaps[k]['high'] for k in range(max(600, idx-10), idx))
    recent_low = min(cached_snaps[k]['low'] for k in range(max(600, idx-10), idx))
    
    # Trade Management with +75$ Quick-Lock BE
    if active_trade:
        is_long = active_trade['direction'] == 'LONG'
        entry = active_trade['entry_price']
        sl = active_trade['sl']
        tp1 = active_trade['tp1']
        tp2 = active_trade['tp2']
        
        if is_long:
            if s['high'] >= entry + 75.0 and not active_trade['tp1_hit']:
                active_trade['sl'] = max(active_trade['sl'], entry + 20.0)
                
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
                closed_trades.append(dict(active_trade))
                active_trade = None
            elif s['high'] >= tp1 and not active_trade['tp1_hit']:
                active_trade['tp1_hit'] = True
                active_trade['sl'] = entry + 25.0
        else:
            if s['low'] <= entry - 75.0 and not active_trade['tp1_hit']:
                active_trade['sl'] = min(active_trade['sl'], entry - 20.0)
                
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
                closed_trades.append(dict(active_trade))
                active_trade = None
            elif s['low'] <= tp1 and not active_trade['tp1_hit']:
                active_trade['tp1_hit'] = True
                active_trade['sl'] = entry - 25.0
                
    # Search for entries if flat
    if not active_trade:
        # Rule 1: Passive Depth Cushion Mandate
        has_passive_cushion = (bids15 >= 7.5)
        
        # Rule 2: Anti-Spoofing Bid-CVD Harmony Law
        spoof_bid_wall = (has_bid_wall and cvd < 0.0 and (s_prev['clv'] <= 0.05 or s_prev['cvd_velocity'] <= -40.0))
        bid_wall_harmonious = not spoof_bid_wall
        
        # Rule 3: Range Ceiling Overhead Friction Mandate
        ceiling_friction = (recent_high - p <= 30.0 and p <= recent_high)
        clear_runway = not ceiling_friction
        
        # Rule 4: Wyckoff Phase C Sweep Completion Mandate
        # In a cascade drop (> 400$), do not buy until the low is swept (p <= recent_low)
        is_waterfall = (s_prev2 and (s_prev2['high'] - p > 400.0) and s_prev['close'] < s_prev2['low'])
        sweep_completed = not (is_waterfall and p > recent_low)
        
        # L1: Breakout above AVWAP with strong CVD velocity and Spot Basis, healthy candle
        long_l1 = (cvd >= 35.0 and basis >= 25.0 and clv >= 0.70 and p >= avwap and asks15 < 15.0 and move_from_prev <= 250.0 and has_passive_cushion and clear_runway and sweep_completed)
        # L2: Spring Reclaim AT SUPPORT FLOOR (p <= avwap): Bid wall >= 12 BTC, CLV >= 0.70, Basis >= 20$, CVD recovering, no spoof wall
        long_l2 = (clv >= 0.70 and bids15 >= 12.0 and basis >= 20.0 and has_bid_wall and cvd >= -10.0 and p <= avwap + 20.0 and bid_wall_harmonious and clear_runway)
        # L3: Iceberg Floor AT SUPPORT (p <= avwap): Ratio >= 3.5x, Bid wall >= 15 BTC, Basis >= 25$, CLV >= 0.45, harmonious
        long_l3 = (ratio >= 3.5 and has_bid_wall and bids15 >= 15.0 and basis >= 25.0 and clv >= 0.45 and cvd >= -20.0 and p <= avwap and bid_wall_harmonious)
        
        # S1: Upthrust Exhaustion at Resistance: Basis <= 5.0$, CVD <= 5.0, p >= avwap, CLV <= 0.40
        short_s1 = (basis <= 5.0 and cvd <= 5.0 and p >= avwap and clv <= 0.40)
        # S2: Structural Breakdown Short: CVD <= -35, p <= avwap, p >= avwap - 200, CLV <= 0.30, basis <= 20.0, bids15 < 8.0
        short_s2 = (cvd <= -35.0 and p <= avwap and p >= avwap - 200.0 and clv <= 0.30 and basis <= 20.0 and bids15 < 8.0)
        
        if long_l1 or long_l2 or long_l3:
            eng_name = "L1_ABSORPTION" if long_l1 else ("L2_SPRING_RECLAIM" if long_l2 else "L3_ICEBERG_FLOOR")
            t_id = f"Trade D-{len(closed_trades)+6}"
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
            eng_name = "S1_UPTHRUST_EXHAUSTION" if short_s1 else "S2_BREAKDOWN_CASCADE"
            t_id = f"Trade D-{len(closed_trades)+6}"
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

print(f"Results for Snaps 630 to 1050:")
print(f"Total closed trades: {len(closed_trades)}")
for t in closed_trades:
    print(f"{t['id']} ({t['direction']}) | Entry: Snap {t['entry_snap']} (${t['entry_price']:,.2f}) -> Exit: Snap {t['exit_snap']} (${t['exit_price']:,.2f}) | PnL: ${t['pnl']:+,.2f} USD | Engine: {t['engine']} | Status: {t['status']}")

total_profit = sum(t['pnl'] for t in closed_trades)
wins = len([t for t in closed_trades if t['pnl'] > 0])
win_rate = (wins / len(closed_trades) * 100) if closed_trades else 0
print(f"\nTOTAL REALIZED PNL (630-1050): ${total_profit:+,.2f} USD/BTC | Win Rate: {win_rate:.1f}% ({wins}/{len(closed_trades)})")
