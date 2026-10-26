import time
import hmac
import hashlib
import requests
import urllib.request
import json
from typing import Dict, Any, List, Tuple
import os

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
SYMBOL = 'BTCUSDT'

BASE_FAPI = "https://fapi.binance.com"
BASE_SPOT = "https://api.binance.com"

try:
    from derivatives_intel import get_derivatives_intel
    from smc_engine import analyze_smc
except ImportError:
    try:
        from src.derivatives_intel import get_derivatives_intel
        from src.smc_engine import analyze_smc
    except ImportError:
        get_derivatives_intel = None
        analyze_smc = None


def get_spot_price(symbol: str = SYMBOL) -> float:
    """جلب السعر الحالي من سوق السبوت (Binance Spot)"""
    try:
        url = f"{BASE_SPOT}/api/v3/ticker/price"
        r = requests.get(url, params={"symbol": symbol})
        r.raise_for_status()
        data = r.json()
        return float(data.get("price", 0.0))
    except Exception as e:
        print(f"Error fetching spot price: {e}")
        return 0.0

def get_spot_aggregate_trades(symbol: str = SYMBOL, limit: int = 500, start_time: int = None, end_time: int = None) -> List[Dict[str, Any]]:
    """جلب التداولات المجمعة من سوق السبوت"""
    url = f"{BASE_SPOT}/api/v3/aggTrades"
    params = {
        "symbol": symbol,
        "limit": limit
    }
    if start_time and end_time:
        params["startTime"] = start_time
        params["endTime"] = end_time
    else:
        end_time = int(time.time() * 1000)
        start_time = end_time - (5 * 60 * 1000)
        params["startTime"] = start_time
        params["endTime"] = end_time

    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error fetching spot agg trades: {e}")
        return []

def get_premium_index_info(symbol: str = SYMBOL) -> Dict[str, Any]:
    """جلب بيانات مؤشر العلاوة ومعدل التمويل الحالي"""
    try:
        url = f"{BASE_FAPI}/fapi/v1/premiumIndex"
        r = requests.get(url, params={"symbol": symbol})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error fetching premium index: {e}")
        return {}

def _headers():
    return {"X-MBX-APIKEY": BINANCE_API_KEY}

