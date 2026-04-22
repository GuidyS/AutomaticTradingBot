import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
models = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-flash-latest"]

print("--- Multi-Model Resilience Test ---")

for model in models:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": "Reply with 'OK' and your model name if you receive this."}]}]
    }
    
    print(f"Testing model: {model}...")
    try:
        r = requests.post(url, json=payload, timeout=20)
        print(f"  Status Code: {r.status_code}")
        if r.status_code == 200:
            resp = r.json()
            text = resp['candidates'][0]['content']['parts'][0]['text']
            print(f"  AI SUCCESS: {text.strip()}")
            print(f"  [RESULT] Model {model} is READY to use.")
            # We found a working one! But let's check others too.
        elif r.status_code == 429:
            print(f"  [RESULT] Model {model} is RATE LIMITED (429).")
        else:
            print(f"  [RESULT] Model {model} returned ERROR: {r.status_code}")
    except Exception as e:
        print(f"  [RESULT] Model {model} exception: {str(e)}")
    
    print("-" * 30)
    time.sleep(1) # Small delay between tests

print("Test Completed.")
