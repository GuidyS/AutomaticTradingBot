import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

def test_symbol_case():
    if not mt5.initialize():
        print("Initialization failed")
        return

    # Try both cases
    sym_upper = "XAUUSDc"
    sym_lower = "xauusdc"
    
    pos_upper = mt5.positions_get(symbol=sym_upper)
    pos_lower = mt5.positions_get(symbol=sym_lower)
    pos_all = mt5.positions_get()
    
    print(f"Checking Symbol: {sym_upper}")
    print(f"Positions (Upper): {len(pos_upper) if pos_upper else 0}")
    print(f"Checking Symbol: {sym_lower}")
    print(f"Positions (Lower): {len(pos_lower) if pos_lower else 0}")
    
    if pos_all:
        print(f"Total Positions (All): {len(pos_all)}")
        unique_syms = set(p.symbol for p in pos_all)
        print(f"Symbols found in MT5: {unique_syms}")
    else:
        print("No open positions found.")

    mt5.shutdown()

if __name__ == "__main__":
    test_symbol_case()
