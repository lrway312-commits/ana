import sys, glob, json, os

sys.stdout.reconfigure(encoding='utf-8')

files = sorted(glob.glob('price_analysis/بيانات/BTCUSDT_snapshot_*.json'), key=os.path.getmtime)

def get_snap_data(idx):
    if idx >= len(files):
        return None
    f = files[idx]
    with open(f, 'r', encoding='utf-8') as fp:
        d = json.load(fp)
    
    cur = d.get('current', {})
    series = d.get('series', {})
    analysis = d.get('analysis', {})
    ob = d.get('order_book', {})
    
    p = cur.get('current_price') or d.get('price')
    spot = cur.get('spot_price') or d.get('spot') or p
    basis = (spot - p) if (spot and p) else 0.0
    cvd_vel = cur.get('futures_cvd_velocity') or 0.0
    oi = cur.get('open_interest') or 0.0
    net_flow = cur.get('institutional_net_flow') or 0.0
    wyckoff_eff = cur.get('wyckoff_effort_vs_result_ratio') or 0.0
    micro_price = cur.get('stoikov_micro_price') or p
    
    klines = series.get('klines_15m', [])
    last_k = klines[-1] if klines else []
    if isinstance(last_k, list) and len(last_k) >= 6:
        k_open = float(last_k[1])
        k_high = float(last_k[2])
        k_low = float(last_k[3])
        k_close = float(last_k[4])
        k_vol = float(last_k[5])
    elif isinstance(last_k, dict):
        k_open = float(last_k.get('open', p or 0.0))
        k_high = float(last_k.get('high', p or 0.0))
        k_low = float(last_k.get('low', p or 0.0))
        k_close = float(last_k.get('close', p or 0.0))
        k_vol = float(last_k.get('volume', 0.0))
    else:
        k_open = k_high = k_low = k_close = float(p or 0.0)
        k_vol = 0.0
    
    clv = 0.5
    if k_high - k_low > 0:
        clv = (k_close - k_low) / (k_high - k_low)
        
    bids = ob.get('bids', [])
    asks = ob.get('asks', [])
    # parse bids/asks: could be [[price, size], ...] or strings
    bid_sum_10 = 0.0
    ask_sum_10 = 0.0
    bid_walls = []
    ask_walls = []
    
    for b in bids[:15]:
        bp, bq = float(b[0]), float(b[1])
        bid_sum_10 += bq
        if bq >= 10.0:
            bid_walls.append((bp, bq))
            
    for a in asks[:15]:
        ap, aq = float(a[0]), float(a[1])
        ask_sum_10 += aq
        if aq >= 10.0:
            ask_walls.append((ap, aq))
            
    # SMC & Liquidation
    smc = analysis.get('smc_structures', {})
    liq = analysis.get('liquidation_clusters', {})
    
    # Calculate AVWAP from past 20 klines if available
    cum_vol = 0.0
    cum_pv = 0.0
    for k in klines[-20:]:
        if isinstance(k, list) and len(k) >= 6:
            c_val = float(k[4])
            v_val = float(k[5])
        elif isinstance(k, dict):
            c_val = float(k.get('close', 0.0))
            v_val = float(k.get('volume', 0.0))
        else:
            continue
        cum_vol += v_val
        cum_pv += (c_val * v_val)
    avwap_mean = (cum_pv / cum_vol) if cum_vol > 0 else (p or 0.0)
    
    # Future trajectory: look at next 12 snapshots (approx 3 hours)
    future_prices = []
    for f_idx in range(idx + 1, min(idx + 13, len(files))):
        try:
            with open(files[f_idx], 'r', encoding='utf-8') as f_fp:
                f_d = json.load(f_fp)
                f_p = f_d.get('current', {}).get('current_price') or f_d.get('price')
                if f_p:
                    future_prices.append(float(f_p))
        except:
            pass
            
    f_min = min(future_prices) if future_prices else p
    f_max = max(future_prices) if future_prices else p
    f_end = future_prices[-1] if future_prices else p
    
    return {
        'idx': idx + 1,
        'filename': os.path.basename(f),
        'timestamp': d.get('timestamp'),
        'price': p,
        'spot': spot,
        'basis': basis,
        'cvd_velocity': cvd_vel,
        'oi': oi,
        'net_flow': net_flow,
        'wyckoff_eff': wyckoff_eff,
        'micro_price': micro_price,
        'open': k_open,
        'high': k_high,
        'low': k_low,
        'close': k_close,
        'volume': k_vol,
        'clv': clv,
        'bid_depth_15': bid_sum_10,
        'ask_depth_15': ask_sum_10,
        'bid_walls': bid_walls,
        'ask_walls': ask_walls,
        'avwap_mean': avwap_mean,
        'future_prices': future_prices,
        'f_min': f_min,
        'f_max': f_max,
        'f_end': f_end
    }

def print_batch_analysis(start_idx, count=3):
    print("="*80)
    batch_num = (start_idx // 3) + 1
    print(f"FORENSIC ANALYSIS FOR BATCH {batch_num} (Snapshots {start_idx+1} to {start_idx+count})")
    print("="*80)
    
    snaps = []
    for i in range(start_idx, start_idx + count):
        s = get_snap_data(i)
        if s:
            snaps.append(s)
            print(f"Snap {s['idx']}: {s['filename']}")
            print(f"  Futures Price: ${s['price']:,.2f} | Spot: ${s['spot']:,.2f} | Basis: {s['basis']:+,.2f}$")
            print(f"  CVD Velocity: {s['cvd_velocity']:+,.2f} | Net Flow: {s['net_flow']:+,.2f} BTC | OI: {s['oi']:,.1f} BTC")
            print(f"  15m Candle: O={s['open']} H={s['high']} L={s['low']} C={s['close']} | CLV={s['clv']:.3f} | Vol={s['volume']:,.2f} BTC")
            print(f"  Orderbook: Bids(15)={s['bid_depth_15']:.2f} BTC | Asks(15)={s['ask_depth_15']:.2f} BTC | Ratio={s['bid_depth_15']/(s['ask_depth_15'] or 1.0):.2f}")
            print(f"  Major Bid Walls: {s['bid_walls'][:3]} | Major Ask Walls: {s['ask_walls'][:3]}")
            print(f"  AVWAP Mean (20k): ${s['avwap_mean']:,.2f}")
            print(f"  Forward Path (next 12 snaps): Min=${s['f_min']:,.2f} | Max=${s['f_max']:,.2f} | End=${s['f_end']:,.2f} (Delta={s['f_end'] - s['price']:+,.2f}$)")
            print("-"*50)
            
if __name__ == '__main__':
    # Let's inspect Batches 175, 176, 177 (Snaps 522 to 530)
    print_batch_analysis(521, 3) # Batch 175: Snaps 522-524
    print_batch_analysis(524, 3) # Batch 176: Snaps 525-527
    print_batch_analysis(527, 3) # Batch 177: Snaps 528-530
