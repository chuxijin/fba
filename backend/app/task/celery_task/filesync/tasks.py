#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Dict, Any, List

from croniter import croniter

from backend.app.coulddrive.crud.crud_filesync import sync_config_dao
from backend.app.coulddrive.service.filesync_service import file_sync_service
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name='check_and_execute_filesync_cron_tasks')
async def check_and_execute_filesync_cron_tasks() -> Dict[str, Any]:
    """
    检查并执行文件同步定时任务
    
    扫描所有启用的同步配置，检查其cron字段，
    如果到了执行时间则触发同步任务
    
    :return: 执行结果统计
    """
    try:
        result = await _check_and_execute_filesync_cron_tasks()
        # logger.info(f"定时任务检查完成: 检查 {result['checked_configs']} 个配置，"
        #            f"执行 {result['executed_tasks']} 个，"
        #            f"失败 {result['failed_tasks']} 个，"
        #            f"跳过 {result['skipped_tasks']} 个")
        return result
            
    except Exception as e:
        logger.error(f"定时任务检查失败: {str(e)}")
        return {
            "checked_configs": 0,
            "executed_tasks": 0,
            "failed_tasks": 0,
            "skipped_tasks": 0,
            "execution_details": [],
            "error": str(e)
        }


async def _check_and_execute_filesync_cron_tasks() -> Dict[str, Any]:
    """
    检查并执行文件同步定时任务的异步实现
    
    :return: 执行结果统计
    """
    result = {
        "checked_configs": 0,
        "executed_tasks": 0,
        "failed_tasks": 0,
        "skipped_tasks": 0,
        "execution_details": []
    }
    
    # 用于收集详细信息的临时列表
    temp_details = []
    
    try:
        async with async_db_session() as db:
            # 获取所有启用的同步配置
            enabled_configs = await sync_config_dao.get_enabled_configs(db)
            result["checked_configs"] = len(enabled_configs)
            
            current_time = datetime.now()
            
            for config in enabled_configs:
                try:
                    # 检查是否有cron表达式
                    if not config.cron:
                        result["skipped_tasks"] += 1
                        temp_details.append({
                            "config_id": config.id,
                            "status": "skipped",
                            "reason": "没有设置cron表达式"
                        })
                        continue
                    
                    # 检查任务是否过期 
                    end_time = datetime.fromisoformat(str(config.end_time)) if config.end_time else None
                    if end_time and current_time > end_time:
                        result["skipped_tasks"] += 1
                        temp_details.append({
                            "config_id": config.id,
                            "status": "skipped",
                            "reason": "任务已过期"
                        })
                        continue
                    
                    # 验证cron表达式
                    if not _is_valid_cron_expression(config.cron):
                        result["failed_tasks"] += 1
                        temp_details.append({
                            "config_id": config.id,
                            "status": "failed",
                            "reason": "cron表达式无效"
                        })
                        continue
                    
                    # 检查是否到了执行时间
                    should_execute = _should_execute_now(config.cron, config.last_sync, current_time)
                    
                    if not should_execute:
                        result["skipped_tasks"] += 1
                        temp_details.append({
                            "config_id": config.id,
                            "status": "skipped",
                            "reason": "未到执行时间"
                        })
                        continue
                    
                    # logger.info(f"执行配置 {config.id} ({config.remark}) 的同步任务")
                    
                    # 执行同步任务
                    sync_result = await file_sync_service.execute_sync_by_config_id(config.id, db)
                    
                    if sync_result.get("success"):
                        result["executed_tasks"] += 1
                        temp_details.append({
                            "config_id": config.id,
                            "status": "success",
                            "task_id": sync_result.get("task_id"),
                            "stats": sync_result.get("stats"),
                            "elapsed_time": sync_result.get("elapsed_time")
                        })
                        logger.info(f"配置 {config.remark} 执行成功")
                    else:
                        result["failed_tasks"] += 1
                        temp_details.append({
                            "config_id": config.id,
                            "status": "failed",
                            "error": sync_result.get("error"),
                            "task_id": sync_result.get("task_id")
                        })
                        logger.error(f"配置 {config.id} 同步任务执行失败: {sync_result.get('error')}")
                
                except Exception as e:
                    logger.error(f"处理配置 {config.id} 时发生错误: {str(e)}")
                    result["failed_tasks"] += 1
                    temp_details.append({
                        "config_id": config.id,
                        "status": "error",
                        "error": str(e)
                    })
    
    except Exception as e:
        logger.error(f"检查文件同步定时任务时发生错误: {str(e)}")
        result["error"] = str(e)
    
    # 合并相同状态和原因的配置
    result["execution_details"] = _merge_execution_details(temp_details)
    
    return result


@celery_app.task(name='execute_filesync_task_by_config_id')
async def execute_filesync_task_by_config_id(config_id: int) -> Dict[str, Any]:
    """
    根据配置ID执行单个文件同步任务
    
    :param config_id: 同步配置ID
    :return: 执行结果
    """
    try:
        return await _execute_filesync_task_by_config_id(config_id)
    except Exception as e:
        logger.error(f"执行配置 {config_id} 同步任务失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "config_id": config_id
        }


