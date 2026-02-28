#!/usr/bin/env python3
"""
快速启动脚本 - 后台管理系统
"""

import asyncio
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ui.admin_backend import AdminBackend


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
    backend = AdminBackend()
    
    async def start_server():
        """启动服务器"""
        # 尝试多个端口
        ports = [8080, 8081, 8082, 8888, 9000]
        runner = None
        
        for port in ports:
            try:
                runner = await backend.start(host='127.0.0.1', port=port)
                
                print("=" * 50)
                print("✅ 后台管理系统已启动!")
                print(f"📱 访问地址: http://127.0.0.1:{port}/admin")
                print("=" * 50)
                print("\n按 Ctrl+C 停止服务器\n")
                break
            except OSError as e:
                if "address already in use" in str(e):
                    print(f"端口 {port} 已被占用，尝试下一个...")
                    continue
                else:
                    raise
        
        if runner is None:
            print("❌ 所有端口都被占用，请手动停止其他服务")
            return
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\n\n正在停止服务器...")
            await runner.cleanup()
            print("服务器已停止")
    
    # 运行服务器
    try:
        asyncio.run(start_server())
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
