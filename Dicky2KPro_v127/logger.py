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
        
        self.signals = None
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
        if hasattr(self, 'signals') and self.signals: 
            self.signals.log_signal.emit(f"INFO: {msg}")

    def warning(self, msg):
        self.logger.warning(msg)
        if hasattr(self, 'signals') and self.signals: 
            self.signals.log_signal.emit(f"WARN: {msg}")

    def debug(self, msg):
        self.logger.debug(msg)
        if hasattr(self, 'signals') and self.signals: 
            self.signals.log_signal.emit(f"DEBUG: {msg}")

    def error(self, msg):
        self.logger.error(msg)
        if hasattr(self, 'signals') and self.signals: 
            self.signals.log_signal.emit(f"ERROR: {msg}")

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

    def get_stats(self):
        """ Calculate performance stats from DB """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Total Profit
            cursor.execute("SELECT SUM(profit) FROM trades")
            total_profit = cursor.fetchone()[0] or 0.0
            
            # Win/Loss counts
            cursor.execute("SELECT COUNT(*) FROM trades WHERE profit > 0")
            wins = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM trades WHERE profit <= 0")
            losses = cursor.fetchone()[0] or 0
            
            total_trades = wins + losses
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            
            conn.close()
            return {
                "total_profit": total_profit,
                "wins": wins,
                "losses": losses,
                "total_trades": total_trades,
                "win_rate": win_rate
            }
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return None

    def get_recent_trades(self, limit=10):
        """ Fetch the last N trades from the database """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, symbol, direction, lot, entry_price, exit_price, profit, status
                FROM trades 
                WHERE status != 'OPEN' AND profit IS NOT NULL
                ORDER BY id DESC 
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            conn.close()
            
            trades = []
            for r in rows:
                trades.append({
                    "timestamp": r[0],
                    "symbol": r[1],
                    "direction": r[2],
                    "lot": r[3],
                    "entry_price": r[4],
                    "exit_price": r[5],
                    "profit": r[6],
                    "status": r[7]
                })
            return trades
        except Exception as e:
            self.logger.error(f"Error fetching recent trades: {e}")
            return []
