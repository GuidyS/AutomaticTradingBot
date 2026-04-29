# 💹 Automatic Trading Bot - Expert v2 (SMC + ML)

Institutional-grade SMC (Smart Money Concepts) trading bot for XAUUSD (Gold), enhanced with Machine Learning filters and real-time monitoring.

## 🚀 Key Features
- **Expert v2 Logic**: Advanced SMC detection (BOS, Liquidity Sweeps, Order Blocks) using vectorized processing.
- **Trend Filtering**: Integrated ADX and Multi-Timeframe (H1, H2, H4) trend confirmation.
- **Machine Learning**: Random Forest classifier to filter low-probability trade signals.
- **Risk Management**: Dynamic SL/TP based on ATR, Break-even (0.25R), and Trailing Stop (0.8R).
- **Telegram Notifications**: Real-time alerts for system status, orders, and performance summaries.
- **Visual Dashboard**: Streamlit-based UI for live monitoring and interactive parameter analysis.
- **Auto-Optimisation**: Optuna-based parameter tuner to find the most profitable settings.

## 📦 Installation
1. Install Python 3.9+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your MT5 credentials and Telegram bot in `.env`:
   ```env
   MT5_LOGIN=your_login
   MT5_PASSWORD=your_password
   MT5_SERVER=your_server
   TELEGRAM_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

## 🛠 Usage
### 1. Live Trading
Run the main trading engine:
```bash
python trader.py
```

### 2. Monitoring Dashboard
Open the visual dashboard in your browser:
```bash
streamlit run dashboard.py
```

### 3. Parameter Optimisation
Fine-tune your settings based on historical data:
```bash
python optimise.py
```

### 4. Data Downloader
Fetch fresh historical data from MT5:
```bash
python download_history.py
```

## 📂 Project Structure
- `trader.py`: Core execution engine.
- `smc_utils.py`: SMC indicators and data processing logic.
- `backtest_engine.py`: High-speed backtest simulator.
- `optimise.py`: Optuna optimisation script.
- `dashboard.py`: Streamlit monitoring interface.
- `telegram_utils.py`: Notification service.
- `ml_classifier.py`: Machine Learning model logic.
- `config.py`: Global settings and tuned parameters.

## ⚠️ Disclaimer
Trading involves significant risk. This bot is for educational and research purposes. Always test on a Demo account before using live capital.
