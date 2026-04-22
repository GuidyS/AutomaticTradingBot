import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QLineEdit, 
                             QPushButton, QTextEdit, QComboBox, QFormLayout, 
                             QStatusBar, QGroupBox)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor, QPalette

class Dicky2KProUI(QMainWindow):
    def __init__(self, bot_engine, config_manager, ai_engine, logger):
        super().__init__()
        self.bot = bot_engine
        self.config = config_manager
        self.ai = ai_engine
        self.logger = logger
        
        self.setWindowTitle("Dicky2K Pro v1.2.7 - AI Trading Terminal")
        self.resize(1000, 700)
        self.apply_dark_theme()
        
        self.init_ui()
        
        # Timer for UI updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)

    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(50, 50, 50))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.setPalette(palette)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Header
        header = QLabel("DICKY 2K PRO v1.2.7")
        header.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("color: #00ffcc; margin-bottom: 10px;")
        main_layout.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_dashboard = QWidget()
        self.tab_settings = QWidget()
        self.tab_ai = QWidget()
        self.tab_logs = QWidget()

        self.tabs.addTab(self.tab_dashboard, "📊 Dashboard")
        self.tabs.addTab(self.tab_settings, "⚙️ Settings")
        self.tabs.addTab(self.tab_ai, "🧠 AI Engine")
        self.tabs.addTab(self.tab_logs, "📝 Logs")

        self.setup_dashboard()
        self.setup_settings()
        self.setup_ai_tab()
        self.setup_logs_tab()

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def setup_dashboard(self):
        layout = QVBoxLayout(self.tab_dashboard)
        
        stats_group = QGroupBox("Market Status")
        stats_layout = QHBoxLayout(stats_group)
        
        self.lbl_symbol = QLabel("Symbol: -")
        self.lbl_price = QLabel("Price: -")
        self.lbl_orders = QLabel("Active Orders: 0")
        
        stats_layout.addWidget(self.lbl_symbol)
        stats_layout.addWidget(self.lbl_price)
        stats_layout.addWidget(self.lbl_orders)
        
        layout.addWidget(stats_group)
        
        # Trade History Table placeholder
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        layout.addWidget(QLabel("Recent Trades:"))
        layout.addWidget(self.history_text)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_start = QPushButton("START BOT")
        self.btn_stop = QPushButton("STOP BOT")
        self.btn_start.setStyleSheet("background-color: #28a745; color: white; height: 40px; font-weight: bold;")
        self.btn_stop.setStyleSheet("background-color: #dc3545; color: white; height: 40px; font-weight: bold;")
        
        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addWidget(self.btn_stop)
        layout.addLayout(ctrl_layout)

    def setup_settings(self):
        layout = QFormLayout(self.tab_settings)
        
        self.edit_symbol = QLineEdit(self.config.get("symbol"))
        self.combo_tf = QComboBox()
        self.combo_tf.addItems(["M1", "M5", "M15", "H1"])
        self.combo_tf.setCurrentText(self.config.get("timeframe"))
        
        self.edit_lot = QLineEdit(str(self.config.get("fixed_lot")))
        self.edit_tp = QLineEdit(str(self.config.get("tp_pips")))
        self.edit_sl = QLineEdit(str(self.config.get("sl_pips")))
        
        layout.addRow("Trading Symbol:", self.edit_symbol)
        layout.addRow("Timeframe:", self.combo_tf)
        layout.addRow("Fixed Lot:", self.edit_lot)
        layout.addRow("Take Profit (Pips):", self.edit_tp)
        layout.addRow("Stop Loss (Pips):", self.edit_sl)

        # Telegram Section
        layout.addRow(QLabel("<br><b>Telegram Notifications:</b>"))
        self.edit_tg_token = QLineEdit(self.config.get("telegram_bot_token"))
        self.edit_tg_chatid = QLineEdit(self.config.get("telegram_chat_id"))
        self.chk_tg_enable = QComboBox()
        self.chk_tg_enable.addItems(["Enabled", "Disabled"])
        self.chk_tg_enable.setCurrentText("Enabled" if self.config.get("enable_telegram") else "Disabled")
        
        layout.addRow("Bot Token:", self.edit_tg_token)
        layout.addRow("Chat ID:", self.edit_tg_chatid)
        layout.addRow("Status:", self.chk_tg_enable)

        btn_test_tg = QPushButton("Test Telegram Connection")
        btn_test_tg.clicked.connect(self.test_telegram)
        layout.addRow(btn_test_tg)
        
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self.save_settings)
        layout.addRow(btn_save)

    def test_telegram(self):
        token = self.edit_tg_token.text()
        chat_id = self.edit_tg_chatid.text()
        msg = "🔔 *Dicky2K Pro Test*\nการเชื่อมต่อ Telegram สำเร็จแล้วครับ!"
        
        # Temporary notifier for testing
        from telegram_notifier import TelegramNotifier
        tester = TelegramNotifier(token, chat_id, True)
        if tester.send_message(msg):
            self.status_bar.showMessage("Telegram Test Sent!")
        else:
            self.status_bar.showMessage("Telegram Test Failed! Check Token/Chat ID")

    def setup_ai_tab(self):
        layout = QVBoxLayout(self.tab_ai)
        
        config_group = QGroupBox("AI Configuration")
        form = QFormLayout(config_group)
        
        self.combo_ai_provider = QComboBox()
        self.combo_ai_provider.addItems(["Ollama", "LM Studio", "OpenAI", "Gemini"])
        self.combo_ai_provider.setCurrentText(self.config.get("ai_provider"))
        
        self.edit_ai_endpoint = QLineEdit(self.config.get("ai_local_endpoint"))
        self.edit_ai_model = QLineEdit(self.config.get("ai_model"))
        
        form.addRow("AI Provider:", self.combo_ai_provider)
        form.addRow("Endpoint URL:", self.edit_ai_endpoint)
        form.addRow("Model Name:", self.edit_ai_model)
        
        layout.addWidget(config_group)
        
        self.btn_test_ai = QPushButton("Test AI Connection")
        self.btn_test_ai.clicked.connect(self.test_ai)
        layout.addWidget(self.btn_test_ai)
        
        self.ai_test_log = QTextEdit()
        self.ai_test_log.setReadOnly(True)
        layout.addWidget(self.ai_test_log)

    def setup_logs_tab(self):
        layout = QVBoxLayout(self.tab_logs)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

    def save_settings(self):
        new_cfg = {
            "symbol": self.edit_symbol.text(),
            "timeframe": self.combo_tf.currentText(),
            "fixed_lot": float(self.edit_lot.text()),
            "tp_pips": int(self.edit_tp.text()),
            "sl_pips": int(self.edit_sl.text()),
            "telegram_bot_token": self.edit_tg_token.text(),
            "telegram_chat_id": self.edit_tg_chatid.text(),
            "enable_telegram": (self.chk_tg_enable.currentText() == "Enabled")
        }
        self.config.save_config(new_cfg)
        
        # Update the active notifier in the bot engine
        self.bot.notifier.token = new_cfg["telegram_bot_token"]
        self.bot.notifier.chat_id = new_cfg["telegram_chat_id"]
        self.bot.notifier.enabled = new_cfg["enable_telegram"]
        
        self.status_bar.showMessage("Settings saved and Notifier updated!")

    def test_ai(self):
        self.ai_test_log.append("Testing connection...")
        success, msg, response = self.ai.test_ai_connection()
        color = "#00ff00" if success else "#ff0000"
        self.ai_test_log.append(f"<span style='color:{color};'>{msg}</span>")
        if response:
            self.ai_test_log.append(f"AI Response: {response}")

    def update_status(self):
        # Update price and info every second
        symbol = self.config.get("symbol")
        price_info = self.bot.mt5.get_current_price(symbol)
        if price_info:
            self.lbl_symbol.setText(f"Symbol: {symbol}")
            self.lbl_price.setText(f"Price: {price_info['bid']}")
        
        # Placeholder for real-time log update
        pass
