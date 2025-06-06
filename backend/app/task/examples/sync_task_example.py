#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件同步任务使用示例

演示如何使用基于 cron 表达式的文件同步任务系统
"""

import asyncio
import logging
from datetime import datetime

from backend.app.task.service.sync_scheduler import get_sync_scheduler, validate_cron
from backend.app.task.celery_task.filesync.tasks import sync_file_task, sync_all_enabled_configs
from backend.database.db import async_db_session
from backend.app.coulddrive.crud.crud_filesync import sync_config_dao

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_1_validate_cron_expressions():
    """示例1: 验证 cron 表达式"""
    print("\n" + "="*50)
    print("示例1: 验证 cron 表达式")
    print("="*50)
    
    # 测试各种 cron 表达式
    test_expressions = [
        "0 2 * * *",        # 每天凌晨2点
        "*/30 * * * *",     # 每30分钟
        "0 9,18 * * 1-5",   # 工作日上午9点和下午6点
        "0 0 1 * *",        # 每月1号凌晨
        "invalid cron",     # 无效表达式
        "0 2 * *",          # 格式错误（缺少字段）
    ]
    
    for expr in test_expressions:
        result = validate_cron(expr)
        status = "✅ 有效" if result["valid"] else "❌ 无效"
        print(f"  {expr:<20} -> {status}")
        if not result["valid"]:
            print(f"    错误: {result['error']}")
        elif result.get("next_run_in_seconds"):
            print(f"    下次执行: {result['next_run_in_seconds']:.0f} 秒后")


async def example_2_scheduler_operations():
    """示例2: 调度器操作"""
    print("\n" + "="*50)
    print("示例2: 调度器操作")
    print("="*50)
    
    scheduler = get_sync_scheduler()
    
    # 获取当前状态
    status = scheduler.get_task_status()
    print(f"  当前调度任务数: {status['total_scheduled_tasks']}")
    print(f"  活跃配置ID: {status['scheduled_config_ids']}")
    
    # 从数据库同步任务
    print("\n  从数据库同步任务...")
    result = await scheduler.sync_all_tasks_from_db()
    
    if result["success"]:
        print(f"  ✅ {result['message']}")
        print(f"    总配置数: {result['total_configs']}")
        print(f"    添加任务: {result['added_count']}")
        print(f"    跳过配置: {result['skipped_count']}")
        print(f"    错误配置: {result['error_count']}")
        print(f"    活跃任务: {result['active_tasks']}")
    else:
        print(f"  ❌ 同步失败: {result.get('message', 'Unknown error')}")


async def example_3_execute_sync_task():
    """示例3: 执行同步任务"""
    print("\n" + "="*50)
    print("示例3: 执行同步任务")
    print("="*50)
    
    try:
        # 获取第一个启用的配置
        async with async_db_session() as db:
            enabled_configs = await sync_config_dao.get_enabled_configs(db)
            
            if not enabled_configs:
                print("  ❌ 没有找到启用的同步配置")
                return
            
            config = enabled_configs[0]
            print(f"  选择配置: ID={config.id}, 备注={config.remark or '未命名'}")
            
            # 立即执行同步任务
            print("  🚀 提交同步任务...")
            task_result = sync_file_task.delay(config.id)
            
            print(f"  ✅ 任务已提交")
            print(f"    任务ID: {task_result.id}")
            print(f"    配置ID: {config.id}")
            print(f"    状态: {task_result.status}")
            
            # 等待任务完成（仅用于演示，实际使用中不建议阻塞等待）
            print("  ⏳ 等待任务完成...")
            try:
                # 设置超时时间，避免无限等待
                result = task_result.get(timeout=300)  # 5分钟超时
                
                if result.get("success"):
                    print("  ✅ 同步任务执行成功")
                    stats = result.get("stats", {})
                    print(f"    耗时: {result.get('elapsed_time', 0):.2f}秒")
                    print(f"    添加成功: {stats.get('added_success', 0)} 个文件")
                    print(f"    删除成功: {stats.get('deleted_success', 0)} 个文件")
                else:
                    print(f"  ❌ 同步任务执行失败: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"  ⚠️  任务执行超时或异常: {e}")
                print(f"    任务ID: {task_result.id} (可稍后查询结果)")
                
    except Exception as e:
        print(f"  ❌ 执行示例失败: {e}")


async def example_4_batch_sync():
    """示例4: 批量同步"""
    print("\n" + "="*50)
    print("示例4: 批量同步所有启用配置")
    print("="*50)
    
    try:
        # 执行批量同步
        print("  🚀 提交批量同步任务...")
        task_result = sync_all_enabled_configs.delay()
        
        print(f"  ✅ 批量任务已提交")
        print(f"    任务ID: {task_result.id}")
        print(f"    状态: {task_result.status}")
        
        # 等待任务完成
        print("  ⏳ 等待批量任务完成...")
        try:
            result = task_result.get(timeout=600)  # 10分钟超时
            
            if result.get("success"):
                print("  ✅ 批量同步任务执行成功")
                print(f"    总配置数: {result.get('total_configs', 0)}")
                print(f"    成功数量: {result.get('success_count', 0)}")
                print(f"    失败数量: {result.get('failed_count', 0)}")
                
                # 显示部分结果
                results = result.get("results", [])
                if results:
                    print("    前3个结果:")
                    for i, res in enumerate(results[:3], 1):
                        status = "✅" if res.get("success") else "❌"
                        config_id = res.get("config_id", "Unknown")
                        message = res.get("message", "No message")
                        print(f"      {i}. {status} 配置{config_id}: {message}")
            else:
                print(f"  ❌ 批量同步任务执行失败: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"  ⚠️  批量任务执行超时或异常: {e}")
            print(f"    任务ID: {task_result.id} (可稍后查询结果)")
            
    except Exception as e:
        print(f"  ❌ 执行批量示例失败: {e}")


async def main():
    """主函数 - 运行所有示例"""
    print("🎯 文件同步任务系统使用示例")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 运行所有示例
        await example_1_validate_cron_expressions()
        await example_2_scheduler_operations()
        await example_3_execute_sync_task()
        await example_4_batch_sync()
        
        print("\n" + "="*50)
        print("🎉 所有示例执行完成！")
        print("="*50)
        
    except Exception as e:
        logger.error(f"示例执行失败: {e}", exc_info=True)
        print(f"\n❌ 示例执行失败: {e}")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main()) 