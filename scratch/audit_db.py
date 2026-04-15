import sqlite3
import pandas as pd
import os

def analyze_db():
    db_path = 'trades.db'
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    
    # Check tables
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {tables}")
    
    if ('trades',) in tables:
        df = pd.read_sql_query("SELECT * FROM trades WHERE result != 'PENDING'", conn)
        if not df.empty:
            print("\n--- Performance Summary (From 'trades' table) ---")
            print(f"Total Closed Trades: {len(df)}")
            print(f"Total Profit: {df['profit'].sum():.2f}")
            print(f"Win Rate: {(df['result'] == 'WIN').mean()*100:.2f}%")
            print(f"Max Profit: {df['profit'].max():.2f}")
            print(f"Max Loss: {df['profit'].min():.2f}")
            print(f"Average Profit: {df['profit'].mean():.2f}")
            
            # Analyze by symbol
            print("\n--- Performance by Symbol ---")
            print(df.groupby('symbol')['profit'].agg(['count', 'sum', 'mean']))
            
            # Analyze by Session
            print("\n--- Performance by Session ---")
            # 0: Asian, 1: London, 2: NY, 3: Overlap
            session_map = {0: "Asian", 1: "London", 2: "NY", 3: "Overlap"}
            df['session_name'] = df['session_idx'].map(session_map)
            print(df.groupby('session_name')['profit'].agg(['count', 'sum', 'mean']))
        else:
            print("Trades table has no closed trades.")

    conn.close()

if __name__ == "__main__":
    analyze_db()
