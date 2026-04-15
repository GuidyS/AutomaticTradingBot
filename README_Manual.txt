================================================================================
AI-POWERED ICT/SMC TRADING BOT - TECHNICAL MANUAL (v4.5)
================================================================================

1. OVERVIEW
-----------
This bot is a Python-based autonomous trading engine designed for MetaTrader 5 (MT5).
It combines high-level SMC (Smart Money Concepts) logic with Gemini AI to filter 
market noise and execute high-probability institutional setups.

2. CORE STRATEGIES
------------------
A. Playbook 1: ICT Consolidation Sweep
   - Identifies an "Original Consolidation" (OC) box on the H1 timeframe.
   - Monitors for a "Turtle Soup" (Liquidity Sweep) outside the box.
   - Trigger: Price must close back INSIDE the box on M15.
   - Confirmation: Candlestick pattern or price reaching the 0.5 Fibo level.

B. Playbook 2: ICT Trending OTE (Optimal Trade Entry)
   - Identifies the current "Impulsive Leg" (Market Structure).
   - Retracements are measured at 62%, 70.5%, and 79% Fibonacci levels.
   - Confluence: AI seeks overlap with Fair Value Gaps (FVG) or Order Blocks.
   - Targets: SD (Standard Deviation) 2.0 and 2.5 of the impulsive leg.

3. MONEY MANAGEMENT
-------------------
- Risk Mode: DIVISOR
- Rule: 1 Lot per 10,000 Equity (e.g., $10,000 Balance = 1.00 Lot).
- Multi-TP: Positions are split into 3 orders with ratios [0.4, 0.3, 0.3].
- SL Method: SL is set based on the Box Size or OTE structure (approx. 1:1 initial RR).

4. CONFIGURATION (config.py)
----------------------------
- AI_API_KEY: Your Google Gemini API key.
- MT5_LOGIN / MT5_PASSWORD / MT5_SERVER: Your account details.
- SYMBOLS: List of pairs to trade (e.g., ["XAUUSDc", "EURUSD"]).
- ICT_STRATEGY_ENABLED: Set to True to active Playbooks 1 & 2.
- RECOVERY_TRIGGER_PERCENT: Drawdown % to activate emergency recovery mode (Default: -10%).

5. USAGE INSTRUCTIONS
---------------------
1. Ensure MetaTrader 5 is installed and logged in.
2. Open MT5 -> Tools -> Options -> Expert Advisors -> Allow WebRequest.
3. Install Python dependencies: pip install MetaTrader5 pandas requests.
4. Run: python trader.py
5. View terminal logs for real-time AI decision making.

6. SAFETY FEATURES
------------------
- Virtual SL: The bot hides your stop-losses from the broker.
- Notification Throttling: Drawdown alerts are limited to every 15 minutes.
- Weekend Protection: Closes positions Friday night to avoid gaps.
- Spread Check: Blocks trades if spread exceeds 3.0 pips (XAUUSDc).

7. TROUBLESHOOTING
------------------
- ERROR: "AI Analytics Error": Check your API key or internet connection.
- ERROR: "MT5 Disconnected": The bot will auto-retry every 10 seconds.
- ERROR: "Max Orders hit": The bot has reached the symbol order cap (Default: 3).

================================================================================
Developed by: Antigravity AI Trading Systems
================================================================================
