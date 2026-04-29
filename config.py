# config.py

SYMBOL = "XAUUSDm"
TIMEFRAME = 15  # M15

# --- Risk Management ---
RISK_PERCENT = 0.5          # Reduced for stability (Recommended 0.3 - 0.8%)
LOT_MIN = 0.01
LOT_MAX = 1.0

# --- Stop Loss & Entry Tuning ---
SL_ATR_MULTIPLIER = 3.2     # Optimized
SL_SWIPE_BUFFER = 0.2       # Optimized
ENTRY_RETRACE_ATR = 0.35    # Optimized
ADX_THRESHOLD = 22          # Minimum trend strength

# --- Take Profit Levels (R-based) ---
# TP1: 0.5R, TP2: 1.0R, TP3: 1.5R, TP4: 2.0R (Expert v2 Split)
TP_LEVELS = [0.5, 1.0, 1.5, 2.0]
TP_LOT_SPLIT = [0.30, 0.30, 0.30, 0.10]
TP_MULTIPLIER = 0.06        # 1R scale factor

# --- Defensive Logic ---
BREAK_EVEN_R = 0.3          # Move to BE at 0.3R profit
TRAIL_START_R = 0.4         # Start trailing at 0.4R
TRAIL_DISTANCE_R = 0.8      # Keep SL 0.8R behind price

# --- Strategy Filters ---
SWING_LOOKBACK = 5
SWEEP_LOOKBACK = 20
SWEEP_STRENGTH_RATIO = 0.05 
ML_THRESHOLD = 0.70         

# --- Timeframe Filters ---
USE_MULTI_TF = True
USE_H2 = True               # Medium TF confirmation
HTF_TIMEFRAME = "H1"

# --- Session / Time-filter (UTC) ---
TRADING_SESSIONS = [
    ("00:00", "09:00"),
    ("13:00", "20:00"),
]


# --- MT5 Connection ---
MAGIC = 20250429
MT5_LOGIN = 0
MT5_PASSWORD = ""
MT5_SERVER = ""