import sqlite3
import pandas as pd

def deep_audit():
    conn = sqlite3.connect('trades.db')
    df = pd.read_sql_query("SELECT * FROM trades WHERE result != 'PENDING'", conn)
    conn.close()
    
    if df.empty:
        print("No data.")
        return

    # Convert timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    
    print("--- Symbol & Direction Performance ---")
    print(df.groupby(['symbol', 'direction'])['profit'].agg(['count', 'sum', 'mean']))
    
    print("\n--- Hourly Performance (Aggregated) ---")
    hourly = df.groupby('hour')['profit'].agg(['count', 'sum'])
    print(hourly)
    
    print("\n--- Loss Analysis ---")
    losses = df[df['result'] == 'LOSS']
    print(f"Total Losses: {len(losses)}")
    print(f"Average Loss: {losses['profit'].mean():.2f}")
    
    wins = df[df['result'] == 'WIN']
    print(f"Total Wins: {len(wins)}")
    print(f"Average Win: {wins['profit'].mean():.2f}")
    
    print(f"Current Profit/Loss Ratio: {abs(wins['profit'].mean() / losses['profit'].mean()):.2f}")

if __name__ == "__main__":
    deep_audit()
