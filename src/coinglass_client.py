import requests
import logging
from typing import Dict, Any, List, Optional
from .config import COINGLASS_API_KEY

logger = logging.getLogger(__name__)

class CoinGlassClient:
    """
    Client for CoinGlass API (v2)
    """
    BASE_URL = "https://open-api.coinglass.com/public/v2"
    V1_BASE_URL = "https://open-api.coinglass.com/api/pro/v1"

    def __init__(self, api_key: str = COINGLASS_API_KEY):
        self.api_key = api_key
        self.headers = {
            "accept": "application/json",
            "coinglassToken": self.api_key
        }

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Try V2 first
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 500 or response.status_code == 401:
                # Try V1 as fallback
                logger.info(f"Retrying with V1 for {endpoint}...")
                v1_endpoint = endpoint.replace("/perpetual/", "/futures/") # Some differences in v1/v2
                url = f"{self.V1_BASE_URL}{v1_endpoint}"
                response = requests.get(url, headers=self.headers, params=params)
            
            response.raise_for_status()
            data = response.json()
            if data.get("success") or data.get("code") == "0":
                return data.get("data", {})
            else:
                logger.error(f"CoinGlass API error: {data.get('msg')} (Code: {data.get('code')})")
                return {}
        except Exception as e:
            logger.error(f"Error fetching from CoinGlass {endpoint}: {e}")
            return {}

    def get_options_open_interest(self, symbol: str = "BTC") -> Dict[str, Any]:
        """BTC Options Open Interest By Strike Price"""
        return self._get("/options/openInterest", {"symbol": symbol})

    def get_options_volume(self, symbol: str = "BTC") -> Dict[str, Any]:
        """Volume By Expiration (BTC/ETH)"""
        return self._get("/options/volume", {"symbol": symbol})

    def get_options_max_pain(self, symbol: str = "BTC") -> Dict[str, Any]:
        """BTC/ETH Max Pain Data"""
        return self._get("/options/maxPain", {"symbol": symbol})

    def get_liquidation_heatmap(self) -> Dict[str, Any]:
        """Liquidation Heatmap & Statistics"""
        return self._get("/liquidation/info")

    def get_liquidation_map(self, symbol: str = "BTC", interval: str = "24h") -> Dict[str, Any]:
        """Liquidation Maps (BTC/ETH)"""
        return self._get("/liquidation/map", {"symbol": symbol, "interval": interval})

    def get_funding_rates(self) -> List[Dict[str, Any]]:
        """Funding Rates For Perpetual Swaps"""
        return self._get("/perpetual/funding_rate")

    def get_exchange_flow(self, symbol: str = "BTC", interval: str = "24h") -> Dict[str, Any]:
        """Exchange Flow Analysis (BTC & ETH)"""
        return self._get("/exchange/flow", {"symbol": symbol, "interval": interval})

    def get_long_short_ratio(self, symbol: str = "BTC", interval: str = "1h") -> Dict[str, Any]:
        """Long/Short Ratio Analysis"""
        return self._get("/indicator/long_short_accounts", {"symbol": symbol, "interval": interval})

    def get_options_strike_data(self, symbol: str = "BTC") -> Dict[str, Any]:
        """Options Net Premium Strike Heatmap / Strike Pressure"""
        return self._get("/options/strike", {"symbol": symbol})
