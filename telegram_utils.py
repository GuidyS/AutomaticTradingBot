import requests
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def tg_send(message: str):
    """Send a text message to Telegram chat."""
    if not TOKEN or not CHAT_ID: 
        print("⚠️ Telegram Token or Chat ID not found in .env")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def tg_send_summary():
    """Calculate and send performance summary from trade_log.csv."""
    path = "logs/trade_log.csv"
    if not os.path.exists(path): return
    
    try:
        df = pd.read_csv(path)
        if df.empty: return
        
        total = len(df)
        buys = len(df[df['direction'] == 'buy'])
        sells = len(df[df['direction'] == 'sell'])
        
        # Note: In trade_log.csv we might not have the 'result' yet if it's just an entry log.
        # This summary is best called after some trades are closed.
        
        msg = (
            "<b>📊 Performance Summary</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📈 Total Trades: {total}\n"
            f"🔵 Buy Orders: {buys}\n"
            f"🔴 Sell Orders: {sells}\n"
            f"━━━━━━━━━━━━━━━"
        )
        tg_send(msg)
    except Exception as e:
        print(f"❌ Summary Error: {e}")
