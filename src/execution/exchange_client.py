"""
执行模块
处理交易所API下单、撤单、仓位管理等
"""

import asyncio
import aiohttp
import hmac
import hashlib
import time
from typing import Dict, List, Optional
from datetime import datetime
import json


# 请求超时（秒），避免长时间挂起
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5)


class ExchangeClient:
    """交易所客户端基类"""
    
    def __init__(self, api_key: str = "", secret_key: str = "", testnet: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        self.session = None
        self.position = {}
        self.balance = {}
        self._timeout = REQUEST_TIMEOUT

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self._timeout)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None
    
    # ========== 行情接口 ==========
    async def get_ticker(self, symbol: str) -> Dict:
        """获取24小时行情"""
        raise NotImplementedError
    
    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """获取订单簿"""
        raise NotImplementedError
    
    async def get_exchange_info(self, symbol: str) -> Dict:
        """获取交易对规则信息"""
        return {}

    # ========== 交易接口 ==========
    async def get_balance(self) -> Dict:
        """获取账户余额"""
        raise NotImplementedError
    
    async def get_position(self, symbol: str) -> Dict:
        """获取仓位"""
        raise NotImplementedError
    
    async def place_order(self, symbol: str, side: str, order_type: str, 
                         quantity: float, price: float = 0, 
                         leverage: int = 10, reduce_only: bool = False) -> Dict:
        """下单"""
        raise NotImplementedError
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """取消订单"""
        raise NotImplementedError
    
    async def get_orders(self, symbol: str) -> List[Dict]:
        """获取活跃订单"""
        raise NotImplementedError
    
    async def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """设置杠杆"""
        raise NotImplementedError
    
    async def set_margin_type(self, symbol: str, margin_type: str = "CROSSED") -> Dict:
        """设置持仓模式 (逐仓/全仓)"""
        raise NotImplementedError


