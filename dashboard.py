import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# import vectorbt as vbt

import pathlib
import os
import MetaTrader5 as mt5
import datetime as dt
from backtest_engine import Backtester
from smc_utils import apply_all, dynamic_tp, normalize_columns
import config

st.set_page_config(page_title="SMC Expert v2 Dashboard", layout="wide", page_icon="💹")

@st.cache_data
def load_history(filename):
    path = filename
    if not os.path.exists(path): return pd.DataFrame()
    df = pd.read_csv(path, sep=None, engine='python')
    df = normalize_columns(df)
    return df

st.sidebar.title("🔧 Expert v2 Params")
dataset = st.sidebar.radio("📊 Select Dataset", ["3 Months", "1 Year"])
data_file = "historical_XAUUSD_M15.csv" if dataset == "3 Months" else "historical_XAUUSD_M15_1y.csv"

sl_atr = st.sidebar.slider("SL ATR Multiplier", 2.5, 4.0, float(config.SL_ATR_MULTIPLIER), 0.1)
retrace = st.sidebar.slider("Entry Retrace %", 0.1, 0.6, float(config.ENTRY_RETRACE_ATR), 0.05)
adx_thr = st.sidebar.slider("ADX Threshold", 15, 30, int(config.ADX_THRESHOLD))
be_r = st.sidebar.slider("Break-Even (R)", 0.2, 0.5, float(config.BREAK_EVEN_R), 0.05)
ml_thr = st.sidebar.slider("ML Threshold", 0.5, 0.8, float(config.ML_THRESHOLD), 0.01)

if st.button("🚀 Run Analysis"):
    df_raw = load_history(data_file)

    if df_raw.empty:
        st.error("Historical data not found!")
    else:
        # Prepare
        df = apply_all(df_raw, sl_atr=sl_atr, retrace_atr=retrace, adx_thr=adx_thr)
        
        # Run Backtest
        bt = Backtester(df)
        # Patch config for simulation
        import config
        config.BREAK_EVEN_R = be_r
        config.ML_THRESHOLD = ml_thr
        
        bt.run()
        
        # Display
        st.subheader("📊 Performance Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Final Balance", f"${bt.balance:,.2f}")
        winrate = (bt.wins / (bt.wins + bt.losses)) * 100 if (bt.wins + bt.losses) > 0 else 0
        col2.metric("Win Rate", f"{winrate:.1f}%")
        col3.metric("Total Trades", f"{bt.wins + bt.losses}")
        
        # (Equity curve and other plots would go here)
        st.info("Simulation complete. Check logs for trade details.")

st.sidebar.markdown("---")
if st.sidebar.checkbox("📂 Show Live Log"):
    log_path = "logs/trade_log.csv"
    if os.path.exists(log_path):
        st.dataframe(pd.read_csv(log_path).tail(20))
    else:
        st.warning("No logs found. Start trader.py first.")
