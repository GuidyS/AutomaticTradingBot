import requests

class TelegramNotifier:
    def __init__(self, token, chat_id, enabled=True):
        self.token = token
        self.chat_id = chat_id
        self.enabled = enabled

    def send_message(self, message):
        if not self.enabled or not self.token or not self.chat_id:
            return
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram error: {e}")
            return False

    def notify_trade_open(self, symbol, direction, lot, price):
        msg = f"🚀 *Order Opened*\nSymbol: {symbol}\nType: {direction}\nLot: {lot}\nPrice: {price}"
        self.send_message(msg)

    def notify_trade_close(self, symbol, profit, status):
        msg = f"🏁 *Order Closed*\nSymbol: {symbol}\nProfit: ${profit:.2f}\nStatus: {status}"
        self.send_message(msg)
