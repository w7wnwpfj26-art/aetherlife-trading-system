"""
IBKR 执行器
完全对接 IBKR TWS API，实现订单执行、账户管理、持仓查询等功能
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from ib_insync import IB, Stock, Future, Forex, Contract, MarketOrder, LimitOrder
    from ib_insync import util as ib_util
    _IB_AVAILABLE = True
except ImportError:
    _IB_AVAILABLE = False
    IB = None
    Stock = Future = Forex = Contract = None

logger = logging.getLogger(__name__)


class IBKRExecutor:
    """
    IBKR 执行器
    
    功能：
    1. 连接 IBKR TWS/Gateway
    2. 订单执行（市价单、限价单）
    3. 账户信息查询
    4. 持仓管理
    5. 订单状态跟踪
    6. 实时成交回报
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        if not _IB_AVAILABLE:
            raise ImportError("ib_insync not installed. Run: pip install ib_insync")
        
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib: Optional[IB] = None
        self._connected = False
        self._orders: Dict[str, Any] = {}  # orderId -> order info
        self._positions: Dict[str, Any] = {}  # symbol -> position info
        
    async def connect(self) -> bool:
        """连接到 IBKR TWS/Gateway"""
        try:
            if self.ib is None:
                self.ib = IB()
            
            if not self.ib.isConnected():
                await self.ib.connectAsync(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    readonly=False,  # 执行需要写权限
                    timeout=20
                )
                
                # 设置订单状态回调
                self.ib.orderStatusEvent += self._on_order_status
                self.ib.execDetailsEvent += self._on_execution
                
                self._connected = True
                logger.info(f"IBKR 执行器连接成功: {self.host}:{self.port}")
                
                # 初始化持仓
                await self._load_positions()
                
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"IBKR 执行器连接失败: {e}")
            self._connected = False
            return False
    
    def _on_order_status(self, trade):
        """订单状态更新回调"""
        order_id = str(trade.order.orderId)
        status = trade.orderStatus.status
        filled = trade.orderStatus.filled
        avg_price = trade.orderStatus.avgFillPrice or 0
        
        logger.info(f"订单状态更新: {order_id} | 状态: {status} | 成交: {filled} | 均价: {avg_price}")
        
        if order_id in self._orders:
            self._orders[order_id].update({
                "status": status,
                "filled_qty": filled,
                "avg_fill_price": avg_price,
                "timestamp": datetime.now()
            })
    
    def _on_execution(self, trade, fill):
        """成交回报回调"""
        order_id = str(trade.order.orderId)
        exec_detail = fill.execution
        commission = fill.commissionReport.commission if fill.commissionReport else 0
        
        logger.info(f"成交回报: {order_id} | 价格: {exec_detail.price} | 数量: {exec_detail.shares} | 佣金: {commission}")
        
        if order_id in self._orders:
            if "executions" not in self._orders[order_id]:
                self._orders[order_id]["executions"] = []
            
            self._orders[order_id]["executions"].append({
                "price": exec_detail.price,
                "quantity": exec_detail.shares,
                "commission": commission,
                "time": exec_detail.time
            })
    
    async def _load_positions(self):
        """加载当前持仓"""
        try:
            if not self.ib:
                return
            
            positions = self.ib.positions()
            
            for pos in positions:
                symbol = pos.contract.symbol
                self._positions[symbol] = {
                    "symbol": symbol,
                    "sec_type": pos.contract.secType,
                    "exchange": pos.contract.exchange,
                    "currency": pos.contract.currency,
                    "position": pos.position,
                    "avg_cost": pos.avgCost,
                    "market_value": pos.marketValue,
                    "unrealized_pnl": pos.unrealizedPNL,
                    "realized_pnl": pos.realizedPNL
                }
            
            logger.info(f"加载持仓完成，共 {len(self._positions)} 个品种")
            
        except Exception as e:
            logger.error(f"加载持仓失败: {e}")
    
    def create_contract(self, symbol: str, sec_type: str = "STK", 
                       exchange: str = "SMART", currency: str = "USD") -> Optional[Contract]:
        """
        创建合约对象
        
        Args:
            symbol: 证券代码
            sec_type: 证券类型 STK/FUT/CASH
            exchange: 交易所
            currency: 货币
        """
        try:
            if sec_type == "STK":
                # A股特殊处理
                if symbol.startswith(("6", "0", "3")):
                    return Stock(symbol, "SEHK", "HKD")  # 通过港交所
                else:
                    return Stock(symbol, exchange, currency)
            
            elif sec_type == "FUT":
                return Future(symbol, exchange, currency)
            
            elif sec_type == "CASH":
                return Forex(symbol)
            
            return None
            
        except Exception as e:
            logger.error(f"创建合约失败 {symbol}: {e}")
            return None
    
    async def place_order(self, symbol: str, action: str, quantity: float,
                         order_type: str = "MKT", price: Optional[float] = None,
                         sec_type: str = "STK", exchange: str = "SMART",
                         currency: str = "USD") -> Dict[str, Any]:
        """
        下单执行
        
        Args:
            symbol: 证券代码
            action: BUY/SELL
            quantity: 数量
            order_type: MKT/LMT
            price: 限价（限价单必需）
            sec_type: 证券类型
            exchange: 交易所
            currency: 货币
        
        Returns:
            订单执行结果
        """
        if not self._connected or not self.ib:
            raise RuntimeError("IBKR 未连接")
        
        try:
            # 创建合约
            contract = self.create_contract(symbol, sec_type, exchange, currency)
            if not contract:
                raise ValueError(f"无法创建合约: {symbol}")
            
            # 验证合约
            qualified = await self.ib.qualifyContractsAsync(contract)
            if not qualified:
                raise ValueError(f"合约无效: {symbol}")
            
            contract = qualified[0]
            
            # 创建订单
            if order_type.upper() == "MKT":
                order = MarketOrder(action.upper(), quantity)
            elif order_type.upper() == "LMT" and price:
                order = LimitOrder(action.upper(), quantity, price)
            else:
                raise ValueError(f"不支持的订单类型: {order_type}")
            
            # 下单
            trade = self.ib.placeOrder(contract, order)
            
            # 等待订单确认
            await asyncio.sleep(0.5)
            
            order_id = str(trade.order.orderId)
            
            # 记录订单
            order_info = {
                "order_id": order_id,
                "symbol": symbol,
                "action": action.upper(),
                "quantity": quantity,
                "order_type": order_type.upper(),
                "price": price,
                "status": trade.orderStatus.status,
                "filled_qty": trade.orderStatus.filled,
                "avg_fill_price": trade.orderStatus.avgFillPrice or 0,
                "contract": contract,
                "timestamp": datetime.now()
            }
            
            self._orders[order_id] = order_info
            
            logger.info(f"下单成功: {order_id} | {symbol} | {action} {quantity}")
            
            return {
                "success": True,
                "order_id": order_id,
                "status": trade.orderStatus.status,
                "filled_qty": trade.orderStatus.filled,
                "avg_fill_price": trade.orderStatus.avgFillPrice or 0
            }
            
        except Exception as e:
            logger.error(f"下单失败 {symbol}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        取消订单
        
        Args:
            order_id: 订单ID
        
        Returns:
            取消结果
        """
        if not self._connected or not self.ib:
            raise RuntimeError("IBKR 未连接")
        
        try:
            if order_id not in self._orders:
                raise ValueError(f"订单不存在: {order_id}")
            
            contract = self._orders[order_id]["contract"]
            self.ib.cancelOrder(contract, int(order_id))
            
            logger.info(f"取消订单: {order_id}")
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"取消订单失败 {order_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_account_summary(self) -> Dict[str, Any]:
        """
        获取账户摘要
        
        Returns:
            账户信息
        """
        if not self._connected or not self.ib:
            await self.connect()
        
        try:
            accounts = self.ib.managedAccounts()
            if not accounts:
                return {}
            
            account = accounts[0]
            summary = self.ib.accountSummary(account)
            
            result = {
                "account": account,
                "available_funds": 0,
                "equity_with_loan": 0,
                "maintenance_margin": 0,
                "gross_position_value": 0,
                "buying_power": 0
            }
            
            for item in summary:
                if item.tag == "AvailableFunds":
                    result["available_funds"] = float(item.value)
                elif item.tag == "EquityWithLoanValue":
                    result["equity_with_loan"] = float(item.value)
                elif item.tag == "MaintMarginReq":
                    result["maintenance_margin"] = float(item.value)
                elif item.tag == "GrossPositionValue":
                    result["gross_position_value"] = float(item.value)
                elif item.tag == "BuyingPower":
                    result["buying_power"] = float(item.value)
            
            return result
            
        except Exception as e:
            logger.error(f"获取账户摘要失败: {e}")
            return {}
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        获取持仓列表
        
        Returns:
            持仓列表
        """
        await self._load_positions()
        return list(self._positions.values())
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取单个品种持仓
        
        Args:
            symbol: 证券代码
        
        Returns:
            持仓信息或None
        """
        await self._load_positions()
        return self._positions.get(symbol)
    
    async def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        获取订单状态
        
        Args:
            order_id: 订单ID
        
        Returns:
            订单信息或None
        """
        return self._orders.get(order_id)
    
    async def close(self):
        """关闭连接"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            logger.info("IBKR 执行器连接已关闭")
        
        self._connected = False
        self._orders.clear()
        self._positions.clear()
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected and self.ib is not None and self.ib.isConnected()


# 工厂函数
async def create_ibkr_executor(host: str = "127.0.0.1", port: int = 7497, 
                              client_id: int = 1) -> IBKRExecutor:
    """创建并连接 IBKR 执行器"""
    executor = IBKRExecutor(host=host, port=port, client_id=client_id)
    await executor.connect()
    return executor


if __name__ == "__main__":
    # 演示用法
    async def demo():
        executor = await create_ibkr_executor()
        
        if not executor.is_connected():
            print("❌ IBKR 未连接，请启动 TWS/Gateway")
            return
        
        print("✅ IBKR 执行器连接成功")
        
        # 1. 查询账户信息
        account = await executor.get_account_summary()
        print(f"可用资金: ${account['available_funds']:,.2f}")
        print(f"购买力: ${account['buying_power']:,.2f}")
        
        # 2. 查询持仓
        positions = await executor.get_positions()
        print(f"当前持仓数: {len(positions)}")
        for pos in positions[:3]:  # 显示前3个
            print(f"  {pos['symbol']}: {pos['position']} 股 @ ${pos['avg_cost']:.2f}")
        
        # 3. 下市价单（演示）
        print("\n--- 下单演示 ---")
        result = await executor.place_order(
            symbol="AAPL",
            action="BUY",
            quantity=10,
            order_type="MKT"
        )
        
        if result["success"]:
            print(f"✅ 下单成功，订单ID: {result['order_id']}")
            print(f"  状态: {result['status']}")
            print(f"  成交数量: {result['filled_qty']}")
        else:
            print(f"❌ 下单失败: {result['error']}")
        
        await asyncio.sleep(2)
        await executor.close()
    
    asyncio.run(demo())
