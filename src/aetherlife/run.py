"""
AetherLife 入口
运行方式（任选其一）:
  cd src && python -m aetherlife.run
  cd 项目根 && python src/aetherlife/run.py
"""

import asyncio
import json
import logging
import os
import sys

# 项目根 = 含 src 的目录；path 需包含 src 以便 import data/execution/aetherlife
_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_here)
if _src not in sys.path:
    sys.path.insert(0, _src)
# 项目根（上一级）
_root = os.path.dirname(_src)

from aetherlife import AetherLife
from aetherlife.config import AetherLifeConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _load_config() -> AetherLifeConfig:
    config = AetherLifeConfig(symbol=os.getenv("AETHERLIFE_SYMBOL", "BTCUSDT"))
    for path in (
        os.path.join(_root, "configs", "aetherlife.json"),
        os.path.join(_root, "aetherlife.json"),
        os.path.join(_src, "aetherlife.json"),
    ):
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                config = AetherLifeConfig.from_dict(data)
            except Exception as e:
                logging.warning("加载配置 %s 失败: %s", path, e)
            break
    config.symbol = os.getenv("AETHERLIFE_SYMBOL", config.symbol)
    config.execution.testnet = os.getenv("AETHERLIFE_TESTNET", "true").lower() == "true"
    return config


async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_root, ".env"))
        load_dotenv()
    except ImportError:
        pass
    config = _load_config()
    life = AetherLife(config=config)
    try:
        await life.run(interval_seconds=float(os.getenv("AETHERLIFE_INTERVAL", "15")))
    except KeyboardInterrupt:
        life.stop()
    finally:
        await life.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
