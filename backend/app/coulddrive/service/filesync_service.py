#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
import time
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.schema.enum import DriveType, RecursionSpeed, SyncMethod
from backend.app.coulddrive.service.rule_template_service import (
    ItemFilter,
    parse_exclusion_rules,
    parse_rule_templates
)
from backend.app.coulddrive.schema.file import (
    BaseFileInfo,
    DiskTargetDefinition,
    ExclusionRuleDefinition,
    ListFilesParam,
    ListShareFilesParam,
    MkdirParam,
    RemoveParam,
    RenameParam,
    RenameRuleDefinition,
    ShareSourceDefinition,
    TransferParam,
)
from backend.app.coulddrive.schema.filesync import (
    CreateSyncTaskParam, 
    UpdateSyncTaskParam,
    UpdateSyncConfigParam,
    CreateSyncTaskItemParam,
)
from backend.app.coulddrive.crud.crud_filesync import sync_task_dao, sync_config_dao, sync_task_item_dao
from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.common.log import log
from backend.common.db_lock import DatabaseMutex
from backend.database.db import async_db_session # 用于获取数据库会话工厂
from backend.app.coulddrive.service.rule_template_service import MatchTarget, RenameRule

logger = logging.getLogger(__name__)


class FileSyncService:
    """
    极简文件同步服务 - 学习成熟方案设计（带详细任务项记录）
    
    核心方法：
    1. perform_sync() - 同步入口（对应alist的sync）
    2. sync_with_have() - 目标存在时同步（对应alist的syncWithHave）
    3. sync_without_have() - 目标不存在时同步（对应alist的syncWithOutHave）
    4. list_dir() - 列出目录（对应alist的listDir）
    5. transfer_files() - 转存文件（批量优势）
    6. delete_files() - 删除文件（批量优势）
    7. create_directory() - 创建目录
    8. record_task_item() - 记录任务项（学习alist）
    """
    
    def __init__(self):
        """初始化同步服务"""
        from backend.app.coulddrive.service.yp_service import get_drive_manager
        self.drive_manager = get_drive_manager()
        self.logger = log

    async def execute_sync_by_config_id(self, config_id: int, db: AsyncSession) -> Dict[str, Any]:
        """
        根据配置ID执行同步任务 - 数据库操作入口
        
        Args:
            config_id: 同步配置ID
            db: 数据库会话
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        start_time = time.time()
        task_id = None
        self.logger.info(f"[任务{task_id or 'unknown'}] 开始执行同步任务，配置ID: {config_id}")
        
        try:
            # 获取并验证配置
            config, error_msg = await sync_config_dao.get_with_validation(db, config_id)
            if not config:
                self.logger.error(f"[任务{task_id or 'unknown'}] 获取配置失败: {error_msg}")
                return {"success": False, "error": error_msg, "config_id": config_id, "elapsed_time": 0}

            # 检查任务是否过期 - 先转换为Python datetime进行比较
            if config.end_time:
                end_time_dt = config.end_time if isinstance(config.end_time, datetime) else datetime.fromisoformat(str(config.end_time))
                if datetime.now() > end_time_dt:
                    self.logger.info(f"[任务{task_id or 'unknown'}] 同步任务已过期，截止时间: {config.end_time}")
                    return {
                    "success": True,
                    "message": f"同步任务已过期，截止时间: {config.end_time}",
                    "config_id": config_id,
                    "elapsed_time": 0,
                        "stats": {"processed": 0, "transferred": 0, "deleted": 0, "skipped": 0, "errors": 0}
                }
            
            # 获取网盘账户信息
            drive_account = await drive_account_dao.get(db, config.user_id)
            if not drive_account or not drive_account.cookies:
                self.logger.error(f"[任务{task_id or 'unknown'}] 网盘账户 {config.user_id} 不存在或cookies为空")
                return {
                    "success": False,
                    "error": f"网盘账户 {config.user_id} 不存在或cookies为空",
                    "config_id": config_id,
                    "elapsed_time": 0
                }
            
            # 创建同步任务记录
            task_params = CreateSyncTaskParam(
                config_id=config_id,
                start_time=datetime.now(),
                status="running",
                err_msg=None,
                task_num="{}",
                dura_time=0
            )
            sync_task = await sync_task_dao.create(db, obj_in=task_params, current_user_id=config.created_by)
            task_id = sync_task.id
            await db.commit()
            self.logger.info(f"[任务{task_id}] 同步任务记录创建成功，任务ID: {task_id}")
            
            # 立即更新配置的最后同步时间，防止并发执行
            try:
                config_update = UpdateSyncConfigParam(last_sync=datetime.now())
                await sync_config_dao.update(db, db_obj=config, obj_in=config_update)
                await db.commit()
                self.logger.info(f"[任务{task_id}] 配置 {config_id} 的last_sync已在任务开始时更新")
            except Exception as update_error:
                self.logger.error(f"[任务{task_id}] 更新配置last_sync失败: {update_error}")
                # 如果更新失败，任务可能会重复执行，但这比数据不一致更安全
                return {
                    "success": False,
                    "error": f"更新last_sync失败: {update_error}",
                    "config_id": config_id,
                    "elapsed_time": 0
                }
            
            # 解析配置参数
            sync_method = self._parse_sync_method(config.method)
            recursion_speed = self._parse_recursion_speed(config.speed)
            
            # 解析规则模板
            exclude_rules, rename_rules = await parse_rule_templates(
                config.exclude_template_id,
                config.rename_template_id,
                db
            )
            # self.logger.info(f"[任务{task_id}] 解析到的重命名规则: {rename_rules}") # 添加调试日志
            
            # 解析源和目标定义
            src_meta = json.loads(config.src_meta) if config.src_meta else {}
            dst_meta = json.loads(config.dst_meta) if config.dst_meta else {}
            
            source_definition = ShareSourceDefinition(
                source_type=src_meta.get("source_type", ""),
                source_id=src_meta.get("source_id", ""),
                file_path=config.src_path,
                ext_params=src_meta.get("ext_params", {})
            )
            
            target_definition = DiskTargetDefinition(
                file_path=config.dst_path,
                file_id=dst_meta.get("file_id", "")
            )
            
            self.logger.info(f"[任务{task_id}] 开始执行核心同步逻辑 perform_sync")
            # 执行同步
            account_key = f"filesync:{DriveType(drive_account.type).value}:{config.user_id}"
            # 确保同一账号同一网盘类型下的同步任务串行执行，避免并发操作导致的数据冲突
            if config.user_id and config.type:
                lock_key = f"filesync:{config.type}:{config.user_id}"
                self.logger.info(f"[任务{task_id}] 尝试获取文件同步锁: {lock_key}")
                try:
                    async with DatabaseMutex(async_db_session, lock_key, owner_id=str(task_id), max_wait_seconds=600, timeout_seconds=300): # 数据库锁，默认持有5分钟，最长等待10分钟
                        self.logger.info(f"[任务{task_id}] 成功获取文件同步锁: {lock_key}")
                        sync_result = await self.perform_sync(
                            x_token=drive_account.cookies,
                            drive_type=DriveType(drive_account.type),
                            source_definition=source_definition,
                            target_definition=target_definition,
                            sync_method=sync_method,
                            recursion_speed=recursion_speed,
                            exclude_rules=exclude_rules,
                            max_depth=100,
                            task_id=task_id,
                            db=db,
                            account_key=account_key
                        )
                    self.logger.info(f"[任务{task_id}] 释放文件同步锁: {lock_key}")
                except TimeoutError:
                    error_message = f"获取文件同步锁超时，请稍后再试或检查是否有其他同步任务正在进行: {lock_key}"
                    logger.warning(f"[任务{task_id}] {error_message}")
                    await self.update_task_status(db, task_id, "failed", error_message)
                    return {"success": False, "error": error_message, "config_id": config_id, "task_id": task_id, "elapsed_time": time.time() - start_time}
            else:
                self.logger.info(f"[任务{task_id}] 无需文件同步锁，直接执行同步")
                # self.logger.info(f"[任务{task_id}] [perform_sync] 调用 sync_with_have/overwrite 之前 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志
                sync_result = await self.perform_sync(
                    x_token=drive_account.cookies,
                    drive_type=DriveType(drive_account.type),
                    source_definition=source_definition,
                    target_definition=target_definition,
                    sync_method=sync_method,
                    recursion_speed=recursion_speed,
                    exclude_rules=exclude_rules,
                    max_depth=100,
                    task_id=task_id,
                    db=db,
                    account_key=account_key
                )
            
            # 从 sync_result 中获取 stats，包括 pending_task_items
            stats_from_sync = sync_result.get("stats", {})
            pending_task_items = stats_from_sync.get("pending_task_items", [])
            
            # 计算执行时间并更新任务状态
            elapsed_time = int(time.time() - start_time)
            
            if sync_result.get("success", False):
                # 在同步成功后，如果存在重命名规则，则执行重命名操作
                if rename_rules:
                    # self.logger.info(f"[任务{task_id}] 开始执行重命名操作，重命名规则: {rename_rules}") # 添加调试日志
                    # 收集所有转存成功的文件信息
                    transferred_files_info = stats_from_sync.get("transferred_files_info", []) # 修正这里
                    # self.logger.info(f"[任务{task_id}] 成功转存的文件信息 (来自 sync_result): {transferred_files_info}") # 修改调试日志
                    
                    # 为重命名操作传递stats_from_sync，以便收集重命名任务项
                    await self.rename_files(
                        x_token=drive_account.cookies,
                        drive_type=DriveType(drive_account.type),
                        transferred_files_info=transferred_files_info,
                        rename_rules=rename_rules,
                        task_id=task_id,
                        db=db,
                        account_key=account_key,
                        stats=stats_from_sync # 将 stats_from_sync 传递下去，以便收集重命名任务项
                    )
                
                # 更新任务为成功状态
                start_time_dt = sync_task.start_time if isinstance(sync_task.start_time, datetime) else None
                
                # 为json序列化准备stats副本
                stats_for_json = dict(stats_from_sync)
                if "pending_task_items" in stats_for_json and stats_for_json["pending_task_items"]:
                    stats_for_json["pending_task_items"] = [
                        item.model_dump() for item in stats_for_json["pending_task_items"]
                    ]

                update_params = UpdateSyncTaskParam(
                    status="completed",
                    dura_time=elapsed_time,
                    task_num=json.dumps(stats_for_json), # 使用转换为JSON友好的stats_for_json
                    err_msg=None,
                    start_time=start_time_dt
                )
                await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)
                
                # ========== 批量记录任务项并提交 ========== #
                self.logger.info(f"[任务{task_id}] 准备批量记录 {len(pending_task_items)} 个任务项")
                if pending_task_items:
                    for item_param in pending_task_items:
                        await sync_task_item_dao.create(db, obj_in=item_param)
                
                await db.commit()
                self.logger.info(f"[任务{task_id}] 任务 {task_id} 状态更新为成功，所有任务项已记录，总耗时: {elapsed_time:.2f}秒")
                # ========== 批量记录任务项并提交 ========== #
                
                # last_sync 已在任务开始时更新，无需重复更新
                
                return {
                    "success": True,
                    "task_id": task_id,
                    "config_id": config_id,
                    "stats": stats_from_sync,
                    "elapsed_time": elapsed_time,
                    "message": "同步任务执行成功"
                }
            else:
                # 更新任务为失败状态
                error_msg = sync_result.get("error", "未知错误")
                start_time_dt = sync_task.start_time if isinstance(sync_task.start_time, datetime) else None

                # 为json序列化准备stats副本
                stats_for_json = dict(stats_from_sync)
                if "pending_task_items" in stats_for_json and stats_for_json["pending_task_items"]:
                    stats_for_json["pending_task_items"] = [
                        item.model_dump() for item in stats_for_json["pending_task_items"]
                    ]

                update_params = UpdateSyncTaskParam(
                    status="failed",
                    dura_time=elapsed_time,
                    err_msg=error_msg,
                    task_num=json.dumps(stats_for_json), # 使用转换为JSON友好的stats_for_json
                    start_time=start_time_dt
                )
                await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)
                
                # ========== 批量记录任务项并提交 ========== #
                self.logger.info(f"[任务{task_id}] 准备批量记录 {len(pending_task_items)} 个任务项 (失败场景)")
                if pending_task_items:
                    for item_param in pending_task_items:
                        await sync_task_item_dao.create(db, obj_in=item_param)
                await db.commit()
                self.logger.error(f"[任务{task_id}] 任务 {task_id} 状态更新为失败，所有任务项已记录，错误: {error_msg}，总耗时: {elapsed_time:.2f}秒")
                # ========== 批量记录任务项并提交 ========== #
                
                return {
                    "success": False,
                    "task_id": task_id,
                    "config_id": config_id,
                    "error": error_msg,
                    "stats": stats_from_sync,
                    "elapsed_time": elapsed_time
                }
                
        except Exception as e:
            error_msg = f"执行同步任务时发生异常: {str(e)}"
            logger.error(f"[任务{task_id or 'unknown'}] {error_msg}", exc_info=True)
            
            # 如果在获取锁或perform_sync之前就发生异常，需要记录任务为失败
            if task_id and db:
                # 如果之前任务记录已创建，但没有pending_task_items，可以尝试记录一个失败的任务项
                if not pending_task_items:
                    # 如果任务记录已创建，尝试更新任务状态
                    if sync_task:
                        try:
                            start_time_dt = sync_task.start_time if isinstance(sync_task.start_time, datetime) else None
                            update_params = UpdateSyncTaskParam(
                                status="failed",
                                dura_time=int(time.time() - start_time),
                                err_msg=error_msg,
                                start_time=start_time_dt
                            )
                            await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)
                            await db.commit()
                        except Exception as update_err:
                            self.logger.error(f"[任务{task_id}] 更新失败任务状态失败: {update_err}")
                        else: # 如果任务记录都未创建成功，则无需更新
                            pass
                    else:
                        # 如果有pending_task_items，也要尝试记录
                        self.logger.info(f"[任务{task_id}] 异常发生时准备批量记录 {len(pending_task_items)} 个任务项")
                        for item_param in pending_task_items:
                            await sync_task_item_dao.create(db, obj_in=item_param)
                        await db.commit()
                
                return {
                    "success": False,
                    "task_id": task_id,
                    "config_id": config_id,
                    "error": error_msg,
                    "elapsed_time": int(time.time() - start_time)
                }

    def _parse_sync_method(self, method_str: str) -> str:
        """解析同步方式"""
        method_lower = method_str.lower() if method_str else ""
        
        if method_lower == SyncMethod.INCREMENTAL.value:
            return SyncMethod.INCREMENTAL.value
        elif method_lower == SyncMethod.FULL.value:
            return SyncMethod.FULL.value
        elif method_lower == SyncMethod.OVERWRITE.value:
            return SyncMethod.OVERWRITE.value
        else:
            self.logger.warning(f"未知的同步方式: {method_str}，使用默认增量同步")
            return SyncMethod.INCREMENTAL.value

    def _parse_recursion_speed(self, speed_value: int) -> RecursionSpeed:
        """解析递归速度"""
        if speed_value == 1:
            return RecursionSpeed.SLOW
        elif speed_value == 2:
            return RecursionSpeed.FAST
        else:
            return RecursionSpeed.NORMAL
    
    def _apply_rename_rules(
        self,
        file_info: Dict[str, Any],
        rename_rules: Optional[List[RenameRule]],
    ) -> Optional[Dict[str, Any]]:
        """在转存文件信息上应用重命名规则，返回带有新名称的文件信息，如果未重命名则返回None"""
        # self.logger.debug(f"[任务{file_info.get('task_id')}][_apply_rename_rules] 应用重命名规则到文件: {file_info.get('file_name', '')}, 规则: {rename_rules}") # 添加调试日志
        if not rename_rules:
            return None

        original_name = file_info.get("file_name", "")
        original_path = file_info.get("target_path", "") + original_name # 目标全路径
        
        new_name = original_name
        new_path = original_path

        temp_item = type('obj', (object,), {'file_name': original_name, 'file_path': original_path})()
        # self.logger.debug(f"[任务{file_info.get('task_id')}] [_apply_rename_rules] 原始名称: {original_name}, 原始路径: {original_path}") # 添加调试日志

        for rule in rename_rules:
            # self.logger.debug(f"[任务{file_info.get('task_id')}] [_apply_rename_rules] 尝试规则: {rule.match_regex} -> {rule.replace_string}, 目标: {rule.target_scope}") # 添加调试日志
            # 尝试生成新路径
            generated_value = rule.generate_new_path(temp_item)
            # self.logger.debug(f"[任务{file_info.get('task_id')}] [_apply_rename_rules] generated_value: {generated_value}") # 添加调试日志
            
            if generated_value:
                if rule.target_scope == MatchTarget.NAME:
                    new_name = generated_value
                    # 如果只重命名文件名，需要更新完整路径
                    parent_path = original_path.rsplit('/', 1)[0] if '/' in original_path else ''
                    new_path = parent_path + '/' + new_name if parent_path else new_name
                elif rule.target_scope == MatchTarget.PATH:
                    new_path = generated_value
                    # 如果重命名完整路径，需要更新文件名
                    new_name = new_path.rsplit('/', 1)[-1] if '/' in new_path else new_path
                
                # 规则被应用，可以跳出循环（或者继续应用其他规则，这里选择跳出）
                # self.logger.debug(f"[任务{file_info.get('task_id')}] [_apply_rename_rules] 规则应用成功，新名称: {new_name}, 新路径: {new_path}") # 添加调试日志
                break

        if new_name != original_name or new_path != original_path:
            # self.logger.debug(f"[任务{file_info.get('task_id')}] [_apply_rename_rules] 文件需要重命名: '{original_name}' -> '{new_name}'") # 添加调试日志
            # 创建一个新的字典，包含所有原始信息和更新后的名称/路径
            renamed_file_info = dict(file_info)
            renamed_file_info["file_name"] = new_name
            # 这里我们不直接修改 target_path，因为 target_path 指的是文件的父目录
            # 重命名操作会更新文件本身的名称，而不是它所在的目录
            renamed_file_info["new_full_path"] = new_path # 存储完整新路径用于rename参数
            return renamed_file_info
        
        # self.logger.debug(f"[任务{file_info.get('task_id')}] [_apply_rename_rules] 文件无需重命名") # 添加调试日志
        return None
    
    async def rename_file_item(
        self,
        x_token: str,
        drive_type: DriveType,
        file_info: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None, # 新增 stats 参数
        **kwargs
    ) -> bool:
        """执行单个文件的重命名操作并记录任务项"""
        # self.logger.debug(f"[任务{task_id}][rename_file_item] 开始处理文件重命名: {file_info.get('file_name', '')}") # 添加调试日志
        original_name = file_info.get("original_name", file_info.get("file_name", "")) # 获取原始名称
        new_name = file_info.get("file_name", original_name) # 获取新名称
        original_path = file_info.get("target_path", "")
        new_full_path = file_info.get("new_full_path", original_path.rstrip('/') + '/' + new_name)
        file_id = file_info.get("file_id", "")

        if not new_name or new_name == original_name: # 如果没有新名称或者名称没有改变，则直接返回成功
            # self.logger.debug(f"[任务{task_id}][rename_file_item] 无需重命名，名称未改变或为空") # 添加调试日志
            return True
            
        try:
            rename_params = RenameParam(
                drive_type=drive_type,
                file_id=file_id if file_id else None,
                file_path=original_path.rstrip('/') + '/' + original_name if not file_id else None,
                file_name=original_name, # 新增此行，补充原始文件名
                parent_id=file_info.get("parent_id", file_info.get("file_id")),
                new_path=new_full_path, # 新增此行，补充新的完整路径
                new_name=new_name
            )
            # self.logger.debug(f"[任务{task_id}][rename_file_item] 构建重命名参数: {rename_params.model_dump_json()}") # 添加调试日志
            
            self.logger.info(f"[任务{task_id}] 执行文件重命名: 从 '{original_name}' 到 '{new_name}'")
            # 调用 drive_manager 的重命名接口
            renamed_file_info = await self.drive_manager.rename_files(x_token, rename_params, **kwargs) # 移除 db=db
            # self.logger.debug(f"[任务{task_id}][rename_file_item] drive_manager.rename_files 结果: {renamed_file_info}") # 添加调试日志
            
            if renamed_file_info:
                self.logger.info(f"[任务{task_id}] 文件重命名成功: '{original_name}' -> '{new_name}'")
                if task_id and stats:
                    task_item = await self.record_task_item(
                        task_id, "rename", original_path, original_path, original_name, 
                        file_info.get("file_size", 0), "completed", None
                    )
                    stats["pending_task_items"].append(task_item) # 添加到待记录列表
                return True
            else:
                error_msg = f"文件重命名失败: API返回False, 源文件: {original_name}, 新名称: {new_name}"
                self.logger.error(f"[任务{task_id}] {error_msg}")
                if task_id and stats:
                    task_item = await self.record_task_item(
                        task_id, "rename", original_path, original_path, original_name, 
                        file_info.get("file_size", 0), "failed", error_msg
                    )
                    stats["pending_task_items"].append(task_item) # 添加到待记录列表
                return False
        except Exception as e:
            error_msg = f"执行重命名异常: {original_name} -> {new_name}, 错误: {e}"
            self.logger.error(f"[任务{task_id}] {error_msg}", exc_info=True)
            if task_id and stats:
                task_item = await self.record_task_item(
                    task_id, "rename", original_path, original_path, original_name, 
                    file_info.get("file_size", 0), "failed", error_msg
                )
                stats["pending_task_items"].append(task_item) # 添加到待记录列表
            return False

    async def perform_sync(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        sync_method: str,
        recursion_speed: RecursionSpeed = RecursionSpeed.NORMAL,
        exclude_rules: Optional[List[ExclusionRuleDefinition]] = None,
        max_depth: int = 100,
        task_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行同步 - 核心入口（对应alist的sync方法）
        
        Args:
            x_token: 认证令牌
            drive_type: 网盘类型
            source_definition: 源定义
            target_definition: 目标定义
            sync_method: 同步方式（incremental/full/overwrite）
            recursion_speed: 递归速度
            exclude_rules: 排除规则
            max_depth: 最大递归深度
            task_id: 任务ID
            db: 数据库会话
            
        Returns:
            Dict[str, Any]: 同步结果统计
        """
        start_perform_sync_time = time.time()
        
        # 解析过滤器
        item_filter = parse_exclusion_rules(exclude_rules) if exclude_rules else None
        
        # 同步统计
        stats = {
            "files_processed": 0,
            "folder_created": 0,
            "files_transferred": 0,
            "files_deleted": 0,
            "files_skipped": 0,
            "errors": [],
            "sync_method": sync_method,
            "start_time": datetime.fromtimestamp(start_perform_sync_time).isoformat(),
            "transferred_files_info": [], # 新增：用于存储成功转存的文件信息
            "pending_task_items": [], # 新增：用于收集待记录的任务项
        }
        # self.logger.info(f"[任务{task_id}] [perform_sync] stats初始化后 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志
        
        try:
            # 根据同步方式选择处理逻辑
            if sync_method == "overwrite":
                # self.logger.info(f"[任务{task_id or 'unknown'}] 采用覆盖同步模式")
                # self.logger.info(f"[任务{task_id}] [perform_sync] 调用 _handle_overwrite_sync 之前 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志
                await self._handle_overwrite_sync(
                    x_token, drive_type, source_definition, target_definition,
                    recursion_speed, item_filter, stats, task_id, db, account_key=account_key
                )
                # self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步逻辑执行完成。")
            else:
                # self.logger.info(f"[任务{task_id or 'unknown'}] 采用增量/完全同步模式")
                # self.logger.info(f"[任务{task_id}] [perform_sync] 调用 sync_with_have 之前 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志
                await self.sync_with_have(
                    x_token, drive_type, source_definition, target_definition,
                    source_definition.file_path, target_definition.file_path, target_definition.file_id,
                    sync_method, recursion_speed, item_filter, 0, max_depth, stats, task_id, db, account_key=account_key
                )
                # self.logger.info(f"[任务{task_id or 'unknown'}] 增量/完全同步逻辑执行完成。")
            
        except Exception as e:
            error_msg = f"同步失败: {str(e)}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)
        
        # 计算总耗时
        elapsed_time = time.time() - start_perform_sync_time
        stats["elapsed_time"] = elapsed_time
        stats["end_time"] = datetime.fromtimestamp(time.time()).isoformat()
        
        # 判断同步是否成功 - 有错误就是失败
        success = len(stats["errors"]) == 0
        
        # self.logger.info(f"[任务{task_id}] [perform_sync] 返回前 final transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志
        return {
            "success": success,
            "stats": stats,
            "error": stats["errors"][0] if stats["errors"] else None
        }
    
    async def sync_with_have(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_path: str,
        target_path: str,
        target_id: Optional[str],
        sync_method: str,
        recursion_speed: RecursionSpeed,
        item_filter: Optional[ItemFilter],
        current_depth: int,
        max_depth: int,
        stats: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        目标存在时的同步 - 对应alist的syncWithHave
        
        扫描并同步-目标目录存在（意味着要继续扫描目标目录）
        逻辑：
        1. 扫描源目录和目标目录
        2. 对比文件（文件名+大小）
        3. 处理差异文件和目录
        4. 如果是完全同步，删除目标多余文件
        """
        start_sync_with_have_time = time.time()
        
        if current_depth >= max_depth:
            self.logger.warning(f"[任务{task_id or 'unknown'}] 达到最大递归深度 {max_depth}，停止递归: {source_path}")
            return
        
        try:
            # 获取源文件和目标文件映射（文件名 -> 文件大小）
            source_file_map = await self.list_dir(
                source_path, True, item_filter, True, x_token, drive_type, source_definition, task_id=task_id, db=db, account_key=account_key
            )
            
            target_file_map = await self.list_dir(
                target_path, False, item_filter, False, x_token, drive_type, target_definition, target_id, task_id, db, account_key=account_key
            )
            
        except Exception as e:
            error_msg = f"扫描目录失败: {source_path} -> {target_path}, 错误: {str(e)}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)
            return

        files_to_transfer: List[Dict[str, Any]] = []
        files_to_delete: List[Dict[str, Any]] = []

        # 用于通过大小快速查找目标目录中尚未被源目录匹配的文件
        # 存储形式为 {file_size: [(file_name, file_info), ...] }
        unmatched_target_files_by_size: defaultdict[int, List[Tuple[str, Dict[str, Any]]]] = defaultdict(list)
        # 用于跟踪目标目录中已经被处理（匹配、修改或重命名）的项，防止重复或错误删除
        # 存储形式为 (文件名, 文件大小)
        processed_target_signatures: Set[Tuple[str, int]] = set()

        # 预处理目标文件信息，填充 unmatched_target_files_by_size
        for target_filename, target_file_info in target_file_map.items():
            if not target_filename.endswith('/'): # 只处理文件，不处理目录
                file_size = target_file_info.get("file_size", 0)
                unmatched_target_files_by_size[file_size].append((target_filename, target_file_info))

        # 处理源目录中的每个文件/目录
        for source_filename, source_file_info in source_file_map.items():
            source_is_folder = source_filename.endswith('/')
            source_size = source_file_info.get("file_size", 0) if not source_is_folder else 0
            
            item_handled = False # 标记当前源文件是否已被处理

            if source_is_folder:
                dir_name = source_filename.rstrip('/')
                source_sub_path = source_path.rstrip('/') + '/' + dir_name + '/'
                target_sub_path = target_path.rstrip('/') + '/' + dir_name + '/'

                # 目标目录没有这个目录
                if source_filename not in target_file_map:
                    await self.sync_without_have(
                        x_token, drive_type, source_definition, target_definition,
                        source_sub_path, target_sub_path,
                        sync_method, recursion_speed, item_filter, current_depth + 1, max_depth, stats, task_id, db, account_key=account_key
                    )
                # 目标目录有这个目录，继续递归
                else:
                    target_sub_file_id = target_file_map.get(source_filename, {}).get("file_id", "")
                    await self.sync_with_have(
                        x_token, drive_type, source_definition, target_definition,
                        source_sub_path, target_sub_path, target_sub_file_id,
                        sync_method, recursion_speed, item_filter, current_depth + 1, max_depth, stats, task_id, db, account_key=account_key
                    )
                
                # 标记目录为已处理。即使是新创建的，也不应被当作多余删除。
                # 这里需要检查目标目录中是否存在，因为 sync_without_have 会创建新目录，但不会在当前的 target_file_map 中。
                if source_filename in target_file_map:
                    processed_target_signatures.add((source_filename, 0)) # 目录大小为0
                
                item_handled = True # 目录处理完毕

            else: # 是文件
                stats["files_processed"] += 1

                target_file_info_in_map = target_file_map.get(source_filename)
                
                # 第一步：尝试文件名匹配（精确匹配 或 文件修改）
                if target_file_info_in_map and not target_file_info_in_map.get("is_folder", False):
                    target_size_by_name = target_file_info_in_map.get("file_size", -1)
                    
                    if source_size == target_size_by_name:
                        # 精确匹配 (文件名和大小都相同)
                        stats["files_skipped"] += 1
                        processed_target_signatures.add((source_filename, source_size))
                        item_handled = True
                    else:
                        # 文件已修改 (文件名相同，大小不同)
                        # 需要转存 (覆盖旧文件)
                        transfer_file_info = {
                            "file_name": source_filename,
                            "file_size": source_size,
                            "source_path": source_path,
                            "target_path": target_path,
                            "file_id": source_file_info.get("file_id", ""), # 源文件的ID
                            **{k: v for k, v in source_file_info.items() if k not in ["file_size", "file_id"]}
                        }
                        files_to_transfer.append(transfer_file_info)
                        processed_target_signatures.add((source_filename, target_size_by_name)) # 旧目标文件被"处理"了 (即将被覆盖)
                        item_handled = True

                    # 从 unmatched_target_files_by_size 中移除已处理的文件
                    if source_size in unmatched_target_files_by_size:
                        unmatched_target_files_by_size[source_size] = [
                            item for item in unmatched_target_files_by_size[source_size] if item[0] != source_filename
                        ]
                        if not unmatched_target_files_by_size[source_size]:
                            del unmatched_target_files_by_size[source_size]

                # 第二步：如果文件名不匹配，尝试大小匹配 (隐式重命名处理)
                if not item_handled and source_size in unmatched_target_files_by_size:
                    # 查找是否有相同大小但文件名不同的目标文件
                    found_rename_candidate = False
                    for i, (target_rename_filename, target_rename_file_info) in enumerate(list(unmatched_target_files_by_size[source_size])):
                        # 检查是否已经被 processed_target_signatures 标记，确保不重复匹配
                        if (target_rename_filename, source_size) not in processed_target_signatures:
                            # 找到一个重命名候选：文件名不同，大小相同，且未被处理
                            stats["files_skipped"] += 1 # 视为跳过，因为是重命名
                            processed_target_signatures.add((target_rename_filename, source_size))
                            
                            # 从查找列表中移除，确保这个目标文件不再被匹配
                            unmatched_target_files_by_size[source_size].pop(i)
                            
                            item_handled = True
                            found_rename_candidate = True
                            break # 找到一个匹配即可
                    if found_rename_candidate:
                        item_handled = True

                # 第三步：如果以上都未匹配，则为新文件
                if not item_handled:
                    transfer_file_info = {
                        "file_name": source_filename,
                        "file_size": source_size,
                        "source_path": source_path,
                        "target_path": target_path,
                        "file_id": source_file_info.get("file_id", ""), # 源文件的ID
                        **{k: v for k, v in source_file_info.items() if k not in ["file_size", "file_id"]}
                    }
                    files_to_transfer.append(transfer_file_info)

        # 批量转存当前目录下需要同步的文件
        if files_to_transfer:
            # self.logger.info(f"[任务{task_id or 'unknown'}] 批量转存当前目录 {len(files_to_transfer)} 个文件")
            transfer_start_time = time.time()
            # self.logger.info(f"[任务{task_id}] [sync_with_have] 调用 transfer_files 之前 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志
            transfer_result = await self.transfer_files(
                x_token, drive_type, source_definition, target_definition,
                files_to_transfer,
                recursion_speed, stats, task_id, db, account_key=account_key
            )
            # self.logger.info(f"[任务{task_id}] [sync_with_have] 调用 transfer_files 之后 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志
            # self.logger.info(f"[任务{task_id or 'unknown'}] 批量转存完成，成功: {transfer_result}, 耗时: {time.time() - transfer_start_time:.2f}秒")
            
            # 失败则跳过当前目录后续处理
            if not transfer_result:
                self.logger.warning(f"[任务{task_id or 'unknown'}] 批量转存失败，跳过当前目录后续处理: {target_path}")
                return
            if db: await db.commit() # 每次批量转存后提交

        # 如果是完全同步，删除目标目录中多余的文件
        if sync_method == "full":
            # 遍历目标目录中的所有项，找出未被 processed_target_signatures 标记的项进行删除
            for target_filename, target_file_info in target_file_map.items():
                target_is_folder = target_filename.endswith('/')
                target_size = target_file_info.get("file_size", 0) if not target_is_folder else 0
                target_signature = (target_filename, target_size)

                if target_signature not in processed_target_signatures:
                    # 这个目标项没有在源目录中找到匹配（精确匹配或大小匹配），也没有被修改，所以是多余的
                    files_to_delete.append({
                        "file_name": target_filename,
                        "file_size": target_size,
                        "target_path": target_path,
                        "file_id": target_file_info.get("file_id", "")
                    })
            
            if files_to_delete:
                # self.logger.info(f"[任务{task_id or 'unknown'}] 完全同步模式，需要删除 {len(files_to_delete)} 个多余文件")
                delete_start_time = time.time()
                await self.delete_files(
                    x_token, drive_type, target_definition, files_to_delete,
                    recursion_speed, stats, task_id, db, account_key=account_key
                )
                # self.logger.info(f"[任务{task_id or 'unknown'}] 批量删除完成，耗时: {time.time() - delete_start_time:.2f}秒")
                if db: await db.commit() # 每次批量删除后提交
        # self.logger.info(f"[任务{task_id or 'unknown'}] 目录 {source_path} ({target_path}) 的 sync_with_have 操作完成，耗时: {time.time() - start_sync_with_have_time:.2f}秒")
        # self.logger.info(f"[任务{task_id}] [sync_with_have] 返回前 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志

    async def sync_without_have(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_path: str,
        target_path: str,
        sync_method: str,
        recursion_speed: RecursionSpeed,
        item_filter: Optional[ItemFilter],
        current_depth: int,
        max_depth: int,
        stats: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        目标不存在时的同步 - 对应alist的syncWithOutHave
        
        扫描并同步-目标目录为空
        逻辑：
        1. 创建目标目录
        2. 扫描源目录
        3. 递归处理所有文件和子目录
        """
        start_sync_without_have_time = time.time()
        
        if current_depth >= max_depth:
            self.logger.warning(f"[任务{task_id or 'unknown'}] 达到最大递归深度 {max_depth}，停止递归: {source_path}")
            return
        
        # 创建目标目录
        dir_name = target_path.rstrip('/').split('/')[-1]
        create_dir_start_time = time.time()
        created_dir_info = await self.create_directory(
            x_token, drive_type, target_definition, dir_name, task_id, db, account_key=account_key
        )
        if not created_dir_info:
            error_msg = f"创建目录失败: {target_path}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}")
            stats["errors"].append(error_msg)
            return
        
        stats["folder_created"] += 1
        
        # 记录创建目录的任务项
        if task_id and stats:
            task_item = await self.record_task_item(
                task_id, "create", source_path, target_path, dir_name, 0, 
                "completed", None
            )
            stats["pending_task_items"].append(task_item) # 添加到待记录列表
        # if db: await db.commit() # 每次创建目录后提交，现在统一在最上层提交
        
        # 更新target_definition为新创建的目录
        target_definition = DiskTargetDefinition(
            file_path=target_path,
            file_id=created_dir_info.file_id
        )
        
        try:
            # 获取源目录文件列表
            source_file_map = await self.list_dir(
                source_path, True, item_filter, True, x_token, drive_type, source_definition, task_id=task_id, db=db, account_key=account_key
            )
        except Exception as e:
            error_msg = f"扫描源目录失败: {source_path}, 错误: {str(e)}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)
            return
        
        # 收集当前目录下的所有文件，用于批量转存
        files_to_transfer = []
        
        # 处理源目录中的每个文件/目录
        for file_name, file_info in source_file_map.items():
            if file_name.endswith('/'):
                # 递归处理子目录 - 确保路径正确拼接
                dir_name = file_name.rstrip('/')
                source_sub_path = source_path.rstrip('/') + '/' + dir_name + '/'
                target_sub_path = target_path.rstrip('/') + '/' + dir_name + '/'
                await self.sync_without_have(
                    x_token, drive_type, source_definition, target_definition,
                    source_sub_path, target_sub_path,
                    sync_method, recursion_speed, item_filter, current_depth + 1, max_depth, stats, task_id, db, account_key=account_key
                )
            else:
                # 收集文件信息，用于批量转存
                stats["files_processed"] += 1  # 增加文件处理计数
                source_file_size = file_info.get("file_size", 0)
                
                # 构建完整的文件信息，包含转存所需的所有参数
                transfer_file_info = {
                    "file_name": file_name,
                    "file_size": source_file_size,
                    "source_path": source_path,
                    "target_path": target_path,  # 使用当前目录的target_path
                    "file_id": file_info.get("file_id", ""),
                }
                
                # 添加扩展信息（msg_id, from_uk等）
                for key, value in file_info.items():
                    if key not in ["file_size", "file_id"]:
                        transfer_file_info[key] = value
                
                files_to_transfer.append(transfer_file_info)
        
        # 批量转存当前目录下的所有文件
        if files_to_transfer:
            # self.logger.info(f"[任务{task_id or 'unknown'}] 批量转存当前目录 {len(files_to_transfer)} 个文件")
            transfer_start_time = time.time()
            # self.logger.info(f"[任务{task_id}] [sync_without_have] 调用 transfer_files 之前 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志
            transfer_result = await self.transfer_files(
                x_token, drive_type, source_definition, target_definition,
                files_to_transfer,
                recursion_speed, stats, task_id, db, account_key=account_key
            )
            # self.logger.info(f"[任务{task_id}] [sync_without_have] 调用 transfer_files 之后 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志
            # self.logger.info(f"[任务{task_id or 'unknown'}] 批量转存完成，成功: {transfer_result}, 耗时: {time.time() - transfer_start_time:.2f}秒")
            
            if not transfer_result:
                self.logger.warning(f"[任务{task_id or 'unknown'}] 批量转存失败，跳过当前目录后续处理: {target_path}")
                return
            if db: await db.commit() # 每次批量转存后提交
        # self.logger.info(f"[任务{task_id or 'unknown'}] 目录 {source_path} ({target_path}) 的 sync_without_have 操作完成，耗时: {time.time() - start_sync_without_have_time:.2f}秒")
        # self.logger.info(f"[任务{task_id}] [sync_without_have] 返回前 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志

    async def list_dir(
        self,
        path: str,
        first_dst: bool,
        item_filter: Optional[ItemFilter],
        is_src: bool,
        x_token: str,
        drive_type: DriveType,
        definition,
        target_id: Optional[str] = None,
        task_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> Dict[str, Dict[str, Any]]:
        """
        列出目录 - 对应alist的listDir
        
        Args:
            path: 目录路径
            first_dst: 是否是第一个目标目录
            item_filter: 过滤器
            is_src: 是否是源目录
            x_token: 认证令牌
            drive_type: 网盘类型
            definition: 目录定义
            target_id: 目标ID
            task_id: 任务ID
            db: 数据库会话
            
        Returns:
            Dict[str, Dict[str, Any]]: 文件映射 {文件名: {file_size: 大小, file_id: ID, msg_id: 消息ID, from_uk: 分享者UK}}
        """
        start_list_dir_time = time.time()
        
        try:
            if is_src:
                # 获取源文件列表
                from backend.app.coulddrive.schema.file import ListShareFilesParam
                params = ListShareFilesParam(
                drive_type=drive_type,
                    source_type=definition.source_type,
                    source_id=definition.source_id,
                    file_path=path
                )
                
                files = await self.drive_manager.get_share_list(x_token, params, db=db, **kwargs)
                
            else:
                # 获取目标文件列表
                from backend.app.coulddrive.schema.file import ListFilesParam
                params = ListFilesParam(
                drive_type=drive_type,
                    file_path=path,
                    file_id=target_id or "",
                    desc=False,
                    name=False,
                    time=False,
                    size_sort=False
                )
                
                files = await self.drive_manager.get_disk_list(x_token, params, db=db, **kwargs)
                
            # 构建文件映射 {文件名: {file_size: 大小, file_id: ID, 扩展信息}}
            file_map = {}
            for file in files:
                # 应用过滤器
                if item_filter and item_filter.should_exclude(file):
                    self.logger.debug(f"[任务{task_id or 'unknown'}] 文件被过滤器排除: {file.file_name}")
                    continue
                
                # 目录以/结尾，文件不以/结尾
                file_name = file.file_name + '/' if getattr(file, 'is_folder', False) else file.file_name
                file_size = file.file_size if not getattr(file, 'is_folder', False) else 0
                
                # 构建完整的文件信息
                file_info = {
                    "file_size": file_size,
                    "file_id": file.file_id,
                }
                
                # 对于源文件，添加扩展信息（msg_id, from_uk等）
                if is_src and hasattr(file, 'file_ext') and file.file_ext:
                    file_info.update(file.file_ext)
                
                file_map[file_name] = file_info
            
            return file_map
            
        except Exception as e:
            error_msg = f"扫描目录失败: {path}, 错误: {str(e)}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}", exc_info=True)
            raise e
    
    async def transfer_files(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        files: List[Dict[str, Any]],
        recursion_speed: RecursionSpeed,
        stats: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        批量转存文件 - 构建正确的扩展参数对应关系
        
        Args:
            files: 文件列表，格式：[{"file_name": "xxx", "file_size": 123, "source_path": "xxx", "target_path": "xxx", "file_id": "xxx", "share_fid_token": "xxx", ...}]
        """
        if not files:
            self.logger.info(f"[任务{task_id or 'unknown'}] 没有文件需要转存，跳过批量转存。")
            return True
        
        try:
            # 提取文件ID列表
            file_ids = []
            for file_info in files:
                file_id = file_info.get("file_id", "")
                if not file_id:
                    error_msg = f"文件 {file_info.get('file_name', '')} 缺少file_id"
                    self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}")
                    stats["errors"].append(error_msg)
                    if task_id and stats:
                        task_item = await self.record_task_item(
                            task_id, "copy", file_info.get("source_path", ""), file_info.get("target_path", ""),
                            file_info.get("file_name", ""), file_info.get("file_size", 0), "failed", error_msg
                        )
                        stats["pending_task_items"].append(task_item) # 添加到待记录列表
                    return False
                file_ids.append(file_id)
            
            # 构建扩展参数：基础参数 + 文件特定参数
            ext_params = dict(source_definition.ext_params) if source_definition.ext_params else {}
            
            # 为每个文件构建扩展信息，确保每个文件都有各自的扩展参数
            files_ext_info = []
            for file_info in files:
                file_ext_info = {
                    'file_id': file_info.get('file_id'),
                    'file_ext': {}
                }
                
                # 提取文件级别的扩展参数
                for key, value in file_info.items():
                    if key not in ["file_size", "file_id"]:
                        file_ext_info['file_ext'][key] = value
                
                files_ext_info.append(file_ext_info)
            
            # 将文件扩展信息添加到参数中
            ext_params['files_ext_info'] = files_ext_info
            
            # 如果第一个文件有扩展参数，也合并其基础信息（保持向后兼容）
            if files:
                first_file = files[0]
                for key, value in first_file.items():
                    if key not in ["file_name", "file_size", "source_path", "target_path", "file_id"]:
                        ext_params[key] = value
            
            # 构建转存参数
            from backend.app.coulddrive.schema.file import TransferParam
            params = TransferParam(
                drive_type=drive_type,
                source_type=source_definition.source_type,
                source_id=source_definition.source_id,
                source_path=first_file.get("source_path", ""),
                target_path=first_file.get("target_path", target_definition.file_path),
                target_id=target_definition.file_id,
                file_ids=file_ids,
                ext=ext_params
            )
            
            self.logger.info(f"[任务{task_id}] 执行文件转存（已由上层获取账户锁）")
            transfer_result = await self.drive_manager.transfer_files(x_token, params, **kwargs)
            # 写后安静期，等待上游平台落盘/索引收敛
            await asyncio.sleep(2)
            
            if transfer_result:
                stats["files_transferred"] += len(files)
                self.logger.info(f"[任务{task_id or 'unknown'}] 批量转存成功: {len(files)} 个文件")
                
                # 记录成功的文件
                for file_info in files:
                    # stats["transferred_files_info"].append(file_info) # 收集成功转存的文件信息
                    # self.logger.info(f"[任务{task_id}] [transfer_files] 添加文件后 transferred_files_info: {stats['transferred_files_info']}") # 添加调试日志

                    if task_id and stats:
                        task_item = await self.record_task_item(
                            task_id, "copy", file_info.get("source_path", ""), file_info.get("target_path", ""),
                            file_info.get("file_name", ""), file_info.get("file_size", 0), "completed", None
                        )
                        stats["pending_task_items"].append(task_item) # 添加到待记录列表

                # ========== 解决 file not found 问题 ========== #
                # 重新获取目标目录的最新文件列表，以获取转存后的正确file_id
                current_target_file_map = await self.list_dir(
                    target_definition.file_path, False, None, False,
                    x_token, drive_type, target_definition, target_definition.file_id,
                    task_id, db, account_key=account_key # 这里需要 db, account_key
                )
                
                # 更新 stats["transferred_files_info"] 中的文件file_id
                for original_file_info in files:
                    original_file_name = original_file_info.get("file_name", "")
                    # 处理目录的情况，list_dir 返回的目录名是带 '/' 的
                    search_name = original_file_name + '/' if original_file_info.get("is_folder") else original_file_name

                    if search_name in current_target_file_map:
                        new_file_info_from_target = current_target_file_map[search_name]
                        updated_file_info = dict(original_file_info) # 复制一份，避免修改原始数据
                        updated_file_info["file_id"] = new_file_info_from_target.get("file_id", original_file_info.get("file_id"))
                        updated_file_info["parent_id"] = target_definition.file_id # 更新 parent_id 为目标目录ID
                        stats["transferred_files_info"].append(updated_file_info) # 收集成功转存并更新ID的文件信息
                        self.logger.debug(f"[任务{task_id}] [transfer_files] 更新文件ID并添加到 transferred_files_info: {updated_file_info.get('file_name')}, new_id: {updated_file_info.get('file_id')}")
                    else:
                        self.logger.warning(f"[任务{task_id}] [transfer_files] 未在目标目录找到转存后的文件: {original_file_name}")
                        # 如果找不到，仍然将原始文件信息添加到 transferred_files_info，但可能ID是旧的或空的
                        stats["transferred_files_info"].append(original_file_info)
                # ========== 解决 file not found 问题 ========== #

            else:
                error_msg = f"批量转存失败：API返回False，涉及 {len(files)} 个文件"
                self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}")
                stats["errors"].append(error_msg)
                
                # 记录失败的文件
                for file_info in files:
                    if task_id and stats:
                        task_item = await self.record_task_item(
                            task_id, "copy", file_info.get("source_path", ""), file_info.get("target_path", ""),
                            file_info.get("file_name", ""), file_info.get("file_size", 0), "failed", error_msg
                        )
                        stats["pending_task_items"].append(task_item) # 添加到待记录列表
            
            # 速度控制
            if recursion_speed == RecursionSpeed.SLOW:
                await asyncio.sleep(2)
            elif recursion_speed == RecursionSpeed.NORMAL:
                await asyncio.sleep(1)
            # 快速模式不暂停
            
            return transfer_result
            
        except Exception as e:
            error_msg = f"批量转存异常: {str(e)}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)
            
            # 记录所有文件失败
            for file_info in files:
                if task_id and stats:
                    task_item = await self.record_task_item(
                        task_id, "copy", file_info.get("source_path", ""), file_info.get("target_path", ""),
                        file_info.get("file_name", ""), file_info.get("file_size", 0), "failed", error_msg
                    )
                    stats["pending_task_items"].append(task_item) # 添加到待记录列表
            
            return False
    
    async def delete_files(
        self,
        x_token: str,
        drive_type: DriveType,
        target_definition: DiskTargetDefinition,
        files: List[Dict[str, Any]],
        recursion_speed: RecursionSpeed,
        stats: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        批量删除文件 - 保持技术优势
        
        Args:
            files: 文件列表，格式：[{"file_name": "xxx", "file_size": 123, "target_path": "xxx"}]
        """
        if not files:
            self.logger.info(f"[任务{task_id or 'unknown'}] 没有文件需要删除，跳过批量删除。")
            return True
            
        try:
            # 批量删除文件
            from backend.app.coulddrive.schema.file import RemoveParam
            
            # 构建正确的文件路径和ID
            file_paths = []
            file_ids = []
            for file_info in files:
                # 确保路径正确拼接，避免出现 '/测试全店会员资源获取群.jpg' 这种情况
                target_path = file_info["target_path"].rstrip('/')
                file_name = file_info["file_name"]
                full_path = target_path + '/' + file_name
                file_paths.append(full_path)
                
                # 如果有file_id，也添加到file_ids中
                if "file_id" in file_info and file_info["file_id"]:
                    file_ids.append(file_info["file_id"])
            
            params = RemoveParam(
                drive_type=drive_type,
                file_paths=file_paths if file_paths else None,
                file_ids=file_ids if file_ids else None,  # 优先使用file_ids
                parent_id=target_definition.file_id,
                file_name=None  # 批量删除时不需要单个文件名
            )
            
            self.logger.info(f"[任务{task_id}] 执行文件删除（已由上层获取账户锁）")
            result = await self.drive_manager.remove_files(x_token, params, db=db, **kwargs)
            
            if result:
                stats["files_deleted"] += len(files)
                self.logger.info(f"[任务{task_id or 'unknown'}] 批量删除成功: {len(files)} 个文件")
                
                # 记录删除的文件
                for file_info in files:
                    # self.logger.info(f"删除成功: {file_info['file_name']}")
                    # 记录任务项
                    if task_id and stats:
                        task_item = await self.record_task_item(
                            task_id, "delete", "", file_info["target_path"],
                            file_info["file_name"], file_info["file_size"], "completed", None
                        )
                        stats["pending_task_items"].append(task_item) # 添加到待记录列表
            else:
                error_msg = f"批量删除失败，涉及 {len(files)} 个文件"
                self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}")
                stats["errors"].append(error_msg)
                # 记录失败的文件
                for file_info in files:
                    if task_id and stats:
                        task_item = await self.record_task_item(
                            task_id, "delete", "", file_info["target_path"],
                            file_info["file_name"], file_info["file_size"], "failed", error_msg
                        )
                        stats["pending_task_items"].append(task_item) # 添加到待记录列表
            
            # 速度控制
            if recursion_speed == RecursionSpeed.SLOW:
                await asyncio.sleep(3)
            elif recursion_speed == RecursionSpeed.NORMAL:
                await asyncio.sleep(1)
            # 快速模式不暂停
            
            return result
            
        except Exception as e:
            error_msg = str(e)  # 直接使用异常信息
            self.logger.error(f"[任务{task_id or 'unknown'}] 批量删除文件失败: {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)  # 直接传递具体错误信息
            
            # 记录失败的文件
            for file_info in files:
                if task_id and stats:
                    task_item = await self.record_task_item(
                        task_id, "delete", "", file_info["target_path"],
                        file_info["file_name"], file_info["file_size"], "failed", error_msg
                    )
                    stats["pending_task_items"].append(task_item) # 添加到待记录列表
            
            return False
    
    async def create_directory(
        self,
        x_token: str,
        drive_type: DriveType,
        target_definition: DiskTargetDefinition,
        dir_name: str,
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        **kwargs
    ) -> Optional[BaseFileInfo]:
        """
        创建目录
        
        Args:
            dir_name: 目录名
            
        Returns:
            BaseFileInfo: 创建的目录信息，失败时返回None
        """
        try:
            # 创建目录
            from backend.app.coulddrive.schema.file import MkdirParam
            params = MkdirParam(
                drive_type=drive_type,
                file_path=target_definition.file_path,
                file_name=dir_name,
                parent_id=target_definition.file_id,
                return_if_exist=True
            )
            self.logger.info(f"[任务{task_id}] 无需创建目录锁，直接执行创建")
            result = await self.drive_manager.create_mkdir(x_token, params, db=db, **kwargs)
            
            # create_mkdir返回BaseFileInfo对象，如果成功创建则有file_id
            if result is not None and result.file_id is not None:
                self.logger.info(f"[任务{task_id or 'unknown'}] 成功创建目录: {dir_name}, file_id: {result.file_id}")
                return result
            else:
                self.logger.error(f"[任务{task_id or 'unknown'}] 创建目录失败: {dir_name}, API返回结果: {result}")
                return None
            
        except Exception as e:
            self.logger.error(f"[任务{task_id or 'unknown'}] 创建目录异常: {dir_name}, 错误: {e}")
            return None

    async def rename_files(
        self,
        x_token: str,
        drive_type: DriveType,
        transferred_files_info: List[Dict[str, Any]],
        rename_rules: Optional[List[RenameRule]],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        在同步完成后执行文件重命名操作
        它会遍历所有成功转存的文件，对它们应用重命名规则，并执行实际的重命名操作。
        
        Args:
            x_token: 认证令牌
            drive_type: 网盘类型
            transferred_files_info: 成功转存的文件信息列表
            rename_rules: 重命名规则列表
            task_id: 任务ID
            db: 数据库会话
            account_key: 账户锁键
        """
        if not rename_rules or not transferred_files_info:
            self.logger.info(f"[任务{task_id}] 无重命名规则或无文件可重命名，跳过重命名操作。")
            return

        self.logger.info(f"[任务{task_id}] 开始执行重命名操作，共有 {len(transferred_files_info)} 个文件待检查")
        files_to_rename = []

        # 遍历所有转存成功的文件，应用重命名规则
        for file_info in transferred_files_info:
            # _apply_rename_rules 返回的是一个包含新名称和路径的新字典，如果未重命名则返回 None
            renamed_info = self._apply_rename_rules(file_info, rename_rules)
            if renamed_info:
                # 存储原始名称用于任务记录
                renamed_info["original_name"] = file_info.get("file_name", "")
                files_to_rename.append(renamed_info)
        
        # 异步并行执行重命名操作
        if files_to_rename:
            self.logger.info(f"[任务{task_id}] 发现 {len(files_to_rename)} 个文件需要重命名")
            rename_tasks = [
                self.rename_file_item(x_token, drive_type, file_info, task_id, db, account_key=account_key)
                for file_info in files_to_rename
            ]
            await asyncio.gather(*rename_tasks)
            if db: await db.commit() # 每次批量重命名后提交
        else:
            self.logger.info(f"[任务{task_id}] 没有文件符合重命名条件")

    async def record_task_item(
        self,
        task_id: int,
        operation_type: str,
        src_path: str,
        dst_path: str,
        file_name: str,
        file_size: int,
        status: str,
        err_msg: Optional[str]
    ) -> CreateSyncTaskItemParam:
        """
        记录任务项 - 学习alist的详细记录方式
        
        Args:
            task_id: 任务ID
            operation_type: 操作类型（transfer/delete/create_dir）
            src_path: 源路径
            dst_path: 目标路径
            file_name: 文件名
            file_size: 文件大小
            status: 状态（pending/running/completed/failed/skipped）
            err_msg: 错误信息
        
        Returns:
            CreateSyncTaskItemParam: 任务项参数对象
        """
        try:
            task_item_params = CreateSyncTaskItemParam(
                task_id=task_id,
                type=operation_type,
                src_path=src_path,
                dst_path=dst_path,
                file_name=file_name,
                file_size=file_size,
                status=status,
                err_msg=err_msg
            )
            
            # await sync_task_item_dao.create(db, obj_in=task_item_params)
            # 注意：这里不提交事务，由上层统一提交
            # self.logger.debug(f"[任务{task_id}] 记录任务项成功: 类型={operation_type}, 文件={file_name}, 状态={status}")
            return task_item_params # 返回任务项参数对象
            
        except Exception as e:
            self.logger.error(f"[任务{task_id}] 记录任务项失败: {e}", exc_info=True)
            # 如果记录任务项本身失败，返回一个带错误的任务项，或者让上层处理
            return CreateSyncTaskItemParam(
                task_id=task_id,
                type=operation_type,
                src_path=src_path,
                dst_path=dst_path,
                file_name=file_name,
                file_size=file_size,
                status="failed",
                err_msg=f"记录任务项失败: {e}"
            )
    
    async def _handle_overwrite_sync(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        recursion_speed: RecursionSpeed,
        item_filter: Optional[ItemFilter],
        stats: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        处理覆盖同步：先删除目标目录所有文件，再一次性转存源目录所有内容
        """
        start_overwrite_sync_time = time.time()
        self.logger.info(f"[任务{task_id or 'unknown'}] 开始覆盖同步: 源={source_definition.file_path}, 目标={target_definition.file_path}")
        try:
            # 1. 获取目标目录所有文件
            self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：开始扫描目标目录进行删除前准备")
            target_file_map = await self.list_dir(
                target_definition.file_path, False, item_filter, False, 
                x_token, drive_type, target_definition, target_definition.file_id, task_id, db, account_key=account_key
            )
            self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：目标目录扫描完成，耗时: {time.time() - start_overwrite_sync_time:.2f}秒，找到 {len(target_file_map)} 个文件/目录")
            
            # 2. 删除目标目录所有文件
            if target_file_map:
                files_to_delete = []
                for file_name, file_info in target_file_map.items():
                    files_to_delete.append({
                        "file_name": file_name,
                        "file_size": file_info.get("file_size", 0),
                        "target_path": target_definition.file_path,
                        "file_id": file_info.get("file_id", "")
                    })
                self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：开始批量删除 {len(files_to_delete)} 个文件/目录")
                delete_start_time = time.time()
                await self.delete_files(
                    x_token, drive_type, target_definition, files_to_delete,
                    recursion_speed, stats, task_id, db, account_key=account_key
                )
                self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：批量删除完成，耗时: {time.time() - delete_start_time:.2f}秒")
                if db: await db.commit() # 每次批量删除后提交
            else:
                self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：目标目录为空，无需删除。")
            
            # 3. 一次性转存整个源目录的所有内容
            self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：开始扫描源目录进行转存准备")
            source_file_map = await self.list_dir(
                source_definition.file_path, True, item_filter, True, 
                x_token, drive_type, source_definition, task_id=task_id, db=db, account_key=account_key
            )
            self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：源目录扫描完成，耗时: {time.time() - start_overwrite_sync_time:.2f}秒，找到 {len(source_file_map)} 个文件/目录")
            
            if source_file_map:
                # 构建所有文件的转存信息（包括文件和目录）
                all_files_to_transfer = []
                for file_name, file_info in source_file_map.items():
                    file_size = file_info.get("file_size", 0)
                    transfer_file_info = {
                        "file_name": file_name,
                        "file_size": file_size,
                        "source_path": source_definition.file_path,
                        "target_path": target_definition.file_path,
                        "file_id": file_info.get("file_id", ""),
                    }
                    
                    # 添加扩展信息（msg_id, from_uk等）
                    for key, value in file_info.items():
                        if key not in ["file_size", "file_id"]:
                            transfer_file_info[key] = value
                    
                    all_files_to_transfer.append(transfer_file_info)
                    stats["files_processed"] += 1
                
                self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：开始批量转存 {len(all_files_to_transfer)} 个项目")
                transfer_start_time = time.time()
                transfer_result = await self.transfer_files(
                    x_token, drive_type, source_definition, target_definition,
                    all_files_to_transfer, recursion_speed, stats, task_id, db, account_key=account_key
                )
                self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：批量转存完成，成功: {transfer_result}, 耗时: {time.time() - transfer_start_time:.2f}秒")
                
                if not transfer_result:
                    self.logger.warning(f"[任务{task_id or 'unknown'}] 覆盖同步批量转存失败，终止当前覆盖流程: {target_definition.file_path}")
                    self.logger.info(f"[任务{task_id or 'unknown'}] 退出 _handle_overwrite_sync (因批量转存失败), 耗时: {time.time() - start_overwrite_sync_time:.2f}秒")
                    return
                if db: await db.commit() # 每次批量转存后提交
            else:
                self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：源目录为空，无需转存。")
                
        except Exception as e:
            error_msg = f"覆盖同步失败: {str(e)}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)
        
        self.logger.info(f"[任务{task_id or 'unknown'}] 退出 _handle_overwrite_sync, 耗时: {time.time() - start_overwrite_sync_time:.2f}秒")

# 全局实例
file_sync_service = FileSyncService()


def get_file_sync_service() -> FileSyncService:
    """获取文件同步服务实例"""
    return file_sync_service