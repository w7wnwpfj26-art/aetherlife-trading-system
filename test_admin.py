#!/usr/bin/env python3
"""
测试后台管理系统是否正常
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """测试导入"""
    print("测试导入模块...")
    
    try:
        from cryptography.fernet import Fernet
        print("✓ cryptography 导入成功")
    except ImportError as e:
        print(f"✗ cryptography 导入失败: {e}")
        return False
    
    try:
        from utils.config_manager import ConfigManager
        print("✓ ConfigManager 导入成功")
    except ImportError as e:
        print(f"✗ ConfigManager 导入失败: {e}")
        return False
    
    try:
        from ui.admin_backend import AdminBackend
        print("✓ AdminBackend 导入成功")
    except ImportError as e:
        print(f"✗ AdminBackend 导入失败: {e}")
        return False
    
    return True

def test_config_manager():
    """测试配置管理器"""
    print("\n测试配置管理器...")
    
    try:
        from utils.config_manager import ConfigManager
        
        # 创建临时配置管理器
        cm = ConfigManager()
        print(f"✓ 配置目录: {cm.config_dir}")
        
        # 测试默认配置
        default_config = cm.get_default_config()
        print(f"✓ 默认配置加载成功")
        print(f"  - 交易所: {default_config['exchange']}")
        print(f"  - 策略: {default_config['strategy']}")
        
        # 测试保存配置
        success = cm.save_config(default_config)
        if success:
            print("✓ 配置保存成功")
        else:
            print("✗ 配置保存失败")
            return False
        
        # 测试加载配置
        loaded_config = cm.load_config()
        if loaded_config:
            print("✓ 配置加载成功")
        else:
            print("✗ 配置加载失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ 配置管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_backend():
    """测试后台服务"""
    print("\n测试后台服务...")
    
    try:
        from ui.admin_backend import AdminBackend
        
        backend = AdminBackend()
        print("✓ AdminBackend 实例创建成功")
        
        # 检查路由
        routes = backend.app.router.routes()
        print(f"✓ 注册了 {len(list(routes))} 个路由")
        
        return True
        
    except Exception as e:
        print(f"✗ 后台服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("后台管理系统测试")
    print("=" * 50)
    
    # 测试导入
    if not test_imports():
        print("\n❌ 导入测试失败")
        sys.exit(1)
    
    # 测试配置管理器
    if not test_config_manager():
        print("\n❌ 配置管理器测试失败")
        sys.exit(1)
    
    # 测试后台服务
    if not test_backend():
        print("\n❌ 后台服务测试失败")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("✅ 所有测试通过！")
    print("=" * 50)
    print("\n可以运行以下命令启动后台管理系统：")
    print("  python3 start_admin.py")
    print("\n然后在浏览器访问：")
    print("  http://127.0.0.1:8080/admin")

if __name__ == '__main__':
    main()
