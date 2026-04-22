import time
import sys
import os

# Add current dir to path
sys.path.append(os.getcwd())

# Mocking
class MockConfig:
    AI_API_KEY = "test_key"
    AI_MODEL = "gemini-2.5-flash"

sys.modules['config'] = MockConfig()

import trader

def test_cooldown():
    ea = trader.SelfLearningEA()
    
    # 1. Initial state: not cooldown
    is_c, w = ea.check_ai_cooldown()
    assert is_c == False
    
    # 2. Set cooldown
    ea.ai_global_cooldown_until = time.time() + 100
    is_c, w = ea.check_ai_cooldown()
    assert is_c == True
    assert 90 <= w <= 101
    
    print("Cooldown logic test PASSED")

if __name__ == "__main__":
    test_cooldown()
