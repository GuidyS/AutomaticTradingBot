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
        # For most brokers, 1 pip = 10 points
        return pips * info.point * 10

    def open_order(self, symbol, order_type, lot, sl_pips=0, tp_pips=0, magic=0, comment=""):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None: return None
        
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        point = mt5.symbol_info(symbol).point
        
        sl = 0
        tp = 0
        
        if sl_pips > 0:
            sl_points = self.pips_to_points(symbol, sl_pips)
            sl = price - sl_points if order_type == mt5.ORDER_TYPE_BUY else price + sl_points
            
        if tp_pips > 0:
            tp_points = self.pips_to_points(symbol, tp_pips)
            tp = price + tp_points if order_type == mt5.ORDER_TYPE_BUY else price - tp_points

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

    def disconnect(self):
        mt5.shutdown()
        self.connected = False
