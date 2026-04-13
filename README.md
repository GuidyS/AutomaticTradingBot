# Self-Learning Scalping EA (MT5 + Machine Learning)

โปรเจกต์นี้คือ Expert Advisor (EA) สำหรับเทรด Forex (เช่น คู่เงิน XAUUSD) ที่ทำงานร่วมกับ MetaTrader 5 และใช้ Machine Learning (Ensemble: CatBoost + Random Forest) เพื่อเรียนรู้ข้อผิดพลาด และช่วยตัดสินใจเมื่อเกิดสัญญาณเข้าเทรดที่ขัดแย้งกัน

## 📂 โครงสร้างไฟล์
| ไฟล์ | คำอธิบาย |
|------|----------|
| `config.py` | ตั้งค่าพอร์ต, คู่เงิน, ความเสี่ยง (Lot/Risk), SL/TP และเชื่อมต่อฐานข้อมูล |
| `database.py` | จัดการเชื่อมต่อ MySQL และสร้างตารางเก็บข้อมูล (`trades`) |
| `trader.py` | สคริปต์บอทหลัก (Main EA) เฝ้ากราฟ M30/M5 และเปิดออเดอร์ |
| `trainer.py` | สคริปต์สอน AI โหลดข้อมูลจากฐานข้อมูลเพื่อเทรนโมเดล `.pkl` ทุกๆ 30 นาที |
| `backtest.py` | สคริปต์ Backtest กลยุทธ์ SMC+ICT |
| `requirements.txt` | Libraries ที่จำเป็น |
| `.env` | **ไฟล์ลับ** เก็บ Credentials (MT5, DB, LINE) - **ห้ามแชร์** |
| `.env.example` | Template สำหรับสร้าง `.env` |

---

## 🔒 ความปลอดภัย (สำคัญมาก)

> **⚠️ คำเตือน:** ไฟล์ `.env` มีข้อมูลลับเช่น รหัสผ่าน MT5 และ Database **ห้ามแชร์ให้ใคร** และ **ห้าม commit ขึ้น Git**

### การตั้งค่า Credentials
1. คัดลอกไฟล์ `.env.example` เป็น `.env`:
   ```bash
   copy .env.example .env
   ```
2. แก้ไขไฟล์ `.env` ให้ตรงกับการตั้งค่าของคุณ:
   ```env
   MT5_LOGIN=your_account_number
   MT5_PASSWORD=your_password
   MT5_SERVER=Exness-MT5Trial14
   
   DB_HOST=localhost
   DB_USER=root
   DB_PASSWORD=your_password
   DB_NAME=forex_ea
   ```

---

## 🚀 ขั้นตอนการติดตั้งและการใช้งาน

### 1. การติดตั้ง Prerequisites
1. ติดตั้ง Python (แนะนำเวอร์ชัน 3.9 - 3.11 ขึ้นไป)
2. ติดตั้ง Library ตามใน `requirements.txt`:
   เปิด Command Prompt (Terminal) ในโฟลเดอร์นี้แล้วรัน:
   ```bash
   pip install -r requirements.txt
   ```
3. สมัคร/ติดตั้งโปรแกรมจำลองฐานข้อมูล เช่น **XAMPP**, **WAMP** หรือติด MySQL Server ปกติลงเครื่อง และอย่าลืมกด **Start MySQL** Service

### 2. การตั้งค่าก่อนใช้งาน (Configuration)

#### สำหรับผู้ใช้ใหม่ (v2.0+)
ระบบใช้ Environment Variables แล้ว แก้ไขไฟล์ `.env` แทนการแก้ `config.py` โดยตรง

#### ตั้งค่าระบบเทรดตามเหมาะสม:
| ตัวแปร | คำอธิบาย | ค่าแนะนำ |
|--------|----------|---------|
| `SYMBOLS` | คู่เงินที่เทรด | `"XAUUSDc"` |
| `RISK_MODE` | `"FIXED"` หรือ `"PERCENT"` | `"PERCENT"` |
| `FIXED_LOT` | Lot ฐาน (เมื่อใช้ FIXED) | `0.01` |
| `RISK_PERCENT` | % ความเสี่ยงต่อออเดอร์ | `1.0` |
| `MAX_ORDERS_PER_SYMBOL` | จำนวนออเดอร์สูงสุดต่อ Symbol | `3` |
| `ATR_SL_MULTIPLIER` | ระยะ Stop Loss (คูณ ATR) | `0.8` |
| `ATR_TP_MULTIPLIER` | ระยะ Take Profit (คูณ ATR) | `1.0` |

