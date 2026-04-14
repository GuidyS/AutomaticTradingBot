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
# 🎯 เลือก Symbol ที่ต้องการเทรด
# ============================================================
ACTIVE_SYMBOL = ["BTCUSDc", "XAUUSDc"]

# ============================================================
# Symbol Profiles
# ============================================================
_PROFILES = {
    "XAUUSDc": {
        "symbols":            ["XAUUSDc"],
        "strength_pairs":     ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "XAUUSDc"],
        # Scalping (Fixed Pip Mode)
        "scalp_tp_pips":      150,      # [P4] เพิ่มเป็น 150 pips เพื่อ R:R ที่คุ้มค่า
        "scalp_sl_pips":      40,
        # ATR Risk Management
        "atr_sl_mul":         0.8,
        "atr_tp_mul":         2.5,      # [P4] เพิ่ม TP multiplier → 2.5
        "be_activation_pips": 100,      # [P4] เลื่อนเป็น 100 pips ให้ราคาได้หายอก
        "be_offset_pips":     10,
        "trail_activation":   0.8,
        "trail_step":         0.3,
        # Grid Trading
        "grid_symbol":        "XAUUSDc",
        "grid_lot":           0.01,
        "grid_spacing_pips":  100,
        "grid_tp_pips":       500,
        "grid_sl_pips":       300,
        "grid_max_levels":    3,
        "grid_max_loss":      -50.0,
        "max_scalp_orders":   3,
        "min_scalp_spacing":  50,
        # [P2] Basket TP/SL (USD)
        "grid_basket_tp":     4.0,
        "grid_basket_sl":    -6.0,      # [P4] กระชับ SL ตะกร้าให้ไวขึ้น -8.0 → -6.0
        # [P2] Trend Lock ใน SYMMETRIC mode
        "grid_symmetric_max_levels": 2,
        # [P2] ATR-Based Dynamic Spacing
        "grid_atr_multiplier": 1.0,
        "grid_min_spacing_pips": 50,
        # Safety
        "scalp_min_sl_pips":  50,
        "scalp_struct_offset": 25,
    },
    "BTCUSDc": {
        "symbols":            ["BTCUSDc"],
        "strength_pairs":     ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
        # Scalping (Fixed Pip Mode)
        "scalp_tp_pips":      1000,
        "scalp_sl_pips":      400,
        # ATR Risk Management
        "atr_sl_mul":         0.8,
        "atr_tp_mul":         2.0,      # [P1] เพิ่ม RR
        "be_activation_pips": 600,
        "be_offset_pips":     100,
        "trail_activation":   0.8,
        "trail_step":         0.3,
        # Grid Trading
        "grid_symbol":        "BTCUSDc",
        "grid_lot":           0.01,
        "grid_spacing_pips":  500,
        "grid_tp_pips":       1500,
        "grid_sl_pips":       1500,
        "grid_max_levels":    3,
        "grid_max_loss":      -50.0,
        "max_scalp_orders":   3,
        "min_scalp_spacing":  500,
        # [P2] Basket TP/SL (USD)
        "grid_basket_tp":     8.0,
        "grid_basket_sl":    -15.0,
        # [P2] Trend Lock
        "grid_symmetric_max_levels": 1,
        # [P2] ATR-Based Dynamic Spacing
        "grid_atr_multiplier": 1.0,
        "grid_min_spacing_pips": 500,
        # Safety
        "scalp_min_sl_pips":  200,
        "scalp_struct_offset": 100,
    },
}

# --- Auto-apply Profile ---
if isinstance(ACTIVE_SYMBOL, list):
    SYMBOLS = ACTIVE_SYMBOL
    _p = _PROFILES.get(SYMBOLS[0], _PROFILES["XAUUSDc"])
else:
    _p = _PROFILES.get(ACTIVE_SYMBOL, _PROFILES["XAUUSDc"])
    SYMBOLS = _p["symbols"]

