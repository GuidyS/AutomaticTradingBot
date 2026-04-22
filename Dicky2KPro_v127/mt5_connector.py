import MetaTrader5 as mt5
import pandas as pd

class MT5Connector:
    def __init__(self, logger):
        self.logger = logger
        self.connected = False

    def connect(self):
        if not mt5.initialize():
            self.logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        
        self.connected = True
        self.logger.info("MT5 initialized successfully")
        return True

    def get_account_info(self):
        info = mt5.account_info()
        if info is None:
            self.logger.error(f"Failed to get account info: {mt5.last_error()}")
            return None
        return info._asdict()

    def get_symbol_info(self, symbol):
        info = mt5.symbol_info(symbol)
        if info is None:
            self.logger.error(f"Symbol {symbol} not found")
            return None
        return info._asdict()

    def get_current_price(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return {"bid": tick.bid, "ask": tick.ask, "spread": (tick.ask - tick.bid)}

    def pips_to_points(self, symbol, pips):
        info = mt5.symbol_info(symbol)
        if info is None: return 0
        # For XAUUSD and most 5-digit brokers, 1 pip = 10 points
        # If it's a 3-digit or 5-digit broker, info.digits will be 3 or 5
        return pips * info.point * 10

    def open_order(self, symbol, order_type, lot, sl_pips=0, tp_pips=0, magic=0, comment=""):
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None: return None
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None: return None
        
        # Determine base price
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        point = symbol_info.point
        digits = symbol_info.digits
        
        # Get minimum stop distance from broker (in points)
        stops_level = symbol_info.trade_stops_level * point
        spread = (tick.ask - tick.bid)
        min_distance = stops_level + spread
        
        # Standard Pip calculation for Gold/Forex
        # For Gold (3 digits), 10 points usually = 1 pip = 0.01 price change
        # However, many traders consider 100 points = 1 pip = 0.10 price change
        # We will use a more robust distance calculation
        sl_dist = self.pips_to_points(symbol, sl_pips)
        tp_dist = self.pips_to_points(symbol, tp_pips)
        
        # Ensure distance is at least Spread + StopsLevel + Padding
        min_dist = min_distance + (5 * point)
        
        sl = 0
        tp = 0
        
        if order_type == mt5.ORDER_TYPE_BUY:
            if sl_pips > 0:
                sl = price - max(sl_dist, min_dist)
            if tp_pips > 0:
                tp = price + max(tp_dist, min_dist)
        else: # SELL
            if sl_pips > 0:
                sl = price + max(sl_dist, min_dist)
            if tp_pips > 0:
                tp = price - max(tp_dist, min_dist)
                
        # Round to correct digits
        if sl > 0: sl = round(sl, digits)
        if tp > 0: tp = round(tp, digits)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": order_type,
            "price": float(price),
            "sl": float(sl),
            "tp": float(tp),
            "magic": int(magic),
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Order failed: {result.comment} (code: {result.retcode})")
            return None
        
        self.logger.info(f"Order opened: {symbol} {order_type} @ {price}")
        return result

    def close_order(self, ticket):
        position = mt5.positions_get(ticket=ticket)
        if not position: return False
        
        pos = position[0]
        symbol = pos.symbol
        lot = pos.volume
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(symbol)
        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": order_type,
            "position": ticket,
            "price": float(price),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Close failed: {result.comment}")
            return False
        return True

    def close_all_positions(self, symbol, magic=None):
        positions = mt5.positions_get(symbol=symbol)
        if not positions: return 0
        
        closed_count = 0
        for pos in positions:
            if magic is None or pos.magic == magic:
                if self.close_order(pos.ticket):
                    closed_count += 1
        
        if closed_count > 0:
            self.logger.info(f"Closed {closed_count} positions for {symbol}")
        return closed_count

    def disconnect(self):
        mt5.shutdown()
        self.connected = False