def _sign(params: Dict[str, Any]) -> Dict[str, Any]:
    query = "&".join([f"{k}={params[k]}" for k in params])
    signature = hmac.new(BINANCE_API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = signature
    return params

def get_funding_rates(symbol: str = SYMBOL, limit: int = 10) -> List[Dict[str, Any]]:
    url = f"{BASE_FAPI}/fapi/v1/fundingRate"
    r = requests.get(url, params={"symbol": symbol, "limit": limit})
    r.raise_for_status()
    return r.json()

def get_open_interest(symbol: str = SYMBOL) -> float:
    url = f"{BASE_FAPI}/fapi/v1/openInterest"
    r = requests.get(url, params={"symbol": symbol})
    r.raise_for_status()
    data = r.json()
    return float(data.get("openInterest", 0.0))

def get_global_long_short_ratio_series(symbol: str = SYMBOL, period: str = "5m", limit: int = 4) -> List[Dict[str, Any]]:
    url = f"{BASE_FAPI}/futures/data/globalLongShortAccountRatio"
    r = requests.get(url, params={"symbol": symbol, "period": period, "limit": limit})
    r.raise_for_status()
    return r.json()

def get_taker_long_short_volume_series(symbol: str = SYMBOL, period: str = "5m", limit: int = 4) -> List[Dict[str, Any]]:
    url = f"{BASE_FAPI}/futures/data/takerlongshortRatio"
    r = requests.get(url, params={"symbol": symbol, "period": period, "limit": limit})
    r.raise_for_status()
    return r.json()

def get_klines_15m(symbol: str = SYMBOL, limit: int = 4) -> List[List[Any]]:
    url = f"{BASE_FAPI}/fapi/v1/klines"
    params = {
        "symbol": symbol, 
        "interval": "5m", 
        "limit": limit,
        "time": int(time.time() * 1000)
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

def get_open_interest_hist(symbol: str = SYMBOL, period: str = "5m", limit: int = 4) -> List[Dict[str, Any]]:
    url = f"{BASE_FAPI}/futures/data/openInterestHist"
    r = requests.get(url, params={"symbol": symbol, "period": period, "limit": limit})
    r.raise_for_status()
    return r.json()

def get_order_book_depth(symbol: str = SYMBOL, limit: int = 5) -> Dict[str, Any]:
    url = f"{BASE_FAPI}/fapi/v1/depth"
    r = requests.get(url, params={"symbol": symbol, "limit": limit})
    r.raise_for_status()
    return r.json()

def get_current_price(symbol: str = SYMBOL) -> float:
    url = f"{BASE_FAPI}/fapi/v1/ticker/price"
    r = requests.get(url, params={"symbol": symbol})
    r.raise_for_status()
    data = r.json()
    return float(data.get("price", 0.0))

def get_price_at_timestamp(symbol: str = SYMBOL, timestamp: int = None) -> float:
    if timestamp is None:
        return 0.0
    url = f"{BASE_FAPI}/fapi/v1/klines"
    r = requests.get(url, params={"symbol": symbol, "interval": "1m", "startTime": timestamp - 60000, "endTime": timestamp, "limit": 1})
    r.raise_for_status()
    klines = r.json()
    if klines:
        return float(klines[0][4])
    return 0.0

def get_recent_trades(symbol: str = SYMBOL, limit: int = 500) -> List[Dict[str, Any]]:
    url = f"{BASE_FAPI}/fapi/v1/trades"
    r = requests.get(url, params={"symbol": symbol, "limit": limit})
    r.raise_for_status()
    return r.json()

def get_aggregate_trades(symbol: str = SYMBOL, limit: int = 500, start_time: int = None, end_time: int = None) -> List[Dict[str, Any]]:
    url = f"{BASE_FAPI}/fapi/v1/aggTrades"
    params = {
        "symbol": symbol,
        "limit": limit
    }
    if start_time and end_time:
        params["startTime"] = start_time
        params["endTime"] = end_time
    else:
        end_time = int(time.time() * 1000)
        start_time = end_time - (5 * 60 * 1000)
        params["startTime"] = start_time
        params["endTime"] = end_time

    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

def get_liquidation_orders(symbol: str = SYMBOL, limit: int = 100) -> List[Dict[str, Any]]:
    from pathlib import Path
    try:
        if symbol == "ADAUSDT":
            data_file = Path("liquidation_data_ada.json")
        else:
            data_file = Path("liquidation_data.json")
        
        if not data_file.exists():
            return []
        
        with open(data_file, 'r', encoding='utf-8') as f:
            all_liquidations = json.load(f)
        
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(minutes=5)
        cutoff_timestamp = int(cutoff_time.timestamp() * 1000)
        
        recent_liquidations = [
            record for record in all_liquidations
            if (record.get('symbol') == symbol and 
                record.get('timestamp', 0) > cutoff_timestamp)
        ]
        
        recent_liquidations.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        recent_liquidations = recent_liquidations[:limit]
        
        formatted_liquidations = []
        for record in recent_liquidations:
            formatted_record = {
                'symbol': record.get('symbol'),
                'side': record.get('side'),
                'orderType': record.get('order_type'),
                'origQty': str(record.get('quantity', 0)),
                'price': str(record.get('price', 0)),
                'avgPrice': str(record.get('average_price', 0)),
                'status': record.get('status'),
                'timeInForce': 'IOC',
                'time': record.get('timestamp'),
                'executedQty': str(record.get('filled_quantity', 0))
            }
            formatted_liquidations.append(formatted_record)
        
        return formatted_liquidations
    except Exception as e:
        print(f"Error reading liquidation data: {e}")
        return []

def collect_snapshot(symbol: str = SYMBOL) -> Dict[str, Any]:
    ls_series = get_global_long_short_ratio_series(symbol, period="5m", limit=4)
    tk_series = get_taker_long_short_volume_series(symbol, period="5m", limit=4)
    oi_series = get_open_interest_hist(symbol, period="5m", limit=4)
    oi_now = get_open_interest(symbol)
    
    kl = get_klines_15m(symbol, limit=4)
    order_book = get_order_book_depth(symbol, limit=100)
    
    try:
        aggregate_trades_now = get_aggregate_trades(symbol, limit=500)
        end_time_before = int(time.time() * 1000) - (5 * 60 * 1000)
        start_time_before = end_time_before - (5 * 60 * 1000)
        aggregate_trades_before_5m = get_aggregate_trades(symbol, limit=500, start_time=start_time_before, end_time=end_time_before)
        liquidation_orders = get_liquidation_orders(symbol, limit=100)
        
        order_book_imbalance_data = calculate_order_book_imbalance(order_book)
        order_book_historical = get_order_book_historical_snapshots(symbol)
        order_book_pressure = analyze_order_book_pressure(order_book, order_book_historical)
        
        spot_price = get_spot_price(symbol)
        spot_trades_now = get_spot_aggregate_trades(symbol, limit=500)
        spot_cvd_now = calculate_cvd(spot_trades_now)
        premium_info = get_premium_index_info(symbol)
        options_intel = get_options_intel(symbol)
        funding_intel = get_funding_rate_trend(symbol)
    except Exception as e:
        aggregate_trades_now = []
        aggregate_trades_before_5m = []
        liquidation_orders = []
        order_book_imbalance_data = {"imbalance": 0.0, "bid_volume": 0.0, "ask_volume": 0.0, "depth_ratio": 0.0}
        order_book_historical = {}
        order_book_pressure = {"pressure_trend": "neutral", "imbalance_change": 0.0, "depth_change": 0.0}
        spot_price = 0.0
        spot_cvd_now = 0.0
        premium_info = {}
        options_intel = {"available": False}
        funding_intel = {}
        print(f"تحذير: فشل في جلب البيانات الجديدة: {e}")

    order_book_imbalance = order_book_imbalance_data.get("imbalance", 0.0)
    
    large_block_analysis = analyze_large_block_trades(aggregate_trades_now)
    liquidation_analysis = analyze_liquidation_data(liquidation_orders)
    current_price_val = get_current_price(symbol)
    ls_last_val = ls_series[-1].get("longShortRatio", 1.0) if ls_series else 1.0
    liquidation_clusters = get_liquidation_clusters(current_price_val, kl, oi_now, float(ls_last_val))
    cvd_now = calculate_cvd(aggregate_trades_now)
    cvd_before_5m = calculate_cvd(aggregate_trades_before_5m)
    cvd_analysis = {
        "cvd_now": cvd_now,
        "cvd_before_5m": cvd_before_5m
    }
    
    def calculate_trend_strength(klines):
        if len(klines) < 3:
            return "ضعيف"
        closes = [float(k[4]) for k in klines]
        trend_up = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        trend_down = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])
        if trend_up >= len(closes) * 0.7:
            return "قوي صعود"
        elif trend_down >= len(closes) * 0.7:
            return "قوي هبوط"
        elif trend_up > trend_down:
            return "متوسط صعود"
        elif trend_down > trend_up:
            return "متوسط هبوط"
        else:
            return "ضعيف/عابر"
    
    def calculate_volume_analysis(taker_data):
        if not taker_data:
            return {"buy_pressure": 0, "sell_pressure": 0, "net_pressure": "محايد"}
        total_buy = sum(float(x.get("buyVol", 0)) for x in taker_data[-4:])
        total_sell = sum(float(x.get("sellVol", 0)) for x in taker_data[-4:])
        buy_pressure = (total_buy / (total_buy + total_sell)) * 100 if (total_buy + total_sell) > 0 else 50
        sell_pressure = (total_sell / (total_buy + total_sell)) * 100 if (total_buy + total_sell) > 0 else 50
        if buy_pressure > sell_pressure + 15:
            net_pressure = "شراء قوي"
        elif sell_pressure > buy_pressure + 15:
            net_pressure = "بيع قوي"
        elif buy_pressure > sell_pressure + 5:
            net_pressure = "شراء خفيف"
        elif sell_pressure > buy_pressure + 5:
            net_pressure = "بيع خفيف"
        else:
            net_pressure = "محايد"
        return {"buy_pressure": round(buy_pressure, 1), "sell_pressure": round(sell_pressure, 1), "net_pressure": net_pressure}
    
    def calculate_oi_trend(oi_data):
        if len(oi_data) < 3:
            return "ثابت"
        recent_oi = [float(x.get("sumOpenInterest", 0)) for x in oi_data[-4:]]
        if len(recent_oi) < 2:
            return "ثابت"
        avg_increase = sum(1 for i in range(1, len(recent_oi)) if recent_oi[i] > recent_oi[i-1])
        avg_decrease = sum(1 for i in range(1, len(recent_oi)) if recent_oi[i] < recent_oi[i-1])
        if avg_increase >= len(recent_oi) * 0.7:
            return "متزايد قوي"
        elif avg_decrease >= len(recent_oi) * 0.7:
            return "متناقص قوي"
        elif avg_increase > avg_decrease:
            return "متزايد خفيف"
        elif avg_decrease > avg_increase:
            return "متناقص خفيف"
        else:
            return "ثابت"
    
    trend_strength = calculate_trend_strength(kl)
    volume_analysis = calculate_volume_analysis(tk_series)
    oi_trend = calculate_oi_trend(oi_series)

    ls_values = [float(x.get("longShortRatio", 0.0)) for x in ls_series]
    oi_values = [float(x.get("sumOpenInterest", 0.0)) for x in oi_series]

    def calculate_oi_velocity(oi_vals):
        if len(oi_vals) < 2:
            return 0.0
        first_oi = oi_vals[0]
        last_oi = oi_vals[-1]
        if first_oi == 0:
            return 0.0
        return round(((last_oi - first_oi) / first_oi) * 100.0, 4)
    
    oi_velocity = calculate_oi_velocity(oi_values)

    def _split_long_short_from_ratio(ratio: float) -> Tuple[float, float]:
        if ratio is None or ratio <= 0:
            return 0.0, 0.0
        long_pct = (ratio / (1.0 + ratio)) * 100.0
        short_pct = 100.0 - long_pct
        return round(long_pct, 2), round(short_pct, 2)

    def _estimate_long_short_oi(oi: float, ratio: float) -> Tuple[float, float]:
        if oi is None or oi <= 0 or ratio is None or ratio <= 0:
            return 0.0, 0.0
        long_oi = oi * (ratio / (1.0 + ratio))
        short_oi = oi - long_oi
        return round(long_oi, 2), round(short_oi, 2)

    long_ratio_percent_series: List[float] = []
    short_ratio_percent_series: List[float] = []
    estimated_long_oi_series: List[float] = []
    estimated_short_oi_series: List[float] = []

    max_len = min(len(ls_values), len(oi_values)) if oi_values else len(ls_values)
    for i in range(max_len):
        r = ls_values[i]
        oi_val = oi_values[i] if i < len(oi_values) else 0.0
        long_pct, short_pct = _split_long_short_from_ratio(r)
        long_oi, short_oi = _estimate_long_short_oi(oi_val, r)
        long_ratio_percent_series.append(long_pct)
        short_ratio_percent_series.append(short_pct)
        estimated_long_oi_series.append(long_oi)
        estimated_short_oi_series.append(short_oi)

    current_long_pct, current_short_pct = _split_long_short_from_ratio(ls_values[-1] if ls_values else 0.0)
    current_long_oi, current_short_oi = _estimate_long_short_oi(oi_now, ls_values[-1] if ls_values else 0.0)

    current_price = get_current_price(symbol)
    timestamp_15_min_ago = int(time.time() * 1000) - (15 * 60 * 1000)
    price_15_min_ago = get_price_at_timestamp(symbol, timestamp_15_min_ago)
    
    import statistics
    if len(oi_values) >= 2:
        oi_mean = statistics.mean(oi_values)
        oi_stdev = statistics.stdev(oi_values) if len(oi_values) > 1 else 0.0
        oi_z_score = (oi_now - oi_mean) / oi_stdev if oi_stdev > 0.0 else 0.0
    else:
        oi_z_score = 0.0
        
    fut_cvd_delta = cvd_now - cvd_before_5m
    imb_trend_vals = [float(x.get("imbalance", 0.0)) for x in order_book_pressure.get("imbalance_trend", [])]
    if imb_trend_vals:
        imb_velocity = order_book_imbalance - statistics.mean(imb_trend_vals)
    else:
        imb_velocity = 0.0
        
    bids = order_book.get("bids", [])
    asks = order_book.get("asks", [])
    if bids and asks:
        best_bid_p, best_bid_q = float(bids[0][0]), float(bids[0][1])
        best_ask_p, best_ask_q = float(asks[0][0]), float(asks[0][1])
        tot_q = best_bid_q + best_ask_q
        if tot_q > 0:
            micro_price = round((best_bid_p * best_ask_q + best_ask_p * best_bid_q) / tot_q, 2)
            mid_p = (best_bid_p + best_ask_p) / 2.0
            micro_price_bps = round(((micro_price - mid_p) / mid_p) * 10000.0, 4)
        else:
            micro_price = current_price
            micro_price_bps = 0.0
    else:
        micro_price = current_price
        micro_price_bps = 0.0
        
    spot_cvd_delta = spot_cvd_now
    institutional_net_flow = round((spot_cvd_delta * 1.5) + fut_cvd_delta, 4)
    price_delta_15m = round(current_price - price_15_min_ago, 2) if price_15_min_ago > 0 else 0.0
    effort_vs_result_ratio = round(fut_cvd_delta / (price_delta_15m + 1e-4), 4)
    
    coin_clean = symbol.replace("USDT", "")

    return {
        "symbol": symbol,
        "timestamp": int(time.time()*1000),
        "series": {
            "open_interest": [float(x.get("sumOpenInterest", 0.0)) for x in oi_series],
            "long_short_ratio": [float(x.get("longShortRatio", 0.0)) for x in ls_series],
            "long_ratio_percent": long_ratio_percent_series,
            "short_ratio_percent": short_ratio_percent_series,
            "estimated_long_open_interest": estimated_long_oi_series,
            "estimated_short_open_interest": estimated_short_oi_series,
            "taker_buy_volume": [float(x.get("buyVol", 0.0)) for x in tk_series],
            "taker_sell_volume": [float(x.get("sellVol", 0.0)) for x in tk_series],
            "klines_15m": kl,
        },
        "analysis": {
            "trend_strength": trend_strength,
            "volume_pressure": volume_analysis,
            "oi_trend": oi_trend,
            "oi_velocity_15m": oi_velocity,
            "ls_ratio_avg": round(sum(float(x.get("longShortRatio", 0.0)) for x in ls_series[-4:]) / min(4, len(ls_series)), 2) if ls_series else 0,
            "order_book_imbalance": order_book_imbalance,
            "large_block_trades": large_block_analysis,
            "liquidation_data": liquidation_analysis,
            "cvd": cvd_analysis,
            "order_book_detailed": order_book_imbalance_data,
            "order_book_pressure": order_book_pressure,
            "order_book_historical": order_book_historical,
            "spot_market": {
                "spot_price": spot_price,
                "spot_cvd_now": spot_cvd_now,
                "spot_vs_futures_spread": round(spot_price - current_price, 4) if spot_price > 0 and current_price > 0 else 0.0,
                "spot_cvd_vs_futures_cvd_ratio": round(spot_cvd_now / cvd_now, 4) if cvd_now != 0 else 0.0
            },
            "premium_index_info": premium_info,
            "options_intel": options_intel,
            "funding_intel": funding_intel,
            "liquidation_clusters": liquidation_clusters,
            "ls_breakdown_current": {
                "long_percent": current_long_pct,
                "short_percent": current_short_pct,
                "estimated_long_oi": current_long_oi,
                "estimated_short_oi": current_short_oi
            },
            "institutional_microstructure_v10": {
                "stoikov_micro_price": micro_price,
                "micro_price_bps": micro_price_bps,
                "institutional_net_flow": institutional_net_flow,
                "wyckoff_effort_vs_result_ratio": effort_vs_result_ratio,
                "price_delta_15m": price_delta_15m
            },
            "derivatives_intel": get_derivatives_intel(coin_clean) if get_derivatives_intel else {"available": False},
            "smc_structures": analyze_smc(coin_clean) if analyze_smc else {"available": False}
        },
        "order_book": order_book,
        "current": {
            "open_interest": oi_now,
            "oi_z_score": oi_z_score,
            "futures_cvd_velocity": fut_cvd_delta,
            "lob_imbalance_velocity": imb_velocity,
            "long_percent": current_long_pct,
            "short_percent": current_short_pct,
            "estimated_long_oi": current_long_oi,
            "estimated_short_oi": current_short_oi,
            "current_price": current_price,
            "price_15_min_ago": price_15_min_ago,
            "spot_price": spot_price,
            "spot_cvd_now": spot_cvd_now,
            "funding_rate": float(premium_info.get("lastFundingRate", 0.0)) if premium_info else 0.0,
            "mark_price": float(premium_info.get("markPrice", 0.0)) if premium_info else 0.0,
            "index_price": float(premium_info.get("indexPrice", 0.0)) if premium_info else 0.0,
            "premium_index": float(premium_info.get("interestRate", 0.0)) if premium_info else 0.0,
            "stoikov_micro_price": micro_price,
            "micro_price_bps": micro_price_bps,
            "institutional_net_flow": institutional_net_flow,
            "wyckoff_effort_vs_result_ratio": effort_vs_result_ratio
        }
    }

