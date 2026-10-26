import requests
import logging
from typing import Dict, Any, List, Optional
from .config import COINGECKO_API_KEY

logger = logging.getLogger(__name__)

class CoinGeckoClient:
    """
    Client for CoinGecko API (v3)
    """
    BASE_URL = "https://api.coingecko.com/api/v3" # Standard API
    PRO_BASE_URL = "https://pro-api.coingecko.com/api/v3"

    def __init__(self, api_key: str = COINGECKO_API_KEY):
        self.api_key = api_key
        # Check if it's a pro key
        # Many modern keys starting with CG- are Demo keys and use the standard URL
        # Let's try the standard URL first as it's more common for these keys
        self.url = self.BASE_URL 
        self.headers = {
            "accept": "application/json",
            "x-cg-demo-api-key": self.api_key
        }

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.url}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 401 or response.status_code == 403:
                # Try Pro URL if standard fails with auth error
                logger.info("Retrying with Pro URL...")
                url = f"{self.PRO_BASE_URL}{endpoint}"
                self.headers["x-cg-pro-api-key"] = self.api_key
                if "x-cg-demo-api-key" in self.headers:
                    del self.headers["x-cg-demo-api-key"]
                response = requests.get(url, headers=self.headers, params=params)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching from CoinGecko: {e}")
            return None

    def get_derivatives_exchanges(self) -> List[Dict[str, Any]]:
        """Top Cryptocurrency Derivatives Exchanges Ranked"""
        return self._get("/derivatives/exchanges")

    def get_exchange_assets(self, exchange_id: str) -> Dict[str, Any]:
        """Crypto Exchanges Assets Transparency"""
        return self._get(f"/exchanges/{exchange_id}")

    def get_coin_markets(self, ids: str = "bitcoin,ethereum,cardano,binancecoin,ripple,dogecoin") -> List[Dict[str, Any]]:
        """Volume (24h) by Coin"""
        params = {
            "vs_currency": "usd",
            "ids": ids,
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": False
        }
        return self._get("/coins/markets", params=params)

    def get_public_companies_bitcoin(self) -> Dict[str, Any]:
        """Public Companies Bitcoin Reserves"""
        return self._get("/companies/public_treasury/bitcoin")

    def get_public_companies_ethereum(self) -> Dict[str, Any]:
        """Public Companies Ethereum Reserves"""
        return self._get("/companies/public_treasury/ethereum")
