# -*- coding: utf-8 -*-
"""
DerivativesIntel — محرك استخبارات المشتقات العالمية
1. Top Trader Position Divergence (تباين صفقات الحيتان مقابل الأفراد)
2. Predicted Funding Rate & Squeeze Alerts (تنبيهات احتراق التمويل)
3. Futures vs Spot Basis Premium (معامل علاوة العقود الآجلة)
4. Market Breadth Index (مؤشر اتساق السوق والعملات البديلة)
"""

import urllib.request
import json
import time
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

_SYMBOL_MAP = {
    "BTC": "BTCUSDT",
    "ADA": "ADAUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
}

def _http_get_json(url: str, timeout: int = 5):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None

def get_top_trader_divergence(coin: str = "BTC") -> dict:
    """جلب تباين صفقات الحيتان (Top Trader Positions) مقابل الأفراد (Global Accounts)"""
    symbol = _SYMBOL_MAP.get(coin.upper(), f"{coin.upper()}USDT")
    base_fapi = "https://fapi.binance.com"

    # Top trader position ratio
    pos_data = _http_get_json(f"{base_fapi}/futures/data/topLongShortPositionRatio?symbol={symbol}&period=15m&limit=1")
    # Global account ratio
    acc_data = _http_get_json(f"{base_fapi}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=15m&limit=1")

    pos_ratio = 1.0
    pos_long_pct = 50.0
    if pos_data and isinstance(pos_data, list) and len(pos_data) > 0:
        pos_ratio = float(pos_data[0].get("longShortRatio", 1.0))
        pos_long_pct = float(pos_data[0].get("longAccount", 0.50)) * 100.0 if "longAccount" in pos_data[0] else (pos_ratio / (1.0 + pos_ratio)) * 100.0

    acc_ratio = 1.0
    acc_long_pct = 50.0
    if acc_data and isinstance(acc_data, list) and len(acc_data) > 0:
        acc_ratio = float(acc_data[0].get("longShortRatio", 1.0))
        acc_long_pct = float(acc_data[0].get("longAccount", 0.50)) * 100.0 if "longAccount" in acc_data[0] else (acc_ratio / (1.0 + acc_ratio)) * 100.0

    # Divergence calculation
    div_type = "متوافق ⚪"
    div_desc = "تطابق مراكز الحيتان مع تداولات الأفراد"
    div_score = 0.0

    # Retail Long Trap: Retail is heavily Long (>58%) while Whales Position is Short (<48%)
    if acc_long_pct > 58.0 and pos_long_pct < 48.0:
        div_type = "⚠️ فخ أفراد (Retail Long Trap)"
        div_desc = f"الأفراد يشترون بـ {acc_long_pct:.1f}% بينما الحيتان يبيعون بـ {100-pos_long_pct:.1f}%"
        div_score = -2.5
    # Whale Bullish Accumulation: Whales Position is heavily Long (>58%) while Retail is Short (<48%)
    elif pos_long_pct > 58.0 and acc_long_pct < 48.0:
        div_type = "🚀 تجميع حيتان (Whale Bullish Accumulation)"
        div_desc = f"الحيتان يشترون بـ {pos_long_pct:.1f}% بينما الأفراد يبيعون بـ {100-acc_long_pct:.1f}%"
        div_score = 2.5
    elif pos_long_pct > 55.0 and acc_long_pct > 55.0:
        div_type = "🟢 إجماع شرائي (Bullish Consensus)"
        div_desc = "الحيتان والأفراد في اتجاه صاعد مشترك"
        div_score = 1.5
    elif pos_long_pct < 45.0 and acc_long_pct < 45.0:
        div_type = "🔴 إجماع بيعي (Bearish Consensus)"
        div_desc = "الحيتان والأفراد في اتجاه هابط مشترك"
        div_score = -1.5

    return {
        "symbol": symbol,
        "pos_ratio": round(pos_ratio, 3),
        "pos_long_pct": round(pos_long_pct, 1),
        "pos_short_pct": round(100.0 - pos_long_pct, 1),
        "acc_ratio": round(acc_ratio, 3),
        "acc_long_pct": round(acc_long_pct, 1),
        "acc_short_pct": round(100.0 - acc_long_pct, 1),
        "divergence_type": div_type,
        "divergence_desc": div_desc,
        "divergence_score": div_score
    }

