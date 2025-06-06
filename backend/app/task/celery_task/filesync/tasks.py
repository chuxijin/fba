#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any

from backend.app.coulddrive.service.filesync_service import file_sync_service
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name='sync_file_task')
async def sync_file_task(config_id: int) -> Dict[str, Any]:
    """
    执行文件同步任务
    
    :param config_id: 同步配置ID
    :return: 同步结果
    """
    logger.info(f"开始执行同步任务，配置ID: {config_id}")
    
    try:
        async with async_db_session() as db:
            result = await file_sync_service.execute_sync_by_config_id(config_id, db)
            
            if result["success"]:
                logger.info(f"同步任务完成，配置ID: {config_id}, 耗时: {result.get('elapsed_time', 0):.2f}秒")
                return {
                    "success": True,
                    "config_id": config_id,
                    "message": "同步任务执行成功",
                    "stats": result.get("stats", {}),
                    "elapsed_time": result.get("elapsed_time", 0)
                }
            else:
                logger.error(f"同步任务失败，配置ID: {config_id}, 错误: {result.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "config_id": config_id,
                    "message": "同步任务执行失败",
                    "error": result.get("error", "Unknown error"),
                    "elapsed_time": result.get("elapsed_time", 0)
                }
                
    except Exception as e:
        error_msg = f"同步任务异常，配置ID: {config_id}, 错误: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "config_id": config_id,
            "message": "同步任务执行异常",
            "error": str(e),
            "elapsed_time": 0
        }


@celery_app.task(name='sync_all_enabled_configs')
async def sync_all_enabled_configs() -> Dict[str, Any]:
    """
    执行所有启用配置的同步任务
    
    :return: 批量同步结果
    """
    logger.info("开始执行所有启用配置的同步任务")
    
    try:
        from backend.app.coulddrive.crud.crud_filesync import sync_config_dao
        
        async with async_db_session() as db:
            # 获取所有启用的配置
            enabled_configs = await sync_config_dao.get_enabled_configs(db)
            
            if not enabled_configs:
                return {
                    "success": True,
                    "message": "没有启用的同步配置",
                    "total_configs": 0,
                    "results": []
                }
            
            results = []
            success_count = 0
            
            # 逐个执行同步任务
            for config in enabled_configs:
                try:
                    async with async_db_session() as sync_db:
                        result = await file_sync_service.execute_sync_by_config_id(config.id, sync_db)
                        
                        # 格式化结果以匹配预期格式
                        formatted_result = {
                            "success": result["success"],
                            "config_id": config.id,
                            "message": "同步任务执行成功" if result["success"] else "同步任务执行失败",
                            "stats": result.get("stats", {}),
                            "elapsed_time": result.get("elapsed_time", 0)
                        }
                        
                        if not result["success"]:
                            formatted_result["error"] = result.get("error", "Unknown error")
                        
                        results.append(formatted_result)
                        
                        if formatted_result.get("success"):
                            success_count += 1
                        
                except Exception as e:
                    error_result = {
                        "success": False,
                        "config_id": config.id,
                        "message": "任务调用失败",
                        "error": str(e)
                    }
                    results.append(error_result)
                    logger.error(f"配置 {config.id} 同步任务调用失败: {e}")
            
            logger.info(f"批量同步完成，总配置数: {len(enabled_configs)}, 成功: {success_count}, 失败: {len(enabled_configs) - success_count}")
            
            return {
                "success": True,
                "message": f"批量同步完成，成功 {success_count}/{len(enabled_configs)} 个配置",
                "total_configs": len(enabled_configs),
                "success_count": success_count,
                "failed_count": len(enabled_configs) - success_count,
                "results": results
            }
            
    except Exception as e:
        error_msg = f"批量同步任务异常: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "message": "批量同步任务执行异常",
            "error": str(e),
            "total_configs": 0,
            "results": []
        } 