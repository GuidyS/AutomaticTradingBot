# config.py — v4 Anti-Loss Edition
import os
from dotenv import load_dotenv
load_dotenv()

MT5_LOGIN    = int(os.getenv('MT5_LOGIN', '0'))
MT5_PASSWORD = os.getenv('MT5_PASSWORD', '')
MT5_SERVER   = os.getenv('MT5_SERVER', 'Exness-MT5Trial14')

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'user':     os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'forex_ea')
}

ACTIVE_SYMBOL = ["BTCUSDc", "XAUUSDc"]

# ============================================================
# Symbol Profiles
# ============================================================
_PROFILES = {
    "XAUUSDc": {
        "symbols":           ["XAUUSDc"],
        "strength_pairs":    ["EURUSD","GBPUSD","USDJPY","AUDUSD","XAUUSDc"],
        # Scalp
        "scalp_tp_pips":     150,
        "scalp_sl_pips":     40,
        "scalp_min_sl_pips": 50,
        "scalp_struct_offset": 25,
        # ATR
        "atr_sl_mul":        0.8,
        "atr_tp_mul":        2.5,
        # Break-Even / Trail
        "be_activation_pips": 100,
        "be_offset_pips":     10,
        "trail_activation":   0.8,
        "trail_step":         0.3,
        # Grid
        "grid_symbol":       "XAUUSDc",
        "grid_lot":          0.01,
        "grid_spacing_pips": 100,
        "grid_tp_pips":      500,
        "grid_sl_pips":      300,
        "grid_max_levels":   3,
        "grid_max_loss":    -50.0,
        "grid_basket_tp":    4.0,
        "grid_basket_sl":   -6.0,
        "grid_symmetric_max_levels": 2,
        "grid_atr_multiplier":  1.0,
        "grid_min_spacing_pips": 50,
        # Scalp control
        "max_scalp_orders":  5,
        "min_scalp_spacing": 50,
        # [H] Auto-Hedge
        "hedge_trigger_pips": 80,
        "hedge_basket_tp":    3.0,
    },
    "BTCUSDc": {
        "symbols":           ["BTCUSDc"],
        "strength_pairs":    ["EURUSD","GBPUSD","USDJPY","AUDUSD"],
        # Scalp
        "scalp_tp_pips":     1000,
        "scalp_sl_pips":     400,
        "scalp_min_sl_pips": 200,
        "scalp_struct_offset": 100,
        # ATR
        "atr_sl_mul":        0.8,
        "atr_tp_mul":        2.5,
        # Break-Even / Trail
        "be_activation_pips": 600,
        "be_offset_pips":     100,
        "trail_activation":   0.8,
        "trail_step":         0.3,
        # Grid
        "grid_symbol":       "BTCUSDc",
        "grid_lot":          0.01,
        "grid_spacing_pips": 500,
        "grid_tp_pips":      1500,
        "grid_sl_pips":      1500,
        "grid_max_levels":   3,
        "grid_max_loss":    -50.0,
        "grid_basket_tp":    8.0,
        "grid_basket_sl":   -15.0,
        "grid_symmetric_max_levels": 1,
        "grid_atr_multiplier":  1.0,
        "grid_min_spacing_pips": 500,
        # Scalp control
        "max_scalp_orders":  5,
        "min_scalp_spacing": 500,
        # [H] Auto-Hedge
        "hedge_trigger_pips": 400,
        "hedge_basket_tp":   10.0,
    },
}

if isinstance(ACTIVE_SYMBOL, list) and len(ACTIVE_SYMBOL) > 0:
    SYMBOLS = ACTIVE_SYMBOL
else:
    SYMBOLS = [ACTIVE_SYMBOL] if isinstance(ACTIVE_SYMBOL, str) else ["XAUUSDc"]

# ============================================================
# Core Settings
# ============================================================
MAGIC_NUMBER           = 20250410
ORDER_COMMENT          = "SMC_AI_v4"
ATR_PERIOD             = 14
ENABLE_TRAILING_STOP   = False  # 🛡️ Trailing stop cuts winners short — OFF by default

# Risk
RISK_MODE    = "PERCENT"
FIXED_LOT    = 0.01
RISK_PERCENT = 0.5
MAX_LOT      = 0.5

# ============================================================
# [E] Entry Filter Thresholds
# ============================================================
SCALP_REQUIRE_H1_CONFIRM = True
SCALP_REQUIRE_SMC_ZONE   = True
SCALP_BUY_RSI_MIN        = 45
SCALP_BUY_RSI_MAX        = 65
SCALP_SELL_RSI_MIN       = 35
SCALP_SELL_RSI_MAX       = 55
MIN_RR_RATIO             = 1.5

# ============================================================
# [H] Auto-Hedge
# ============================================================
ENABLE_HEDGE = True

# ============================================================
# [M] Smart Martingale
# ============================================================
ENABLE_MARTINGALE   = False
MART_MAX_LEVEL      = 3
MART_LOT_MULTIPLIER = 1.5

# ============================================================
# Grid
# ============================================================
ENABLE_GRID       = False
GRID_MAGIC_NUMBER = 20250412
GRID_MODE         = "AUTO"
GRID_RISK_MODE    = "PERCENT"
GRID_RISK_PERCENT = 0.1

# ============================================================
# Filters & Timing
# ============================================================
TRADE_TIME_START   = 0
TRADE_TIME_END     = 23
ENABLE_NEWS_FILTER = False

# ============================================================
# Notification
# ============================================================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_USER_ID              = os.getenv('LINE_USER_ID', '')
TELEGRAM_BOT_TOKEN        = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID          = os.getenv('TELEGRAM_CHAT_ID', '')

# ============================================================
# Pending Orders
# ============================================================
ENABLE_PENDING_ORDERS  = True
MAX_PENDING_PER_SYMBOL = 2
PENDING_EXPIRY_HOURS   = 4
BREAKOUT_DISTANCE_PIPS  = 30

# ============================================================
# Portfolio Recovery
# ============================================================
RECOVERY_MODE               = True
RECOVERY_TRIGGER_PERCENT    = 10.0
RECOVERY_EXIT_PROFIT        = 0.50
POST_TRADE_COOLDOWN_MINUTES = 5
ENABLE_LOSS_SHAVING         = True
MIN_PROFIT_TO_SHAVE         = 1.0

