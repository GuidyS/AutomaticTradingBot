import pandas as pd
import numpy as np
import datetime
import logging
import config

class Backtester:
    def __init__(self, df: pd.DataFrame, spread=0.0, slippage=0.0, max_holding_candles=0, htf_df=None, session_start=6, session_end=18):
        self.df = df
        self.spread = spread
        self.slippage = slippage
        self.max_holding = max_holding_candles
        self.htf_df = htf_df
        self.balance = 1000.0
        self.wins = 0
        self.losses = 0
        self.trade_log = []
        
        # Pre-calculate session mask for performance
        if 'time' in self.df.columns:
            ts_series = self.df['time']
            # Vectorized datetime conversion
            dts = pd.to_datetime(ts_series, unit='s', utc=True)
            times = dts.dt.strftime("%H:%M")
            self.session_mask = pd.Series(False, index=self.df.index)
            for start, end in config.TRADING_SESSIONS:
                self.session_mask |= (times >= start) & (times < end)
        else:
            self.session_mask = pd.Series(True, index=self.df.index)

    def _is_allowed_session(self, idx: int) -> bool:
        return self.session_mask.iloc[idx]

    def _sweep_quality(self, idx: int) -> str | None:
        if idx < config.SWEEP_LOOKBACK: return None
        df = self.df
        prev_high = df['high'].iloc[idx-config.SWEEP_LOOKBACK:idx].max()
        prev_low = df['low'].iloc[idx-config.SWEEP_LOOKBACK:idx].min()
        last = df.iloc[idx]
        range_size = prev_high - prev_low
        if range_size == 0: return None
        
        if last['high'] > prev_high and last['close'] < prev_high:
            if (last['high'] - prev_high) > (range_size * config.SWEEP_STRENGTH_RATIO):
                return "SELL"
        if last['low'] < prev_low and last['close'] > prev_low:
            if (prev_low - last['low']) > (range_size * config.SWEEP_STRENGTH_RATIO):
                return "BUY"
        return None

    def run(self):
        df = self.df
        n = len(df)
        i = 100
        while i < n:
            # 0. ADX Filter
            if df['adx'].iloc[i] < config.ADX_THRESHOLD:
                i += 1
                continue

            # 1. Sweep detection
            direction = self._sweep_quality(i)
            if not direction:
                i += 1
                continue
            
            # 2. HTF Bias (Proxy)
            bias = "UP" if df['close'].iloc[i] > df['close'].rolling(100).mean().iloc[i] else "DOWN"
            if (direction == "BUY" and bias != "UP") or (direction == "SELL" and bias != "DOWN"):
                i += 1
                continue
            
            # 3. Wait for BOS
            bos_found = False
            bos_idx = -1
            if direction == "BUY":
                bos_level = df['high'].iloc[i-config.SWING_LOOKBACK:i].max()
            else:
                bos_level = df['low'].iloc[i-config.SWING_LOOKBACK:i].min()
                
            for k in range(i, min(i + 10, n)): 
                if (direction == "BUY" and df['close'].iloc[k] > bos_level) or \
                   (direction == "SELL" and df['close'].iloc[k] < bos_level):
                    bos_found = True
                    bos_idx = k
                    break
            
            if not bos_found:
                i += 1
                continue

            # 4. Defensive Entry (Retracement)
            entry_idx = -1
            atr_val = df['atr'].iloc[bos_idx]
            retrace_limit = df['close'].iloc[bos_idx] - (1 if direction == "BUY" else -1) * (atr_val * config.ENTRY_RETRACE_ATR)
            
            for m in range(bos_idx, min(bos_idx + 20, n)):
                if (direction == "BUY" and df['low'].iloc[m] <= retrace_limit) or \
                   (direction == "SELL" and df['high'].iloc[m] >= retrace_limit):
                    entry_idx = m
                    break
            
            if entry_idx == -1:
                i = bos_idx + 1
                continue

            if not self._is_allowed_session(entry_idx):
                i = entry_idx + 1
                continue

            # 5. ML Filter
            # Skip ML for now to speed up backtest (can add if model is fast)
            
            # 6. Trade Execution Simulation
            entry_price = retrace_limit
            sl_dist = (atr_val * config.SL_ATR_MULTIPLIER + config.SL_SWIPE_BUFFER)
            sl = entry_price - (1 if direction == "BUY" else -1) * sl_dist
            
            from smc_utils import dynamic_tp
            tps = dynamic_tp(entry_price, 1 if direction == "BUY" else -1, atr_val, base_mult=config.TP_MULTIPLIER)
            
            # 7. Monitoring Trade
            active_lots = 1.0
            total_profit_r = 0.0
            current_sl = sl
            tp_hit_mask = [False] * len(tps)
            be_hit = False
            exit_idx = -1
            
            for j in range(entry_idx + 1, n):
                candle = df.iloc[j]
                curr_r = abs(candle['close'] - entry_price) / sl_dist
                
                # Check Break-even
                if not be_hit and curr_r >= config.BREAK_EVEN_R:
                    be_hit = True
                    current_sl = entry_price
                
                # Check Trailing
                if curr_r >= config.TRAIL_START_R:
                    new_sl = candle['close'] - (1 if direction == "BUY" else -1) * sl_dist * config.TRAIL_DISTANCE_R
                    if direction == "BUY":
                        current_sl = max(current_sl, new_sl)
                    else:
                        current_sl = min(current_sl, new_sl)

                # Check SL
                if (direction == "BUY" and candle['low'] <= current_sl) or \
                   (direction == "SELL" and candle['high'] >= current_sl):
                    total_profit_r += active_lots * ((current_sl - entry_price) / sl_dist if direction == "BUY" else (entry_price - current_sl) / sl_dist)
                    exit_idx = j
                    break
                
                # Check TPs
                for idx_tp, tp_price in enumerate(tps):
                    if not tp_hit_mask[idx_tp]:
                        if (direction == "BUY" and candle['high'] >= tp_price) or \
                           (direction == "SELL" and candle['low'] <= tp_price):
                            tp_hit_mask[idx_tp] = True
                            profit_r = config.TP_LEVELS[idx_tp]
                            gain = config.TP_LOT_SPLIT[idx_tp] * profit_r
                            total_profit_r += gain
                            active_lots -= config.TP_LOT_SPLIT[idx_tp]
                            if active_lots <= 0:
                                exit_idx = j
                                break
                if exit_idx != -1: break
            
            if exit_idx == -1: exit_idx = n - 1
            
            # Stats
            self.balance *= (1 + total_profit_r * config.RISK_PERCENT / 100)
            if total_profit_r > 0: self.wins += 1
            else: self.losses += 1
            
            i = exit_idx + 1
        
        return self.balance

def run_backtest(csv_path: str, *, spread: float = 0.0, slippage: float = 0.0,
                 max_holding: int = 0, htf_csv: str | None = None,
                 session_start: int = 6, session_end: int = 18):
    df = pd.read_csv(csv_path, sep=None, engine='python')
    from smc_utils import apply_all
    df = apply_all(df)
    
    bt = Backtester(df, spread=spread, slippage=slippage,
                    max_holding_candles=max_holding, htf_df=None,
                    session_start=session_start, session_end=session_end)
    result = bt.run()
    print(f"=== Expert v2 Result ===\nFinal Balance: {result:.2f} | Wins: {bt.wins} | Losses: {bt.losses}")
    return result