### 3. การเตรียมโปรแกรม MetaTrader 5 (MT5)
1. เปิดโปรแกรม MT5 เข้าสู่ระบบพอร์ตเทรดของคุณให้เรียบร้อย (ทดสอบบัญชี Demo ก่อนเสมอ)
2. ไปที่เมนูบนสุด: `Tools` > `Options` > แท็บ `Expert Advisors`
3. ติ๊กเครื่องหมายถูกที่ **[x] Allow algorithmic trading** เพื่ออนุญาตให้บอทเปิดออเดอร์

### 4. การเริ่มรันระบบปฏิบัติการ
ให้เปิด Command Prompt หรือ Terminal แยกกันเป็น **2 หน้าต่าง** และ `cd` เข้ามาที่โฟลเดอร์นี้

**💻 หน้าต่างที่ 1: บอทเทรดหลัก (Main EA Trader)**
```bash
python trader.py
```
> **หน้าที่:** บอทหลักจะทำงานคอยเฝ้ากราฟ M30 และ M5 ถ้าสัญญาณสอดคล้องกันจะเปิดออเดอร์ทันที ระบบ AI จะช่วยโหวตความน่าจะเป็นของทิศทาง

**🧠 หน้าต่างที่ 2: ระบบสอน AI เรียนรู้ (AI Trainer)**
```bash
python trainer.py
```
> **หน้าที่:** ดึงประวัติออเดอร์จากฐานข้อมูลทุกๆ 30 นาที และเทรน Machine Learning โมเดล XGBoost + CatBoost ตลอดเวลา บอทเทรดจะหยิบไฟล์นี้ไปใช้อัตโนมัติ (Hot-Swap)

> **หมายเหตุ:** ช่วงแรกที่ยังไม่มีข้อมูลออเดอร์ในฐานข้อมูล (น้อยกว่า 10 ออเดอร์) ระบบจะแจ้งเตือนว่า "ข้อมูลไม่พอเทรน" ซึ่งเป็นเรื่องปกติ

---

## 📊 สรุปการปรับปรุง (v2.0)

### 🔒 Security Improvements
- ✅ ย้าย Credentials ไปใช้ Environment Variables (`.env`)
- ✅ แก้ SQL Injection vulnerability ใน `trainer.py`
- ✅ เพิ่ม `.gitignore` ป้องกัน commit ไฟล์ลับ
- ✅ สร้าง `.env.example` template

### 🐛 Bug Fixes
- ✅ แก้ RSI logic ขัดแย้งกันเอง (BUY/SELL ช่วงซ้อนทับ)
- ✅ แก้ FVG Detection loop (IndexError risk)
- ✅ แก้ ALTER TABLE syntax error ใน `database.py`
- ✅ เพิ่ม Error Handling ครอบคลุมจุดสำคัญ

### 🛡️ Error Handling
- ✅ เพิ่ม try-catch ใน `execute_trade()`
- ✅ เพิ่ม try-catch ใน `manage_trailing_stop()`
- ✅ เพิ่ม try-catch ใน `check_and_update_db()`
- ✅ Validate SL/TP prices ก่อนส่งออเดอร์

---

## 🛠 แนวทางการนำไปต่อเติมและพัฒนา (Advanced)

ระบบนี้ถูกออกแบบให้รองรับการปรับแต่ง Logic การเทรดได้ง่าย:

### เพิ่ม Indicator ส่วนตัว
แก้ไขในไฟล์ `trader.py` บริเวณฟังก์ชัน:
- `get_m30_trend()` - สำหรับเช็คเทรนด์ภาพใหญ่
- `get_m5_market_state()` - สำหรับหาจุดเข้าออเดอร์และสัญญาณ

### ปรับกลยุทธ์ Scalping
แก้ไขเงื่อนไขใน `run()` method (บรรทัด ~706):
```python
# BUY : EMA14 > EMA50, RSI 45-65, MACD > 0
buy_signal  = ('BUY' in m5_signals) and (45 <= rsi_m5 <= 65) and (macd_diff > 0)

# SELL: EMA14 < EMA50, RSI 35-55, MACD < 0
sell_signal = ('SELL' in m5_signals) and (35 <= rsi_m5 <= 55) and (macd_diff < 0)
```

---

## 📝 License & Disclaimer

> **⚠️ การเตือนความเสี่ยง:** การเทรด Forex มีความเสี่ยงสูง คุณอาจสูญเสียเงินทุนทั้งหมด โปรดศึกษาและทดสอบระบบในบัญชี Demo ก่อนใช้งานจริง

โปรเจกต์นี้พัฒนาเพื่อการศึกษาและวิจัยเท่านั้น ผู้ใช้งานต้องรับผิดชอบผลการเทรดด้วยตนเอง
