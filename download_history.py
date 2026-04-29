import MetaTrader5 as mt5
import pandas as pd
import datetime as dt
import os
from dotenv import load_dotenv

load_dotenv()

# Config
SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_M15
DAYS_BACK = 365
FILENAME = "historical_XAUUSD_M15_1y.csv"

def download():
    if not mt5.initialize():
        print("[ERROR] MT5 Initialization Failed")
        return

    print(f"[INFO] Downloading {DAYS_BACK} days of {SYMBOL} M15 data...")
    
    end_date = dt.datetime.now()
    start_date = end_date - dt.timedelta(days=DAYS_BACK)
    
    rates = mt5.copy_rates_range(SYMBOL, TIMEFRAME, start_date, end_date)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("[ERROR] No data received. Check if symbol exists in Market Watch.")
        return


    df = pd.DataFrame(rates)
    # Rename columns to match MT5 export style for compatibility with our engine
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.strftime('%Y.%m.%d')
    df['time_str'] = df['time'].dt.strftime('%H:%M:%S')
    
    # Final cleanup to match the expected CSV format
    export_df = pd.DataFrame({
        "<DATE>": df['date'],
        "<TIME>": df['time_str'],
        "<OPEN>": df['open'],
        "<HIGH>": df['high'],
        "<LOW>": df['low'],
        "<CLOSE>": df['close'],
        "<TICKVOL>": df['tick_volume'],
        "<VOL>": df['real_volume'],
        "<SPREAD>": df['spread']
    })

    export_df.to_csv(FILENAME, index=False, sep='\t')
    print(f"[SUCCESS] Successfully saved {len(export_df)} bars to {FILENAME}")

if __name__ == "__main__":
    download()
