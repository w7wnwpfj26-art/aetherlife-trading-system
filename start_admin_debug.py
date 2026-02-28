#!/usr/bin/env python3
"""
快速启动脚本 - 后台管理系统（调试版）
"""

import asyncio
import sys
import os
import traceback

# 添加父目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("正在导入模块...")

try:
    from ui.admin_backend import AdminBackend
    print("✓ 模块导入成功")
except Exception as e:
    print(f"✗ 模块导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)


def main():
    """主函数"""
    print("""
    ╔═══════════════════════════════════════════╗
    ║   AI 合约交易系统 - 后台管理           ║
    ╚═══════════════════════════════════════════╝
    
    📝 功能:
       ✓ API密钥配置和测试
       ✓ 交易所对接管理
       ✓ 策略参数配置
       ✓ 风控设置
       ✓ AI功能开关
       ✓ 系统配置管理
    
    🔒 安全:
       ✓ API密钥加密存储
       ✓ 本地配置文件
       ✓ 无需上传到服务器
    
    """)
    
    # 创建后台实例
    try:
        print("正在创建后台实例...")
        backend = AdminBackend()
        print("✓ 后台实例创建成功")
    except Exception as e:
        print(f"✗ 创建后台实例失败: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    async def start_server():
        """启动服务器"""
        try:
            print("正在启动服务器...")
            runner = await backend.start(host='127.0.0.1', port=8080)
            
            print("=" * 50)
            print("✅ 后台管理系统已启动!")
            print(f"📱 访问地址: http://127.0.0.1:8080/admin")
            print("=" * 50)
            print("\n按 Ctrl+C 停止服务器\n")
            
            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                print("\n\n正在停止服务器...")
                await runner.cleanup()
                print("服务器已停止")
        except Exception as e:
            print(f"✗ 启动服务器失败: {e}")
            traceback.print_exc()
            sys.exit(1)
    
    # 运行服务器
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        print(f"❌ 运行失败: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
