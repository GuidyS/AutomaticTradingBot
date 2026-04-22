import MetaTrader5 as mt5
import os

def check():
    if not mt5.initialize():
        print("MT5 Init failed")
        return
    
    positions = mt5.positions_get()
    if positions:
        print(f"Total positions: {len(positions)}")
        for p in positions:
            print(f"Ticket: {p.ticket}, Symbol: {p.symbol}, Magic: {p.magic}, Profit: {p.profit}")
    else:
        print("No positions found.")
    
    mt5.shutdown()

if __name__ == "__main__":
    check()
