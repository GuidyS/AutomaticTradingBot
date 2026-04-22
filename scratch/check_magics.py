import MetaTrader5 as mt5
import os

def check_magics():
    if not mt5.initialize():
        print("Initialization failed")
        return

    sym = "XAUUSDc"
    pos = mt5.positions_get(symbol=sym)
    
    if pos:
        print(f"Total positions for {sym}: {len(pos)}")
        magic_counts = {}
        for p in pos:
            magic_counts[p.magic] = magic_counts.get(p.magic, 0) + 1
        
        print("Magic Number Counts:")
        for magic, count in magic_counts.items():
            print(f"  Magic {magic}: {count} orders")
    else:
        print(f"No positions found for {sym}")

    mt5.shutdown()

if __name__ == "__main__":
    check_magics()
