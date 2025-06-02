#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件同步服务测试工具 - clientTest.py

这是一个专门用于测试文件同步服务的工具，提供了以下测试功能：

## 文件同步服务测试（41-46）
- 41. 测试同步方法解析 - 测试增量、完全、覆写同步方法的解析
- 42. 测试递归速度解析 - 测试正常、慢速、快速递归速度的解析
- 43. 测试比较逻辑 - 支持交互式路径选择，测试文件比较算法
- 44. 测试同步操作应用 - 测试实际的文件传输和删除操作
- 45. 创建测试同步配置 - 交互式创建同步配置，支持路径选择
- 46. 执行完整同步测试 - 端到端的完整同步流程测试

## 综合测试（94）
- 94. 运行文件同步服务测试套件

## 新特性
✨ 智能路径选择：在测试文件同步功能时，可以通过文件浏览器的方式选择路径，
   无需手动输入，支持：
   - 分享文件路径浏览
   - 本地磁盘路径浏览
   - 上下级目录导航
   - 手动路径输入作为备选

## 使用方法
1. 直接运行测试功能，系统会自动创建模拟客户端
2. 建议按顺序执行41->45->46

## 依赖配置
需要在 TEST_CONFIGS 中配置正确的网盘认证信息：
- 百度网盘：BDUSS, STOKEN, cookies
- 夸克网盘：cookie

