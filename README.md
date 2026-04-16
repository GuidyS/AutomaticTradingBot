# 🤖 AI-Powered SMC/ICT Scalp Bot (v5.0)

![Trading Bot](https://img.shields.io/badge/Strategy-SMC%20%2F%20ICT-gold)
![AI](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-blue)
![Mode](https://img.shields.io/badge/Mode-Scalp%20Only-red)
![Platform](https://img.shields.io/badge/Platform-MT5%20%2F%20Python-green)

ระบบเทรดอัตโนมัติอัจฉริยะที่ออกแบบมาเพื่อ **XAUUSD (Gold)** และคู่เงินหลัก โดยใช้กลยุทธ์สถาบัน (SMC/ICT) ผสานกับพลังการตัดสินใจของ **Gemini 2.5 AI** เพื่อความแม่นยำสูงสุดในตลาดปี 2026

## 🌟 ฟีเจอร์เด่น (v5.0)

### 📊 กลยุทธ์การเทรดขั้นสูง
*   **Pure SMC/ICT Scalping**: เน้นการเข้าเทรดในช่วงราคาพักตัว (Consolidation) และการกวาดสภาพคล่อง (Liquidity Sweeps)
*   **Optimal Trade Entry (OTE)**: ระบบคำนวณจุดเข้าที่ได้เปรียบที่สุดอัตโนมัติ
*   **Gemini 2.5 AI Brain**: ใช้ AI ในการวิเคราะห์โครงสร้างตลาดและคัดกรองสัญญาณหลอก (False Breaks)
*   **TP-Bias Dynamic**: AI จะกำหนดระดับความมั่นใจ และปรับเป้าหมายกำไร (Multiplier) ตามสภาวะตลาดจริง

### 🛡️ ระบบบริหารความเสี่ยง (Risk Management)
*   **Multi-TP RR Levels**: ตั้งเป้ากำไร 3 ระดับที่ค่า **Risk:Reward [1.0, 1.5, 2.5]** เพื่อรักษากำไรสุทธิให้เป็นบวกเสมอ
*   **Virtual Stop Loss**: ซ่อนจุดตัดขาดทุนจากโบรกเกอร์ (Stop-Hunt Protection)
*   **Equity-Based Sizing**: คำนวณ Lot อัตโนมัติ (Balance / 10,000) พร้อมบังคับ **Min Lot 0.02**
*   **Global Recovery Mode**: หยุดการเทรดปกติและเข้าสู่โหมดกู้พอร์ตทันทีเมื่อ Drawdown ถึงระดับที่กำหนด

## ⚙️ การตั้งค่าที่สำคัญ

ในไฟล์ `config.py`:
- `AI_MODEL`: รุ่น AI ที่ใช้งาน (แนะนำ: `gemini-2.5-flash`)
- `AI_CONFIDENCE_THRESHOLD`: ระดับความเชื่อมั่นขั้นต่ำ (70%)
- `LOT_DIVISOR`: ตัวหารขนาด Lot (10,000)
- `MIN_LOT`: ขนาด Lot เริ่มต้น (0.02)

## 🚀 เริ่มต้นใช้งาน

1.  **ติดตั้ง Dependency**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **ตั้งค่าบัญชี**: กรอกข้อมูลใน `.env` (API Key) และ `config.py` (MT5 Login)
3.  **เริ่มระบบทำงาน**:
    ```bash
    python trader.py
    ```

## 📂 โครงสร้างโปรเจกต์
- `trader.py`: ระบบการจัดการออเดอร์และการคำนวณกลยุทธ์หลัก
- `config.py`: ศูนย์กลางการตั้งค่าและโปรไฟล์ Risk/Reward
- `database.py`: ระบบจัดเก็บสถิติและประวัติการเทรด (SQLite)
- `analyze_trades.py`: เครื่องมือวิเคราะห์ประสิทธิภาพและสรุปผลกำไร

---

> [!CAUTION]
> การเทรดมีความเสี่ยงสูง ระบบนี้ถูกออกแบบมาเพื่อช่วยสนับสนุนการตัดสินใจและทำงานอัตโนมัติตามกลยุทธ์ โปรดทดสอบในบัญชี Demo ก่อนใช้งานจริงเสมอ

**Antigravity Trading System — Precision in Every Trade**
