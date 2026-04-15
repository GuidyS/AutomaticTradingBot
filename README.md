# 🤖 AI-Powered ICT/SMC Trading Bot (v4.5)

![Trading Bot](https://img.shields.io/badge/Strategy-ICT%20%2F%20SMC-gold)
![AI](https://img.shields.io/badge/AI-Gemini%202.5-blue)
![Platform](https://img.shields.io/badge/Platform-MT5%20%2F%20Python-green)

An autonomous professional-grade trading system that integrates **Inner Circle Trader (ICT)** concepts with **Gemini AI** for high-probability trade execution in the Forex and Gold markets.

## 🌟 Key Features

### 🏛️ Institutional Strategies
*   **7-Step ICT Consolidation**: Detects side-ways ranges, identifies liquidity sweeps (Turtle Soup), and executes upon confirmed re-entry.
*   **Optimal Trade Entry (OTE)**: Automatically identifies trend retracement levels (0.62, 0.705, 0.79) for high-reward entries.
*   **Standard Deviation Projections**: Uses SD expansion (2.0, 2.5) for precise institutional profit targets.

### 🧠 Gemini AI Market Analysis
*   **Dual-Playbook Mode**: AI switches between Range (Consolidation) and Trend (OTE) logic based on market context.
*   **Confluence Filtering**: AI validates setups using **FVG (Fair Value Gaps)**, **Order Blocks (OB)**, and Multi-Timeframe (H1/M15) trend analysis.

### 🛡️ Risk & Money Management
*   **Equity Divisor Sizing**: Lot size calculated as `Capital / 10,000`.
*   **Multi-TP Scaling**: Every trade is split into 3 segments with different profit targets to secure gains.
*   **Virtual SL Cache**: Stops are stored locally to prevent broker-side stop-hunting.
*   **Emergency Recovery**: Automatic drawdown protection mode triggers at -10%.

## 🚀 Quick Start

1.  **Install Requirements**:
    ```bash
    pip install MetaTrader5 pandas requests pytz
    ```
2.  **Configure**: Update `config.py` with your MT5 credentials and Gemini API Key.
3.  **Run**:
    ```bash
    python trader.py
    ```

---

## 📂 File Structure
*   `trader.py`: Core execution engine and trading loop.
*   `config.py`: Configuration and symbol profiles.
*   `database.py`: Local trade storage and performance tracking.
*   `ConsolidationICT.mq5`: Native MQL5 version for MetaTrader 5.
*   `consolidation_ict_strategy.pine`: Native PineScript version for TradingView.

> [!IMPORTANT]
> This bot is designed for autonomous trading on **XAUUSDc** and major pairs. Ensure your MT5 account has sufficient margin and the "Market Watch" includes the traded symbols.