async def _execute_filesync_task_by_config_id(config_id: int) -> Dict[str, Any]:
    """
    根据配置ID执行单个文件同步任务的异步实现
    
    :param config_id: 同步配置ID
    :return: 执行结果
    """
    try:
        async with async_db_session() as db:
            result = await file_sync_service.execute_sync_by_config_id(config_id, db)
            
            if result.get("success"):
                pass
            else:
                logger.error(f"配置 {config_id} 同步任务执行失败: {result.get('error')}")
            
            return result
    
    except Exception as e:
        error_msg = f"执行配置 {config_id} 同步任务时发生错误: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "config_id": config_id
        }


@celery_app.task(name='get_filesync_configs_with_cron')
async def get_filesync_configs_with_cron() -> List[Dict[str, Any]]:
    """
    获取所有设置了cron表达式的同步配置
    
    :return: 配置列表
    """
    try:
        return await _get_filesync_configs_with_cron()
    except Exception as e:
        logger.error(f"获取cron配置列表失败: {str(e)}")
        return []


async def _get_filesync_configs_with_cron() -> List[Dict[str, Any]]:
    """
    获取所有设置了cron表达式的同步配置的异步实现
    
    :return: 配置列表
    """
    try:
        async with async_db_session() as db:
            enabled_configs = await sync_config_dao.get_enabled_configs(db)
            
            configs_with_cron = []
            for config in enabled_configs:
                if config.cron:
                    config_info = {
                        "id": config.id,
                        "remark": config.remark,
                        "cron": config.cron,
                        "last_sync": str(config.last_sync) if config.last_sync else None,
                        "end_time": str(config.end_time) if config.end_time else None,
                        "src_path": config.src_path,
                        "dst_path": config.dst_path,
                        "type": config.type,
                        "is_valid_cron": _is_valid_cron_expression(config.cron)
                    }
                    
                    # 计算下次执行时间
                    if config_info["is_valid_cron"]:
                        try:
                            cron = croniter(config.cron, datetime.now())
                            next_run = cron.get_next(datetime)
                            config_info["next_run"] = next_run.isoformat()
                        except Exception:
                            config_info["next_run"] = None
                    else:
                        config_info["next_run"] = None
                    
                    configs_with_cron.append(config_info)
            
            return configs_with_cron
    
    except Exception as e:
        logger.error(f"获取cron配置时发生错误: {str(e)}")
        return []


def _is_valid_cron_expression(cron_expr: str) -> bool:
    """
    验证cron表达式是否有效
    
    :param cron_expr: cron表达式
    :return: 是否有效
    """
    try:
        croniter(cron_expr)
        return True
    except Exception:
        return False


def _should_execute_now(cron_expr: str, last_sync: Any | None, current_time: datetime) -> bool:
    """
    判断是否应该在当前时间执行任务
    
    :param cron_expr: cron表达式
    :param last_sync: 上次同步时间
    :param current_time: 当前时间
    :return: 是否应该执行
    """
    try:
        # 从未同步过，立即执行
        if last_sync is None:
            return True
        
        # 基于当前时间创建 croniter，检查当前时间是否符合 cron 表达式
        cron = croniter(cron_expr, current_time)
        
        # 获取当前时间之前的最近一次执行时间
        prev_execution_time = cron.get_prev(datetime)
        
        # 如果上次同步时间早于最近一次应该执行的时间，说明需要执行
        last_sync_dt = datetime.fromisoformat(str(last_sync)) if last_sync else None
        if last_sync_dt and last_sync_dt < prev_execution_time:
            return True
        
        return False
    
    except Exception as e:
        logger.error(f"解析cron表达式 {cron_expr} 时发生错误: {str(e)}")
        return False


def _merge_execution_details(details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    合并相同状态和原因的执行详情
    
    :param details: 原始执行详情列表
    :return: 合并后的执行详情列表
    """
    if not details:
        return []
    
    # 用于分组的字典，key为(status, reason/error)，value为配置ID列表和其他信息
    groups = {}
    
    for detail in details:
        status = detail.get("status")
        
        # 根据状态确定分组的key
        if status in ["skipped", "failed"] and "reason" in detail:
            # 对于有reason的情况，使用(status, reason)作为key
            group_key = (status, detail.get("reason"))
        elif status == "failed" and "error" in detail:
            # 对于有error的情况，使用(status, error)作为key
            group_key = (status, detail.get("error"))
        else:
            # 对于success等其他情况，每个配置单独一条记录
            group_key = (status, detail.get("config_id"))
        
        if group_key not in groups:
            groups[group_key] = {
                "config_ids": [],
                "detail": detail.copy()
            }
        
        groups[group_key]["config_ids"].append(detail.get("config_id"))
    
    # 生成合并后的结果
    merged_details = []
    for (status, reason_or_error), group_data in groups.items():
        config_ids = group_data["config_ids"]
        detail = group_data["detail"]
        
        if len(config_ids) > 1:
            # 多个配置ID，合并显示
            detail["config_id"] = config_ids
        else:
            # 单个配置ID，保持原样
            detail["config_id"] = config_ids[0]
        
        merged_details.append(detail)
    
    # 按状态排序：success -> failed -> error -> skipped
    status_order = {"success": 1, "failed": 2, "error": 3, "skipped": 4}
    merged_details.sort(key=lambda x: status_order.get(x.get("status"), 5))
    
    return merged_details 