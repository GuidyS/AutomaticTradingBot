import asyncio
import datetime as dt
import logging
import pandas as pd
import MetaTrader5 as mt5
from mt5_connector import MT5
from smc_utils import apply_all, dynamic_tp
from ml_classifier import load_model, predict_signal
from telegram_utils import tg_send, tg_send_summary
from config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

class SMCBot:
    def __init__(self):
        self.mt5 = MT5(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER)
        self.ml = load_model()
        self.last_entry_time = None
        self.active_tickets = set()

    async def fetch_and_prepare(self) -> pd.DataFrame:
        # Get M15 data
        df = self.mt5.get_history(SYMBOL, mt5.TIMEFRAME_M15, 800)
        if df.empty: return df
        # Apply SMC logic with config params
        df = apply_all(df, sl_atr=SL_ATR_MULTIPLIER, sl_buf=SL_SWIPE_BUFFER, retrace_atr=ENTRY_RETRACE_ATR)
        return df

    def is_allowed_time(self) -> bool:
        now = dt.datetime.now(dt.UTC).strftime("%H:%M")

        for s, e in TRADING_SESSIONS:
            if s <= now < e: return True
        return False

    def get_signal(self, df: pd.DataFrame):
        if not self.is_allowed_time(): return None
        last_row = df.iloc[-1]
        
        # 0️⃣ Trend Strength & Direction (ADX)
        if not last_row.get("adx_ok", False): return None
        direction_hint = last_row.get("adx_trend", 0)

        # 1️⃣ Structure Check
        bos_up = last_row.get("bos_up", False)
        bos_down = last_row.get("bos_down", False)
        sweep_up = last_row.get("sweep_up", False)
        sweep_down = last_row.get("sweep_down", False)

        if not ((bos_up and sweep_down) or (bos_down and sweep_up)):
            return None

        direction = 1 if bos_up else -1
        
        # 1.5️⃣ Trend alignment check
        if direction != direction_hint: return None

        # 2️⃣ Higher-TF Confirmation (H1 + H2 + H4)
        if USE_MULTI_TF:
            h1 = self.mt5.get_history(SYMBOL, mt5.TIMEFRAME_H1, 200)
            h4 = self.mt5.get_history(SYMBOL, mt5.TIMEFRAME_H4, 200)
            tfs_ok = True
            if not h1.empty and not h4.empty:
                h1.columns = [c.lower() for c in h1.columns]
                h4.columns = [c.lower() for c in h4.columns]
                h1_ok = (h1["close"].iloc[-1] > h1["high"].rolling(20).max().iloc[-2]) if direction == 1 else (h1["close"].iloc[-1] < h1["low"].rolling(20).min().iloc[-2])
                h4_ok = (h4["close"].iloc[-1] > h4["high"].rolling(20).max().iloc[-2]) if direction == 1 else (h4["close"].iloc[-1] < h4["low"].rolling(20).min().iloc[-2])
                if not (h1_ok and h4_ok): tfs_ok = False
                
                if USE_H2:
                    h2 = self.mt5.get_history(SYMBOL, mt5.TIMEFRAME_H2, 200)
                    if not h2.empty:
                        h2.columns = [c.lower() for c in h2.columns]
                        h2_ok = (h2["close"].iloc[-1] > h2["high"].rolling(20).max().iloc[-2]) if direction == 1 else (h2["close"].iloc[-1] < h2["low"].rolling(20).min().iloc[-2])
                        if not h2_ok: tfs_ok = False
            
            if not tfs_ok: return None

        # 3️⃣ Entry Price (Retracement)
        atr_val = last_row["atr"]
        retrace = atr_val * ENTRY_RETRACE_ATR
        entry_price = last_row["close"] - direction * retrace
        entry_price = round(entry_price, 2)

        # 4️⃣ ML Filter
        prob = predict_signal(last_row.to_frame().T)
        if prob < ML_THRESHOLD: return None

        # 5️⃣ Dynamic SL / TP / LOT
        sl_dist = (atr_val * SL_ATR_MULTIPLIER + SL_SWIPE_BUFFER)
        sl = entry_price - direction * sl_dist
        
        # Dynamic TP Scaling
        tps = dynamic_tp(entry_price, direction, atr_val, base_mult=TP_MULTIPLIER)
        
        lot = self.calc_lot(entry_price, sl)
        
        return {
            "direction": "buy" if direction == 1 else "sell",
            "entry": entry_price, "sl": sl, "tp": tps, "lot": lot, "prob": prob, "sl_dist": sl_dist, "atr": atr_val
        }

    def calc_lot(self, entry, sl):
        acc = self.mt5.account_info()
        if not acc: return LOT_MIN
        risk_amount = acc.balance * (RISK_PERCENT/100)
        pip_risk = abs(entry - sl)
        if pip_risk == 0: return LOT_MIN
        lot = risk_amount / (pip_risk * 10) 
        return max(min(round(lot, 3), LOT_MAX), LOT_MIN)

    async def break_even_task(self, ticket, entry_price, direction_int, sl_dist):
        """Move SL to BE after BREAK_EVEN_R profit."""
        while True:
            await asyncio.sleep(15)
            pos = mt5.positions_get(ticket=ticket)
            if not pos: break
            tick = mt5.symbol_info_tick(SYMBOL)
            curr = tick.ask if direction_int == 1 else tick.bid
            
            profit_r = abs(curr - entry_price) / sl_dist
            if profit_r >= BREAK_EVEN_R:
                mt5.order_modify(ticket, sl=entry_price + direction_int * 0.1)
                logging.info(f"🔐 BE set for {ticket}")
                tg_send(f"🔐 <b>Break-even Set</b>\nTicket: #{ticket}\nPrice: {entry_price:.2f}")
                break

    async def trailing_task(self, ticket, direction_int, entry_price, sl_dist):
        """Asynchronous trailing stop manager."""
        while True:
            await asyncio.sleep(20)
            pos = mt5.positions_get(ticket=ticket)
            if not pos: break
            tick = mt5.symbol_info_tick(SYMBOL)
            curr = tick.ask if direction_int == 1 else tick.bid
            
            trail_start = entry_price + direction_int * sl_dist * TRAIL_START_R
            if (direction_int == 1 and curr > trail_start) or (direction_int == -1 and curr < trail_start):
                new_sl = curr - direction_int * sl_dist * TRAIL_DISTANCE_R
                if (direction_int == 1 and new_sl > pos[0].sl) or (direction_int == -1 and new_sl < pos[0].sl):
                    mt5.order_modify(ticket, sl=new_sl)
                    # We don't spam TG for every trailing tick, only major moves if needed.

    async def monitor_closure(self, ticket, symbol, direction, entry, tp):
        """Monitor when an order closes to report profit/loss."""
        while True:
            await asyncio.sleep(30)
            pos = mt5.positions_get(ticket=ticket)
            if not pos:
                # Order closed - fetch history
                history = mt5.history_orders_get(ticket=ticket)
                if history:
                    # In a real scenario, we'd fetch the deal profit
                    tg_send(f"🏁 <b>Order Closed</b>\nTicket: #{ticket}\nSymbol: {symbol}\nResult: Check MT5 for PnL")
                    tg_send_summary() # Send summary update
                break

    def log_trade(self, data):
        import csv, os
        path = "logs/trade_log.csv"
        os.makedirs("logs", exist_ok=True)
        headers = ["time", "symbol", "direction", "entry", "sl", "tp1", "tp2", "tp3", "tp4", "lot", "prob"]
        with open(path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if f.tell() == 0: writer.writeheader()
            writer.writerow(data)

    async def run(self):
        logging.info("🚀 SMC Bot (Expert v2) started...")
        tg_send("🚀 <b>SMC Expert v2 Started</b>\nMonitoring XAUUSD M15...")
        while True:
            try:
                df = await self.fetch_and_prepare()
                if not df.empty:
                    signal = self.get_signal(df)
                    if signal:
                        if self.last_entry_time is None or (dt.datetime.now() - self.last_entry_time).seconds > 900:
                            msg = (
                                f"🟢 <b>New {signal['direction'].upper()} Order</b>\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"📍 Entry: {signal['entry']:.2f}\n"
                                f"🛡️ SL: {signal['sl']:.2f}\n"
                                f"🎯 TP1: {signal['tp'][0]:.2f}\n"
                                f"🎯 TP4: {signal['tp'][3]:.2f}\n"
                                f"📊 Prob: {signal['prob']:.2%}\n"
                                f"━━━━━━━━━━━━━━━"
                            )
                            tg_send(msg)
                            tickets = []
                            for i, tp in enumerate(signal["tp"]):
                                part_lot = signal["lot"] * TP_LOT_SPLIT[i]
                                ticket = self.mt5.send_order(SYMBOL, round(part_lot, 2), signal["direction"], 
                                                            signal["entry"], signal["sl"], tp)
                                if ticket: 
                                    tickets.append(ticket)
                                    asyncio.create_task(self.monitor_closure(ticket, SYMBOL, signal['direction'], signal['entry'], tp))
                            
                            if tickets:
                                direction_int = 1 if signal["direction"] == "buy" else -1
                                for t in tickets:
                                    asyncio.create_task(self.break_even_task(t, signal["entry"], direction_int, signal["sl_dist"]))
                                    asyncio.create_task(self.trailing_task(t, direction_int, signal["entry"], signal["sl_dist"]))
                                self.log_trade({
                                    "time": dt.datetime.now().isoformat(), "symbol": SYMBOL, "direction": signal["direction"],
                                    "entry": signal["entry"], "sl": signal["sl"], "tp1": signal["tp"][0],
                                    "tp2": signal["tp"][1], "tp3": signal["tp"][2], "tp4": signal["tp"][3],
                                    "lot": signal["lot"], "prob": signal["prob"]
                                })
                                self.last_entry_time = dt.datetime.now()
                await asyncio.sleep(30)
            except Exception as e:
                logging.error(f"❌ Error: {e}")
                await asyncio.sleep(30)



    def close(self):
        self.mt5.shutdown()

if __name__ == "__main__":
    bot = SMCBot()
    try: asyncio.run(bot.run())
    except KeyboardInterrupt: pass
    finally: bot.close()