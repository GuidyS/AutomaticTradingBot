import MetaTrader5 as mt5
import pandas as pd
import datetime as dt

class MT5:
    def __init__(self, login: int, password: str, server: str):
        if not mt5.initialize(login=login, password=password, server=server):
            print(f"❌ MT5 init failed: {mt5.last_error()}")
            return
        print("✅ MT5 initialized")

    def get_history(self, symbol: str, timeframe: int, n_bars: int) -> pd.DataFrame:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n_bars)
        if rates is None:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def account_info(self):
        return mt5.account_info()

    def send_order(self, symbol: str, lot: float, side: str, 
                   price: float, sl: float, tp: float, magic: int = 20250429) -> int:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": magic,
            "comment": "SMC Bot Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Order failed: {result.retcode}")
            return 0
        return result.order

    def shutdown(self):
        mt5.shutdown()
