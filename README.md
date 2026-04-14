# SMC AI Trading Bot v4 — Anti-Loss Edition 🚀

ระบบเทรดอัตโนมัติ (EA) บน Python ที่ผสานกลยุทธ์ **Smart Money Concepts (SMC)** เข้ากับ **AI Analysis** ออกแบบมาเพื่อความแม่นยำสูงและการจัดการความเสี่ยงที่เข้มงวด (Anti-Loss) สำหรับเทรด XAUUSDc และ BTCUSDc บนแพลตฟอร์ม MetaTrader 5

---

## 🌟 ฟีเจอร์หลัก (Key Modules)

### 🛡️ 1. Anti-Loss Systems
*   **[H] Auto-Hedge:** ระบบเปิดไม้ตรงข้ามทันทีเมื่อราคาวิ่งสวนทางถึงจุด Trigger เพื่อล็อกความเสี่ยง และปิดทั้งตะกร้าเมื่อกำไรรวมเป็นบวก
*   **[S] Structural SL/TP:** การวางจุดตัดขาดทุนตามโครงสร้างราคาจริง (Swing High/Low) และจุดทำกำไรตาม Order Block หรือ ATR
*   **[R] Recovery Mode:** ระบบกู้พอร์ตอัตโนมัติเมื่อ Drawdown ถึงระดับที่กำหนด และระบบ **Loss Shaving** (เฉือนปิดไม้เสียด้วยไม้กำไร)
*   **[M] Smart Martingale:** การเพิ่ม Lot อย่างเป็นระบบเมื่อแพ้ โดยต้องผ่านเกณฑ์ Entry Filter เท่านั้น

### 🎯 2. Entry Filter v2 (5-Layer Gate)
บอทจะเปิดออเดอร์เมื่อผ่านเงื่อนไขทั้ง 5 ชั้น:
1.  **H4 Mega-Trend:** เทรดตามแนวโน้มใหญ่ระดับ 4 ชั่วโมง
2.  **Volume & Volatility:** เช็คแรงซื้อขาย (Relative Volume) และความผันผวน
3.  **RSI/MACD Window:** กรองสัญญาณ Overbought/Oversold และ Momentum
4.  **MTF Alignment:** เทรนด์ M30 และ H1 ต้องสอดคล้องกับสัญญาณเข้า
5.  **SMC Zone:** เข้าเทรดในโซน Discount/Premium เท่านั้น เพื่อให้ได้เปรียบด้านราคา

### 🤖 3. AI Analysis Integration
*   เชื่อมต่อกับ **Ollama (Gemma)** เพื่อวิเคราะห์สภาพตลาดแบบ Real-time
*   ระบบ **AI Bias Multiplier:** ปรับ Take Profit ตามความมั่นใจของ AI (Aggressive / Conservative)
*   ส่ง AI Insights และสรุปผลงานผ่าน **Telegram**

---

## 🛠️ การติดตั้งและใช้งาน (Setup & Usage)

### 1. ความต้องการของระบบ (Requirements)
*   Python 3.10+
*   MetaTrader 5 Terminal (Login เรียบร้อย)
*   Ollama (สำหรับระบบ AI)

### 2. ติดตั้ง Library
```bash
pip install pandas MetaTrader5 requests python-dotenv
```

### 3. การตั้งค่า (Configuration)
แก้ไขไฟล์ `config.py`:
*   ใส่ `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
*   ตั้งค่า `TELEGRAM_BOT_TOKEN` และ `TELEGRAM_CHAT_ID`
*   ปรับระดับความเสี่ยงที่ `RISK_PERCENT` และ `MAX_LOT`

### 4. เริ่มต้นการทำงาน
```bash
python trader.py
```

---

## 📁 โครงสร้างไฟล์
*   `trader.py`: ไฟล์หลักควบคุมการทำงาน (Logic v4)
*   `config.py`: ศูนย์รวมการตั้งค่าทั้งหมด
*   `database.py`: จัดการฐานข้อมูลและสถิติการเทรด
*   `README.md`: คู่มือการใช้งาน

---

## ⚠️ คำเตือนความเสี่ยง (Disclaimer)
การเทรด CFD และ Forex มีความเสี่ยงสูง ผู้ใช้ควรทดสอบในบัญชี Demo ก่อนใช้งานจริง และควรเข้าใจกลยุทธ์ SMC ที่บอทใช้งานเพื่อการปรับจูนที่เหมาะสม

---
**Version 4 - Refactored for High Precision & Safety**
