import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import MetaTrader5 as mt5
import pandas as pd
import time, requests, re
from math import floor
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import config
import database


# ============================================================
# SelfLearningEA v4 — Anti-Loss Edition
# ============================================================
# ระบบใหม่ที่เพิ่มเข้ามา:
#   [H]  Auto-Hedge       — เปิดไม้ตรงข้ามเมื่อราคาวิ่งสวนถึง trigger
#   [M]  Smart Martingale — เพิ่ม lot ตามทิศที่ถูก (ควบคุม max level)
#   [E]  Entry Filter v2  — 5-layer gate + RR check ก่อนเปิดทุกครั้ง
#   [S]  Structural SL/TP — SL ตาม Swing Low/High, TP ตาม OB หรือ 2.5×ATR
#   [R]  Recovery         — Global basket management + Loss Shaving
# ============================================================

class SelfLearningEA:

    # ----------------------------------------------------------
    # Init
    # ----------------------------------------------------------
    def __init__(self):
        self.usd_news_today = False
        self.last_news_check = ""
        self.last_summary_time = datetime.now() - timedelta(hours=11.9)
        self.last_ai_report_time = {}
        self.ai_in_progress = {}
        self.executor = ThreadPoolExecutor(max_workers=2)

        self.grid_last_open_time  = {}
        self.grid_safety_triggered = {}
        self.symbol_tp_multipliers = {}
        self.last_close_time = {}
        self.acc_scalp_profit = {}
        self.last_log_time = {}

        # [P4] Win-rate tracking
        self.trade_stats = {}

        # [H] Hedge state  {symbol: {'hedge_ticket': int, 'original_ticket': int, 'triggered': bool}}
        self.hedge_state = {}

        # [M] Martingale state  {symbol: {'level': 0, 'direction': None, 'base_lot': 0.01}}
        self.mart_state = {}

        # [V] Virtual SL cache  {ticket: sl_price}
        self.virtual_sl_cache = {}

        # [AI] TP multiplier cache with expiry (30 min)
        self.symbol_tp_multipliers = {}
        self.symbol_tp_multiplier_expire = {}  # {symbol: datetime}

        # Recovery
        self.global_recovery_active = False

    # ----------------------------------------------------------
    # Helpers: logging / stats
    # ----------------------------------------------------------
    def log_throttled(self, msg, symbol=None, throttle_sec=60):
        key = (symbol, msg[:40])
        now = time.time()
        if now - self.last_log_time.get(key, 0) > throttle_sec:
            print(f"\n{msg}")
            self.last_log_time[key] = now

    def _init_stats(self, symbol):
        if symbol not in self.trade_stats:
            self.trade_stats[symbol] = {
                'SCALP': {'wins':0,'losses':0,'gross_profit':0.0,'gross_loss':0.0},
                'GRID':  {'wins':0,'losses':0,'gross_profit':0.0,'gross_loss':0.0},
                'HEDGE': {'wins':0,'losses':0,'gross_profit':0.0,'gross_loss':0.0},
                'MART':  {'wins':0,'losses':0,'gross_profit':0.0,'gross_loss':0.0},
            }

    def _record_trade(self, symbol, trade_type, profit):
        self._init_stats(symbol)
        t = trade_type if trade_type in self.trade_stats[symbol] else 'SCALP'
        s = self.trade_stats[symbol][t]
        if profit >= 0:
            s['wins'] += 1; s['gross_profit'] += profit
        else:
            s['losses'] += 1; s['gross_loss'] += abs(profit)

    def get_stats_summary(self, symbol):
        self._init_stats(symbol)
        lines = [f"📊 *[Stats/{symbol}]*"]
        for t, s in self.trade_stats[symbol].items():
            total = s['wins'] + s['losses']
            if total == 0: lines.append(f"  {t}: ยังไม่มีข้อมูล"); continue
            wr  = s['wins'] / total * 100
            net = s['gross_profit'] - s['gross_loss']
            avg_w = s['gross_profit'] / s['wins']   if s['wins']   > 0 else 0
            avg_l = s['gross_loss']   / s['losses'] if s['losses'] > 0 else 0
            rr    = avg_w / avg_l if avg_l > 0 else 0
            lines.append(f"  {t}: W{s['wins']}/L{s['losses']} | WR:{wr:.1f}% | Net:${net:.2f} | RR:{rr:.2f}")
        return "\n".join(lines)

    # ----------------------------------------------------------
    # MT5 init & model
    # ----------------------------------------------------------
    def init_mt5(self):
        if not mt5.initialize():
            print("MT5 Initialization failed.")
            return False
        ok = mt5.login(config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER)
        if not ok:
            print(f"🔴 MT5 Login Failed: {mt5.last_error()}")
            return False
        print(f"✅ MT5 Connected: {config.MT5_LOGIN}")
        try:
            self.global_recovery_active = database.get_bot_setting("global_recovery_active", False)
        except Exception:
            pass
        return True

    # ----------------------------------------------------------
    # Notifications
    # ----------------------------------------------------------
    def send_line_message(self, msg):
        if not (getattr(config,'LINE_CHANNEL_ACCESS_TOKEN','') and getattr(config,'LINE_USER_ID','')):
            return
        uids = [u.strip() for u in str(config.LINE_USER_ID).split(',') if u.strip()]
        hdr  = {"Content-Type":"application/json","Authorization":f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}"}
        for uid in uids:
            try: requests.post("https://api.line.me/v2/bot/message/push",
                               headers=hdr, json={"to":uid,"messages":[{"type":"text","text":msg}]}, timeout=10)
            except: pass

    def send_telegram_message(self, msg):
        if not (getattr(config,'TELEGRAM_BOT_TOKEN','') and getattr(config,'TELEGRAM_CHAT_ID','')):
            return
        html = re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',msg)
        html = re.sub(r'\*(.*?)\*',   r'<b>\1</b>',html)
        html = re.sub(r'`(.*?)`',     r'<code>\1</code>',html)
        html = html.replace('[','(').replace(']',')')
        try:
            r = requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                              json={"chat_id":config.TELEGRAM_CHAT_ID,"text":html,"parse_mode":"HTML"}, timeout=10)
            if r.status_code != 200:
                print(f"🔴 Telegram: {r.status_code}")
        except: pass

    def notify(self, msg, telegram=True):
        print(f"\n📢 {msg.replace('*','')}")
        self.send_line_message(msg)
        if telegram: self.send_telegram_message(msg)

    def send_performance_report(self):
        stats = database.get_performance_summary(hours=12)
        lines = []
        if stats:
            lines.append(f"📊 *[12h Report]*\n"
                         f"💰 Net: *{stats['net_profit']:.2f}$* | W:{stats['wins']} L:{stats['losses']} | WR:{stats['win_rate']:.1f}%")
        for sym in config.SYMBOLS:
            lines.append(self.get_stats_summary(sym))
        if lines:
            self.notify("\n\n".join(lines)+"\n\n🚀 สรุปทุก 4 ชม.")
            return True
        return False

    # ----------------------------------------------------------
    # Data & Indicators
    # ----------------------------------------------------------
    def check_news_forexfactory(self):
        ds = datetime.now().strftime("%Y-%m-%d")
        if self.last_news_check == ds: return self.usd_news_today
        try:
            r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=5)
            if r.status_code == 200:
                news = [n for n in r.json() if n['country']=='USD' and n['impact']=='High' and ds in n['date']]
                self.usd_news_today = len(news) > 0
                self.last_news_check = ds
        except: pass
        return self.usd_news_today

    def check_time_filter(self):
        h = datetime.now().hour
        return config.TRADE_TIME_START <= h <= config.TRADE_TIME_END

    def get_data(self, symbol, tf, n=200):
        r = mt5.copy_rates_from_pos(symbol, tf, 0, n)
        if r is None or len(r) == 0: return None
        df = pd.DataFrame(r)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def calculate_atr(self, df, period=14):
        hl = df['high'] - df['low']
        hc = (df['high'] - df['close'].shift()).abs()
        lc = (df['low']  - df['close'].shift()).abs()
        return pd.concat([hl,hc,lc],axis=1).max(axis=1).rolling(period).mean()

    def add_indicators(self, df):
        df['ema_14'] = df['close'].ewm(span=14,adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50,adjust=False).mean()
        d = df['close'].diff()
        g = d.where(d>0,0).rolling(14).mean()
        l = (-d.where(d<0,0)).rolling(14).mean()
        df['rsi_14']    = 100-(100/(1+g/l))
        df['atr']       = self.calculate_atr(df)
        df['volatility']= ((df['high']-df['low'])/df['atr']).fillna(1.0)
        e1 = df['close'].ewm(span=12,adjust=False).mean()
        e2 = df['close'].ewm(span=26,adjust=False).mean()
        ml = e1-e2
        df['macd_diff'] = ml - ml.ewm(span=9,adjust=False).mean()
        df['bb_mid']    = df['close'].rolling(20).mean()
        bb_std          = df['close'].rolling(20).std()
        df['bb_upper']  = df['bb_mid'] + bb_std*2
        df['bb_lower']  = df['bb_mid'] - bb_std*2
        vs              = df['tick_volume'].rolling(20).mean()
        df['rel_volume']= df['tick_volume'] / vs.replace(0,1)
        return df

    def get_trend(self, symbol, tf, span=50):
        df = self.get_data(symbol, tf, 100)
        if df is None: return None
        df['ema'] = df['close'].ewm(span=span,adjust=False).mean()
        return 'UP' if df.iloc[-1]['close'] > df.iloc[-1]['ema'] else 'DOWN'

    def get_h4_trend(self, symbol): return self.get_trend(symbol, mt5.TIMEFRAME_H4)
    def get_h1_trend(self, symbol): return self.get_trend(symbol, mt5.TIMEFRAME_H1)
    def get_m30_trend(self, symbol): return self.get_trend(symbol, mt5.TIMEFRAME_M30)

    def get_market_session(self):
        h = datetime.now().hour
        if h < 7:  return "Asian"
        if h < 14: return "London"
        if h < 22: return "NY"
        return "Overlap"

    def get_currency_strength(self, symbol):
        s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        pairs = s_cfg.get('strength_pairs',["EURUSD","GBPUSD","USDJPY","AUDUSD"])
        strengths = {}
        for sym in pairs:
            try:
                mt5.symbol_select(sym, True)
                r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 20)
                if r is not None and len(r) > 1:
                    strengths[sym] = round(float((r[-1][4]-r[0][1])/r[0][1]*100), 6)
                else: strengths[sym] = 0.0
            except: strengths[sym] = 0.0
        usd = 0.0; cnt = 0
        for p,sign in [("EURUSD",-1),("GBPUSD",-1),("AUDUSD",-1),("USDJPY",1)]:
            if p in strengths: usd += sign*strengths[p]; cnt += 1
        usd = usd/cnt if cnt else 0.0
        xau = strengths.get("XAUUSDc", strengths.get("XAUUSD", 0.0))
        return xau, usd

    def check_candlestick_pattern(self, df):
        if len(df) < 2: return "None"
        r = df.iloc[-1]; p = df.iloc[-2]
        body = abs(r['close']-r['open'])
        uw   = r['high']-max(r['close'],r['open'])
        lw   = min(r['close'],r['open'])-r['low']
        if body <= (r['high']-r['low'])*0.1: return "Doji"
        if lw > body*2 and uw < body*0.5:    return "Pinbar_Bull"
        if uw > body*2 and lw < body*0.5:    return "Pinbar_Bear"
        if r['close']>p['open'] and r['open']<p['close'] and r['close']>r['open'] and p['close']<p['open']: return "Engulfing_Bull"
        if r['close']<p['open'] and r['open']>p['close'] and r['close']<r['open'] and p['close']>p['open']: return "Engulfing_Bear"
        return "None"

    # ----------------------------------------------------------
    # SMC
    # ----------------------------------------------------------
    def _is_swing_high(self, df, i, lb=5):
        if i < lb or i >= len(df)-lb: return False
        v = df.iloc[i]['high']
        return all(df.iloc[i-j]['high'] <= v and df.iloc[i+j]['high'] <= v for j in range(1,lb+1))

    def _is_swing_low(self, df, i, lb=5):
        if i < lb or i >= len(df)-lb: return False
        v = df.iloc[i]['low']
        return all(df.iloc[i-j]['low'] >= v and df.iloc[i+j]['low'] >= v for j in range(1,lb+1))

    def find_last_swings(self, df, lb=5):
        sh = sl = -1
        for i in range(len(df)-lb-1, lb, -1):
            if sh==-1 and self._is_swing_high(df,i,lb): sh=i
            if sl==-1 and self._is_swing_low(df,i,lb):  sl=i
            if sh!=-1 and sl!=-1: break
        return sh, sl

    def get_smc_structure(self, symbol, tf=mt5.TIMEFRAME_M30):
        df = self.get_data(symbol, tf, 200)
        if df is None or len(df) < 100: return "NEUTRAL", None, None
        sh_i, sl_i = self.find_last_swings(df)
        if sh_i==-1 or sl_i==-1: return "NEUTRAL", None, None
        lc = df.iloc[-1]['close']
        sh = df.iloc[sh_i]['high']; sl = df.iloc[sl_i]['low']
        bias="NEUTRAL"; ob=(None,None)
        if lc > sh:
            bias = "BULL_BOS"
            for i in range(sh_i,0,-1):
                if df.iloc[i]['close'] < df.iloc[i]['open']:
                    ob=(df.iloc[i]['high'],df.iloc[i]['low']); break
        elif lc < sl:
            bias = "BEAR_BOS"
            for i in range(sl_i,0,-1):
                if df.iloc[i]['close'] > df.iloc[i]['open']:
                    ob=(df.iloc[i]['high'],df.iloc[i]['low']); break
        return bias, ob[0], ob[1]

    def get_m5_market_state(self, symbol):
        df = self.get_data(symbol, mt5.TIMEFRAME_M5, 200)
        if df is None:
            return [],None,None,None,None,None,None,None,None,None,None,None,None,None,None,0,0,0
        df = self.add_indicators(df)
        row = df.iloc[-1]
        signals = []
        if row['close']>row['ema_14'] and row['close']>row['ema_50'] and row['rsi_14']<70: signals.append('BUY')
        if row['close']<row['ema_14'] and row['close']<row['ema_50'] and row['rsi_14']>30: signals.append('SELL')
        ema_dist = ((row['close']-row['ema_50'])/row['ema_50'])*100
        atr_val  = row['atr']
        if pd.isna(atr_val) or pd.isna(row['rsi_14']): 
            return [],50.0,0.0,0.001,"None",1.0,0,0.0,"Middle","None","Equilibrium","Asian",1.0,0.0,0.0,0,0,0
        bb_pos = "Upper" if row['close']>row['bb_upper'] else ("Lower" if row['close']<row['bb_lower'] else "Middle")
        rh = df['high'].rolling(50).max().iloc[-1]; rl = df['low'].rolling(50).min().iloc[-1]
        eq = (rh+rl)/2
        smc_zone = "Premium" if row['close']>eq+(rh-eq)*0.2 else ("Discount" if row['close']<eq-(eq-rl)*0.2 else "Equilibrium")
        smc_fvg = "None"; fvg_entry = 0.0
        for i in range(max(len(df)-15,2), len(df)-1):
            try:
                if df['high'].iloc[i-2]<df['low'].iloc[i]:
                    if not any(df['low'].iloc[j]<=df['high'].iloc[i-2] for j in range(i+1,len(df))):
                        smc_fvg="Bullish"; fvg_entry=df['low'].iloc[i]; break
            except: pass
            try:
                if df['low'].iloc[i-2]>df['high'].iloc[i]:
                    if not any(df['high'].iloc[j]>=df['low'].iloc[i-2] for j in range(i+1,len(df))):
                        smc_fvg="Bearish"; fvg_entry=df['high'].iloc[i]; break
            except: pass
        xau,usd = self.get_currency_strength(symbol)
        b_high = df['high'].rolling(20).max().iloc[-1]
        b_low  = df['low'].rolling(20).min().iloc[-1]
        return (signals, row['rsi_14'], ema_dist, atr_val,
                self.check_candlestick_pattern(df), row['volatility'],
                datetime.now().weekday(), row['macd_diff'], bb_pos,
                smc_fvg, smc_zone, self.get_market_session(),
                row['rel_volume'], xau, usd, fvg_entry, b_high, b_low)

    # ----------------------------------------------------------
    # [S] Structural SL/TP calculation
    # ----------------------------------------------------------
    def calculate_structural_sl_tp(self, symbol, direction, atr_val, entry_price=None):
        """
        คำนวณ SL ตาม Swing Structure และ TP ตาม Order Block หรือ 2.5×ATR (โดยอิงจาก Entry Price ที่ระบุ)
        Returns: (sl_price, tp_price, rr_ratio)
        """
        s_cfg    = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        sym_info = mt5.symbol_info(symbol)
        tick     = mt5.symbol_info_tick(symbol)
        if sym_info is None or tick is None: return None, None, 0.0

        pip = sym_info.point * 10
        entry = entry_price if entry_price is not None else (tick.ask if direction == 'BUY' else tick.bid)

        # --- SL: Swing Low/High + buffer ---
        df_m30 = self.get_data(symbol, mt5.TIMEFRAME_M30, 100)
        sl_price = None
        if df_m30 is not None:
            sh_i, sl_i = self.find_last_swings(df_m30, lb=5)
            buf = s_cfg.get('scalp_struct_offset', 25) * pip
            if direction == 'BUY' and sl_i != -1:
                swing_sl = df_m30.iloc[sl_i]['low'] - buf
                # ใช้ค่าที่ไกลกว่า (ปลอดภัยกว่า) ระหว่าง swing vs ATR
                atr_sl   = entry - atr_val * s_cfg.get('atr_sl_mul', 0.8)
                sl_price = min(swing_sl, atr_sl)
            elif direction == 'SELL' and sh_i != -1:
                swing_sl = df_m30.iloc[sh_i]['high'] + buf
                atr_sl   = entry + atr_val * s_cfg.get('atr_sl_mul', 0.8)
                sl_price = max(swing_sl, atr_sl)

        # Fallback: ATR only
        if sl_price is None:
            sl_dist  = atr_val * s_cfg.get('atr_sl_mul', 0.8)
            sl_price = (entry - sl_dist) if direction == 'BUY' else (entry + sl_dist)

        # --- Safety Floor: minimum SL distance ---
        min_sl = s_cfg.get('scalp_min_sl_pips', 50) * pip
        actual_sl_dist = abs(entry - sl_price)
        if actual_sl_dist < min_sl:
            actual_sl_dist = min_sl
            sl_price = (entry - min_sl) if direction == 'BUY' else (entry + min_sl)

        # --- TP: Order Block หรือ 2.5×ATR ---
        _, ob_high, ob_low = self.get_smc_structure(symbol)
        # Decay multiplier if stale (>30 min)
        if symbol in self.symbol_tp_multiplier_expire:
            if datetime.now() > self.symbol_tp_multiplier_expire[symbol]:
                self.symbol_tp_multipliers.pop(symbol, None)
                self.symbol_tp_multiplier_expire.pop(symbol, None)
        ai_mul = self.symbol_tp_multipliers.get(symbol, 1.0)
        tp_price = None

        if direction == 'BUY' and ob_high and ob_high > entry:
            tp_price = ob_high * 0.998  # ก่อนถึง OB นิดนึง
        elif direction == 'SELL' and ob_low and ob_low < entry:
            tp_price = ob_low  * 1.002

        # Fallback: ATR × multiplier
        if tp_price is None:
            tp_dist  = atr_val * s_cfg.get('atr_tp_mul', 2.5) * ai_mul
            tp_price = (entry + tp_dist) if direction == 'BUY' else (entry - tp_dist)

        # --- Compute RR ---
        tp_dist_actual = abs(tp_price - entry)
        rr = tp_dist_actual / actual_sl_dist if actual_sl_dist > 0 else 0.0

        return sl_price, tp_price, rr

    # ----------------------------------------------------------
    # [E] Entry Filter v2 (5-layer gate)
    # ----------------------------------------------------------
    def _validate_entry(self, symbol, direction, rsi, macd, h4, h1, m30, smc_zone, vol_ok, volatility):
        """
        Returns (is_valid: bool, reason: str)
        Gate 0: Recovery mode block
        Gate 1: H4 mega-trend
        Gate 2: Volume + Volatility
        Gate 3: RSI + MACD window
        Gate 4: MTF alignment (M30 + H1)
        Gate 5: SMC zone
        """
        if self.global_recovery_active:
            return False, "Global Recovery active"
        # Gate 1
        if direction == 'BUY'  and h4 == 'DOWN': return False, "H4 Bearish"
        if direction == 'SELL' and h4 == 'UP':   return False, "H4 Bullish"
        # Gate 2
        if not vol_ok:      return False, "Volume ต่ำ"
        if volatility > 2.5: return False, f"Volatility {volatility:.1f} > 2.5"
        # Gate 3
        rsi_ok_buy  = config.SCALP_BUY_RSI_MIN  <= rsi <= config.SCALP_BUY_RSI_MAX
        rsi_ok_sell = config.SCALP_SELL_RSI_MIN <= rsi <= config.SCALP_SELL_RSI_MAX
        if direction == 'BUY':
            if not rsi_ok_buy:  return False, f"RSI {rsi:.1f} นอกช่วง BUY"
            if macd <= 0:       return False, "MACD ≤ 0"
        else:
            if not rsi_ok_sell: return False, f"RSI {rsi:.1f} นอกช่วง SELL"
            if macd >= 0:       return False, "MACD ≥ 0"
        # Gate 4
        if getattr(config,'SCALP_REQUIRE_H1_CONFIRM',True):
            if direction == 'BUY'  and h1  != 'UP':   return False, f"H1={h1}"
            if direction == 'SELL' and h1  != 'DOWN':  return False, f"H1={h1}"
        if direction == 'BUY'  and m30 != 'UP':   return False, f"M30={m30}"
        if direction == 'SELL' and m30 != 'DOWN':  return False, f"M30={m30}"
        # Gate 5
        if getattr(config,'SCALP_REQUIRE_SMC_ZONE',False):
            if direction == 'BUY'  and smc_zone != 'Discount': return False, f"Zone={smc_zone}"
            if direction == 'SELL' and smc_zone != 'Premium':  return False, f"Zone={smc_zone}"
        return True, "ผ่าน"

    # ----------------------------------------------------------
    # Lot calculation
    # ----------------------------------------------------------
    def calculate_lot(self, symbol, sl_dist=None, risk_pct=None):
        acc = mt5.account_info()
        if not acc: return config.FIXED_LOT
        if config.RISK_MODE == "FIXED": return config.FIXED_LOT

        balance    = acc.balance
        r_pct      = risk_pct if risk_pct is not None else config.RISK_PERCENT
        risk_amt   = balance * (r_pct / 100.0)
        sym_info   = mt5.symbol_info(symbol)
        if sym_info is None: return config.FIXED_LOT

        dist = sl_dist
        if dist is None or dist <= 0:
            dist = 300 * sym_info.point * 10
        ts = sym_info.trade_tick_size
        tv = sym_info.trade_tick_value
        if ts > 0 and tv > 0:
            # 🛡️ Safety Check: ป้องกันระยะ SL แคบเกินไปจนทำให้ Lot ระเบิด (ขั้นต่ำ 2 pips มูลค่า)
            pip = sym_info.point * 10
            safe_dist = max(dist, 2 * pip)
            
            lot = risk_amt / ((safe_dist/ts) * tv)
            lot = round(lot / sym_info.volume_step) * sym_info.volume_step
            
            # 🔥 [MAX LOT] ด่านสุดท้ายป้องกันความเสี่ยงเกินขนาด
            max_l = getattr(config, 'MAX_LOT', 0.5)
            lot   = min(lot, max_l)
            
            return max(sym_info.volume_min, min(lot, sym_info.volume_max))
        return config.FIXED_LOT

    # ----------------------------------------------------------
    # Trade helpers
    # ----------------------------------------------------------
    def count_open_orders(self, symbol, magic=None):
        pos = mt5.positions_get(symbol=symbol)
        if not pos: return 0
        m = magic or config.MAGIC_NUMBER
        return sum(1 for p in pos if p.magic == m)

    def count_pending_orders(self, symbol):
        o = mt5.orders_get(symbol=symbol)
        if not o: return 0
        return sum(1 for x in o if x.magic == config.MAGIC_NUMBER)

    def get_symbol_pip(self, symbol):
        si = mt5.symbol_info(symbol)
        return si.point * 10 if si else 0.0001

    def check_trade_safety(self, symbol, direction, price, is_scalp=False):
        """Anti-hedging + spacing check"""
        pip  = self.get_symbol_pip(symbol)
        s_cfg= config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        min_d= s_cfg.get('min_scalp_spacing',50) * pip
        magics = [config.MAGIC_NUMBER, config.GRID_MAGIC_NUMBER]

        pos = mt5.positions_get(symbol=symbol) or []
        for p in pos:
            if p.magic in magics:
                ed = 'BUY' if p.type==mt5.ORDER_TYPE_BUY else 'SELL'
                if ed != direction and not is_scalp:
                    self.log_throttled(f"⚠️ [{symbol}] สวนทาง {ed}", symbol)
                    return False
                if abs(p.price_open - price) < min_d:
                    self.log_throttled(f"⚠️ [{symbol}] ใกล้ไม้เดิมเกินไป", symbol)
                    return False
        orders = mt5.orders_get(symbol=symbol) or []
        for o in orders:
            if o.magic in magics:
                od = 'BUY' if o.type in [mt5.ORDER_TYPE_BUY_LIMIT,mt5.ORDER_TYPE_BUY_STOP] else 'SELL'
                if od != direction and not is_scalp:
                    return False
                if abs(o.price_open - price) < min_d:
                    return False
        return True

    def _send_order(self, symbol, direction, lot, sl, tp, magic, comment,
                    pending_type=None, pending_price=0.0, expiry_hours=4):
        """Low-level order sender — returns ticket or None"""
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return None
        price = pending_price if pending_type else (tick.ask if direction=='BUY' else tick.bid)
        otype = pending_type if pending_type else (mt5.ORDER_TYPE_BUY if direction=='BUY' else mt5.ORDER_TYPE_SELL)

        req = {
            "action":   mt5.TRADE_ACTION_PENDING if pending_type else mt5.TRADE_ACTION_DEAL,
            "symbol":   symbol, "volume": lot, "type": otype, "price": float(price),
            "sl": float(sl), "tp": float(tp), "deviation": 30,
            "magic": magic, "comment": comment,
            "type_time":    mt5.ORDER_TIME_SPECIFIED if pending_type else mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK if not pending_type else mt5.ORDER_FILLING_RETURN,
        }
        if pending_type:
            req["expiration"] = int(time.time() + expiry_hours*3600)
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            return res.order
        print(f"🔴 [{symbol}] Order fail: {res.retcode if res else 'None'} | {mt5.last_error()}")
        return None

    def execute_trade(self, symbol, direction, atr_val, order_index=1, pending_type=None, pending_price=0.0):
        """Main scalp order entry with structural SL/TP and RR gate"""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None: return None

        check_p = pending_price if pending_type else (tick.ask if direction=='BUY' else tick.bid)
        if not self.check_trade_safety(symbol, direction, check_p, is_scalp=True):
            return None

        sl, tp, rr = self.calculate_structural_sl_tp(symbol, direction, atr_val, entry_price=check_p)
        if sl is None: return None

        # [E] RR gate — must be ≥ configured minimum
        min_rr = getattr(config, 'MIN_RR_RATIO', 1.5)
        if rr < min_rr:
            self.log_throttled(f"⚠️ [{symbol}] RR={rr:.2f} < {min_rr} → ข้าม", symbol, throttle_sec=120)
            return None

        sl_dist = abs((pending_price if pending_type else check_p) - sl)
        lot     = self.calculate_lot(symbol, sl_dist=sl_dist)
        comment = f"{config.ORDER_COMMENT}_{direction[0]}#{order_index}"

        ticket = self._send_order(symbol, direction, lot, sl, tp,
                                  config.MAGIC_NUMBER, comment, pending_type, pending_price)
        if ticket:
            s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
            self.notify(f"🟢 *[{symbol}] {direction}* #{order_index}/{s_cfg.get('max_scalp_orders',2)}\n"
                        f"Lot:{lot} | SL:{sl:.2f} | TP:{tp:.2f} | RR:{rr:.2f}")
        return ticket

    # ----------------------------------------------------------
    # [H] Auto-Hedge System
    # ----------------------------------------------------------
    def check_and_trigger_hedge(self, symbol, position, atr_val):
        """
        เมื่อราคาวิ่งสวนทาง trigger_pips → เปิดไม้ตรงข้ามขนาด lot เท่ากัน
        ปิดทั้งคู่เมื่อกำไรรวม ≥ hedge_tp_usd
        """
        s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        pip   = self.get_symbol_pip(symbol)
        trigger_pips = s_cfg.get('hedge_trigger_pips', 80)
        hedge_tp_usd = s_cfg.get('hedge_basket_tp',    2.0)

        tick = mt5.symbol_info_tick(symbol)
        if not tick: return

        hs = self.hedge_state.get(symbol, {})
        orig_ticket = position.ticket

        # ตรวจสอบว่าไม้นี้มี hedge อยู่แล้วหรือไม่
        if hs.get('original_ticket') == orig_ticket and hs.get('hedge_ticket'):
            # Hedge เปิดอยู่แล้ว → เช็ค basket profit
            pos_all = mt5.positions_get(symbol=symbol) or []
            tickets = {orig_ticket, hs['hedge_ticket']}
            basket  = [p for p in pos_all if p.ticket in tickets]
            total_p = sum(p.profit + p.swap for p in basket)

            # Hedge basket close — atomic: verify each close succeeds before the next
            if total_p >= hedge_tp_usd and len(basket) > 0:
                self.notify(f"🎯 *[HEDGE/{symbol}] Basket TP ${total_p:.2f}!* ปิดทั้งคู่...")
                closed_tickets = []
                failed = []
                for pos in basket:
                    close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
                    close_dir   = 'SELL' if pos.type == mt5.ORDER_TYPE_BUY else 'BUY'
                    ticket = self._send_order(symbol, close_dir, pos.volume, 0, 0,
                                              pos.magic, "HEDGE_BASKET_TP",
                                              pending_price=close_price)
                    if ticket:
                        closed_tickets.append(ticket)
                    else:
                        failed.append(pos.ticket)
                if failed:
                    print(f"⚠️ [HEDGE/{symbol}] Partially closed — failed tickets: {failed}")
                else:
                    self.notify(f"✅ *[HEDGE/{symbol}] ปิดครบ {len(basket)} ไม้ สำเร็จ")
                self.hedge_state.pop(symbol, None)
            return

        # ยังไม่มี hedge → เช็ค trigger
        direction = 'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'
        if direction == 'BUY':
            adverse_dist = (position.price_open - tick.bid) / pip
        else:
            adverse_dist = (tick.ask - position.price_open) / pip

        if adverse_dist < trigger_pips:
            return  # ยังไม่ถึง trigger

        # Trigger! เปิด hedge ตรงข้าม
        hedge_dir = 'SELL' if direction == 'BUY' else 'BUY'
        hedge_sl  = 0.0  # ไม่ตั้ง SL ให้ hedge ไม้ — ควบคุมด้วย basket TP แทน
        hedge_tp  = 0.0

        # คำนวณ TP ของ hedge ให้อยู่ที่ entry ของไม้เดิม ± buffer
        # BUY hedge TP below entry (price must retrace below to hit TP)
        # SELL hedge TP above entry (price must retrace above to hit TP)
        buffer = 1 * pip
        hedge_tp = position.price_open - buffer if hedge_dir == 'BUY' else position.price_open + buffer

        hedge_ticket = self._send_order(symbol, hedge_dir, position.volume,
                                        hedge_sl if hedge_sl > 0 else 0.00001,
                                        hedge_tp if hedge_tp > 0 else 0.00001,
                                        config.MAGIC_NUMBER, "AUTO_HEDGE")
        if hedge_ticket:
            self.hedge_state[symbol] = {
                'original_ticket': orig_ticket,
                'hedge_ticket':    hedge_ticket,
            }
            self.notify(f"🛡️ *[HEDGE/{symbol}] เปิด {hedge_dir} lot:{position.volume}*\n"
                        f"ราคาสวน {adverse_dist:.0f} pips — Hedge TP ที่ {hedge_tp:.2f}")

    # ----------------------------------------------------------
    # [M] Smart Martingale
    # ----------------------------------------------------------
    def smart_martingale(self, symbol, losing_direction, atr_val):
        """
        เมื่อ SL โดน → เปิดไม้ใหม่ทิศเดิมด้วย lot เพิ่มขึ้น ×MART_LOT_MULTIPLIER
        จำกัด max level ด้วย MART_MAX_LEVEL
        ต้องผ่าน Entry Filter ก่อนเสมอ
        """
        if not getattr(config, 'ENABLE_MARTINGALE', False):
            return
        s_cfg   = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        max_lvl = getattr(config, 'MART_MAX_LEVEL', 3)
        mult    = getattr(config, 'MART_LOT_MULTIPLIER', 1.5)

        ms = self.mart_state.get(symbol, {'level':0,'direction':None,'base_lot':config.FIXED_LOT})

        # Reset ถ้าทิศเปลี่ยน
        if ms['direction'] and ms['direction'] != losing_direction:
            self.mart_state[symbol] = {'level':0,'direction':None,'base_lot':config.FIXED_LOT}
            ms = self.mart_state[symbol]

        if ms['level'] >= max_lvl:
            self.notify(f"⚠️ *[MART/{symbol}] ถึง Max Level {max_lvl}* — หยุด Martingale รอบนี้")
            self.mart_state.pop(symbol, None)
            return

        # ตรวจ Entry Filter ก่อนเสมอ (ป้องกันเปิดสวนตลาด)
        h4  = self.get_h4_trend(symbol)
        h1  = self.get_h1_trend(symbol)
        m30 = self.get_m30_trend(symbol)
        m5d = self.get_m5_market_state(symbol)
        _, rsi, _, _, _, vol, _, macd, _, _, zone, _, rel_vol, _, _, _, _, _ = m5d
        vol_ok = rel_vol > 1.1 if rel_vol else False

        valid, reason = self._validate_entry(symbol, losing_direction, rsi, macd, h4, h1, m30, zone, vol_ok,
                                             vol if vol else 1.0)
        if not valid:
            self.log_throttled(f"🔄 [{symbol}] Martingale ข้าม: Entry ไม่ผ่าน ({reason})", symbol)
            return

        new_level = ms['level'] + 1
        new_lot   = round(ms['base_lot'] * (mult ** new_level), 2)
        # Hard cap: ไม่เกิน 2% ของ Balance
        acc = mt5.account_info()
        if acc:
            max_lot_by_risk = self.calculate_lot(symbol, sl_dist=atr_val*0.8, risk_pct=2.0)
            new_lot = min(new_lot, max_lot_by_risk)

        sl, tp, rr = self.calculate_structural_sl_tp(symbol, losing_direction, atr_val)
        if sl is None: return
        if rr < getattr(config,'MIN_RR_RATIO',1.2):
            self.log_throttled(f"🔄 [{symbol}] Martingale ข้าม: RR={rr:.2f}", symbol)
            return

        sl_dist = abs((mt5.symbol_info_tick(symbol).ask if losing_direction=='BUY' else mt5.symbol_info_tick(symbol).bid) - sl)
        ticket  = self._send_order(symbol, losing_direction, new_lot, sl, tp,
                                   config.MAGIC_NUMBER, f"MART_L{new_level}")
        if ticket:
            self.mart_state[symbol] = {'level':new_level,'direction':losing_direction,'base_lot':ms['base_lot']}
            self.notify(f"🔄 *[MART/{symbol}] Level {new_level}/{max_lvl}*\n"
                        f"Lot: {new_lot} | RR: {rr:.2f} | SL:{sl:.2f} | TP:{tp:.2f}")
            self._record_trade(symbol, 'MART', 0)
        else:
            self.log_throttled(f"⚠️ [{symbol}] Martingale order failed", symbol)

    # ----------------------------------------------------------
    # Trailing stop / Break-Even
    # ----------------------------------------------------------
    def manage_trailing_stop(self, symbol, pos, atr_val):
        try:
            tick = mt5.symbol_info_tick(symbol)
            if not tick: return
            s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
            pip   = self.get_symbol_pip(symbol)
            be_d  = s_cfg.get('be_activation_pips',80)*pip
            be_o  = s_cfg.get('be_offset_pips',10)*pip
            act   = atr_val * s_cfg.get('trail_activation',1.2)
            step  = atr_val * s_cfg.get('trail_step',0.5)
            new_sl = None

            if pos.type == mt5.ORDER_TYPE_BUY:
                pd_ = tick.bid - pos.price_open
                # Break-even: lock in once price moved be_d in our favour
                if pd_ >= be_d:
                    new_sl = pos.price_open + be_o
                # Trailing: move SL up as price continues to climb
                elif pd_ >= act:
                    ts = tick.bid - step
                    if ts > (pos.sl or 0) and ts > pos.price_open:
                        new_sl = ts
            else:
                pd_ = pos.price_open - tick.ask
                # Break-even: lock in once price moved be_d in our favour
                if pd_ >= be_d:
                    new_sl = pos.price_open - be_o
                # Trailing: move SL down as price continues to fall
                elif pd_ >= act:
                    ts = tick.ask + step
                    if ts < (pos.sl or float('inf')) and ts < pos.price_open:
                        new_sl = ts

            if new_sl and new_sl != pos.sl:
                mt5.order_send({"action":mt5.TRADE_ACTION_SLTP,"position":pos.ticket,
                                "symbol":symbol,"sl":float(new_sl),"tp":float(pos.tp)})
        except Exception as e:
            if "position" not in str(e).lower(): print(f"⚠️ TrailStop: {e}")

    # ----------------------------------------------------------
    # Grid
    # ----------------------------------------------------------
    def get_grid_positions(self, symbol):
        bp=[]; sp=[]; fl=0.0
        for p in (mt5.positions_get(symbol=symbol) or []):
            if p.magic == config.GRID_MAGIC_NUMBER:
                fl += p.profit + p.swap + getattr(p,'commission',0.0)
                (bp if p.type==mt5.ORDER_TYPE_BUY else sp).append(p.price_open)
        return bp, sp, fl

    def detect_grid_mode(self, symbol):
        h4=self.get_h4_trend(symbol); h1=self.get_h1_trend(symbol)
        if h4=='UP'   and h1=='UP':   return 'LONG_ONLY',  'H4↑H1↑'
        if h4=='DOWN' and h1=='DOWN': return 'SHORT_ONLY', 'H4↓H1↓'
        return 'SYMMETRIC', f'H4{h4} H1{h1}'

    def close_all_grid_positions(self, symbol):
        closed = 0
        for pos in (mt5.positions_get(symbol=symbol) or []):
            if pos.magic != config.GRID_MAGIC_NUMBER: continue
            tick = mt5.symbol_info_tick(symbol)
            if not tick: continue
            ot = mt5.ORDER_TYPE_SELL if pos.type==mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            pr = tick.bid if pos.type==mt5.ORDER_TYPE_BUY else tick.ask
            res= mt5.order_send({"action":mt5.TRADE_ACTION_DEAL,"symbol":symbol,
                                 "volume":pos.volume,"type":ot,"position":pos.ticket,
                                 "price":pr,"deviation":30,"magic":config.GRID_MAGIC_NUMBER,
                                 "comment":"GRID_EXIT","type_time":mt5.ORDER_TIME_GTC,
                                 "type_filling":mt5.ORDER_FILLING_FOK})
            if res and res.retcode==mt5.TRADE_RETCODE_DONE: closed+=1
        if closed: self.notify(f"🛑 *[GRID/{symbol}]* ปิด {closed} ออเดอร์")
        self.grid_safety_triggered[symbol] = True

    def run_grid(self, symbol, atr_val=None):
        if not getattr(config,'ENABLE_GRID',False) or symbol not in config.SYMBOLS: return
        try:
            tick=mt5.symbol_info_tick(symbol); si=mt5.symbol_info(symbol)
            if not tick or not si: return
            pip  = si.point*10
            s_cfg= config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
            spacing = max(atr_val * s_cfg.get('grid_atr_multiplier',1.0),
                         s_cfg.get('grid_min_spacing_pips',50)*pip) if atr_val else s_cfg.get('grid_spacing_pips',100)*pip
            mode,reason = self.detect_grid_mode(symbol) if getattr(config,'GRID_MODE','AUTO')=='AUTO' else (getattr(config,'GRID_MODE','SYMMETRIC'),f'Manual')
            bp,sp,fl = self.get_grid_positions(symbol)
            basket_tp = s_cfg.get('grid_basket_tp', 4.0)
            basket_sl = s_cfg.get('grid_basket_sl',-8.0)
            total = len(bp)+len(sp)

            if total > 0:
                if fl >= basket_tp:
                    self.notify(f"🎯 *[GRID/{symbol}] Basket TP +${fl:.2f}!*"); self.close_all_grid_positions(symbol)
                    self.grid_safety_triggered[symbol]=False; return
                if fl <= s_cfg.get('grid_max_loss',-50.0):
                    print(f"\n🛑 [GRID/{symbol}] Safety Stop ${fl:.2f}"); self.close_all_grid_positions(symbol); return

            if total==0 and self.grid_safety_triggered.get(symbol):
                self.grid_safety_triggered[symbol]=False
            if self.grid_safety_triggered.get(symbol): return

            max_lvl = s_cfg.get('grid_symmetric_max_levels',2) if mode=='SYMMETRIC' else s_cfg.get('grid_max_levels',3)
            cd_ok   = not self.grid_last_open_time.get(symbol) or \
                      (datetime.now()-self.grid_last_open_time[symbol]).total_seconds()>=60
            cur     = (tick.ask+tick.bid)/2.0

            for dir_, prices in [('BUY',bp),('SELL',sp)]:
                need = (mode in ('SYMMETRIC','LONG_ONLY') and dir_=='BUY') or \
                       (mode in ('SYMMETRIC','SHORT_ONLY') and dir_=='SELL')
                if not need or not cd_ok or len(prices)>=max_lvl: continue
                if any(abs(p-cur)<spacing*0.6 for p in prices): continue
                lot    = s_cfg.get('grid_lot',0.01)
                tp_d   = s_cfg.get('grid_tp_pips',500)*pip
                sl_d   = s_cfg.get('grid_sl_pips',300)*pip
                pr     = tick.ask if dir_=='BUY' else tick.bid
                tp     = pr+tp_d if dir_=='BUY' else pr-tp_d
                sl     = pr-sl_d if dir_=='BUY' else pr+sl_d
                ticket = self._send_order(symbol, dir_, lot, sl, tp, config.GRID_MAGIC_NUMBER,
                                          f"GRID_{dir_[0]}#{len(prices)+1}")
                if ticket:
                    prices.append(cur); self.grid_last_open_time[symbol]=datetime.now()
                    self.notify(f"🟩 *[GRID/{symbol}] {dir_} L{len(prices)}*\n"
                                f"Lot:{lot} | SL:{sl:.2f} | TP:{tp:.2f}")

            print(f"\r📊 [GRID/{symbol}] {mode}({reason}) B:{len(bp)} S:{len(sp)} F:${fl:.2f}"
                  f" TP:${basket_tp:.1f} SL:${basket_sl:.1f}     ", end="", flush=True)
        except Exception as e:
            print(f"⚠️ [GRID/{symbol}] {e}")

    # ----------------------------------------------------------
    # Pending orders
    # ----------------------------------------------------------
    def place_pending_orders(self, symbol, signals, atr_val, fvg_type, fvg_entry, b_high, b_low):
        if not getattr(config,'ENABLE_PENDING_ORDERS',False): return
        s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        open_c= self.count_open_orders(symbol)
        pend_c= self.count_pending_orders(symbol)
        max_t = s_cfg.get('max_scalp_orders',2)
        max_p = getattr(config,'MAX_PENDING_PER_SYMBOL',2)
        if open_c+pend_c >= max_t or pend_c >= max_p: return
        tick = mt5.symbol_info_tick(symbol); si = mt5.symbol_info(symbol)
        if not tick or not si: return
        pip  = si.point*10
        d_p  = getattr(config,'BREAKOUT_DISTANCE_PIPS',30)

        def near(price):
            for p in (mt5.positions_get(symbol=symbol) or []):
                if p.magic==config.MAGIC_NUMBER and abs(p.price_open-price)<15*pip: return True
            for o in (mt5.orders_get(symbol=symbol) or []):
                if o.magic==config.MAGIC_NUMBER and abs(o.price_open-price)<15*pip: return True
            return False

        if fvg_entry>0 and not near(fvg_entry):
            if   fvg_type=="Bullish" and fvg_entry<tick.ask:
                self.execute_trade(symbol,'BUY',atr_val,order_index=91,
                                   pending_type=mt5.ORDER_TYPE_BUY_LIMIT,pending_price=fvg_entry)
            elif fvg_type=="Bearish" and fvg_entry>tick.bid:
                self.execute_trade(symbol,'SELL',atr_val,order_index=91,
                                   pending_type=mt5.ORDER_TYPE_SELL_LIMIT,pending_price=fvg_entry)

        if self.count_open_orders(symbol)+self.count_pending_orders(symbol) < max_t:
            if 'BUY' in signals:
                p = b_high + d_p*pip
                if p>tick.ask and not near(p):
                    self.execute_trade(symbol,'BUY',atr_val,order_index=92,
                                       pending_type=mt5.ORDER_TYPE_BUY_STOP,pending_price=p)
            elif 'SELL' in signals:
                p = b_low - d_p*pip
                if p<tick.bid and not near(p):
                    self.execute_trade(symbol,'SELL',atr_val,order_index=92,
                                       pending_type=mt5.ORDER_TYPE_SELL_STOP,pending_price=p)

    # ----------------------------------------------------------
    # DB / Notifications
    # ----------------------------------------------------------
    def check_and_update_db(self, symbol):
        try:
            history = mt5.history_deals_get(datetime.now()-timedelta(days=2),
                                            datetime.now()+timedelta(days=1))
            if not history: return
            scalp_m = config.MAGIC_NUMBER; grid_m = config.GRID_MAGIC_NUMBER
            new_deals = [d for d in history
                         if d.symbol==symbol and d.magic in (scalp_m,grid_m)
                         and d.entry==mt5.DEAL_ENTRY_OUT
                         and not database.is_deal_notified(d.ticket)]
            if not new_deals: return

            groups = {}
            for d in new_deals:
                key = (d.magic, "WIN 🏆" if d.profit>=0 else "LOSS 📉")
                groups.setdefault(key,[]).append(d)

            for (magic, res_str), deals in groups.items():
                trade_type = "GRID" if magic==grid_m else "SCALP"
                total_p    = sum(d.profit for d in deals)
                active     = mt5.positions_get(symbol=symbol) or []
                rem        = sum(1 for p in active if p.magic==magic)
                msg = (f"*{res_str} [{symbol}] {trade_type} ปิดแล้ว!*\n"
                       f"ปิด {len(deals)}/{len(deals)+rem} ไม้ | Net: *{total_p:.2f}$*")
                self.notify(msg)
                for d in deals:
                    database.mark_deal_as_notified(d.ticket)
                    database.update_pending_trades(d.position_id, d.profit,
                                                   "WIN" if d.profit>=0 else "LOSS")
                    self.last_close_time[symbol] = datetime.now()
                    self._record_trade(symbol, trade_type, d.profit)

                    # [M] Trigger Martingale on SL hit
                    if d.profit < 0 and magic == scalp_m:
                        pos_hist = mt5.history_orders_get(ticket=d.order)
                        if pos_hist:
                            dir_ = 'BUY' if pos_hist[0].type in [mt5.ORDER_TYPE_BUY] else 'SELL'
                            # ดึง ATR ปัจจุบัน
                            df_m5 = self.get_data(symbol, mt5.TIMEFRAME_M5, 50)
                            if df_m5 is not None:
                                df_m5 = self.add_indicators(df_m5)
                                atr_now = df_m5.iloc[-1]['atr']
                                self.smart_martingale(symbol, dir_, atr_now)

                    # Loss Shaving
                    if getattr(config,'ENABLE_LOSS_SHAVING',False) and d.profit>0 and magic==scalp_m:
                        self.acc_scalp_profit[symbol] = self.acc_scalp_profit.get(symbol,0.0) + d.profit
                        self.shave_losing_positions(symbol)
        except Exception as e:
            print(f"⚠️ check_db [{symbol}]: {e}")

    # ----------------------------------------------------------
    # Recovery & Shaving
    # ----------------------------------------------------------
    def get_managed_positions(self, symbol):
        pos = mt5.positions_get(symbol=symbol) or []
        managed = [p for p in pos if p.magic in (config.MAGIC_NUMBER, config.GRID_MAGIC_NUMBER)]
        total   = sum(p.profit+p.swap+getattr(p,'commission',0.0) for p in managed)
        return managed, total

    def run_global_recovery_exit(self):
        if not self.global_recovery_active: return False
        total_p=0.0; all_pos=[]
        for sym in config.SYMBOLS:
            mp, p = self.get_managed_positions(sym)
            total_p += p; all_pos.extend((sym,pos) for pos in mp)
        target = getattr(config,'RECOVERY_EXIT_PROFIT',0.50)
        print(f"\r🛠️ [RECOVERY] Total:${total_p:.2f} / Target:${target:.2f} ({len(all_pos)} pos)     ",
              end="",flush=True)
        if total_p >= target:
            self.notify(f"🛠️ *[RECOVERY] เป้าหมาย ${total_p:.2f}!* ปิด {len(all_pos)} ไม้...")
            for sym,pos in all_pos:
                tick = mt5.symbol_info_tick(sym)
                if not tick: continue
                ot = mt5.ORDER_TYPE_SELL if pos.type==mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                pr = tick.bid if pos.type==mt5.ORDER_TYPE_BUY else tick.ask
                mt5.order_send({"action":mt5.TRADE_ACTION_DEAL,"symbol":sym,
                                "volume":pos.volume,"type":ot,"position":pos.ticket,
                                "price":pr,"deviation":30,"magic":pos.magic,
                                "comment":"GLOBAL_RECOVERY_EXIT",
                                "type_time":mt5.ORDER_TIME_GTC,"type_filling":mt5.ORDER_FILLING_FOK})
            self.global_recovery_active = False
            try: database.set_bot_setting("global_recovery_active", False)
            except: pass
            return True
        return False

    def shave_losing_positions(self, symbol):
        if not getattr(config,'ENABLE_LOSS_SHAVING',False): return
        acc = self.acc_scalp_profit.get(symbol,0.0)
        if acc < getattr(config,'MIN_PROFIT_TO_SHAVE',1.0): return
        mp,_ = self.get_managed_positions(symbol)
        losing = sorted([p for p in mp if p.profit<0], key=lambda x:(x.profit,x.time))
        if not losing: return
        tp = losing[0]
        vol= floor((acc/abs(tp.profit))*tp.volume*100)/100.0
        if vol < 0.01: return
        vol = min(vol, tp.volume)
        tick= mt5.symbol_info_tick(symbol)
        if not tick: return

        # MT5 partial close: close the full position, then reopen the remainder.
        # TRADE_ACTION_DEAL + position=N with reduced vol is NOT reliably a
        # partial close on all brokers — close full, reopen remainder instead.
        remaining = tp.volume - vol
        close_ot  = mt5.ORDER_TYPE_SELL if tp.type==mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        close_pr  = tick.bid if tp.type==mt5.ORDER_TYPE_BUY else tick.ask
        res = mt5.order_send({"action":mt5.TRADE_ACTION_DEAL,"symbol":symbol,
                              "volume":tp.volume,"type":close_ot,"position":tp.ticket,
                              "price":close_pr,"deviation":20,"magic":tp.magic,
                              "comment":"LOSS_SHAVING","type_time":mt5.ORDER_TIME_GTC,
                              "type_filling":mt5.ORDER_FILLING_FOK})
        if res and res.retcode==mt5.TRADE_RETCODE_DONE:
            # Cost = portion of the shaved volume relative to full position
            cost = (vol / tp.volume) * abs(tp.profit)
            self.acc_scalp_profit[symbol] -= cost
            # Reopen remainder if any
            if remaining >= 0.01:
                s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
                reopen_dir = 'BUY' if close_ot == mt5.ORDER_TYPE_SELL else 'SELL'
                atr_val = 0.0
                df = self.get_data(symbol, mt5.TIMEFRAME_M5, 50)
                if df is not None:
                    df = self.add_indicators(df)
                    atr_val = df.iloc[-1]['atr']
                sl, tp_new, rr = self.calculate_structural_sl_tp(symbol, reopen_dir, atr_val)
                self._send_order(symbol, reopen_dir, remaining, sl or 0, tp_new or 0,
                                 tp.magic, "LOSS_SHAVE_REMAIN")
            self.notify(f"✂️ *[SHAVER/{symbol}]* Shaved {vol}lot → -${cost:.2f}{' | Reopened ' + f'{remaining}lot' if remaining >= 0.01 else ''}")

    # ----------------------------------------------------------
    # AI Analysis
    # ----------------------------------------------------------
    def get_ai_market_analysis(self, symbol, ctx):
        try:
            prompt = (f"วิเคราะห์ {symbol}: ราคา={ctx['price']:.2f}, RSI={ctx['rsi']:.1f}, "
                      f"MACD={ctx['macd']:.4f}, Trend={ctx['trend']}, Profit=${ctx['profit']:.2f}, "
                      f"Session={ctx['session']}\n"
                      f"สรุปสั้น 2-3 บรรทัด และใส่ [TP_BIAS: AGGRESSIVE|NORMAL|CONSERVATIVE] ท้ายสุด")
            r = requests.post("http://localhost:11434/api/generate",
                              json={"model":"gemma4:latest","prompt":prompt,"stream":False,
                                    "options":{"num_predict":200,"temperature":0.5}}, timeout=300)
            if r.status_code == 200:
                text = r.json().get('response','')
                mul  = 1.8 if "AGGRESSIVE" in text else (0.7 if "CONSERVATIVE" in text else 1.2)
                self.symbol_tp_multipliers[symbol] = mul
                self.symbol_tp_multiplier_expire[symbol] = datetime.now() + timedelta(minutes=30)
                return text
        except Exception as e:
            return f"AI Error: {e}"
        return "AI ไม่ตอบสนอง"

    def _run_ai_bg(self, symbol, ctx):
        try:
            self.ai_in_progress[symbol] = True
            text = self.get_ai_market_analysis(symbol, ctx)
            self.notify(f"🤖 *[AI/{symbol}]*\n{text}", telegram=False)
        except Exception as e:
            print(f"⚠️ AI bg error: {e}")
        finally:
            self.ai_in_progress[symbol] = False

    # ----------------------------------------------------------
    # Main loop
    # ----------------------------------------------------------
    def run(self):
        if not self.init_mt5(): return
        database.setup_db()
        self.notify(f"🚀 *[EA v4 Online]*\nSymbol:{config.SYMBOLS} | Risk:{config.RISK_PERCENT}% | "
                    f"Hedge:{'ON' if getattr(config,'ENABLE_HEDGE',True) else 'OFF'} | "
                    f"Mart:{'ON' if getattr(config,'ENABLE_MARTINGALE',False) else 'OFF'}")

        loop = 0
        while True:
            loop += 1

            # Global drawdown check
            try:
                acc = mt5.account_info()
                if acc:
                    dd = (acc.equity - acc.balance) / acc.balance * 100
                    trig = -abs(getattr(config,'RECOVERY_TRIGGER_PERCENT',10.0))
                    if dd <= trig and not self.global_recovery_active:
                        self.global_recovery_active = True
                        try: database.set_bot_setting("global_recovery_active", True)
                        except: pass
                        self.notify(f"⚠️ *[EMERGENCY]* พอร์ตติดลบ *{dd:.1f}%* → Global Recovery ON")
            except: pass

            self.run_global_recovery_exit()

            for symbol in config.SYMBOLS:
                if not mt5.symbol_select(symbol, True):
                    print(f"\n❌ [{symbol}] ไม่พบใน MT5"); continue

                # All open positions (scalp + grid)
                all_pos = mt5.positions_get(symbol=symbol) or []
                s_magic = config.MAGIC_NUMBER; g_magic = config.GRID_MAGIC_NUMBER
                our_pos  = [p for p in all_pos if p.magic in (s_magic, g_magic)]
                open_cnt = sum(1 for p in our_pos if p.magic == s_magic)

                # Trailing stop
                if our_pos:
                    df_t = self.get_data(symbol, mt5.TIMEFRAME_M5, 50)
                    if df_t is not None:
                        df_t = self.add_indicators(df_t)
                        atr_t= df_t.iloc[-1]['atr']
                        for pos in our_pos:
                            if pos.magic == s_magic:
                                if getattr(config,'ENABLE_TRAILING_STOP',False):
                                    self.manage_trailing_stop(symbol, pos, atr_t)
                                # [H] Auto-Hedge check
                                if getattr(config,'ENABLE_HEDGE',True):
                                    self.check_and_trigger_hedge(symbol, pos, atr_t)

                self.check_and_update_db(symbol)

                # Recovery per-symbol
                if self.global_recovery_active: continue

                # Post-trade cooldown
                lc = self.last_close_time.get(symbol)
                if lc:
                    diff = (datetime.now()-lc).total_seconds()/60
                    cd_m = getattr(config,'POST_TRADE_COOLDOWN_MINUTES',5)
                    if diff < cd_m:
                        print(f"\r[{symbol}] ⏳ Cooldown {int((cd_m-diff)*60)}s     ", end="", flush=True)
                        continue

                # Market data
                m5d = self.get_m5_market_state(symbol)
                (signals, rsi, ema_dist, atr_val, pattern, volatility, dow,
                 macd, bb_pos, smc_fvg, smc_zone, session,
                 rel_vol, xau_str, usd_str, fvg_entry, b_high, b_low) = m5d

                if rsi is None or atr_val is None:
                    print(f"\r[{symbol}] ⏳ รอ Data...     ", end="", flush=True); continue

                h4=self.get_h4_trend(symbol); h1=self.get_h1_trend(symbol); m30=self.get_m30_trend(symbol)
                vol_ok = rel_vol > 1.1

                # Grid
                self.run_grid(symbol, atr_val=atr_val)

                s_cfg      = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
                max_orders = s_cfg.get('max_scalp_orders',2)
                if open_cnt >= max_orders:
                    print(f"\r[{symbol}] ⛔ Max Orders {open_cnt}/{max_orders}     ", end="", flush=True); continue

                if getattr(config,'ENABLE_NEWS_FILTER',False) and self.check_news_forexfactory():
                    print(f"\r[{symbol}] 📰 ข่าวแดง USD     ", end="", flush=True); continue
                if not self.check_time_filter():
                    print(f"\r[{symbol}] ⏰ นอกเวลา     ", end="", flush=True); continue

                # [E] Entry filter + execute
                direction = None
                for sig in ('BUY','SELL'):
                    if sig not in signals: continue
                    ok, reason = self._validate_entry(symbol, sig, rsi, macd, h4, h1, m30,
                                                      smc_zone, vol_ok, volatility)
                    if ok: direction = sig; break
                    print(f"\r[{symbol}] ❌ {sig} rejected: {reason}     ", end="", flush=True)

                if direction:
                    now_cnt = self.count_open_orders(symbol)
                    if now_cnt < max_orders:
                        ticket = self.execute_trade(symbol, direction, atr_val, order_index=now_cnt+1)
                        if ticket:
                            # Reset martingale on new clean entry
                            self.mart_state.pop(symbol, None)
                            sm = {"Asian":0,"London":1,"NY":2,"Overlap":3}
                            database.log_trade(ticket, datetime.now(), symbol, m30 or "N/A", h1 or "N/A",
                                               smc_fvg, smc_zone, ",".join(signals), direction,
                                               rsi, macd, bb_pos, ema_dist, datetime.now().hour,
                                               dow, pattern, volatility, 0.0, "PENDING",
                                               config.MT5_LOGIN, sm.get(session,0), rel_vol, xau_str, usd_str)

                self.place_pending_orders(symbol, signals, atr_val, smc_fvg, fvg_entry, b_high, b_low)

                # AI hourly
                last_ai = self.last_ai_report_time.get(symbol, datetime.now()-timedelta(hours=5))
                if (datetime.now()-last_ai).total_seconds() >= 3600 and not self.ai_in_progress.get(symbol):
                    _,_,gf = self.get_grid_positions(symbol)
                    tk = mt5.symbol_info_tick(symbol)
                    if tk:
                        self.executor.submit(self._run_ai_bg, symbol, {
                            "price":(tk.ask+tk.bid)/2,"rsi":rsi,"macd":macd,
                            "trend":f"H4:{h4}/H1:{h1}/M30:{m30}","profit":gf,"session":session})
                    self.last_ai_report_time[symbol] = datetime.now()

                # Status
                h4i="🟢" if h4=='UP' else "🔴"; h1i="🟢" if h1=='UP' else "🔴"
                m30i="🟢" if m30=='UP' else "🔴"; vi="🔥" if vol_ok else "❄️"
                zi={"Premium":"🔴","Discount":"🟢","Equilibrium":"⚪"}.get(smc_zone,"⚪")
                hs = "🛡️" if self.hedge_state.get(symbol,{}).get('hedge_ticket') else ""
                ms = f"M{self.mart_state.get(symbol,{}).get('level',0)}" if self.mart_state.get(symbol) else ""
                st = f"[{symbol}] {h4i}H4 {h1i}H1 {m30i}M30 | RSI:{rsi:.0f} {zi}{smc_zone} | Vol:{rel_vol:.1f}{vi}{hs}{ms}"

                if loop % 10 == 1: print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {st}")
                else: print(f"\r{st} L{loop}     ", end="", flush=True)

                # Performance report
                if (datetime.now()-self.last_summary_time).total_seconds() >= 14400:
                    if self.send_performance_report():
                        self.last_summary_time = datetime.now()

            time.sleep(5)


if __name__ == "__main__":
    ea = SelfLearningEA()
    try:
        ea.run()
    except KeyboardInterrupt:
        print("\nEA Stopped.")
        mt5.shutdown()