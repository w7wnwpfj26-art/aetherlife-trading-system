"""
配置管理器
负责配置文件的加密存储、读取和验证
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, List
import base64
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = None):
        """初始化配置管理器"""
        if config_dir is None:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs")
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.config_dir / "config.json"
        self.secure_config_file = self.config_dir / "secure.enc"
        
        # 加密密钥（生产环境应该从环境变量读取）
        self._init_encryption()
        
    def _init_encryption(self):
        """初始化加密"""
        key_file = self.config_dir / ".key"
        
        if key_file.exists():
            with open(key_file, "rb") as f:
                self.key = f.read()
        else:
            # 生成新密钥
            self.key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(self.key)
            # 设置文件权限为只读
            os.chmod(key_file, 0o600)
        
        self.cipher = Fernet(self.key)
    
    def save_config(self, config: Dict) -> bool:
        """保存配置（普通配置）"""
        try:
            # 分离敏感信息
            safe_config = config.copy()
            secure_data = {}
            
            # 提取敏感字段
            sensitive_fields = ["api_key", "secret_key", "passphrase"]
            for field in sensitive_fields:
                if field in safe_config:
                    secure_data[field] = safe_config.pop(field)
            
            # 保存普通配置
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(safe_config, f, indent=2, ensure_ascii=False)
            
            # 加密保存敏感信息
            if secure_data:
                self._save_secure_data(secure_data)
            
            return True
        except Exception as e:
            logger.exception("保存配置失败")
            return False
    
    def _save_secure_data(self, data: Dict):
        """加密保存敏感数据"""
        json_data = json.dumps(data).encode()
        encrypted_data = self.cipher.encrypt(json_data)
        with open(self.secure_config_file, "wb") as f:
            f.write(encrypted_data)
        os.chmod(self.secure_config_file, 0o600)
    
    def load_config(self) -> Optional[Dict]:
        """加载完整配置"""
        try:
            config = {}
            
            # 加载普通配置
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
            
            # 加载加密的敏感信息
            secure_data = self._load_secure_data()
            if secure_data:
                config.update(secure_data)
            
            return config if config else None
        except Exception as e:
            logger.exception("加载配置失败")
            return None
    
    def _load_secure_data(self) -> Optional[Dict]:
        """解密加载敏感数据"""
        try:
            if not self.secure_config_file.exists():
                return None
            
            with open(self.secure_config_file, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.warning("解密敏感数据失败: %s", e)
            return None
    
    def get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "exchange": "binance",
            "testnet": True,
            "symbols": ["BTCUSDT"],
            "timeframe": "1m",
            "strategy": "breakout",
            "leverage": 10,
            "strategy_config": {
                "lookback_period": 20,
                "threshold": 0.005,
                "atr_multiplier": 2
            },
            "risk": {
                "max_position_pct": 0.1,
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.05,
                "max_daily_loss": 0.05
            },
            "ai_enhance": {
                "enabled": False,
                "multi_agent": False,
                "ml_predictor": False,
                "sentiment": False,
                "auto_compound": False
            }
        }
    
    def validate_api_keys(self, exchange: str, api_key: str, secret_key: str, testnet: bool = True) -> tuple[bool, str]:
        """
        验证API密钥
        返回: (是否有效, 错误信息)
        """
        if not api_key or not secret_key:
            return False, "API Key 和 Secret Key 不能为空"
        
        if len(api_key) < 20:
            return False, "API Key 格式不正确"
        
        if len(secret_key) < 20:
            return False, "Secret Key 格式不正确"
        
        return True, ""
    
    def list_saved_configs(self) -> List[str]:
        """列出所有保存的配置"""
        configs = []
        if self.config_file.exists():
            configs.append("default")
        return configs
    
    def delete_config(self) -> bool:
        """删除配置"""
        try:
            if self.config_file.exists():
                os.remove(self.config_file)
            if self.secure_config_file.exists():
                os.remove(self.secure_config_file)
            return True
        except Exception as e:
            logger.exception("删除配置失败")
            return False
    
    def export_config(self, include_sensitive: bool = False) -> Optional[Dict]:
        """导出配置（可选是否包含敏感信息）"""
        config = self.load_config()
        if not config:
            return None
        
        if not include_sensitive:
            # 移除敏感字段
            sensitive_fields = ["api_key", "secret_key", "passphrase"]
            for field in sensitive_fields:
                config.pop(field, None)
        
        return config
    
    def test_connection(self, exchange: str, api_key: str, secret_key: str, testnet: bool = True) -> tuple[bool, str]:
        """
        测试交易所连接（先校验格式，再实际请求公开行情接口）
        返回: (是否成功, 消息)
        """
        import asyncio

        # ── 1. 格式校验 ──────────────────────────────────────────
        valid, msg = self.validate_api_keys(exchange, api_key, secret_key, testnet)
        if not valid:
            return False, msg

        # ── 2. 实际网络连通性测试（调用公开接口，不需要签名）────────
        async def _ping() -> tuple[bool, str]:
            try:
                import sys, os
                src_dir = os.path.join(os.path.dirname(__file__), "..")
                if src_dir not in sys.path:
                    sys.path.insert(0, src_dir)
                from execution.exchange_client import create_client
                client = create_client(exchange, api_key, secret_key, testnet)
                try:
                    # 使用公开 ticker 接口测试网络连通性
                    default_symbol = "BTCUSDT" if exchange.lower() == "binance" else "BTC-USDT-SWAP"
                    ticker = await client.get_ticker(default_symbol)
                    if ticker and ticker.get("last_price", 0) > 0:
                        price = ticker["last_price"]
                        net_label = "测试网" if testnet else "主网"
                        return True, f"连接成功 [{exchange.upper()} {net_label}] BTC 最新价: ${price:,.2f}"
                    return False, "接口返回数据异常，请检查网络或交易所状态"
                finally:
                    await client.close()
            except Exception as e:
                return False, f"连接失败: {e}"

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已在异步上下文中（如 Jupyter / 异步服务器），创建独立 task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, _ping())
                    return future.result(timeout=20)
            else:
                return loop.run_until_complete(_ping())
        except Exception as e:
            return False, f"连接测试失败: {e}"
