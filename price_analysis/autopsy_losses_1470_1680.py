import sys
sys.path.append('price_analysis')
sys.stdout.reconfigure(encoding='utf-8')
from directional_parser import parse_snap

print("=== AUTOPSY SNAP 1633 (Trade D-39) ===")
for idx in range(1630, 1637):
    s = parse_snap(idx)
    i = s['idx']
    p = s['price']
    h = s['high']
    l = s['low']
    c = s['close']
    cvd = s['cvd_velocity']
    basis = s['basis']
    bids15 = s['bid_depth_15']
    walls = s['bid_walls']
    print(f"Snap {i}: P={p}, H={h}, L={l}, C={c}, CVD={cvd:.1f}, Basis={basis:.1f}, Bids15={bids15:.1f}, Walls={walls}")

print("\n=== AUTOPSY SNAP 1669 (Trade D-41) ===")
for idx in range(1666, 1673):
    s = parse_snap(idx)
    i = s['idx']
    p = s['price']
    h = s['high']
    l = s['low']
    c = s['close']
    cvd = s['cvd_velocity']
    basis = s['basis']
    bids15 = s['bid_depth_15']
    asks15 = s['ask_depth_15']
    print(f"Snap {i}: P={p}, H={h}, L={l}, C={c}, CVD={cvd:.1f}, Basis={basis:.1f}, Bids15={bids15:.1f}, Asks15={asks15:.1f}")
