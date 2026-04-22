import requests
import json
import time

url = "http://localhost:11434/api/generate"
model = "llama3.1:latest"
prompt = "Hello! Please respond with 'OLLAMA_SUCCESS'."

print(f"Testing local Ollama integration with model: {model}...")
payload = {
    "model": model,
    "prompt": prompt,
    "stream": False
}

try:
    start_time = time.time()
    r = requests.post(url, json=payload, timeout=60)
    elapsed = time.time() - start_time
    print(f"HTTP Status: {r.status_code} (took {elapsed:.1f}s)")
    if r.status_code == 200:
        resp = r.json().get('response', '')
        print(f"AI Response: {resp.strip()}")
        print("RESULT: Ollama integration is WORKING.")
    else:
        print(f"RESULT: Ollama returned error: {r.text}")
except Exception as e:
    print(f"RESULT: Error connecting to Ollama: {e}")
