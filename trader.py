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
# SelfLearningEA v4 — Intraday Edition (M15 Focus)
# ============================================================
class SelfLearningEA:

    def __init__(self):
        self.usd_news_today = False
        self.last_news_check = ""
        self._cached_news_events = []
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

        self.trade_stats = {}
        self.hedge_state = {}
        self.mart_state = {}
        self.virtual_sl_cache = {}

        self.symbol_tp_multipliers = {}
        self.symbol_tp_multiplier_expire = {} 

        self.global_recovery_active = False

        self._data_cache = {}  
        self._swing_cache = {}  
        self._last_m30_close = {}  
        self._daily_pnl_cache = None  
        self._daily_pnl_cache_time = 0  

        self._order_retry_cache = {}  
        self._telegram_offset = None

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
        valid_lines = []
        for t, s in self.trade_stats[symbol].items():
            total = s['wins'] + s['losses']
            if total == 0: continue
            wr  = s['wins'] / total * 100
            net = s['gross_profit'] - s['gross_loss']
            avg_w = s['gross_profit'] / s['wins']   if s['wins']   > 0 else 0
            avg_l = s['gross_loss']   / s['losses'] if s['losses'] > 0 else 0
            rr    = avg_w / avg_l if avg_l > 0 else 0
            valid_lines.append(f"  {t}: W{s['wins']}/L{s['losses']} | WR:{wr:.1f}% | Net:${net:.2f} | RR:{rr:.2f}")
            
        if not valid_lines:
            return None
            
        return f"📊 *[Stats/{symbol}]*\n" + "\n".join(valid_lines)

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

    def ensure_mt5_connected(self):
        ti = mt5.terminal_info()
        if ti and ti.connected:
            if mt5.account_info():
                return True
        self.notify("🔴 MT5 Disconnected — Attempting reconnect...")
        mt5.shutdown() 
        time.sleep(2)
        if mt5.initialize():
            if mt5.login(config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
                self.notify("✅ MT5 Reconnected successfully")
                return True
        self.notify("🚨 MT5 Reconnect FAILED — Check broker/network!")
        return False

    def check_telegram_commands(self):
        if not getattr(config, 'TELEGRAM_BOT_TOKEN', ''): 
            return False
        close_all_trigger = False
        try:
            offset = getattr(self, '_telegram_offset', None)
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"timeout": 0, "limit": 5}
            if offset: params["offset"] = offset
            
            r = requests.get(url, params=params, timeout=2)
            if r.status_code == 200:
                data = r.json()
                for item in data.get('result', []):
                    self._telegram_offset = item['update_id'] + 1
                    msg = item.get('message', {}).get('text', '')
                    if not msg: continue
                    
                    msg = msg.strip().upper()
                    if msg == '/CLOSEALL':
                        close_all_trigger = True
                    elif msg == '/STATUS':
                        self.send_performance_report()
                        self.notify("✅ สถานะปัจุบันถูกรายงานด่านบนแล้ว", telegram=True)
                    elif msg == '/PING':
                        self.notify("🏓 PONG! บอทยังทำงานอยู่และคอยดูกราฟให้ตามปกติครับ!", telegram=True)
                    elif msg == '/HELP':
                        self.notify("🛠️ **คำสั่งที่บอทรองรับ:**\n/CLOSEALL - ปิดทุกไม้ฉุกเฉิน\n/STATUS - สรุปยอดและผลประกอบการล่าสุด\n/PING - เช็คว่าบอทหลุดไหม\n/HELP - ดูคำสั่งทั้งหมด", telegram=True)
        except:
            pass
        return close_all_trigger

    def send_line_message(self, msg):
        if not (getattr(config,'LINE_CHANNEL_ACCESS_TOKEN','') and getattr(config,'LINE_USER_ID','')): return
        uids = [u.strip() for u in str(config.LINE_USER_ID).split(',') if u.strip()]
        hdr  = {"Content-Type":"application/json","Authorization":f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}"}
        for uid in uids:
            try: requests.post("https://api.line.me/v2/bot/message/push", headers=hdr, json={"to":uid,"messages":[{"type":"text","text":msg}]}, timeout=10)
            except: pass

    def send_telegram_message(self, msg):
        if not (getattr(config,'TELEGRAM_BOT_TOKEN','') and getattr(config,'TELEGRAM_CHAT_ID','')): return
        html = re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',msg)
        html = re.sub(r'\*(.*?)\*',   r'<b>\1</b>',html)
        html = re.sub(r'`(.*?)`',     r'<code>\1</code>',html)
        html = html.replace('[','(').replace(']',')')
        try:
            r = requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id":config.TELEGRAM_CHAT_ID,"text":html,"parse_mode":"HTML"}, timeout=10)
        except: pass

    def notify(self, msg, telegram=True):
        print(f"\n📢 {msg.replace('*','')}")
        self.send_line_message(msg)
        if telegram: self.send_telegram_message(msg)

    def send_15m_open_positions_report(self):
        lines = []
        for sym in config.SYMBOLS:
            pos = mt5.positions_get(symbol=sym)
            if not pos:
                lines.append(f"• {sym}: ยังไม่มี order")
            else:
                total_pnl = sum(p.profit + p.swap + getattr(p, 'commission', 0.0) for p in pos)
                lines.append(f"• {sym}: {len(pos)} orders | Float: ${total_pnl:.2f}")
        
        self.notify(f"🕒 *[15m Update]* สถานะออเดอร์เปิด:\n" + "\n".join(lines), telegram=True)

    def send_performance_report(self):
        stats = database.get_performance_summary(hours=12)
        lines = []
        if stats:
            lines.append(f"📊 *[12h Report]*\n💰 Net: *{stats['net_profit']:.2f}$* | W:{stats['wins']} L:{stats['losses']} | WR:{stats['win_rate']:.1f}%")
        for sym in config.SYMBOLS:
            summary = self.get_stats_summary(sym)
            if summary: lines.append(summary)
        if lines:
            self.notify("\n\n".join(lines)+"\n\n🚀 สรุปทุก 4 ชม.")
            return True
        return False

    def check_spread_safety(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        si = mt5.symbol_info(symbol)
        if not tick or not si: return True
        pip = si.point * 10
        spread = (tick.ask - tick.bid) / pip
        max_spread = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"]).get('max_spread_pips', config.MAX_SPREAD_PIPS)
        if spread > max_spread:
            self.log_throttled(f"🚫 [{symbol}] Spread {spread:.1f} pips > {max_spread} — blocked", symbol, throttle_sec=30)
            return False
        return True

    def get_cached_data(self, symbol, timeframe, min_bars=200, cache_seconds=10):
        key = (symbol, timeframe)
        now = time.time()
        if key in self._data_cache:
            cached = self._data_cache[key]
            if (now - cached['time']) < cache_seconds and len(cached['df']) >= min_bars:
                return cached['df']
        r = mt5.copy_rates_from_pos(symbol, timeframe, 0, min_bars + 50)
        if r is None or len(r) == 0: return None
        df = pd.DataFrame(r)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        self._data_cache[key] = {'df': df, 'time': now}
        return df

    def get_cached_swings(self, symbol, df, lb=5):
        now = time.time()
        if symbol in self._swing_cache:
            cached = self._swing_cache[symbol]
            if (now - cached['time']) < 60 and cached['df_len'] == len(df):
                return cached['sh_i'], cached['sl_i']
        sh_i, sl_i = self.find_last_swings(df, lb)
        self._swing_cache[symbol] = {'sh_i': sh_i, 'sl_i': sl_i, 'time': now, 'df_len': len(df)}
        return sh_i, sl_i

    def get_daily_pnl(self):
        now = time.time()
        if self._daily_pnl_cache is not None and (now - self._daily_pnl_cache_time) < 30:
            return self._daily_pnl_cache
        today = datetime.now().strftime("%Y-%m-%d")
        daily_pnl = database.get_daily_pnl(today)
        self._daily_pnl_cache = daily_pnl
        self._daily_pnl_cache_time = now
        return daily_pnl

    def check_daily_loss_limit(self):
        daily_pnl = self.get_daily_pnl()
        if daily_pnl <= -config.MAX_DAILY_LOSS_USD:
            self.log_throttled(f"🚨 DAILY LOSS LIMIT HIT: ${daily_pnl:.2f} ≤ -${config.MAX_DAILY_LOSS_USD}", throttle_sec=60)
            if not self.global_recovery_active:
                self.global_recovery_active = True
                database.set_bot_setting("global_recovery_active", True)
                self.notify(f"🚨 DAILY LOSS LIMIT HIT (${daily_pnl:.2f}) — Activating Recovery Mode")
            return False
        return True

    def check_weekend_risk(self):
        if not getattr(config, 'ENABLE_WEEKEND_CLOSE', True): return False
        now = datetime.now()
        if now.weekday() == 4 and now.hour >= 22: return True
        if now.weekday() in [5, 6]: return True
        return False

    def get_portfolio_exposure(self):
        total_risk = 0.0
        for symbol in config.SYMBOLS:
            positions = mt5.positions_get(symbol=symbol) or []
            tick = mt5.symbol_info_tick(symbol)
            if not tick: continue
            for p in positions:
                if p.magic not in [config.MAGIC_NUMBER, config.GRID_MAGIC_NUMBER]: continue
                current_price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
                price_diff = abs(p.price_open - current_price)
                si = mt5.symbol_info(symbol)
                if si:
                    tick_value = si.trade_tick_value
                    tick_size = si.trade_tick_size
                    if tick_size > 0:
                        risk_usd = (price_diff / tick_size) * tick_value * p.volume
                        total_risk += risk_usd
        return total_risk

    def check_portfolio_exposure(self):
        exposure = self.get_portfolio_exposure()
        if exposure > config.MAX_PORTFOLIO_RISK_USD:
            self.log_throttled(f"🚫 Portfolio exposure ${exposure:.2f} > ${config.MAX_PORTFOLIO_RISK_USD} — blocked", throttle_sec=60)
            return False
        return True

    def close_all_positions(self, reason="Weekend Close"):
        all_positions = mt5.positions_get() or []
        closed_count = 0
        for p in all_positions:
            if p.magic not in [config.MAGIC_NUMBER, config.GRID_MAGIC_NUMBER]: continue
            close_price = mt5.symbol_info_tick(p.symbol).bid if p.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(p.symbol).ask
            close_dir = 'SELL' if p.type == mt5.ORDER_TYPE_BUY else 'BUY'
            ticket = self._send_order(p.symbol, close_dir, p.volume, 0, 0, p.magic, f"{reason}_CLOSE", pending_price=close_price)
            if ticket:
                closed_count += 1
                self.notify(f"🔒 [{p.symbol}] Closed {p.volume} {close_dir} @ {close_price:.2f} ({reason})")
        if closed_count > 0:
            self.notify(f"✅ Closed {closed_count} positions ({reason})")
        return closed_count

    def _fetch_news_events(self):
        ds = datetime.now().strftime("%Y-%m-%d")
        if self.last_news_check == ds: return self._cached_news_events
        try:
            r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=5)
            if r.status_code != 200: return []
            events = []
            for n in r.json():
                if n.get('country') != 'USD' or n.get('impact') != 'High': continue
                raw_date = n.get('date', '')
                if not raw_date: continue
                try:
                    dt_utc = datetime.strptime(raw_date[:19], "%m-%d-%YT%H:%M:%S")
                    if len(raw_date) > 19:
                        tz_str = raw_date[19:]
                        sign   = 1 if tz_str[0]=='+' else -1
                        tz_h   = int(tz_str[1:3])
                        tz_m   = int(tz_str[3:5]) if len(tz_str) >= 5 else 0
                        dt_utc = dt_utc - timedelta(hours=sign*tz_h, minutes=sign*tz_m)
                    import calendar
                    epoch  = calendar.timegm(dt_utc.timetuple())
                    dt_local = datetime.fromtimestamp(epoch)
                    events.append({'title': n.get('title',''), 'local_time': dt_local})
                except: continue
            self._cached_news_events = events
            self.last_news_check     = ds
            self.usd_news_today      = len(events) > 0
            return events
        except: return getattr(self, '_cached_news_events', [])

    def check_news_forexfactory(self):
        if not getattr(config, 'ENABLE_NEWS_FILTER', False): return False
        mins_before = getattr(config, 'NEWS_MINUTES_BEFORE', 30)
        mins_after  = getattr(config, 'NEWS_MINUTES_AFTER',  30)
        now         = datetime.now()
        events      = self._fetch_news_events()
        for ev in events:
            dt  = ev['local_time']
            diff = (now - dt).total_seconds() / 60.0
            if -mins_before <= diff <= mins_after:
                self.log_throttled(f"📰 [NEWS] '{ev['title']}' @ {dt.strftime('%H:%M')} — blocked ({diff:+.0f}m)", throttle_sec=60)
                return True
        return False

    def check_time_filter(self):
        h = datetime.now().hour
        return config.TRADE_TIME_START <= h <= config.TRADE_TIME_END

    def get_data(self, symbol, tf, n=200):
        return self.get_cached_data(symbol, tf, n, cache_seconds=10)

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
                r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 20)
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
        sh_i, sl_i = self.get_cached_swings(symbol, df, lb=5)
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

    def get_m15_market_state(self, symbol):
        df = self.get_data(symbol, mt5.TIMEFRAME_M15, 200)
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
        # [ICT OTE & Expansion Logic]
        sh_idx, sl_idx = self.find_last_swings(df, lb=5)
        ote_62, ote_705, ote_79 = 0, 0, 0
        sd_2_0, sd_2_5 = 0, 0
        
        if sh_idx != -1 and sl_idx != -1:
            swing_h = df.iloc[sh_idx]['high']
            swing_l = df.iloc[sl_idx]['low']
            diff = swing_h - swing_l
            
            # Identify OTE (Optimal Trade Entry) zones
            ote_62  = swing_h - 0.62 * diff  if row['close'] < swing_h else swing_l + 0.62 * diff
            ote_705 = swing_h - 0.705 * diff if row['close'] < swing_h else swing_l + 0.705 * diff
            ote_79  = swing_h - 0.79 * diff  if row['close'] < swing_h else swing_l + 0.79 * diff
            
            # Standard Deviation Projections (Targeting Liquidity)
            if row['close'] > swing_h: # Bullish expansion
                sd_2_0 = swing_l + 2.0 * diff
                sd_2_5 = swing_l + 2.5 * diff
            else: # Bearish expansion
                sd_2_0 = swing_h - 2.0 * diff
                sd_2_5 = swing_h - 2.5 * diff

        xau,usd = self.get_currency_strength(symbol)
        b_high = df['high'].rolling(20).max().iloc[-1]
        b_low  = df['low'].rolling(20).min().iloc[-1]
        
        return (signals, row['rsi_14'], ema_dist, atr_val,
                self.check_candlestick_pattern(df), row['volatility'],
                datetime.now().weekday(), row['macd_diff'], bb_pos,
                smc_fvg, smc_zone, self.get_market_session(),
                row['rel_volume'], xau, usd, fvg_entry, b_high, b_low,
                (ote_62, ote_705, ote_79), (sd_2_0, sd_2_5))

    def calculate_structural_sl_tp(self, symbol, direction, atr_val, entry_price=None):
        s_cfg    = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        sym_info = mt5.symbol_info(symbol)
        tick     = mt5.symbol_info_tick(symbol)
        if sym_info is None or tick is None: return None, None, 0.0

        pip = sym_info.point * 10
        entry = entry_price if entry_price is not None else (tick.ask if direction == 'BUY' else tick.bid)

        df_m30 = self.get_data(symbol, mt5.TIMEFRAME_M30, 100)
        sl_price = None
        if df_m30 is not None:
            sh_i, sl_i = self.find_last_swings(df_m30, lb=5)
            buf = s_cfg.get('scalp_struct_offset', 25) * pip
            if direction == 'BUY' and sl_i != -1:
                swing_sl = df_m30.iloc[sl_i]['low'] - buf
                atr_sl   = entry - atr_val * s_cfg.get('atr_sl_mul', 0.8)
                sl_price = min(swing_sl, atr_sl)
            elif direction == 'SELL' and sh_i != -1:
                swing_sl = df_m30.iloc[sh_i]['high'] + buf
                atr_sl   = entry + atr_val * s_cfg.get('atr_sl_mul', 0.8)
                sl_price = max(swing_sl, atr_sl)

        if sl_price is None:
            sl_dist  = atr_val * s_cfg.get('atr_sl_mul', 0.8)
            sl_price = (entry - sl_dist) if direction == 'BUY' else (entry + sl_dist)

        min_sl = s_cfg.get('scalp_min_sl_pips', 50) * pip
        actual_sl_dist = abs(entry - sl_price)
        if actual_sl_dist < min_sl:
            actual_sl_dist = min_sl
            sl_price = (entry - min_sl) if direction == 'BUY' else (entry + min_sl)

        _, ob_high, ob_low = self.get_smc_structure(symbol)
        if symbol in self.symbol_tp_multiplier_expire:
            if datetime.now() > self.symbol_tp_multiplier_expire[symbol]:
                self.symbol_tp_multipliers.pop(symbol, None)
                self.symbol_tp_multiplier_expire.pop(symbol, None)
        ai_mul = self.symbol_tp_multipliers.get(symbol, 1.0)
        tp_price = None

        if direction == 'BUY' and ob_high and ob_high > entry:
            tp_price = ob_high * 0.998  
        elif direction == 'SELL' and ob_low and ob_low < entry:
            tp_price = ob_low  * 1.002

        if tp_price is None:
            tp_dist  = atr_val * s_cfg.get('atr_tp_mul', 2.5) * ai_mul
            tp_price = (entry + tp_dist) if direction == 'BUY' else (entry - tp_dist)

        tp_dist_actual = abs(tp_price - entry)
        rr = tp_dist_actual / actual_sl_dist if actual_sl_dist > 0 else 0.0

        return sl_price, tp_price, rr

    def _validate_entry(self, symbol, direction, rsi, macd, h4, h1, m30, smc_zone, vol_ok, volatility):
        if self.check_weekend_risk(): return False, "Weekend approaching"
        if not self.check_daily_loss_limit(): return False, "Daily loss limit hit"
        if not self.check_spread_safety(symbol): return False, f"Spread too wide"
        if not self.check_portfolio_exposure(): return False, "Portfolio risk exceeded"
        
        if self.global_recovery_active: return False, "Global Recovery active"
        if not vol_ok:      return False, "Volume ต่ำ"
        if volatility > 2.5: return False, f"Volatility {volatility:.1f} > 2.5"
        
        rsi_ok_buy  = config.SCALP_BUY_RSI_MIN  <= rsi <= config.SCALP_BUY_RSI_MAX
        rsi_ok_sell = config.SCALP_SELL_RSI_MIN <= rsi <= config.SCALP_SELL_RSI_MAX
        if direction == 'BUY':
            if not rsi_ok_buy:  return False, f"RSI {rsi:.1f} นอกช่วง BUY"
            if macd <= 0:       return False, "MACD ≤ 0"
        else:
            if not rsi_ok_sell: return False, f"RSI {rsi:.1f} นอกช่วง SELL"
            if macd >= 0:       return False, "MACD ≥ 0"
            
        if getattr(config,'SCALP_REQUIRE_H1_CONFIRM',True):
            if direction == 'BUY'  and h1  != 'UP':   return False, f"H1={h1}"
            if direction == 'SELL' and h1  != 'DOWN':  return False, f"H1={h1}"
        
        if direction == 'BUY'  and smc_zone != 'Discount': return False, f"Zone={smc_zone} (BUY requires Discount)"
        if direction == 'SELL' and smc_zone != 'Premium': return False, f"Zone={smc_zone} (SELL requires Premium)"
        return True, "ผ่าน"

    def calculate_lot(self, symbol, sl_dist=None, risk_pct=None):
        acc = mt5.account_info()
        if not acc: return config.FIXED_LOT
        if config.RISK_MODE == "FIXED": return config.FIXED_LOT

        balance    = acc.balance
        sym_info   = mt5.symbol_info(symbol)
        if sym_info is None: return config.FIXED_LOT

        if getattr(config, 'RISK_MODE', 'PERCENT') == "DIVISOR":
            div = getattr(config, 'LOT_DIVISOR', 10000)
            lot = balance / div if div > 0 else config.FIXED_LOT
            lot = round(lot / sym_info.volume_step) * sym_info.volume_step
            max_l = getattr(config, 'MAX_LOT', 0.5)
            lot   = min(lot, max_l)
            return max(sym_info.volume_min, min(lot, sym_info.volume_max))

        r_pct      = risk_pct if risk_pct is not None else config.RISK_PERCENT
        risk_amt   = balance * (r_pct / 100.0)

        dist = sl_dist
        if dist is None or dist <= 0:
            dist = 300 * sym_info.point * 10
        ts = sym_info.trade_tick_size
        tv = sym_info.trade_tick_value
        if ts > 0 and tv > 0:
            pip = sym_info.point * 10
            safe_dist = max(dist, 2 * pip)
            lot = risk_amt / ((safe_dist/ts) * tv)
            lot = round(lot / sym_info.volume_step) * sym_info.volume_step
            max_l = getattr(config, 'MAX_LOT', 0.5)
            lot   = min(lot, max_l)
            return max(sym_info.volume_min, min(lot, sym_info.volume_max))
        return config.FIXED_LOT

    def normalize_lot(self, symbol, lot):
        si = mt5.symbol_info(symbol)
        if not si: return lot
        return max(si.volume_min, min(round(lot / si.volume_step) * si.volume_step, si.volume_max))

    def count_open_orders(self, symbol, magic=None):
        m = magic or config.MAGIC_NUMBER
        symbol = symbol.upper()
        all_p = mt5.positions_get()
        if not all_p: return 0
        return sum(1 for p in all_p if p.symbol.upper() == symbol and p.magic == m)

    def count_pending_orders(self, symbol):
        symbol = symbol.upper()
        all_o = mt5.orders_get()
        if not all_o: return 0
        return sum(1 for o in all_o if o.symbol.upper() == symbol and o.magic == config.MAGIC_NUMBER)

    def get_symbol_pip(self, symbol):
        si = mt5.symbol_info(symbol)
        return si.point * 10 if si else 0.0001

    def check_trade_safety(self, symbol, direction, price, is_scalp=False, smc_zone=None, ignore_spacing=False):
        pip   = self.get_symbol_pip(symbol)
        s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        min_d = s_cfg.get('min_scalp_spacing', 15) * pip
        magics = [config.MAGIC_NUMBER, config.GRID_MAGIC_NUMBER]

        all_now = mt5.positions_get(symbol=symbol) or []
        max_t = s_cfg.get('max_scalp_orders', 2)
        if len(all_now) >= max_t + 5:
            self.log_throttled(f"🚫 [{symbol}] HARD LIMIT: {len(all_now)} positions! ปฏิเสธการเข้าเพิ่มทุกกรณี", symbol)
            return False

        for p in all_now:
            if p.magic not in magics: continue
            existing_dir = 'BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL'
            if existing_dir != direction:
                self.log_throttled(f"⚠️ [{symbol}] สวนทาง {existing_dir} → ห้ามเปิด {direction}", symbol)
                return False
            if not ignore_spacing and abs(p.price_open - price) < min_d:
                return False

        orders = mt5.orders_get(symbol=symbol) or []
        for o in orders:
            if o.magic not in magics: continue
            od = 'BUY' if o.type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP] else 'SELL'
            if od != direction: return False
            if abs(o.price_open - price) < min_d: return False
        return True

    def normalize_price(self, symbol, price):
        if price is None or price <= 0: return 0.0
        si = mt5.symbol_info(symbol)
        if not si: return price
        digits = si.digits
        tick_size = si.trade_tick_size
        if tick_size > 0:
            price = round(price / tick_size) * tick_size
        return round(float(price), digits)

    def _send_order(self, symbol, direction, lot, sl, tp, magic, comment, pending_type=None, pending_price=0.0, expiry_hours=4):
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return None
        raw_price = pending_price if pending_type else (tick.ask if direction=='BUY' else tick.bid)
        price = self.normalize_price(symbol, raw_price)
        otype = pending_type if pending_type else (mt5.ORDER_TYPE_BUY if direction=='BUY' else mt5.ORDER_TYPE_SELL)

        norm_sl = self.normalize_price(symbol, sl) if sl > 0 else 0.0
        norm_tp = self.normalize_price(symbol, tp) if tp > 0 else 0.0

        si = mt5.symbol_info(symbol)
        if si:
            stops_level = si.trade_stops_level * si.point
            if norm_sl > 0:
                if direction == 'BUY'  and (price - norm_sl) < stops_level: norm_sl = self.normalize_price(symbol, price - stops_level)
                if direction == 'SELL' and (norm_sl - price) < stops_level: norm_sl = self.normalize_price(symbol, price + stops_level)
            if norm_tp > 0:
                if direction == 'BUY'  and (norm_tp - price) < stops_level: norm_tp = self.normalize_price(symbol, price + stops_level)
                if direction == 'SELL' and (price - norm_tp) < stops_level: norm_tp = self.normalize_price(symbol, price - stops_level)

        req = {
            "action":   mt5.TRADE_ACTION_PENDING if pending_type else mt5.TRADE_ACTION_DEAL,
            "symbol":   symbol, "volume": lot, "type": otype, "price": float(price),
            "sl": float(norm_sl), "tp": float(norm_tp), "deviation": 30,
            "magic": magic, "comment": comment,
            "type_time":    mt5.ORDER_TIME_SPECIFIED if pending_type else mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK if not pending_type else mt5.ORDER_FILLING_RETURN,
        }
        if pending_type:
            req["expiration"] = int(time.time() + expiry_hours*3600)
            
        max_retries = 3
        for attempt in range(max_retries):
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                if norm_sl > 0:
                    self.virtual_sl_cache[res.order] = float(norm_sl)
                return res.order
            if res and res.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_CONNECTION, mt5.TRADE_RETCODE_PRICE]:
                self.log_throttled(f"⚠️ [{symbol}] Order rejected ({res.retcode}) - Retrying {attempt+1}/{max_retries}...", symbol)
                time.sleep(0.5)
                continue
            else:
                break 
                
        print(f"🔴 [{symbol}] Order fail: {res.retcode if res else 'None'} | {mt5.last_error()}")
        return None

    def get_dynamic_min_rr(self, symbol):
        """Calculate dynamic minimum RR based on session win rate."""
        base_rr = getattr(config, 'MIN_RR_RATIO', 1.2)
        
        self._init_stats(symbol)
        s = self.trade_stats[symbol].get('SCALP')
        if not s: return base_rr
        
        total = s['wins'] + s['losses']
        if total <= 3:
            return base_rr
            
        wr = s['wins'] / total
        
        safe_wr = max(0.2, min(wr, 0.8))
        breakeven_rr = (1 - safe_wr) / safe_wr
        target_rr = breakeven_rr + 0.2
        
        return max(0.8, min(target_rr, 2.5))

    def execute_trade(self, symbol, direction, atr_val, order_index=1, pending_type=None, pending_price=0.0, smc_zone=None, comment=None, box_high=0.0, box_low=0.0, manual_tp=0.0):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None: return None

        check_p = pending_price if pending_type else (tick.ask if direction=='BUY' else tick.bid)
        ignore_s = "RECOVERY" in (comment or "")
        if not self.check_trade_safety(symbol, direction, check_p, is_scalp=True, smc_zone=smc_zone, ignore_spacing=ignore_s):
            return None

        # [ICT 7-Step Logic] Specialized Box-sized SL/TP
        if box_high > 0 and box_low > 0:
            box_size = box_high - box_low
            # SL = 1x box distance on the breakout side
            # TP = 1x box distance on the opposite side (from entry)
            if direction == 'BUY':
                sl = check_p - box_size
                structural_tp = manual_tp if manual_tp > 0 else (check_p + box_size)
            else:
                sl = check_p + box_size
                structural_tp = manual_tp if manual_tp > 0 else (check_p - box_size)
            structural_rr = abs(structural_tp - check_p) / box_size if box_size > 0 else 1.0
        else:
            sl, structural_tp, structural_rr = self.calculate_structural_sl_tp(symbol, direction, atr_val, entry_price=check_p)
            if manual_tp > 0:
                structural_tp = manual_tp
                sl_dist_calc = abs(check_p - sl) if sl else 0.0001
                structural_rr = abs(structural_tp - check_p) / sl_dist_calc
            
        if sl is None: return None

        is_recovery = "RECOVERY" in (comment or "")
        use_multi_tp = getattr(config, 'ENABLE_MULTI_TP', False) and not is_recovery

        if use_multi_tp:
            is_limit_setup = pending_type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT]
            if is_limit_setup:
                rr_levels = getattr(config, 'CONSOLIDATION_TP_MULTS', [0.5, 0.75, 1.0])
            else:
                rr_levels = getattr(config, 'MULTI_TP_RR_LEVELS', [0.8, 1.5, 3.0])
            check_rr = rr_levels[-1] if len(rr_levels) > 0 else structural_rr
        else:
            check_rr = structural_rr

        min_rr = self.get_dynamic_min_rr(symbol)
        if not (use_multi_tp and pending_type) and check_rr < min_rr:
            self.log_throttled(f"⚠️ [{symbol}] RR={check_rr:.2f} < {min_rr:.2f} → ข้าม", symbol, throttle_sec=120)
            return None

        sl_dist = abs((pending_price if pending_type else check_p) - sl)
        total_lot = self.calculate_lot(symbol, sl_dist=sl_dist)

        if use_multi_tp:
            ratios = getattr(config, 'MULTI_TP_RATIOS', [0.4, 0.3, 0.3])
            
            if is_limit_setup:
                rr_levels = getattr(config, 'CONSOLIDATION_TP_MULTS', [0.5, 0.75, 1.0])
            else:
                rr_levels = getattr(config, 'MULTI_TP_RR_LEVELS', [0.8, 1.5, 3.0])
            
            # If AI provided a specific target, ensure the last TP segment hits it
            if manual_tp > 0 and len(rr_levels) > 0:
                rr_levels[-1] = structural_rr
                
            check_rr = rr_levels[-1] if len(rr_levels) > 0 else structural_rr
            for i, (ratio, rr_lvl) in enumerate(zip(ratios, rr_levels)):
                lvl_lot = self.normalize_lot(symbol, total_lot * ratio)
                if lvl_lot < 0.01: continue
                
                dist = sl_dist * rr_lvl
                lvl_tp = (check_p + dist) if direction == 'BUY' else (check_p - dist)
                lvl_tp = self.normalize_price(symbol, lvl_tp)
                
                lvl_comment = f"{config.ORDER_COMMENT}_{direction[0]}#{order_index}_TP{i+1}" if not comment else comment
                ticket = self._send_order(symbol, direction, lvl_lot, sl, lvl_tp, config.MAGIC_NUMBER, lvl_comment, pending_type, pending_price)
                if ticket:
                    if not first_ticket: first_ticket = ticket
                    self.notify(f"🟢 *[{symbol}] {direction} TP{i+1}* Lot:{lvl_lot} | SL:{sl:.2f} | TP:{lvl_tp:.2f} | RR:{rr_lvl}")
            return first_ticket
        else:
            order_comment = f"{config.ORDER_COMMENT}_{direction[0]}#{order_index}" if not comment else comment
            ticket = self._send_order(symbol, direction, total_lot, sl, structural_tp, config.MAGIC_NUMBER, order_comment, pending_type, pending_price)
            if ticket:
                s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
                self.notify(f"🟢 *[{symbol}] {direction}* #{order_index}/{s_cfg.get('max_scalp_orders',2)}\n"
                            f"Lot:{total_lot} | SL:{sl:.2f} | TP:{structural_tp:.2f} | RR:{structural_rr:.2f}")
            return ticket


    def check_and_trigger_hedge(self, symbol, position, atr_val):
        s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        pip   = self.get_symbol_pip(symbol)
        trigger_pips = s_cfg.get('hedge_trigger_pips', 80)
        hedge_tp_usd = s_cfg.get('hedge_basket_tp',    2.0)

        tick = mt5.symbol_info_tick(symbol)
        if not tick: return

        all_pos = mt5.positions_get(symbol=symbol) or []
        hedge_positions = [p for p in all_pos if "HEDGE" in p.comment or "RECOVERY" in p.comment or 
                          (p.magic in [config.MAGIC_NUMBER, config.GRID_MAGIC_NUMBER] and 
                           any(p.ticket == self.hedge_state.get(symbol, {}).get('hedge_ticket') for _ in [0]))]
        
        if len(hedge_positions) > 0:
            hs = self.hedge_state.get(symbol, {})
            basket = []
            total_p = 0.0
            if hs.get('hedge_ticket') and hs.get('original_ticket'):
                tickets = {hs['original_ticket'], hs['hedge_ticket']}
                basket = [p for p in all_pos if p.ticket in tickets]
                total_p = sum(p.profit + p.swap + getattr(p,'commission',0.0) for p in basket)
            else:
                basket = hedge_positions
                total_p = sum(p.profit + p.swap + getattr(p,'commission',0.0) for p in basket)

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
                    if ticket: closed_tickets.append(ticket)
                    else: failed.append(pos.ticket)
                if failed: print(f"⚠️ [HEDGE/{symbol}] Partially closed — failed tickets: {failed}")
                else: self.notify(f"✅ *[HEDGE/{symbol}] ปิดครบ {len(basket)} ไม้ สำเร็จ")
                self.hedge_state.pop(symbol, None)
            return

        direction = 'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL'
        if direction == 'BUY': adverse_dist = (position.price_open - tick.bid) / pip
        else: adverse_dist = (tick.ask - position.price_open) / pip

        if adverse_dist < trigger_pips: return  

        hedge_dir = direction 
        rec_mul = getattr(config, 'RECOVERY_LOT_MULTIPLIER', 1.0)
        rec_lot = self.normalize_lot(symbol, position.volume * rec_mul)
        hedge_ticket = self._send_order(symbol, hedge_dir, rec_lot, 0, 0, config.MAGIC_NUMBER, "AUTO_RECOVERY")
        if hedge_ticket:
            self.hedge_state[symbol] = {
                'original_ticket': position.ticket,
                'hedge_ticket':    hedge_ticket,
            }
            self.notify(f"🛡️ *[RECOVERY/{symbol}] เปิด {hedge_dir} (Same-Side) lot:{rec_lot}*\n"
                        f"ราคาสวน {adverse_dist:.0f} pips — คุมความเสี่ยงด้วย Basket TP")

    def smart_martingale(self, symbol, losing_direction, atr_val):
        if not getattr(config, 'ENABLE_MARTINGALE', False): return
        max_lvl = getattr(config, 'MART_MAX_LEVEL', 3)
        mult    = getattr(config, 'MART_LOT_MULTIPLIER', 1.5)

        ms = self.mart_state.get(symbol, {'level':0,'direction':None,'base_lot':config.FIXED_LOT})
        if ms['direction'] and ms['direction'] != losing_direction:
            self.mart_state[symbol] = {'level':0,'direction':None,'base_lot':config.FIXED_LOT}
            ms = self.mart_state[symbol]

        if ms['level'] >= max_lvl:
            self.notify(f"⚠️ *[MART/{symbol}] ถึง Max Level {max_lvl}* — หยุด Martingale รอบนี้")
            self.mart_state.pop(symbol, None)
            return

        h4  = self.get_h4_trend(symbol)
        h1  = self.get_h1_trend(symbol)
        m30 = self.get_m30_trend(symbol)
        m15d = self.get_m15_market_state(symbol)
        _, rsi, _, _, _, vol, _, macd, _, _, zone, _, rel_vol, _, _, _, _, _ = m15d
        vol_ok = rel_vol > 1.1 if rel_vol else False

        valid, reason = self._validate_entry(symbol, losing_direction, rsi, macd, h4, h1, m30, zone, vol_ok, vol if vol else 1.0)
        if not valid:
            self.log_throttled(f"🔄 [{symbol}] Martingale ข้าม: Entry ไม่ผ่าน ({reason})", symbol)
            return

        new_level = ms['level'] + 1
        new_lot   = round(ms['base_lot'] * (mult ** new_level), 2)
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
        ticket  = self._send_order(symbol, losing_direction, new_lot, sl, tp, config.MAGIC_NUMBER, f"MART_L{new_level}")
        if ticket:
            self.mart_state[symbol] = {'level':new_level,'direction':losing_direction,'base_lot':ms['base_lot']}
            self.notify(f"🔄 *[MART/{symbol}] Level {new_level}/{max_lvl}*\nLot: {new_lot} | RR: {rr:.2f} | SL:{sl:.2f} | TP:{tp:.2f}")
            self._record_trade(symbol, 'MART', 0)

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
                
                # ICT Fibo Trailing Logic
                if pos.sl and pos.sl < pos.price_open:
                    box_size = abs(pos.price_open - pos.sl)
                    mid_target = pos.price_open + 0.5 * box_size
                    high_target = pos.price_open + box_size
                    
                    if tick.bid >= high_target:
                        new_sl = mid_target # Move SL to Middle
                    elif tick.bid >= mid_target:
                        new_sl = pos.price_open + 5*pip # Move SL to Break-even + buffer
                
                # Standard Trailing (if ICT not triggered)
                if not new_sl:
                    if pd_ >= be_d: new_sl = pos.price_open + be_o
                    elif pd_ >= act:
                        ts = tick.bid - step
                        if ts > (pos.sl or 0) and ts > pos.price_open: new_sl = ts
            else:
                pd_ = pos.price_open - tick.ask
                
                # ICT Fibo Trailing Logic
                if pos.sl and pos.sl > pos.price_open:
                    box_size = abs(pos.sl - pos.price_open)
                    mid_target = pos.price_open - 0.5 * box_size
                    high_target = pos.price_open - box_size
                    
                    if tick.ask <= high_target:
                        new_sl = mid_target # Move SL to Middle
                    elif tick.ask <= mid_target:
                        new_sl = pos.price_open - 5*pip # Move SL to Break-even + buffer

                # Standard Trailing (if ICT not triggered)
                if not new_sl:
                    if pd_ >= be_d: new_sl = pos.price_open - be_o
                    elif pd_ >= act:
                        ts = tick.ask + step
                        if ts < (pos.sl or float('inf')) and ts < pos.price_open: new_sl = ts

            if new_sl and new_sl != pos.sl:
                norm_sl = self.normalize_price(symbol, new_sl)
                mt5.order_send({"action":mt5.TRADE_ACTION_SLTP,"position":pos.ticket, "symbol":symbol,"sl":float(norm_sl),"tp":float(pos.tp)})
        except Exception as e:
            if "position" not in str(e).lower(): print(f"⚠️ TrailStop: {e}")

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
            res= mt5.order_send({"action":mt5.TRADE_ACTION_DEAL,"symbol":symbol,"volume":pos.volume,"type":ot,"position":pos.ticket,
                                 "price":pr,"deviation":30,"magic":config.GRID_MAGIC_NUMBER,"comment":"GRID_EXIT",
                                 "type_time":mt5.ORDER_TIME_GTC,"type_filling":mt5.ORDER_FILLING_FOK})
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

            if total==0 and self.grid_safety_triggered.get(symbol): self.grid_safety_triggered[symbol]=False
            if self.grid_safety_triggered.get(symbol): return

            max_lvl = s_cfg.get('grid_symmetric_max_levels',2) if mode=='SYMMETRIC' else s_cfg.get('grid_max_levels',3)
            cd_ok   = not self.grid_last_open_time.get(symbol) or (datetime.now()-self.grid_last_open_time[symbol]).total_seconds()>=60
            cur     = (tick.ask+tick.bid)/2.0

            for dir_, prices in [('BUY',bp),('SELL',sp)]:
                need = (mode in ('SYMMETRIC','LONG_ONLY') and dir_=='BUY') or (mode in ('SYMMETRIC','SHORT_ONLY') and dir_=='SELL')
                if not need or not cd_ok or len(prices)>=max_lvl: continue
                if any(abs(p-cur)<spacing*0.6 for p in prices): continue
                lot    = s_cfg.get('grid_lot',0.01)
                tp_d   = s_cfg.get('grid_tp_pips',500)*pip
                sl_d   = s_cfg.get('grid_sl_pips',300)*pip
                pr     = tick.ask if dir_=='BUY' else tick.bid
                tp     = pr+tp_d if dir_=='BUY' else pr-tp_d
                sl     = pr-sl_d if dir_=='BUY' else pr+sl_d
                ticket = self._send_order(symbol, dir_, lot, sl, tp, config.GRID_MAGIC_NUMBER, f"GRID_{dir_[0]}#{len(prices)+1}")
                if ticket:
                    prices.append(cur); self.grid_last_open_time[symbol]=datetime.now()
                    self.notify(f"🟩 *[GRID/{symbol}] {dir_} L{len(prices)}*\nLot:{lot} | SL:{sl:.2f} | TP:{tp:.2f}")

            print(f"\r📊 [GRID/{symbol}] {mode}({reason}) B:{len(bp)} S:{len(sp)} F:${fl:.2f} TP:${basket_tp:.1f} SL:${basket_sl:.1f}     ", end="", flush=True)
        except Exception as e: print(f"⚠️ [GRID/{symbol}] {e}")

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
                self.execute_trade(symbol,'BUY',atr_val,order_index=91,pending_type=mt5.ORDER_TYPE_BUY_LIMIT,pending_price=fvg_entry)
            elif fvg_type=="Bearish" and fvg_entry>tick.bid:
                self.execute_trade(symbol,'SELL',atr_val,order_index=91,pending_type=mt5.ORDER_TYPE_SELL_LIMIT,pending_price=fvg_entry)

        if self.count_open_orders(symbol)+self.count_pending_orders(symbol) < max_t:
            if 'BUY' in signals:
                p = b_high + d_p*pip
                if p>tick.ask and not near(p):
                    self.execute_trade(symbol,'BUY',atr_val,order_index=92,pending_type=mt5.ORDER_TYPE_BUY_STOP,pending_price=p)
            elif 'SELL' in signals:
                p = b_low - d_p*pip
                if p<tick.bid and not near(p):
                    self.execute_trade(symbol,'SELL',atr_val,order_index=92,pending_type=mt5.ORDER_TYPE_SELL_STOP,pending_price=p)

    def check_and_update_db(self, symbol):
        try:
            history = mt5.history_deals_get(datetime.now()-timedelta(days=2), datetime.now()+timedelta(days=1))
            if not history: return
            scalp_m = config.MAGIC_NUMBER; grid_m = config.GRID_MAGIC_NUMBER
            new_deals = [d for d in history if d.symbol==symbol and d.magic in (scalp_m,grid_m) and d.entry==mt5.DEAL_ENTRY_OUT and not database.is_deal_notified(d.ticket)]
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
                msg = (f"*{res_str} [{symbol}] {trade_type} ปิดแล้ว!*\nปิด {len(deals)}/{len(deals)+rem} ไม้ | Net: *{total_p:.2f}$*")
                self.notify(msg)
                
                for d in deals:
                    database.mark_deal_as_notified(d.ticket)
                    database.update_pending_trades(d.position_id, d.profit, "WIN" if d.profit>=0 else "LOSS")
                    self.last_close_time[symbol] = datetime.now()
                    self._record_trade(symbol, trade_type, d.profit)

                    if d.profit < 0 and magic == scalp_m:
                        pos_hist = mt5.history_orders_get(ticket=d.order)
                        if pos_hist:
                            dir_ = 'BUY' if pos_hist[0].type in [mt5.ORDER_TYPE_BUY] else 'SELL'
                            df_m15 = self.get_data(symbol, mt5.TIMEFRAME_M15, 50)
                            if df_m15 is not None:
                                df_m15 = self.add_indicators(df_m15)
                                atr_now = df_m15.iloc[-1]['atr']
                                self.smart_martingale(symbol, dir_, atr_now)

                    if getattr(config,'ENABLE_LOSS_SHAVING',False) and d.profit>0 and magic==scalp_m:
                        self.acc_scalp_profit[symbol] = self.acc_scalp_profit.get(symbol,0.0) + d.profit
                        self.shave_losing_positions(symbol)
        except Exception as e: print(f"⚠️ check_db [{symbol}]: {e}")

    def get_managed_positions(self, symbol):
        pos = mt5.positions_get(symbol=symbol) or []
        managed = [p for p in pos if p.magic in (config.MAGIC_NUMBER, config.GRID_MAGIC_NUMBER)]
        total   = sum(p.profit+p.swap+getattr(p,'commission',0.0) for p in managed)
        return managed, total

    def run_global_recovery_exit(self):
        if self.global_recovery_active:
            self.global_recovery_active = False
            try: database.set_bot_setting("global_recovery_active", False)
            except: pass
        return False

        pass
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

        si = mt5.symbol_info(symbol)
        if not si: return
        pip = si.point * 10
        spread = (tick.ask - tick.bid) / pip
        if spread > 30: 
            self.log_throttled(f"✂️ [{symbol}] Shaving skipped: spread {spread:.1f} pips too wide", symbol)
            return
        
        df = self.get_data(symbol, mt5.TIMEFRAME_M15, 50)
        if df is not None:
            df = self.add_indicators(df)
            if df.iloc[-1]['volatility'] > 2.5:
                self.log_throttled(f"✂️ [{symbol}] Shaving skipped: volatility too high", symbol)
                return

        remaining = tp.volume - vol
        close_ot  = mt5.ORDER_TYPE_SELL if tp.type==mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        close_pr  = tick.bid if tp.type==mt5.ORDER_TYPE_BUY else tick.ask
        res = mt5.order_send({"action":mt5.TRADE_ACTION_DEAL,"symbol":symbol,"volume":tp.volume,"type":close_ot,"position":tp.ticket,
                              "price":close_pr,"deviation":20,"magic":tp.magic,"comment":"LOSS_SHAVING","type_time":mt5.ORDER_TIME_GTC,
                              "type_filling":mt5.ORDER_FILLING_FOK})
        if res and res.retcode==mt5.TRADE_RETCODE_DONE:
            cost = (vol / tp.volume) * abs(tp.profit)
            self.acc_scalp_profit[symbol] -= cost
            if remaining >= 0.01:
                s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
                reopen_dir = 'BUY' if close_ot == mt5.ORDER_TYPE_SELL else 'SELL'
                atr_val = 0.0
                df = self.get_data(symbol, mt5.TIMEFRAME_M15, 50)
                if df is not None:
                    df = self.add_indicators(df)
                    atr_val = df.iloc[-1]['atr']
                sl, tp_new, rr = self.calculate_structural_sl_tp(symbol, reopen_dir, atr_val)
                self._send_order(symbol, reopen_dir, remaining, sl or 0, tp_new or 0, tp.magic, "LOSS_SHAVE_REMAIN")
            self.notify(f"✂️ *[SHAVER/{symbol}]* Shaved {vol}lot → -${cost:.2f}{' | Reopened ' + f'{remaining}lot' if remaining >= 0.01 else ''}")

    def check_virtual_sl(self):
        all_pos = mt5.positions_get() or []
        for p in all_pos:
            sl_price = self.virtual_sl_cache.get(p.ticket)
            if not sl_price: continue
            
            tick = mt5.symbol_info_tick(p.symbol)
            if not tick: continue
            
            hit = False
            if p.type == mt5.ORDER_TYPE_BUY and tick.bid <= sl_price: hit = True
            if p.type == mt5.ORDER_TYPE_SELL and tick.ask >= sl_price: hit = True
            
            if hit:
                self.notify(f"🛡️ *[VIRTUAL SL]* #{p.ticket} ({p.symbol}) hit @ {sl_price:.5f} — Closing Position")
                close_dir = 'SELL' if p.type == mt5.ORDER_TYPE_BUY else 'BUY'
                close_pr  = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
                ticket = self._send_order(p.symbol, close_dir, p.volume, 0, 0, p.magic, "VIRTUAL_SL_CLOSE", pending_price=close_pr)
                if ticket:
                    self.virtual_sl_cache.pop(p.ticket, None)

    def get_ai_trade_decision(self, symbol, ctx_data):
        import requests, json
        api_key = getattr(config, 'AI_API_KEY', '')
        if not api_key:
            return {"signal": "HOLD", "reason": "No API Key configured"}
            
        import time
        model = getattr(config, 'AI_MODEL', 'gemini-2.5-flash')
        if '3.1-pro' in model and 'preview' not in model: model = 'gemini-3.1-pro-preview'
        elif '1.5-pro' in model: model = 'gemini-2.5-pro'
        
        prompt = f"""
You are an expert algorithmic Forex trading AI specializing in Smart Money Concepts (SMC), Price Action, and specifically the 7-Step ICT Consolidation Strategy.
Analyze the following chart data for {symbol}:
{ctx_data}

### YOUR 7-STEP TRADING PLAYBOOK:
1. **Identify Consolidation**: Look for 20-30 candles of sideways movement after a trend.
2. **Define Original Consolidation (OC)**: Identify the very first High and Low peaks that formed the box after the initial price run.
3. **Analyze Breakout**: Watch for price leaving the box. Anticipate a "False Breakout" (Turtle Soup).
4. **Wait for Re-entry**: A trade is ONLY valid if a candle closes BACK INSIDE the OC box.
5. **Confirmation**:
    - Candlestick pattern at the Low/Mid/High lines.
    - OR "Price Stretch": Price reaching the Middle (Fibo 0.5) line immediately after re-entry.
6. **Execution**: If confirmed, issue a BUY_LIMIT or SELL_LIMIT at the specific confirmed line.
7. **Exit Targets**:
    - TP: Exactly 1x the box distance on the opposite side.
    - SL: Exactly 1x the box distance on the breakout side.

### OUTPUT REQUIREMENTS:
You must reply STRICTLY in JSON format. Use the following schema:
{{
  "signal": "BUY_LIMIT", // strictly "BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT", or "HOLD"
  "limit_price": 0.0, // Specific entry price (Fibo 0, 0.5, or 1)
  "box_high": 0.0, // High of the Original Consolidation box
  "box_low": 0.0,  // Low of the Original Consolidation box
  "confidence": 85, // integer from 0 to 100
  "reason": "Detailed explanation of which stage (1-7) we are currently in"
}}
"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}
        }

        fallback_models = [model, 'gemini-2.0-flash', 'gemini-flash-lite-latest', 'gemini-2.5-pro']
        for attempt in range(3):
            current_model = fallback_models[attempt] if attempt < len(fallback_models) else model
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
            try:
                r = requests.post(url, json=payload, timeout=20)
                if r.status_code == 200:
                    resp = r.json()
                    text = resp['candidates'][0]['content']['parts'][0]['text']
                    
                    text = text.strip('` \n')
                    if text.startswith('json'): text = text[4:].strip()
                    
                    data = json.loads(text)
                    return data
                elif r.status_code == 503:
                    if attempt < 2:
                        print(f"[{symbol}] Gemini {current_model} High Demand (503). Retrying with backup AI... ({attempt+1}/3)")
                        time.sleep(2)
                else:
                    print(f"⚠️ AI Trade Decision API Error: {r.status_code} - {r.text}")
                    break
            except Exception as e:
                print(f"⚠️ AI Trade Decision Exception: {e}")
                if attempt < 2: time.sleep(2)
                
        return None

    def get_ai_market_analysis(self, symbol, ctx):
        api_key = getattr(config, 'AI_API_KEY', '')
        if not api_key: return "ไม่สามารถติดต่อ AI ได้ (ไม่มี API Key)"
        try:
            prompt = (f"วิเคราะห์ {symbol}: ราคา={ctx['price']:.2f}, RSI={ctx['rsi']:.1f}, "
                      f"MACD={ctx['macd']:.4f}, Trend={ctx['trend']}, Profit=${ctx['profit']:.2f}, "
                      f"Session={ctx['session']}\n"
                      f"ตอบเป็นภาษาไทย สรุปสั้น 2-3 บรรทัด และบังคับใส่ [TP_BIAS: AGGRESSIVE|NORMAL|CONSERVATIVE] แทรกมาท้ายสุดเพื่อกำหนดเป้า")
                      
            model = getattr(config, 'AI_MODEL', 'gemini-2.5-flash')
            if '3.1-pro' in model and 'preview' not in model: model = 'gemini-3.1-pro-preview'
            elif '1.5-pro' in model: model = 'gemini-2.5-pro'
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            
            import time
            for attempt in range(3):
                payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.5}}
                r = requests.post(url, json=payload, timeout=20)
                
                if r.status_code == 200:
                    resp = r.json()
                    text = resp.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                    if not text: return "AI ไม่ตอบสนองเนื้อหา"
                    mul  = 1.8 if "AGGRESSIVE" in text else (0.7 if "CONSERVATIVE" in text else 1.2)
                    self.symbol_tp_multipliers[symbol] = mul
                    self.symbol_tp_multiplier_expire[symbol] = datetime.now() + timedelta(minutes=30)
                    return text
                elif r.status_code == 503:
                    if attempt < 2: time.sleep(5)
                else:
                    return f"⚠️ Gemini API Error: {r.status_code} - {r.text}"
            return "⚠️ Gemini API Error: 503 - Server Overloaded"
        except Exception as e:
            msg = f"⚠️ AI Analysis Error ({symbol}): {str(e)}"
            print(f"\n{msg}")
            if time.time() - getattr(self, '_last_ai_err_notify', 0) > 21600:
                self.notify(f"🤖 AI Endpoint Unreachable (Gemini)\nError: {str(e)[:100]}", telegram=True)
                self._last_ai_err_notify = time.time()
            return f"AI Error: {e}"

    def _run_ai_bg(self, symbol, ctx):
        try:
            self.ai_in_progress[symbol] = True
            text = self.get_ai_market_analysis(symbol, ctx)
            self.notify(f"🤖 *[AI/{symbol}]*\n{text}", telegram=False)
        except Exception as e: print(f"⚠️ AI bg error: {e}")
        finally: self.ai_in_progress[symbol] = False

    def check_layer_basket_and_zone_sl(self, symbol, smc_zone, atr_val):
        s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        scalp_pos = [p for p in (mt5.positions_get(symbol=symbol) or []) if p.magic == config.MAGIC_NUMBER]
        if not scalp_pos: return
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return

        total_profit = sum(p.profit + p.swap for p in scalp_pos)
        tp_per_order = s_cfg.get('layer_basket_tp_per_order_usd', 2.5)
        basket_tp = len(scalp_pos) * tp_per_order

        if total_profit >= basket_tp:
            self.notify(f"🎯 *[LAYER/{symbol}] Basket TP ${total_profit:.2f}!* (เป้า ${basket_tp:.2f}) ปิด {len(scalp_pos)} ไม้...")
            self._close_all_scalp(symbol, scalp_pos, tick, reason="LAYER_BASKET_TP")
            return

        df = self.get_data(symbol, mt5.TIMEFRAME_M15, 200)
        if df is None: return
        rh  = df['high'].rolling(50).max().iloc[-1]
        rl  = df['low'].rolling(50).min().iloc[-1]
        eq  = (rh + rl) / 2
        mid = (tick.ask + tick.bid) / 2
        buf = atr_val  

        directions = set('BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL' for p in scalp_pos)
        if len(scalp_pos) > 1 or getattr(self, 'global_recovery_active', False): return

        zone_violated = False
        reason_str    = ""

        if 'BUY' in directions:
            discount_boundary = eq - (eq - rl) * 0.2
            if mid < discount_boundary - buf:
                zone_violated = True
                reason_str = f"Price {mid:.2f} broke Discount {discount_boundary:.2f}-ATR vs BUY stack"

        if 'SELL' in directions:
            premium_boundary = eq + (rh - eq) * 0.2
            if mid > premium_boundary + buf:
                zone_violated = True
                reason_str = f"Price {mid:.2f} broke Premium {premium_boundary:.2f}+ATR vs SELL stack"

        if zone_violated:
            self.notify(f"🚨 *[ZONE_SL/{symbol}]* Zone break! {reason_str}\nปิด {len(scalp_pos)} ไม้ | Float: ${total_profit:.2f}")
            self._close_all_scalp(symbol, scalp_pos, tick, reason="ZONE_SL")

    def _close_all_scalp(self, symbol, positions, tick, reason="BASKET"):
        failed = []
        for pos in positions:
            close_type  = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            res = mt5.order_send({"action":mt5.TRADE_ACTION_DEAL,"symbol":symbol,"volume":pos.volume,"type":close_type,
                                  "position":pos.ticket,"price":float(close_price),"deviation":30,"magic":pos.magic,
                                  "comment":reason,"type_time":mt5.ORDER_TIME_GTC,"type_filling":mt5.ORDER_FILLING_FOK})
            if not (res and res.retcode == mt5.TRADE_RETCODE_DONE): failed.append(pos.ticket)
        if failed: print(f"⚠️ [{symbol}] {reason}: ปิดไม่ได้ tickets {failed}")
        else: self.last_close_time[symbol] = datetime.now()

    def run(self):
        if not self.init_mt5(): return
        database.setup_db()
        self.notify(f"🚀 *[EA v4 Intraday Edition Online]*\nSymbol:{config.SYMBOLS} | Risk:{config.RISK_PERCENT}% | "
                    f"Hedge:{'ON' if getattr(config,'ENABLE_HEDGE',True) else 'OFF'} | "
                    f"Mart:{'ON' if getattr(config,'ENABLE_MARTINGALE',False) else 'OFF'}")

        loop = 0
        self.last_15m_pnl_report = datetime.now()
        self.last_recovery_notify_time = datetime.now() - timedelta(minutes=15)
        while True:
            try:
                loop += 1
                
                now = datetime.now()
                if (now - self.last_15m_pnl_report).total_seconds() >= 900:
                    self.last_15m_pnl_report = now
                    self.send_15m_open_positions_report()

                if loop % 5 == 0:
                    if self.check_telegram_commands():
                        self.notify("🚨 *[KILL SWITCH]* ได้รับคำสั่ง /CLOSEALL! กำลังบังคับปิดทุกออเดอร์...")
                        self.close_all_positions(reason="TELEGRAM_KILL_SWITCH")
                        self.global_recovery_active = True
                        try: database.set_bot_setting("global_recovery_active", True)
                        except: pass
                        continue
                        
                if loop % 60 == 1:
                    if not self.ensure_mt5_connected():
                        print("\n❌ MT5 Disconnected — Waiting for reconnect...")
                        time.sleep(10)
                        continue

                if getattr(config, 'ENABLE_WEEKEND_CLOSE', True):
                    now = datetime.now()
                    if now.weekday() == 4 and now.hour == 22 and now.minute < 5 and loop % 10 == 1:
                        self.close_all_positions(reason="Weekend_Close")
                        continue
                    if now.weekday() in [5, 6] and loop % 120 == 1:
                        self.close_all_positions(reason="Weekend_Close")
                        continue

                try:
                    acc = mt5.account_info()
                    if acc:
                        dd = (acc.equity - acc.balance) / acc.balance * 100
                        trig = -abs(getattr(config,'RECOVERY_TRIGGER_PERCENT',10.0))
                        if dd <= trig and not self.global_recovery_active:
                            self.global_recovery_active = True
                            try: database.set_bot_setting("global_recovery_active", True)
                            except: pass
                            
                        # Notify about drawdown independently of status for transparency, but throttled
                        if dd <= trig:
                            last_n = getattr(self, 'last_recovery_notify_time', datetime.min)
                            if (datetime.now() - last_n).total_seconds() >= getattr(config, 'ICT_RECOVERY_INTERVAL', 900):
                                self.notify(f"⚠️ *[EMERGENCY]* พอร์ตติดลบ *{dd:.1f}%* → { 'Global Recovery ON' if self.global_recovery_active else 'Monitoring'}")
                                self.last_recovery_notify_time = datetime.now()
                except Exception as e:
                    print(f"⚠️ Global Drawdown Check Error: {e}")

                self.run_global_recovery_exit()

                for symbol in config.SYMBOLS:
                    if not mt5.symbol_select(symbol, True):
                        print(f"\n❌ [{symbol}] ไม่พบใน MT5"); continue

                    all_pos = mt5.positions_get(symbol=symbol) or []
                    s_magic = config.MAGIC_NUMBER; g_magic = config.GRID_MAGIC_NUMBER
                    our_pos  = [p for p in all_pos if p.magic in (s_magic, g_magic)]
                    open_cnt = sum(1 for p in our_pos if p.magic == s_magic)

                    if our_pos:
                        df_t = self.get_data(symbol, mt5.TIMEFRAME_M15, 50)
                        if df_t is not None:
                            df_t = self.add_indicators(df_t)
                            atr_t= df_t.iloc[-1]['atr']
                            for pos in our_pos:
                                if pos.magic == s_magic:
                                    if getattr(config,'ENABLE_TRAILING_STOP',False): self.manage_trailing_stop(symbol, pos, atr_t)
                                    if getattr(config,'ENABLE_HEDGE',True): self.check_and_trigger_hedge(symbol, pos, atr_t)

                    self.check_virtual_sl()

                    if open_cnt > 0:
                        try:
                            _df_z = self.get_data(symbol, mt5.TIMEFRAME_M15, 200)
                            _atr_z = atr_t if 'atr_t' in dir() else (self.add_indicators(_df_z).iloc[-1]['atr'] if _df_z is not None else 0.01)
                            _rh = _df_z['high'].rolling(50).max().iloc[-1]
                            _rl = _df_z['low'].rolling(50).min().iloc[-1]
                            _eq = (_rh + _rl) / 2
                            _tk = mt5.symbol_info_tick(symbol)
                            _mid = (_tk.ask + _tk.bid) / 2 if _tk else 0
                            _z = ("Premium" if _mid > _eq + (_rh - _eq) * 0.2 else ("Discount" if _mid < _eq - (_eq - _rl) * 0.2 else "Equilibrium"))
                            self.check_layer_basket_and_zone_sl(symbol, _z, _atr_z)
                        except Exception as _e: pass

                    self.check_and_update_db(symbol)
                    if self.global_recovery_active: continue

                    if symbol == "XAUUSDc" and getattr(config, 'ENABLE_GOLD_SESSION_FILTER', False):
                        now_hour = datetime.now().hour
                        if now_hour in getattr(config, 'GOLD_DISALLOW_HOURS', []):
                            print(f"\r[{symbol}] 🚫 Forbidden Hour {now_hour}     ", end="", flush=True); continue

                    lc = self.last_close_time.get(symbol)
                    if lc:
                        diff = (datetime.now()-lc).total_seconds()/60
                        cd_m = getattr(config,'POST_TRADE_COOLDOWN_MINUTES',5)
                        if diff < cd_m:
                            print(f"\r[{symbol}] ⏳ Cooldown {int((cd_m-diff)*60)}s     ", end="", flush=True); continue

                    m15d = self.get_m15_market_state(symbol)
                    (signals, rsi, ema_dist, atr_val, pattern, volatility, dow,
                     macd, bb_pos, smc_fvg, smc_zone, session,
                     rel_vol, xau_str, usd_str, fvg_entry, b_high, b_low,
                     ote_zone, sd_targets) = m15d

                    if rsi is None or atr_val is None:
                        print(f"\r[{symbol}] ⏳ รอ Data M15...     ", end="", flush=True); continue

                    h4=self.get_h4_trend(symbol); h1=self.get_h1_trend(symbol); m30=self.get_m30_trend(symbol)
                    vol_ok = rel_vol > 1.1

                    self.run_grid(symbol, atr_val=atr_val)

                    s_cfg      = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
                    max_orders = s_cfg.get('max_scalp_orders',2)
                    if open_cnt >= max_orders:
                        self.log_throttled(f"⛔ Max Orders {open_cnt}/{max_orders}", symbol, throttle_sec=120)
                        continue

                    if getattr(config,'ENABLE_NEWS_FILTER',False) and self.check_news_forexfactory():
                        print(f"\r[{symbol}] 📰 ข่าวแดง USD     ", end="", flush=True); continue
                    if not self.check_time_filter():
                        print(f"\r[{symbol}] ⏰ นอกเวลา     ", end="", flush=True); continue

                    ai_mode = getattr(config, 'ENABLE_AI_TRADING_MODE', False)
                    if not hasattr(self, 'ai_last_decision_time'): self.ai_last_decision_time = {}
                    if not hasattr(self, 'ai_cached_signal'): self.ai_cached_signal = {}

                    if ai_mode:
                        if (datetime.now() - self.ai_last_decision_time.get(symbol, datetime.min)).total_seconds() > 840:
                            print(f"\n[{symbol}] 🤖 กำลังถาม AI (Gemini) กรุณารอสักครู่...")
                            tk = mt5.symbol_info_tick(symbol)
                            
                            df_h1_ctx = self.get_data(symbol, mt5.TIMEFRAME_H1, 50)
                            if df_h1_ctx is not None and not df_h1_ctx.empty:
                                ctx_h, ctx_l = df_h1_ctx['high'].max(), df_h1_ctx['low'].min()
                            else: ctx_h, ctx_l = b_high, b_low
                            
                            ote_62, ote_705, ote_79 = ote_zone
                            sd_2_0, sd_2_5 = sd_targets
                            
                            ctx = (f"Price: {(tk.ask+tk.bid)/2:.2f}, RSI: {rsi:.1f}, MACD: {macd:.4f}, Trend (H4:{h4}, H1:{h1}, M30:{m30}), Zone: {smc_zone}, "
                                   f"FVG: {smc_fvg} @ {fvg_entry:.2f}, H1 Fibo/Swing(H:{ctx_h:.2f}, L:{ctx_l:.2f}), "
                                   f"OTE Zone(62%:{ote_62:.2f}, 70.5%:{ote_705:.2f}, 79%:{ote_79:.2f}), "
                                   f"SD Extensions(2.0:{sd_2_0:.2f}, 2.5:{sd_2_5:.2f}), "
                                   f"PA Pattern: {pattern}, Volatility: {volatility:.2f}, RelVol: {rel_vol:.2f}\n"
                                   f"*Playbook 1 (Consolidation): Sweep liquidity out of box -> wait for Pullback back inside -> limit entry.\n"
                                   f"*Playbook 2 (Trend OTE): Identify strong impulsive move -> wait for retracement to OTE zone (0.62-0.79) -> confluence with FVG/OB -> target SD 2.0/2.5.")
                                   
                            ai_resp = self.get_ai_trade_decision(symbol, ctx)
                            self.ai_last_decision_time[symbol] = datetime.now()
                            if ai_resp and 'signal' in ai_resp:
                                self.ai_cached_signal[symbol] = ai_resp
                                print(f"[{symbol}] 🤖 AI Decision: {ai_resp['signal']} (Conf: {ai_resp.get('confidence')}%) - {ai_resp.get('reason')}")
                            else:
                                print(f"[{symbol}] ⚠️ AI Fallback: Stop Trading (Error or No Response)")
                                self.ai_cached_signal[symbol] = {"signal": "HOLD", "reason": "AI Error"}

                        cached = self.ai_cached_signal.get(symbol, {"signal":"HOLD"})
                        conf = cached.get('confidence', 0)
                        threshold = getattr(config, 'AI_CONFIDENCE_THRESHOLD', 70)
                        
                        signals = []
                        raw_sig = cached.get('signal', 'HOLD')
                        limit_price = float(cached.get('limit_price', 0.0))
                        
                        if 'BUY' in raw_sig and conf >= threshold: signals.append(raw_sig)
                        if 'SELL' in raw_sig and conf >= threshold: signals.append(raw_sig)

                    direction = None
                    is_limit_order = False
                    for sig in ('BUY','SELL','BUY_LIMIT','SELL_LIMIT'):
                        if sig not in signals: continue
                        if ai_mode:
                            ok, reason = True, self.ai_cached_signal.get(symbol, {}).get('reason', 'AI Logic')
                        else:
                            base_dir = 'BUY' if 'BUY' in sig else 'SELL'
                            ok, reason = self._validate_entry(symbol, base_dir, rsi, macd, h4, h1, m30, smc_zone, vol_ok, volatility)
                        
                        if ok: 
                            direction = 'BUY' if 'BUY' in sig else 'SELL'
                            is_limit_order = 'LIMIT' in sig
                            break
                        print(f"\r[{symbol}] ❌ {sig} rejected: {reason}     ", end="", flush=True)

                    if direction:
                        now_cnt = self.count_open_orders(symbol)
                        if now_cnt < max_orders:
                            b_high = float(cached.get('box_high', 0.0))
                            b_low  = float(cached.get('box_low', 0.0))
                            target_tp = float(cached.get('profit_target', 0.0))
                            
                            if is_limit_order and limit_price > 0:
                                p_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == 'BUY' else mt5.ORDER_TYPE_SELL_LIMIT
                                ticket = self.execute_trade(symbol, direction, atr_val, order_index=now_cnt+1, 
                                                           smc_zone=smc_zone, pending_type=p_type, pending_price=limit_price,
                                                           box_high=b_high, box_low=b_low, manual_tp=target_tp)
                            else:
                                ticket = self.execute_trade(symbol, direction, atr_val, order_index=now_cnt+1, 
                                                           smc_zone=smc_zone, box_high=b_high, box_low=b_low, manual_tp=target_tp)
                                
                            if ticket:
                                self.mart_state.pop(symbol, None)
                                sm = {"Asian":0,"London":1,"NY":2,"Overlap":3}
                                vsl = self.virtual_sl_cache.get(ticket, 0.0)
                                database.log_trade(ticket, datetime.now(), symbol, m30 or "N/A", h1 or "N/A",
                                                   smc_fvg, smc_zone, ",".join(signals), direction,
                                                   rsi, macd, bb_pos, ema_dist, datetime.now().hour,
                                                   dow, pattern, volatility, 0.0, "PENDING",
                                                   config.MT5_LOGIN, sm.get(session,0), rel_vol, xau_str, usd_str, vsl)

                    self.place_pending_orders(symbol, signals, atr_val, smc_fvg, fvg_entry, b_high, b_low)

                    last_ai = self.last_ai_report_time.get(symbol, datetime.now()-timedelta(hours=5))
                    if (datetime.now()-last_ai).total_seconds() >= 3600 and not self.ai_in_progress.get(symbol):
                        _,_,gf = self.get_grid_positions(symbol)
                        tk = mt5.symbol_info_tick(symbol)
                        if tk:
                            self.executor.submit(self._run_ai_bg, symbol, {
                                "price":(tk.ask+tk.bid)/2,"rsi":rsi,"macd":macd,
                                "trend":f"H4:{h4}/H1:{h1}/M30:{m30}","profit":gf,"session":session})
                        self.last_ai_report_time[symbol] = datetime.now()

                    h1i="🟢" if h1=='UP' else "🔴"
                    m15i="🟢" if 'BUY' in signals else ("🔴" if 'SELL' in signals else "⚪")
                    vi="🔥" if vol_ok else "❄️"
                    zi={"Premium":"🔴","Discount":"🟢","Equilibrium":"⚪"}.get(smc_zone,"⚪")
                    hs = "🛡️" if self.hedge_state.get(symbol,{}).get('hedge_ticket') else ""
                    ms = f"M{self.mart_state.get(symbol,{}).get('level',0)}" if self.mart_state.get(symbol) else ""
                    st = f"[{symbol}] {h1i}H1 {m15i}M15 | RSI:{rsi:.0f} {zi}{smc_zone} | Vol:{rel_vol:.1f}{vi}{hs}{ms}"

                    if loop % 10 == 1: print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {st}")
                    else: print(f"\r{st} L{loop}     ", end="", flush=True)

                    if (datetime.now()-self.last_summary_time).total_seconds() >= 14400:
                        if self.send_performance_report():
                            self.last_summary_time = datetime.now()

            except Exception as e:
                print(f"\n❌ [CRITICAL_ERROR] Loop Break: {e}")
                time.sleep(10)
                continue

            time.sleep(5)

if __name__ == "__main__":
    ea = SelfLearningEA()
    try:
        ea.run()
    except KeyboardInterrupt:
        print("\nEA Stopped.")
        mt5.shutdown()