def analyze_large_block_trades(trades_data: List[Dict[str, Any]], threshold_multiplier: float = 2.0) -> Dict[str, Any]:
    if not trades_data:
        return {"large_trades_count": 0, "total_large_volume": 0.0, "avg_large_trade_size": 0.0, "whale_pressure": "محايد"}
    volumes = [float(trade.get("q", 0)) for trade in trades_data]
    if not volumes:
        return {"large_trades_count": 0, "total_large_volume": 0.0, "avg_large_trade_size": 0.0, "whale_pressure": "محايد"}
    avg_volume = sum(volumes) / len(volumes)
    threshold = avg_volume * threshold_multiplier
    large_trades = [trade for trade in trades_data if float(trade.get("q", 0)) >= threshold]
    if not large_trades:
        return {"large_trades_count": 0, "total_large_volume": 0.0, "avg_large_trade_size": 0.0, "whale_pressure": "محايد"}
    buy_volume = sum(float(trade.get("q", 0)) for trade in large_trades if not trade.get("m", True))
    sell_volume = sum(float(trade.get("q", 0)) for trade in large_trades if trade.get("m", True))
    total_large_volume = buy_volume + sell_volume
    if buy_volume > sell_volume * 1.5:
        whale_pressure = "شراء قوي"
    elif sell_volume > buy_volume * 1.5:
        whale_pressure = "بيع قوي"
    elif buy_volume > sell_volume:
        whale_pressure = "شراء خفيف"
    elif sell_volume > buy_volume:
        whale_pressure = "بيع خفيف"
    else:
        whale_pressure = "محايد"
    return {
        "large_trades_count": len(large_trades),
        "total_large_volume": round(total_large_volume, 4),
        "avg_large_trade_size": round(total_large_volume / len(large_trades), 4) if large_trades else 0.0,
        "whale_pressure": whale_pressure,
        "buy_volume": round(buy_volume, 4),
        "sell_volume": round(sell_volume, 4)
    }

