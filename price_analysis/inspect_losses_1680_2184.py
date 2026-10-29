import sys
sys.path.append('price_analysis')
sys.stdout.reconfigure(encoding='utf-8')
from directional_parser import parse_snap

print("=== INSPECTION OF LOSSES IN 1680-2184 ===")

for snap_id in [1747, 1789, 1827, 1846, 1853, 1912, 2018]:
    s = parse_snap(snap_id - 1)
    s_prev = parse_snap(snap_id - 2)
    p = s['price']
    cvd = s['cvd_velocity']
    basis = s['basis']
    clv = s['clv']
    bids15 = s['bid_depth_15']
    asks15 = s['ask_depth_15']
    ratio = bids15 / (asks15 or 1)
    walls = s['bid_walls']
    print(f"\n--- SNAP {snap_id} ---")
    print(f"Price: {p}, High: {s['high']}, Low: {s['low']}, Close: {s['close']}")
    print(f"Prev P: {s_prev['price']}, Prev Low: {s_prev['low']}, Prev CVD: {s_prev['cvd_velocity']:.1f}")
    print(f"CVD: {cvd:.1f}, Basis: {basis:.1f}, CLV: {clv:.2f}, Bids15: {bids15:.1f}, Asks15: {asks15:.1f}, Ratio: {ratio:.1f}")
    print(f"Bid Walls: {walls}")
