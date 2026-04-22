import sys
from PyQt6.QtWidgets import QApplication
from config_manager import ConfigManager
from logger import Logger
from telegram_notifier import TelegramNotifier
from mt5_connector import MT5Connector
from ai_engine import AIEngine
from trading_logic import TradingLogic
from ui_main import Dicky2KProUI
import threading
import time

class Dicky2KBot:
    def __init__(self):
        self.config = ConfigManager("config.json")
        self.logger = Logger()
        
        self.notifier = TelegramNotifier(
            self.config.get("telegram_bot_token"),
            self.config.get("telegram_chat_id"),
            self.config.get("enable_telegram")
        )
        
        self.mt5 = MT5Connector(self.logger)
        self.ai = AIEngine(self.logger, self.config)
        self.logic = TradingLogic(self.mt5, self.ai, self.logger, self.config, self.notifier)
        
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            self.logger.info("Bot is already running")
            return False
            
        if not self.mt5.connect():
            self.logger.error("Failed to connect to MT5")
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        self.logger.info("Bot execution thread started")
        return True

    def stop(self):
        self.running = False
        self.mt5.disconnect()
        self.logger.info("Bot stopped")

    def loop(self):
        while self.running:
            try:
                self.logic.run_tick()
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
            time.sleep(1) # Frequency of check

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    bot_engine = Dicky2KBot()
    
    # Initialize UI
    window = Dicky2KProUI(bot_engine, bot_engine.config, bot_engine.ai, bot_engine.logger)
    
    # Connect UI buttons to bot engine
    window.btn_start.clicked.connect(bot_engine.start)
    window.btn_stop.clicked.connect(bot_engine.stop)
    
    window.show()
    sys.exit(app.exec())
