# 🤖 SelfLearningEA v6.1: Hybrid AI Edition (XAUUSD Focus)

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Trading](https://img.shields.io/badge/Strategy-ICT%20Consolidation-orange.svg)](#)
[![AI](https://img.shields.io/badge/AI-Gemini%20%2B%20Ollama-green.svg)](#)

ระบบเทรดอัตโนมัติ (EA) ขั้นสูงสำหรับ MetaTrader 5 ที่ผสานพลังของ **Institutional Trading (ICT)** และ **Generative AI** เพื่อความแม่นยำและความทนทานสูงสุดในการเทรดทองคำ (XAUUSD)

---

## 🌟 ฟีเจอร์หลัก (Key Features)

- **Dual AI Engine:** ระบบ Hybrid สลับการใช้งานระหว่าง **Google Gemini 2.0 Flash** (คลาวด์) และ **Ollama/Llama 3.1** (เครื่องผู้ใช้) อัตโนมัติ เพื่อแก้ปัญหา API โควตาเต็ม
- **ICT 7-Step Strategy:** กลยุทธ์การเทรดตามรอยรายใหญ่ เน้นโซน Consolidation, Liquidity Sweep และ Optimal Trade Entry (OTE)
- **Advanced Risk Management:**
    - **Safety Brake (Recovery Mode):** หยุดเทรดอัตโนมัติเมื่อ Drawdown ถึงเกณฑ์ที่กำหนด
    - **Virtual Stop Loss:** ระบบซ่อนจุดตัดขาดทุนจากโบรกเกอร์ ป้องกันการโดนล่า SL
    - **News Filter:** กรองข่าวสำคัญระดับ High Impact (USD) อัตโนมัติจาก ForexFactory
- **Multi-Target Extraction:** ระบบแบ่งปิดกำไร 3 ระดับ (Partial Close) เพื่อล็อกกำไรต้นเทรนและรันเทรนยาว
- **Local Database Analytics:** เก็บประวัติการเทรดและปัจจัยการเข้าออเดอร์ทั้งหมดลง `SQLite` เพื่อนำมาวิเคราะห์ย้อนหลัง

---

## 🛠️ โครงสร้างไฟล์ในโปรเจกต์

- `trader.py`: ไฟล์หลักสำหรับการรันบอทเทรด
- `config.py`: การตั้งค่าพารามิเตอร์, ความเสี่ยง และ API
- `README.py`: **[แนะนำ]** หน้าจอ Dashboard สำหรับจัดการระบบ ตรวจสอบความพร้อม และสั่งรันบอท
- `analyze_trades.py`: สคริปต์วิเคราะห์สถิติการเทรดจากฐานข้อมูล
- `database.py`: ระบบจัดการฐานข้อมูล SQLite
- `README_MANUAL.md`: คู่มือการใช้งานฉบับเต็มภาษาไทย

---

## 🚀 การติดตั้งและเริ่มต้นใช้งาน

### 1. ติดตั้ง Library ที่จำเป็น
```bash
pip install -r requirements.txt
```

### 2. ตั้งค่าสภาพแวดล้อม
- คัดลอกไฟล์ `.env.example` เป็น `.env`
- ใส่ค่า `MT5_LOGIN`, `MT5_PASSWORD`, `GEMINI_API_KEY` และ `TELEGRAM_BOT_TOKEN`

### 3. รันระบบ Command Center (แนะนำ)
เพื่อให้ง่ายต่อการจัดการ แนะนำให้รันผ่าน `README.py`:
```bash
python README.py
```

---

## 📊 ระบบความปลอดภัย (Resilience)
เวอร์ชัน 6.1 ถูกออกแบบมาให้ทนทานต่อสภาวะตลาดที่ผันผวน:
- **Ollama Fallback:** บอททำงานต่อได้แม้ไม่มีอินเทอร์เน็ตหรือ Gemini Cloud มีปัญหา
- **Portfolio Exposure Limit:** จำกัดความเสี่ยงรวมของพอร์ตไม่ให้เกินค่าที่ตั้งไว้
- **Daily Loss Limit:** ตัดวงจรการเทรดทันทีที่เสียเกินโควตาต่อวัน

---

## ⚖️ คำเตือนความเสี่ยง (Disclaimer)
การเทรด Forex และทองคำมีความเสี่ยงสูง ผู้ใช้งานควรทำความเข้าใจกลยุทธ์และทดสอบในบัญชี Demo ก่อนใช้งานจริง Antigravity Systems และผู้พัฒนาไม่รับผิดชอบต่อความเสียหายทางการเงินใดๆ ที่เกิดขึ้น

---
*Antigravity AI Trading Systems - Precision - Resilience - Growth*
