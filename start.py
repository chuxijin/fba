#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FastAPI Best Architecture 启动脚本
作者: null
功能: 通过命令行参数控制启动 FastAPI、Celery 或两者
"""

import os
import sys
import time
import signal
import argparse
import subprocess
import threading
from pathlib import Path

# Windows编码兼容性处理
if os.name == 'nt':
    try:
        # 设置控制台编码为UTF-8
        os.system('chcp 65001 >nul 2>&1')
        # 设置环境变量
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    except:
        pass


class ServiceManager:
    """服务管理器"""
    
    def __init__(self):
        self.fastapi_process = None
        self.celery_process = None
        self.project_root = Path(__file__).parent.absolute()
        self.backend_dir = self.project_root / "backend"
        
        # 设置 PYTHONPATH
        current_pythonpath = os.environ.get('PYTHONPATH', '')
        if current_pythonpath:
            os.environ['PYTHONPATH'] = f"{self.project_root};{current_pythonpath}"
        else:
            os.environ['PYTHONPATH'] = str(self.project_root)
    
    def check_environment(self):
        """检查运行环境"""
        print("[检查] 运行环境...")
        
        # 检查是否在正确的目录
        if not (self.backend_dir / "main.py").exists():
            print("[错误] 未找到 backend/main.py 文件")
            print("   请确保在项目根目录运行此脚本")
            sys.exit(1)
        
        # 检查 Python 环境
        try:
            result = subprocess.run([sys.executable, "--version"], 
                                  capture_output=True, text=True, check=True)
            print(f"[成功] Python 版本: {result.stdout.strip()}")
        except subprocess.CalledProcessError:
            print("[错误] Python 环境异常")
            sys.exit(1)
        
        # 检查 FastAPI CLI
        try:
            subprocess.run(["fastapi", "--version"], 
                          capture_output=True, check=True)
            print("[成功] FastAPI CLI 已安装")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("[警告] FastAPI CLI 未安装，将使用 uvicorn 启动")
        
        print(f"[成功] 项目根目录: {self.project_root}")
        print(f"[成功] PYTHONPATH: {os.environ.get('PYTHONPATH')}")
        print()
    
    def start_fastapi(self):
        """启动 FastAPI 服务"""
        print("[启动] FastAPI 开发服务器...")
        
        try:
            # 优先使用 fastapi dev，如果失败则使用 uvicorn
            try:
                self.fastapi_process = subprocess.Popen(
                    ["fastapi", "dev", "main.py"],
                    cwd=self.backend_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='replace'
                )
            except FileNotFoundError:
                print("   使用 uvicorn 启动...")
                self.fastapi_process = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
                    cwd=self.backend_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='replace'
                )
            
            print("[成功] FastAPI 服务已启动")
            
            # 在后台线程中输出日志
            def output_fastapi_logs():
                try:
                    for line in iter(self.fastapi_process.stdout.readline, ''):
                        if line.strip():
                            print(f"[FastAPI] {line.strip()}")
                except Exception as e:
                    print(f"[错误] FastAPI 日志输出异常: {e}")
                        
            threading.Thread(target=output_fastapi_logs, daemon=True).start()
            
        except Exception as e:
            print(f"[错误] FastAPI 启动失败: {e}")
            return False
        
        return True
    
    def start_celery(self):
        """启动 Celery 服务"""
        print("[启动] Celery 工作进程...")
        
        try:
            self.celery_process = subprocess.Popen(
                [sys.executable, "start_celery.py"],
                cwd=self.backend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace'
            )
            
            print("[成功] Celery 服务已启动")
            
            # 在后台线程中输出日志
            def output_celery_logs():
                try:
                    for line in iter(self.celery_process.stdout.readline, ''):
                        if line.strip():
                            print(f"[Celery] {line.strip()}")
                except Exception as e:
                    print(f"[错误] Celery 日志输出异常: {e}")
                        
            threading.Thread(target=output_celery_logs, daemon=True).start()
            
        except Exception as e:
            print(f"[错误] Celery 启动失败: {e}")
            return False
        
        return True
    
    def stop_services(self):
        """停止所有服务"""
        print("\n[停止] 正在停止服务...")
        
        if self.celery_process:
            print("   停止 Celery...")
            try:
                self.celery_process.terminate()
                self.celery_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.celery_process.kill()
            except Exception as e:
                print(f"   停止 Celery 时出错: {e}")
        
        if self.fastapi_process:
            print("   停止 FastAPI...")
            try:
                self.fastapi_process.terminate()
                self.fastapi_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.fastapi_process.kill()
            except Exception as e:
                print(f"   停止 FastAPI 时出错: {e}")
        
        print("[完成] 所有服务已停止")
    
    def run_fastapi_only(self):
        """仅运行 FastAPI"""
        print("[模式] 仅 FastAPI")
        self.check_environment()
        
        if self.start_fastapi():
            try:
                self.fastapi_process.wait()
            except KeyboardInterrupt:
                pass
            finally:
                self.stop_services()
    
    def run_celery_only(self):
        """仅运行 Celery"""
        print("[模式] 仅 Celery")
        self.check_environment()
        
        if self.start_celery():
            try:
                self.celery_process.wait()
            except KeyboardInterrupt:
                pass
            finally:
                self.stop_services()
    
    def run_all(self):
        """运行 FastAPI + Celery"""
        print("[模式] FastAPI + Celery")
        self.check_environment()
        
        # 先启动 Celery
        celery_started = self.start_celery()
        if celery_started:
            time.sleep(2)  # 等待 Celery 完全启动
        
        # 再启动 FastAPI
        fastapi_started = self.start_fastapi()
        
        if not (celery_started or fastapi_started):
            print("[错误] 所有服务启动失败")
            return
        
        print("\n[完成] 服务启动完成!")
        print("   FastAPI: http://localhost:8000")
        print("   API 文档: http://localhost:8000/docs")
        print("   Flower 监控: http://localhost:8555")
        print("   按 Ctrl+C 停止服务")
        print()
        
        try:
            # 等待任一进程结束
            while True:
                if self.fastapi_process and self.fastapi_process.poll() is not None:
                    print("FastAPI 进程已结束")
                    break
                if self.celery_process and self.celery_process.poll() is not None:
                    print("Celery 进程已结束")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n收到停止信号...")
        finally:
            self.stop_services()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="FastAPI Best Architecture 启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python start.py -all          # 启动 FastAPI + Celery (默认)
  python start.py -fastapi      # 仅启动 FastAPI
  python start.py -celery       # 仅启动 Celery
  python start.py --help        # 显示帮助信息
        """
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-all', '--all', action='store_true', 
                      help='启动 FastAPI + Celery (默认)')
    group.add_argument('-fastapi', '--fastapi', action='store_true',
                      help='仅启动 FastAPI 开发服务器')
    group.add_argument('-celery', '--celery', action='store_true',
                      help='仅启动 Celery 工作进程')
    
    args = parser.parse_args()
    
    # 创建服务管理器
    manager = ServiceManager()
    
    # 设置信号处理
    def signal_handler(signum, frame):
        print(f"\n收到信号 {signum}，正在停止服务...")
        manager.stop_services()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 50)
    print("FastAPI Best Architecture 启动脚本")
    print("   作者: null")
    print("=" * 50)
    
    # 根据参数启动相应服务
    if args.fastapi:
        manager.run_fastapi_only()
    elif args.celery:
        manager.run_celery_only()
    else:
        # 默认启动所有服务
        manager.run_all()


if __name__ == "__main__":
    main() 