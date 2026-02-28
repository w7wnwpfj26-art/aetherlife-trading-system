#!/usr/bin/env python3
"""
检查后台管理系统是否运行
"""

import socket
import sys

def check_port(host, port):
    """检查端口是否被占用"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

def main():
    print("检查后台管理系统状态...\n")
    
    ports = [8080, 8081, 8082, 8888, 9000]
    running_ports = []
    
    for port in ports:
        if check_port('127.0.0.1', port):
            running_ports.append(port)
            print(f"✓ 端口 {port} 正在运行")
    
    if running_ports:
        print(f"\n✅ 后台管理系统正在运行!")
        print(f"\n📱 访问地址:")
        for port in running_ports:
            print(f"   http://127.0.0.1:{port}/admin")
        print("\n💡 提示: 在浏览器中打开上述地址访问管理界面")
    else:
        print("\n❌ 后台管理系统未运行")
        print("\n启动命令: python3 start_admin.py")

if __name__ == '__main__':
    main()
