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
from datetime import datetime, timedelta
import config
import database


class SelfLearningEA:
    def __init__(self):
        self.model_cat = None
        self.model_rf = None
        self.model_last_modified = 0
        self.usd_news_today = False
        self.last_news_check = ""
        self.last_summary_time = datetime.now() - timedelta(hours=11.9) # ส่งรายงานครั้งแรกเกือบทันที
        self.last_ai_report_time = datetime.now() - timedelta(hours=5) # บังคับรันครั้งแรก

    def init_mt5(self):
        if not mt5.initialize():
            print("MT5 Initialization failed. Make sure MT5 is installed and open.")
            return False
            
        authorized = mt5.login(
            config.MT5_LOGIN, 
            password=config.MT5_PASSWORD, 
            server=config.MT5_SERVER
        )
        if not authorized:
            print(f"Failed to connect to MT5 account {config.MT5_LOGIN}, error code: {mt5.last_error()}")
            return False
        else:
            print(f"✅ Successfully connected to MT5 Account: {config.MT5_LOGIN}")
            return True

    def load_model(self):
        """Hot-Swap โหลด 2 โมเดลเข้ามาเช็คเงื่อนไขพร้อมกัน"""
        if os.path.exists(config.CAT_MODEL_PATH) and os.path.exists(config.RF_MODEL_PATH):
            mod_time = os.path.getmtime(config.CAT_MODEL_PATH) # เช็คไฟล์ใดไฟล์หนึ่งก็พอเพราะเซฟพร้อมกัน
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

    def check_news_forexfactory(self):
        """เช็คข่าวจาก API ฟรี (ForexFactory) ดึงข้อมูลข่าวกล่องแดง USD วันนี้"""
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
        """ส่งข้อความแจ้งเตือนผ่าน LINE Messaging API (รองรับหลาย User ID คั่นด้วย ,)"""
        if hasattr(config, 'LINE_CHANNEL_ACCESS_TOKEN') and config.LINE_CHANNEL_ACCESS_TOKEN and \
           hasattr(config, 'LINE_USER_ID') and config.LINE_USER_ID:
            
            user_ids = [uid.strip() for uid in str(config.LINE_USER_ID).split(',') if uid.strip()]
            if not user_ids: return
                
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}"}
            try:
                for uid in user_ids:
                    url = "https://api.line.me/v2/bot/message/push"
                    data = {"to": uid, "messages": [{"type": "text", "text": message}]}
                    requests.post(url, headers=headers, json=data, timeout=10)
            except Exception as e:
                print(f"🔴 LINE Exception: {e}")

    def send_telegram_message(self, message):
        """ส่งข้อความแจ้งเตือนผ่าน Telegram Bot API (ฟรีและไม่จำกัด)"""
        if hasattr(config, 'TELEGRAM_BOT_TOKEN') and config.TELEGRAM_BOT_TOKEN and \
           hasattr(config, 'TELEGRAM_CHAT_ID') and config.TELEGRAM_CHAT_ID:
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            try:
                res = requests.post(url, json=data, timeout=10)
                if res.status_code != 200:
                    print(f"🔴 Telegram Error ({res.status_code}): {res.text}")
                else:
                    print(f"📡 Telegram Sent.")
            except Exception as e:
                print(f"🔴 Telegram Exception: {e}")

    def notify(self, message):
        """ส่งแจ้งเตือนทุกช่องทางที่มีการตั้งค่าไว้ (LINE + Telegram)"""
        # พิมพ์ลง Terminal เสมอ
        clean_msg = message.replace('*', '') # ปัด Markdown ออกสำหรับ terminal
        print(f"\n📢 [NOTIFY]: {clean_msg}")
        
        # ส่ง LINE
        self.send_line_message(message)
        # ส่ง Telegram
        self.send_telegram_message(message)

    def send_performance_report(self):
        """สรุปผลงานในช่วง 12 ชม. ล่าสุด"""
        stats = database.get_performance_summary(hours=12)
        if stats:
            msg = (f"📊 *[Report - 12h Performance Summary]*\n"
                   f"🗓 _ช่วงเวลา 12 ชั่วโมงที่ผ่านมา_\n\n"
                   f"💰 กำไรสุทธิ: *{stats['net_profit']:.2f}$*\n"
                   f"📈 ชนะ: {stats['wins']} | แพ้: {stats['losses']}\n"
                   f"🎯 Win Rate: *{stats['win_rate']:.1f}%*\n"
                   f"Total Trades: {stats['total']}\n\n"
                   f"บอทจะสรุปผลให้คุณทราบทุกๆ 12 ชม. ครับ 🚀")
            self.notify(msg)
            return True
        return False

    def get_ai_market_analysis(self, symbol, context_data):
        """ส่งข้อมูลตลาดให้ Ollama (Gemma4) ช่วยวิเคราะห์เป็นภาษาไทย"""
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
                f"ช่วยสรุปสั้นๆ เป็นภาษาไทย 2-3 บรรทัดว่าสภาวะเป็นอย่างไร และควรระวังอะไรบ้าง?"
            )
            payload = {
                "model": "gemma4:latest",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 150,  # จำกัดการตอบไม่ให้ยาวเกินไป เพื่อความเร็ว
                    "temperature": 0.7
                }
            }
            response = requests.post(url, json=payload, timeout=120)
            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'ไม่สามารถดึงบทวิเคราะห์ได้')
            return "AI ไม่ตอบสนอง (ตรวจสอบ Ollama)"
        except Exception as e:
            return f"AI Error: {e}"

    def check_time_filter(self):
        """เช็คเวลาเทรด ไม่เทรดช่วงเวลาที่ไม่กำหนด"""
        current_hour = datetime.now().hour
        return config.TRADE_TIME_START <= current_hour <= config.TRADE_TIME_END

    def get_data(self, symbol, timeframe, n=100):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
        if rates is None or len(rates)==0: return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean()
        return atr

    def check_candlestick_pattern(self, df):
        if len(df) < 2: return "None"
        row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        body = abs(row['close'] - row['open'])
        upper_wick = row['high'] - max(row['close'], row['open'])
        lower_wick = min(row['close'], row['open']) - row['low']
        
        # Doji
        if body <= (row['high'] - row['low']) * 0.1:
            return "Doji"
        # Pinbar (Bullish/Bearish)
        elif lower_wick > body * 2 and upper_wick < body * 0.5:
            return "Pinbar_Bull"
        elif upper_wick > body * 2 and lower_wick < body * 0.5:
            return "Pinbar_Bear"
        # Engulfing
        elif row['close'] > prev_row['open'] and row['open'] < prev_row['close'] and row['close'] > row['open'] and prev_row['close'] < prev_row['open']:
            return "Engulfing_Bull"
        elif row['close'] < prev_row['open'] and row['open'] > prev_row['close'] and row['close'] < row['open'] and prev_row['close'] > prev_row['open']:
            return "Engulfing_Bear"
            
        return "None"
        
    def get_market_session(self):
        """เช็คช่วงเวลาตลาด (UTC) เพื่อให้ AI รู้สภาวะตลาด"""
        # สมมติฐาน: Sever Time คือ UTC+2/3 (ปรับตาม Exness)
        # เราใช้ Hour จาก datetime.now() เป็นตัวแทน
        hour = datetime.now().hour
        if 0 <= hour < 7: return "Asian"
        if 7 <= hour < 14: return "London"
        if 14 <= hour < 22: return "NY"
        return "Overlap"

    def get_currency_strength(self):
        """คำนวณความแข็งค่าของค่าเงิน XAU และ USD — มี symbol_select + error handling ป้องกันค้างตลอด"""
        strengths = {}
        strength_pairs = getattr(config, 'STRENGTH_PAIRS', ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "XAUUSDm"])
        for sym in strength_pairs:
            try:
                # เลือก Symbol ใน Market Watch ก่อนดึงข้อมูล (สำคัญ!)
                mt5.symbol_select(sym, True)
                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 20)
                if rates is not None and len(rates) > 1:
                    change = ((rates[-1][4] - rates[0][1]) / rates[0][1]) * 100
                    strengths[sym] = round(float(change), 6)
                else:
                    strengths[sym] = 0.0
            except Exception:
                strengths[sym] = 0.0  # ถ้า symbol ไม่มี ให้ใส่ 0 แทน crash
        
        # คำนวณ USD Strength
        usd_str = 0.0
        count = 0
        for pair, sign in [("EURUSD", -1), ("GBPUSD", -1), ("AUDUSD", -1), ("USDJPY", 1)]:
            if pair in strengths:
                usd_str += sign * strengths[pair]
                count += 1
        if count > 0:
            usd_str /= count
        
        # XAU Strength — รองรับทั้ง XAUUSD และ XAUUSDm
        xau_str = strengths.get("XAUUSDm", strengths.get("XAUUSD", 0.0))
        
        return xau_str, usd_str

    # --- SMC Advanced Logic (Ported from MQL5) ---
    def is_swing_high(self, df, idx, lookback=5):
        if idx < lookback or idx >= len(df) - lookback: return False
        high_val = df.iloc[idx]['high']
        for i in range(1, lookback + 1):
            if df.iloc[idx - i]['high'] > high_val or df.iloc[idx + i]['high'] > high_val:
                return False
        return True

    def is_swing_low(self, df, idx, lookback=5):
        if idx < lookback or idx >= len(df) - lookback: return False
        low_val = df.iloc[idx]['low']
        for i in range(1, lookback + 1):
            if df.iloc[idx - i]['low'] < low_val or df.iloc[idx + i]['low'] < low_val:
                return False
        return True

    def find_last_swings(self, df, lookback=5):
        """ค้นหา Swing High และ Swing Low ล่าสุด"""
        last_sh_idx = -1
        last_sl_idx = -1
        # วนลูปถอยหลังจากแท่งปัจจุบัน (ไม่รวมแท่ง 0 ที่กำลังวิ่ง)
        for i in range(len(df) - lookback - 1, lookback, -1):
            if last_sh_idx == -1 and self.is_swing_high(df, i, lookback):
                last_sh_idx = i
            if last_sl_idx == -1 and self.is_swing_low(df, i, lookback):
                last_sl_idx = i
            if last_sh_idx != -1 and last_sl_idx != -1:
                break
        return last_sh_idx, last_sl_idx

    def get_smc_structure(self, symbol, timeframe=mt5.TIMEFRAME_M30):
        """วิเคราะห์โครงสร้างตลาด SMC (BOS & OB) ใน Timeframe ที่กำหนด"""
        df = self.get_data(symbol, timeframe, 200)
        if df is None or len(df) < 100: return "CHoCH", None, None # Bias, OB_High, OB_Low
        
        sh_idx, sl_idx = self.find_last_swings(df)
        if sh_idx == -1 or sl_idx == -1: return "NEUTRAL", None, None
        
        last_close = df.iloc[-1]['close']
        sh_val = df.iloc[sh_idx]['high']
        sl_val = df.iloc[sl_idx]['low']
        
        bias = "NEUTRAL"
        ob_zone = (None, None)
        
        # Check for BOS (Break of Structure)
        if last_close > sh_val: # Bullish BOS
            bias = "BULL_BOS"
            # หา Buy Order Block (แท่ง Bearish สุดท้ายก่อนเกิดการพุ่งขึ้น)
            for i in range(sh_idx, 0, -1):
                if df.iloc[i]['close'] < df.iloc[i]['open']: # Bearish candle
                    ob_zone = (df.iloc[i]['high'], df.iloc[i]['low'])
                    break
        elif last_close < sl_val: # Bearish BOS
            bias = "BEAR_BOS"
            # หา Sell Order Block (แท่ง Bullish สุดท้ายก่อนเกิดการร่วงลง)
            for i in range(sl_idx, 0, -1):
                if df.iloc[i]['close'] > df.iloc[i]['open']: # Bullish candle
                    ob_zone = (df.iloc[i]['high'], df.iloc[i]['low'])
                    break
                    
        return bias, ob_zone[0], ob_zone[1]

    def check_spread(self, symbol):
        """ตรวจสอบค่า Spread ปัจจุบันว่าเกินกว่าที่กำหนดใน Config หรือไม่"""
        info = mt5.symbol_info(symbol)
        if info is None: return False
        current_spread = info.spread
        if current_spread > config.MAX_SPREAD:
            print(f"\r[{symbol}] ❌ ข้าม: Spread สูงเกินไป ({current_spread} > {config.MAX_SPREAD})      ", end="", flush=True)
            return False
        return True

    def add_indicators(self, df):
        """คำนวณ Technical Indicators ตัวใหม่เพิ่ม ATR และ Volatility"""
        df['ema_14'] = df['close'].ewm(span=14, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        df['atr'] = self.calculate_atr(df, config.ATR_PERIOD)
        df['volatility'] = ((df['high'] - df['low']) / df['atr']).fillna(1.0)
        
        # MACD (12, 26, 9)
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        df['macd_diff'] = macd_line - signal_line
        
        # Bollinger Bands (20, 2)
        df['bb_mid'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * 2)
        
        # Relative Volume (ปัจจุบันเทียบกับค่าเฉลี่ย 20 แท่ง)
        df['vol_sma'] = df['tick_volume'].rolling(window=20).mean()
        df['rel_volume'] = df['tick_volume'] / df['vol_sma'].replace(0, 1)
        
        return df

    def get_h1_trend(self, symbol):
        df = self.get_data(symbol, mt5.TIMEFRAME_H1, 100)
        if df is None: return None
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        last_close = df.iloc[-1]['close']
        last_ema = df.iloc[-1]['ema_50']
        return 'UP' if last_close > last_ema else 'DOWN'

    def get_m30_trend(self, symbol):
        df = self.get_data(symbol, mt5.TIMEFRAME_M30, 100)
        if df is None: return None
        df = self.add_indicators(df)
        last_close = df.iloc[-1]['close']
        last_ema = df.iloc[-1]['ema_50']
        return 'UP' if last_close > last_ema else 'DOWN'

    def get_m5_market_state(self, symbol):
        df = self.get_data(symbol, mt5.TIMEFRAME_M5, 200)
        if df is None: return [], None, None, None, None, None, None, None, None, None, None, None, None, None, None
        df = self.add_indicators(df)
        row = df.iloc[-1]
        
        signals = []
        if row['close'] > row['ema_14'] and row['close'] > row['ema_50'] and row['rsi_14'] < 70:
            signals.append('BUY')
        if row['close'] < row['ema_14'] and row['close'] < row['ema_50'] and row['rsi_14'] > 30:
            signals.append('SELL')
            
        ema_dist = ((row['close'] - row['ema_50']) / row['ema_50']) * 100 
        atr_val = row['atr']
        volatility = row['volatility']
        pattern = self.check_candlestick_pattern(df)
        day_of_week = datetime.now().weekday()
        
        macd_diff = row['macd_diff']
        
        bb_position = "Middle"
        if row['close'] > row['bb_upper']:
            bb_position = "Upper"
        elif row['close'] < row['bb_lower']:
            bb_position = "Lower"
            
        # SMC: Premium / Discount Zone (Last 50 candles)
        recent_high = df['high'].rolling(50).max().iloc[-1]
        recent_low = df['low'].rolling(50).min().iloc[-1]
        equilibrium = (recent_high + recent_low) / 2
        smc_zone = "Equilibrium"
        if row['close'] > equilibrium + (recent_high - equilibrium) * 0.2:
            smc_zone = "Premium"
        elif row['close'] < equilibrium - (equilibrium - recent_low) * 0.2:
            smc_zone = "Discount"
            
        # SMC: FVG Detection (scan last 15 candles for unmitigated gap)
        # ป้องกัน IndexError โดยเริ่มจาก index ที่ปลอดภัย (อย่างน้อย 2 จากจุดเริ่มต้น)
        smc_fvg = "None"
        start_idx = max(len(df) - 15, 2)  # อย่างน้อย index 2 เพื่อให้อ่าน i-2 ได้
        for i in range(start_idx, len(df) - 1):
            # Bullish FVG: แท่งก่อนหน้ามี low สูงกว่า แท่งก่อนหน้านั้นมี high ต่ำกว่า
            try:
                if df['high'].iloc[i-2] < df['low'].iloc[i]:
                    mitigated = False
                    for j in range(i+1, len(df)):
                        if df['low'].iloc[j] <= df['high'].iloc[i-2]:
                            mitigated = True
                            break
                    if not mitigated:
                        smc_fvg = "Bullish"
                        break  # เจอแล้วไม่ต้องหาต่อ
            except (IndexError, KeyError):
                continue

            # Bearish FVG: แท่งก่อนหน้ามี high ต่ำกว่า แท่งก่อนหน้านั้นมี low สูงกว่า
            try:
                if df['low'].iloc[i-2] > df['high'].iloc[i]:
                    mitigated = False
                    for j in range(i+1, len(df)):
                        if df['high'].iloc[j] >= df['low'].iloc[i-2]:
                            mitigated = True
                            break
                    if not mitigated:
                        smc_fvg = "Bearish"
                        break  # เจอแล้วไม่ต้องหาต่อ
            except (IndexError, KeyError):
                continue
        
        if pd.isna(row['rsi_14']) or pd.isna(ema_dist) or pd.isna(atr_val) or pd.isna(macd_diff):
            return [], 50.0, 0.0, 0.001, "None", 1.0, day_of_week, 0.0, "Middle", "None", "Equilibrium", "Asian", 1.0, 0.0, 0.0
            
        session = self.get_market_session()
        rel_vol = row['rel_volume']
        xau_str, usd_str = self.get_currency_strength()
        
        return signals, row['rsi_14'], ema_dist, atr_val, pattern, volatility, day_of_week, macd_diff, bb_position, smc_fvg, smc_zone, session, rel_vol, xau_str, usd_str

    def ml_predict(self, m30_trend, h1_trend, rsi_m5, ema_dist_m5, trade_hour, day_of_week, volatility, pattern, macd_diff, bb_position, smc_fvg, smc_zone, session, rel_vol, xau_str, usd_str):
        """ระบบโหวต (Double Confirmation) จากทั้ง 2 โมเดล"""
        if self.model_cat is None or self.model_rf is None:
            return None
            
        m30_val = 1 if m30_trend == 'UP' else 0
        h1_val = 1 if h1_trend == 'UP' else 0
        patterns_list = ["Doji", "Pinbar_Bull", "Pinbar_Bear", "Engulfing_Bull", "Engulfing_Bear", "None"]
        pat_val = patterns_list.index(pattern) if pattern in patterns_list else 5
        
        bb_list = ["Upper", "Middle", "Lower"]
        bb_val = bb_list.index(bb_position) if bb_position in bb_list else 1
        
        fvg_list = ["Bullish", "Bearish", "None"]
        fvg_val = fvg_list.index(smc_fvg) if smc_fvg in fvg_list else 2
        
        zone_list = ["Premium", "Discount", "Equilibrium"]
        zone_val = zone_list.index(smc_zone) if smc_zone in zone_list else 2
        
        base_features = {
            'm30_trend_up': [m30_val], 
            'h1_trend_up': [h1_val],
            'rsi_m5': [rsi_m5], 
            'ema_dist_m5': [ema_dist_m5], 
            'trade_hour': [trade_hour],
            'day_of_week': [day_of_week],
            'volatility': [volatility],
            'pattern_idx': [pat_val],
            'macd_diff': [macd_diff],
            'bb_position_idx': [bb_val],
            'fvg_idx': [fvg_val],
            'zone_idx': [zone_val],
            'session_idx': [["Asian", "London", "NY", "Overlap"].index(session) if session in ["Asian", "London", "NY", "Overlap"] else 0],
            'rel_volume': [rel_vol],
            'xau_strength': [xau_str],
            'usd_strength': [usd_str]
        }
        
        df_pred_buy = pd.DataFrame(base_features)
        df_pred_buy['dir_buy'] = 1
        df_pred_sell = pd.DataFrame(base_features)
        df_pred_sell['dir_buy'] = 0
        
        try:
            cols = ['m30_trend_up', 'h1_trend_up', 'dir_buy', 'rsi_m5', 'ema_dist_m5', 'trade_hour', 'day_of_week', 'volatility', 'pattern_idx', 'macd_diff', 'bb_position_idx', 'fvg_idx', 'zone_idx', 'session_idx', 'rel_volume', 'xau_strength', 'usd_strength']
            df_pred_buy = df_pred_buy[cols]
            df_pred_sell = df_pred_sell[cols]
            
            # ให้โมเดลทั้งคู่ทำนายความน่าจะเป็น
            prob_cat_buy = self.model_cat.predict_proba(df_pred_buy)[0][1]
            prob_rf_buy = self.model_rf.predict_proba(df_pred_buy)[0][1]
            
            prob_cat_sell = self.model_cat.predict_proba(df_pred_sell)[0][1]
            prob_rf_sell = self.model_rf.predict_proba(df_pred_sell)[0][1]
            
            print(f"AI Vote -> BUY: [Cat:{prob_cat_buy:.2f}, RF:{prob_rf_buy:.2f}] | SELL: [Cat:{prob_cat_sell:.2f}, RF:{prob_rf_sell:.2f}]")
            
            # ตัดสินใจออกออเดอร์เมื่อทั้งคู่โหวตตรงกัน และความมั่นใจเกิน 55%
            if prob_cat_buy > 0.55 and prob_rf_buy > 0.55:
                return 'BUY'
            elif prob_cat_sell > 0.55 and prob_rf_sell > 0.55:
                return 'SELL'
                
        except Exception as e:
            err_msg = str(e)
            if "feature_names mismatch" in err_msg:
                print(f"\r⚠️ AI Model Mismatch: ระบบพบฟีเจอร์ SMC ใหม่ แต่ไฟล์โมเดลเก่า... (รอ Trainer รีเซ็ตไฟล์สักครู่)", end="", flush=True)
            else:
                print(f"\r⚠️ ML Error: {err_msg}", end="", flush=True)
        return None

    def calculate_lot(self, symbol=None, atr_val=None):
        if config.RISK_MODE == "FIXED":
            return config.FIXED_LOT
            
        elif config.RISK_MODE == "PERCENT":
            account = mt5.account_info()
            if not account:
                print("⚠️ ไม่สามารถดึงข้อมูลบัญชีได้ ใช้ FIXED_LOT แทน")
                return config.FIXED_LOT

            balance = account.balance
            
            # 1. การคำนวณแบบแม่นยำตามระยะ SL (Position Sizing)
            if symbol and atr_val:
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info:
                    # คำนวณจำนวนเงินที่ยอมเสียได้ (เช่น 1% ของ Balance)
                    risk_amount = balance * (config.RISK_PERCENT / 100.0)
                    
                    # คำนวณระยะ SL ตาม ATR
                    sl_dist = atr_val * config.ATR_SL_MULTIPLIER
                    
                    tick_size = symbol_info.trade_tick_size
                    tick_value = symbol_info.trade_tick_value
                    
                    if tick_size > 0 and tick_value > 0:
                        # คำนวณ Lot: Risk Amount / (SL_Ticks * Tick_Value)
                        sl_ticks = sl_dist / tick_size
                        calculated_lot = risk_amount / (sl_ticks * tick_value)
                        
                        # ปรับทศนิยม Lot ให้ถูกต้องตาม Step ของโบรกเกอร์ (เช่น 0.01)
                        lot_step = symbol_info.volume_step
                        calculated_lot = round(calculated_lot / lot_step) * lot_step
                        
                        # จำกัด Min/Max Lot ป้องกัน Error
                        min_lot = symbol_info.volume_min
                        max_lot = symbol_info.volume_max
                        return max(min_lot, min(calculated_lot, max_lot))

            # 2. ถ้าหาข้อมูล Symbol ไม่ได้ ให้ใช้สูตรสำรอง (เทียบสัดส่วน Balance)
            # สมมติฐาน: ทุน $10,000 ความเสี่ยง 1% จะออกประมาณ 0.10 Lot
            fallback_lot = (balance / 100000.0) * (config.RISK_PERCENT * 10)
            return max(round(fallback_lot, 2), 0.01)
            
        return config.FIXED_LOT

    def count_open_orders(self, symbol):
        """นับออเดอร์ที่ Bot เปิดอยู่สำหรับ Symbol นี้ (เฉพาะ Magic Number ของเรา)"""
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return 0
        return sum(1 for p in positions if p.magic == config.MAGIC_NUMBER)

    def execute_trade(self, symbol, direction, atr_val, order_index=1):
        """เปิดออเดอร์พร้อมตั้งระยะ SL / TP
        - ถ้า USE_FIXED_PIPS = True -> ใช้ SCALP_TP_PIPS / SCALP_SL_PIPS
        - ถ้า USE_FIXED_PIPS = False -> ใช้ ATR Multiplier (Dynamic)
        order_index: ลำดับที่ของออเดอร์ใน batch (1, 2, 3...) ใช้ใน Comment
        """
        try:
            lot = self.calculate_lot(symbol, atr_val)
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print(f"🔴 [{symbol}] ไม่สามารถดึง Tick ได้")
                return None

            # --- คำนวณระยะ SL / TP ---
            if getattr(config, 'USE_FIXED_PIPS', False):
                sym_info = mt5.symbol_info(symbol)
                if sym_info is None:
                    print(f"🔴 [{symbol}] ไม่สามารถดึง Symbol Info ได้")
                    return None
                # 1 pip = 10 points สำหรับ XAUUSD (digits=2 -> point=0.01)
                # สำหรับ Forex 5 digits: 1 pip = 10 points (point=0.00001)
                pip_size = sym_info.point * 10
                sl_dist = config.SCALP_SL_PIPS * pip_size
                tp_dist = config.SCALP_TP_PIPS * pip_size
                mode_label = f"Pips({config.SCALP_SL_PIPS}SL/{config.SCALP_TP_PIPS}TP)"
            else:
                sl_dist = atr_val * config.ATR_SL_MULTIPLIER
                tp_dist = atr_val * config.ATR_TP_MULTIPLIER
                mode_label = f"ATR({atr_val:.5f})"

            if direction == 'BUY':
                price = tick.ask
                sl = price - sl_dist
                tp = price + tp_dist
                order_type = mt5.ORDER_TYPE_BUY
            else:
                price = tick.bid
                sl = price + sl_dist
                tp = price - tp_dist
                order_type = mt5.ORDER_TYPE_SELL

            # Validate SL/TP prices
            if sl <= 0 or tp <= 0:
                print(f"🔴 [{symbol}] SL/TP ไม่ถูกต้อง (SL={sl}, TP={tp})")
                return None

            # Comment แสดงลำดับออเดอร์ใน Batch
            comment = f"{getattr(config, 'ORDER_COMMENT', 'SMC_AI')}_{direction[0]}#{order_index}"

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot,
                "type": order_type,
                "price": price,
                "sl": float(sl),
                "tp": float(tp),
                "deviation": 20,
                "magic": getattr(config, 'MAGIC_NUMBER', 999999),
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,  # เปลี่ยนเป็น FOK เพื่อความเสถียร
            }

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                msg = (f"🟢 *[{symbol}] เปิดออเดอร์ {direction}* #{order_index}/{config.MAX_ORDERS_PER_SYMBOL}\n"
                       f"Lot: {lot} | Mode: {mode_label}\n"
                       f"Ticket: `{result.order}` | SL: {sl:.5f} | TP: {tp:.5f}\n"
                       f"Magic: {request['magic']} | Comment: {comment}")
                self.notify(msg)
                return result.order  # คืนค่า Ticket
            else:
                retcode_msg = result.retcode if result else 'None'
                print(f"🔴 [{symbol}] Trade failed: {retcode_msg}")
                # เพิ่มรายละเอียด error จาก MT5
                if result:
                    print(f"   Response: {result}")
                return None
        except Exception as e:
            print(f"🔴 [{symbol}] execute_trade error: {e}")
            return None

    def manage_trailing_stop(self, symbol, position, atr_val):
        """รับบทเป็น Trailing Stop และเลื่อน SL บังหน้าทุน"""
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return
            ActivationDist = atr_val * config.TRAIL_ACTIVATION
            TrailStep = atr_val * config.TRAIL_STEP

            if position.type == mt5.ORDER_TYPE_BUY:  # type: ignore[comparison-overlap]
                profit_dist = tick.bid - position.price_open
                if profit_dist > ActivationDist:
                    new_sl = tick.bid - TrailStep
                    if new_sl > position.sl and new_sl > position.price_open:
                        request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": position.ticket,
                            "sl": float(new_sl),
                            "tp": position.tp
                        }
                        res = mt5.order_send(request)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            print(f"🔵 [{symbol}] Trailing Stop (BUY) Moved to: {new_sl}")

            elif position.type == mt5.ORDER_TYPE_SELL:  # type: ignore[comparison-overlap]
                profit_dist = position.price_open - tick.ask
                if profit_dist > ActivationDist:
                    new_sl = tick.ask + TrailStep
                    if (position.sl == 0 or new_sl < position.sl) and new_sl < position.price_open:
                        request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": position.ticket,
                            "sl": float(new_sl),
                            "tp": position.tp
                        }
                        res = mt5.order_send(request)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            print(f"🔵 [{symbol}] Trailing Stop (SELL) Moved to: {new_sl}")
        except Exception as e:
            # Fail silently for trailing stop errors - don't spam logs
            if "position" in str(e).lower():
                pass  # Position may have been closed
            else:
                print(f"⚠️ [{symbol}] Trailing Stop error: {e}")

    def check_and_update_db(self, symbol):
        """เช็คประวัติการเทรดที่ปิดแล้ว แจ้งสถานะอัปเดตลงตาราง Database (Reliable Version)"""
        try:
            # เช็คย้อนหลัง 2 วันพอเพื่อความเร็ว
            date_from = datetime.now() - timedelta(days=2)
            date_to = datetime.now() + timedelta(days=1)
            history = mt5.history_deals_get(date_from, date_to)
            scalp_magic = getattr(config, 'MAGIC_NUMBER', 999999)
            grid_magic = getattr(config, 'GRID_MAGIC_NUMBER', 20250412)
            
            if history:
                # กรองเฉพาะดีลที่เป็นการปิดออเดอร์ (ENTRY_OUT) และมี Magic ของเรา
                deals = [d for d in history if (d.magic == scalp_magic or d.magic == grid_magic) and d.symbol == symbol]
                for deal in deals:
                    if deal.entry == mt5.DEAL_ENTRY_OUT:
                        # --- เช็คว่าแจ้งเตือนไปหรือยัง ---
                        if database.is_deal_notified(deal.ticket):
                            continue
                            
                        is_grid = " (GRID)" if deal.magic == grid_magic else ""
                        profit = deal.profit
                        res_str = "WIN 🏆" if profit >= 0 else "LOSS 📉"
                        
                        msg = (f"*{res_str} [{symbol}] ออเดอร์{is_grid} ปิดแล้ว!*\n"
                               f"Ticket: `{deal.position_id}`\n"
                               f"ผลกำไร: *{profit:.2f}$*")
                        
                        # ส่งแจ้งเตือน
                        self.notify(msg)
                        
                        # บันทึกว่าส่งแล้ว และอัปเดตสถานะในตารางหลักด้วย
                        database.mark_deal_as_notified(deal.ticket)
                        database.update_pending_trades(deal.position_id, profit, "WIN" if profit >= 0 else "LOSS")
                        
        except Exception as e:
            print(f"⚠️ [{symbol}] check_and_update_db error: {e}")

    # =========================================================
    # Grid Trading Methods
    # =========================================================

    def get_grid_positions(self, symbol):
        """ดึง Grid Positions ที่เปิดอยู่ทั้งหมด แยก BUY/SELL และคืนราคาที่เปิด"""
        positions = mt5.positions_get(symbol=symbol)
        buy_prices  = []
        sell_prices = []
        floating_loss = 0.0
        if positions:
            for p in positions:
                if p.magic == config.GRID_MAGIC_NUMBER:
                    floating_loss += p.profit
                    if p.type == mt5.ORDER_TYPE_BUY:
                        buy_prices.append(p.price_open)
                    elif p.type == mt5.ORDER_TYPE_SELL:
                        sell_prices.append(p.price_open)
        return buy_prices, sell_prices, floating_loss

    def execute_grid_order(self, symbol, direction, level_num):
        """เปิด Grid Order พร้อม TP และ SL (ถ้า GRID_SL_PIPS > 0)"""
        try:
            sym_info = mt5.symbol_info(symbol)
            tick     = mt5.symbol_info_tick(symbol)
            if sym_info is None or tick is None:
                print(f"🔴 [GRID/{symbol}] ดึง Symbol Info / Tick ไม่ได้")
                return None

            pip_size = sym_info.point * 10
            tp_dist  = config.GRID_TP_PIPS * pip_size
            sl_pips  = getattr(config, 'GRID_SL_PIPS', 0)
            sl_dist  = sl_pips * pip_size if sl_pips > 0 else 0.0
            lot      = config.GRID_LOT

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

                # บันทึกลงตารางชั่วคราวเพื่อให้ bot รู้ว่ามีออเดอร์นี้เวลาไปตรวจสอบ TP/SL
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
                retcode = result.retcode if result else 'None'
                print(f"🔴 [GRID/{symbol}] Order Failed: {retcode}")
                return None
        except Exception as e:
            print(f"🔴 [GRID/{symbol}] execute_grid_order error: {e}")
            return None


    def detect_grid_mode(self, symbol):
        """ตรวจทิศตลาดอัตโนมัติเพื่อเลือก Grid Mode
        - H1 + M30 ขาขึ้นตรงกัน  → LONG_ONLY  (BUY เท่านั้น)
        - H1 + M30 ขาลงตรงกัน   → SHORT_ONLY (SELL เท่านั้น)
        - ขัดแย้งกัน / Conflict  → SYMMETRIC  (เปิดทั้งสองทิศ = Sideway)
        """
        try:
            h1_trend  = self.get_h1_trend(symbol)
            m30_trend = self.get_m30_trend(symbol)
            if h1_trend == 'UP' and m30_trend == 'UP':
                return 'LONG_ONLY',  f'H1↑ M30↑ → Uptrend'
            elif h1_trend == 'DOWN' and m30_trend == 'DOWN':
                return 'SHORT_ONLY', f'H1↓ M30↓ → Downtrend'
            else:
                return 'SYMMETRIC',  f'H1{"↑" if h1_trend=="UP" else "↓"} M30{"↑" if m30_trend=="UP" else "↓"} → Sideway'
        except Exception:
            return 'SYMMETRIC', 'Error → Fallback Sideway'

    def run_grid(self, symbol):
        """Grid Trading Logic หลัก — เรียกทุก Loop
        1. เลือก Mode อัตโนมัติ (AUTO) หรือใช้ค่าจาก config
        2. คำนวณ Floating Loss รวม → Safety Stop
        3. เปิด Order ที่ Level ยังว่างอยู่
        """
        if not getattr(config, 'ENABLE_GRID', False):
            return
        if getattr(config, 'GRID_SYMBOL', '') != symbol:
            return

        try:
            tick     = mt5.symbol_info_tick(symbol)
            sym_info = mt5.symbol_info(symbol)
            if tick is None or sym_info is None:
                return

            pip_size = sym_info.point * 10
            spacing  = config.GRID_SPACING_PIPS * pip_size
            max_lvl  = getattr(config, 'GRID_MAX_LEVELS', 5)

            # --- เลือก Mode ---
            cfg_mode = getattr(config, 'GRID_MODE', 'SYMMETRIC')
            if cfg_mode == 'AUTO':
                mode, mode_reason = self.detect_grid_mode(symbol)
            else:
                mode        = cfg_mode
                mode_reason = f'Manual({cfg_mode})'

            buy_prices, sell_prices, floating_loss = self.get_grid_positions(symbol)

            # --- Safety Stop ---
            max_loss = getattr(config, 'GRID_MAX_TOTAL_LOSS', -50.0)
            if floating_loss <= max_loss:
                print(f"\r🛑 [GRID/{symbol}] Safety Stop! Loss: ${floating_loss:.2f} (Limit: ${max_loss:.2f})      ", end="", flush=True)
                return

            current_price = (tick.ask + tick.bid) / 2.0

            # --- เปิด BUY Levels ---
            if mode in ('SYMMETRIC', 'LONG_ONLY'):
                for i in range(max_lvl):
                    target_price = current_price - (i * spacing)
                    already_open = any(abs(p - target_price) < spacing * 0.5 for p in buy_prices)
                    if not already_open and len(buy_prices) < max_lvl:
                        ticket = self.execute_grid_order(symbol, 'BUY', len(buy_prices) + 1)
                        if ticket:
                            buy_prices.append(target_price)
                        break

            # --- เปิด SELL Levels ---
            if mode in ('SYMMETRIC', 'SHORT_ONLY'):
                for i in range(max_lvl):
                    target_price = current_price + (i * spacing)
                    already_open = any(abs(p - target_price) < spacing * 0.5 for p in sell_prices)
                    if not already_open and len(sell_prices) < max_lvl:
                        ticket = self.execute_grid_order(symbol, 'SELL', len(sell_prices) + 1)
                        if ticket:
                            sell_prices.append(target_price)
                        break

            total_grid = len(buy_prices) + len(sell_prices)
            print(f"\r📊 [GRID/{symbol}] Mode:{mode} ({mode_reason}) | "
                  f"BUY:{len(buy_prices)} SELL:{len(sell_prices)} | "
                  f"Floating:${floating_loss:.2f}      ", end="", flush=True)

        except Exception as e:
            print(f"⚠️ [GRID/{symbol}] run_grid error: {e}")

    def run(self):
        if not self.init_mt5(): return
        database.setup_db()
        
        # ส่งข้อความทดสอบการเชื่อมต่อทันทีที่เริ่ม
        startup_msg = f"🚀 *[EA Online]* บอทเริ่มทำงานแล้ว!\nSymbol: `{config.ACTIVE_SYMBOL}`\nMagic: `{config.MAGIC_NUMBER}`\nStatus: _เชื่อมต่อสำเร็จ_"
        self.notify(startup_msg)

        loop_count = 0
        while True:
            self.load_model()
            loop_count += 1
            
            for symbol in config.SYMBOLS:
                # เลือก Symbol ใน Market Watch
                if not mt5.symbol_select(symbol, True):
                    print(f"\n❌ [{symbol}] Symbol ไม่พบใน MT5 — ตรวจสอบชื่อ Symbol ใน Market Watch (สาเหตุหลักที่ Bot หยุดเงียบ)")
                    continue
                    
                positions = mt5.positions_get(symbol=symbol)
                magic = getattr(config, 'MAGIC_NUMBER', 999999)
                our_positions = [p for p in positions if p.magic == magic] if positions else []
                open_count = len(our_positions)

                # --- Manage Trailing Stop สำหรับออเดอร์ที่เปิดอยู่ทั้งหมด ---
                if our_positions:
                    df_trail = self.get_data(symbol, mt5.TIMEFRAME_M5, 100)
                    if df_trail is not None:
                        df_trail = self.add_indicators(df_trail)
                        atr_val_trail = df_trail.iloc[-1]['atr']
                        for pos in our_positions:
                            self.manage_trailing_stop(symbol, pos, atr_val_trail)

                # --- อัปเดต DB เสมอ (ดึงออเดอร์ที่ปิดแล้ว) ---
                self.check_and_update_db(symbol)

                # --- Grid Trading (ทำงานแยกจาก Scalping) ---
                self.run_grid(symbol)

                # --- ถ้าถึง Max Orders แล้ว ไม่ต้องหาสัญญาณใหม่ ---
                max_orders = getattr(config, 'MAX_ORDERS_PER_SYMBOL', 1)
                if open_count >= max_orders:
                    print(f"\r[{symbol}] ⛔ Max Orders ({open_count}/{max_orders}) — รอปิดออเดอร์ก่อน      ", end="", flush=True)
                    continue

                if config.ENABLE_NEWS_FILTER and self.check_news_forexfactory():
                    print(f"\r[{symbol}] หลบออเดอร์ วันนี้มีข่าวแดง USD...", end="", flush=True)
                    continue
                    
                if not self.check_time_filter():
                    print(f"\r[{symbol}] ⏳ อยู่นอกช่วงเวลาเทรด ({config.TRADE_TIME_START}:00 - {config.TRADE_TIME_END}:00)   ", end="", flush=True)
                    continue

                # 1. ดึง M5 Data + คำนวณ Indicators
                m5_data = self.get_m5_market_state(symbol)
                m5_signals, rsi_m5, ema_dist_m5, atr_val, pattern, volatility, day_of_week, macd_diff, bb_position, smc_fvg, smc_zone, session, rel_vol, xau_strength, usd_strength = m5_data

                if rsi_m5 is None or atr_val is None:
                    print(f"\r[{symbol}] ⏳ รอ Indicator พร้อม...      ", end="", flush=True)
                    continue

                # 2. เช็ค Spread (ปิดไว้ชั่วคราว — เปิดได้โดยยกเลิก comment)
                # if not self.check_spread(symbol):
                #     continue

                # 3. Pure Scalping Logic — EMA Crossover + RSI + MACD
                #    BUY : EMA14 > EMA50, RSI อยู่ช่วง 45-65 (ไม่ Overbought), MACD Diff > 0
                #    SELL: EMA14 < EMA50, RSI อยู่ช่วง 35-55 (ไม่ Oversold), MACD Diff < 0
                #    ช่วง RSI แยกชัดเจนเพื่อหลีกเลี่ยงสัญญาณขัดแย้ง
                direction = None

                buy_signal  = ('BUY' in m5_signals) and (45 <= rsi_m5 <= 65) and (macd_diff > 0)
                sell_signal = ('SELL' in m5_signals) and (35 <= rsi_m5 <= 55) and (macd_diff < 0)

                if buy_signal:
                    direction = 'BUY'
                elif sell_signal:
                    direction = 'SELL'

                # 4. ออกออเดอร์
                if direction:
                    open_count_now = self.count_open_orders(symbol)
                    if open_count_now >= max_orders:
                        print(f"\r[{symbol}] ⛔ Max Orders ({open_count_now}/{max_orders}) — รอปิดก่อน      ", end="", flush=True)
                    else:
                        order_idx = open_count_now + 1
                        print(f"\n[{symbol}] 🎯 Scalp Signal: {direction} #{order_idx}/{max_orders} "
                              f"| RSI:{rsi_m5:.1f} | MACD:{macd_diff:.4f} | BB:{bb_position}")
                        ticket = self.execute_trade(symbol, direction, atr_val, order_index=order_idx)
                        if ticket:
                            session_map = {"Asian": 0, "London": 1, "NY": 2, "Overlap": 3}
                            s_idx = session_map.get(session, 0)
                            database.log_trade(ticket, datetime.now(), symbol, "SCALP", "N/A", smc_fvg, smc_zone, ",".join(m5_signals), direction, rsi_m5, macd_diff, bb_position, ema_dist_m5, datetime.now().hour, day_of_week, pattern, volatility, 0.0, "PENDING", config.MT5_LOGIN, s_idx, rel_vol, xau_strength, usd_strength)
                # 5. AI Market Analysis (ทุก 4 ชม.)
                time_since_ai = (datetime.now() - self.last_ai_report_time).total_seconds()
                if time_since_ai >= 14400: # 4 hours
                    print(f"\n🤖 AI กำลังวิเคราะห์ตลาด {symbol}...")
                    
                    # --- ดึงข้อมูลที่จำเป็นสำหรับ AI ให้ครบถ้วนใน Scope นี้ (แกั NameError) ---
                    h1_trend  = self.get_h1_trend(symbol)
                    m30_trend = self.get_m30_trend(symbol)
                    _, _, grid_floating = self.get_grid_positions(symbol)
                    
                    ctx = {
                        "price": (mt5.symbol_info_tick(symbol).ask + mt5.symbol_info_tick(symbol).bid)/2,
                        "rsi": rsi_m5,
                        "macd": macd_diff,
                        "trend": f"H1:{h1_trend} / M30:{m30_trend}",
                        "profit": grid_floating,
                        "session": session
                    }
                    ai_view = self.get_ai_market_analysis(symbol, ctx)
                    report = f"🤖 *[AI Market Insight - {symbol}]*\n\n{ai_view}"
                    self.notify(report)
                    self.last_ai_report_time = datetime.now()
                    print(f"✅ AI Analysis Processed.")

                # แสดง status ทุก 10 รอบ
                if loop_count % 10 == 1:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{symbol}] ⏳ รอสัญญาณ.. | RSI:{rsi_m5:.1f} MACD:{macd_diff:.4f} EMA:{'\u2191' if 'BUY' in m5_signals else '\u2193' if 'SELL' in m5_signals else '\u2014'}")
                else:
                    print(f"\r[{symbol}] ⏳ รอสัญญาณ.. | RSI:{rsi_m5:.1f} MACD:{macd_diff:.4f} | Loop#{loop_count}      ", end="", flush=True)

                # 6. Performance Summary Report (ทุก 12 ชม.)
                time_since_summary = (datetime.now() - self.last_summary_time).total_seconds()
                if time_since_summary >= 43200: # 12 hours
                    if self.send_performance_report():
                        self.last_summary_time = datetime.now()
                        
            time.sleep(5)  # Loop delay

if __name__ == "__main__":
    ea = SelfLearningEA()
    try:
        ea.run()
    except KeyboardInterrupt:
        print("EA Stopped.")
        mt5.shutdown()
