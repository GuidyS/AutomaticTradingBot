import sys
import io

# Fix: รองรับ emoji ใน Windows terminal (cp1252 → utf-8)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import MetaTrader5 as mt5
import pandas as pd
import time
import os
import pickle
import requests
from math import floor
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor
import config
import database


class SelfLearningEA:
    def __init__(self):
        self.model_cat = None
        self.model_rf = None
        self.model_last_modified = 0
        self.usd_news_today = False
        self.last_news_check = ""
        self.last_summary_time = datetime.now() - timedelta(hours=11.9)
        self.last_ai_report_time = {}
        self.ai_in_progress = {}
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.grid_last_open_time = {}
        self.grid_safety_triggered = {}
        self.symbol_tp_multipliers = {}
        self.last_close_time = {}
        self.acc_scalp_profit = {}

        # [P4] Win Rate Tracking: {symbol: {'SCALP': {'wins':0,'losses':0}, 'GRID': {...}}}
        self.trade_stats = {}
        
        # [P4] Virtual SL Cache: {ticket: sl_price}
        self.virtual_sl_cache = {}

        # [P4] Smart Recovery State: {symbol: bool}
        self.recovery_active = {}
        self.global_recovery_active = False  # จะโหลดจริงใน init_mt5 หรือภายหลัง

    # =========================================================
    # [P4] Win Rate Tracking Helpers
    # =========================================================

    def _init_stats(self, symbol):
        if symbol not in self.trade_stats:
            self.trade_stats[symbol] = {
                'SCALP': {'wins': 0, 'losses': 0, 'gross_profit': 0.0, 'gross_loss': 0.0},
                'GRID':  {'wins': 0, 'losses': 0, 'gross_profit': 0.0, 'gross_loss': 0.0},
            }

    def _record_trade(self, symbol, trade_type, profit):
        """บันทึกผลการเทรดแยก SCALP/GRID"""
        self._init_stats(symbol)
        t = trade_type if trade_type in ('SCALP', 'GRID') else 'SCALP'
        s = self.trade_stats[symbol][t]
        if profit >= 0:
            s['wins'] += 1
            s['gross_profit'] += profit
        else:
            s['losses'] += 1
            s['gross_loss'] += abs(profit)

    def get_stats_summary(self, symbol):
        """คืนค่า string สรุปผล win rate แยก SCALP/GRID"""
        self._init_stats(symbol)
        lines = [f"📊 *[Stats/{symbol}]*"]
        for t in ('SCALP', 'GRID'):
            s = self.trade_stats[symbol][t]
            total = s['wins'] + s['losses']
            if total == 0:
                lines.append(f"  {t}: ยังไม่มีข้อมูล")
                continue
            wr = (s['wins'] / total) * 100
            net = s['gross_profit'] - s['gross_loss']
            avg_win  = s['gross_profit'] / s['wins']  if s['wins']   > 0 else 0
            avg_loss = s['gross_loss']   / s['losses'] if s['losses'] > 0 else 0
            rr = (avg_win / avg_loss) if avg_loss > 0 else 0
            lines.append(
                f"  {t}: W{s['wins']}/L{s['losses']} | WR:{wr:.1f}% | "
                f"Net:${net:.2f} | RR:{rr:.2f} | AvgW:${avg_win:.2f} AvgL:${avg_loss:.2f}"
            )
        return "\n".join(lines)

    # =========================================================
    # MT5 Init & Model Loading
    # =========================================================

    def init_mt5(self):
        if not mt5.initialize():
            print("MT5 Initialization failed. Make sure MT5 is installed and open.")
            return False
        authorized = mt5.login(
            config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER
        )
        if authorized:
            print(f"✅ Successfully connected to MT5 Account: {config.MT5_LOGIN}")
            # [P4] Sync Virtual SLs from Database
            self.load_virtual_sls_from_db()
            
            # [P4] Load Global Recovery State
            self.global_recovery_active = database.get_bot_setting("global_recovery_active", False)
            if self.global_recovery_active:
                print("⚠️ [RECOVERY] Portfolio is currently in Global Recovery Mode (Loaded from DB)")
            
            return True
        else:
            print(f"🔴 MT5 Login Failed: {mt5.last_error()}")
            return False

    def load_virtual_sls_from_db(self):
        """[NEW] ดึง Virtual SL ของออเดอร์ที่ยังไม่ปิดมาเก็บไว้ใน Cache"""
        try:
            conn = database.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT ticket, virtual_sl FROM trades WHERE result = 'PENDING' AND virtual_sl > 0")
            rows = cursor.fetchall()
            for ticket, sl in rows:
                self.virtual_sl_cache[int(ticket)] = float(sl)
            print(f"🔄 [P4] Synced {len(rows)} Virtual SLs from DB.")
            conn.close()
        except Exception as e:
            print(f"🔴 Error syncing Virtual SLs: {e}")

    def load_model(self):
        """Hot-Swap โหลด 2 โมเดลเข้ามาเช็คเงื่อนไขพร้อมกัน"""
        if os.path.exists(config.CAT_MODEL_PATH) and os.path.exists(config.RF_MODEL_PATH):
            mod_time = os.path.getmtime(config.CAT_MODEL_PATH)
            if mod_time > self.model_last_modified:
                try:
                    with open(config.CAT_MODEL_PATH, 'rb') as f:
                        self.model_cat = pickle.load(f)
                    with open(config.RF_MODEL_PATH, 'rb') as f:
                        self.model_rf = pickle.load(f)
                    self.model_last_modified = mod_time
                    print(f"[{datetime.now()}] 🔄 Models Reloaded (CatBoost + RF Hot-Swap Success).")
                except Exception as e:
                    print(f"Error loading models: {e}")

    # =========================================================
    # News & Notifications
    # =========================================================

    def check_news_forexfactory(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        if self.last_news_check == date_str:
            return self.usd_news_today
        try:
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                news_data = response.json()
                today_news = [n for n in news_data if n['country'] == 'USD' and n['impact'] == 'High' and date_str in n['date']]
                self.usd_news_today = len(today_news) > 0
                self.last_news_check = date_str
                print(f"📰 News Filter Check: High Impact USD News Today = {self.usd_news_today}")
                return self.usd_news_today
        except Exception as e:
            print(f"Error checking news (using default=False): {e}")
        return False

    def send_line_message(self, message):
        if hasattr(config, 'LINE_CHANNEL_ACCESS_TOKEN') and config.LINE_CHANNEL_ACCESS_TOKEN and \
           hasattr(config, 'LINE_USER_ID') and config.LINE_USER_ID:
            user_ids = [uid.strip() for uid in str(config.LINE_USER_ID).split(',') if uid.strip()]
            if not user_ids:
                return
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}"}
            try:
                for uid in user_ids:
                    url = "https://api.line.me/v2/bot/message/push"
                    data = {"to": uid, "messages": [{"type": "text", "text": message}]}
                    requests.post(url, headers=headers, json=data, timeout=10)
            except Exception as e:
                print(f"🔴 LINE Exception: {e}")

    def send_telegram_message(self, message):
        if hasattr(config, 'TELEGRAM_BOT_TOKEN') and config.TELEGRAM_BOT_TOKEN and \
           hasattr(config, 'TELEGRAM_CHAT_ID') and config.TELEGRAM_CHAT_ID:
            import re
            html_msg = message
            html_msg = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_msg)
            html_msg = re.sub(r'\*(.*?)\*', r'<b>\1</b>', html_msg)
            html_msg = re.sub(r'`(.*?)`', r'<code>\1</code>', html_msg)
            html_msg = html_msg.replace('[', '(').replace(']', ')')
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {"chat_id": config.TELEGRAM_CHAT_ID, "text": html_msg, "parse_mode": "HTML"}
            try:
                res = requests.post(url, json=data, timeout=10)
                if res.status_code != 200:
                    print(f"🔴 Telegram Error ({res.status_code}): {res.text}")
                else:
                    print(f"📡 Telegram Sent.")
            except Exception as e:
                print(f"🔴 Telegram Exception: {e}")

    def notify(self, message):
        clean_msg = message.replace('*', '')
        print(f"\n📢 [NOTIFY]: {clean_msg}")
        self.send_line_message(message)
        self.send_telegram_message(message)

    def send_performance_report(self):
        """สรุปผลงาน 12h + win rate แยก SCALP/GRID"""
        stats = database.get_performance_summary(hours=12)
        lines = []
        if stats:
            lines.append(
                f"📊 *[Report - 12h Performance Summary]*\n"
                f"💰 กำไรสุทธิ: *{stats['net_profit']:.2f}$*\n"
                f"📈 ชนะ: {stats['wins']} | แพ้: {stats['losses']}\n"
                f"🎯 Win Rate: *{stats['win_rate']:.1f}%*\n"
                f"Total Trades: {stats['total']}"
            )
        # [P4] เพิ่ม stats แยก SCALP/GRID
        for symbol in config.SYMBOLS:
            lines.append(self.get_stats_summary(symbol))

        if lines:
            msg = "\n\n".join(lines) + "\n\nบอทจะสรุปผลให้คุณทราบทุกๆ 4 ชม. ครับ 🚀"
            self.notify(msg)
            return True
        return False

    # =========================================================
    # AI Market Analysis
    # =========================================================

    def get_ai_market_analysis(self, symbol, context_data):
        try:
            url = "http://localhost:11434/api/generate"
            prompt = (
                f"คุณคือผู้เชี่ยวชาญการเทรดช่วยวิเคราะห์คู่เงิน {symbol} จากข้อมูลปัจจุบันดังนี้:\n"
                f"- ราคาปัจจุบัน: {context_data['price']}\n"
                f"- RSI (M5): {context_data['rsi']:.1f}\n"
                f"- MACD Diff: {context_data['macd']:.4f}\n"
                f"- เทรนด์ (H1/M30): {context_data['trend']}\n"
                f"- กำไร/ขาดทุนรวมปัจจุบัน: ${context_data['profit']:.2f}\n"
                f"- ช่วงเวลาตลาด: {context_data['session']}\n\n"
                f"ช่วยสรุปสั้นๆ เป็นภาษาไทย 2-3 บรรทัดว่าสภาวะเป็นอย่างไร และควรระวังอะไรบ้าง?\n"
                f"⚠️ สำคัญมาก: ในบรรทัดสุดท้ายกรุณาใส่รหัสลับดังนี้:\n"
                f"- สำหรับสภาวะเทรนด์แรง: [TP_BIAS: AGGRESSIVE]\n"
                f"- สำหรับสภาวะปกติ: [TP_BIAS: NORMAL]\n"
                f"- สำหรับสภาวะผันผวน/พักตัว: [TP_BIAS: CONSERVATIVE]"
            )
            payload = {
                "model": "gemma4:latest",
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 250, "temperature": 0.5}
            }
            print(f"\n--- [AI PROMPT / {symbol}] ---\n{prompt}\n---------------------------")
            response = requests.post(url, json=payload, timeout=300)
            if response.status_code == 200:
                result = response.json()
                ai_text = result.get('response', '')
                print(f"DEBUG: AI Response received ({len(ai_text)} chars)")
                multiplier = 1.0
                if "[TP_BIAS: AGGRESSIVE]"   in ai_text: multiplier = 1.8
                elif "[TP_BIAS: CONSERVATIVE]" in ai_text: multiplier = 0.7
                elif "[TP_BIAS: NORMAL]"       in ai_text: multiplier = 1.2
                self.symbol_tp_multipliers[symbol] = multiplier
                print(f"🤖 [AI/{symbol}] Updated TP Multiplier: {multiplier}x")
                return ai_text if ai_text else 'ไม่สามารถดึงบทวิเคราะห์ได้'
            return "AI ไม่ตอบสนอง (ตรวจสอบ Ollama)"
        except Exception as e:
            return f"AI Error: {e}"

    def _run_ai_in_background(self, symbol, context_data):
        try:
            self.ai_in_progress[symbol] = True
            ai_view = self.get_ai_market_analysis(symbol, context_data)
            report = f"🤖 *[AI Market Insight - {symbol}]*\n\n{ai_view}"
            self.notify(report)
            print(f"✅ AI Analysis for {symbol} Completed in background.")
        except Exception as e:
            print(f"⚠️ Background AI Task Error ({symbol}): {e}")
        finally:
            self.ai_in_progress[symbol] = False

    # =========================================================
    # Time & Data Helpers
    # =========================================================

    def check_time_filter(self):
        current_hour = datetime.now().hour
        return config.TRADE_TIME_START <= current_hour <= config.TRADE_TIME_END

    def get_data(self, symbol, timeframe, n=100):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def calculate_atr(self, df, period=14):
        high_low    = df['high'] - df['low']
        high_close  = (df['high'] - df['close'].shift()).abs()
        low_close   = (df['low']  - df['close'].shift()).abs()
        ranges      = pd.concat([high_low, high_close, low_close], axis=1)
        true_range  = ranges.max(axis=1)
        return true_range.rolling(period).mean()

    def check_candlestick_pattern(self, df):
        if len(df) < 2:
            return "None"
        row      = df.iloc[-1]
        prev_row = df.iloc[-2]
        body        = abs(row['close'] - row['open'])
        upper_wick  = row['high'] - max(row['close'], row['open'])
        lower_wick  = min(row['close'], row['open']) - row['low']
        if body <= (row['high'] - row['low']) * 0.1:
            return "Doji"
        elif lower_wick > body * 2 and upper_wick < body * 0.5:
            return "Pinbar_Bull"
        elif upper_wick > body * 2 and lower_wick < body * 0.5:
            return "Pinbar_Bear"
        elif row['close'] > prev_row['open'] and row['open'] < prev_row['close'] and \
             row['close'] > row['open'] and prev_row['close'] < prev_row['open']:
            return "Engulfing_Bull"
        elif row['close'] < prev_row['open'] and row['open'] > prev_row['close'] and \
             row['close'] < row['open'] and prev_row['close'] > prev_row['open']:
            return "Engulfing_Bear"
        return "None"

    def get_market_session(self):
        hour = datetime.now().hour
        if 0  <= hour < 7:  return "Asian"
        if 7  <= hour < 14: return "London"
        if 14 <= hour < 22: return "NY"
        return "Overlap"

    def get_currency_strength(self, symbol):
        strengths = {}
        s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        strength_pairs = s_cfg.get('strength_pairs', ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "XAUUSDc"])
        for sym in strength_pairs:
            try:
                mt5.symbol_select(sym, True)
                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 20)
                if rates is not None and len(rates) > 1:
                    change = ((rates[-1][4] - rates[0][1]) / rates[0][1]) * 100
                    strengths[sym] = round(float(change), 6)
                else:
                    strengths[sym] = 0.0
            except Exception:
                strengths[sym] = 0.0

        usd_str = 0.0
        count   = 0
        for pair, sign in [("EURUSD", -1), ("GBPUSD", -1), ("AUDUSD", -1), ("USDJPY", 1)]:
            if pair in strengths:
                usd_str += sign * strengths[pair]
                count   += 1
        if count > 0:
            usd_str /= count

        xau_str = strengths.get("XAUUSDc", strengths.get("XAUUSD", 0.0))
        return xau_str, usd_str

    # =========================================================
    # SMC Advanced Logic
    # =========================================================

    def is_swing_high(self, df, idx, lookback=5):
        if idx < lookback or idx >= len(df) - lookback:
            return False
        high_val = df.iloc[idx]['high']
        for i in range(1, lookback + 1):
            if df.iloc[idx - i]['high'] > high_val or df.iloc[idx + i]['high'] > high_val:
                return False
        return True

    def is_swing_low(self, df, idx, lookback=5):
        if idx < lookback or idx >= len(df) - lookback:
            return False
        low_val = df.iloc[idx]['low']
        for i in range(1, lookback + 1):
            if df.iloc[idx - i]['low'] < low_val or df.iloc[idx + i]['low'] < low_val:
                return False
        return True

    def find_last_swings(self, df, lookback=5):
        last_sh_idx = -1
        last_sl_idx = -1
        for i in range(len(df) - lookback - 1, lookback, -1):
            if last_sh_idx == -1 and self.is_swing_high(df, i, lookback):
                last_sh_idx = i
            if last_sl_idx == -1 and self.is_swing_low(df, i, lookback):
                last_sl_idx = i
            if last_sh_idx != -1 and last_sl_idx != -1:
                break
        return last_sh_idx, last_sl_idx

    def get_smc_structure(self, symbol, timeframe=mt5.TIMEFRAME_M30):
        df = self.get_data(symbol, timeframe, 200)
        if df is None or len(df) < 100:
            return "CHoCH", None, None
        sh_idx, sl_idx = self.find_last_swings(df)
        if sh_idx == -1 or sl_idx == -1:
            return "NEUTRAL", None, None
        last_close = df.iloc[-1]['close']
        sh_val = df.iloc[sh_idx]['high']
        sl_val = df.iloc[sl_idx]['low']
        bias   = "NEUTRAL"
        ob_zone = (None, None)
        if last_close > sh_val:
            bias = "BULL_BOS"
            for i in range(sh_idx, 0, -1):
                if df.iloc[i]['close'] < df.iloc[i]['open']:
                    ob_zone = (df.iloc[i]['high'], df.iloc[i]['low'])
                    break
        elif last_close < sl_val:
            bias = "BEAR_BOS"
            for i in range(sl_idx, 0, -1):
                if df.iloc[i]['close'] > df.iloc[i]['open']:
                    ob_zone = (df.iloc[i]['high'], df.iloc[i]['low'])
                    break
        return bias, ob_zone[0], ob_zone[1]

    def check_spread(self, symbol):
        info = mt5.symbol_info(symbol)
        if info is None:
            return False
        current_spread = info.spread
        if current_spread > config.MAX_SPREAD:
            print(f"\r[{symbol}] ❌ ข้าม: Spread สูงเกินไป ({current_spread} > {config.MAX_SPREAD})      ", end="", flush=True)
            return False
        return True

    def add_indicators(self, df):
        df['ema_14'] = df['close'].ewm(span=14, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        delta = df['close'].diff()
        gain  = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs    = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        df['atr']        = self.calculate_atr(df, config.ATR_PERIOD)
        df['volatility'] = ((df['high'] - df['low']) / df['atr']).fillna(1.0)
        exp1   = df['close'].ewm(span=12, adjust=False).mean()
        exp2   = df['close'].ewm(span=26, adjust=False).mean()
        macd_line   = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        df['macd_diff'] = macd_line - signal_line
        df['bb_mid']   = df['close'].rolling(window=20).mean()
        df['bb_std']   = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * 2)
        df['vol_sma']    = df['tick_volume'].rolling(window=20).mean()
        df['rel_volume'] = df['tick_volume'] / df['vol_sma'].replace(0, 1)
        return df

    def get_h1_trend(self, symbol):
        df = self.get_data(symbol, mt5.TIMEFRAME_H1, 100)
        if df is None:
            return None
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        return 'UP' if df.iloc[-1]['close'] > df.iloc[-1]['ema_50'] else 'DOWN'

    def get_h4_trend(self, symbol):
        """[NEW] ดึงเทรนด์จาก TF H4 เพื่อใช้เป็นเข็มทิศหลัก"""
        df = self.get_data(symbol, mt5.TIMEFRAME_H4, 100)
        if df is None:
            return None
        # ใช้ EMA 50 บน H4 เพื่อหาเมกะเทรนด์ (Mega Trend)
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        return 'UP' if df.iloc[-1]['close'] > df.iloc[-1]['ema_50'] else 'DOWN'

    def get_m30_trend(self, symbol):
        df = self.get_data(symbol, mt5.TIMEFRAME_M30, 100)
        if df is None:
            return None
        df = self.add_indicators(df)
        return 'UP' if df.iloc[-1]['close'] > df.iloc[-1]['ema_50'] else 'DOWN'

    def get_m5_market_state(self, symbol):
        df = self.get_data(symbol, mt5.TIMEFRAME_M5, 200)
        if df is None:
            return [], None, None, None, None, None, None, None, None, None, None, None, None, None, None, 0.0, 0.0, 0.0
        df = self.add_indicators(df)
        row = df.iloc[-1]

        signals = []
        if row['close'] > row['ema_14'] and row['close'] > row['ema_50'] and row['rsi_14'] < 70:
            signals.append('BUY')
        if row['close'] < row['ema_14'] and row['close'] < row['ema_50'] and row['rsi_14'] > 30:
            signals.append('SELL')

        ema_dist   = ((row['close'] - row['ema_50']) / row['ema_50']) * 100
        atr_val    = row['atr']
        volatility = row['volatility']
        pattern    = self.check_candlestick_pattern(df)
        day_of_week = datetime.now().weekday()
        macd_diff  = row['macd_diff']

        bb_position = "Middle"
        if row['close'] > row['bb_upper']:
            bb_position = "Upper"
        elif row['close'] < row['bb_lower']:
            bb_position = "Lower"

        recent_high  = df['high'].rolling(50).max().iloc[-1]
        recent_low   = df['low'].rolling(50).min().iloc[-1]
        equilibrium  = (recent_high + recent_low) / 2
        smc_zone     = "Equilibrium"
        if row['close'] > equilibrium + (recent_high - equilibrium) * 0.2:
            smc_zone = "Premium"
        elif row['close'] < equilibrium - (equilibrium - recent_low) * 0.2:
            smc_zone = "Discount"

        smc_fvg   = "None"
        fvg_entry = 0.0
        start_idx = max(len(df) - 15, 2)
        for i in range(start_idx, len(df) - 1):
            try:
                if df['high'].iloc[i - 2] < df['low'].iloc[i]:
                    mitigated = any(df['low'].iloc[j] <= df['high'].iloc[i - 2] for j in range(i + 1, len(df)))
                    if not mitigated:
                        smc_fvg   = "Bullish"
                        fvg_entry = df['low'].iloc[i]
                        break
            except (IndexError, KeyError):
                continue
            try:
                if df['low'].iloc[i - 2] > df['high'].iloc[i]:
                    mitigated = any(df['high'].iloc[j] >= df['low'].iloc[i - 2] for j in range(i + 1, len(df)))
                    if not mitigated:
                        smc_fvg   = "Bearish"
                        fvg_entry = df['high'].iloc[i]
                        break
            except (IndexError, KeyError):
                continue

        if pd.isna(row['rsi_14']) or pd.isna(ema_dist) or pd.isna(atr_val) or pd.isna(macd_diff):
            return [], 50.0, 0.0, 0.001, "None", 1.0, day_of_week, 0.0, "Middle", "None", "Equilibrium", "Asian", 1.0, 0.0, 0.0, 0.0, 0.0, 0.0

        session        = self.get_market_session()
        rel_vol        = row['rel_volume']
        xau_str, usd_str = self.get_currency_strength(symbol)
        breakout_high  = df['high'].rolling(5).max().iloc[-1]
        breakout_low   = df['low'].rolling(5).min().iloc[-1]

        return signals, row['rsi_14'], ema_dist, atr_val, pattern, volatility, day_of_week, macd_diff, bb_position, smc_fvg, smc_zone, session, rel_vol, xau_str, usd_str, fvg_entry, breakout_high, breakout_low

    # =========================================================
    # ML Prediction
    # =========================================================

    def ml_predict(self, m30_trend, h1_trend, rsi_m5, ema_dist_m5, trade_hour, day_of_week,
                   volatility, pattern, macd_diff, bb_position, smc_fvg, smc_zone,
                   session, rel_vol, xau_str, usd_str):
        if self.model_cat is None or self.model_rf is None:
            return None
        m30_val = 1 if m30_trend == 'UP' else 0
        h1_val  = 1 if h1_trend  == 'UP' else 0
        patterns_list = ["Doji", "Pinbar_Bull", "Pinbar_Bear", "Engulfing_Bull", "Engulfing_Bear", "None"]
        pat_val  = patterns_list.index(pattern)  if pattern  in patterns_list  else 5
        bb_list  = ["Upper", "Middle", "Lower"]
        bb_val   = bb_list.index(bb_position)    if bb_position in bb_list     else 1
        fvg_list = ["Bullish", "Bearish", "None"]
        fvg_val  = fvg_list.index(smc_fvg)       if smc_fvg    in fvg_list     else 2
        zone_list = ["Premium", "Discount", "Equilibrium"]
        zone_val = zone_list.index(smc_zone)      if smc_zone   in zone_list    else 2

        base_features = {
            'm30_trend_up': [m30_val], 'h1_trend_up': [h1_val],
            'rsi_m5': [rsi_m5], 'ema_dist_m5': [ema_dist_m5],
            'trade_hour': [trade_hour], 'day_of_week': [day_of_week],
            'volatility': [volatility], 'pattern_idx': [pat_val],
            'macd_diff': [macd_diff], 'bb_position_idx': [bb_val],
            'fvg_idx': [fvg_val], 'zone_idx': [zone_val],
            'session_idx': [["Asian", "London", "NY", "Overlap"].index(session) if session in ["Asian", "London", "NY", "Overlap"] else 0],
            'rel_volume': [rel_vol], 'xau_strength': [xau_str], 'usd_strength': [usd_str]
        }

        df_pred_buy  = pd.DataFrame(base_features)
        df_pred_buy['dir_buy'] = 1
        df_pred_sell = pd.DataFrame(base_features)
        df_pred_sell['dir_buy'] = 0

        try:
            cols = ['m30_trend_up', 'h1_trend_up', 'dir_buy', 'rsi_m5', 'ema_dist_m5',
                    'trade_hour', 'day_of_week', 'volatility', 'pattern_idx', 'macd_diff',
                    'bb_position_idx', 'fvg_idx', 'zone_idx', 'session_idx', 'rel_volume',
                    'xau_strength', 'usd_strength']
            df_pred_buy  = df_pred_buy[cols]
            df_pred_sell = df_pred_sell[cols]

            prob_cat_buy  = self.model_cat.predict_proba(df_pred_buy)[0][1]
            prob_rf_buy   = self.model_rf.predict_proba(df_pred_buy)[0][1]
            prob_cat_sell = self.model_cat.predict_proba(df_pred_sell)[0][1]
            prob_rf_sell  = self.model_rf.predict_proba(df_pred_sell)[0][1]

            print(f"AI Vote -> BUY: [Cat:{prob_cat_buy:.2f}, RF:{prob_rf_buy:.2f}] | SELL: [Cat:{prob_cat_sell:.2f}, RF:{prob_rf_sell:.2f}]")

            # [P4] เพิ่มเกณฑ์ความมั่นใจจาก 0.55 → 0.65 เพื่อคัดไม้คุณภาพสูง
            # หมายเหตุ: ใช้ค่า 0.65 เป็นมาตรฐานสำหรับ Scalp Signal ในส่วนอื่นๆ ด้วย
            if prob_cat_buy  > 0.65 and prob_rf_buy  > 0.65: return 'BUY'
            if prob_cat_sell > 0.65 and prob_rf_sell > 0.65: return 'SELL'
        except Exception as e:
            err_msg = str(e)
            if "feature_names mismatch" in err_msg:
                print(f"\r⚠️ AI Model Mismatch: ระบบพบฟีเจอร์ SMC ใหม่ แต่ไฟล์โมเดลเก่า...", end="", flush=True)
            else:
                print(f"\r⚠️ ML Error: {err_msg}", end="", flush=True)
        return None

    # =========================================================
    # Lot Calculation & Order Counting
    # =========================================================

    def calculate_lot(self, symbol=None, atr_val=None, risk_percent=None, fixed_sl_pips=None):
        risk_mode = config.GRID_RISK_MODE if fixed_sl_pips else config.RISK_MODE

        if risk_mode == "FIXED":
            return config.FIXED_LOT
        elif risk_mode == "PERCENT":
            account = mt5.account_info()
            if not account:
                print("⚠️ ไม่สามารถดึงข้อมูลบัญชีได้ ใช้ FIXED_LOT แทน")
                return config.FIXED_LOT
            balance = account.balance
            
            # ใช้ risk_percent ที่ส่งมา หรือใช้ค่าตามโหมด (Scalp vs Grid)
            r_pct = risk_percent if risk_percent is not None else (
                config.GRID_RISK_PERCENT if fixed_sl_pips else config.RISK_PERCENT
            )

            if symbol:
                symbol_info = mt5.symbol_info(symbol)
                s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
                if symbol_info:
                    risk_amount = balance * (r_pct / 100.0)
                    
                    # คำนวณระยะ SL: ถ้ามี fixed_sl_pips ให้ใช้ค่านั้น ถ้าไม่มีใช้ ATR
                    if fixed_sl_pips:
                        pip_size = symbol_info.point * 10
                        sl_dist  = fixed_sl_pips * pip_size
                    elif atr_val:
                        sl_dist  = atr_val * s_cfg.get('atr_sl_mul', 0.8)
                    else:
                        # กรณีไม่มีทั้งสองอย่าง ให้ใช้ Pip กลางๆ (เช่น 300 pips)
                        pip_size = symbol_info.point * 10
                        sl_dist  = 300 * pip_size

                    tick_size   = symbol_info.trade_tick_size
                    tick_value  = symbol_info.trade_tick_value
                    if tick_size > 0 and tick_value > 0:
                        sl_ticks       = sl_dist / tick_size
                        calculated_lot = risk_amount / (sl_ticks * tick_value)
                        lot_step       = symbol_info.volume_step
                        calculated_lot = round(calculated_lot / lot_step) * lot_step
                        min_lot = symbol_info.volume_min
                        max_lot = symbol_info.volume_max
                        return max(min_lot, min(calculated_lot, max_lot))
            fallback_lot = (balance / 100000.0) * (config.RISK_PERCENT * 10)
            return max(round(fallback_lot, 2), 0.01)
        return config.FIXED_LOT

    def count_open_orders(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return 0
        return sum(1 for p in positions if p.magic == config.MAGIC_NUMBER)

    def count_pending_orders(self, symbol):
        orders = mt5.orders_get(symbol=symbol)
        if not orders:
            return 0
        return sum(1 for o in orders if o.magic == config.MAGIC_NUMBER)

    # =========================================================
    # Trade Safety
    # =========================================================

    def check_trade_safety(self, symbol, direction, price, is_pending=False, is_scalp=False):
        our_magics = [
            getattr(config, 'MAGIC_NUMBER', 999999),
            getattr(config, 'GRID_MAGIC_NUMBER', 20250412)
        ]
        s_cfg = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
        min_spacing_pips = s_cfg.get('min_scalp_spacing', 50)
        sym_info = mt5.symbol_info(symbol)
        if not sym_info:
            return False
        pip_size = sym_info.point * 10
        min_dist = min_spacing_pips * pip_size
        positions = mt5.positions_get(symbol=symbol)

        if is_scalp and getattr(config, 'ENABLE_LOSS_SHAVING', False):
            opposite_count = 0
            if positions:
                for p in positions:
                    p_dir = 'BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL'
                    if p_dir != direction and p.magic == getattr(config, 'MAGIC_NUMBER', 999999):
                        opposite_count += 1
            if opposite_count >= getattr(config, 'MAX_OPPOSITE_SCALPS', 1):
                print(f"⚠️ [{symbol}] Loss Shaving: จำกัดไม้สวนทาง ({opposite_count} ไม้)")
                return False
            m30_trend = self.get_m30_trend(symbol)
            if (direction == 'BUY' and m30_trend != 'UP') or (direction == 'SELL' and m30_trend != 'DOWN'):
                print(f"⚠️ [{symbol}] Loss Shaving: เทรนด์ {m30_trend} ไม่สนับสนุน {direction}")
                return False
            print(f"✅ [{symbol}] Loss Shaving: อนุญาตให้เปิด {direction}")
        else:
            if positions:
                for p in positions:
                    existing_dir = 'BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL'
                    if existing_dir != direction:
                        print(f"⚠️ [{symbol}] GLOBAL SAFETY: สวนทางกับ {existing_dir} ที่เปิดอยู่")
                        return False

        if positions:
            for p in positions:
                if p.magic in our_magics:
                    dist = abs(p.price_open - price)
                    if dist < min_dist:
                        print(f"⚠️ [{symbol}] GLOBAL SAFETY: ใกล้ไม้เดิม ({dist/pip_size:.1f} pips)")
                        return False

        orders = mt5.orders_get(symbol=symbol)
        if orders:
            for o in orders:
                if o.magic in our_magics:
                    pending_dir = 'BUY' if o.type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP] else 'SELL'
                    if pending_dir != direction and not (is_scalp and getattr(config, 'ENABLE_LOSS_SHAVING', False)):
                        print(f"⚠️ [{symbol}] GLOBAL SAFETY: สวนทางกับ Pending {pending_dir}")
                        return False
                    dist = abs(o.price_open - price)
                    if dist < min_dist:
                        print(f"⚠️ [{symbol}] GLOBAL SAFETY: ใกล้ Pending เดิมเกินไป ({dist/pip_size:.1f} pips)")
                        return False
        return True

    # =========================================================
    # Execute Trade
    # =========================================================

    def execute_trade(self, symbol, direction, atr_val, order_index=1, pending_type=None, pending_price=0.0, structural_sl=None):
        try:
            is_scalp = not pending_type
            if not self.check_trade_safety(
                symbol, direction,
                pending_price if pending_type else (
                    mt5.symbol_info_tick(symbol).ask if direction == 'BUY'
                    else mt5.symbol_info_tick(symbol).bid
                ),
                is_scalp=is_scalp
            ):
                return None

            lot  = self.calculate_lot(symbol, atr_val)
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print(f"🔴 [{symbol}] ไม่สามารถดึง Tick ได้")
                return None

            s_cfg  = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
            ai_mul = self.symbol_tp_multipliers.get(symbol, 1.0)

            m30_trend   = self.get_m30_trend(symbol)
            h1_trend    = self.get_h1_trend(symbol)
            trend_bonus = 1.0
            if direction == 'BUY':
                if m30_trend == 'UP':   trend_bonus += 0.3
                if h1_trend  == 'UP':   trend_bonus += 0.2
            elif direction == 'SELL':
                if m30_trend == 'DOWN': trend_bonus += 0.3
                if h1_trend  == 'DOWN': trend_bonus += 0.2
            final_mul = ai_mul * trend_bonus

            if getattr(config, 'USE_FIXED_PIPS', False):
                sym_info = mt5.symbol_info(symbol)
                if sym_info is None:
                    return None
                pip_size  = sym_info.point * 10
                # [P4] ใช้ Structural SL หากมีการส่งค่ามา ถ้าไม่มีใช้ Fixed Pips ปกติ
                if structural_sl and structural_sl > 0:
                    sl = structural_sl
                    sl_dist = abs(tick.ask - sl) if direction == 'BUY' else abs(tick.bid - sl)
                else:
                    sl_dist   = s_cfg.get('scalp_sl_pips', 40)  * pip_size
                    sl = (tick.ask - sl_dist) if direction == 'BUY' else (tick.bid + sl_dist)
                
                tp_dist   = (s_cfg.get('scalp_tp_pips', 150) * pip_size) * final_mul
                mode_label = f"Dyn-Pips({final_mul:.1f}x)"
            else:
                # [P4] ATR Mode พร้อม Structural SL
                if structural_sl and structural_sl > 0:
                    sl = structural_sl
                else:
                    sl_dist = atr_val * s_cfg.get('atr_sl_mul', 0.8)
                    sl = (tick.ask - sl_dist) if direction == 'BUY' else (tick.bid + sl_dist)
                
                tp_dist   = (atr_val * s_cfg.get('atr_tp_mul', 2.5)) * final_mul
                mode_label = f"Dyn-ATR({final_mul:.1f}x)"

            if pending_type:
                order_type = pending_type
                price = pending_price
                sl = price - sl_dist if direction == 'BUY' else price + sl_dist
                tp = price + tp_dist if direction == 'BUY' else price - tp_dist
            elif direction == 'BUY':
                price      = tick.ask
                sl         = price - sl_dist
                tp         = price + tp_dist
                order_type = mt5.ORDER_TYPE_BUY
            else:
                price      = tick.bid
                sl         = price + sl_dist
                tp         = price - tp_dist
                order_type = mt5.ORDER_TYPE_SELL

            if sl <= 0 or tp <= 0:
                print(f"🔴 [{symbol}] SL/TP ไม่ถูกต้อง (SL={sl}, TP={tp})")
                return None

            comment = f"{getattr(config, 'ORDER_COMMENT', 'SMC_AI')}_{direction[0]}#{order_index}"
            
            # [P4] Virtual (Hidden) SL Logic
            real_sl = sl
            broker_sl = sl
            if getattr(config, 'ENABLE_VIRTUAL_SL', False) and not pending_type:
                # วาง Emergency SL ไกลๆ ให้โบรกรมองไม่เห็นจุดจริง
                e_dist = getattr(config, 'EMERGENCY_SL_PIPS', 300) * (mt5.symbol_info(symbol).point * 10)
                broker_sl = (price - e_dist) if direction == 'BUY' else (price + e_dist)
                mode_label += " (H)"

            request = {
                "action":       mt5.TRADE_ACTION_PENDING if pending_type else mt5.TRADE_ACTION_DEAL,
                "symbol":       symbol,
                "volume":       lot,
                "type":         order_type,
                "price":        float(price),
                "sl":           float(broker_sl),
                "tp":           float(tp),
                "deviation":    20,
                "magic":        getattr(config, 'MAGIC_NUMBER', 999999),
                "comment":      comment,
                "type_time":    mt5.ORDER_TIME_SPECIFIED if pending_type else mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK if not pending_type else mt5.ORDER_FILLING_RETURN,
            }

            if pending_type:
                expiry_hours = getattr(config, 'PENDING_EXPIRY_HOURS', 4)
                request["expiration"] = int(time.time() + (expiry_hours * 3600))

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                max_orders = s_cfg.get('max_scalp_orders', 2)
                msg = (f"🟢 *[{symbol}] เปิดออเดอร์ {direction}* #{order_index}/{max_orders}\n"
                       f"Lot: {lot} | Mode: {mode_label}\n"
                       f"Ticket: `{result.order}` | SL: {sl:.5f} | TP: {tp:.5f}\n"
                       f"Magic: {request['magic']} | Comment: {comment}")
                self.notify(msg)
                return result.order
            else:
                retcode_msg = result.retcode if result else 'None'
                print(f"🔴 [{symbol}] Trade failed: {retcode_msg}")
                if result:
                    print(f"   Response: {result}")
                return None
        except Exception as e:
            print(f"🔴 [{symbol}] execute_trade error: {e}")
            return None

    # =========================================================
    # Pending Orders
    # =========================================================

    def place_pending_orders(self, symbol, signals, atr_val, fvg_type, fvg_entry, b_high, b_low):
        if not getattr(config, 'ENABLE_PENDING_ORDERS', False):
            return
        pending_count = self.count_pending_orders(symbol)
        max_p = getattr(config, 'MAX_PENDING_PER_SYMBOL', 2)

        orders = mt5.orders_get(symbol=symbol)
        if orders:
            tick     = mt5.symbol_info_tick(symbol)
            pip_size = mt5.symbol_info(symbol).point * 10
            for o in orders:
                if o.magic == getattr(config, 'MAGIC_NUMBER', 999999):
                    dist = abs(o.price_open - tick.bid) / pip_size
                    if dist > 300:
                        mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                        pending_count -= 1

        if pending_count >= max_p:
            return

        tick     = mt5.symbol_info_tick(symbol)
        pip_size = mt5.symbol_info(symbol).point * 10
        dist_pips = getattr(config, 'BREAKOUT_DISTANCE_PIPS', 30)

        if fvg_entry > 0 and pending_count < max_p:
            if fvg_type == "Bullish" and fvg_entry < tick.ask:
                self.execute_trade(symbol, 'BUY',  atr_val, order_index=91,
                                   pending_type=mt5.ORDER_TYPE_BUY_LIMIT,  pending_price=fvg_entry)
            elif fvg_type == "Bearish" and fvg_entry > tick.bid:
                self.execute_trade(symbol, 'SELL', atr_val, order_index=91,
                                   pending_type=mt5.ORDER_TYPE_SELL_LIMIT, pending_price=fvg_entry)

        pending_count = self.count_pending_orders(symbol)
        if pending_count < max_p:
            if 'BUY' in signals:
                price = b_high + (dist_pips * pip_size)
                if price > tick.ask:
                    self.execute_trade(symbol, 'BUY',  atr_val, order_index=92,
                                       pending_type=mt5.ORDER_TYPE_BUY_STOP,  pending_price=price)
            elif 'SELL' in signals:
                price = b_low - (dist_pips * pip_size)
                if price < tick.bid:
                    self.execute_trade(symbol, 'SELL', atr_val, order_index=92,
                                       pending_type=mt5.ORDER_TYPE_SELL_STOP, pending_price=price)

    # =========================================================
    # Trailing Stop
    # =========================================================

    def manage_trailing_stop(self, symbol, position, atr_val):
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return
            s_cfg    = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
            sym_info = mt5.symbol_info(symbol)
            pip_size = sym_info.point * 10

            be_pips   = s_cfg.get('be_activation_pips', 80)
            be_dist   = be_pips * pip_size
            be_offset = s_cfg.get('be_offset_pips', 10) * pip_size

            ActivationDist = atr_val * s_cfg.get('trail_activation', 1.2)
            TrailStep      = atr_val * s_cfg.get('trail_step', 0.5)
            new_sl = None

            # [P4] ดึง Virtual SL มาเฝ้าดู
            v_sl = self.virtual_sl_cache.get(position.ticket)
            use_v = getattr(config, 'ENABLE_VIRTUAL_SL', False) and v_sl is not None

            # --- Check Virtual Stop Loss Hit ---
            if use_v:
                hit = False
                if position.type == mt5.ORDER_TYPE_BUY and tick.bid <= v_sl: hit = True
                elif position.type == mt5.ORDER_TYPE_SELL and tick.ask >= v_sl: hit = True
                
                if hit:
                    self.notify(f"🛡️ *[V-SL/{symbol}] แตะจุด Hidden SL ({v_sl:.2f})*\nสั่งปิดออเดอร์ #{position.ticket} ทันที!")
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": position.volume,
                        "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                        "position": position.ticket, "price": tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask,
                        "deviation": 20, "magic": position.magic, "comment": "VIRTUAL_SL_HIT",
                        "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_FOK,
                    })
                    if position.ticket in self.virtual_sl_cache: del self.virtual_sl_cache[position.ticket]
                    return

            # --- Trailing / BE Logic (Virtual or Hard) ---
            current_sl = v_sl if use_v else position.sl

            if position.type == mt5.ORDER_TYPE_BUY:
                profit_dist = tick.bid - position.price_open
                if (current_sl < position.price_open) and profit_dist > be_dist:
                    new_sl = position.price_open + be_offset
                    print(f"🛡️ [{symbol}] BE Activated ({'V-' if use_v else ''}BUY)")
                elif profit_dist > ActivationDist:
                    ts_sl = tick.bid - TrailStep
                    if ts_sl > (new_sl or current_sl) and ts_sl > position.price_open:
                        new_sl = ts_sl

            elif position.type == mt5.ORDER_TYPE_SELL:
                profit_dist = position.price_open - tick.ask
                if (current_sl == 0 or current_sl > position.price_open) and profit_dist > be_dist:
                    new_sl = position.price_open - be_offset
                    print(f"🛡️ [{symbol}] BE Activated ({'V-' if use_v else ''}SELL)")
                elif profit_dist > ActivationDist:
                    ts_sl = tick.ask + TrailStep
                    if (current_sl == 0 or ts_sl < (new_sl or current_sl)) and ts_sl < position.price_open:
                        new_sl = ts_sl

            if new_sl:
                if use_v:
                    # อัปเดตเฉพาะใน Cache และ DB (ไม่ส่งโบรก)
                    self.virtual_sl_cache[position.ticket] = new_sl
                    try:
                        conn = database.get_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE trades SET virtual_sl = ? WHERE ticket = ?", (new_sl, position.ticket))
                        conn.commit()
                        conn.close()
                    except: pass
                else:
                    # ส่งโบรกตามปกติ
                    mt5.order_send({
                        "action":   mt5.TRADE_ACTION_SLTP,
                        "position": position.ticket,
                        "symbol":   symbol, "sl": float(new_sl), "tp": float(position.tp),
                    })
        except Exception as e:
            if "position" not in str(e).lower():
                print(f"⚠️ [{symbol}] Trailing Stop error: {e}")

    # =========================================================
    # DB & Notifications
    # =========================================================

    def check_and_update_db(self, symbol):
        try:
            date_from   = datetime.now() - timedelta(days=2)
            date_to     = datetime.now() + timedelta(days=1)
            history     = mt5.history_deals_get(date_from, date_to)
            scalp_magic = getattr(config, 'MAGIC_NUMBER', 999999)
            grid_magic  = getattr(config, 'GRID_MAGIC_NUMBER', 20250412)

            if not history:
                return

            new_deals = [
                d for d in history
                if d.symbol == symbol
                and (d.magic == scalp_magic or d.magic == grid_magic)
                and d.entry == mt5.DEAL_ENTRY_OUT
                and not database.is_deal_notified(d.ticket)
            ]

            if not new_deals:
                return

            groups = {}
            for d in new_deals:
                res_str = "WIN 🏆" if d.profit >= 0 else "LOSS 📉"
                key = (d.magic, res_str)
                groups.setdefault(key, []).append(d)

            for (magic, res_str), deals in groups.items():
                is_grid    = " (GRID)" if magic == grid_magic else ""
                trade_type = "GRID"    if magic == grid_magic else "SCALP"
                total_profit = sum(d.profit for d in deals)

                active_pos  = mt5.positions_get(symbol=symbol)
                remaining   = sum(1 for p in active_pos if p.magic == magic) if active_pos else 0
                total_start = len(deals) + remaining

                msg = (f"*{res_str} [{symbol}] ออเดอร์{is_grid} ปิดแล้ว!*\n"
                       f"📊 สรุป: ปิดไป *{len(deals)}/{total_start}* ไม้\n"
                       f"💰 กำไรสุทธิ: *{total_profit:.2f}$*\n"
                       f"Tickets: " + ", ".join([f"`{d.position_id}`" for d in deals]))
                self.notify(msg)

                for d in deals:
                    database.mark_deal_as_notified(d.ticket)
                    database.update_pending_trades(d.position_id, d.profit, "WIN" if d.profit >= 0 else "LOSS")
                    self.last_close_time[symbol] = datetime.now()

                    # [P4] บันทึก stats แยกประเภท
                    self._record_trade(symbol, trade_type, d.profit)

                    if getattr(config, 'ENABLE_LOSS_SHAVING', False) and d.profit > 0:
                        pos_history = mt5.history_orders_get(ticket=d.order)
                        if pos_history and pos_history[0].magic == getattr(config, 'MAGIC_NUMBER', 999999):
                            self.acc_scalp_profit[symbol] = self.acc_scalp_profit.get(symbol, 0.0) + (d.profit + d.swap)
                            print(f"💰 [{symbol}] Loss Shaving: +${d.profit:.2f} (ยอดสะสม: ${self.acc_scalp_profit[symbol]:.2f})")
                            self.shave_losing_positions(symbol)

        except Exception as e:
            print(f"⚠️ [{symbol}] check_and_update_db error: {e}")

    # =========================================================
    # Portfolio Recovery
    # =========================================================

    def get_managed_positions(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return [], 0.0
        scalp_magic = getattr(config, 'MAGIC_NUMBER', 999999)
        grid_magic  = getattr(config, 'GRID_MAGIC_NUMBER', 20250412)
        managed     = [p for p in positions if p.magic in (scalp_magic, grid_magic)]
        total_profit = sum(p.profit + p.swap + getattr(p, 'commission', 0.0) for p in managed)
        return managed, total_profit

    def run_global_recovery_exit(self):
        """[NEW] ตรวจสอบการออกจากโหมด Recovery ทั้งพอร์ต หากกำไรรวมเป็นบวกตามเป้า"""
        if not self.global_recovery_active:
            return False
            
        total_p = 0.0
        all_managed = []
        
        # รวบรวมออเดอร์จากทุก Symbol ที่เราเทรด
        for sym in config.SYMBOLS:
            managed, p = self.get_managed_positions(sym)
            total_p += p
            all_managed.extend([(sym, pos) for pos in managed])
            
        target = getattr(config, 'RECOVERY_EXIT_PROFIT', 0.50)
        print(f"\r🛠️ [GLOBAL-RECOVERY] Total Profit: ${total_p:.2f} / Target: ${target:.2f} (Total Orders:{len(all_managed)})      ", end="", flush=True)
        
        if total_p >= target:
            msg = f"🛠️ *[GLOBAL-RECOVERY] เป้าหมายสำเร็จ!*\nกำไรรวมทั้งพอร์ต: *{total_p:.2f}$*\nกำลังปิดออเดอร์ทั้งหมด {len(all_managed)} ไม้..."
            self.notify(msg)
            
            for sym, pos in all_managed:
                tick = mt5.symbol_info_tick(sym)
                if not tick: continue
                order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                price      = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
                mt5.order_send({
                    "action": mt5.TRADE_ACTION_DEAL, "symbol": sym,
                    "volume": pos.volume, "type": order_type,
                    "position": pos.ticket, "price": price,
                    "deviation": 30, "magic": pos.magic,
                    "comment": "GLOBAL_RECOVERY_EXIT",
                    "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_FOK,
                })
            
            self.global_recovery_active = False
            database.set_bot_setting("global_recovery_active", False)
            return True
        return False

    def shave_losing_positions(self, symbol):
        if not getattr(config, 'ENABLE_LOSS_SHAVING', False):
            return
        acc_profit = self.acc_scalp_profit.get(symbol, 0.0)
        if acc_profit < getattr(config, 'MIN_PROFIT_TO_SHAVE', 1.0):
            return
        managed_pos, _ = self.get_managed_positions(symbol)
        losing_pos = [p for p in managed_pos if p.profit < 0]
        if not losing_pos:
            return
        losing_pos.sort(key=lambda x: (x.profit, x.time))
        target_pos = losing_pos[0]
        abs_loss   = abs(target_pos.profit)
        shave_vol  = floor((acc_profit / abs_loss) * target_pos.volume * 100) / 100.0
        if shave_vol < 0.01:
            return
        shave_vol = min(shave_vol, target_pos.volume)
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return
        order_type = mt5.ORDER_TYPE_SELL if target_pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price      = tick.bid if target_pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        result = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
            "volume": shave_vol, "type": order_type,
            "position": target_pos.ticket, "price": price,
            "deviation": 20, "magic": target_pos.magic,
            "comment": "LOSS_SHAVING",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        })
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            cost = (shave_vol / target_pos.volume) * abs_loss
            self.acc_scalp_profit[symbol] -= cost
            self.notify(f"✂️ *[SHAVER/{symbol}] เฉือนขาดทุนสำเร็จ!*\n"
                        f"ปิดสัดส่วน: *{shave_vol} lot* ของไม้ #{target_pos.ticket}\n"
                        f"ใช้กำไรสะสม: *-${cost:.2f}* | คงเหลือ: *${self.acc_scalp_profit[symbol]:.2f}*")

    # =========================================================
    # Grid Trading
    # =========================================================

    def get_grid_positions(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        buy_prices   = []
        sell_prices  = []
        floating_loss = 0.0
        if positions:
            for p in positions:
                if p.magic == config.GRID_MAGIC_NUMBER:
                    net_profit = p.profit + p.swap + getattr(p, 'commission', 0.0)
                    floating_loss += net_profit
                    if p.type == mt5.ORDER_TYPE_BUY:
                        buy_prices.append(p.price_open)
                    elif p.type == mt5.ORDER_TYPE_SELL:
                        sell_prices.append(p.price_open)
        return buy_prices, sell_prices, floating_loss

    def execute_grid_order(self, symbol, direction, level_num):
        try:
            tick = mt5.symbol_info_tick(symbol)
            check_price = tick.ask if direction == 'BUY' else tick.bid
            if not self.check_trade_safety(symbol, direction, check_price):
                return None

            sym_info = mt5.symbol_info(symbol)
            tick     = mt5.symbol_info_tick(symbol)
            if sym_info is None or tick is None:
                print(f"🔴 [GRID/{symbol}] ดึง Symbol Info / Tick ไม่ได้")
                return None

            s_cfg    = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
            pip_size = sym_info.point * 10
            tp_dist  = s_cfg.get('grid_tp_pips', 500) * pip_size
            sl_pips  = s_cfg.get('grid_sl_pips', 300)
            sl_dist  = sl_pips * pip_size if sl_pips > 0 else 0.0
            
            # [NEW] Dynamic Grid Lot
            lot = self.calculate_lot(symbol, fixed_sl_pips=sl_pips)

            if direction == 'BUY':
                price      = tick.ask
                tp         = price + tp_dist
                sl         = (price - sl_dist) if sl_dist > 0 else 0.0
                order_type = mt5.ORDER_TYPE_BUY
            else:
                price      = tick.bid
                tp         = price - tp_dist
                sl         = (price + sl_dist) if sl_dist > 0 else 0.0
                order_type = mt5.ORDER_TYPE_SELL

            if tp <= 0:
                return None

            comment = f"GRID_{direction[0]}#{level_num}"
            request = {
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       symbol,
                "volume":       lot,
                "type":         order_type,
                "price":        price,
                "tp":           float(tp),
                "deviation":    20,
                "magic":        config.GRID_MAGIC_NUMBER,
                "comment":      comment,
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            if sl > 0:
                request["sl"] = float(sl)

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                sl_txt = f"{sl:.2f}" if sl > 0 else "None"
                msg = (f"🟩 *[GRID/{symbol}] เปิด {direction} Level#{level_num}*\n"
                       f"Lot: {lot} | Price: {price:.2f} | TP: {tp:.2f} | SL: {sl_txt}\n"
                       f"Ticket: `{result.order}`")
                self.notify(msg)
                database.log_trade(
                    ticket=result.order, timestamp=datetime.now(), symbol=symbol,
                    m30_trend="GRID", h1_trend="GRID", smc_fvg="None", smc_zone="None",
                    m5_signal="GRID", direction=direction, rsi_m5=0.0, macd_diff=0.0,
                    bb_position="None", ema_dist_m5=0.0, trade_hour=datetime.now().hour,
                    day_of_week=datetime.now().weekday(), candle_pattern="None",
                    volatility=0.0, profit=0.0, result="PENDING",
                    account_id=config.MT5_LOGIN, session_idx=0, rel_volume=0.0,
                    xau_strength=0.0, usd_strength=0.0
                )
                return result.order
            else:
                print(f"🔴 [GRID/{symbol}] Order Failed: {result.retcode if result else 'None'}")
                return None
        except Exception as e:
            print(f"🔴 [GRID/{symbol}] execute_grid_order error: {e}")
            return None

    def detect_grid_mode(self, symbol):
        """[P3] ตรวจทิศตลาดอัตโนมัติ (Top-Down):
        - H4 + H1 ตรงกัน → LONG_ONLY / SHORT_ONLY
        - H4 + H1 ขัดแย้ง → SYMMETRIC (Sideway)
        """
        try:
            h4_trend  = self.get_h4_trend(symbol)
            h1_trend  = self.get_h1_trend(symbol)

            if h4_trend == 'UP' and h1_trend == 'UP':
                return 'LONG_ONLY',  f'H4↑ H1↑ → Strict Uptrend'
            elif h4_trend == 'DOWN' and h1_trend == 'DOWN':
                return 'SHORT_ONLY', f'H4↓ H1↓ → Strict Downtrend'
            else:
                # กรณี H4 กับ H1 ขัดแย้งกัน ( conflict ) ให้ถือว่าตลาดไม่มีทิศทางชัดเจน
                reason = f'H4{"↑" if h4_trend=="UP" else "↓"} H1{"↑" if h1_trend=="UP" else "↓"}'
                return 'SYMMETRIC',  f'{reason} → Sideway Mode'
        except Exception:
            return 'SYMMETRIC', 'Error → Fallback Sideway'

    def close_all_grid_positions(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return
        closed = 0
        for pos in positions:
            if pos.magic != config.GRID_MAGIC_NUMBER:
                continue
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                continue
            order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price      = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            res = mt5.order_send({
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       symbol,
                "volume":       pos.volume,
                "type":         order_type,
                "position":     pos.ticket,
                "price":        price,
                "deviation":    30,
                "magic":        config.GRID_MAGIC_NUMBER,
                "comment":      "GRID_SAFETY_STOP",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            })
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                closed += 1
        if closed > 0:
            self.notify(f"🛑 *[GRID/{symbol}] Safety Stop!*\nปิด {closed} ออเดอร์ทั้งหมดแล้ว")
        self.grid_safety_triggered[symbol] = True

    def run_grid(self, symbol, atr_val=None):
        """
        [P2] Grid Trading Logic — อัปเดต:
        1. Basket TP/SL: ปิดทั้งตะกร้าเมื่อกำไร/ขาดทุนรวมถึงเป้า
        2. Trend Lock: ลด max_levels เมื่อ SYMMETRIC (Sideway)
        3. Safety Stop ยังคงทำงานเป็น fallback
        """
        if not getattr(config, 'ENABLE_GRID', False):
            return
        if symbol not in config.SYMBOLS:
            return

        try:
            tick     = mt5.symbol_info_tick(symbol)
            sym_info = mt5.symbol_info(symbol)
            if tick is None or sym_info is None:
                return

            pip_size = sym_info.point * 10
            s_cfg    = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
            
            # --- [P2] ATR-Based Dynamic Spacing ---
            multiplier = s_cfg.get('grid_atr_multiplier', 1.0)
            min_pips   = s_cfg.get('grid_min_spacing_pips', 50)
            
            if atr_val is not None:
                # แปลง ATR (ราคาส่วนต่าง) เป็นระยะห่าง และคุมขั้นต่ำ
                spacing = max(atr_val * multiplier, min_pips * pip_size)
            else:
                # Fallback กรณีไม่มี ATR
                spacing = s_cfg.get('grid_spacing_pips', 100) * pip_size

            # --- เลือก Mode ---
            cfg_mode = getattr(config, 'GRID_MODE', 'SYMMETRIC')
            if cfg_mode == 'AUTO':
                mode, mode_reason = self.detect_grid_mode(symbol)
            else:
                mode        = cfg_mode
                mode_reason = f'Manual({cfg_mode})'

            buy_prices, sell_prices, floating_loss = self.get_grid_positions(symbol)

            # --- [P2] Basket TP: ปิดทั้งตะกร้าเมื่อกำไรรวมถึงเป้า ---
            basket_tp = s_cfg.get('grid_basket_tp', getattr(config, 'GRID_BASKET_TP_USD', 4.0))
            basket_sl = s_cfg.get('grid_basket_sl', getattr(config, 'GRID_BASKET_SL_USD', -8.0))

            total_open = len(buy_prices) + len(sell_prices)
            if total_open > 0:
                if floating_loss >= basket_tp:
                    self.notify(f"🎯 *[GRID/{symbol}] Basket TP สำเร็จ!*\n"
                                f"กำไรรวม: *+${floating_loss:.2f}* (เป้า: ${basket_tp:.2f})\n"
                                f"ปิดตะกร้า {total_open} ไม้...")
                    self.close_all_grid_positions(symbol)
                    # Reset flag ให้ Grid เปิดใหม่ได้ (TP ไม่ใช่ Safety)
                    self.grid_safety_triggered[symbol] = False
                    return
                elif floating_loss <= basket_sl:
                    # ใช้ Safety Stop เดิม (ยังคงอยู่ด้านล่าง)
                    pass

            # --- Safety Stop: ตัดขาดทุนฉุกเฉิน ---
            max_loss = s_cfg.get('grid_max_loss', -50.0)
            if floating_loss <= max_loss:
                print(f"\n🛑 [GRID/{symbol}] Safety Stop! Floating=${floating_loss:.2f} Limit=${max_loss:.2f}")
                self.close_all_grid_positions(symbol)
                return

            # --- Reset safety flag ---
            if total_open == 0 and self.grid_safety_triggered.get(symbol, False):
                self.grid_safety_triggered[symbol] = False
                print(f"\n✅ [GRID/{symbol}] Safety Stop cleared — Grid พร้อมเริ่มใหม่")

            if self.grid_safety_triggered.get(symbol, False):
                return

            current_price = (tick.ask + tick.bid) / 2.0

            # --- [P2] Trend Lock: ลด max_levels เมื่อ SYMMETRIC ---
            if mode == 'SYMMETRIC':
                max_lvl = s_cfg.get('grid_symmetric_max_levels', 2)
                print(f"\r⚠️ [GRID/{symbol}] Sideway mode — ลด max_levels → {max_lvl}      ", end="", flush=True)
            else:
                max_lvl = s_cfg.get('grid_max_levels', 3)

            # --- Cooldown ---
            GRID_COOLDOWN_SEC = 60
            last_open  = self.grid_last_open_time.get(symbol)
            cooldown_ok = (last_open is None) or \
                          ((datetime.now() - last_open).total_seconds() >= GRID_COOLDOWN_SEC)

            opened_this_cycle = False

            if mode in ('SYMMETRIC', 'LONG_ONLY') and cooldown_ok and not opened_this_cycle:
                if len(buy_prices) < max_lvl:
                    already_open = any(abs(p - current_price) < spacing * 0.6 for p in buy_prices)
                    if not already_open:
                        ticket = self.execute_grid_order(symbol, 'BUY', len(buy_prices) + 1)
                        if ticket:
                            buy_prices.append(current_price)
                            self.grid_last_open_time[symbol] = datetime.now()
                            opened_this_cycle = True

            if mode in ('SYMMETRIC', 'SHORT_ONLY') and cooldown_ok and not opened_this_cycle:
                if len(sell_prices) < max_lvl:
                    already_open = any(abs(p - current_price) < spacing * 0.6 for p in sell_prices)
                    if not already_open:
                        ticket = self.execute_grid_order(symbol, 'SELL', len(sell_prices) + 1)
                        if ticket:
                            sell_prices.append(current_price)
                            self.grid_last_open_time[symbol] = datetime.now()

            print(f"\r📊 [GRID/{symbol}] Mode:{mode} ({mode_reason}) | "
                  f"BUY:{len(buy_prices)} SELL:{len(sell_prices)} | "
                  f"Float:${floating_loss:.2f} TP:${basket_tp:.1f} SL:${basket_sl:.1f}      ", end="", flush=True)

        except Exception as e:
            print(f"⚠️ [GRID/{symbol}] run_grid error: {e}")

    # =========================================================
    # [P3] Scalp Signal Validation
    # =========================================================

    def _validate_scalp_signal(self, symbol, direction, rsi_m5, macd_diff,
                                h4_trend, h1_trend, m30_trend, smc_zone, vol_ok, volatility):
        """
        [P3] ตรวจสอบสัญญาณ Scalp แบบ Multi-filter:
        0. Global Recovery Check (ห้ามเปิดไม้ Scalp ในช่วงกู้พอร์ต)
        """
        if self.global_recovery_active:
            return False, "อยู่ในโหมดกู้พอร์ต (Recovery Mode Active)"
            
        # 0. H4 Filter (Primary Compass)
        if direction == 'BUY' and h4_trend == 'DOWN':
            return False, "สวนทาง H4 Bearish"
        if direction == 'SELL' and h4_trend == 'UP':
            return False, "สวนทาง H4 Bullish"
        # 1. Volume (ต้องผ่านก่อนเสมอ)
        if not vol_ok:
            return False, "Volume ต่ำ"

        # 3. [P4] ATR Volatility Filter (ตลาดบ้าคลั่งห้ามเข้า)
        if volatility > 2.5:
            return False, f"Volatility สูงเกินไป ({volatility:.1f})"

        # 4. RSI window
        buy_rsi_ok  = getattr(config, 'SCALP_BUY_RSI_MIN',  45) <= rsi_m5 <= getattr(config, 'SCALP_BUY_RSI_MAX',  65)
        sell_rsi_ok = getattr(config, 'SCALP_SELL_RSI_MIN', 35) <= rsi_m5 <= getattr(config, 'SCALP_SELL_RSI_MAX', 55)

        if direction == 'BUY':
            if not buy_rsi_ok:
                return False, f"RSI {rsi_m5:.1f} นอกช่วง BUY ({getattr(config,'SCALP_BUY_RSI_MIN',45)}-{getattr(config,'SCALP_BUY_RSI_MAX',65)})"
            if macd_diff <= 0:
                return False, f"MACD {macd_diff:.5f} ไม่สนับสนุน BUY"
        elif direction == 'SELL':
            if not sell_rsi_ok:
                return False, f"RSI {rsi_m5:.1f} นอกช่วง SELL ({getattr(config,'SCALP_SELL_RSI_MIN',35)}-{getattr(config,'SCALP_SELL_RSI_MAX',55)})"
            if macd_diff >= 0:
                return False, f"MACD {macd_diff:.5f} ไม่สนับสนุน SELL"

        # 3. M30 Trend (เดิม)
        if direction == 'BUY'  and m30_trend != 'UP':
            return False, f"M30={m30_trend} ไม่สนับสนุน BUY"
        if direction == 'SELL' and m30_trend != 'DOWN':
            return False, f"M30={m30_trend} ไม่สนับสนุน SELL"

        # 4. [P3] H1 Confirmation — บังคับ
        if getattr(config, 'SCALP_REQUIRE_H1_CONFIRM', True):
            if direction == 'BUY'  and h1_trend != 'UP':
                return False, f"H1={h1_trend} ไม่สนับสนุน BUY (H1 Filter)"
            if direction == 'SELL' and h1_trend != 'DOWN':
                return False, f"H1={h1_trend} ไม่สนับสนุน SELL (H1 Filter)"

        # 5. [P3] SMC Zone Filter
        if getattr(config, 'SCALP_REQUIRE_SMC_ZONE', True):
            if direction == 'BUY'  and smc_zone != 'Discount':
                return False, f"SMC Zone={smc_zone} (ต้องการ Discount สำหรับ BUY)"
            if direction == 'SELL' and smc_zone != 'Premium':
                return False, f"SMC Zone={smc_zone} (ต้องการ Premium สำหรับ SELL)"

        return True, "ผ่าน"

    # =========================================================
    # Main Loop
    # =========================================================

    def run(self):
        if not self.init_mt5():
            return
        database.setup_db()

        startup_msg = (f"🚀 *[EA Online - v3]* บอทเริ่มทำงานแล้ว!\n"
                       f"Symbol: `{config.SYMBOLS}`\n"
                       f"Magic: `{config.MAGIC_NUMBER}`\n"
                       f"Risk: `{config.RISK_PERCENT}%` per trade\n"
                       f"Status: _เชื่อมต่อสำเร็จ_ ✅")
        self.notify(startup_msg)

        loop_count = 0
        while True:
            self.load_model()
            loop_count += 1
            
            # --- [NEW] Global Portfolio Drawdown Check ---
            try:
                acc = mt5.account_info()
                if acc:
                    equity  = acc.equity
                    balance = acc.balance
                    dd_percent = ((equity - balance) / balance) * 100
                    
                    # ถ้าติดลบเกินค่าที่กำหนด และยังไม่ได้อยู่ในโหมด Recovery
                    trigger_val = -abs(getattr(config, 'RECOVERY_TRIGGER_PERCENT', 10.0))
                    if dd_percent <= trigger_val and not self.global_recovery_active:
                        self.global_recovery_active = True
                        database.set_bot_setting("global_recovery_active", True)
                        msg = (f"⚠️ *[EMERGENCY]*พอร์ตติดลบสะสม *{dd_percent:.2f}%*\n"
                               f"เปิดใช้งาน *Global Recovery Mode* อัตโนมัติ!\n"
                               f"งดเปิดออเดอร์ Scalp ใหม่จนกว่าจะเคลียร์พอร์ตสำเร็จ")
                        self.notify(msg)
            except Exception as e:
                print(f"Error checking global drawdown: {e}")

            # --- Check Recovery Exit for the whole portfolio ---
            self.run_global_recovery_exit()

            for symbol in config.SYMBOLS:
                if not mt5.symbol_select(symbol, True):
                    print(f"\n❌ [{symbol}] Symbol ไม่พบใน MT5 — ตรวจสอบชื่อ Symbol")
                    continue

                positions    = mt5.positions_get(symbol=symbol)
                scalp_magic  = getattr(config, 'MAGIC_NUMBER', 999999)
                grid_magic   = getattr(config, 'GRID_MAGIC_NUMBER', 20250412)
                our_positions = [p for p in positions if p.magic in (scalp_magic, grid_magic)] if positions else []
                open_count    = sum(1 for p in our_positions if p.magic == scalp_magic)

                # --- Trailing Stop ---
                if our_positions:
                    df_trail = self.get_data(symbol, mt5.TIMEFRAME_M5, 100)
                    if df_trail is not None:
                        df_trail   = self.add_indicators(df_trail)
                        atr_val_t  = df_trail.iloc[-1]['atr']
                        for pos in our_positions:
                            if pos.magic == scalp_magic:
                                self.manage_trailing_stop(symbol, pos, atr_val_t)

                # --- DB Update ---
                self.check_and_update_db(symbol)

                # --- Post-Trade Cooldown ---
                last_close = self.last_close_time.get(symbol)
                if last_close:
                    cooldown_m = getattr(config, 'POST_TRADE_COOLDOWN_MINUTES', 5)
                    diff       = (datetime.now() - last_close).total_seconds() / 60.0
                    if diff < cooldown_m:
                        wait_sec = int((cooldown_m - diff) * 60)
                        print(f"\r[{symbol}] ⏳ Cooldown: {wait_sec}s      ", end="", flush=True)
                        continue

                # --- M5 Data & Indicators ---
                m5_data = self.get_m5_market_state(symbol)
                (m5_signals, rsi_m5, ema_dist_m5, atr_val, pattern, volatility,
                 day_of_week, macd_diff, bb_position, smc_fvg, smc_zone, session,
                 rel_vol, xau_strength, usd_strength, fvg_entry, b_high, b_low) = m5_data

                if rsi_m5 is None or atr_val is None:
                    # ถ้าข้อมูลยังไม่นิ่ง ให้ข้ามไปวน Loop ใหม่
                    print(f"\r[{symbol}] ⏳ รอ Data พร้อม...      ", end="", flush=True)
                    continue

                h4_trend  = self.get_h4_trend(symbol)
                h1_trend  = self.get_h1_trend(symbol)
                m30_trend = self.get_m30_trend(symbol)
                vol_ok    = rel_vol > 1.1

                # --- Grid Trading ---
                self.run_grid(symbol, atr_val=atr_val)

                # --- Max Scalp Orders Check ---
                s_cfg      = config._PROFILES.get(symbol, config._PROFILES["XAUUSDc"])
                max_orders = s_cfg.get('max_scalp_orders', 2)
                if open_count >= max_orders:
                    print(f"\r[{symbol}] ⛔ Max Orders ({open_count}/{max_orders})      ", end="", flush=True)
                    continue

                if config.ENABLE_NEWS_FILTER and self.check_news_forexfactory():
                    print(f"\r[{symbol}] หลบออเดอร์ วันนี้มีข่าวแดง USD...", end="", flush=True)
                    continue

                if not self.check_time_filter():
                    print(f"\r[{symbol}] ⏳ นอกช่วงเวลาเทรด ({config.TRADE_TIME_START}:00-{config.TRADE_TIME_END}:00)   ", end="", flush=True)
                    continue

                # --- [P3] Scalp Signal with Enhanced Filter ---
                direction = None
                if 'BUY' in m5_signals:
                    valid, reason = self._validate_scalp_signal(
                        symbol, 'BUY', rsi_m5, macd_diff,
                        h4_trend, h1_trend, m30_trend, smc_zone, vol_ok, volatility
                    )
                    if valid:
                        direction = 'BUY'
                    else:
                        print(f"\r[{symbol}] ❌ BUY rejected: {reason}      ", end="", flush=True)

                elif 'SELL' in m5_signals:
                    valid, reason = self._validate_scalp_signal(
                        symbol, 'SELL', rsi_m5, macd_diff,
                        h4_trend, h1_trend, m30_trend, smc_zone, vol_ok, volatility
                    )
                    if valid:
                        direction = 'SELL'
                    else:
                        print(f"\r[{symbol}] ❌ SELL rejected: {reason}      ", end="", flush=True)

                # --- Execute Market Order ---
                if direction:
                    open_count_now = self.count_open_orders(symbol)
                    if open_count_now >= max_orders:
                        print(f"\r[{symbol}] ⛔ Max Orders ({open_count_now}/{max_orders})      ", end="", flush=True)
                    else:
                        order_idx = open_count_now + 1
                        # --- [P4] Calculate Structural SL ---
                        sym_info = mt5.symbol_info(symbol)
                        pip_size = sym_info.point * 10 if sym_info else 0.0001
                        # วาง SL ไว้ห่างจาก High/Low ล่าสุด 5-10 pips
                        offset = 10 * pip_size
                        st_sl = (b_low - offset) if direction == 'BUY' else (b_high + offset)

                        print(f"\n[{symbol}] 🎯 Scalp Signal: {direction} #{order_idx}/{max_orders} "
                              f"| Confidence: 0.65+ | Structural SL: {st_sl:.2f}")
                        
                        ticket = self.execute_trade(symbol, direction, atr_val, 
                                                   order_index=order_idx, structural_sl=st_sl)
                        if ticket:
                            # [P4] เก็บ Virtual SL ลง Cache
                            if getattr(config, 'ENABLE_VIRTUAL_SL', False):
                                self.virtual_sl_cache[ticket] = st_sl

                            session_map = {"Asian": 0, "London": 1, "NY": 2, "Overlap": 3}
                            s_idx = session_map.get(session, 0)
                            database.log_trade(
                                ticket, datetime.now(), symbol, m30_trend or "N/A", h1_trend or "N/A",
                                smc_fvg, smc_zone, ",".join(m5_signals), direction,
                                rsi_m5, macd_diff, bb_position, ema_dist_m5,
                                datetime.now().hour, day_of_week, pattern, volatility,
                                0.0, "PENDING", config.MT5_LOGIN, s_idx, rel_vol,
                                xau_strength, usd_strength,
                                virtual_sl=st_sl if getattr(config, 'ENABLE_VIRTUAL_SL', False) else 0.0
                            )

                # --- Pending Orders ---
                self.place_pending_orders(symbol, m5_signals, atr_val, smc_fvg, fvg_entry, b_high, b_low)

                # --- AI Hourly Analysis ---
                last_time      = self.last_ai_report_time.get(symbol, datetime.now() - timedelta(hours=5))
                time_since_ai  = (datetime.now() - last_time).total_seconds()
                if time_since_ai >= 3600 and not self.ai_in_progress.get(symbol, False):
                    print(f"\n🚀 Launching AI Market Analysis for {symbol}...")
                    _, _, grid_floating = self.get_grid_positions(symbol)
                    ctx = {
                        "price":   (mt5.symbol_info_tick(symbol).ask + mt5.symbol_info_tick(symbol).bid) / 2,
                        "rsi":     rsi_m5,
                        "macd":    macd_diff,
                        "trend":   f"H1:{h1_trend} / M30:{m30_trend}",
                        "profit":  grid_floating,
                        "session": session
                    }
                    self.executor.submit(self._run_ai_in_background, symbol, ctx)
                    self.last_ai_report_time[symbol] = datetime.now()

                # --- Status Display ---
                h4_icon    = "🟢" if h4_trend  == 'UP' else "🔴"
                h1_icon    = "🟢" if h1_trend  == 'UP' else "🔴"
                m30_icon   = "🟢" if m30_trend == 'UP' else "🔴" if m30_trend == 'DOWN' else "⚪"
                vol_icon   = "🔥" if vol_ok else "❄️"
                zone_icon  = {"Premium": "🔴", "Discount": "🟢", "Equilibrium": "⚪"}.get(smc_zone, "⚪")

                status_msg = (f"[{symbol}] {h4_icon}H4 {h1_icon}H1 {m30_icon}M30 | "
                              f"RSI:{rsi_m5:.1f} MACD:{macd_diff:.4f} | "
                              f"{zone_icon}Zone:{smc_zone} | Vol:{rel_vol:.1f}{vol_icon}")

                if loop_count % 10 == 1:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {status_msg}")
                else:
                    print(f"\r{status_msg} | Loop#{loop_count}      ", end="", flush=True)

                # --- [P4] Performance Report (ทุก 4 ชม.) ---
                time_since_summary = (datetime.now() - self.last_summary_time).total_seconds()
                if time_since_summary >= 14400:
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