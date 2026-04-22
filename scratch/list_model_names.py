import requests
import os
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv('GEMINI_API_KEY', '')
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
try:
    r = requests.get(url)
    data = r.json()
    if 'models' in data:
        print("Available Models:")
        for m in data['models']:
            print(f"- {m['name']}")
    else:
        print(data)
except Exception as e:
    print(f"Error: {e}")