运行方式：python clientTest.py
"""
import sys
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入核心模块
from backend.app.coulddrive.service.filesync_service import (
    FileSyncService,
    file_sync_service,
    perform_comparison_logic,
    apply_comparison_operations
)
from backend.app.coulddrive.schema.enum import DriveType, RecursionSpeed, SyncMethod
from backend.app.coulddrive.schema.file import (
    ShareSourceDefinition,
    DiskTargetDefinition,
    ExclusionRuleDefinition,
    RenameRuleDefinition
)
from backend.app.coulddrive.schema.filesync import GetSyncConfigDetail
from backend.app.coulddrive.service.yp_service import get_drive_manager

# 测试配置
TEST_CONFIGS = {
    DriveType.BAIDU_DRIVE: {
        "bduss": "0ZtMFhnd1d4YXJjUENPdHJ5Sk1HaHY4QVdqZWlyU2o1LUhNU1pXVWhuTFFwZmhuRVFBQUFBJCQAAAAAAAAAAAEAAABbzI2fvfCz~urYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAANAY0WfQGNFnM",
        "stoken": "7e82f475423e5c1a35e63a972b9cb67f0c2ce6418468fdccc002d695aadcc032",
        "cookies": {
            "BDUSS": "0ZtMFhnd1d4YXJjUENPdHJ5Sk1HaHY4QVdqZWlyU2o1LUhNU1pXVWhuTFFwZmhuRVFBQUFBJCQAAAAAAAAAAAEAAABbzI2fvfCz~urYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAANAY0WfQGNFnM",
            "STOKEN": "7e82f475423e5c1a35e63a972b9cb67f0c2ce6418468fdccc002d695aadcc032"
        }
    },
    DriveType.QUARK_DRIVE: {
        "cookie": "__pus=test_pus_value; __puus=test_puus_value"
    }
}

# 全局变量
sync_service: FileSyncService = file_sync_service
current_drive_type: DriveType = DriveType.BAIDU_DRIVE  # 默认使用百度网盘

def print_menu():
    """显示主菜单"""
    print("\n" + "="*60)
    print("🚀 文件同步服务测试工具 - 交互式菜单")
    print("="*60)
    print("【测试配置】")
    print("  1. 选择网盘类型（当前: {}）".format(current_drive_type.value))
    print()
    print("【文件同步服务测试】")
    print("  41. 测试同步方法解析")
    print("  42. 测试递归速度解析")
    print("  43. 测试比较逻辑")
    print("  44. 测试同步操作应用")
    print("  45. 创建测试同步配置")
    print("  46. 执行完整同步测试")
    print("  47. 使用真实配置执行同步测试")
    print()
    print("【综合测试】")
    print("  94. 运行文件同步服务测试套件")
    print()
    print("  0. 退出程序")
    print("="*60)

def select_drive_type():
    """选择网盘类型"""
    global current_drive_type
    
    print("\n请选择网盘类型:")
    print("  1. 百度网盘")
    print("  2. 夸克网盘")
    
    choice = input("请选择 (1-2): ").strip()
    if choice == "1":
        current_drive_type = DriveType.BAIDU_DRIVE
        print("✅ 已选择百度网盘")
    elif choice == "2":
        current_drive_type = DriveType.QUARK_DRIVE
        print("✅ 已选择夸克网盘")
    else:
        print("❌ 无效选择，保持当前配置")

async def select_share_source() -> tuple[str, str]:
    """让用户选择分享源"""
    print("\n🔗 选择分享源:")
    print("  1. 好友分享 (friend)")
    print("  2. 群组分享 (group)")
    
    choice = input("请选择分享类型 (1-2): ").strip()
    source_type_map = {"1": "friend", "2": "group"}
    source_type = source_type_map.get(choice, "friend")
    
    if source_type == "friend":
        print("\n请输入好友信息:")
        source_id = input("好友ID (默认: test_friend_123): ").strip()
        if not source_id:
            source_id = "test_friend_123"
    else:  # group
        print("\n请输入群组信息:")
        source_id = input("群组ID (默认: test_group_456): ").strip()
        if not source_id:
            source_id = "test_group_456"
    
    return source_type, source_id

def test_sync_method_parsing():
    """测试同步方法解析"""
    print("\n📝 测试同步方法解析:")
    
    test_methods = [
        "incremental", "full", "overwrite",
        "INCREMENTAL", "FULL", "OVERWRITE",
        "invalid_method", "", None
    ]
    
    for method in test_methods:
        try:
            result = sync_service._parse_sync_method(method)
            print(f"   '{method}' -> '{result}'")
        except Exception as e:
            print(f"   '{method}' -> 错误: {e}")

def test_recursion_speed_parsing():
    """测试递归速度解析"""
    print("\n⚡ 测试递归速度解析:")
    
    test_speeds = [0, 1, 2, -1, 5, None]
    
    for speed in test_speeds:
        try:
            result = sync_service._parse_recursion_speed(speed)
            print(f"   {speed} -> {result.value} ({result.name})")
        except Exception as e:
            print(f"   {speed} -> 错误: {e}")

async def test_comparison_logic():
    """测试比较逻辑"""
    print("\n🔍 测试比较逻辑:")
    
    # 选择分享源
    source_type, source_id = await select_share_source()
    
    # 手动输入路径（注意：分享内部路径不能为根路径）
    print(f"\n输入分享源路径 ({source_type}: {source_id}):")
    print("注意：分享内部路径不能为根路径 '/'，请输入具体的子路径")
    source_path = input("分享源路径 (默认: /共享文件夹): ").strip()
    if not source_path:
        source_path = "/共享文件夹"
    
    print("\n输入目标路径:")
    target_path = input("目标路径 (默认: /测试同步): ").strip()
    if not target_path:
        target_path = "/测试同步"
    
    try:
        # 构建源定义和目标定义
        source_definition = ShareSourceDefinition(
            source_type=source_type,
            source_id=source_id,
            file_path=source_path,
            ext_params={}
        )
        
        target_definition = DiskTargetDefinition(
            file_path=target_path,
            file_id=""
        )
        
        # 获取网盘管理器
        drive_manager = get_drive_manager()
        
        # 构建认证令牌
        config = TEST_CONFIGS[current_drive_type]
        if current_drive_type == DriveType.BAIDU_DRIVE:
            # 直接传递 cookies 字符串，让底层 api.py 自己解析
            cookies = config.get("cookies", {})
            if isinstance(cookies, dict):
                # 将字典转换为cookie字符串
                cookie_pairs = []
                for key, value in cookies.items():
                    cookie_pairs.append(f"{key}={value}")
                x_token = "; ".join(cookie_pairs)
            else:
                x_token = str(cookies)
        else:
            x_token = config.get("cookie", "")
        
        # 映射网盘类型
        drive_type_str = current_drive_type.value
        
        print("   开始执行比较逻辑...")
        print(f"   源: {source_type}:{source_id}:{source_path}")
        print(f"   目标: {target_path}")
        
        # 执行比较逻辑
        comparison_result = await perform_comparison_logic(
            drive_manager=drive_manager,
            x_token=x_token,
            source_definition=source_definition,
            target_definition=target_definition,
            recursive=True,
            recursion_speed=RecursionSpeed.NORMAL,
            comparison_mode="incremental",
            exclude_rules_def=None,
            rename_rules_def=None,
            drive_type_str=drive_type_str
        )
        
        print("✅ 比较逻辑执行成功:")
        print(f"   网盘类型: {comparison_result.drive_type}")
        print(f"   源文件数量: {comparison_result.source_list_num}")
        print(f"   目标文件数量: {comparison_result.target_list_num}")
        print(f"   源列表耗时: {comparison_result.source_list_time:.2f}秒")
        print(f"   目标列表耗时: {comparison_result.target_list_time:.2f}秒")
        print(f"   需要添加: {len(comparison_result.to_add)} 个文件")
        print(f"   需要删除: {len(comparison_result.to_delete_from_target)} 个文件")
        print(f"   需要更新: {len(comparison_result.to_update_in_target)} 个文件")
        print(f"   需要重命名: {len(comparison_result.to_rename_in_target)} 个文件")
        
        # 显示具体的操作项目
        if comparison_result.to_add:
            print("\n   需要添加的文件:")
            for i, item in enumerate(comparison_result.to_add[:5]):  # 只显示前5个
                print(f"     {i+1}. {item.file_name} ({item.file_path})")
            if len(comparison_result.to_add) > 5:
                print(f"     ... 还有 {len(comparison_result.to_add) - 5} 个文件")
        
        if comparison_result.to_delete_from_target:
            print("\n   需要删除的文件:")
            for i, item in enumerate(comparison_result.to_delete_from_target[:5]):  # 只显示前5个
                print(f"     {i+1}. {item.file_name} ({item.file_path})")
            if len(comparison_result.to_delete_from_target) > 5:
                print(f"     ... 还有 {len(comparison_result.to_delete_from_target) - 5} 个文件")
        
        return comparison_result
        
    except Exception as e:
        print(f"❌ 比较逻辑测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_sync_operations(comparison_result=None):
    """测试同步操作应用"""
    print("\n🔧 测试同步操作应用:")
    
    if not comparison_result:
        print("   没有提供比较结果，将执行比较逻辑...")
        comparison_result = await test_comparison_logic()
        if not comparison_result:
            return
    
    # 确认是否执行操作
    total_operations = (len(comparison_result.to_add) + 
                       len(comparison_result.to_delete_from_target) + 
                       len(comparison_result.to_update_in_target) + 
                       len(comparison_result.to_rename_in_target))
    
    if total_operations == 0:
        print("   没有需要执行的操作")
        return
    
    confirm = input(f"⚠️  将执行 {total_operations} 个操作，确认继续? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ 操作已取消")
        return
    
    try:
        # 获取网盘管理器
        drive_manager = get_drive_manager()
        
        # 构建认证令牌
        config = TEST_CONFIGS[current_drive_type]
        if current_drive_type == DriveType.BAIDU_DRIVE:
            # 直接传递 cookies 字符串，让底层 api.py 自己解析
            cookies = config.get("cookies", {})
            if isinstance(cookies, dict):
                # 将字典转换为cookie字符串
                cookie_pairs = []
                for key, value in cookies.items():
                    cookie_pairs.append(f"{key}={value}")
                x_token = "; ".join(cookie_pairs)
            else:
                x_token = str(cookies)
        else:
            x_token = config.get("cookie", "")
        
        # 映射网盘类型
        drive_type_str = current_drive_type.value
        
        print("   开始执行同步操作...")
        
        # 应用同步操作
        operation_results = await apply_comparison_operations(
            drive_manager=drive_manager,
            x_token=x_token,
            comparison_result=comparison_result,
            drive_type_str=drive_type_str
        )
        
        print("✅ 同步操作执行完成:")
        
        # 显示添加操作结果
        add_results = operation_results.get("add", {})
        add_succeeded = add_results.get("succeeded", [])
        add_failed = add_results.get("failed", [])
        
        print(f"   添加操作: {len(add_succeeded)} 成功, {len(add_failed)} 失败")
        if add_succeeded:
            print("     成功添加:")
            for i, result in enumerate(add_succeeded[:3]):  # 只显示前3个
                print(f"       {i+1}. {result}")
            if len(add_succeeded) > 3:
                print(f"       ... 还有 {len(add_succeeded) - 3} 个")
        
        if add_failed:
            print("     添加失败:")
            for i, result in enumerate(add_failed[:3]):  # 只显示前3个
                print(f"       {i+1}. {result}")
            if len(add_failed) > 3:
                print(f"       ... 还有 {len(add_failed) - 3} 个")
        
        # 显示删除操作结果
        delete_results = operation_results.get("delete", {})
        delete_succeeded = delete_results.get("succeeded", [])
        delete_failed = delete_results.get("failed", [])
        
        print(f"   删除操作: {len(delete_succeeded)} 成功, {len(delete_failed)} 失败")
        if delete_succeeded:
            print("     成功删除:")
            for i, result in enumerate(delete_succeeded[:3]):  # 只显示前3个
                print(f"       {i+1}. {result}")
            if len(delete_succeeded) > 3:
                print(f"       ... 还有 {len(delete_succeeded) - 3} 个")
        
        if delete_failed:
            print("     删除失败:")
            for i, result in enumerate(delete_failed[:3]):  # 只显示前3个
                print(f"       {i+1}. {result}")
            if len(delete_failed) > 3:
                print(f"       ... 还有 {len(delete_failed) - 3} 个")
        
        return operation_results
        
    except Exception as e:
        print(f"❌ 同步操作测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

async def create_test_sync_config():
    """创建测试同步配置"""
    print("\n⚙️ 创建测试同步配置:")
    
    # 获取用户输入
    account_id = input("请输入账户ID (默认: 1): ").strip()
    if not account_id:
        account_id = 1
    else:
        try:
            account_id = int(account_id)
        except ValueError:
            account_id = 1
    
    remark = input("请输入备注 (默认: 测试同步任务): ").strip()
    if not remark:
        remark = "测试同步任务"
    
    # 选择分享源
    source_type, source_id = await select_share_source()
    
    # 输入源路径（注意：分享内部路径不能为根路径）
    print("\n输入源路径:")
    print("注意：分享内部路径不能为根路径 '/'，请输入具体的子路径")
    src_path = input("请输入源路径 (默认: /共享文件夹): ").strip()
    if not src_path:
        src_path = "/共享文件夹"
    
    # 输入目标路径
    dst_path = input("请输入目标路径 (默认: /测试同步): ").strip()
    if not dst_path:
        dst_path = "/测试同步"
    
    # 选择同步方法
    print("\n请选择同步方法:")
    print("  1. incremental (增量同步)")
    print("  2. full (完全同步)")
    print("  3. overwrite (覆写同步)")
    
    method_choice = input("请选择 (1-3, 默认: 1): ").strip()
    method_map = {"1": SyncMethod.INCREMENTAL, "2": SyncMethod.FULL, "3": SyncMethod.OVERWRITE}
    method = method_map.get(method_choice, SyncMethod.INCREMENTAL)
    
    # 选择递归速度
    print("\n请选择递归速度:")
    print("  0. normal (正常)")
    print("  1. slow (慢速)")
    print("  2. fast (快速)")
    
    speed_choice = input("请选择 (0-2, 默认: 0): ").strip()
    speed_map = {"0": 0, "1": 1, "2": 2}
    speed = speed_map.get(speed_choice, 0)
    
    # 创建同步配置
    import json
    from datetime import datetime
    
    # 源元数据
    src_meta = {
        "source_type": source_type,
        "source_id": source_id,
        "ext_params": {}
    }
    
    # 目标元数据
    dst_meta = {
        "file_id": ""
    }
    
    # 创建 GetSyncConfigDetail 对象（注意：这是测试用的模拟配置，不会保存到数据库）
    sync_config = GetSyncConfigDetail(
        id=999,  # 测试ID（模拟ID，实际使用时会从数据库获取真实ID）
        user_id=1,
        account_id=account_id,
        remark=remark,
        type=current_drive_type,  # 添加必需的 type 字段
        src_path=src_path,
        dst_path=dst_path,
        src_meta=json.dumps(src_meta),
        dst_meta=json.dumps(dst_meta),
        method=method,
        speed=speed,
        enable=True,
        exclude=None,
        rename=None,
        created_time=datetime.now(),
        updated_time=datetime.now(),
        created_by=1,  # 添加必需的 created_by 字段
        updated_by=1   # 添加必需的 updated_by 字段
    )
    
    print("✅ 测试同步配置创建成功:")
    print(f"   ID: {sync_config.id}")
    print(f"   账户ID: {sync_config.account_id}")
    print(f"   备注: {sync_config.remark}")
    print(f"   源类型: {source_type}")
    print(f"   源ID: {source_id}")
    print(f"   源路径: {sync_config.src_path}")
    print(f"   目标路径: {sync_config.dst_path}")
    print(f"   同步方法: {sync_config.method.value if hasattr(sync_config.method, 'value') else sync_config.method}")
    print(f"   递归速度: {sync_config.speed}")
    print(f"   启用状态: {sync_config.enable}")
    print(f"   网盘类型: {current_drive_type.value}")
    
    return sync_config

async def test_full_sync():
    """执行完整同步测试"""
    print("\n🚀 执行完整同步测试:")
    
    # 创建测试配置
    sync_config = await create_test_sync_config()
    if not sync_config:
        print("❌ 创建同步配置失败")
        return
    
    print("\n   开始执行同步...")
    
    try:
        # 执行同步
        result = await sync_service.perform_sync(sync_config)
        
        if result["success"]:
            print("✅ 同步执行成功:")
            stats = result.get("stats", {})
            print(f"   总耗时: {result['elapsed_time']:.2f}秒")
            print(f"   同步方法: {stats.get('sync_method', 'N/A')}")
            print(f"   递归速度: {stats.get('recursion_speed', 'N/A')}")
            print(f"   源文件数: {stats.get('source_list_num', 0)}")
            print(f"   目标文件数: {stats.get('target_list_num', 0)}")
            print(f"   需要添加: {stats.get('to_add_total', 0)} 个文件")
            print(f"   需要删除: {stats.get('to_delete_total', 0)} 个文件")
            print(f"   添加成功: {stats.get('added_success', 0)} 个")
            print(f"   添加失败: {stats.get('added_fail', 0)} 个")
            print(f"   删除成功: {stats.get('deleted_success', 0)} 个")
            print(f"   删除失败: {stats.get('deleted_fail', 0)} 个")
        else:
            print("❌ 同步执行失败:")
            print(f"   错误信息: {result.get('error', 'Unknown error')}")
            print(f"   耗时: {result['elapsed_time']:.2f}秒")
        
        return result
        
    except Exception as e:
        print(f"❌ 完整同步测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_real_config_sync():
    """使用真实配置执行同步测试"""
    print("\n🔧 使用真实配置执行同步测试:")
    print("这个测试将从数据库中选择已有的账号和同步配置进行同步")
    
    # 从数据库获取同步配置列表
    try:
        from backend.database.db import async_db_session
        from backend.app.coulddrive.crud.crud_filesync import sync_config_dao
        
        async with async_db_session() as db:
            configs = await sync_config_dao.get_all(db)
            
            if not configs:
                print("❌ 数据库中没有找到任何同步配置，请先创建同步配置")
                return
            
            print(f"\n找到 {len(configs)} 个同步配置:")
            for i, config in enumerate(configs, 1):
                status = "启用" if config.enable else "禁用"
                print(f"  {i}. {config.remark or '未命名'} ({config.type}) - {status}")
                print(f"     源: {config.src_path} -> 目标: {config.dst_path}")
            
            # 选择配置
            while True:
                try:
                    choice = input(f"\n请选择同步配置 (1-{len(configs)}): ").strip()
                    config_index = int(choice) - 1
                    if 0 <= config_index < len(configs):
                        selected_config = configs[config_index]
                        break
                    else:
                        print(f"❌ 请输入 1-{len(configs)} 之间的数字")
                except ValueError:
                    print("❌ 请输入有效的数字")
            
            print(f"✅ 已选择配置: {selected_config.remark or '未命名'}")
            
            # 检查配置状态
            if not selected_config.enable:
                print("⚠️  警告: 选择的配置已禁用")
                confirm = input("是否继续执行? (y/N): ").strip().lower()
                if confirm != 'y':
                    print("❌ 操作已取消")
                    return
            
            # 构建 GetSyncConfigDetail 对象
            from backend.app.coulddrive.schema.filesync import GetSyncConfigDetail
            
            # 处理 DriveType 映射（数据库存储的是枚举名称，需要转换为枚举对象）
            def get_drive_type_from_db_value(db_value: str) -> DriveType:
                """从数据库值获取 DriveType 枚举"""
                # 数据库中存储的是枚举名称，如 "BAIDU_DRIVE"
                try:
                    return DriveType[db_value]
                except KeyError:
                    # 如果找不到，尝试通过值匹配
                    for drive_type in DriveType:
                        if drive_type.value == db_value:
                            return drive_type
                    # 默认返回百度网盘
                    return DriveType.BAIDU_DRIVE
            
            sync_config_detail = GetSyncConfigDetail(
                id=selected_config.id,
                enable=selected_config.enable,
                remark=selected_config.remark,
                type=get_drive_type_from_db_value(selected_config.type),
                src_path=selected_config.src_path,
                src_meta=selected_config.src_meta,
                dst_path=selected_config.dst_path,
                dst_meta=selected_config.dst_meta,
                account_id=selected_config.user_id,  # 注意：模型中是 user_id，但 schema 中是 account_id
                cron=selected_config.cron,
                speed=selected_config.speed,
                method=SyncMethod(selected_config.method) if hasattr(SyncMethod, selected_config.method.upper()) else SyncMethod.INCREMENTAL,
                end_time=selected_config.end_time,
                exclude=selected_config.exclude,
                rename=selected_config.rename,
                last_sync=selected_config.last_sync,
                created_time=selected_config.created_time,
                updated_time=selected_config.updated_time or selected_config.created_time,
                created_by=getattr(selected_config, 'created_by', 1),  # 如果没有该字段，使用默认值1
                updated_by=getattr(selected_config, 'updated_by', 1)   # 如果没有该字段，使用默认值1
            )
            
            print(f"\n开始执行同步...")
            print(f"   配置ID: {sync_config_detail.id}")
            print(f"   账户ID: {sync_config_detail.account_id}")
            print(f"   源路径: {sync_config_detail.src_path}")
            print(f"   目标路径: {sync_config_detail.dst_path}")
            print(f"   同步方法: {sync_config_detail.method}")
            print(f"   递归速度: {sync_config_detail.speed}")
            
            # 使用 filesync_service 的 perform_sync 方法
            result = await sync_service.perform_sync(sync_config_detail)
            
            if result["success"]:
                print("\n✅ 同步执行成功:")
                stats = result.get("stats", {})
                print(f"   总耗时: {result['elapsed_time']:.2f}秒")
                print(f"   同步方法: {stats.get('sync_method', 'N/A')}")
                print(f"   递归速度: {stats.get('recursion_speed', 'N/A')}")
                print(f"   源文件数: {stats.get('source_list_num', 0)}")
                print(f"   目标文件数: {stats.get('target_list_num', 0)}")
                print(f"   需要添加: {stats.get('to_add_total', 0)} 个文件")
                print(f"   需要删除: {stats.get('to_delete_total', 0)} 个文件")
                print(f"   添加成功: {stats.get('added_success', 0)} 个")
                print(f"   添加失败: {stats.get('added_fail', 0)} 个")
                print(f"   删除成功: {stats.get('deleted_success', 0)} 个")
                print(f"   删除失败: {stats.get('deleted_fail', 0)} 个")
                
                # 显示详细结果
                details = result.get("details", {})
                if details:
                    add_results = details.get("add", {})
                    add_succeeded = add_results.get("succeeded", [])
                    add_failed = add_results.get("failed", [])
                    
                    if add_succeeded:
                        print("\n   成功添加的文件:")
                        for i, result_msg in enumerate(add_succeeded[:5]):  # 只显示前5个
                            print(f"     {i+1}. {result_msg}")
                        if len(add_succeeded) > 5:
                            print(f"     ... 还有 {len(add_succeeded) - 5} 个")
                    
                    if add_failed:
                        print("\n   添加失败的文件:")
                        for i, result_msg in enumerate(add_failed[:5]):  # 只显示前5个
                            print(f"     {i+1}. {result_msg}")
                        if len(add_failed) > 5:
                            print(f"     ... 还有 {len(add_failed) - 5} 个")
            else:
                print("\n❌ 同步执行失败:")
                print(f"   错误信息: {result.get('error', 'Unknown error')}")
                print(f"   耗时: {result['elapsed_time']:.2f}秒")
            
            return result
                
    except Exception as e:
        print(f"❌ 获取同步配置失败: {e}")
        import traceback
        traceback.print_exc()
        return None

async def run_sync_service_test_suite():
    """运行文件同步服务测试套件"""
    print("\n🎯 开始运行文件同步服务测试套件...")
    
    print("\n" + "="*50)
    print("1. 测试同步方法解析")
    test_sync_method_parsing()
    
    print("\n" + "="*50)
    print("2. 测试递归速度解析")
    test_recursion_speed_parsing()
    
    print("\n" + "="*50)
    print("3. 测试比较逻辑")
    comparison_result = await test_comparison_logic()
    
    if comparison_result:
        print("\n" + "="*50)
        print("4. 测试同步操作应用")
        await test_sync_operations(comparison_result)
    
    print("\n" + "="*50)
    print("5. 测试完整同步流程")
    await test_full_sync()
    
    print("\n✅ 文件同步服务测试套件执行完成!")

async def main():
    """主函数 - 交互式菜单"""
    print("🎉 欢迎使用文件同步服务测试工具!")
    
    while True:
        print_menu()
        choice = input("请选择操作 (0-94): ").strip()
        
        if choice == "0":
            print("👋 再见!")
            break
        elif choice == "1":
            select_drive_type()
        elif choice == "41":
            test_sync_method_parsing()
        elif choice == "42":
            test_recursion_speed_parsing()
        elif choice == "43":
            await test_comparison_logic()
        elif choice == "44":
            await test_sync_operations()
        elif choice == "45":
            await create_test_sync_config()
        elif choice == "46":
            await test_full_sync()
        elif choice == "47":
            await test_real_config_sync()
        elif choice == "94":
            await run_sync_service_test_suite()
        else:
            print("❌ 无效选择，请重新输入!")
        
        # 等待用户按键继续
        input("\n按回车键继续...")

if __name__ == "__main__":
    # 运行交互式主函数
    asyncio.run(main())
