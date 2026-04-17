# config.py — v6.1 Hybrid AI Edition (XAUUSD Focus)
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

# 🎯 โฟกัสเฉพาะทองคำ
ACTIVE_SYMBOL = ["XAUUSDc"]

# ============================================================
# Symbol Profiles (Intraday M15 Focus)
# ============================================================
_PROFILES = {
    "XAUUSDc": {
        "symbols":           ["XAUUSDc"],
        "strength_pairs":    ["EURUSD","GBPUSD","USDJPY","AUDUSD","XAUUSDc"],
        # Intraday
        "scalp_tp_pips":     500,   # เป้ากำไร 500 จุด (5$ ทอง)
        "scalp_sl_pips":     300,   # SL 300 จุด (3$ ทอง)
        "scalp_min_sl_pips": 150,   # SL ขั้นต่ำ 150 จุด กันโดนสวิงหลอก
        "scalp_struct_offset": 50,
        # ATR
        "atr_sl_mul":        1.5,
        "atr_tp_mul":        3.0,
        # Break-Even / Trail
        "be_activation_pips": 250,  # กันทุนเมื่อกำไร 2.5$
        "be_offset_pips":     30,
        "trail_activation":   1.2,
        "trail_step":         0.5,
        # Layer control
        "max_scalp_orders":  5,
        "min_scalp_spacing": 50,
        "layer_basket_tp_per_order_usd": 5.0,
        "max_spread_pips":   40,
        # Auto-Hedge
        "hedge_trigger_pips": 400,
        "hedge_basket_tp":    5.0,
    }
}

if isinstance(ACTIVE_SYMBOL, list) and len(ACTIVE_SYMBOL) > 0:
    SYMBOLS = ACTIVE_SYMBOL
else:
    SYMBOLS = [ACTIVE_SYMBOL] if isinstance(ACTIVE_SYMBOL, str) else ["XAUUSDc"]

# ============================================================
# Core Settings
# ============================================================
MAGIC_NUMBER           = 20250415
ORDER_COMMENT          = "Intraday_V4"
ATR_PERIOD             = 14
# -------------------------------------------------------------
# MONEY MANAGEMENT (7-Step Consolidation Rule)
# -------------------------------------------------------------
RISK_MODE              = "DIVISOR"   # Options: "FIXED", "PERCENT", "DIVISOR"
LOT_DIVISOR            = 10000       # Lot size = Balance / 10000
RISK_PERCENT           = 1.0         # Used only if RISK_MODE = "PERCENT"
FIXED_LOT              = 0.02        # Used only if RISK_MODE = "FIXED"
MIN_LOT                = 0.02        # ขั้นต่ำเริ่มที่ 0.02
MAX_LOT                = 2.0
MAX_DAILY_LOSS_USD     = 200.0

# [ICT] 7-Step Consolidation Strategy
ICT_STRATEGY_ENABLED   = True
CONSOLIDATION_TP_MULTS = [0.5, 0.75, 1.0] # Fibo expansion multipliers vs BoxSize
ICT_RECOVERY_INTERVAL  = 900             # Notification throttle (15 min)
MAX_PORTFOLIO_RISK_USD = 500.0
MAX_SPREAD_PIPS        = 0
ENABLE_WEEKEND_CLOSE   = True

# [E] Entry Filter Thresholds (Intraday)
SCALP_REQUIRE_H1_CONFIRM = True   # บังคับเทรดตามเทรนด์ H1 เสมอ
SCALP_REQUIRE_SMC_ZONE   = True
SCALP_BUY_RSI_MIN        = 40
SCALP_BUY_RSI_MAX        = 65
SCALP_SELL_RSI_MIN       = 35
SCALP_SELL_RSI_MAX       = 60
MIN_RR_RATIO             = 1.2    # ปรับเหลือ 1.2 จะเข้าออเดอร์ง่ายขึ้น
ENABLE_MULTI_TP          = True   # เปิดระบบ TP 1, 2, 3
MULTI_TP_RATIOS          = [0.4, 0.3, 0.3]  # แบ่ง Lot 40% / 30% / 30%
MULTI_TP_RR_LEVELS       = [1, 1.5, 2.5]  # ระดับ TP ในมุมมอง Risk:Reward (TP1, TP2, TP3)

# [AI] Fully AI-Driven Trading
ENABLE_AI_TRADING_MODE   = True
AI_PROVIDER              = "GEMINI"
AI_API_KEY               = os.getenv('GEMINI_API_KEY', '') # ไปตั้งค่าในไฟล์ .env ถ้ามี หรือใส่ตรงนี้ก็ได้
AI_MODEL                 = "gemini-2.0-flash-lite"
AI_CONFIDENCE_THRESHOLD  = 70
AI_CHECK_INTERVAL        = 7200   # ลดความถี่เหลือ 2 ชั่วโมง เพื่อแก้ปัญหา RPD Quota เต็ม
ENABLE_AGGRESSIVE_AI_ENTRY = True # ถ้าความมั่นใจเกินเกณฑ์ ให้เปิดไม้ Market ทันที
AI_AGGRESSIVE_THRESHOLD    = 75   # เกณฑ์ความแม่นยำ (%) ที่จะสั่งเปิดไม้แบบ Aggressive
AI_DOUBLE_ENTRY_THRESHOLD  = 85   # เกณฑ์ความมั่นใจ (%) ที่อนุญาตให้เบิ้ลไม้ (Double Entry)

# --- Ollama Local AI Fallback (Resilience for 429 errors) ---
ENABLE_OLLAMA_FALLBACK    = True
OLLAMA_MODEL              = "llama3.1:latest" # หรือตัวที่คุณลงไว้ในเครื่อง
OLLAMA_API_URL            = "http://localhost:11434/api/generate"


ENABLE_GOLD_SESSION_FILTER = False 
GOLD_DISALLOW_HOURS        = [7, 8, 9, 10]

ENABLE_HEDGE = False

ENABLE_MARTINGALE   = False
MART_MAX_LEVEL      = 3
MART_LOT_MULTIPLIER = 1.5

TRADE_TIME_START   = 0
TRADE_TIME_END     = 23
ENABLE_NEWS_FILTER = True
NEWS_MODE          = "AVOID"
NEWS_MINUTES_BEFORE = 30
NEWS_MINUTES_AFTER  = 30

TELEGRAM_BOT_TOKEN        = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID          = os.getenv('TELEGRAM_CHAT_ID', '')

ENABLE_PENDING_ORDERS  = True
MAX_PENDING_PER_SYMBOL = 5
PENDING_EXPIRY_HOURS   = 4
BREAKOUT_DISTANCE_PIPS  = 30

RECOVERY_MODE               = False
RECOVERY_TRIGGER_PERCENT    = 10.0
RECOVERY_EXIT_PROFIT        = 5.0
RECOVERY_LOT_MULTIPLIER     = 1.5
POST_TRADE_COOLDOWN_MINUTES = 0.1
ENABLE_LOSS_SHAVING         = False
MIN_PROFIT_TO_SHAVE         = 2.0