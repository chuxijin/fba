#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery服务启动脚本 - Python版本
适用于跨平台运行，特别是Windows环境
"""
import os
import sys
import signal
import subprocess
import time
import atexit
from pathlib import Path


class CeleryManager:
    """Celery服务管理器"""
    
    def __init__(self):
        self.processes = []
        self.base_dir = Path(__file__).parent
        
    def start_process(self, name: str, cmd: list[str]) -> subprocess.Popen | None:
        """
        启动子进程
        
        :param name: 进程名称
        :param cmd: 命令列表
        :return: 进程对象或None
        """
        try:
            print(f"🚀 启动 {name}...")
            print(f"   命令: {' '.join(cmd)}")
            
            # Windows下创建新的进程组
            if os.name == 'nt':
                process = subprocess.Popen(
                    cmd,
                    cwd=self.base_dir,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                process = subprocess.Popen(cmd, cwd=self.base_dir)
            
            self.processes.append({
                'name': name,
                'process': process,
                'cmd': cmd
            })
            
            print(f"✅ {name} 已启动 (PID: {process.pid})")
            return process
            
        except Exception as e:
            print(f"❌ 启动 {name} 失败: {e}")
            return None
    
    def check_python_environment(self) -> bool:
        """检查Python环境"""
        try:
            import celery
            print(f"✅ Python环境检查通过")
            print(f"   Python版本: {sys.version.split()[0]}")
            print(f"   Celery版本: {celery.__version__}")
            return True
        except ImportError as e:
            print(f"❌ 环境检查失败: {e}")
            print("   请安装依赖: pip install celery[gevent] flower")
            return False
    
    def start_all_services(self):
        """启动所有Celery服务"""
        print("=" * 50)
        print("    🎯 Celery Services Manager")
        print("=" * 50)
        
        # 检查环境
        if not self.check_python_environment():
            return False
        
        print("\n📋 开始启动服务...")
        
        # 启动Worker
        worker_cmd = [
            sys.executable, '-m', 'celery',
            '-A', 'app.task.celery',
            'worker',
            '-l', 'info',
            '-P', 'gevent' if os.name == 'nt' else 'prefork',
            '-c', '100'
        ]
        
        worker_process = self.start_process("Celery Worker", worker_cmd)
        if not worker_process:
            return False
        
        # 等待Worker启动
        time.sleep(3)
        
        # 启动Beat
        beat_cmd = [
            sys.executable, '-m', 'celery',
            '-A', 'app.task.celery',
            'beat',
            '-l', 'info'
        ]
        
        beat_process = self.start_process("Celery Beat", beat_cmd)
        if not beat_process:
            return False
        
        # 等待Beat启动
        time.sleep(2)
        
        # 启动Flower
        print("\n🌸 启动 Celery Flower...")
        print("   监控界面: http://localhost:8555")
        print("   用户名: admin, 密码: 123456")
        print("\n⏸️  按 Ctrl+C 停止所有服务\n")
        
        flower_cmd = [
            sys.executable, '-m', 'celery',
            '-A', 'app.task.celery',
            'flower',
            '--port=8555',
            '--basic-auth=admin:123456'
        ]
        
        try:
            # Flower在前台运行
            subprocess.run(flower_cmd, cwd=self.base_dir, check=True)
        except KeyboardInterrupt:
            print("\n🛑 接收到停止信号...")
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Flower运行出错: {e}")
        
        return True
    
    def stop_all_services(self):
        """停止所有服务"""
        if not self.processes:
            return
        
        print("\n🛑 正在停止所有Celery服务...")
        
        for service in self.processes:
            try:
                process = service['process']
                name = service['name']
                
                if process.poll() is None:  # 进程仍在运行
                    print(f"   停止 {name} (PID: {process.pid})...")
                    
                    if os.name == 'nt':
                        # Windows下终止进程组
                        subprocess.run([
                            'taskkill', '/F', '/T', '/PID', str(process.pid)
                        ], capture_output=True)
                    else:
                        # Unix系统下发送SIGTERM
                        process.terminate()
                        
                    # 等待进程结束
                    try:
                        process.wait(timeout=5)
                        print(f"   ✅ {name} 已停止")
                    except subprocess.TimeoutExpired:
                        # 强制杀死进程
                        if os.name == 'nt':
                            subprocess.run([
                                'taskkill', '/F', '/T', '/PID', str(process.pid)
                            ], capture_output=True)
                        else:
                            process.kill()
                        print(f"   🔥 {name} 已强制停止")
                else:
                    print(f"   ⚪ {name} 已经停止")
                    
            except Exception as e:
                print(f"   ❌ 停止 {service['name']} 时出错: {e}")
        
        self.processes.clear()
        print("🎉 所有服务已停止")


def main():
    """主函数"""
    manager = CeleryManager()
    
    # 注册退出处理
    atexit.register(manager.stop_all_services)
    
    # 信号处理
    def signal_handler(signum, frame):
        print(f"\n接收到信号 {signum}")
        manager.stop_all_services()
        sys.exit(0)
    
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, signal_handler)
    
    try:
        success = manager.start_all_services()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 用户中断程序")
    except Exception as e:
        print(f"\n💥 程序异常: {e}")
        sys.exit(1)
    finally:
        manager.stop_all_services()


if __name__ == "__main__":
    main() 