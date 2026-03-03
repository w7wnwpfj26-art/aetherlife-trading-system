#!/usr/bin/env python3
"""
IBKR 完全对接演示脚本
展示如何将 AetherLife 系统完全对接到 IBKR TWS
"""

import asyncio
import logging
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aetherlife.perception.ibkr_connector_enhanced import create_ibkr_enhanced_connector
from aetherlife.execution.ibkr_executor import create_ibkr_executor
from aetherlife.execution.smart_router import SmartRouter, Exchange, LiquidityProvider
from aetherlife.cognition.schemas import TradeIntent, Action, Market


async def demo_full_ibkr_integration():
    """演示完整的 IBKR 对接流程"""
    
    print("=" * 60)
    print("🤖 AetherLife IBKR 完全对接演示")
    print("=" * 60)
    
    # 1. 连接 IBKR TWS
    print("\n🔌 正在连接 IBKR TWS...")
    try:
        connector = await create_ibkr_enhanced_connector(
            host="127.0.0.1",
            port=7497,  # Paper trading
            client_id=1,
            readonly=False  # 需要交易权限
        )
        
        if not connector.is_connected():
            print("❌ 无法连接到 IBKR TWS")
            print("💡 请确保：")
            print("   1. 已启动 TWS 或 IB Gateway")
            print("   2. 已启用 API 访问")
            print("   3. 端口设置为 7497 (Paper Trading)")
            return
        
        print("✅ IBKR 连接成功")
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return
    
    # 2. 创建执行器
    print("\n⚙️  初始化执行器...")
    try:
        executor = await create_ibkr_executor(
            host="127.0.0.1",
            port=7497,
            client_id=1
        )
        print("✅ 执行器初始化完成")
    except Exception as e:
        print(f"❌ 执行器初始化失败: {e}")
        return
    
    # 3. 查询账户信息
    print("\n💰 账户信息:")
    try:
        account = await executor.get_account_summary()
        print(f"   账户: {account.get('account', 'N/A')}")
        print(f"   可用资金: ${account.get('available_funds', 0):,.2f}")
        print(f"   购买力: ${account.get('buying_power', 0):,.2f}")
        print(f"   账户净值: ${account.get('equity_with_loan', 0):,.2f}")
    except Exception as e:
        print(f"   查询账户信息失败: {e}")
    
    # 4. 查询持仓
    print("\n📊 当前持仓:")
    try:
        positions = await executor.get_positions()
        if positions:
            for pos in positions[:5]:  # 显示前5个
                print(f"   {pos['symbol']}: {pos['position']} 股 @ ${pos['avg_cost']:.2f}")
        else:
            print("   无持仓")
    except Exception as e:
        print(f"   查询持仓失败: {e}")
    
    # 5. 智能路由演示
    print("\n🧭 智能路由测试:")
    router = SmartRouter(verbose=1)
    
    # 测试A股路由
    intent_a = TradeIntent(
        action=Action.BUY,
        market=Market.A_STOCK,
        symbol="600000",
        quantity_pct=0.1,  # 10%仓位
        confidence=0.8
    )
    
    decision_a = router.route(intent_a, balance=account.get('buying_power', 10000))
    print(f"   A股 {intent_a.symbol} → {decision_a.exchange.value} | {decision_a.order_type.value}")
    print(f"   原因: {decision_a.reason}")
    
    # 测试美股路由
    intent_us = TradeIntent(
        action=Action.BUY,
        market=Market.US_STOCK,
        symbol="AAPL",
        quantity_pct=0.05,  # 5%仓位
        confidence=0.9
    )
    
    decision_us = router.route(intent_us, balance=account.get('buying_power', 10000))
    print(f"   美股 {intent_us.symbol} → {decision_us.exchange.value} | {decision_us.order_type.value}")
    print(f"   原因: {decision_us.reason}")
    
    # 6. 实际下单演示（Dry Run）
    print("\n📝 订单执行演示 (Dry Run):")
    
    # 订阅实时行情
    def on_price_update(data):
        print(f"   📈 实时价格: {data['symbol']} = ${data['last_price']:.2f}")
    
    try:
        await connector.subscribe_ticker("AAPL", callback=on_price_update)
        await asyncio.sleep(2)  # 等待行情更新
    except Exception as e:
        print(f"   行情订阅失败: {e}")
    
    # 7. 模拟下单（不实际执行）
    print("\n🛒 模拟下单:")
    try:
        # 获取AAPL当前价格
        snapshot = await connector.get_snapshot("AAPL")
        if snapshot:
            price = snapshot.last_price
            print(f"   AAPL 当前价格: ${price:.2f}")
            
            # 计算订单数量（假设用1000 USD）
            quantity = 1000 / price
            print(f"   计划买入: {quantity:.2f} 股")
            
            # 模拟下单（实际不执行）
            print("   🎯 下单指令已生成（模拟模式）")
            print("   如需实际下单，请修改 dry_run=False")
        else:
            print("   无法获取AAPL价格")
            
    except Exception as e:
        print(f"   模拟下单失败: {e}")
    
    # 8. 清理资源
    print("\n🧹 清理资源...")
    await connector.close()
    await executor.close()
    
    print("\n✅ 演示完成！")
    print("\n📋 下一步:")
    print("   1. 修改配置启用实际交易")
    print("   2. 集成到 trading_bot.py")
    print("   3. 配置风险管理参数")
    print("   4. 启动自动化交易")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        asyncio.run(demo_full_ibkr_integration())
    except KeyboardInterrupt:
        print("\n👋 用户中断程序")
    except Exception as e:
        print(f"\n💥 程序异常: {e}")
        import traceback
        traceback.print_exc()
