import sys, glob, json, os, math

sys.stdout.reconfigure(encoding='utf-8')

files = sorted(glob.glob('price_analysis/بيانات/BTCUSDT_snapshot_*.json'), key=os.path.getmtime)

def parse_snap(idx):
    if idx >= len(files):
        return None
    f = files[idx]
    try:
        with open(f, 'r', encoding='utf-8') as fp:
            d = json.load(fp)
    except Exception as e:
        return None

    cur = d.get('current', {})
    series = d.get('series', {})
    ob = d.get('order_book', {})
    
    p = cur.get('current_price') or d.get('price') or 0.0
    spot = cur.get('spot_price') or d.get('spot') or p
    basis = (spot - p) if (spot and p) else 0.0
    cvd_vel = cur.get('futures_cvd_velocity') or 0.0
    oi = cur.get('open_interest') or 0.0
    net_flow = cur.get('institutional_net_flow') or 0.0
    
    klines = series.get('klines_15m', [])
    last_k = klines[-1] if klines else []
    if isinstance(last_k, list) and len(last_k) >= 6:
        k_open = float(last_k[1])
        k_high = float(last_k[2])
        k_low = float(last_k[3])
        k_close = float(last_k[4])
        k_vol = float(last_k[5])
    elif isinstance(last_k, dict):
        k_open = float(last_k.get('open', p))
        k_high = float(last_k.get('high', p))
        k_low = float(last_k.get('low', p))
        k_close = float(last_k.get('close', p))
        k_vol = float(last_k.get('volume', 0.0))
    else:
        k_open = k_high = k_low = k_close = p
        k_vol = 0.0

    clv = 0.5
    if k_high - k_low > 0:
        clv = (k_close - k_low) / (k_high - k_low)

    bids = ob.get('bids', [])
    asks = ob.get('asks', [])
    bid_sum_15 = 0.0
    ask_sum_15 = 0.0
    bid_walls = []
    ask_walls = []
    
    for b in bids[:15]:
        bp, bq = float(b[0]), float(b[1])
        bid_sum_15 += bq
        if bq >= 10.0:
            bid_walls.append((bp, bq))
            
    for a in asks[:15]:
        ap, aq = float(a[0]), float(a[1])
        ask_sum_15 += aq
        if aq >= 10.0:
            ask_walls.append((ap, aq))

    # Calculate AVWAP
    cum_vol = 0.0
    cum_pv = 0.0
    for k in klines[-20:]:
        if isinstance(k, list) and len(k) >= 6:
            c_val = float(k[4])
            v_val = float(k[5])
        elif isinstance(k, dict):
            c_val = float(k.get('close', p))
            v_val = float(k.get('volume', 0.0))
        else:
            continue
        cum_vol += v_val
        cum_pv += (c_val * v_val)
    avwap_mean = (cum_pv / cum_vol) if cum_vol > 0 else p

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
        'open': k_open,
        'high': k_high,
        'low': k_low,
        'close': k_close,
        'volume': k_vol,
        'clv': clv,
        'bid_depth_15': bid_sum_15,
        'ask_depth_15': ask_sum_15,
        'bid_walls': bid_walls,
        'ask_walls': ask_walls,
        'avwap_mean': avwap_mean
    }

print("Parsing engine loaded successfully. Ready to run directional audit.")
