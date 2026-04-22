"""
สคริปต์วิเคราะห์ปัญหาการเทรด XAUUSDc จาก Database
- สรุปภาพรวม Win/Loss
- วิเคราะห์แยก Scalp vs Grid
- ดูช่วงเวลาที่ขาดทุน
- ดูปัจจัยที่ทำให้แพ้
"""
import sqlite3
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_FILE = 'trades.db'

def analyze():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ========== 1. ภาพรวมทั้งหมด ==========
    print("=" * 70)
    print("📊 1. ภาพรวมการเทรดทั้งหมด (XAUUSDc)")
    print("=" * 70)
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result='PENDING' THEN 1 ELSE 0 END) as pending,
            SUM(profit) as net_profit,
            SUM(CASE WHEN result='WIN' THEN profit ELSE 0 END) as win_profit,
            SUM(CASE WHEN result='LOSS' THEN profit ELSE 0 END) as loss_profit,
            AVG(CASE WHEN result='WIN' THEN profit END) as avg_win,
            AVG(CASE WHEN result='LOSS' THEN profit END) as avg_loss,
            MIN(profit) as worst_trade,
            MAX(profit) as best_trade
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
    """)
    row = cur.fetchone()
    if row and row['total'] > 0:
        total = row['total']
        wins = row['wins'] or 0
        losses = row['losses'] or 0
        net = row['net_profit'] or 0
        win_profit = row['win_profit'] or 0
        loss_profit = row['loss_profit'] or 0
        avg_win = row['avg_win'] or 0
        avg_loss = row['avg_loss'] or 0
        wr = (wins / total * 100) if total > 0 else 0
        print(f"  Total Trades : {total}")
        print(f"  WIN          : {wins}  ({wr:.1f}%)")
        print(f"  LOSS         : {losses}  ({100-wr:.1f}%)")
        print(f"  Net Profit   : ${net:.2f}")
        print(f"  Win Profit   : ${win_profit:.2f}")
        print(f"  Loss Profit  : ${loss_profit:.2f}")
        print(f"  Avg WIN      : ${avg_win:.2f}")
        print(f"  Avg LOSS     : ${avg_loss:.2f}")
        print(f"  Best Trade   : ${row['best_trade']:.2f}")
        print(f"  Worst Trade  : ${row['worst_trade']:.2f}")
        if avg_win and avg_loss:
            rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            print(f"  Risk/Reward  : 1:{rr:.2f}")
    
    # ========== 2. แยก Scalp vs Grid ==========
    print("\n" + "=" * 70)
    print("📊 2. แยกผลลัพธ์ Scalp vs Grid (ดูจาก direction/comment)")
    print("=" * 70)
    
    # Grid trades มักมี direction เป็น BUY หรือ SELL เหมือนกัน
    # แต่เราสามารถดูจาก m5_signal ว่ามี GRID หรือไม่
    cur.execute("""
        SELECT 
            direction,
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(profit) as net_profit,
            AVG(profit) as avg_profit
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
        GROUP BY direction
    """)
    for row in cur.fetchall():
        total = row['total']
        wins = row['wins'] or 0
        wr = (wins / total * 100) if total > 0 else 0
        print(f"  {row['direction']:8s} | Total: {total:4d} | Win: {wins:4d} ({wr:5.1f}%) | Net: ${row['net_profit'] or 0:.2f} | Avg: ${row['avg_profit'] or 0:.2f}")

    # ========== 3. วิเคราะห์ตามชั่วโมง ==========
    print("\n" + "=" * 70)
    print("📊 3. ผลลัพธ์แยกตามชั่วโมง (Trade Hour)")
    print("=" * 70)
    cur.execute("""
        SELECT 
            trade_hour,
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(profit) as net_profit
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
        GROUP BY trade_hour
        ORDER BY trade_hour
    """)
    for row in cur.fetchall():
        total = row['total']
        wins = row['wins'] or 0
        wr = (wins / total * 100) if total > 0 else 0
        net = row['net_profit'] or 0
        bar = "🟢" if net >= 0 else "🔴"
        print(f"  {bar} Hour {row['trade_hour']:2d} | Trades: {total:4d} | WinRate: {wr:5.1f}% | Net: ${net:+.2f}")

    # ========== 4. วิเคราะห์ตาม Session ==========
    print("\n" + "=" * 70)
    print("📊 4. ผลลัพธ์แยกตาม Market Session")
    print("=" * 70)
    session_map = {0: "Asian", 1: "London", 2: "NY", 3: "Overlap"}
    cur.execute("""
        SELECT 
            session_idx,
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(profit) as net_profit
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
        GROUP BY session_idx
        ORDER BY session_idx
    """)
    for row in cur.fetchall():
        total = row['total']
        wins = row['wins'] or 0
        wr = (wins / total * 100) if total > 0 else 0
        net = row['net_profit'] or 0
        session_name = session_map.get(row['session_idx'], f"Unknown({row['session_idx']})")
        bar = "🟢" if net >= 0 else "🔴"
        print(f"  {bar} {session_name:10s} | Trades: {total:4d} | WinRate: {wr:5.1f}% | Net: ${net:+.2f}")

    # ========== 5. วิเคราะห์ตาม M30 Trend ==========
    print("\n" + "=" * 70)
    print("📊 5. ผลลัพธ์แยกตาม M30 Trend")
    print("=" * 70)
    cur.execute("""
        SELECT 
            m30_trend,
            direction,
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(profit) as net_profit
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
        GROUP BY m30_trend, direction
        ORDER BY m30_trend, direction
    """)
    for row in cur.fetchall():
        total = row['total']
        wins = row['wins'] or 0
        wr = (wins / total * 100) if total > 0 else 0
        net = row['net_profit'] or 0
        bar = "🟢" if net >= 0 else "🔴"
        print(f"  {bar} M30={row['m30_trend']:5s} + {row['direction']:4s} | Trades: {total:4d} | WinRate: {wr:5.1f}% | Net: ${net:+.2f}")

    # ========== 6. วิเคราะห์ตาม RSI Range ==========
    print("\n" + "=" * 70)
    print("📊 6. ผลลัพธ์แยกตาม RSI Range (M5)")
    print("=" * 70)
    cur.execute("""
        SELECT 
            CASE 
                WHEN rsi_m5 < 30 THEN 'Oversold (<30)'
                WHEN rsi_m5 BETWEEN 30 AND 40 THEN '30-40'
                WHEN rsi_m5 BETWEEN 40 AND 50 THEN '40-50'
                WHEN rsi_m5 BETWEEN 50 AND 60 THEN '50-60'
                WHEN rsi_m5 BETWEEN 60 AND 70 THEN '60-70'
                WHEN rsi_m5 > 70 THEN 'Overbought (>70)'
            END as rsi_range,
            direction,
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(profit) as net_profit
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
        GROUP BY rsi_range, direction
        ORDER BY rsi_range, direction
    """)
    for row in cur.fetchall():
        total = row['total']
        wins = row['wins'] or 0
        wr = (wins / total * 100) if total > 0 else 0
        net = row['net_profit'] or 0
        bar = "🟢" if net >= 0 else "🔴"
        print(f"  {bar} RSI {row['rsi_range']:18s} + {row['direction']:4s} | Trades: {total:4d} | WinRate: {wr:5.1f}% | Net: ${net:+.2f}")

    # ========== 7. วิเคราะห์ LOSS ที่ใหญ่ที่สุด 20 รายการ ==========
    print("\n" + "=" * 70)
    print("📊 7. Top 20 LOSS ที่ใหญ่ที่สุด")
    print("=" * 70)
    cur.execute("""
        SELECT ticket, timestamp, direction, profit, rsi_m5, m30_trend, h1_trend, 
               smc_zone, trade_hour, volatility
        FROM trades 
        WHERE symbol LIKE '%XAUUSD%' AND result = 'LOSS'
        ORDER BY profit ASC
        LIMIT 20
    """)
    for row in cur.fetchall():
        print(f"  🔴 ${row['profit']:+.2f} | {row['direction']:4s} | RSI:{row['rsi_m5'] or 0:.0f} | M30:{row['m30_trend']} H1:{row['h1_trend']} | Zone:{row['smc_zone']} | Hour:{row['trade_hour']} | Vol:{row['volatility'] or 0:.2f} | {row['timestamp']}")

    # ========== 8. Grid vs Scalp (ตาม m5_signal) ==========
    print("\n" + "=" * 70)
    print("📊 8. แยกประเภท Order จาก m5_signal")
    print("=" * 70)
    cur.execute("""
        SELECT 
            m5_signal,
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(profit) as net_profit,
            AVG(profit) as avg_profit
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
        GROUP BY m5_signal
        ORDER BY net_profit ASC
    """)
    for row in cur.fetchall():
        total = row['total']
        wins = row['wins'] or 0
        wr = (wins / total * 100) if total > 0 else 0
        net = row['net_profit'] or 0
        bar = "🟢" if net >= 0 else "🔴"
        print(f"  {bar} Signal: {str(row['m5_signal']):20s} | Total: {total:4d} | Win: {wins:4d} ({wr:5.1f}%) | Net: ${net:+.2f} | Avg: ${row['avg_profit'] or 0:.2f}")

    # ========== 9. วิเคราะห์ SMC Zone ==========
    print("\n" + "=" * 70)
    print("📊 9. ผลลัพธ์แยกตาม SMC Zone")
    print("=" * 70)
    cur.execute("""
        SELECT 
            smc_zone,
            direction,
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(profit) as net_profit
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
        GROUP BY smc_zone, direction
        ORDER BY net_profit ASC
    """)
    for row in cur.fetchall():
        total = row['total']
        wins = row['wins'] or 0
        wr = (wins / total * 100) if total > 0 else 0
        net = row['net_profit'] or 0
        bar = "🟢" if net >= 0 else "🔴"
        print(f"  {bar} {str(row['smc_zone']):15s} + {row['direction']:4s} | Trades: {total:4d} | WinRate: {wr:5.1f}% | Net: ${net:+.2f}")

    # ========== 10. วิเคราะห์ Day of Week ==========
    print("\n" + "=" * 70)
    print("📊 10. ผลลัพธ์แยกตามวัน")
    print("=" * 70)
    day_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    cur.execute("""
        SELECT 
            day_of_week,
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(profit) as net_profit
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
        GROUP BY day_of_week
        ORDER BY day_of_week
    """)
    for row in cur.fetchall():
        total = row['total']
        wins = row['wins'] or 0
        wr = (wins / total * 100) if total > 0 else 0
        net = row['net_profit'] or 0
        day = day_map.get(row['day_of_week'], f"Day{row['day_of_week']}")
        bar = "🟢" if net >= 0 else "🔴"
        print(f"  {bar} {day:3s} | Trades: {total:4d} | WinRate: {wr:5.1f}% | Net: ${net:+.2f}")

    # ========== 11. Grid SL Analysis ==========
    print("\n" + "=" * 70)
    print("📊 11. วิเคราะห์สัดส่วน Grid TP vs SL")
    print("=" * 70)
    cur.execute("""
        SELECT 
            result,
            COUNT(*) as cnt,
            SUM(profit) as total_profit,
            AVG(profit) as avg_profit
        FROM trades 
        WHERE symbol LIKE '%XAUUSD%' 
          AND m5_signal LIKE '%GRID%' 
          AND result != 'PENDING'
        GROUP BY result
    """)
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"  {row['result']:6s} | Count: {row['cnt']:4d} | Total: ${row['total_profit'] or 0:.2f} | Avg: ${row['avg_profit'] or 0:.2f}")
    else:
        # ลองหาด้วย candle_pattern ที่มี GRID
        cur.execute("""
            SELECT 
                result,
                COUNT(*) as cnt,
                SUM(profit) as total_profit,
                AVG(profit) as avg_profit
            FROM trades 
            WHERE symbol LIKE '%XAUUSD%' 
              AND result != 'PENDING'
              AND (candle_pattern LIKE '%GRID%' OR m5_signal LIKE '%grid%')
            GROUP BY result
        """)
        rows = cur.fetchall()
        if rows:
            for row in rows:
                print(f"  {row['result']:6s} | Count: {row['cnt']:4d} | Total: ${row['total_profit'] or 0:.2f} | Avg: ${row['avg_profit'] or 0:.2f}")
        else:
            print("  (ไม่พบข้อมูลที่ tag ว่าเป็น Grid ใน m5_signal หรือ candle_pattern)")

    # ========== 12. ดูเฉพาะ profit ที่เป็น -3 ลงไป ==========
    print("\n" + "=" * 70)
    print("📊 12. จำนวนออเดอร์ที่ขาดทุนหนัก (profit <= -2)")
    print("=" * 70)
    cur.execute("""
        SELECT 
            COUNT(*) as cnt,
            SUM(profit) as total_loss
        FROM trades 
        WHERE symbol LIKE '%XAUUSD%' AND result = 'LOSS' AND profit <= -2
    """)
    row = cur.fetchone()
    if row:
        print(f"  จำนวน: {row['cnt']} ออเดอร์ | ขาดทุนรวม: ${row['total_loss'] or 0:.2f}")

    cur.execute("""
        SELECT 
            COUNT(*) as cnt,
            SUM(profit) as total_loss
        FROM trades 
        WHERE symbol LIKE '%XAUUSD%' AND result = 'LOSS' AND profit <= -3
    """)
    row = cur.fetchone()
    if row:
        print(f"  จำนวน (>=$3): {row['cnt']} ออเดอร์ | ขาดทุนรวม: ${row['total_loss'] or 0:.2f}")

    # ========== 13. วิเคราะห์ win/loss แยก profit ranges ==========
    print("\n" + "=" * 70)
    print("📊 13. การกระจายผลลัพธ์ (Profit Distribution)")
    print("=" * 70)
    cur.execute("""
        SELECT 
            CASE 
                WHEN profit <= -5 THEN '[-5 ลงไป]'
                WHEN profit BETWEEN -5 AND -3 THEN '[-5 to -3]'
                WHEN profit BETWEEN -3 AND -2 THEN '[-3 to -2]'
                WHEN profit BETWEEN -2 AND -1 THEN '[-2 to -1]'
                WHEN profit BETWEEN -1 AND 0 THEN '[-1 to  0]'
                WHEN profit BETWEEN 0 AND 1 THEN '[ 0 to  1]'
                WHEN profit BETWEEN 1 AND 2 THEN '[ 1 to  2]'
                WHEN profit BETWEEN 2 AND 3 THEN '[ 2 to  3]'
                WHEN profit > 3 THEN '[ 3 ขึ้นไป]'
            END as profit_range,
            COUNT(*) as cnt,
            SUM(profit) as total
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
        GROUP BY profit_range
        ORDER BY MIN(profit) ASC
    """)
    for row in cur.fetchall():
        bar = "🟢" if (row['total'] or 0) >= 0 else "🔴"
        print(f"  {bar} {str(row['profit_range']):14s} | Count: {row['cnt']:4d} | Total: ${row['total'] or 0:+.2f}")

    # ========== 14. ดู Volatility ที่ทำให้ LOSS ==========
    print("\n" + "=" * 70)
    print("📊 14. Avg Volatility เมื่อ WIN vs LOSS")
    print("=" * 70)
    cur.execute("""
        SELECT 
            result,
            AVG(volatility) as avg_vol,
            AVG(rsi_m5) as avg_rsi,
            AVG(ABS(macd_diff)) as avg_macd
        FROM trades WHERE symbol LIKE '%XAUUSD%' AND result != 'PENDING'
        GROUP BY result
    """)
    for row in cur.fetchall():
        print(f"  {row['result']:6s} | Avg Vol: {row['avg_vol'] or 0:.3f} | Avg RSI: {row['avg_rsi'] or 0:.1f} | Avg |MACD|: {row['avg_macd'] or 0:.4f}")

    conn.close()
    print("\n" + "=" * 70)
    print("✅ Analysis Complete!")
    print("=" * 70)

if __name__ == "__main__":
    analyze()
