
import os
import asyncio
import logging
import random
from playwright.async_api import async_playwright

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("chart_capture")

OUTPUT_DIR = os.path.join("price_analysis", "charts")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# قائمة المهام المطلوبة للجلب
CAPTURE_TASKS = [
    {"name": "coinglass_btc_treasuries", "url": "https://www.coinglass.com/BitcoinTreasuries"},
    {"name": "coinglass_whale_alert", "url": "https://www.coinglass.com/whale-alert"},
    {"name": "coinglass_btc_heatmap", "url": "https://www.coinglass.com/pro/futures/LiquidationHeatMapNew?coin=BTC&type=pair"},
    {"name": "coinglass_liquidation_map", "url": "https://www.coinglass.com/pro/futures/LiquidationMap"},
    {"name": "coinglass_liquidations", "url": "https://www.coinglass.com/liquidations"},
    {"name": "coinglass_liquidation_maxpain", "url": "https://www.coinglass.com/liquidation-maxpain"},
    {"name": "coinglass_funding_rate", "url": "https://www.coinglass.com/FundingRate"},
    {"name": "coinglass_futures_volume", "url": "https://www.coinglass.com/pro/futures/FuturesVolume"},
    {"name": "coinglass_transparency", "url": "https://www.coinglass.com/Transparency"},
    {"name": "coinglass_exchanges", "url": "https://www.coinglass.com/exchanges"},
    {"name": "coinglass_options_vol_expiry", "url": "https://www.coinglass.com/pro/options/VolExpiry"},
    {"name": "coinglass_options_net_premium", "url": "https://www.coinglass.com/pro/options/net-premium-strike-heatmap"},
    {"name": "coinglass_options_max_pain", "url": "https://www.coinglass.com/pro/options/max-pain"},
    {"name": "coinglass_options_main", "url": "https://www.coinglass.com/options"},
    {"name": "coinglass_etf_main", "url": "https://www.coinglass.com/etf"},
    {"name": "coinglass_etf_btc", "url": "https://www.coinglass.com/etf/bitcoin"},
    {"name": "coinglass_spot_inflow", "url": "https://www.coinglass.com/spot-inflow-outflow"},
    {"name": "coinglass_inflow_outflow", "url": "https://www.coinglass.com/inflow-outflow"},
    {"name": "coinglass_long_short_ratio", "url": "https://www.coinglass.com/LongShortRatio"},
    {"name": "coinglass_orderbook_pressure", "url": "https://www.coinglass.com/orderbook-pressure"},
    {"name": "coinglass_large_orderbook", "url": "https://www.coinglass.com/large-orderbook-statistics"},
    {"name": "coinglass_combined_orderbook", "url": "https://www.coinglass.com/mergev2/BTC-USDT"},
    {"name": "coinglass_liquidity_heatmap", "url": "https://www.coinglass.com/LiquidityHeatmap"},
    {"name": "tradingview_adausdt", "url": "https://ar.tradingview.com/chart/Hod3AQZ3/?symbol=BINANCE%3AADAUSDT"},
    {"name": "tradingview_btcusdt", "url": "https://ar.tradingview.com/chart/Hod3AQZ3/?symbol=BINANCE%3ABTCUSDT"}
]

async def capture_single_task(browser, task):
    name = task["name"]
    url = task["url"]
    path = os.path.join(OUTPUT_DIR, f"{name}.png")
    
    logger.info(f"Starting task: {name}")
    context = None
    page = None
    try:
        # Create a fresh context for each task to avoid cache pollution
        context = await browser.new_context(
            viewport={'width': 1600, 'height': 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Stealth
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Goto with increased timeout
        try:
            await page.goto(url, timeout=90000, wait_until="commit")
        except Exception as e:
            logger.warning(f"Timeout/Error loading {url}, but trying to proceed: {e}")
        
        # Check for redirects
        if "pro/futures" in url and "pro/futures" not in page.url:
             logger.warning(f"Redirected from {url} to {page.url}. This might be wrong.")

        # Initial wait
        await asyncio.sleep(5)
        
        # Auto-scroll logic
        try:
            for i in range(1, 4):
                await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i/3})")
                await asyncio.sleep(1)
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass
            
        # Popup handling (simplified for async)
        try:
            await page.evaluate("""() => {
                ['.ant-modal-mask', '.ant-modal-wrap', '.login-modal', '.mask', '.overlay', '.dialog-mask'].forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        el.style.display = 'none';
                        el.remove();
                    });
                });
            }""")
        except Exception:
            pass

        # Final wait for data loading
        await asyncio.sleep(15)
        
        # Screenshot
        await page.screenshot(path=path, full_page=True)
        logger.info(f"Done: {name}")
        return path

    except Exception as e:
        logger.error(f"Error in {name}: {e}")
        return None
    finally:
        if page:
            await page.close()
        if context:
            await context.close()

async def capture_all_charts():
    logger.info("Starting Async Parallel Capture...")
    start_time = asyncio.get_event_loop().time()
    
    async with async_playwright() as p:
        # Launch browser once
        browser = await p.chromium.launch(headless=True)
        
        # Semaphore to limit concurrent tabs/contexts (3 workers)
        sem = asyncio.Semaphore(3)
        
        async def run_with_sem(task):
            async with sem:
                return await capture_single_task(browser, task)

        tasks = [run_with_sem(task) for task in CAPTURE_TASKS]
        results = await asyncio.gather(*tasks)
        
        await browser.close()
    
    end_time = asyncio.get_event_loop().time()
    logger.info(f"Async Parallel Capture finished in {end_time - start_time:.1f} seconds.")
    return [r for r in results if r]

if __name__ == "__main__":
    asyncio.run(capture_all_charts())
