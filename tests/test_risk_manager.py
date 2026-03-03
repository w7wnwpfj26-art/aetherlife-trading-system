# tests/test_risk_manager.py
"""风控模块单元测试：仓位计算、止损止盈、仓位管理"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.risk_manager import RiskManager, PositionManager


class TestRiskManager(unittest.TestCase):
    def setUp(self):
        self.config = {
            "max_position_pct": 0.1,
            "min_position_pct": 0.01,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.05,
            "max_daily_trades": 20,
            "max_consecutive_losses": 5,
            "circuit_breaker_loss_pct": 0.2,
        }
        self.risk = RiskManager(self.config)

    def test_calculate_position_size_zero_price(self):
        self.assertEqual(
            self.risk.calculate_position_size({"strength": 0.8}, 10000, 0), 0.0
        )

    def test_calculate_position_size_zero_balance(self):
        self.assertEqual(
            self.risk.calculate_position_size({"strength": 0.8}, 0, 50000), 0.0
        )

    def test_calculate_position_size_in_range(self):
        size = self.risk.calculate_position_size(
            {"strength": 0.8}, 10000, 50000
        )
        # 10000 * 0.1 * 0.8 / 50000 = 0.016, 介于 min 0.002 与 max 0.02 之间
        self.assertGreater(size, 0)
        self.assertLessEqual(size, 10000 * 0.1 / 50000)

    def test_calculate_position_size_respects_min_max(self):
        # 极弱信号应不低于 min_position_pct
        size_low = self.risk.calculate_position_size(
            {"strength": 0.01}, 10000, 50000
        )
        self.assertGreaterEqual(size_low, 10000 * 0.01 / 50000)
        # 满信号应不超过 max_position_pct
        size_high = self.risk.calculate_position_size(
            {"strength": 1.5}, 10000, 50000
        )
        self.assertLessEqual(size_high, 10000 * 0.1 / 50000)

    def test_check_stop_loss_long(self):
        # LONG: 跌 2% 触发止损
        r = self.risk.check_stop_loss(50000, 49000, "LONG")
        self.assertTrue(r["should_stop"])
        self.assertAlmostEqual(r["loss_pct"], 0.02)
        self.assertEqual(r["reason"], "stop_loss")
        r2 = self.risk.check_stop_loss(50000, 49200, "LONG")
        self.assertFalse(r2["should_stop"])

    def test_check_stop_loss_short(self):
        # SHORT: 涨 2% 触发止损
        r = self.risk.check_stop_loss(50000, 51000, "SHORT")
        self.assertTrue(r["should_stop"])
        self.assertAlmostEqual(r["loss_pct"], 0.02)

    def test_check_take_profit_long(self):
        r = self.risk.check_take_profit(50000, 52500, "LONG")
        self.assertTrue(r["should_stop"])
        self.assertAlmostEqual(r["profit_pct"], 0.05)
        self.assertEqual(r["reason"], "take_profit")
        r2 = self.risk.check_take_profit(50000, 52400, "LONG")
        self.assertFalse(r2["should_stop"])

    def test_check_take_profit_short(self):
        r = self.risk.check_take_profit(50000, 47500, "SHORT")
        self.assertTrue(r["should_stop"])
        self.assertAlmostEqual(r["profit_pct"], 0.05)

    def test_check_stop_loss_invalid_entry(self):
        r = self.risk.check_stop_loss(0, 100, "LONG")
        self.assertFalse(r["should_stop"])
        self.assertEqual(r["loss_pct"], 0)


class TestPositionManager(unittest.TestCase):
    def setUp(self):
        self.mgr = PositionManager()

    def test_open_and_get_position(self):
        self.mgr.open_position("BTCUSDT", "LONG", 0.01, 50000.0, 10)
        pos = self.mgr.get_position("BTCUSDT")
        self.assertIsNotNone(pos)
        self.assertEqual(pos["symbol"], "BTCUSDT")
        self.assertEqual(pos["side"], "LONG")
        self.assertEqual(pos["quantity"], 0.01)
        self.assertEqual(pos["leverage"], 10)

    def test_get_nonexistent_position(self):
        self.assertIsNone(self.mgr.get_position("ETHUSDT"))

    def test_update_position(self):
        self.mgr.open_position("BTCUSDT", "LONG", 0.01, 50000.0, 10)
        self.mgr.update_position("BTCUSDT", 51000.0)
        pos = self.mgr.get_position("BTCUSDT")
        self.assertEqual(pos["current_price"], 51000.0)

    def test_close_position(self):
        self.mgr.open_position("BTCUSDT", "LONG", 0.01, 50000.0, 10)
        result = self.mgr.close_position("BTCUSDT", 51000.0)
        self.assertIn("pnl", result)
        self.assertTrue(result.get("success", False))
        self.assertIsNone(self.mgr.get_position("BTCUSDT"))

    def test_get_all_positions(self):
        self.mgr.open_position("BTCUSDT", "LONG", 0.01, 50000.0, 10)
        all_pos = self.mgr.get_all_positions()
        self.assertIsInstance(all_pos, dict)
        self.assertIn("BTCUSDT", all_pos)


if __name__ == "__main__":
    unittest.main()