def analyze_liquidation_data(liquidation_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not liquidation_data:
        return {"liquidation_count": 0, "total_liquidated_volume": 0.0, "liquidation_pressure": "محايد", "long_liquidations": 0.0, "short_liquidations": 0.0}
    long_liquidations = sum(float(liq.get("executedQty", 0)) for liq in liquidation_data if liq.get("side") == "SELL")
    short_liquidations = sum(float(liq.get("executedQty", 0)) for liq in liquidation_data if liq.get("side") == "BUY")
    total_liquidated = long_liquidations + short_liquidations
    if long_liquidations > short_liquidations * 2:
        liquidation_pressure = "تصفية طويلة قوية"
    elif short_liquidations > long_liquidations * 2:
        liquidation_pressure = "تصفية قصيرة قوية"
    elif long_liquidations > short_liquidations:
        liquidation_pressure = "تصفية طويلة خفيفة"
    elif short_liquidations > long_liquidations:
        liquidation_pressure = "تصفية قصيرة خفيفة"
    else:
        liquidation_pressure = "محايد"
    return {
        "liquidation_count": len(liquidation_data),
        "total_liquidated_volume": round(total_liquidated, 4),
        "liquidation_pressure": liquidation_pressure,
        "long_liquidations": round(long_liquidations, 4),
        "short_liquidations": round(short_liquidations, 4)
    }

def calculate_cvd(trades_data: List[Dict[str, Any]]) -> float:
    if not trades_data:
        return 0.0
    cvd = 0.0
    for trade in trades_data:
        volume = float(trade.get("q", 0))
        if not trade.get("m", True):
            cvd += volume
        else:
            cvd -= volume
    return round(cvd, 4)

def calculate_order_book_imbalance(order_book: Dict[str, Any]) -> Dict[str, Any]:
    try:
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        if not bids or not asks:
            return {"imbalance": 0.0, "bid_volume": 0.0, "ask_volume": 0.0}
        top_levels = min(10, len(bids), len(asks))
        bid_volume = sum(float(bid[1]) for bid in bids[:top_levels])
        ask_volume = sum(float(ask[1]) for ask in asks[:top_levels])
        total_volume = bid_volume + ask_volume
        imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0.0
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid_price = (best_bid + best_ask) / 2.0
        def get_volume_within_pct(orders, mid, pct):
            limit_val = mid * (pct / 100.0)
            vol = 0.0
            for price_str, qty_str in orders:
                price = float(price_str)
                if abs(price - mid) <= limit_val:
                    vol += float(qty_str)
            return vol
        bid_vol_0_5 = get_volume_within_pct(bids, mid_price, 0.5)
        ask_vol_0_5 = get_volume_within_pct(asks, mid_price, 0.5)
        total_0_5 = bid_vol_0_5 + ask_vol_0_5
        imbalance_0_5 = (bid_vol_0_5 - ask_vol_0_5) / total_0_5 if total_0_5 > 0 else 0.0
        bid_vol_1 = get_volume_within_pct(bids, mid_price, 1.0)
        ask_vol_1 = get_volume_within_pct(asks, mid_price, 1.0)
        total_1 = bid_vol_1 + ask_vol_1
        imbalance_1 = (bid_vol_1 - ask_vol_1) / total_1 if total_1 > 0 else 0.0
        bid_vol_2 = get_volume_within_pct(bids, mid_price, 2.0)
        ask_vol_2 = get_volume_within_pct(asks, mid_price, 2.0)
        total_2 = bid_vol_2 + ask_vol_2
        imbalance_2 = (bid_vol_2 - ask_vol_2) / total_2 if total_2 > 0 else 0.0
        return {
            "imbalance": round(imbalance, 4),
            "bid_volume": round(bid_volume, 2),
            "ask_volume": round(ask_volume, 2),
            "total_volume": round(total_volume, 2),
            "mid_price": round(mid_price, 2),
            "depth_0_5": {
                "bid_volume": round(bid_vol_0_5, 2),
                "ask_volume": round(ask_vol_0_5, 2),
                "imbalance": round(imbalance_0_5, 4)
            },
            "depth_1_0": {
                "bid_volume": round(bid_vol_1, 2),
                "ask_volume": round(ask_vol_1, 2),
                "imbalance": round(imbalance_1, 4)
            },
            "depth_2_0": {
                "bid_volume": round(bid_vol_2, 2),
                "ask_volume": round(ask_vol_2, 2),
                "imbalance": round(imbalance_2, 4)
            }
        }
    except Exception as e:
        return {"imbalance": 0.0, "bid_volume": 0.0, "ask_volume": 0.0, "error": str(e)}

OB_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ob_history_cache.json")

def get_order_book_historical_snapshots(symbol: str = SYMBOL, intervals: List[int] = [300, 600, 900, 1800, 3600, 7200]) -> Dict[str, Any]:
    now = int(time.time() * 1000)
    try:
        current_book = get_order_book_depth(symbol, 50)
        current_imbalance = calculate_order_book_imbalance(current_book)
    except Exception:
        current_book = {}
        current_imbalance = {"imbalance": 0.0, "bid_volume": 0.0, "ask_volume": 0.0}
        
    records = []
    if os.path.exists(OB_CACHE_FILE):
        try:
            with open(OB_CACHE_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []
            
    records.append({
        "timestamp": now,
        "symbol": symbol,
        "order_book": current_book,
        "imbalance": current_imbalance
    })
    
    cutoff = now - (7500 * 1000)
    records = [r for r in records if r.get("timestamp", 0) >= cutoff]
    
    try:
        temp_file = OB_CACHE_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, OB_CACHE_FILE)
    except Exception:
        pass

    snapshots = {}
    for sec in intervals:
        target_ts = now - (sec * 1000)
        best_rec = None
        min_diff = float("inf")
        for r in records:
            if r.get("symbol") == symbol:
                diff = abs(r.get("timestamp", 0) - target_ts)
                if diff < min_diff:
                    min_diff = diff
                    best_rec = r
        if best_rec:
            snapshots[f"before_{sec}s"] = {
                "timestamp": best_rec["timestamp"],
                "order_book": best_rec.get("order_book", {}),
                "imbalance": best_rec.get("imbalance", {}),
                "interval_seconds": sec
            }
        else:
            snapshots[f"before_{sec}s"] = {
                "timestamp": target_ts,
                "order_book": current_book,
                "imbalance": current_imbalance,
                "interval_seconds": sec
            }
    return snapshots

def analyze_order_book_pressure(current_book: Dict[str, Any], historical_snapshots: Dict[str, Any]) -> Dict[str, Any]:
    try:
        current_imbalance = calculate_order_book_imbalance(current_book)
        analysis = {
            "current_imbalance": current_imbalance,
            "imbalance_trend": [],
            "pressure_direction": "neutral",
            "pressure_strength": 0.0,
            "rapid_changes": False
        }
        imbalance_values = [current_imbalance["imbalance"]]
        for period in ["before_300s", "before_600s", "before_900s"]:
            if period in historical_snapshots and "imbalance" in historical_snapshots[period]:
                hist_imbalance = historical_snapshots[period]["imbalance"]["imbalance"]
                imbalance_values.append(hist_imbalance)
                analysis["imbalance_trend"].append({
                    "period": period,
                    "imbalance": hist_imbalance
                })
        if len(imbalance_values) >= 2:
            recent_change = imbalance_values[0] - imbalance_values[1]
            if abs(recent_change) >= 0.1:
                analysis["rapid_changes"] = True
            if current_imbalance["imbalance"] > 0.15:
                analysis["pressure_direction"] = "bullish"
                analysis["pressure_strength"] = min(abs(current_imbalance["imbalance"]) * 100, 100)
            elif current_imbalance["imbalance"] < -0.15:
                analysis["pressure_direction"] = "bearish"
                analysis["pressure_strength"] = min(abs(current_imbalance["imbalance"]) * 100, 100)
            else:
                analysis["pressure_direction"] = "neutral"
                analysis["pressure_strength"] = abs(current_imbalance["imbalance"]) * 100
        return analysis
    except Exception as e:
        return {
            "error": str(e),
            "current_imbalance": {"imbalance": 0.0, "bid_volume": 0.0, "ask_volume": 0.0},
            "pressure_direction": "neutral",
            "pressure_strength": 0.0
        }

def get_options_intel(symbol: str = "BTCUSDT") -> Dict[str, Any]:
    """جلب وتحليل حقيقي لخيارات BTC من Binance Options EAPI"""
    try:
        url = "https://eapi.binance.com/eapi/v1/ticker"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            res = json.loads(r.read().decode('utf-8'))
        coin = symbol.replace("USDT", "")
        btc_opts = [t for t in res if t.get('symbol', '').startswith(coin)]
        if not btc_opts:
            return {"available": False, "reason": "No options found"}
        call_vol = sum(float(t.get('volume', 0)) for t in btc_opts if t.get('symbol', '').endswith('-C'))
        put_vol = sum(float(t.get('volume', 0)) for t in btc_opts if t.get('symbol', '').endswith('-P'))
        pc_ratio = round(put_vol / call_vol, 4) if call_vol > 0 else 1.0
        spot_price = float(btc_opts[0].get('exercisePrice', 64800))
        if pc_ratio > 1.25:
            gamma_regime = "Short Gamma (High Volatility / Bearish Put Skew)"
        elif pc_ratio < 0.75:
            gamma_regime = "Long Gamma (Price Pinning / Bullish Call Skew)"
        else:
            gamma_regime = "Neutral Gamma (Balanced Volatility)"
        return {
            "available": True,
            "call_volume_btc": round(call_vol, 2),
            "put_volume_btc": round(put_vol, 2),
            "put_call_ratio": pc_ratio,
            "exercise_mark_price": spot_price,
            "gamma_regime": gamma_regime,
            "options_count": len(btc_opts)
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

def get_funding_rate_trend(symbol: str = "BTCUSDT") -> Dict[str, Any]:
    """جلب سعة واتجاه معدل التمويل اللحظي والتاريخي"""
    try:
        url_prem = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
        req_prem = urllib.request.Request(url_prem, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_prem, timeout=5) as r:
            prem_data = json.loads(r.read().decode('utf-8'))
        url_hist = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=5"
        req_hist = urllib.request.Request(url_hist, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_hist, timeout=5) as r:
            hist_data = json.loads(r.read().decode('utf-8'))
        current_rate = float(prem_data.get("lastFundingRate", 0.0)) * 100.0
        mark_price = float(prem_data.get("markPrice", 0.0))
        index_price = float(prem_data.get("indexPrice", 0.0))
        next_funding_time = prem_data.get("nextFundingTime", 0)
        hist_rates = [float(x.get("fundingRate", 0.0)) * 100.0 for x in hist_data]
        if len(hist_rates) >= 2:
            trend_val = hist_rates[-1] - hist_rates[0]
            rate_trend = "متزايد" if trend_val > 0.001 else "متناقص" if trend_val < -0.001 else "مستقر"
        else:
            rate_trend = "مستقر"
        if current_rate > 0.03:
            regime = "⚠️ Tilted Extremely Bullish (Long Flush Risk)"
        elif current_rate < -0.015:
            regime = "⚡ Tilted Extremely Bearish (Short Squeeze Risk)"
        else:
            regime = "Normal Balanced Funding"
        return {
            "current_funding_rate_pct": round(current_rate, 4),
            "historical_rates_5p": [round(x, 4) for x in hist_rates],
            "funding_rate_trend": rate_trend,
            "funding_regime": regime,
            "mark_price": mark_price,
            "index_price": index_price,
            "next_funding_time": next_funding_time
        }
    except Exception as e:
        return {"error": str(e)}

def get_liquidation_clusters(current_price: float, klines: list, oi_now: float, ls_ratio: float) -> Dict[str, Any]:
    """حساب تجمعات التصفيات المتوقعة للونج والشورت للرافعات 25x, 50x, 100x"""
    try:
        if not current_price or current_price <= 0:
            return {}
        highs = [float(k[2]) for k in klines] if klines else [current_price]
        lows = [float(k[3]) for k in klines] if klines else [current_price]
        recent_high = max(highs)
        recent_low = min(lows)
        long_100x = round(recent_low * 0.99, 2)
        long_50x  = round(recent_low * 0.98, 2)
        long_25x  = round(recent_low * 0.96, 2)
        short_100x = round(recent_high * 1.01, 2)
        short_50x  = round(recent_high * 1.02, 2)
        short_25x  = round(recent_high * 1.04, 2)
        estimated_long_oi = oi_now * (ls_ratio / (1.0 + ls_ratio)) if ls_ratio > 0 else oi_now * 0.5
        estimated_short_oi = oi_now - estimated_long_oi
        primary_target = "LONG_LIQUIDATION_SWEEP" if estimated_long_oi > estimated_short_oi * 1.2 else "SHORT_LIQUIDATION_SWEEP" if estimated_short_oi > estimated_long_oi * 1.2 else "BALANCED_SWEEP"
        return {
            "long_liquidation_clusters": {
                "level_100x": long_100x,
                "level_50x": long_50x,
                "level_25x": long_25x,
                "estimated_long_oi_btc": round(estimated_long_oi, 2)
            },
            "short_liquidation_clusters": {
                "level_100x": short_100x,
                "level_50x": short_50x,
                "level_25x": short_25x,
                "estimated_short_oi_btc": round(estimated_short_oi, 2)
            },
            "primary_liquidity_magnet": primary_target,
            "recent_range_high": recent_high,
            "recent_range_low": recent_low
        }
    except Exception as e:
        return {"error": str(e)}
