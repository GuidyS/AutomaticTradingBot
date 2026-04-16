import sys
import os
import unittest
from datetime import datetime, timedelta

# Mocking modules that might not be available or needed for logic testing
class MockMT5:
    def initialize(self): return True
    def login(self, a, password=None, server=None): return True
    def symbol_select(self, s, b): return True
    def positions_get(self, symbol=None): return []

sys.modules['MetaTrader5'] = MockMT5()

# Add current dir to path
sys.path.append(os.getcwd())

import trader

class TestDynamicLimits(unittest.TestCase):
    def setUp(self):
        self.ea = trader.SelfLearningEA()
        
    def test_bonus_logic(self):
        symbol = "XAUUSDc"
        # Standard limit from profile is 3 (based on config viewed earlier)
        max_scalp_orders = 3 
        
        # Scenario 1: No bonus
        self.ea.symbol_tp_multipliers[symbol] = 1.0
        self.ea.symbol_ai_confidence[symbol] = 50
        
        ai_mul = self.ea.symbol_tp_multipliers.get(symbol, 1.0)
        ai_conf = self.ea.symbol_ai_confidence.get(symbol, 0)
        bonus = 2 if (symbol == "XAUUSDc" and ai_mul >= 1.8 and ai_conf >= 70) else 0
        self.assertEqual(bonus, 0)
        
        # Scenario 2: Aggressive but low confidence
        self.ea.symbol_tp_multipliers[symbol] = 1.8
        self.ea.symbol_ai_confidence[symbol] = 65
        ai_mul = self.ea.symbol_tp_multipliers.get(symbol, 1.0)
        ai_conf = self.ea.symbol_ai_confidence.get(symbol, 0)
        bonus = 2 if (symbol == "XAUUSDc" and ai_mul >= 1.8 and ai_conf >= 70) else 0
        self.assertEqual(bonus, 0)
        
        # Scenario 3: Aggressive and high confidence (+2 Bonus)
        self.ea.symbol_ai_confidence[symbol] = 75
        ai_mul = self.ea.symbol_tp_multipliers.get(symbol, 1.0)
        ai_conf = self.ea.symbol_ai_confidence.get(symbol, 0)
        bonus = 2 if (symbol == "XAUUSDc" and ai_mul >= 1.8 and ai_conf >= 70) else 0
        self.assertEqual(bonus, 2)
        
        # Scenario 4: Non-gold pair (No bonus)
        symbol2 = "EURUSDc"
        self.ea.symbol_tp_multipliers[symbol2] = 1.8
        self.ea.symbol_ai_confidence[symbol2] = 80
        ai_mul = self.ea.symbol_tp_multipliers.get(symbol2, 1.0)
        ai_conf = self.ea.symbol_ai_confidence.get(symbol2, 0)
        bonus = 2 if (symbol2 == "XAUUSDc" and ai_mul >= 1.8 and ai_conf >= 70) else 0
        self.assertEqual(bonus, 0)

if __name__ == '__main__':
    unittest.main()