def get_funding_and_basis(coin: str = "BTC") -> dict:
    """جلب معدلات التمويل ومعامل علاوة العقود الآجلة مقابل السوق الفوري Spot"""
    symbol = _SYMBOL_MAP.get(coin.upper(), f"{coin.upper()}USDT")
    base_fapi = "https://fapi.binance.com"
    base_spot = "https://api.binance.com"

    prem_data = _http_get_json(f"{base_fapi}/fapi/v1/premiumIndex?symbol={symbol}")
    spot_data = _http_get_json(f"{base_spot}/api/v3/ticker/price?symbol={symbol}")

    funding_rate = 0.0
    mark_price = 0.0

    if prem_data and isinstance(prem_data, dict):
        funding_rate = float(prem_data.get("lastFundingRate", 0.0)) * 100.0
        mark_price = float(prem_data.get("markPrice", 0.0))

    spot_price = float(spot_data.get("price", 0.0)) if spot_data and isinstance(spot_data, dict) else mark_price

    # Basis calculation %
    basis_pct = 0.0
    if spot_price > 0:
        basis_pct = ((mark_price - spot_price) / spot_price) * 100.0

    # Basis Regime
    basis_regime = "محايد (Neutral Basis)"
    if basis_pct > 0.35:
        basis_regime = "Contango (مضاربة آجل مفرطة)"
    elif basis_pct < -0.15:
        basis_regime = "Spot Premium (تجميع فوري مستدام)"

    # Funding Squeeze Warning
    squeeze_alert = "طبيعي ✅"
    squeeze_desc = "معدلات تمويل متوازنة"
    if funding_rate < -0.02:
        squeeze_alert = "⚡ Short Squeeze Warning (احتراق شورت قادم)"
        squeeze_desc = "البائعون يدفعون رسوم تمويل عالية، يمهد لانفجار صاعد"
    elif funding_rate > +0.04:
        squeeze_alert = "⚠️ Long Flush Warning (تصفية لونج قادمة)"
        squeeze_desc = "المشترون يدفعون تمويلاً مرتفعاً، يمهد لكسر هابط"

    return {
        "funding_rate_pct": round(funding_rate, 4),
        "mark_price": round(mark_price, 4),
        "spot_price": round(spot_price, 4),
        "basis_pct": round(basis_pct, 4),
        "basis_regime": basis_regime,
        "squeeze_alert": squeeze_alert,
        "squeeze_desc": squeeze_desc
    }

def get_market_breadth() -> dict:
    """حساب مؤشر اتساع شهية السوق والعملات البديلة الصاعدة من Binance 24h Tickers"""
    url = "https://api.binance.com/api/v3/ticker/24hr"
    tickers = _http_get_json(url)

    if not tickers or not isinstance(tickers, list):
        return {
            "green_pct": 50.0,
            "regime": "متوازن ⚪",
            "advances": 0, "declines": 0, "total": 0
        }

    usdt_tickers = [t for t in tickers if t.get("symbol", "").endswith("USDT") and not any(x in t["symbol"] for x in ["UP", "DOWN", "BULL", "BEAR", "BUSD"])]
    if not usdt_tickers:
        return {"green_pct": 50.0, "regime": "متوازن ⚪", "advances": 0, "declines": 0, "total": 0}

    advances = sum(1 for t in usdt_tickers if float(t.get("priceChangePercent", 0)) > 0)
    declines = len(usdt_tickers) - advances
    green_pct = (advances / len(usdt_tickers)) * 100.0

    regime = "متوازن ⚪"
    if green_pct >= 70.0:
        regime = "Risk-on / Altseason 🚀"
    elif green_pct <= 30.0:
        regime = "BTC Dominant / Risk-off ⚠️"

    return {
        "green_pct": round(green_pct, 1),
        "regime": regime,
        "advances": advances,
        "declines": declines,
        "total": len(usdt_tickers)
    }

def get_derivatives_intel(coin: str = "BTC") -> dict:
    """جلب وتحليل حزمة الاستخبارات كاملة لعملة واحدة"""
    try:
        div = get_top_trader_divergence(coin)
        fb = get_funding_and_basis(coin)
        mb = get_market_breadth()
        return {
            "available": True,
            "divergence": div,
            "funding_basis": fb,
            "market_breadth": mb
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

if __name__ == "__main__":
    print("Testing DerivativesIntel Module...")
    print(get_derivatives_intel("BTC"))
