import requests
import config

def test_line():
    token = config.LINE_CHANNEL_ACCESS_TOKEN
    user_id = str(config.LINE_USER_ID)
    
    print(f"Testing LINE Notification...")
    print(f"Token: {token[:10]}...")
    print(f"User ID: {user_id}")
    
    user_ids = [uid.strip() for uid in user_id.split(',') if uid.strip()]
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    for uid in user_ids:
        url = "https://api.line.me/v2/bot/message/push"
        data = {
            "to": uid,
            "messages": [{"type": "text", "text": "🔔 Test: Bot is online and checking LINE connectivity."}]
        }
        try:
            r = requests.post(url, headers=headers, json=data, timeout=10)
            print(f"Response for {uid}: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Error for {uid}: {e}")

if __name__ == "__main__":
    test_line()
