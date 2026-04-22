import logging
import sqlite3
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

class Logger:
    def __init__(self, log_file="app.log", db_file="trades.db"):
        self.db_file = db_file
        
        # Setup logging
        self.logger = logging.getLogger("Dicky2KPro")
        self.logger.setLevel(logging.INFO)
        
        handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Console output
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                direction TEXT,
                lot REAL,
                entry_price REAL,
                tp REAL,
                sl REAL,
                exit_price REAL,
                profit REAL,
                ai_signal TEXT,
                confidence REAL,
                status TEXT,
                comment TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def info(self, msg):
        self.logger.info(msg)

    def error(self, msg):
        self.logger.error(msg)

    def log_trade(self, trade_data):
        """ trade_data: dict with trade details """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            keys = ', '.join(trade_data.keys())
            placeholders = ', '.join(['?'] * len(trade_data))
            values = tuple(trade_data.values())
            cursor.execute(f'INSERT INTO trades ({keys}) VALUES ({placeholders})', values)
            conn.commit()
            conn.close()
            self.info(f"Trade logged: {trade_data.get('symbol')} {trade_data.get('direction')} Profit: {trade_data.get('profit')}")
        except Exception as e:
            self.error(f"Error logging trade to DB: {e}")

    def update_trade_exit(self, trade_id, exit_price, profit, status="CLOSED"):
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE trades 
                SET exit_price = ?, profit = ?, status = ?
                WHERE id = ?
            ''', (exit_price, profit, status, trade_id))
            conn.commit()
            conn.close()
        except Exception as e:
            self.error(f"Error updating trade exit in DB: {e}")
