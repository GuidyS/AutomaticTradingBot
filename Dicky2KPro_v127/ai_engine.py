import requests
import json
import time

class AIEngine:
    def __init__(self, logger, config_manager):
        self.logger = logger
        self.config = config_manager

    def test_ai_connection(self):
        provider = self.config.get("ai_provider")
        endpoint = self.config.get("ai_local_endpoint")
        model = self.config.get("ai_model")
        
        start_time = time.time()
        try:
            if provider == "Ollama":
                payload = {
                    "model": model,
                    "prompt": "Respond with OK if you receive this.",
                    "stream": False
                }
                response = requests.post(endpoint, json=payload, timeout=180)
                if response.status_code == 200:
                    resp_json = response.json()
                    response_time = time.time() - start_time
                    return True, f"Connected! Response Time: {response_time:.2f}s", resp_json.get("response", "")
            
            elif provider == "LM Studio":
                # Assuming OpenAI-compatible endpoint
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Respond with OK"}],
                    "temperature": 0.1
                }
                response = requests.post(f"{endpoint}/v1/chat/completions", json=payload, timeout=60)
                if response.status_code == 200:
                    resp_json = response.json()
                    response_time = time.time() - start_time
                    return True, f"Connected! Response Time: {response_time:.2f}s", resp_json["choices"][0]["message"]["content"]

            return False, "Provider not supported or connection failed", ""
        except Exception as e:
            return False, f"Error: {str(e)}", ""

    def get_local_models(self):
        provider = self.config.get("ai_provider")
        endpoint = self.config.get("ai_local_endpoint")
        
        if provider != "Ollama":
            return []
            
        try:
            # Ollama tags API to list models
            tags_url = endpoint.replace("/api/generate", "/api/tags")
            response = requests.get(tags_url, timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [m["name"] for m in models]
        except:
            pass
        return []

    def get_signal(self, market_data):
        """
        market_data: dict containing prices, indicators, etc.
        """
        provider = self.config.get("ai_provider")
        endpoint = self.config.get("ai_local_endpoint")
        model = self.config.get("ai_model")
        
        prompt = f"""
        Analysis Task: Scalping M1/M5
        Symbol: {market_data.get('symbol')}
        Price: {market_data.get('price')}
        Indicators: {json.dumps(market_data.get('indicators'))}
        
        Provide a recommendation: BUY, SELL, or HOLD.
        Format your response as JSON: {{"signal": "BUY", "confidence": 85, "reason": "Short explanation"}}
        """
        
        try:
            if provider == "Ollama":
                payload = {"model": model, "prompt": prompt, "stream": False, "format": "json"}
                response = requests.post(endpoint, json=payload, timeout=180)
                if response.status_code == 200:
                    result = response.json().get("response", "")
                    return self._parse_json_signal(result)
            
            # Add other providers here...
            
        except Exception as e:
            self.logger.error(f"AI Signal Error: {e}")
        
        return {"signal": "HOLD", "confidence": 0, "reason": "AI Error or Timeout"}

    def _parse_json_signal(self, text):
        try:
            # Clean text if AI adds fluff
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(text[start:end])
        except:
            pass
        return {"signal": "HOLD", "confidence": 0, "reason": "Failed to parse AI response"}
