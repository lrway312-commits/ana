import sys, glob, json, os, math

sys.stdout.reconfigure(encoding='utf-8')

files = sorted(glob.glob('price_analysis/بيانات/BTCUSDT_snapshot_*.json'), key=os.path.getmtime)

def parse_institutional_snap(idx):
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
    oi_z = cur.get('oi_z_score') or 0.0
    funding = cur.get('funding_rate') or 0.0
    net_flow = cur.get('institutional_net_flow') or 0.0
    wyckoff_ratio = cur.get('wyckoff_effort_vs_result_ratio') or 1.0
    stoikov_p = cur.get('stoikov_micro_price') or p
    micro_bps = cur.get('micro_price_bps') or 0.0
    
    # Series taker volumes
    taker_buys = series.get('taker_buy_volume', [])
    taker_sells = series.get('taker_sell_volume', [])
    tb_now = float(taker_buys[-1]) if taker_buys else 0.0
    ts_now = float(taker_sells[-1]) if taker_sells else 0.0
    taker_ratio = tb_now / (ts_now + 1e-5) if ts_now else 1.0
    
    # Klines
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

    # Order book
    bids = ob.get('bids', [])
    asks = ob.get('asks', [])
    bid_sum_15 = sum([float(b[1]) for b in bids[:15]]) if bids else 0.0
    ask_sum_15 = sum([float(a[1]) for a in asks[:15]]) if asks else 0.0
    bid_walls = [float(b[0]) for b in bids[:15] if float(b[1]) >= 10.0]
    ask_walls = [float(a[0]) for a in asks[:15] if float(a[1]) >= 10.0]

    # AVWAP
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
        'oi_z': oi_z,
        'funding': funding,
        'net_flow': net_flow,
        'wyckoff_ratio': wyckoff_ratio,
        'stoikov_p': stoikov_p,
        'micro_bps': micro_bps,
        'taker_buy': tb_now,
        'taker_sell': ts_now,
        'taker_ratio': taker_ratio,
        'open': k_open,
        'high': k_high,
        'low': k_low,
        'close': k_close,
        'volume': k_vol,
        'clv': clv,
        'bid_depth_15': bid_sum_15,
        'ask_depth_15': ask_sum_15,
        'depth_ratio': bid_sum_15 / (ask_sum_15 or 1.0),
        'bid_walls': bid_walls,
        'ask_walls': ask_walls,
        'avwap_mean': avwap_mean
    }