STRENGTH_PAIRS      = _p["strength_pairs"]
SCALP_TP_PIPS       = _p["scalp_tp_pips"]
SCALP_SL_PIPS       = _p["scalp_sl_pips"]
ATR_SL_MULTIPLIER   = _p["atr_sl_mul"]
ATR_TP_MULTIPLIER   = _p["atr_tp_mul"]
TRAIL_ACTIVATION    = _p["trail_activation"]
TRAIL_STEP          = _p["trail_step"]
GRID_SYMBOL         = _p["grid_symbol"]
GRID_LOT            = _p["grid_lot"]
GRID_SPACING_PIPS   = _p["grid_spacing_pips"]
GRID_TP_PIPS        = _p["grid_tp_pips"]
GRID_SL_PIPS        = _p["grid_sl_pips"]
GRID_MAX_LEVELS     = _p["grid_max_levels"]
GRID_MAX_TOTAL_LOSS = _p["grid_max_loss"]
SCALP_MIN_SL_PIPS   = _p.get("scalp_min_sl_pips", 50)
SCALP_STRUCTURAL_OFFSET = _p.get("scalp_struct_offset", 25)

# ============================================================
# ค่าคงที่ (ไม่เปลี่ยนตาม Symbol)
# ============================================================
TIMEFRAME_TREND = 30
TIMEFRAME_ENTRY = 5
USE_FIXED_PIPS  = False
MAGIC_NUMBER    = 20250410
ORDER_COMMENT   = "SMC_AI_v3"
MAX_ORDERS_PER_SYMBOL = _p.get("max_scalp_orders", 3)

# ============================================================
# [P1] PHASE 1 — Emergency Risk Reduction
# ============================================================
RISK_MODE    = "PERCENT"
FIXED_LOT    = 0.01
RISK_PERCENT = 0.5
ATR_PERIOD   = 14
TRADE_TIME_START   = 0
TRADE_TIME_END     = 23
ENABLE_NEWS_FILTER = False
MAX_SPREAD         = 999
CAT_MODEL_PATH = "catboost_model.pkl"
RF_MODEL_PATH  = "rf_model.pkl"

# ความถี่ของ AI และการสรุปผล
AI_CHECK_INTERVAL_HOURS = 1
PERFORMANCE_REPORT_INTERVAL_HOURS = 4

# ============================================================
# Grid Trading
# ============================================================
ENABLE_GRID       = True
GRID_MAGIC_NUMBER = 20250412
GRID_MODE = "AUTO"
GRID_BASKET_TP_USD  = _p.get("grid_basket_tp", 4.0)
GRID_BASKET_SL_USD  = _p.get("grid_basket_sl", -8.0)
GRID_RISK_MODE      = "PERCENT"
GRID_RISK_PERCENT   = 0.1  # เริ่มต้นที่ 0.1% ต่อไม้

# LINE & Telegram
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_USER_ID = os.getenv('LINE_USER_ID', '')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID', '')

# Pending Orders
ENABLE_PENDING_ORDERS   = True
MAX_PENDING_PER_SYMBOL  = 2
PENDING_EXPIRY_HOURS    = 4
BREAKOUT_DISTANCE_PIPS  = 30

# Recovery & Cooldown
RECOVERY_MODE               = True
RECOVERY_TRIGGER_PERCENT    = 10.0  # เริ่มกู้พอร์ตเมื่อติดลบเกิน 10% ของบาลานซ์
RECOVERY_EXIT_PROFIT        = 0.50
POST_TRADE_COOLDOWN_MINUTES = 2
ENABLE_LOSS_SHAVING   = True
MAX_OPPOSITE_SCALPS   = 1
MIN_PROFIT_TO_SHAVE   = 1.0

# ============================================================
# [P3] Scalp Signal Filter Thresholds
# ============================================================
SCALP_REQUIRE_H1_CONFIRM = True
SCALP_REQUIRE_SMC_ZONE   = True
SCALP_BUY_RSI_MIN  = 45
SCALP_BUY_RSI_MAX  = 65
SCALP_SELL_RSI_MIN = 35
SCALP_SELL_RSI_MAX = 55

# ============================================================
# [P4] Win Rate Tracking
# ============================================================
ENABLE_TRADE_TYPE_TRACKING = True

# ============================================================
# [P4] Virtual (Hidden) Stop Loss
# ============================================================
ENABLE_VIRTUAL_SL  = True   # บอทจะซ่อน SL จากโบรกเกอร์ (ยกเว้น Emergency SL)
EMERGENCY_SL_PIPS  = 300    # SL จริงที่วางไว้ไกลๆ เพื่อความปลอดภัย (300 pips)
HIDDEN_BE_ENABLED  = True   # ซ่อนจุด Break-Even ต่อไปด้วย