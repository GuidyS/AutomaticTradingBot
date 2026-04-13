import sqlite3
import os

DB_FILE = 'trades.db'

def get_connection():
    return sqlite3.connect(DB_FILE)

def setup_db():
    """สร้าง Database และ Table อัตโนมัติหากยังไม่มี (เป็นไฟล์ .db)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # SQLite ใช้ INTEGER PRIMARY KEY AUTOINCREMENT แทน INT AUTO_INCREMENT
    table_query = """
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket BIGINT,
        timestamp DATETIME,
        symbol TEXT,
        m30_trend TEXT,
        m5_signal TEXT,
        direction TEXT,
        rsi_m5 REAL,
        ema_dist_m5 REAL,
        trade_hour INTEGER,
        day_of_week INTEGER,
        candle_pattern TEXT,
        volatility REAL,
        h1_trend TEXT,
        macd_diff REAL,
        bb_position TEXT,
        smc_fvg TEXT,
        smc_zone TEXT,
        profit REAL,
        result TEXT,
        account_id BIGINT,
        session_idx INTEGER,
        rel_volume REAL,
        xau_strength REAL,
        usd_strength REAL,
        virtual_sl REAL
    )
    """
    cursor.execute(table_query)
    
    # พยายามเพิ่ม Column สำหรับคนที่เคยรันเวอร์ชันเก่าไปแล้ว
    columns_to_check = [
        ("h1_trend", "TEXT"),
        ("macd_diff", "REAL"),
        ("bb_position", "TEXT"),
        ("smc_fvg", "TEXT"),
        ("smc_zone", "TEXT"),
        ("account_id", "BIGINT"),
        ("session_idx", "INTEGER"),
        ("rel_volume", "REAL"),
        ("xau_strength", "REAL"),
        ("usd_strength", "REAL")
    ]

    for col_name, col_type in columns_to_check:
        try:
            cursor.execute(f"ALTER TABLE trades ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to trades table.")
        except sqlite3.OperationalError:
            pass
    
    # [P4] Add virtual_sl column separately
    try:
        cursor.execute("ALTER TABLE trades ADD COLUMN virtual_sl REAL")
        print("Added column virtual_sl to trades table.")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()
    
    # Initialize settings table
    setup_settings_table()
    
    print("Database check/upgrade completed using SQLite.")

def setup_settings_table():
    """สร้างตารางสำหรับเก็บค่าสถานะของบอท (Bot Settings/State)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error setting up settings table: {e}")

def get_bot_setting(key, default=None):
    """ดึงค่าจากตาราง bot_settings"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            # ลองแปลงเป็นชนิดข้อมูลที่เหมาะสม
            val = row[0]
            if val.lower() == 'true': return True
            if val.lower() == 'false': return False
            try:
                if '.' in val: return float(val)
                return int(val)
            except:
                return val
        return default
    except Exception:
        return default

def set_bot_setting(key, value):
    """บันทึกค่าลงในตาราง bot_settings"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error setting bot setting: {e}")

def log_trade(ticket, timestamp, symbol, m30_trend, h1_trend, smc_fvg, smc_zone, m5_signal, direction, rsi_m5, macd_diff, bb_position, ema_dist_m5, trade_hour, day_of_week, candle_pattern, volatility, profit, result, account_id, session_idx, rel_volume, xau_strength, usd_strength, virtual_sl=0.0):
    """บันทึกข้อมูลการเทรดลงฐานข้อมูล SQLite"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # SQLite ใช้เครื่องหมาย ? แทน %s
        query = """
        INSERT INTO trades (ticket, timestamp, symbol, m30_trend, h1_trend, smc_fvg, smc_zone, m5_signal, direction, rsi_m5, macd_diff, bb_position, ema_dist_m5, trade_hour, day_of_week, candle_pattern, volatility, profit, result, account_id, session_idx, rel_volume, xau_strength, usd_strength, virtual_sl)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (int(ticket), timestamp, symbol, m30_trend, h1_trend, smc_fvg, smc_zone, m5_signal, direction, float(rsi_m5), float(macd_diff), bb_position, float(ema_dist_m5), int(trade_hour), int(day_of_week), candle_pattern, float(volatility), profit, result, int(account_id), int(session_idx), float(rel_volume), float(xau_strength), float(usd_strength), float(virtual_sl)))
        conn.commit()
    except Exception as e:
        print(f"Error logging trade: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def update_pending_trades(ticket, profit, result):
    """อัปเดตออเดอร์ล่าสุดที่ยังคงค้าง (PENDING) ให้เป็น WIN หรือ LOSS ตาม Ticket"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # SQLite ใช้เครื่องหมาย ? แทน %s
        query = """
        UPDATE trades 
        SET profit = ?, result = ?
        WHERE ticket = ? AND result = 'PENDING'
        """
        cursor.execute(query, (profit, result, int(ticket)))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        print(f"Error updating trade: {e}")
        return 0
    finally:
        if 'conn' in locals():
            conn.close()

def is_deal_notified(ticket):
    """ตรวจสอบว่า Deal นี้ถูกแจ้งเตือนไปแล้วหรือยัง (ใช้ SQLite)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # สร้างตารางถ้ายังไม่มี (sqlite_master)
        cursor.execute("CREATE TABLE IF NOT EXISTS notified_deals (ticket BIGINT PRIMARY KEY)")
        cursor.execute("SELECT 1 FROM notified_deals WHERE ticket = ?", (int(ticket),))
        res = cursor.fetchone()
        return res is not None
    except Exception:
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def mark_deal_as_notified(ticket):
    """บันทึกว่า Deal นี้แจ้งเตือนไปแล้วเพื่อป้องกันการส่งซ้ำ"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS notified_deals (ticket BIGINT PRIMARY KEY)")
        cursor.execute("INSERT OR IGNORE INTO notified_deals (ticket) VALUES (?)", (int(ticket),))
        conn.commit()
    except Exception as e:
        print(f"Error marking deal as notified: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def get_performance_summary(hours=12):
    """ดึงสถิติการเทรดในช่วงเวลาที่กำหนด (ชั่วโมง) และคำนวณกำไร/WinRate"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ค้นหาข้อมูลช่วงย้อนหลัง (SQLite ใช้ datetime('now', '-N hours'))
        query = f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(profit) as net_profit
        FROM trades
        WHERE result != 'PENDING' 
          AND timestamp >= datetime('now', '-{hours} hours')
        """
        cursor.execute(query)
        row = cursor.fetchone()
        
        if row and row[0] > 0:
            total, wins, losses, net_profit = row
            win_rate = (wins / total) * 100 if total > 0 else 0
            return {
                "total": total,
                "wins": wins,
                "losses": losses,
                "net_profit": net_profit if net_profit else 0.0,
                "win_rate": win_rate
            }
        return None
    except Exception as e:
        print(f"Error getting summary: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()
