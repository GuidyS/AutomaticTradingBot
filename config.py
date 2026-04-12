# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Exness MT5 Authentication
MT5_LOGIN = int(os.getenv('MT5_LOGIN', '0'))
MT5_PASSWORD = os.getenv('MT5_PASSWORD', '')
MT5_SERVER = os.getenv('MT5_SERVER', 'Exness-MT5Trial14')

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'forex_ea')
}

# ============================================================
# 🎯 เลือก Symbol ที่ต้องการเทรด (แก้แค่บรรทัดนี้บรรทัดเดียว!)
# ============================================================
#   "XAUUSDm"  → ทองคำ  (Spread ต่ำ, ATR ~$1-3/M5)
#   "BTCUSDm"  → Bitcoin (Volatile, ATR ~$50-200/M5)
# ============================================================
ACTIVE_SYMBOL = "BTCUSDc"

# ============================================================
# Symbol Profiles — ค่าทุกอย่างเปลี่ยนอัตโนมัติตาม ACTIVE_SYMBOL
# ============================================================
_PROFILES = {
    # ----------------------------------------------------------
    # Profile: XAUUSDm (ทองคำ)
    # ----------------------------------------------------------
    "XAUUSDm": {
        "symbols":           ["XAUUSDm"],
        "strength_pairs":    ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "XAUUSDm"],
        # Scalping (Fixed Pip Mode)
        "scalp_tp_pips":     50,        # 50 pips ≈ $5 / 0.01 Lot
        "scalp_sl_pips":     30,        # 30 pips ≈ $3 / 0.01 Lot
        # ATR Risk Management
        "atr_sl_mul":        0.8,
        "atr_tp_mul":        1.0,
        "trail_activation":  0.8,
        "trail_step":        0.3,
        # Grid Trading
        "grid_symbol":       "XAUUSDm",
        "grid_lot":          0.01,
        "grid_spacing_pips": 100,       # ≈ $1 spacing
        "grid_tp_pips":      100,       # ≈ $1 TP
        "grid_sl_pips":      300,       # ≈ $3 SL (3x spacing = ป้องกัน Trend แรง)
        "grid_max_levels":   5,
        "grid_max_loss":     -50.0,
    },
    # ----------------------------------------------------------
    # Profile: BTCUSDm (Bitcoin)
    # ----------------------------------------------------------
    "BTCUSDc": {
        "symbols":           ["BTCUSDc"],
        "strength_pairs":    ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
        # Scalping (Fixed Pip Mode)
        "scalp_tp_pips":     500,       # 500 pips ≈ $50 movement
        "scalp_sl_pips":     300,       # 300 pips ≈ $30 movement
        # ATR Risk Management
        "atr_sl_mul":        0.8,
        "atr_tp_mul":        1.0,
        "trail_activation":  0.8,
        "trail_step":        0.3,
        # Grid Trading
        "grid_symbol":       "BTCUSDc",
        "grid_lot":          0.01,
        "grid_spacing_pips": 500,       # ≈ $50 spacing
        "grid_tp_pips":      500,       # ≈ $50 TP
        "grid_sl_pips":      1500,      # ≈ $150 SL (3x spacing = ป้องกัน Trend แรง)
        "grid_max_levels":   5,
        "grid_max_loss":     -100.0,
    },
}

# --- Auto-apply Profile ---
_p = _PROFILES.get(ACTIVE_SYMBOL, _PROFILES["XAUUSDm"])
SYMBOLS           = _p["symbols"]
STRENGTH_PAIRS    = _p["strength_pairs"]
SCALP_TP_PIPS     = _p["scalp_tp_pips"]
SCALP_SL_PIPS     = _p["scalp_sl_pips"]
ATR_SL_MULTIPLIER = _p["atr_sl_mul"]
ATR_TP_MULTIPLIER = _p["atr_tp_mul"]
TRAIL_ACTIVATION  = _p["trail_activation"]
TRAIL_STEP        = _p["trail_step"]
GRID_SYMBOL       = _p["grid_symbol"]
GRID_LOT          = _p["grid_lot"]
GRID_SPACING_PIPS = _p["grid_spacing_pips"]
GRID_TP_PIPS      = _p["grid_tp_pips"]
GRID_SL_PIPS      = _p["grid_sl_pips"]   # SL ต่อ Order (pips) — 0 = ไม่มี SL
GRID_MAX_LEVELS   = _p["grid_max_levels"]
GRID_MAX_TOTAL_LOSS = _p["grid_max_loss"]

# ============================================================
# ค่าคงที่ (ไม่เปลี่ยนตาม Symbol)
# ============================================================
TIMEFRAME_TREND = 30  # M30 (Minutes)
TIMEFRAME_ENTRY = 5   # M5  (Minutes)

# Multi-Order Scalping
MAX_ORDERS_PER_SYMBOL = 3
USE_FIXED_PIPS        = False  # False = ใช้ ATR (แนะนำ), True = ใช้ Fixed Pips

# Magic Number & Comment
MAGIC_NUMBER  = 20250410
ORDER_COMMENT = "SMC_AI_v2"

# Money Management
RISK_MODE    = "PERCENT"
FIXED_LOT    = 0.01
RISK_PERCENT = 1.0      # ความเสี่ยง 1% ของพอร์ตต่อออเดอร์

# ATR Period
ATR_PERIOD = 14

# Market Filters
TRADE_TIME_START   = 0
TRADE_TIME_END     = 23
ENABLE_NEWS_FILTER = False
MAX_SPREAD         = 999

# Machine Learning Model
CAT_MODEL_PATH = "catboost_model.pkl"
RF_MODEL_PATH  = "rf_model.pkl"

# Grid Trading (Fixed Settings)
ENABLE_GRID       = True
GRID_MAGIC_NUMBER = 20250412
#   "AUTO"       → ตรวจทิศตลาดอัตโนมัติ (แนะนำ)
#                  H1+M30 ขาขึ้น  → LONG_ONLY
#                  H1+M30 ขาลง   → SHORT_ONLY
#                  ขัดแย้ง/Sideway → SYMMETRIC
#   "SYMMETRIC"  → เปิดทั้ง BUY + SELL (ตลาด Sideway)
#   "LONG_ONLY"  → BUY อย่างเดียว (ตลาดขาขึ้น)
#   "SHORT_ONLY" → SELL อย่างเดียว (ตลาดขาลง)
GRID_MODE         = "AUTO"

# LINE Messaging API
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_USER_ID = os.getenv('LINE_USER_ID', '')

# Telegram Bot API
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