class BinanceClient(ExchangeClient):
    """Binance 合约交易客户端"""
    
    def __init__(self, api_key: str = "", secret_key: str = "", testnet: bool = True):
        super().__init__(api_key, secret_key, testnet)
        self.exchange = "binance"
        self.exchange_info = {}
        if testnet:
            self.base_url = "https://testnet.binancefuture.com"
            self.ws_url = "wss://stream.testnet.binancefuture.com/ws"
        else:
            self.base_url = "https://fapi.binance.com"
            self.ws_url = "wss://fstream.binance.com/ws"
    
    async def load_exchange_info(self):
        """加载交易规则"""
        try:
            info = await self._request("GET", "/fapi/v1/exchangeInfo")
            if "symbols" in info:
                for s in info["symbols"]:
                    self.exchange_info[s["symbol"]] = {
                        "quantity_precision": s["quantityPrecision"],
                        "price_precision": s["pricePrecision"],
                        "min_qty": 0.001, # Default fallback
                        "step_size": 0.001
                    }
                    # 解析 filters 获取更精确的 stepSize
                    for f in s.get("filters", []):
                        if f["filterType"] == "LOT_SIZE":
                            self.exchange_info[s["symbol"]]["min_qty"] = float(f["minQty"])
                            self.exchange_info[s["symbol"]]["step_size"] = float(f["stepSize"])
                            
        except Exception as e:
            print(f"Failed to load exchange info: {e}")

    async def get_exchange_info(self, symbol: str) -> Dict:
        """获取交易对规则信息"""
        if not self.exchange_info:
            await self.load_exchange_info()
        return self.exchange_info.get(symbol, {})

    def _sign(self, params: str) -> str:
        """签名"""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        """发送请求"""
        session = await self._get_session()
        
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if params is None:
            params = {}
        
        # 签名
        if signed and self.api_key and self.secret_key:
            params['timestamp'] = int(time.time() * 1000)
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            params['signature'] = self._sign(query_string)
            headers['X-MBX-APIKEY'] = self.api_key
        
        try:
            if method == "GET":
                async with session.get(url, params=params, headers=headers) as resp:
                    data = await resp.json()
            elif method == "POST":
                async with session.post(url, params=params, headers=headers) as resp:
                    data = await resp.json()
            elif method == "DELETE":
                async with session.delete(url, params=params, headers=headers) as resp:
                    data = await resp.json()
            else:
                return {}
            # Binance 错误码：非 2xx 或 body 中 code 非 0 表示错误
            if isinstance(data, dict) and data.get("code") is not None and data.get("code") != 0:
                raise RuntimeError(f"Binance API 错误: code={data.get('code')} msg={data.get('msg', '')}")
            return data
        except aiohttp.ClientError as e:
            raise RuntimeError(f"请求失败: {e}") from e
    
    # ========== 行情接口 ==========
    async def get_ticker(self, symbol: str = "BTCUSDT") -> Dict:
        """获取24小时行情"""
        return await self._request("GET", "/fapi/v1/ticker/24hr", {"symbol": symbol})
    
    async def get_orderbook(self, symbol: str = "BTCUSDT", limit: int = 20) -> Dict:
        """获取订单簿"""
        return await self._request("GET", "/fapi/v1/depth", {"symbol": symbol, "limit": limit})
    
    async def get_price(self, symbol: str = "BTCUSDT") -> float:
        """获取当前价格"""
        ticker = await self.get_ticker(symbol)
        return float(ticker.get("lastPrice", 0))
    
    # ========== 交易接口 ==========
    async def get_balance(self) -> Dict:
        """获取账户余额"""
        if not self.api_key:
            return {"total": 0, "free": 0, "locked": 0}
        try:
            result = await self._request("GET", "/fapi/v2/account", {}, signed=True)
        except Exception:
            return getattr(self, "balance", {"total": 0, "free": 0, "locked": 0}) or {"total": 0, "free": 0, "locked": 0}
        if isinstance(result, dict) and "assets" in result:
            for asset in result["assets"]:
                if asset.get("asset") == "USDT":
                    self.balance = {
                        "total": float(asset.get("walletBalance", 0)),
                        "free": float(asset.get("availableBalance", 0)),
                        "locked": float(asset.get("walletBalance", 0)) - float(asset.get("availableBalance", 0))
                    }
                    return self.balance
        return self.balance if self.balance else {"total": 0, "free": 0, "locked": 0}
    
    async def get_position(self, symbol: str = "BTCUSDT") -> Dict:
        """获取仓位"""
        if not self.api_key:
            return {"symbol": symbol, "amount": 0, "entry_price": 0, "leverage": 10}
        
        result = await self._request("GET", "/fapi/v2/positionRisk", {"symbol": symbol}, signed=True)
        
        if result:
            pos = result[0] if result else {}
            self.position = {
                "symbol": pos.get("symbol"),
                "amount": float(pos.get("positionAmt", 0)),
                "entry_price": float(pos.get("entryPrice", 0)),
                "unrealized_pnl": float(pos.get("unrealizedProfit", 0)),
                "leverage": int(pos.get("leverage", 10)),
                "margin": float(pos.get("margin", 0)),
            }
        
        return self.position
    
    async def place_order(self, symbol: str = "BTCUSDT", side: str = "BUY", 
                         order_type: str = "MARKET", quantity: float = 0.001,
                         price: float = 0, leverage: int = 10,
                         reduce_only: bool = False) -> Dict:
        """下单"""
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "positionSide": "BOTH",
            "reduceOnly": reduce_only,
        }
        
        if order_type.upper() == "MARKET":
            params["type"] = "MARKET"
            
            # 动态精度处理
            precision = 3
            if not self.exchange_info:
                await self.load_exchange_info()
            
            if symbol in self.exchange_info:
                precision = self.exchange_info[symbol]["quantity_precision"]
            
            # 确保 quantity 符合 step_size
            step_size = self.exchange_info.get(symbol, {}).get("step_size", 0.001)
            if step_size > 0:
                quantity = int(quantity / step_size) * step_size
                
            params["quantity"] = round(quantity, precision)
        else:
            params["type"] = "LIMIT"
            params["quantity"] = quantity
            params["price"] = price
            params["timeInForce"] = "GTC"
        
        # 设置杠杆
        await self.set_leverage(symbol, leverage)
        
        result = await self._request("POST", "/fapi/v1/order", params, signed=True)
        
        return {
            "success": result.get("orderId") is not None,
            "order_id": result.get("orderId"),
            "symbol": result.get("symbol"),
            "side": result.get("side"),
            "price": float(result.get("price", 0)),
            "quantity": float(result.get("origQty", 0)),
            "status": result.get("status"),
            "raw": result
        }
    
    async def cancel_order(self, symbol: str = "BTCUSDT", order_id: str = "") -> Dict:
        """取消订单"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        
        result = await self._request("DELETE", "/fapi/v1/order", params, signed=True)
        
        return {
            "success": result.get("orderId") is not None,
            "order_id": result.get("orderId"),
            "raw": result
        }
    
    async def get_orders(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """获取活跃订单"""
        if not self.api_key:
            return []
        
        params = {"symbol": symbol}
        result = await self._request("GET", "/fapi/v1/openOrders", params, signed=True)
        
        return result
    
    async def set_leverage(self, symbol: str = "BTCUSDT", leverage: int = 10) -> Dict:
        """设置杠杆"""
        if not self.api_key:
            return {"success": True}
        
        params = {
            "symbol": symbol,
            "leverage": leverage
        }
        
        result = await self._request("POST", "/fapi/v1/leverage", params, signed=True)
        
        return {
            "success": result.get("leverage") is not None,
            "leverage": leverage,
            "raw": result
        }
    
    async def set_margin_type(self, symbol: str = "BTCUSDT", margin_type: str = "CROSSED") -> Dict:
        """设置持仓模式"""
        if not self.api_key:
            return {"success": True}
        
        params = {
            "symbol": symbol,
            "marginType": margin_type
        }
        
        result = await self._request("POST", "/fapi/v1/marginType", params, signed=True)
        
        return {
            "success": result.get("code") is None or result.get("code") == 200 or result.get("marginType") == margin_type,
            "margin_type": margin_type,
            "raw": result
        }
    
    async def get_leverage_bracket(self, symbol: str = "BTCUSDT") -> Dict:
        """获取杠杆分层"""
        params = {"symbol": symbol}
        result = await self._request("GET", "/fapi/v1/leverageBracket", params, signed=True)
        return result


class OKXClient(ExchangeClient):
    """OKX 合约交易客户端"""
    
    def __init__(self, api_key: str = "", secret_key: str = "", testnet: bool = True):
        super().__init__(api_key, secret_key, testnet)
        self.exchange = "okx"
        self.base_url = "https://www.okx.com"
    
    # 实现类似的接口...
    async def get_ticker(self, symbol: str = "BTC-USDT-SWAP") -> Dict:
        session = await self._get_session()
        url = f"{self.base_url}/api/v5/market/ticker"
        params = {"instId": symbol}
        
        async with session.get(url, params=params) as resp:
            data = await resp.json()
        
        if data.get("code") == "0":
            ticker = data["data"][0]
            return {
                "symbol": ticker.get("instId"),
                "last_price": float(ticker.get("last", 0)),
                "bid_price": float(ticker.get("bidPx", 0)),
                "ask_price": float(ticker.get("askPx", 0)),
            }
        return {}
    
    async def get_orderbook(self, symbol: str = "BTC-USDT-SWAP", limit: int = 20) -> Dict:
        session = await self._get_session()
        url = f"{self.base_url}/api/v5/market/books"
        params = {"instId": symbol, "sz": limit}
        
        async with session.get(url, params=params) as resp:
            data = await resp.json()
        
        if data.get("code") == "0":
            return data["data"][0]
        return {}
    
    async def get_balance(self) -> Dict:
        # OKX 账户余额查询需要签名
        return {"total": 0, "free": 0, "locked": 0}
    
    async def get_position(self, symbol: str = "BTC-USDT-SWAP") -> Dict:
        return {"symbol": symbol, "amount": 0, "entry_price": 0, "leverage": 10}
    
    async def place_order(self, symbol: str = "BTC-USDT-SWAP", side: str = "buy", 
                         order_type: str = "market", quantity: float = 0.001,
                         price: float = 0, leverage: int = 10,
                         reduce_only: bool = False) -> Dict:
        # OKX 下单需要签名
        return {"success": False, "error": "OKX not implemented yet"}
    
    async def set_leverage(self, symbol: str = "BTC-USDT-SWAP", leverage: int = 10) -> Dict:
        return {"success": True}


# 便捷函数
def create_client(exchange: str = "binance", api_key: str = "", secret_key: str = "", testnet: bool = True) -> ExchangeClient:
    """创建交易所客户端"""
    if exchange.lower() == "binance":
        return BinanceClient(api_key, secret_key, testnet)
    elif exchange.lower() == "okx":
        return OKXClient(api_key, secret_key, testnet)
    else:
        raise ValueError(f"Unsupported exchange: {exchange}")


# 测试
if __name__ == "__main__":
    async def test():
        # 测试 Binance 测试网
        client = BinanceClient(testnet=True)
        
        # 获取行情
        ticker = await client.get_ticker("BTCUSDT")
        print("24小时行情:", ticker.get("lastPrice"))
        
        # 获取订单簿
        orderbook = await client.get_orderbook("BTCUSDT")
        print("卖单:", orderbook.get("asks", [])[:3])
        print("买单:", orderbook.get("bids", [])[:3])
        
        await client.close()
        print("\n测试完成!")
    
    asyncio.run(test())
