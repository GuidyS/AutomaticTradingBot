# 🤖 AI-Powered ICT/SMC Trading Bot (v4.5)

![Trading Bot](https://img.shields.io/badge/Strategy-ICT%20%2F%20SMC-gold)
![AI](https://img.shields.io/badge/AI-Gemini%202.5-blue)
![Platform](https://img.shields.io/badge/Platform-MT5%20%2F%20Python-green)

ระบบเทรดอัตโนมัติระดับมืออาชีพที่ผสานกลยุทธ์ **Inner Circle Trader (ICT)** เข้ากับพลังของ **Gemini AI** เพื่อการวิเคราะห์ตลาดและเข้าเทรดในจุดที่มีความได้เปรียบสูง ทั้งในตลาด Forex และ Gold (XAUUSD)

## 🌟 ฟีเจอร์หลัก

### 🏛️ กลยุทธ์สถาบัน (Institutional Strategies)
*   **7-Step ICT Consolidation**: ตรวจจับช่วงราคาพักตัว (Sideways), ระบุจุดกวาดสภาพคล่อง (Liquidity Sweep/Turtle Soup), และเข้าเทรดเมื่อราคากลับเข้าสู่กรอบ (Confirmed Re-entry)
*   **Optimal Trade Entry (OTE)**: ระบุจุดย่อตัวที่คุ้มค่าที่สุดอัตโนมัติที่ระดับ Fibonacci **0.62, 0.705, และ 0.79**
*   **Standard Deviation Projections**: ใช้การขยายของราคา (Expansion) ที่ระดับ **SD 2.0 และ 2.5** เพื่อกำหนดเป้าหมายกำไรตามรอยรายใหญ่

### 🧠 การวิเคราะห์ด้วย Gemini AI 
*   **Dual-Playbook Mode**: AI จะสลับโหมดการทำงานระหว่างช่วงตลาดพักตัว (Consolidation) และตลาดมีเทรนด์ (OTE) โดยอัตโนมัติ
*   **Confluence Filtering**: AI จะตรวจสอบปัจจัยร่วม ทั้ง **FVG (Fair Value Gaps)**, **Order Blocks (OB)**, และแนวโน้มหลายไทม์เฟรม (H1/M15) ก่อนส่งคำสั่ง

### 🛡️ การบริหารความเสี่ยงอย่างเป็นระบบ
*   **Equity Divisor Sizing**: คำนวณขนาด Lot ตามสูตร **`Capital / 10,000`** เพื่อความปลอดภัยของพอร์ต
*   **Multi-TP Scaling**: แบ่งปิดกำไร 3 ระยะ เพื่อล็อคกำไรเข้าพอร์ตและลดความเสี่ยง
*   **Virtual SL Cache**: ซ่อนจุดตัดขาดทุนจากโบรกเกอร์เพื่อป้องกันการถูกลากกิน SL (Stop-hunting)
*   **Global Recovery Mode**: ระบบป้องกันพอร์ตอัตโนมัติเมื่อเกิด Drawdown ถึง -10%

## 🚀 เริ่มต้นใช้งาน

1.  **ติดตั้ง Library ที่จำเป็น**:
    ```bash
    pip install MetaTrader5 pandas requests pytz
    ```
2.  **ตั้งค่าระบบ**: อัปเดตไฟล์ `config.py` ด้วยข้อมูลบัญชี MT5 และ Gemini API Key ของคุณ
3.  **รันระบบ**:
    ```bash
    python trader.py
    ```

---

## 📂 โครงสร้างไฟล์
*   `trader.py`: หัวใจหลักของระบบและการทำงานของบอท
*   `config.py`: ศูนย์รวมการตั้งค่าและโปรไฟล์ของแต่ละสัญลักษณ์
*   `database.py`: ระบบบันทึกประวัติการเทรดและตรวจสอบผลงาน
*   `ConsolidationICT.mq5`: เวอร์ชั่น MQL5 สำหรับรันบน MetaTrader 5 โดยตรง
*   `consolidation_ict_strategy.pine`: เวอร์ชั่น PineScript สำหรับใช้งานบน TradingView

> [!IMPORTANT]
> บอทถูกออกแบบมาเพื่อทำงานอัตโนมัติบน **XAUUSDc** และคู่เงินหลัก โปรดตรวจสอบให้แน่ใจว่าบัญชี MT5 ของคุณมี Margin เพียงพอและเพิ่มสัญลักษณ์ที่ต้องการเทรดใน Market Watch แล้ว
