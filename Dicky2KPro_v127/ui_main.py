import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QLineEdit, 
                             QPushButton, QTextEdit, QComboBox, QFormLayout, 
                             QStatusBar, QGroupBox, QGridLayout, QListWidget, QListWidgetItem, QAbstractItemView,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import QTimer, Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette
import logging
import MetaTrader5 as mt5

class LogSignal(QObject):
    text_received = pyqtSignal(str)

class GuiLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
    def emit(self, record):
        msg = self.format(record)
        self.signal.text_received.emit(msg)

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
        
        # Setup real-time log streaming
        self.log_signal = LogSignal()
        self.log_signal.text_received.connect(self.append_log)
        
        gui_handler = GuiLogHandler(self.log_signal)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.logger.addHandler(gui_handler)
        
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

        # Status Bar (Initialize early so other functions can use it)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

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

    def setup_dashboard(self):
        layout = QVBoxLayout(self.tab_dashboard)
        
        stats_group = QGroupBox("Account Performance")
        stats_layout = QGridLayout(stats_group)
        stats_layout.setSpacing(15)
        
        self.lbl_symbol = QLabel("Symbol: -")
        self.lbl_price = QLabel("Price: -")
        self.lbl_profit = QLabel("Total Profit: $0.00")
        self.lbl_win_rate = QLabel("Win Rate: 0.0%")
        self.lbl_trades = QLabel("Trades: 0 (W:0 / L:0)")
        self.lbl_floating = QLabel("Floating: $0.00")
        self.lbl_orders = QLabel("Active Orders: 0")
        
        # Style
        style = "font-weight: bold; font-size: 13px;"
        for lbl in [self.lbl_profit, self.lbl_win_rate, self.lbl_trades, self.lbl_orders, self.lbl_floating, self.lbl_symbol, self.lbl_price]:
            lbl.setStyleSheet(style)
        
        self.lbl_profit.setStyleSheet(style + " color: #2ecc71;")
        self.lbl_floating.setStyleSheet(style + " color: #f1c40f;")
        self.lbl_orders.setStyleSheet(style + " color: #3498db;")

        # Grid Layout (Row, Col)
        stats_layout.addWidget(self.lbl_symbol, 0, 0)
        stats_layout.addWidget(self.lbl_price, 0, 1)
        stats_layout.addWidget(self.lbl_orders, 0, 2)
        
        stats_layout.addWidget(self.lbl_profit, 1, 0)
        stats_layout.addWidget(self.lbl_floating, 1, 1)
        stats_layout.addWidget(self.lbl_win_rate, 1, 2)
        
        stats_layout.addWidget(self.lbl_trades, 2, 0, 1, 3) # Span across 3 columns
        
        layout.addWidget(stats_group)
        
        # Recent Trades Table
        layout.addWidget(QLabel("Recent Trades (Last 10):"))
        self.table_recent = QTableWidget(0, 5)
        self.table_recent.setHorizontalHeaderLabels(["Time", "Symbol", "Type", "Lot", "Profit ($)"])
        self.table_recent.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_recent.setStyleSheet("background-color: #1e1e1e; color: white; border: 1px solid #333;")
        layout.addWidget(self.table_recent, 1) # Give it stretch factor
        
        # Controls
        layout.addSpacing(10)
        ctrl_layout = QHBoxLayout()
        self.btn_start = QPushButton("START BOT")
        self.btn_stop = QPushButton("STOP BOT")
        self.btn_start.setStyleSheet("background-color: #2ecc71; color: white; height: 45px; font-weight: bold; border-radius: 5px;")
        self.btn_stop.setStyleSheet("background-color: #e74c3c; color: white; height: 45px; font-weight: bold; border-radius: 5px;")
        
        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addWidget(self.btn_stop)
        layout.addLayout(ctrl_layout)

    def setup_settings(self):
        layout = QFormLayout(self.tab_settings)
        
        self.edit_symbol_list = QListWidget()
        self.edit_symbol_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.edit_symbol_list.setFixedHeight(120)
        
        # Fetch symbols from MT5
        all_symbols_data = mt5.symbols_get()
        if all_symbols_data is None:
            # Try to initialize if not already
            mt5.initialize()
            all_symbols_data = mt5.symbols_get()
            
        all_symbols = [s.name for s in all_symbols_data] if all_symbols_data else []
        current_symbols = [s.strip() for s in self.config.get("symbol", "").split(",") if s.strip()]
        
        # If still no symbols from MT5, at least show the ones from config
        if not all_symbols:
            all_symbols = current_symbols
        
        for sym in sorted(all_symbols):
            # Show symbols in Market Watch or those already selected
            info = mt5.symbol_info(sym)
            if (info and info.select) or sym in current_symbols:
                item = QListWidgetItem(sym)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if sym in current_symbols else Qt.CheckState.Unchecked)
                self.edit_symbol_list.addItem(item)
        
        self.combo_tf = QComboBox()
        self.combo_tf.addItems(["M1", "M5", "M15", "H1"])
        self.combo_tf.setCurrentText(self.config.get("timeframe"))
        
        self.edit_lot = QLineEdit(str(self.config.get("fixed_lot")))
        self.edit_max_lot = QLineEdit(str(self.config.get("max_lot", 0.5)))
        self.edit_max_orders = QLineEdit(str(self.config.get("max_concurrent_orders", 10)))
        self.edit_tp = QLineEdit(str(self.config.get("tp_pips")))
        self.edit_sl = QLineEdit(str(self.config.get("sl_pips")))
        self.edit_min_dist = QLineEdit(str(self.config.get("min_order_distance_pips", 200)))
        
        layout.addRow("Trading Symbols:", self.edit_symbol_list)
        layout.addRow("Timeframe:", self.combo_tf)
        layout.addRow("Fixed Lot:", self.edit_lot)
        layout.addRow("Max Lot:", self.edit_max_lot)
        layout.addRow("Max Total Orders:", self.edit_max_orders)
        layout.addRow("Min Order Distance (Pips):", self.edit_min_dist)
        layout.addRow("Take Profit (Pips):", self.edit_tp)
        layout.addRow("Stop Loss (Pips):", self.edit_sl)
        
        layout.addRow(QLabel("<br><b>Basket Management (USD):</b>"))
        self.chk_basket_enable = QComboBox()
        self.chk_basket_enable.addItems(["Enabled", "Disabled"])
        self.chk_basket_enable.setCurrentText("Enabled" if self.config.get("enable_basket_management") else "Disabled")
        layout.addRow("Basket Mode:", self.chk_basket_enable)
        
        self.edit_basket_tp = QLineEdit(str(self.config.get("basket_tp_usd")))
        self.edit_basket_sl = QLineEdit(str(self.config.get("basket_sl_usd")))
        layout.addRow("Basket TP ($):", self.edit_basket_tp)
        layout.addRow("Basket SL ($):", self.edit_basket_sl)
        
        layout.addRow(QLabel("<br><b>Recovery System (Grid):</b>"))
        self.edit_recovery_step = QLineEdit(str(self.config.get("recovery_step_pips")))
        self.edit_recovery_multiplier = QLineEdit(str(self.config.get("recovery_lot_multiplier")))
        self.edit_recovery_max = QLineEdit(str(self.config.get("max_recovery_orders")))
        layout.addRow("Recovery Step (Pips):", self.edit_recovery_step)
        layout.addRow("Lot Multiplier:", self.edit_recovery_multiplier)
        layout.addRow("Max Recovery Orders:", self.edit_recovery_max)

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
        
        self.combo_ai_model = QComboBox()
        self.refresh_models() # Initial fetch
        
        btn_refresh = QPushButton("🔄 Refresh Local Models")
        btn_refresh.clicked.connect(self.refresh_models)
        
        form.addRow("AI Provider:", self.combo_ai_provider)
        form.addRow("Endpoint URL:", self.edit_ai_endpoint)
        form.addRow("Model Name:", self.combo_ai_model)
        form.addRow("", btn_refresh)
        
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
        self.log_output.setStyleSheet("background-color: #1a1a1a; color: #00ff00; font-family: 'Consolas', monospace;")
        layout.addWidget(self.log_output)

    def append_log(self, text):
        self.log_output.append(text)
        # Auto-scroll to bottom
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def save_settings(self):
        selected_symbols = []
        for i in range(self.edit_symbol_list.count()):
            item = self.edit_symbol_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_symbols.append(item.text())
        
        new_cfg = {
            "symbol": ",".join(selected_symbols),
            "timeframe": self.combo_tf.currentText(),
            "fixed_lot": float(self.edit_lot.text()),
            "max_lot": float(self.edit_max_lot.text()),
            "max_concurrent_orders": int(self.edit_max_orders.text()),
            "min_order_distance_pips": int(self.edit_min_dist.text()),
            "tp_pips": int(self.edit_tp.text()),
            "sl_pips": int(self.edit_sl.text()),
            "enable_basket_management": (self.chk_basket_enable.currentText() == "Enabled"),
            "basket_tp_usd": float(self.edit_basket_tp.text()),
            "basket_sl_usd": float(self.edit_basket_sl.text()),
            "recovery_step_pips": int(self.edit_recovery_step.text()),
            "recovery_lot_multiplier": float(self.edit_recovery_multiplier.text()),
            "max_recovery_orders": int(self.edit_recovery_max.text()),
            "telegram_bot_token": self.edit_tg_token.text(),
            "telegram_chat_id": self.edit_tg_chatid.text(),
            "enable_telegram": (self.chk_tg_enable.currentText() == "Enabled"),
            "ai_provider": self.combo_ai_provider.currentText(),
            "ai_local_endpoint": self.edit_ai_endpoint.text(),
            "ai_model": self.combo_ai_model.currentText()
        }
        self.config.save_config(new_cfg)
        
        # Update the active notifier in the bot engine
        self.bot.notifier.token = new_cfg["telegram_bot_token"]
        self.bot.notifier.chat_id = new_cfg["telegram_chat_id"]
        self.bot.notifier.enabled = new_cfg["enable_telegram"]
        
        self.status_bar.showMessage("Settings saved and Notifier updated!")

    def test_ai(self):
        self.ai_test_log.append("Testing connection...")
        
        # Update config temporarily for test
        self.config.config["ai_provider"] = self.combo_ai_provider.currentText()
        self.config.config["ai_local_endpoint"] = self.edit_ai_endpoint.text()
        self.config.config["ai_model"] = self.combo_ai_model.currentText()
        
        success, msg, response = self.ai.test_ai_connection()
        color = "#00ff00" if success else "#ff0000"
        self.ai_test_log.append(f"<span style='color:{color};'>{msg}</span>")
        if response:
            self.ai_test_log.append(f"AI Response: {response}")

    def refresh_models(self):
        current_model = self.config.get("ai_model")
        # Update endpoint first if user changed it
        if hasattr(self, 'edit_ai_endpoint'):
            self.config.config["ai_local_endpoint"] = self.edit_ai_endpoint.text()
        
        models = self.ai.get_local_models()
        self.combo_ai_model.clear()
        if models:
            self.combo_ai_model.addItems(models)
            if current_model in models:
                self.combo_ai_model.setCurrentText(current_model)
            self.status_bar.showMessage(f"Found {len(models)} local models")
        else:
            self.combo_ai_model.addItem("No models found")
            self.status_bar.showMessage("Failed to fetch models. Is Ollama running?")

    def update_status(self):
        # 1. Update Performance Stats from DB
        stats = self.logger.get_stats()
        if stats:
            self.lbl_profit.setText(f"Total Profit: ${stats['total_profit']:.2f}")
            self.lbl_win_rate.setText(f"Win Rate: {stats['win_rate']:.1f}%")
            self.lbl_trades.setText(f"Trades: {stats['total_trades']} (W:{stats['wins']} / L:{stats['losses']})")

        # 2. Update price and info every second
        symbols_str = self.config.get("symbol", "")
        symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
        
        if symbols:
            primary_symbol = symbols[0]
            price_info = self.bot.mt5.get_current_price(primary_symbol)
            if price_info:
                display_sym = primary_symbol if len(symbols) == 1 else f"{primary_symbol} (+{len(symbols)-1})"
                self.lbl_symbol.setText(f"Symbol: {display_sym}")
                self.lbl_price.setText(f"Price: {price_info['bid']}")
        
        # 3. Update active orders count and floating profit
        import MetaTrader5 as mt5
        positions = mt5.positions_get()
        count = 0
        floating_profit = 0.0
        if positions:
            for p in positions:
                if p.magic == self.config.get("magic_number"):
                    count += 1
                    floating_profit += p.profit
        
        self.lbl_orders.setText(f"Active Orders: {count}")
        self.lbl_floating.setText(f"Floating: ${floating_profit:.2f}")
        
        # Change floating color based on profit/loss
        if floating_profit > 0:
            self.lbl_floating.setStyleSheet("color: #2ecc71; font-weight: bold;")
        elif floating_profit < 0:
            self.lbl_floating.setStyleSheet("color: #e74c3c; font-weight: bold;")
        else:
            self.lbl_floating.setStyleSheet("color: #f1c40f; font-weight: bold;")

        # 4. Update Recent Trades Table
        trades = self.logger.get_recent_trades(10)
        self.table_recent.setRowCount(len(trades))
        for i, t in enumerate(trades):
            self.table_recent.setItem(i, 0, QTableWidgetItem(t['timestamp'][11:])) # Show only HH:MM:SS
            self.table_recent.setItem(i, 1, QTableWidgetItem(t['symbol']))
            self.table_recent.setItem(i, 2, QTableWidgetItem(t['direction']))
            self.table_recent.setItem(i, 3, QTableWidgetItem(str(t['lot'])))
            
            profit = t['profit'] if t['profit'] is not None else 0.0
            profit_item = QTableWidgetItem(f"{profit:.2f}")
            if profit > 0: profit_item.setForeground(QColor("#2ecc71"))
            elif profit < 0: profit_item.setForeground(QColor("#e74c3c"))
            
            self.table_recent.setItem(i, 4, profit_item)
