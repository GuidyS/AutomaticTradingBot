# 🤖 AI-Powered SMC/ICT Hybrid Scalp Bot (v6.1)

![Trading Bot](https://img.shields.io/badge/Strategy-SMC%20%2F%20ICT-gold)
![AI](https://img.shields.io/badge/AI-Hybrid%20(Gemini%20%2B%20Ollama)-blue)
![Mode](https://img.shields.io/badge/Mode-Scalp%20Only-red)
![Series](https://img.shields.io/badge/Series-2026%20Edition-green)

ระบบเทรดอัตโนมัติอัจฉริยะที่ออกแบบมาเพื่อ **XAUUSD (Gold)** โดยเฉพาะ ผสานกลยุทธ์สถาบัน (SMC/ICT) เข้ากับพลังการตัดสินใจของเทคโนโลยี **Hybrid AI** (Cloud + Local) เพื่อความแม่นยำและความทนทานสูงสุดต่อข้อจำกัดของ API ในปี 2026

## 🌟 ฟีเจอร์เด่น (v6.1 Hybrid Edition)

### 🧠 ระบบ Hybrid AI อันทรงพลัง
*   **Dual-Brain Architecture**: ใช้ **Gemini 2.0/2.5 Flash** เป็นหลัก และสลับไปใช้ **Ollama (Llama 3.1)** ในเครื่องคุณทันทีหาก API ของ Google ติด Rate Limit (429)
*   **Zero-Downtime Analysis**: ไม่พลาดทุกจังหวะสำคัญด้วยระบบสลับ AI อัตโนมัติ ทำให้บอทยังวิเคราะห์ตลาดได้แม้ไม่มีอินเทอร์เน็ตหรือ API ค้าง
*   **Smart Fallback 5.0**: ระบบจำศีลและสลับรุ่น AI อัจฉริยะ พร้อมการเชื่อมต่อผ่าน Stable Endpoint (`v1`)

### 📊 กลยุทธ์การเทรดขั้นสูง
*   **7-Step ICT Consolidation**: เข้าเทรดในช่วงราคาพักตัวและการกวาดสภาพคล่อง (Liquidity Sweeps)
*   **Optimal Trade Entry (OTE)**: ระบบคำนวณจุดเข้าที่ระดับ Fibonacci 62% - 79% อัตโนมัติ
*   **Bias-Based Scalping**: AI จะกำหนดทิศทาง (Bias) และระดับความเชื่อมั่น (Confidence) เพื่อคัดกรองสัญญาณหลอก

### 🛡️ ความปลอดภัยและบริหารความเสี่ยง
*   **Safety Brake Recovery**: ระบบกู้พอร์ตอัจฉริยะที่จะ "หยุดออกไม้เพิ่ม" เมื่อ Drawdown สูง แต่จะไม่ปิดไม้ของคุณ เพื่อให้คุณตัดสินใจได้เอง (Non-Closing Mode)
*   **Virtual Stop Loss**: ซ่อนจุดตัดขาดทุนจากโบรกเกอร์ ป้องกันการโดนล่า SL (Stop-Hunt Protection)
*   **Multi-TP RR Levels**: ตั้งเป้ากำไร 3 ระดับ พร้อมระบบ Multiplier ตามระดับความมั่นใจของ AI

## 🚀 เริ่มต้นใช้งานแบบด่วน

1.  **ติดตั้งขุมพลัง**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **ตั้งค่า**: 
    - ใส่ API Key ใน `.env`
    - (แนะนำ) ติดตั้ง **Ollama** และโหลด `llama3.1` เพื่อใช้เป็นระบบ AI สำรอง
3.  **รันระบบ**:
    ```bash
    python trader.py
    ```

## 📂 โครงสร้างโปรเจกต์
- `trader.py`: หัวใจหลักของระบบ จัดการกลยุทธ์และการเชื่อมต่อ AI
- `config.py`: ศูนย์กลางการตั้งค่า Risk, AI Model และโปรไฟล์คู่เงิน
- `database.py`: ระบบจัดเก็บสถิติและประวัติการเทรด (SQLite)
- `analyze_trades.py`: เครื่องมือสรุปผลกำไรและวิเคราะห์ประสิทธิภาพเชิงลึก

---

> [!IMPORTANT]
> **EA v6.1** ถูกออกแบบมาเพื่อความยืดหยุ่นสูงสุด การเปิดใช้งาน **Ollama** ควบคู่ไปด้วยจะช่วยให้บอทของคุณทำงานได้ราบรื่น 24/7 แม้ติดปัญหาเรื่อง API Quota

**Antigravity Trading System — The Future of Algorithmic Trading (2026)**
