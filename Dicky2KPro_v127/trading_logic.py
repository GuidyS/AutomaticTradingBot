import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
from datetime import datetime

class TradingLogic:
    def __init__(self, mt5_conn, ai_engine, logger, config_manager, notifier, news_filter):
        self.mt5 = mt5_conn
        self.ai = ai_engine
        self.logger = logger
        self.config = config_manager
        self.notifier = notifier
        self.news = news_filter
        self.status_msg = ""

    def run_tick(self, symbol):
        if not symbol: return
        max_orders = self.config.get("max_concurrent_orders")
        
        # 0. Check Spread Filter
        tick = self.mt5.get_current_price(symbol)
        if not tick: return
        
        # 0.1 Check News Filter (High Impact USD)
        is_safe, mins_left = self.news.is_safe_to_trade(avoidance_mins=30)
        if not is_safe:
            msg = f"🚫 NEWS DANGER ZONE: USD Red Box News at {abs(mins_left):.0f} mins. Skipping trading."
            if "NEWS DANGER" not in self.status_msg:
                self.logger.info(msg)
            self.status_msg = msg
            return
        
        # Convert raw spread to pips (Gold/Forex)
        current_spread_pips = (tick['ask'] - tick['bid']) / (self.mt5.get_symbol_info(symbol)['point'] * 10)
        max_spread = self.config.get("max_spread_pips", 50)
        if current_spread_pips > max_spread:
            self.status_msg = f"Spread too high: {current_spread_pips:.1f} pips. Waiting..."
            return
        
        # 1. Global Basket Management (Across all symbols)
        all_positions = mt5.positions_get()
        total_profit = 0
        total_orders_count = 0
        symbol_positions = []
        
        if all_positions:
            for pos in all_positions:
                if pos.magic == self.config.get("magic_number"):
                    total_profit += pos.profit
                    total_orders_count += 1
                    if pos.symbol == symbol:
                        symbol_positions.append(pos)

            if self.config.get("enable_basket_management", True):
                # Global Basket TP
                tp_target = self.config.get("basket_tp_usd", 10.0)
                if total_profit >= tp_target:
                    msg = f"💰 *GLOBAL BASKET TP REACHED*\nProfit: ${total_profit:.2f}\nAction: Closed All Symbols"
                    self.logger.info(msg)
                    
                    # Record trades before closing
                    for pos in all_positions:
                        if pos.magic == self.config.get("magic_number"):
                            self.logger.log_trade({
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "symbol": pos.symbol,
                                "direction": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                                "lot": pos.volume,
                                "entry_price": pos.price_open,
                                "exit_price": tick['bid'] if pos.type == mt5.ORDER_TYPE_BUY else tick['ask'],
                                "profit": pos.profit,
                                "status": "TP_BASKET"
                            })
                    
                    self.mt5.close_all_positions(None, self.config.get("magic_number")) # Close ALL symbols
                    self.notifier.send_message(msg)
                    return

                # Global Basket SL
                sl_limit = self.config.get("basket_sl_usd", -50.0)
                if total_profit <= sl_limit:
                    msg = f"⚠️ *GLOBAL BASKET SL (CUT LOSS)*\nLoss: ${total_profit:.2f}\nAction: Closed All Symbols"
                    self.logger.info(msg)
                    
                    # Record trades before closing
                    for pos in all_positions:
                        if pos.magic == self.config.get("magic_number"):
                            self.logger.log_trade({
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "symbol": pos.symbol,
                                "direction": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                                "lot": pos.volume,
                                "entry_price": pos.price_open,
                                "exit_price": tick['bid'] if pos.type == mt5.ORDER_TYPE_BUY else tick['ask'],
                                "profit": pos.profit,
                                "status": "SL_BASKET"
                            })
                            
                    self.mt5.close_all_positions(None, self.config.get("magic_number")) # Close ALL symbols
                    self.notifier.send_message(msg)
                    return

        # Max orders check (Global)
        max_orders = self.config.get("max_concurrent_orders", 10)
        if total_orders_count >= max_orders:
            return

        # 2. Prepare Market Data
        market_data = self._get_market_data(symbol)
        if not market_data: return
        tick = self.mt5.get_current_price(symbol)
        if not tick: return

        # 3. Check for Recovery Opportunity (Symbol-Specific)
        recovery_signal = None
        recovery_lot = self.config.get("fixed_lot")
        
        if symbol_positions:
            buy_positions = [p for p in symbol_positions if p.type == mt5.ORDER_TYPE_BUY]
            sell_positions = [p for p in symbol_positions if p.type == mt5.ORDER_TYPE_SELL]
            
            step_points = self.mt5.pips_to_points(symbol, self.config.get("recovery_step_pips", 200))
            current_tick = self.mt5.get_current_price(symbol)
            
            if buy_positions:
                lowest_buy = min(p.price_open for p in buy_positions)
                if current_tick['bid'] <= (lowest_buy - step_points) and len(buy_positions) < self.config.get("max_recovery_orders", 5):
                    recovery_signal = "BUY"
                    recovery_lot = buy_positions[-1].volume * self.config.get("recovery_lot_multiplier", 1.0)
            
            if sell_positions:
                highest_sell = max(p.price_open for p in sell_positions)
                if current_tick['ask'] >= (highest_sell + step_points) and len(sell_positions) < self.config.get("max_recovery_orders", 5):
                    recovery_signal = "SELL"
                    recovery_lot = sell_positions[-1].volume * self.config.get("recovery_lot_multiplier", 1.0)

        if recovery_signal:
            self.logger.info(f"Recovery Triggered: {recovery_signal} at distance. New Lot: {recovery_lot}")
            self._execute_trade(symbol, recovery_signal, {"confidence": 100, "reason": "Recovery Grid"}, lot=recovery_lot)
            return

        # 4. SMC + Trend Following Logic
        trend = market_data.get("trend")
        bos = market_data.get("bos")
        ob_zone = market_data.get("ob_zone")
        
        signal = "HOLD"
        reason = ""
        
        # BUY Condition: Trend UP + Bullish BOS + Price near Bullish OB
        if trend == "UP" and bos == "BULLISH_BOS":
            if ob_zone and tick['bid'] <= ob_zone * 1.002: # Within 20 pips of OB
                signal = "BUY"
                reason = "SMC: Trend UP + Bullish BOS + Near OB Zone"
        
        # SELL Condition: Trend DOWN + Bearish BOS + Price near Bearish OB
        elif trend == "DOWN" and bos == "BEARISH_BOS":
            if ob_zone and tick['ask'] >= ob_zone * 0.998: # Within 20 pips of OB
                signal = "SELL"
                reason = "SMC: Trend DOWN + Bearish BOS + Near OB Zone"

        if signal != "HOLD":
            # Check Minimum Distance for NEW trades
            if symbol_positions:
                min_dist_points = self.mt5.pips_to_points(symbol, self.config.get("min_order_distance_pips", 100))
                nearest_dist = min(abs(p.price_open - tick['bid']) for p in symbol_positions)
                if nearest_dist < min_dist_points:
                    self.status_msg = f"SMC Signal {signal} ignored: Too close to existing order"
                    return

            self.logger.info(f"SMC Signal: {signal} - {reason}")
            self._execute_trade(symbol, signal, {"confidence": 100, "reason": reason})

    def _calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs.iloc[-1]))

    def _get_market_data(self, symbol):
        tick = self.mt5.get_current_price(symbol)
        if not tick: return None
        
        # Get more candles for SMC analysis (100 candles)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
        if rates is None: return None
        
        df = pd.DataFrame(rates)
        
        # 1. Trend Filter (EMA 200)
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        current_ema = df['ema200'].iloc[-1]
        trend = "UP" if tick['bid'] > current_ema else "DOWN"
        
        # 2. Market Structure (Simple BOS)
        highs = df['high'].rolling(window=5, center=True).max()
        lows = df['low'].rolling(window=5, center=True).min()
        
        last_high = highs.iloc[-10:-1].max()
        last_low = lows.iloc[-10:-1].min()
        
        bos = None
        if df['close'].iloc[-1] > last_high: bos = "BULLISH_BOS"
        if df['close'].iloc[-1] < last_low: bos = "BEARISH_BOS"

        # 3. Order Block (OB) Detection
        ob_zone = None
        if trend == "UP":
            for i in range(len(df)-2, 10, -1):
                if df['close'].iloc[i] < df['open'].iloc[i]:
                    ob_zone = df['low'].iloc[i]
                    break
        else:
            for i in range(len(df)-2, 10, -1):
                if df['close'].iloc[i] > df['open'].iloc[i]:
                    ob_zone = df['high'].iloc[i]
                    break
        
        return {
            "symbol": symbol,
            "price": tick['bid'],
            "trend": trend,
            "bos": bos,
            "ob_zone": ob_zone,
            "indicators": {
                "ema200": current_ema,
                "rsi": self._calculate_rsi(df['close']),
                "spread": tick['spread']
            }
        }

    def _execute_trade(self, symbol, signal, ai_data, lot=None):
        if lot is None:
            lot_mode = self.config.get("lot_size_mode")
            lot = self.config.get("fixed_lot")
            if lot_mode == "RISK":
                # Risk calculation logic (Optional)
                pass

        # Apply Max Lot limit
        max_lot = self.config.get("max_lot", 0.5)
        if lot > max_lot:
            self.logger.warning(f"Trade capped: Requested {lot} but Max Lot is {max_lot}")
            lot = max_lot

        order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
        
        result = self.mt5.open_order(
            symbol=symbol,
            order_type=order_type,
            lot=lot,
            sl_pips=self.config.get("sl_pips"),
            tp_pips=self.config.get("tp_pips"),
            magic=self.config.get("magic_number"),
            comment=self.config.get("comment")
        )
        
        if result:
            trade_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": symbol,
                "direction": signal,
                "lot": lot,
                "entry_price": result.price,
                "tp": result.request.tp,
                "sl": result.request.sl,
                "ai_signal": signal,
                "confidence": ai_data.get("confidence"),
                "status": "OPEN",
                "comment": self.config.get("comment")
            }
            self.logger.log_trade(trade_data)
            self.notifier.notify_trade_open(symbol, signal, lot, result.price)

import pandas as pd
