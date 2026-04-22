import requests
import config
import re

def test_telegram():
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    
    print(f"Testing Telegram Notification...")
    if not token or not chat_id:
        print("❌ Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing in .env")
        return

    print(f"Token: {token[:10]}...")
    print(f"Chat ID: {chat_id}")
    
    msg = "🔔 *Test Message*\nYour bot is now connected to **Telegram**!"
    
    # Simple markdown to HTML conversion similar to trader.py
    html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', msg)
    html = re.sub(r'\*(.*?)\*', r'<b>\1</b>', html)
    html = html.replace('[','(').replace(']',')')
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": html,
        "parse_mode": "HTML"
    }
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Success! Check your Telegram.")
        else:
            print(f"❌ Failed: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_telegram()
