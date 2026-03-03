# tests/test_config_manager.py
"""配置管理器单元测试：默认配置、校验、导出等"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_dir = self.tmp.name
        self.manager = ConfigManager(config_dir=self.config_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_default_config(self):
        cfg = self.manager.get_default_config()
        self.assertIsInstance(cfg, dict)
        self.assertIn("exchange", cfg)
        self.assertEqual(cfg["exchange"], "binance")
        self.assertIn("symbols", cfg)
        self.assertIn("risk", cfg)
        self.assertIn("strategy_config", cfg)

    def test_validate_api_keys_empty(self):
        ok, msg = self.manager.validate_api_keys("binance", "", "secret")
        self.assertFalse(ok)
        self.assertIn("不能为空", msg)
        ok, msg = self.manager.validate_api_keys("binance", "key", "")
        self.assertFalse(ok)

    def test_validate_api_keys_too_short(self):
        ok, msg = self.manager.validate_api_keys(
            "binance", "short_key", "x" * 25
        )
        self.assertFalse(ok)
        self.assertIn("API Key", msg)
        ok, msg = self.manager.validate_api_keys(
            "binance", "a" * 25, "short"
        )
        self.assertFalse(ok)
        self.assertIn("Secret", msg)

    def test_validate_api_keys_ok(self):
        ok, msg = self.manager.validate_api_keys(
            "binance", "a" * 25, "b" * 25
        )
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_save_and_load_config(self):
        cfg = self.manager.get_default_config()
        cfg["symbols"] = ["BTCUSDT", "ETHUSDT"]
        self.assertTrue(self.manager.save_config(cfg))
        loaded = self.manager.load_config()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.get("symbols"), ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(loaded.get("exchange"), "binance")

    def test_export_config_excludes_sensitive_by_default(self):
        cfg = self.manager.get_default_config()
        cfg["api_key"] = "test_key"
        cfg["secret_key"] = "test_secret"
        self.manager.save_config(cfg)
        exported = self.manager.export_config(include_sensitive=False)
        self.assertIsNotNone(exported)
        self.assertNotIn("api_key", exported)
        self.assertNotIn("secret_key", exported)

    def test_list_saved_configs(self):
        configs = self.manager.list_saved_configs()
        self.assertIsInstance(configs, list)
        self.manager.save_config(self.manager.get_default_config())
        configs = self.manager.list_saved_configs()
        self.assertIn("default", configs)


if __name__ == "__main__":
    unittest.main()
