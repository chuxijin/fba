#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flet 应用打包脚本
支持打包为 Windows EXE、Android APK/AAB、iOS IPA、Web 应用
"""
import os
import subprocess
import sys
# 项目配置
PROJECT_CONFIG = {
    'main_file': 'my_app/main.py',
    'project_name': 'bili_manager',
    'product_name': 'BiliManager',  # 避免中文，打包后可以手动改名
    'org': 'com.bili.manager',
    'description': 'Bilibili Account Manager',  # 避免中文
    'version': '1.0.0',
    'company': 'BiliManager',
    # 可选：图标路径（需要自己准备）
    'icon_windows': 'my_app/assets/icon.ico',
    'icon_android': 'my_app/assets/icon.png',
    'icon_ios': 'my_app/assets/icon.png',
    # 启动画面颜色
    'splash_color': '#2196F3',
    'splash_dark_color': '#1565C0',
}


def print_banner():
    """打印横幅"""
    print('=' * 60)
    print('           Flet 应用打包工具')
    print('=' * 60)
    print()


def print_menu():
    """打印菜单"""
    print('请选择要打包的平台：')
    print()
    print('  [1] Windows EXE  - 桌面应用程序')
    print('  [2] Android APK  - 安卓安装包')
    print('  [3] Android AAB  - Google Play 上架格式')
    print('  [4] iOS IPA      - 苹果应用 (需要 macOS)')
    print('  [5] Web          - 网页应用')
    print('  [6] 全部打包      - 打包所有平台')
    print('  [0] 退出')
    print()


def check_flutter():
    """检查 Flutter 是否安装（支持 fvm）"""
    # 先检查 fvm flutter
    try:
        result = subprocess.run(['fvm', 'flutter', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            return 'fvm'
    except FileNotFoundError:
        pass

    # 再检查直接安装的 flutter
    try:
        result = subprocess.run(['flutter', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            return 'direct'
    except FileNotFoundError:
        pass

    return None


def get_flutter_cmd():
    """获取 Flutter 命令前缀"""
    flutter_type = check_flutter()
    if flutter_type == 'fvm':
        return ['fvm', 'flutter']
    elif flutter_type == 'direct':
        return ['flutter']
    return None


def check_pyinstaller():
    """检查 PyInstaller 是否安装"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def build_windows():
    """打包 Windows EXE"""
    print('\n' + '=' * 60)
    print('🖥️  开始打包 Windows EXE...')
    print('=' * 60)

    if not check_pyinstaller():
        print('⚠️  未安装 PyInstaller，正在安装...')
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])

    cmd = [
        'flet', 'pack', PROJECT_CONFIG['main_file'],
        '--name', PROJECT_CONFIG['product_name'],
        '--product-name', PROJECT_CONFIG['product_name'],
        '--product-version', PROJECT_CONFIG['version'],
        '--file-version', PROJECT_CONFIG['version'],
        '--company-name', PROJECT_CONFIG['company'],
        # 隐藏导入 - 解决 bilibili_api 模块问题
        '--hidden-import', 'bilibili_api.clients',
        '--hidden-import', 'bilibili_api.clients.HTTPXClient',
        '--hidden-import', 'bilibili_api.clients.AiohttpClient',
        '--hidden-import', 'httpx',
        '--hidden-import', 'aiohttp',
    ]

    # 添加图标（如果存在）
    if os.path.exists(PROJECT_CONFIG['icon_windows']):
        cmd.extend(['--icon', PROJECT_CONFIG['icon_windows']])

    # 添加配置文件目录
    config_dir = 'my_app/config'
    if os.path.exists(config_dir):
        cmd.extend(['--add-data', f'{config_dir};my_app/config'])

    print(f'执行命令: {" ".join(cmd)}')
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print('\n✅ Windows EXE 打包成功！')
        print(f'📁 输出目录: dist/{PROJECT_CONFIG["product_name"]}.exe')
    else:
        print('\n❌ Windows EXE 打包失败！')

    return result.returncode == 0


