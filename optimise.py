import optuna
import pandas as pd
import numpy as np
import warnings
import MetaTrader5 as mt5
import re
import pathlib
import asyncio
from config import *
from smc_utils import apply_all, dynamic_tp
from backtest_engine import Backtester

warnings.filterwarnings("ignore")

DATA_PATH = "historical_XAUUSD_M15.csv"

from smc_utils import apply_all, dynamic_tp, normalize_columns

def load_data():
    df = pd.read_csv(DATA_PATH, sep=None, engine='python')
    df = normalize_columns(df)
    return df


def MT5_get_history_tf(symbol: str, tf: int, n: int) -> pd.DataFrame:
    if not mt5.initialize():
        return pd.DataFrame()
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    mt5.shutdown()
    if rates is None: return pd.DataFrame()
    df = pd.DataFrame(rates)
    df.columns = [c.lower() for c in df.columns]
    return df

def objective(trial):
    # Search Space
    adx_thr = trial.suggest_int("adx_thr", 20, 26)
    sl_atr = trial.suggest_float("sl_atr", 2.8, 3.5, step=0.1)
    sl_buf = trial.suggest_float("sl_buf", 0.15, 0.5, step=0.05)
    retrace_atr = trial.suggest_float("retrace_atr", 0.30, 0.45, step=0.05)
    break_even_r = trial.suggest_float("break_even_r", 0.25, 0.35, step=0.01)
    tp_mult = trial.suggest_float("tp_mult", 0.05, 0.08, step=0.005)
    ml_thr = trial.suggest_float("ml_thr", 0.65, 0.78, step=0.01)

    # Load data ONCE if possible (or use global)
    global df_cache
    if 'df_cache' not in globals():
        df_cache = load_data()
        df_cache = apply_all(df_cache) # Core indicators
        
    df = df_cache.copy()
    
    # Patch trial-specific logic if needed (e.g. ADX ok)
    df["adx_ok"] = df["adx"] > adx_thr
    
    # Patch config values for this trial
    import config
    original_be = config.BREAK_EVEN_R
    original_tp = config.TP_MULTIPLIER
    original_sl_atr = config.SL_ATR_MULTIPLIER
    original_sl_buf = config.SL_SWIPE_BUFFER
    original_retrace = config.ENTRY_RETRACE_ATR
    original_adx_thr = config.ADX_THRESHOLD
    
    config.BREAK_EVEN_R = break_even_r
    config.TP_MULTIPLIER = tp_mult
    config.ML_THRESHOLD = ml_thr
    config.SL_ATR_MULTIPLIER = sl_atr
    config.SL_SWIPE_BUFFER = sl_buf
    config.ENTRY_RETRACE_ATR = retrace_atr
    config.ADX_THRESHOLD = adx_thr
    
    # Backtest
    bt = Backtester(df)
    result = bt.run()
    
    # Restore config
    config.BREAK_EVEN_R = original_be
    config.TP_MULTIPLIER = original_tp
    config.SL_ATR_MULTIPLIER = original_sl_atr
    config.SL_SWIPE_BUFFER = original_sl_buf
    config.ENTRY_RETRACE_ATR = original_retrace
    config.ADX_THRESHOLD = original_adx_thr
    
    return result


if __name__ == "__main__":
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=30) # Reduced for speed

    print("\n🚀 Best Parameters:")
    for k, v in study.best_params.items():
        print(f"{k} = {v}")

    # Update config.py
    cfg_path = pathlib.Path("config.py")
    cfg_text = cfg_path.read_text()
    
    replace_map = {
        "ADX_THRESHOLD": f"{study.best_params['adx_thr']}",
        "SL_ATR_MULTIPLIER": f"{study.best_params['sl_atr']}",
        "SL_SWIPE_BUFFER": f"{study.best_params['sl_buf']}",
        "ENTRY_RETRACE_ATR": f"{study.best_params['retrace_atr']}",
        "BREAK_EVEN_R": f"{study.best_params['break_even_r']}",
        "TP_MULTIPLIER": f"{study.best_params['tp_mult']}",
        "ML_THRESHOLD": f"{study.best_params['ml_thr']}",
    }

    for var, val in replace_map.items():
        pattern = rf"^{var}\s*=\s*.+$"
        repl = f"{var} = {val}"
        cfg_text = re.sub(pattern, repl, cfg_text, flags=re.MULTILINE)

    cfg_path.write_text(cfg_text)
    print("\n✅ config.py updated.")
