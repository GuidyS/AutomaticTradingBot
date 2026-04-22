import MetaTrader5 as mt5
import pandas as pd
import os
import sys

# Add directory to path to import config
sys.path.append(r'c:\Users\HeyBo\OneDrive\Desktop\Forex')
import config

def get_h1_trend(symbol):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    last_close = df.iloc[-1]['close']
    last_ema = df.iloc[-1]['ema_50']
    return 'UP' if last_close > last_ema else 'DOWN'

def get_m30_trend(symbol):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M30, 0, 100)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    last_close = df.iloc[-1]['close']
    last_ema = df.iloc[-1]['ema_50']
    return 'UP' if last_close > last_ema else 'DOWN'

if mt5.initialize():
    mt5.login(config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER)
    for symbol in ["BTCUSDc", "XAUUSDc"]:
        h1 = get_h1_trend(symbol)
        m30 = get_m30_trend(symbol)
        print(f"Symbol: {symbol} | H1: {h1} | M30: {m30}")
    mt5.shutdown()
else:
    print("MT5 Init Failed")
