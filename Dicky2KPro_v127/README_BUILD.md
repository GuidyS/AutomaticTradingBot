# Dicky2K Pro v1.2.7 - Deployment Guide

## Prerequisites
1. **Python 3.10+**
2. **MetaTrader 5** (Terminal must be open and logged in)
3. **Libraries**: Run `pip install -r requirements.txt`
4. **MT5 Settings**:
   - Go to `Tools > Options > Expert Advisors`
   - Enable `Allow DLL imports`
   - Enable `Allow WebRequest`

## AI Setup
- **Ollama**: Install from [ollama.com](https://ollama.com). Default endpoint: `http://localhost:11434/api/generate`
- **LM Studio**: Set up a Local Server in LM Studio. Default endpoint: `http://localhost:1234`

## How to Build (.exe)
Use PyInstaller or Nuitka:

### Option 1: PyInstaller (Quick)
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --add-data "config.json;." main.py --name Dicky2KPro_v127
```

### Option 2: Nuitka (Better performance & protection)
```bash
pip install nuitka
python -m nuitka --standalone --onefile --enable-plugin=pyqt6 --windows-disable-console main.py -o Dicky2KPro_v127.exe
```

## Folder Structure
- `main.py`: Entry point
- `config_manager.py`: Configuration
- `logger.py`: DB & File Logging
- `mt5_connector.py`: MT5 Communication
- `ai_engine.py`: AI Logic & Health Check
- `trading_logic.py`: Scalping Strategy
- `ui_main.py`: Dashboard UI
- `config.json`: User Settings
