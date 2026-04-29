import pandas as pd
import numpy as np
import ta

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names and merge Date/Time to epoch."""
    df.columns = [c.strip().strip('<>').lower() for c in df.columns]
    mapping = {
        'vol': 'tick_volume',
        'volume': 'tick_volume',
        'tickvol': 'tick_volume',
        'date': 'date',
        'time': 'time'
    }
    df = df.rename(columns=mapping)
    
    # Merge Date + Time into a single unix epoch column if both exist
    if 'date' in df.columns and 'time' in df.columns:
        try:
            dt_str = df['date'].astype(str) + ' ' + df['time'].astype(str)
            df['time'] = pd.to_datetime(dt_str).astype('int64') // 10**9
            # df.drop(columns=['date'], inplace=True) # Optional
        except:
            pass
    return df



def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's Average True Range"""
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def _pivot_high_low(df: pd.DataFrame, window: int = 2):
    """True/False pivot high / low (centered window)"""
    ph = (df["high"] == df["high"].rolling(window*2+1, center=True).max())
    pl = (df["low"]  == df["low"].rolling(window*2+1, center=True).min())
    return ph, pl

def detect_order_blocks(df: pd.DataFrame) -> pd.DataFrame:
    ph, pl = _pivot_high_low(df, window=2)
    # Look forward 5 bars for mitigation/confirmation
    min_low_forward = df["low"].rolling(5).min().shift(-5)
    max_high_forward = df["high"].rolling(5).max().shift(-5)
    
    df["ob_up"] = ph & (min_low_forward < df["high"] * 0.999)
    df["ob_down"] = pl & (max_high_forward > df["low"] * 1.001)
    return df

def detect_bos(df: pd.DataFrame) -> pd.DataFrame:
    """Break-of-Structure using 20 bar rolling high/low"""
    high_swing = df["high"].rolling(20).max().shift(1)
    low_swing  = df["low"].rolling(20).min().shift(1)
    df["bos_up"] = df["close"] > high_swing
    df["bos_down"] = df["close"] < low_swing
    return df

def detect_liquidity_sweep(df: pd.DataFrame, look_back: int = 20) -> pd.DataFrame:
    """Detect liquidity sweep based on recent high/low and ATR"""
    if "atr" not in df.columns:
        df["atr"] = atr(df)
        
    prev_high = df["high"].rolling(look_back).max().shift(1)
    prev_low = df["low"].rolling(look_back).min().shift(1)
    range_size = prev_high - prev_low
    
    df["sweep_up"] = (df["high"] > prev_high) & (df["close"] < prev_high) & \
                     ((df["high"] - prev_high) > (0.02 * range_size))
                     
    df["sweep_down"] = (df["low"] < prev_low) & (df["close"] > prev_low) & \
                       ((prev_low - df["low"]) > (0.02 * range_size))
    return df


def add_adx_direction(df: pd.DataFrame, window: int = 14, thr: int = 22):
    """Add ADX and DI indicators for trend direction and strength"""
    indicator_adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=window)
    df["adx"] = indicator_adx.adx()
    df["di_plus"] = indicator_adx.adx_pos()
    df["di_minus"] = indicator_adx.adx_neg()
    df["adx_ok"] = df["adx"] > thr
    df["adx_trend"] = np.where(df["di_plus"] > df["di_minus"], 1, -1)
    return df

def dynamic_tp(entry, direction, atr, base_mult=1.0):
    """
    Scale TP levels based on market volatility (ATR).
    Higher ATR -> Wider TPs.
    """
    mult = base_mult
    if atr > 6.0: mult *= 1.25
    elif atr < 3.0: mult *= 0.90
    
    import config
    tps = [entry + direction * (atr * config.SL_ATR_MULTIPLIER + config.SL_SWIPE_BUFFER) * r * mult for r in config.TP_LEVELS]
    return tps

def apply_all(df: pd.DataFrame,
              sl_atr: float = 3.2,
              sl_buf: float = 0.2,
              retrace_atr: float = 0.35,
              adx_thr: int = 22) -> pd.DataFrame:
    """
    Expert v2 processing pipeline.
    """
    df = df.copy()
    df = normalize_columns(df)
    
    df["atr"] = atr(df, period=14)
    df = add_adx_direction(df, thr=adx_thr)
    df = detect_order_blocks(df)
    df = detect_bos(df)
    df = detect_liquidity_sweep(df)
    
    return df



