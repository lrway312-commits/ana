import sys, json, os
sys.stdout.reconfigure(encoding='utf-8')

f = 'price_analysis/بيانات/BTCUSDT_snapshot_1793249952255.json'
with open(f, 'r', encoding='utf-8') as fp:
    d = json.load(fp)

cur = d.get('current', {})
series = d.get('series', {})
analysis = d.get('analysis', {})
ob = d.get('order_book', {})

p = cur.get('current_price') or d.get('price')
spot = cur.get('spot_price') or d.get('spot') or p
basis = (spot - p) if spot and p else 0.0
cvd = cur.get('futures_cvd_velocity') or 0.0
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
else:
    k_open = k_high = k_low = k_close = p
    k_vol = 0.0

clv = (k_close - k_low) / (k_high - k_low) if (k_high - k_low) > 0 else 0.5

bids = ob.get('bids', [])
asks = ob.get('asks', [])
b_sum = sum(float(b[1]) for b in bids[:15]) if bids else 0.0
a_sum = sum(float(a[1]) for a in asks[:15]) if asks else 0.0

# Calculate AVWAP
cum_vol = 0.0
cum_pv = 0.0
for k in klines[-20:]:
    if isinstance(k, list) and len(k) >= 6:
        cv = float(k[4])
        vv = float(k[5])
        cum_vol += vv
        cum_pv += (cv * vv)
avwap_mean = cum_pv / cum_vol if cum_vol > 0 else p

# Calculate standard deviation of close for bands
import math
variance = sum(((float(k[4]) - avwap_mean)**2) * float(k[5]) for k in klines[-20:] if isinstance(k, list) and len(k) >= 6) / cum_vol if cum_vol > 0 else 0
std_dev = math.sqrt(variance) if variance > 0 else 50.0

avwap_upper1 = avwap_mean + std_dev
avwap_lower1 = avwap_mean - std_dev

print(f"LATEST LIVE SNAPSHOT AUDIT:")
print(f"File: {os.path.basename(f)}")
print(f"Timestamp: {d.get('timestamp')}")
print(f"Futures Price: ${p:,.2f}")
print(f"Spot Price: ${spot:,.2f} | Basis: {basis:+,.2f} USD")
print(f"Futures CVD Velocity: {cvd:+,.2f} | Net Flow: {net_flow:+,.2f} BTC")
print(f"Open Interest: {oi:,.2f} BTC")
print(f"15m Candle: O=${k_open:,.2f} H=${k_high:,.2f} L=${k_low:,.2f} C=${k_close:,.2f} | CLV={clv:.4f} | Vol={k_vol:,.2f} BTC")
print(f"Orderbook 15 depth: Bids={b_sum:.2f} BTC vs Asks={a_sum:.2f} BTC | Ratio={b_sum/(a_sum or 1.0):.2f}x")
print(f"AVWAP Mean: ${avwap_mean:,.2f} | Upper 1s: ${avwap_upper1:,.2f} | Lower 1s: ${avwap_lower1:,.2f}")
