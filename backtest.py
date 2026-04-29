import argparse
import pandas as pd
import config
from backtest_engine import run_backtest


def main():
    parser = argparse.ArgumentParser(description="Backtest with realistic engine")
    parser.add_argument("csv_path", help="Path to historical OHLC CSV file")
    parser.add_argument("--spread", type=float, default=0.0, help="Spread in price points (added to BUY entry, subtracted from SELL)")
    parser.add_argument("--slippage", type=float, default=0.0, help="Slippage in price points applied to entry price")
    parser.add_argument("--max-holding", type=int, default=0, help="Maximum number of candles a trade can stay open (0 = unlimited)")
    parser.add_argument("--htf-csv", help="Optional higher‑time‑frame CSV for bias filter (e.g., H1)")
    parser.add_argument("--session-start", type=int, default=6, help="UTC hour to start trading (inclusive)")
    parser.add_argument("--session-end", type=int, default=18, help="UTC hour to end trading (inclusive)")
    args = parser.parse_args()

    # Run the backtest engine
    run_backtest(
        args.csv_path,
        spread=args.spread,
        slippage=args.slippage,
        max_holding=args.max_holding,
        htf_csv=args.htf_csv,
        session_start=args.session_start,
        session_end=args.session_end,
    )

if __name__ == "__main__":
    main()