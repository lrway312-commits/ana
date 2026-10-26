# 👑 ZERO-BTC SOVEREIGN FORENSIC TRADING PROTOCOL (PHASE 16.0)

> **Institutional Algorithmic Telemetry, Microstructure Order Flow & Symmetrical Execution Engine for Bitcoin (BTC/USDT Perpetual & Spot)**

---

## 📌 Overview
This repository contains the complete production codebase, data ingestion infrastructure, forensic telemetry snapshots, and master governing protocol for the **ZERO-BTC Trading System (Phase 16.0: The Sovereign Omnidirectional Matrix)**.

The system integrates real-time institutional order book dynamics, Level-3 trade flow imbalances, multi-exchange basis spreads, liquidation cascades, and Wyckoff/Auction Market Theory (AMT) structures.

---

## 🏛️ Master Protocol & Constitutional Documentation
* **[ZeroZero_Protocol_V16_Sovereign_Master.md](file:///c:/Users/ersan/Desktop/ZERO_BTC_FINAL/ZeroZero_Protocol_V16_Sovereign_Master.md)**: The supreme constitutional protocol defining all 5 execution engines, 15+ mandatory zero-tolerance vetoes, dynamic risk management, and the cumulative rule evolution across all 90 recorded trades.
* **[price_analysis/CONTINUOUS_FORENSIC_JOURNAL.md](file:///c:/Users/ersan/Desktop/ZERO_BTC_FINAL/price_analysis/CONTINUOUS_FORENSIC_JOURNAL.md)**: The continuous live forensic journal documenting all 30-minute forensic cycles (Cycles 1000 through 1106+).

---

## ⚙️ Data Ingestion & Fetching Engine (`src/` & Root Schedulers)
* **`src/binance_client.py`**: High-frequency client for Binance Spot and USD-M Futures APIs. Fetches mid-prices, Level-2/3 order book depth (0.5%, 1%, 2% imbalance), aggregated trade flow (`aggTrades`), whale large block trades, open interest, and Klines.
* **`run_fetch_scheduler.py`**: Automated cron scheduler collecting multi-dimensional telemetry snapshots every 15/30 minutes and persisting them as structured JSON files in `price_analysis/بيانات/`.
* **`run_liquidation_websocket.py`**: Real-time WebSocket listener tracking Binance liquidation cascades (`!forceOrder@arr`), computing 25x, 50x, and 100x liquidation clusters and liquidity magnets.
* **`src/smc_engine.py`**: Smart Money Concepts engine calculating Anchored VWAP (AVWAP), dynamic standard deviation volatility bands ($\pm 1\sigma, \pm 2\sigma$), Fair Value Gaps (FVG), and order blocks.
* **`src/derivatives_intel.py`**: Derivatives intelligence calculating Spot vs Futures basis spreads, Open Interest delta velocity, and Options Gamma regimes (Long vs Short Gamma).

---

## 📊 Telemetry Dataset (Last 3 Days)
Located in `price_analysis/بيانات/`:
* Contains complete microsecond-level telemetry snapshots (`BTCUSDT_snapshot_*.json`) captured across the last 3 days of institutional market action.
* Each snapshot captures:
  - Exact order book bid/ask distributions
  - Stoikov micro-price & arrival rates
  - Wyckoff Effort-vs-Result (EvR) ratios
  - Net institutional flow & whale block executions
  - Active liquidation magnets and structural SMC biases

---

## 🚀 Quickstart & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Create or verify your `.env` file in the project root:
```env
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here
SYMBOL=BTCUSDT
```

### 3. Launch Data Fetching Schedulers
```bash
# Start 15-minute telemetry snapshot scheduler
python run_fetch_scheduler.py

# Start real-time liquidation WebSocket tracker
python run_liquidation_websocket.py
```
