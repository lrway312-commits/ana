from typing import Dict, Any, List

def segment_last_hour(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    تقسيم البيانات إلى فترات زمنية مختلفة مع التركيز على آخر 5 دقائق
    """
    series = snapshot.get("series", {})
    kl: List = series.get("klines_15m", [])
    def pick(arr: List, idx: int):
        return arr[idx] if len(arr) > idx else None
    # باستخدام فترات 5 دقائق: المؤشر 3 = قبل 15 دقيقة، 2 = قبل 10 دقائق، 1 = قبل 5 دقائق، 0 = الأحدث ضمن السلسلة
    return {
        "before_15m": {
            "open_interest": pick(series.get("open_interest", []), 3),
            "long_short_ratio": pick(series.get("long_short_ratio", []), 3),
            "taker_buy_volume": pick(series.get("taker_buy_volume", []), 3),
            "taker_sell_volume": pick(series.get("taker_sell_volume", []), 3),
            "kline": pick(kl, 3),
        },
        "before_10m": {
            "open_interest": pick(series.get("open_interest", []), 2),
            "long_short_ratio": pick(series.get("long_short_ratio", []), 2),
            "taker_buy_volume": pick(series.get("taker_buy_volume", []), 2),
            "taker_sell_volume": pick(series.get("taker_sell_volume", []), 2),
            "kline": pick(kl, 2),
        },
        "before_5m": {
            "open_interest": pick(series.get("open_interest", []), 1),
            "long_short_ratio": pick(series.get("long_short_ratio", []), 1),
            "taker_buy_volume": pick(series.get("taker_buy_volume", []), 1),
            "taker_sell_volume": pick(series.get("taker_sell_volume", []), 1),
            "kline": pick(kl, 1),
        },
        "now": {
            "open_interest": pick(series.get("open_interest", []), 0),
            "long_short_ratio": pick(series.get("long_short_ratio", []), 0),
            "taker_buy_volume": pick(series.get("taker_buy_volume", []), 0),
            "taker_sell_volume": pick(series.get("taker_sell_volume", []), 0),
            "kline": pick(kl, 0),
            **snapshot.get("current", {}),
            "order_book_imbalance": snapshot.get("analysis", {}).get("order_book_imbalance"),
            "order_book": snapshot.get("order_book"),
            # البيانات الجديدة للسكالبنج السريع (آخر 5 دقائق فقط)
            "large_block_trades": snapshot.get("analysis", {}).get("large_block_trades"),
            "liquidation_data": snapshot.get("analysis", {}).get("liquidation_data"),
            "cvd": snapshot.get("analysis", {}).get("cvd")
        },
    }