def build_android_apk():
    """打包 Android APK"""
    print('\n' + '=' * 60)
    print('📱 开始打包 Android APK...')
    print('=' * 60)

    flutter_type = check_flutter()
    if not flutter_type:
        print('❌ 未安装 Flutter SDK！')
        print('请访问 https://flutter.dev/docs/get-started/install 安装')
        return False

    if flutter_type == 'fvm':
        print('✅ 检测到 FVM，使用 fvm flutter')

    cmd = [
        'flet', 'build', 'apk',
        '--module-name', 'my_app.main',  # 使用 Python 模块路径，不是文件路径
        '--project', PROJECT_CONFIG['project_name'],
        '--product', PROJECT_CONFIG['product_name'],
        '--org', PROJECT_CONFIG['org'],
        '--description', PROJECT_CONFIG['description'],
        '--build-version', PROJECT_CONFIG['version'],
        '--splash-color', PROJECT_CONFIG['splash_color'],
        '--splash-dark-color', PROJECT_CONFIG['splash_dark_color'],
    ]

    # 如果使用 fvm，需要设置环境变量让 flet 使用 fvm 的 flutter
    env = os.environ.copy()
    if flutter_type == 'fvm':
        # 获取 fvm flutter 路径
        result = subprocess.run(['fvm', 'which'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            fvm_flutter_path = result.stdout.strip()
            flutter_dir = os.path.dirname(os.path.dirname(fvm_flutter_path))
            env['FLUTTER_ROOT'] = flutter_dir
            print(f'📂 Flutter 路径: {flutter_dir}')

    # 设置输出编码为 UTF-8
    env['PYTHONIOENCODING'] = 'utf-8'

    print(f'执行命令: {" ".join(cmd)}')
    result = subprocess.run(cmd, env=env, encoding='utf-8', errors='ignore')

    if result.returncode == 0:
        print('\n✅ Android APK 打包成功！')
        print(f'📁 输出目录: build/apk/')
    else:
        print('\n❌ Android APK 打包失败！')

    return result.returncode == 0


def build_android_aab():
    """打包 Android AAB"""
    print('\n' + '=' * 60)
    print('📱 开始打包 Android AAB (Google Play)...')
    print('=' * 60)

    flutter_type = check_flutter()
    if not flutter_type:
        print('❌ 未安装 Flutter SDK！')
        print('请访问 https://flutter.dev/docs/get-started/install 安装')
        return False

    if flutter_type == 'fvm':
        print('✅ 检测到 FVM，使用 fvm flutter')

    cmd = [
        'flet', 'build', 'aab',
        '--module-name', 'my_app.main',  # 使用 Python 模块路径
        '--project', PROJECT_CONFIG['project_name'],
        '--product', PROJECT_CONFIG['product_name'],
        '--org', PROJECT_CONFIG['org'],
        '--description', PROJECT_CONFIG['description'],
        '--build-version', PROJECT_CONFIG['version'],
        '--splash-color', PROJECT_CONFIG['splash_color'],
        '--splash-dark-color', PROJECT_CONFIG['splash_dark_color'],
    ]

    # 如果使用 fvm，设置环境变量
    env = os.environ.copy()
    if flutter_type == 'fvm':
        result = subprocess.run(['fvm', 'which'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            fvm_flutter_path = result.stdout.strip()
            flutter_dir = os.path.dirname(os.path.dirname(fvm_flutter_path))
            env['FLUTTER_ROOT'] = flutter_dir

    env['PYTHONIOENCODING'] = 'utf-8'

    print(f'执行命令: {" ".join(cmd)}')
    result = subprocess.run(cmd, env=env, encoding='utf-8', errors='ignore')

    if result.returncode == 0:
        print('\n✅ Android AAB 打包成功！')
        print(f'📁 输出目录: build/aab/')
    else:
        print('\n❌ Android AAB 打包失败！')

    return result.returncode == 0


def build_ios():
    """打包 iOS IPA"""
    print('\n' + '=' * 60)
    print('🍎 开始打包 iOS IPA...')
    print('=' * 60)

    if sys.platform != 'darwin':
        print('❌ iOS 打包需要在 macOS 上进行！')
        return False

    flutter_type = check_flutter()
    if not flutter_type:
        print('❌ 未安装 Flutter SDK！')
        print('请访问 https://flutter.dev/docs/get-started/install 安装')
        return False

    if flutter_type == 'fvm':
        print('✅ 检测到 FVM，使用 fvm flutter')

    cmd = [
        'flet', 'build', 'ipa',
        '--module-name', 'my_app.main',  # 使用 Python 模块路径
        '--project', PROJECT_CONFIG['project_name'],
        '--product', PROJECT_CONFIG['product_name'],
        '--org', PROJECT_CONFIG['org'],
        '--description', PROJECT_CONFIG['description'],
        '--build-version', PROJECT_CONFIG['version'],
    ]

    # 如果使用 fvm，设置环境变量
    env = os.environ.copy()
    if flutter_type == 'fvm':
        result = subprocess.run(['fvm', 'which'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            fvm_flutter_path = result.stdout.strip()
            flutter_dir = os.path.dirname(os.path.dirname(fvm_flutter_path))
            env['FLUTTER_ROOT'] = flutter_dir

    env['PYTHONIOENCODING'] = 'utf-8'

    print(f'执行命令: {" ".join(cmd)}')
    result = subprocess.run(cmd, env=env, encoding='utf-8', errors='ignore')

    if result.returncode == 0:
        print('\n✅ iOS IPA 打包成功！')
        print(f'📁 输出目录: build/ipa/')
    else:
        print('\n❌ iOS IPA 打包失败！')

    return result.returncode == 0


def build_web():
    """打包 Web 应用"""
    print('\n' + '=' * 60)
    print('🌐 开始打包 Web 应用...')
    print('=' * 60)

    flutter_type = check_flutter()
    if not flutter_type:
        print('❌ 未安装 Flutter SDK！')
        print('请访问 https://flutter.dev/docs/get-started/install 安装')
        return False

    if flutter_type == 'fvm':
        print('✅ 检测到 FVM，使用 fvm flutter')

    cmd = [
        'flet', 'build', 'web',
        '--module-name', 'my_app.main',  # 使用 Python 模块路径
        '--project', PROJECT_CONFIG['project_name'],
    ]

    # 如果使用 fvm，设置环境变量
    env = os.environ.copy()
    if flutter_type == 'fvm':
        result = subprocess.run(['fvm', 'which'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            fvm_flutter_path = result.stdout.strip()
            flutter_dir = os.path.dirname(os.path.dirname(fvm_flutter_path))
            env['FLUTTER_ROOT'] = flutter_dir

    env['PYTHONIOENCODING'] = 'utf-8'

    print(f'执行命令: {" ".join(cmd)}')
    result = subprocess.run(cmd, env=env, encoding='utf-8', errors='ignore')

    if result.returncode == 0:
        print('\n✅ Web 应用打包成功！')
        print(f'📁 输出目录: build/web/')
        print('💡 可以部署到任何 Web 服务器')
    else:
        print('\n❌ Web 应用打包失败！')

    return result.returncode == 0


def build_all():
    """打包所有平台"""
    print('\n开始打包所有平台...')
    results = {}

    results['Windows EXE'] = build_windows()
    results['Android APK'] = build_android_apk()
    results['Android AAB'] = build_android_aab()
    results['Web'] = build_web()

    if sys.platform == 'darwin':
        results['iOS IPA'] = build_ios()

    print('\n' + '=' * 60)
    print('打包结果汇总')
    print('=' * 60)
    for platform, success in results.items():
        status = '✅ 成功' if success else '❌ 失败'
        print(f'  {platform}: {status}')


def main():
    """主函数"""
    print_banner()

    while True:
        print_menu()
        choice = input('请输入选项 [0-6]: ').strip()

        if choice == '0':
            print('\n👋 再见！')
            break
        elif choice == '1':
            build_windows()
        elif choice == '2':
            build_android_apk()
        elif choice == '3':
            build_android_aab()
        elif choice == '4':
            build_ios()
        elif choice == '5':
            build_web()
        elif choice == '6':
            build_all()
        else:
            print('\n⚠️  无效选项，请重新输入！')

        print('\n' + '-' * 60 + '\n')
        input('按 Enter 键继续...')
        print()


if __name__ == '__main__':
    main()
