#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import re
import time
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Pattern, Tuple, Set
from pathlib import PurePosixPath

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.model.filesync import SyncConfig, SyncTask, SyncTaskItem
from backend.app.coulddrive.schema.enum import DriveType, ItemType, MatchMode, MatchTarget, RecursionSpeed, SyncMethod
from backend.app.coulddrive.schema.file import (
    BaseFileInfo,
    DiskTargetDefinition,
    ExclusionRuleDefinition,
    ListFilesParam,
    ListShareFilesParam,
    MkdirParam,
    RemoveParam,
    RenameRuleDefinition,
    ShareSourceDefinition,
    TransferParam,
)
from backend.app.coulddrive.schema.filesync import (
    GetSyncConfigDetail, 
    CreateSyncTaskParam, 
    GetSyncTaskDetail,
    GetSyncTaskWithRelationDetail,
    GetSyncTaskItemDetail,
    UpdateSyncTaskParam,
    UpdateSyncConfigParam,
)
from backend.app.coulddrive.schema.user import GetDriveAccountDetail
from backend.app.coulddrive.crud.crud_filesync import sync_task_dao, sync_task_item_dao, sync_config_dao
from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.crud.crud_rule_template import rule_template_dao
from backend.database.db import async_db_session
from backend.common.log import log

logger = logging.getLogger(__name__)

class FileSyncService:
    """文件同步服务 - 仅保留数据库操作和工具方法"""
    
    def __init__(self):
        """初始化文件同步服务"""
        pass
    
    def _parse_sync_method(self, method_str: str) -> str:
        """解析同步方式
        
        Args:
            method_str: 同步方式字符串
            
        Returns:
            str: 标准化的同步方式
        """
        method_lower = method_str.lower() if method_str else ""
        
        if method_lower == SyncMethod.INCREMENTAL.value:
            return SyncMethod.INCREMENTAL.value
        elif method_lower == SyncMethod.FULL.value:
            return SyncMethod.FULL.value
        elif method_lower == SyncMethod.OVERWRITE.value:
            return SyncMethod.OVERWRITE.value
        else:
            logger.warning(f"未知的同步方式: {method_str}，使用默认增量同步")
            return SyncMethod.INCREMENTAL.value

    def _parse_recursion_speed(self, speed_value: int) -> RecursionSpeed:
        """解析递归速度
        
        Args:
            speed_value: 速度值（0-2）
            
        Returns:
            RecursionSpeed: 递归速度枚举
        """
        if speed_value == 1:
            return RecursionSpeed.SLOW
        elif speed_value == 2:
            return RecursionSpeed.FAST
        else:
            return RecursionSpeed.NORMAL

    async def _parse_rule_templates(
        self, 
        exclude_template_id: Optional[int], 
        rename_template_id: Optional[int],
        db: AsyncSession
    ) -> Tuple[Optional[List[ExclusionRuleDefinition]], Optional[List[RenameRuleDefinition]]]:
        """
        解析规则模板
        
        Args:
            exclude_template_id: 排除规则模板ID
            rename_template_id: 重命名规则模板ID
            db: 数据库会话
            
        Returns:
            Tuple[Optional[List[ExclusionRuleDefinition]], Optional[List[RenameRuleDefinition]]]: 排除规则和重命名规则
        """
        exclude_rules = None
        rename_rules = None
        
        # 解析排除规则模板
        if exclude_template_id:
            try:
                exclude_template = await rule_template_dao.get(db, exclude_template_id)
                if exclude_template and exclude_template.rule_config:
                    rules_data = exclude_template.rule_config
                    # 如果rule_config是字符串，需要解析JSON
                    if isinstance(rules_data, str):
                        rules_data = json.loads(rules_data)
                    
                    # 根据实际数据格式解析规则
                    rules_list = rules_data.get('rules', [])
                    if rules_list:
                        exclude_rules = [
                            ExclusionRuleDefinition(**rule) for rule in rules_list
                        ]
            except Exception as e:
                logger.error(f"解析排除规则模板失败: {e}")
        
        # 解析重命名规则模板
        if rename_template_id:
            try:
                rename_template = await rule_template_dao.get(db, rename_template_id)
                if rename_template and rename_template.rule_config:
                    rules_data = rename_template.rule_config
                    # 如果rule_config是字符串，需要解析JSON
                    if isinstance(rules_data, str):
                        rules_data = json.loads(rules_data)
                    
                    # 根据实际数据格式解析规则
                    rules_list = rules_data.get('rules', [])
                    if rules_list:
                        rename_rules = [
                            RenameRuleDefinition(**rule) for rule in rules_list
                        ]
            except Exception as e:
                logger.error(f"解析重命名规则模板失败: {e}")
        
        return exclude_rules, rename_rules



    async def execute_sync_by_config_id(self, config_id: int, db: AsyncSession) -> Dict[str, Any]:
        """
        根据配置ID执行同步任务
        
        Args:
            config_id: 同步配置ID
            db: 数据库会话
            
        Returns:
            Dict[str, Any]: 执行结果，包含 success、task_id、stats、elapsed_time 等字段
        """
        start_time = time.time()
        task_id = None
        
        try:
            # 获取并验证配置
            config, error_msg = await sync_config_dao.get_with_validation(db, config_id)
            if not config:
                return {
                    "success": False,
                    "error": error_msg,
                    "config_id": config_id,
                    "elapsed_time": 0
                }
            
            # 检查任务是否过期
            current_time = datetime.now()
            if config.end_time and current_time > config.end_time:
                return {
                    "success": True,
                    "message": f"同步任务已过期，截止时间: {config.end_time}",
                    "config_id": config_id,
                    "elapsed_time": 0,
                    "stats": {
                        "processed": 0,
                        "transferred": 0,
                        "deleted": 0,
                        "skipped": 0,
                        "errors": 0
                    }
                }
            
            # 获取网盘账户信息
            drive_account = await drive_account_dao.get(db, config.user_id)
            if not drive_account:
                return {
                    "success": False,
                    "error": f"网盘账户 {config.user_id} 不存在",
                    "config_id": config_id,
                    "elapsed_time": 0
                }
            
            # 创建同步任务记录
            task_params = CreateSyncTaskParam(
                config_id=config_id,
                start_time=datetime.now(),
                status="running"
            )
            sync_task = await sync_task_dao.create(db, obj_in=task_params, current_user_id=config.created_by)
            task_id = sync_task.id
            
            # 解析配置参数
            sync_method = self._parse_sync_method(config.method)
            recursion_speed = self._parse_recursion_speed(config.speed)
            
            # 解析规则模板
            exclude_rules, rename_rules = await self._parse_rule_templates(
                config.exclude_template_id,
                config.rename_template_id,
                db
            )
            
            # 解析源和目标定义
            src_meta = json.loads(config.src_meta) if config.src_meta else {}
            dst_meta = json.loads(config.dst_meta) if config.dst_meta else {}
            
            # 构建源定义
            source_definition = ShareSourceDefinition(
                source_type=src_meta.get("source_type", ""),
                source_id=src_meta.get("source_id", ""),
                file_path=config.src_path,  # 使用配置中的源路径
                ext_params=src_meta.get("ext_params", {})
            )
            
            # 构建目标定义
            if not config.dst_path:
                raise ValueError("目标路径不能为空，请检查同步配置中的目标路径设置")
            
            target_definition = DiskTargetDefinition(
                file_path=config.dst_path,
                file_id=dst_meta.get("file_id", ""),
                drive_type=DriveType(drive_account.type)
            )
            
            # 执行分层同步
            layered_sync_service = get_layered_sync_service()
            sync_result = await layered_sync_service.perform_layered_sync(
                x_token=drive_account.cookies,
                drive_type=DriveType(drive_account.type),
                source_definition=source_definition,
                target_definition=target_definition,
                sync_method=sync_method,
                recursion_speed=recursion_speed,
                exclude_rules=exclude_rules,
                max_depth=100,
                task_id=task_id,
                db=db
            )
            
            # 计算执行时间
            elapsed_time = int(time.time() - start_time)
            
            # 更新任务状态
            if sync_result.get("success", False):
                # 更新任务为成功状态
                update_params = UpdateSyncTaskParam(
                    status="completed",
                    dura_time=elapsed_time,
                    task_num=json.dumps(sync_result.get("stats", {}))
                )
                await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)
                
                # 更新配置的最后同步时间
                config_update = UpdateSyncConfigParam(last_sync=datetime.now())
                await sync_config_dao.update(db, db_obj=config, obj_in=config_update)
                
                return {
                    "success": True,
                    "task_id": task_id,
                    "config_id": config_id,
                    "stats": sync_result.get("stats", {}),
                    "elapsed_time": elapsed_time,
                    "message": "同步任务执行成功"
                }
            else:
                # 更新任务为失败状态
                error_msg = sync_result.get("error", "未知错误")
                update_params = UpdateSyncTaskParam(
                    status="failed",
                    start_time=datetime.now(),
                    dura_time=elapsed_time,
                    err_msg=error_msg,
                    task_num=json.dumps(sync_result.get("stats", {}))
                )
                await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)
                
                return {
                    "success": False,
                    "task_id": task_id,
                    "config_id": config_id,
                    "error": error_msg,
                    "stats": sync_result.get("stats", {}),
                    "elapsed_time": elapsed_time
                }
                
        except Exception as e:
            error_msg = f"执行同步任务时发生异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # 如果有任务ID，更新任务状态为错误
            if task_id:
                try:
                    elapsed_time = int(time.time() - start_time)
                    update_params = UpdateSyncTaskParam(
                        status="failed",
                        dura_time=elapsed_time,
                        err_msg=error_msg
                    )
                    sync_task = await sync_task_dao.select_model(db, task_id)
                    if sync_task:
                        await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)
                except Exception as update_error:
                    logger.error(f"更新任务状态失败: {update_error}")
            
            return {
                "success": False,
                "task_id": task_id,
                "config_id": config_id,
                "error": error_msg,
                "elapsed_time": int(time.time() - start_time)
            }


class LayeredSyncService:
    """
    分层同步服务 - 边扫描边处理模式
    
    实现类似 Alist 的同步逻辑：
    1. 按目录层级递归处理
    2. 边扫描边对比边处理
    3. 内存友好，不预加载整个目录树
    4. 即时执行操作，提供实时进度
    """
    
    def __init__(self):
        """初始化分层同步服务"""
        from backend.app.coulddrive.service.yp_service import get_drive_manager
        self.drive_manager = get_drive_manager()
        self.logger = log
        
    async def perform_layered_sync(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        sync_method: str,  # "incremental", "full", "overwrite"
        recursion_speed: RecursionSpeed = RecursionSpeed.NORMAL,
        exclude_rules: Optional[List[ExclusionRuleDefinition]] = None,
        max_depth: int = 100,
        task_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行分层同步
        
        Args:
            x_token: 认证令牌
            drive_type: 网盘类型
            source_definition: 源定义
            target_definition: 目标定义
            sync_method: 同步方式
                - "incremental": 增量同步 - 只新增文件，不删除
                - "full": 完全同步 - 新增文件+删除多余文件
                - "overwrite": 覆盖同步 - 覆盖已存在文件
            recursion_speed: 递归速度
            exclude_rules: 排除规则
            max_depth: 最大递归深度
            task_id: 任务ID
            db: 数据库会话
            **kwargs: 其他参数
            
        Returns:
            Dict[str, Any]: 同步结果统计
        """
        start_time = time.time()
        
        # 解析过滤器
        item_filter = _parse_exclusion_rules(exclude_rules) if exclude_rules else None
        
        # 同步统计
        stats = {
            "files_processed": 0,
            "folder_created": 0,
            "files_transferred": 0,  # 使用 transferred 而不是 copied
            "files_deleted": 0,
            "files_skipped": 0,
            "errors": [],
            "sync_method": sync_method,
            "start_time": datetime.fromtimestamp(start_time).isoformat(),
        }
        
        # 打印开始同步的详细信息
        #self.logger.info(f"🚀 开始分层同步 - 方式: {sync_method}, 源: {source_definition.file_path}, 目标: {target_definition.file_path}")
        
        try:
            # 根据同步方式选择不同的处理逻辑
            if sync_method == "overwrite":
                # 覆盖同步：先删除目标目录所有文件，再转存源目录所有文件
                await self._handle_overwrite_sync(
                    x_token=x_token,
                    drive_type=drive_type,
                    source_definition=source_definition,
                    target_definition=target_definition,
                    source_path=source_definition.file_path,
                    target_path=target_definition.file_path,
                    target_id=target_definition.file_id,
                    recursion_speed=recursion_speed,
                    item_filter=item_filter,
                    current_depth=0,
                    max_depth=max_depth,
                    stats=stats,
                    task_id=task_id,
                    db=db,
                    **kwargs
                )
            else:
                # 增量同步和完全同步：使用普通的递归同步逻辑
                await self._sync_with_have(
                    x_token=x_token,
                    drive_type=drive_type,
                    source_definition=source_definition,
                    target_definition=target_definition,
                    source_path=source_definition.file_path,
                    target_path=target_definition.file_path,
                    target_id=target_definition.file_id,
                    sync_method=sync_method,
                    recursion_speed=recursion_speed,
                    item_filter=item_filter,
                    current_depth=0,
                    max_depth=max_depth,
                    stats=stats,
                    task_id=task_id,
                    db=db,
                    **kwargs
                )
            
        except Exception as e:
            self.logger.error(f"分层同步过程中发生错误: {e}")
            stats["errors"].append(f"同步失败: {str(e)}")
        
        # 计算总耗时
        elapsed_time = time.time() - start_time
        stats["elapsed_time"] = elapsed_time
        stats["end_time"] = datetime.fromtimestamp(time.time()).isoformat()
        
        # 判断同步是否成功（没有错误即为成功）
        success = len(stats["errors"]) == 0
        
        #self.logger.info(f"✅ 分层同步完成，耗时 {elapsed_time:.2f}s，统计: {stats}")
        
        return {
            "success": success,
            "stats": stats,
            "error": stats["errors"][0] if stats["errors"] else None
        }
    
    async def _sync_with_have(
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
        **kwargs
    ) -> None:
        """
        处理目标目录存在的情况（对应 Alist 的 syncWithHave）
        
        Args:
            x_token: 认证令牌
            drive_type: 网盘类型
            source_definition: 源定义
            target_definition: 目标定义
            source_path: 源路径
            target_path: 目标路径
            target_id: 目标ID
            sync_method: 同步方法
            recursion_speed: 递归速度
            item_filter: 过滤器
            current_depth: 当前深度
            max_depth: 最大深度
            stats: 统计信息
            task_id: 任务ID
            db: 数据库会话
            **kwargs: 其他参数
        """
        if current_depth >= max_depth:
            return
        
        # 获取源目录和目标目录的文件列表
        #self.logger.info(f"📂 正在扫描目录 - 源: {source_path}")
        source_files = await self._get_source_files_single_layer(
            x_token, drive_type, source_definition, source_path, item_filter, db, **kwargs
        )
        
        #self.logger.info(f"📁 正在扫描目录 - 目标: {target_path}")
        target_files = await self._get_target_files_single_layer(
            x_token, drive_type, target_definition, target_path, target_id, item_filter, db, **kwargs
        )
        
        #self.logger.info(f"📊 扫描结果 - 源文件: {len(source_files)}个, 目标文件: {len(target_files)}个")
        
        # 创建目标文件映射
        target_file_map = {file.file_name: file for file in target_files}
        
        # 分离文件和目录
        source_files_to_transfer = []
        source_dirs_to_process = []
        
        for source_file in source_files:
            stats["files_processed"] += 1
            
            if source_file.is_folder:
                source_dirs_to_process.append(source_file)
            else:
                # 判断是否需要转存文件
                if source_file.file_name not in target_file_map:
                    source_files_to_transfer.append(source_file)
                else:
                    stats["files_skipped"] += 1
                    self.logger.debug(f"文件已存在，跳过: {source_file.file_name}")
        
        # 批量转存文件
        if source_files_to_transfer:
            # 使用当前层级的目标路径，而不是根目标路径
            current_target_path = target_path  # 使用当前实际的目标路径
            
            #self.logger.info(f"📤 开始批量转存 {len(source_files_to_transfer)} 个文件: {[f.file_name for f in source_files_to_transfer]}")
            success = await self._batch_transfer_files(
                x_token=x_token,
                drive_type=drive_type,
                source_definition=source_definition,
                target_definition=DiskTargetDefinition(
                    file_path=current_target_path,  # 使用当前层级路径
                    file_id=target_id,
                    drive_type=drive_type
                ),
                source_files=source_files_to_transfer,
                recursion_speed=recursion_speed,
                task_id=task_id,
                db=db,
                **kwargs
            )
            
            if success:
                stats["files_transferred"] += len(source_files_to_transfer)
                #self.logger.info(f"✅ 批量转存成功: {len(source_files_to_transfer)} 个文件")
            else:
                error_msg = f"❌ 批量转存失败: {len(source_files_to_transfer)} 个文件"
                self.logger.error(error_msg)
                stats["errors"].append(error_msg)
        
        # 处理目录（逐个递归）
        for source_file in source_dirs_to_process:
            await self._handle_source_directory(
                x_token=x_token,
                drive_type=drive_type,
                source_definition=source_definition,
                target_definition=DiskTargetDefinition(
                    file_path=target_path,  # 使用当前层级的完整路径
                    file_id=target_id,
                    drive_type=drive_type
                ),
                source_file=source_file,
                target_file_map=target_file_map,
                sync_method=sync_method,
                recursion_speed=recursion_speed,
                item_filter=item_filter,
                current_depth=current_depth,
                max_depth=max_depth,
                stats=stats,
                task_id=task_id,
                db=db,
                **kwargs
            )
        # 注意：source_files_to_transfer 中的文件已经在上面的批量转存中处理过了
        # 这里不需要再次处理，避免重复转存
        # 如果需要单独处理某些文件的特殊逻辑，应该在批量转存之外单独识别
        
        # 完全同步模式：删除目标目录中多余的文件
        if sync_method == "full":
            await self._handle_target_cleanup_batch(
                x_token=x_token,
                drive_type=drive_type,
                target_definition=target_definition,
                source_files=source_files,
                target_files=target_files,
                recursion_speed=recursion_speed,
                stats=stats,
                task_id=task_id,
                db=db,  # 添加缺失的db参数
                **kwargs
            )

    async def _get_source_files_single_layer(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        source_path: str,
        item_filter: Optional[ItemFilter],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> List[BaseFileInfo]:
        """获取源目录单层文件列表"""
        params = ListShareFilesParam(
            drive_type=drive_type,
            source_type=source_definition.source_type,
            source_id=source_definition.source_id,
            file_path=source_path
        )
        
        files = await self.drive_manager.get_share_list(
            x_token, params, db=db, **kwargs
        )
        
        # 应用排除规则过滤器
        if item_filter:
            filtered_files = []
            for file in files:
                if not item_filter.should_exclude(file):
                    filtered_files.append(file)
                else:
                    self.logger.debug(f"排除规则匹配，跳过文件: {file.file_name}")
            files = filtered_files
        
        return files
    
    async def _get_target_files_single_layer(
        self,
        x_token: str,
        drive_type: DriveType,
        target_definition: DiskTargetDefinition,
        target_path: str,
        target_id: Optional[str],
        item_filter: Optional[ItemFilter],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> List[BaseFileInfo]:
        """获取目标目录单层文件列表"""
        params = ListFilesParam(
            drive_type=drive_type,
            file_path=target_path,
            file_id=target_id or "",
            desc=False,
            name=False,
            time=False,
            size_sort=False
        )
        
        files = await self.drive_manager.get_disk_list(
            x_token, params, db=db, **kwargs
        )
        
        # 应用排除规则过滤器（对目标文件也过滤，用于一致性）
        if item_filter:
            filtered_files = []
            for file in files:
                if not item_filter.should_exclude(file):
                    filtered_files.append(file)
                else:
                    self.logger.debug(f"排除规则匹配，跳过目标文件: {file.file_name}")
            files = filtered_files
        
        self.logger.debug(f"获取目标目录 {target_path} 文件列表: {len(files)} 个项目")
        return files
    
    async def _handle_source_directory(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_file: BaseFileInfo,
        target_file_map: Dict[str, BaseFileInfo],
        sync_method: str,
        recursion_speed: RecursionSpeed,
        item_filter: Optional[ItemFilter],
        current_depth: int,
        max_depth: int,
        stats: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> None:
        """处理源目录"""
        target_file = target_file_map.get(source_file.file_name)
        
        if target_file and target_file.is_folder:
            # 目标目录存在，递归同步
            self.logger.info(f"📁 目标目录存在，递归同步: {source_file.file_name}")
            
            await self._sync_with_have(
                x_token=x_token,
                drive_type=drive_type,
                source_definition=source_definition,
                target_definition=target_definition,
                source_path=source_file.file_path,
                target_path=target_file.file_path,
                target_id=target_file.file_id,
                sync_method=sync_method,
                recursion_speed=recursion_speed,
                item_filter=item_filter,
                current_depth=current_depth + 1,
                max_depth=max_depth,
                stats=stats,
                task_id=task_id,
                db=db,
                **kwargs
            )
        else:
            # 创建目标目录
            #self.logger.info(f"📁 目录不存在，需要创建")
            target_dir_path = f"{target_definition.file_path}/{source_file.file_name}"  # 使用target_definition中的路径
            
            success = await self._create_directory(
                x_token=x_token,
                drive_type=drive_type,
                target_definition=target_definition,  # 直接使用传入的target_definition
                dir_name=source_file.file_name,
                task_id=task_id,  # 添加缺失的task_id参数
                db=db,
                **kwargs
            )
            
            if success:
                stats["folder_created"] += 1
                #self.logger.info(f"📁 目录创建成功: {target_dir_path}")
                
                # 创建目录成功后，直接递归处理目录内的所有内容
                #self.logger.info(f"🔄 开始递归处理新创建目录的内容: {source_file.file_name}")
                await self._sync_with_have(
                    x_token=x_token,
                    drive_type=drive_type,
                    source_definition=source_definition,
                    target_definition=DiskTargetDefinition(
                        file_path=target_dir_path,  # 使用新创建的完整目录路径
                        file_id="",  # 新创建的目录可能没有 ID
                        drive_type=drive_type
                    ),
                    source_path=source_file.file_path,  # 源目录路径
                    target_path=target_dir_path,        # 新创建的目标目录路径
                    target_id="",                       # 新创建的目录ID
                    sync_method=sync_method,
                    recursion_speed=recursion_speed,
                    item_filter=item_filter,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                    stats=stats,
                    task_id=task_id,
                    db=db,
                    **kwargs
                )
            else:
                error_msg = f"创建目录失败: {target_dir_path}"
                stats["errors"].append(error_msg)
                self.logger.error(error_msg)
    
    async def _handle_source_file(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_file: BaseFileInfo,
        target_file_map: Dict[str, BaseFileInfo],
        sync_method: str,
        recursion_speed: RecursionSpeed,
        stats: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> None:
        """处理源文件"""
        target_file = target_file_map.get(source_file.file_name)
        
        # 检查文件是否需要转存
        need_transfer = True
        
        if target_file and not target_file.is_folder:
            if sync_method == "incremental":
                # 增量同步：目标文件存在且大小相同，跳过
                if target_file.file_size == source_file.file_size:
                    need_transfer = False
                    stats["files_skipped"] += 1
                    self.logger.debug(f"增量同步：文件已存在且大小相同，跳过: {source_file.file_name}")
            elif sync_method == "overwrite":
                # 覆盖同步：总是转存文件（覆盖模式在外层已处理目录清理）
                need_transfer = True
                self.logger.debug(f"覆盖同步：强制转存文件: {source_file.file_name}")
            elif sync_method == "full":
                # 完全同步：文件存在且大小相同，跳过
                if target_file.file_size == source_file.file_size:
                    need_transfer = False
                    stats["files_skipped"] += 1
                    self.logger.debug(f"完全同步：文件已存在且大小相同，跳过: {source_file.file_name}")
        
        if need_transfer:
            # 需要转存文件
            expected_dst_path = f"{target_definition.file_path}/{source_file.file_name}"
            
            success = await self._transfer_file(
                x_token=x_token,
                drive_type=drive_type,
                source_definition=source_definition,
                target_definition=target_definition,
                source_file=source_file,
                recursion_speed=recursion_speed,
                task_id=task_id,
                db=db,
                **kwargs
            )
            
            if success:
                stats["files_transferred"] += 1
                self.logger.debug(f"文件转存成功: {source_file.file_name}")
            else:
                error_msg = f"文件转存失败: {source_file.file_name}"
                stats["errors"].append(error_msg)
                self.logger.error(error_msg)
    
    async def _sync_without_have(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_file: BaseFileInfo,
        sync_method: str,
        recursion_speed: RecursionSpeed,
        item_filter: Optional[ItemFilter],
        current_depth: int,
        max_depth: int,
        stats: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> None:
        """
        同步无目标目录的情况（对应 Alist 的 syncWithOutHave）
        先创建目录，然后转存所有内容
        """
        if current_depth >= max_depth:
            return
        
        # 1. 先创建目标目录
        target_dir_path = f"{target_definition.file_path.rstrip('/')}/{source_file.file_name}"
        
        success = await self._create_directory(
            x_token=x_token,
            drive_type=drive_type,
            target_definition=target_definition,
            dir_name=source_file.file_name,
            task_id=task_id,
            db=db,
            **kwargs
        )
        
        if not success:
            error_msg = f"创建目录失败: {target_dir_path}"
            stats["errors"].append(error_msg)
            self.logger.error(error_msg)
            return
        
        stats["folder_created"] += 1
        
        # 2. 扫描源目录内容
        source_children = await self._get_source_files_single_layer(
            x_token, drive_type, source_definition, source_file.file_path, item_filter, db, **kwargs
        )
        
        # 3. 递归转存所有内容
        for child_file in source_children:
            stats["files_processed"] += 1
            
            if child_file.is_folder:
                # 递归处理子目录 - 使用新创建的目录作为目标路径
                await self._sync_without_have(
                    x_token=x_token,
                    drive_type=drive_type,
                    source_definition=source_definition,
                    target_definition=DiskTargetDefinition(
                        file_path=target_dir_path,  # 使用新创建的完整目录路径
                        file_id="",  # 新创建的目录可能没有 ID
                        drive_type=drive_type
                    ),
                    source_file=child_file,
                    sync_method=sync_method,
                    recursion_speed=recursion_speed,
                    item_filter=item_filter,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                    stats=stats,
                    task_id=task_id,
                    db=db,
                    **kwargs
                )
            else:
                # 直接转存文件
                success = await self._transfer_file(
                    x_token=x_token,
                    drive_type=drive_type,
                    source_definition=source_definition,
                    target_definition=DiskTargetDefinition(
                        file_path=target_dir_path,
                        file_id=""
                    ),
                    source_file=child_file,
                    recursion_speed=recursion_speed,
                    task_id=task_id,
                    db=db,
                    **kwargs
                )
                
                if success:
                    stats["files_transferred"] += 1
                else:
                    error_msg = f"文件转存失败: {child_file.file_path}"
                    stats["errors"].append(error_msg)
    
    async def _handle_overwrite_sync(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_path: str,
        target_path: str,
        target_id: Optional[str],
        recursion_speed: RecursionSpeed,
        item_filter: Optional[ItemFilter],
        current_depth: int,
        max_depth: int,
        stats: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> None:
        """
        处理覆盖同步模式：
        1. 先批量删除目标目录的所有文件
        2. 然后批量转存源目录的所有文件（不递归，只转存当前层级）
        """
        if current_depth >= max_depth:
            return
        
        # 1. 获取目标目录的所有文件（用于删除）
        target_files = await self._get_target_files_single_layer(
            x_token, drive_type, target_definition, target_path, target_id, None, db, **kwargs
        )
        
        # 2. 批量删除目标目录的所有文件
        if target_files:
            success = await self._batch_delete_files(
                x_token=x_token,
                drive_type=drive_type,
                target_definition=target_definition,
                target_files=target_files,
                recursion_speed=recursion_speed,
                task_id=task_id,
                db=db,  # 添加缺失的db参数
                **kwargs
            )
            
            if success:
                stats["files_deleted"] += len(target_files)
                #self.logger.info(f"✅ 覆盖同步：批量删除成功: {len(target_files)} 个文件")
            else:
                error_msg = f"覆盖同步：批量删除失败: {len(target_files)} 个文件"
                stats["errors"].append(error_msg)
                self.logger.error(error_msg)
        else:
            self.logger.info("🔍 覆盖同步：目标目录为空，无需删除")
        
        # 3. 获取源目录的所有文件（用于转存）
        source_files = await self._get_source_files_single_layer(
            x_token, drive_type, source_definition, source_path, item_filter, db, **kwargs
        )
        
        if source_files:
            #self.logger.info(f"📁 覆盖同步：批量转存源目录 {source_path} 中的 {len(source_files)} 个文件")
            success = await self._batch_transfer_files(
                x_token=x_token,
                drive_type=drive_type,
                source_definition=source_definition,
                target_definition=target_definition,
                source_files=source_files,
                recursion_speed=recursion_speed,
                task_id=task_id,
                db=db,  # 传递db参数用于记录任务项
                **kwargs
            )
            
            if success:
                file_count = sum(1 for f in source_files if not f.is_folder)
                folder_count = sum(1 for f in source_files if f.is_folder)
                stats["files_transferred"] += file_count
                stats["folder_created"] += folder_count  # 目录也算作创建
                stats["files_processed"] += len(source_files)
                # self.logger.info(f"✅ 覆盖同步：批量转存成功，包含 {file_count} 个文件和 {folder_count} 个目录")
            else:
                error_msg = f"覆盖同步：批量转存失败: {source_path}"
                stats["errors"].append(error_msg)
                self.logger.error(error_msg)
        else:
            self.logger.info("🔍 覆盖同步：源目录为空，无需转存")

    async def _handle_target_cleanup_batch(
        self,
        x_token: str,
        drive_type: DriveType,
        target_definition: DiskTargetDefinition,
        source_files: List[BaseFileInfo],
        target_files: List[BaseFileInfo],
        recursion_speed: RecursionSpeed,
        stats: Dict[str, Any],
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> None:
        """批量处理目标目录清理（完全同步模式）"""
        # 创建源文件名集合
        source_names = {file.file_name for file in source_files}
        
        # 找出需要删除的文件
        files_to_delete = [
            target_file for target_file in target_files 
            if target_file.file_name not in source_names
        ]
        
        if files_to_delete:
            #self.logger.info(f"🗑️ 完全同步：需要删除 {len(files_to_delete)} 个多余文件")
            success = await self._batch_delete_files(
                x_token=x_token,
                drive_type=drive_type,
                target_definition=target_definition,
                target_files=files_to_delete,
                recursion_speed=recursion_speed,
                task_id=task_id,
                db=db,  # 传递db参数用于记录删除任务项
                **kwargs
            )
            
            if success:
                stats["files_deleted"] += len(files_to_delete)
                self.logger.debug(f"批量删除多余文件成功: {len(files_to_delete)} 个文件")
            else:
                error_msg = f"批量删除多余文件失败: {len(files_to_delete)} 个文件"
                stats["errors"].append(error_msg)
        else:
            self.logger.info("🔍 完全同步：未发现需要删除的多余文件")

    async def _apply_speed_control(self, recursion_speed: RecursionSpeed) -> None:
        """应用速度控制"""
        if recursion_speed == RecursionSpeed.SLOW:
            await asyncio.sleep(3)  # 慢速：3秒
        elif recursion_speed == RecursionSpeed.NORMAL:
            await asyncio.sleep(1)  # 正常：1秒
        # 快速模式不暂停

    async def _create_directory(
        self,
        x_token: str,
        drive_type: DriveType,
        target_definition: DiskTargetDefinition,
        dir_name: str,
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> bool:
        """创建目录"""
        try:
            params = MkdirParam(
                drive_type=drive_type,
                file_path=f"{target_definition.file_path.rstrip('/')}/{dir_name}",
                parent_id=target_definition.file_id or "",
                file_name=dir_name,
                return_if_exist=True
            )
            
            result = await self.drive_manager.create_mkdir(x_token, params)
            
            # 记录任务项
            if task_id and db:
                from backend.app.coulddrive.schema.filesync import CreateSyncTaskItemParam
                from backend.app.coulddrive.crud.crud_filesync import sync_task_item_dao
                
                item_param = CreateSyncTaskItemParam(
                    task_id=task_id,
                    type="create",  # 创建目录操作
                    src_path=f"{target_definition.file_path.rstrip('/')}/{dir_name}",
                    dst_path=f"{target_definition.file_path.rstrip('/')}/{dir_name}",
                    file_name=dir_name,
                    file_size=0,  # 目录大小为0
                    status="completed" if result else "failed",
                    err_msg=None if result else f"创建目录失败: {dir_name}"
                )
                try:
                    await sync_task_item_dao.create(db, obj_in=item_param)
                except Exception as e:
                    self.logger.error(f"创建目录任务项记录失败: {e}")
            
            if not result:
                # 记录详细的创建失败信息到日志，但不抛出异常
                target_path = f"{target_definition.file_path.rstrip('/')}/{dir_name}"
                self.logger.error(f"创建目录失败: {dir_name}, 目标路径: {target_path}")
                # 不抛出异常，让同步任务继续完成
            
            return True if result else False
        except Exception as e:
            self.logger.error(f"创建目录失败: {e}")
            
            # 记录失败的任务项
            if task_id and db:
                from backend.app.coulddrive.schema.filesync import CreateSyncTaskItemParam
                from backend.app.coulddrive.crud.crud_filesync import sync_task_item_dao
                
                item_param = CreateSyncTaskItemParam(
                    task_id=task_id,
                    type="create",
                    src_path=f"{target_definition.file_path.rstrip('/')}/{dir_name}",
                    dst_path=f"{target_definition.file_path.rstrip('/')}/{dir_name}",
                    file_name=dir_name,
                    file_size=0,
                    status="failed",
                    err_msg=str(e)
                )
                try:
                    await sync_task_item_dao.create(db, obj_in=item_param)
                except Exception as create_error:
                    self.logger.error(f"创建失败目录任务项记录失败: {create_error}")
            
            return False
    
    async def _batch_transfer_files(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_files: List[BaseFileInfo],
        recursion_speed: RecursionSpeed,
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> bool:
        """批量转存文件"""
        if not source_files:
            return True
        
        try:
            # 速度控制
            await self._apply_speed_control(recursion_speed)
            
            # 执行批量转存
            file_ids = [file.file_id for file in source_files]
            
            # 合并扩展参数：基础参数 + 文件特定参数
            ext_params = dict(source_definition.ext_params)
            if source_files and source_files[0].file_ext:
                ext_params.update(source_files[0].file_ext)
            
            params = TransferParam(
                drive_type=drive_type,
                source_type=source_definition.source_type,
                source_id=source_definition.source_id,
                source_path=source_definition.file_path,
                file_ids=file_ids,
                target_path=target_definition.file_path,
                target_id=target_definition.file_id,
                ext=ext_params
            )
            
            success = await self.drive_manager.transfer_files(x_token, params, **kwargs)
            
            # 记录任务项
            if task_id and db:
                from backend.app.coulddrive.schema.filesync import CreateSyncTaskItemParam
                from backend.app.coulddrive.crud.crud_filesync import sync_task_item_dao
                
                self.logger.debug(f"开始创建 {len(source_files)} 个文件的 add 类型任务项记录")
                
                for file in source_files:
                    expected_dst_path = f"{target_definition.file_path}/{file.file_name}"
                    
                    item_param = CreateSyncTaskItemParam(
                        task_id=task_id,
                        type="add",  # 转存操作
                        src_path=file.file_path,
                        dst_path=expected_dst_path,
                        file_name=file.file_name,
                        file_size=file.file_size or 0,  # 确保不为None
                        status="completed" if success else "failed",
                        err_msg=None if success else f"批量转存失败: {file.file_name}"
                    )
                    try:
                        await sync_task_item_dao.create(db, obj_in=item_param)
                        self.logger.debug(f"创建 add 任务项成功: {file.file_name}")
                    except Exception as e:
                        self.logger.error(f"创建 add 任务项记录失败: {file.file_name}, 错误: {e}")
            else:
                self.logger.debug(f"跳过任务项记录创建 - task_id: {task_id}, db: {db is not None}")
            
            if not success:
                # 记录详细的失败信息到日志，但不抛出异常
                failed_files = [{"file_name": f.file_name, "file_path": f.file_path, "file_id": f.file_id} for f in source_files]
                self.logger.error(f"批量转存失败，涉及文件: {failed_files}")
                # 不抛出异常，让同步任务继续完成
            
            return success
            
        except Exception as e:
            self.logger.error(f"批量转存文件失败: {e}")
            
            # 记录失败的任务项
            if task_id and db:
                from backend.app.coulddrive.schema.filesync import CreateSyncTaskItemParam
                from backend.app.coulddrive.crud.crud_filesync import sync_task_item_dao
                
                for file in source_files:
                    item_param = CreateSyncTaskItemParam(
                        task_id=task_id,
                        type="add",
                        src_path=file.file_path,
                        dst_path=f"{target_definition.file_path}/{file.file_name}",
                        file_name=file.file_name,
                        file_size=file.file_size,
                        status="failed",
                        err_msg=str(e)
                    )
                    try:
                        await sync_task_item_dao.create(db, obj_in=item_param)
                    except Exception as create_error:
                        self.logger.error(f"创建失败任务项记录失败: {create_error}")
            
            return False
    
    async def _batch_delete_files(
        self,
        x_token: str,
        drive_type: DriveType,
        target_definition: DiskTargetDefinition,
        target_files: List[BaseFileInfo],
        recursion_speed: RecursionSpeed,
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> bool:
        """批量删除文件"""
        if not target_files:
            return True
            
        try:
            # 提取所有文件路径和ID
            file_paths = [file.file_path for file in target_files]
            file_ids = [file.file_id for file in target_files if file.file_id]
            
            params = RemoveParam(
                drive_type=drive_type,
                file_paths=file_paths,
                file_ids=file_ids if file_ids else None,
                parent_id=target_definition.file_id
            )
            
            result = await self.drive_manager.remove_files(x_token, params)
            
            # 记录任务项
            if task_id and db:
                from backend.app.coulddrive.schema.filesync import CreateSyncTaskItemParam
                from backend.app.coulddrive.crud.crud_filesync import sync_task_item_dao
                
                self.logger.debug(f"开始创建 {len(target_files)} 个文件的 delete 类型任务项记录")
                
                for file in target_files:
                    item_param = CreateSyncTaskItemParam(
                        task_id=task_id,
                        type="delete",  # 删除操作
                        src_path=file.file_path,
                        dst_path=file.file_path,  # 删除操作源和目标路径相同
                        file_name=file.file_name,
                        file_size=file.file_size,
                        status="completed" if result else "failed",
                        err_msg=None if result else f"批量删除失败: {file.file_name}"
                    )
                    try:
                        await sync_task_item_dao.create(db, obj_in=item_param)
                        self.logger.debug(f"创建 delete 任务项成功: {file.file_name}")
                    except Exception as e:
                        self.logger.error(f"创建 delete 任务项记录失败: {file.file_name}, 错误: {e}")
            else:
                self.logger.debug(f"跳过删除任务项记录创建 - task_id: {task_id}, db: {db is not None}")
            
            if not result:
                # 记录详细的删除失败信息到日志，但不抛出异常
                failed_files = [{"file_name": f.file_name, "file_path": f.file_path, "file_id": f.file_id} for f in target_files]
                self.logger.error(f"批量删除失败，涉及文件: {failed_files}")
                # 不抛出异常，让同步任务继续完成
            
            # 根据递归速度控制暂停时间（批量操作只暂停一次）
            if recursion_speed == RecursionSpeed.SLOW:
                await asyncio.sleep(3)  # 慢速：3秒
            elif recursion_speed == RecursionSpeed.NORMAL:
                await asyncio.sleep(1)  # 正常：1秒
            # 快速模式不暂停
            
            return result
        except Exception as e:
            self.logger.error(f"批量删除文件失败: {e}")
            
            # 记录失败的任务项
            if task_id and db:
                from backend.app.coulddrive.schema.filesync import CreateSyncTaskItemParam
                from backend.app.coulddrive.crud.crud_filesync import sync_task_item_dao
                
                for file in target_files:
                    item_param = CreateSyncTaskItemParam(
                        task_id=task_id,
                        type="delete",
                        src_path=file.file_path,
                        dst_path=file.file_path,
                        file_name=file.file_name,
                        file_size=file.file_size,
                        status="failed",
                        err_msg=str(e)
                    )
                    try:
                        await sync_task_item_dao.create(db, obj_in=item_param)
                    except Exception as create_error:
                        self.logger.error(f"创建失败删除任务项记录失败: {create_error}")
            
            return False
    
    async def _transfer_entire_directory(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_path: str,
        recursion_speed: RecursionSpeed,
        task_id: Optional[int],
        **kwargs
    ) -> bool:
        """转存整个目录（覆盖同步专用）"""
        try:
            # 构建转存整个目录的参数
            params = TransferParam(
                drive_type=drive_type,
                source_type=source_definition.source_type,
                source_id=source_definition.source_id,
                source_path=source_path,
                target_path=target_definition.file_path,
                target_id=target_definition.file_id,
                file_ids=None,  # 不指定具体文件ID，表示转存整个目录
                ext={}
            )
            
            result = await self.drive_manager.transfer_files(x_token, params)
            
            if not result:
                # 记录详细的转存失败信息到日志，但不抛出异常
                self.logger.error(f"转存整个目录失败: {source_path} -> {target_definition.file_path}")
                # 不抛出异常，让同步任务继续完成
            
            # 根据递归速度控制暂停时间
            if recursion_speed == RecursionSpeed.SLOW:
                await asyncio.sleep(3)  # 慢速：3秒
            elif recursion_speed == RecursionSpeed.NORMAL:
                await asyncio.sleep(1)  # 正常：1秒
            # 快速模式不暂停
            
            return result
        except Exception as e:
            self.logger.error(f"转存整个目录失败: {e}")
            return False

    async def _transfer_file(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_file: BaseFileInfo,
        recursion_speed: RecursionSpeed,
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> bool:
        """转存单个文件（保留用于向后兼容）"""
        return await self._batch_transfer_files(
            x_token=x_token,
            drive_type=drive_type,
            source_definition=source_definition,
            target_definition=target_definition,
            source_files=[source_file],
            recursion_speed=recursion_speed,
            task_id=task_id,
            db=db,
            **kwargs
        )
    
    async def _delete_file(
        self,
        x_token: str,
        drive_type: DriveType,
        target_definition: DiskTargetDefinition,
        target_file: BaseFileInfo,
        recursion_speed: RecursionSpeed,
        **kwargs
    ) -> bool:
        """删除单个文件（保留用于向后兼容）"""
        return await self._batch_delete_files(
            x_token=x_token,
            drive_type=drive_type,
            target_definition=target_definition,
            target_files=[target_file],
            recursion_speed=recursion_speed,
            **kwargs
        )


class ExclusionRule:
    """排除规则类"""
    
    def __init__(self,
                 pattern: str,
                 target: MatchTarget = MatchTarget.NAME,
                 item_type: ItemType = ItemType.ANY,
                 mode: MatchMode = MatchMode.CONTAINS,
                 case_sensitive: bool = False):
        self.pattern = pattern
        self.target = target
        self.item_type = item_type
        self.mode = mode
        self.case_sensitive = case_sensitive
        
        # 预编译正则表达式（如果需要）
        if mode == MatchMode.REGEX:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                self.compiled_regex: Optional[Pattern] = re.compile(pattern, flags)
            except re.error as e:
                logger.error(f"Invalid regex pattern '{pattern}': {e}")
                # 如果正则表达式无效，回退到字符串匹配
                self.mode = MatchMode.CONTAINS
                self.compiled_regex = None
        else:
            self.compiled_regex = None

    def _get_value_to_match(self, item: BaseFileInfo) -> Optional[str]:
        """获取用于匹配的值"""
        if self.target == MatchTarget.NAME:
            return item.file_name
        elif self.target == MatchTarget.PATH:
            return item.file_path
        elif self.target == MatchTarget.EXTENSION:
            if '.' in item.file_name:
                return item.file_name.split('.')[-1]
            return ""
        return None

    def matches(self, item: BaseFileInfo) -> bool:
        """检查项目是否匹配规则"""
        # 1. Check item type
        if self.item_type != ItemType.ANY:
            if self.item_type == ItemType.FILE and item.is_folder:
                return False
            elif self.item_type == ItemType.FOLDER and not item.is_folder:
                return False
        
        # 2. Get value to match
        value = self._get_value_to_match(item)
        if value is None:
            return False
        
        # 3. Apply case sensitivity
        if not self.case_sensitive:
            value = value.lower()
            pattern = self.pattern.lower()
        else:
            pattern = self.pattern
        
        # 4. Match based on mode
        if self.mode == MatchMode.EXACT:
            return value == pattern
        elif self.mode == MatchMode.CONTAINS:
            return pattern in value
        elif self.mode == MatchMode.STARTS_WITH:
            return value.startswith(pattern)
        elif self.mode == MatchMode.ENDS_WITH:
            return value.endswith(pattern)
        elif self.mode == MatchMode.REGEX and self.compiled_regex:
            return bool(self.compiled_regex.search(value))
        
        return False


class ItemFilter:
    """项目过滤器"""
    
    def __init__(self, exclusion_rules: Optional[List[ExclusionRule]] = None):
        self.exclusion_rules = exclusion_rules or []

    def add_rule(self, rule: ExclusionRule):
        """添加排除规则"""
        self.exclusion_rules.append(rule)

    def should_exclude(self, item: BaseFileInfo) -> bool:
        """检查是否应该排除该项目"""
        for rule in self.exclusion_rules:
            if rule.matches(item):
                return True
        return False


class RenameRule:
    """重命名规则类"""
    
    def __init__(self,
                 match_regex: str,
                 replace_string: str,
                 target_scope: MatchTarget = MatchTarget.NAME,
                 case_sensitive: bool = False):
        self.match_regex = match_regex
        self.replace_string = replace_string
        self.target_scope = target_scope
        self.case_sensitive = case_sensitive
        
        # 预编译正则表达式
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            self.compiled_regex = re.compile(match_regex, flags)
        except re.error as e:
            logger.error(f"Invalid rename regex pattern '{match_regex}': {e}")
            self.compiled_regex = None

    def generate_new_path(self, item: BaseFileInfo) -> Optional[str]:
        """根据重命名规则生成新路径"""
        if self.compiled_regex is None:
            return None
        
        if self.target_scope == MatchTarget.NAME:
            # 只重命名文件名部分
            new_name = self.compiled_regex.sub(self.replace_string, item.file_name)
            if new_name != item.file_name:
                # 构建新的完整路径
                path_parts = item.file_path.rstrip('/').split('/')
                path_parts[-1] = new_name
                return '/'.join(path_parts)
        elif self.target_scope == MatchTarget.PATH:
            # 重命名整个路径
            new_path = self.compiled_regex.sub(self.replace_string, item.file_path)
            if new_path != item.file_path:
                return new_path
        
        return None


def _parse_exclusion_rules(rules_def: Optional[List[ExclusionRuleDefinition]]) -> Optional[ItemFilter]:
    """解析排除规则定义"""
    if not rules_def:
        return None
    
    exclusion_rules = []
    for rule_def in rules_def:
        try:
            rule = ExclusionRule(
                pattern=rule_def.pattern,
                target=MatchTarget(rule_def.target),
                item_type=ItemType(rule_def.item_type),
                mode=MatchMode(rule_def.mode),
                case_sensitive=rule_def.case_sensitive
            )
            exclusion_rules.append(rule)
        except (ValueError, AttributeError) as e:
            logger.error(f"解析排除规则失败: {rule_def} - {e}")
            continue
    
    if exclusion_rules:
        return ItemFilter(exclusion_rules)
    return None


def _parse_rename_rules(rules_def: Optional[List[RenameRuleDefinition]]) -> Optional[List[RenameRule]]:
    """解析重命名规则定义"""
    if not rules_def:
        return None
    
    rename_rules = []
    for rule_def in rules_def:
        try:
            rule = RenameRule(
                match_regex=rule_def.match_regex,
                replace_string=rule_def.replace_string,
                target_scope=MatchTarget(rule_def.target_scope),
                case_sensitive=rule_def.case_sensitive
            )
            rename_rules.append(rule)
        except (ValueError, AttributeError) as e:
            logger.error(f"解析重命名规则失败: {rule_def} - {e}")
            continue
    
    if rename_rules:
        return rename_rules
    return None


# 全局实例
file_sync_service = FileSyncService()
layered_sync_service = LayeredSyncService()


def get_file_sync_service() -> FileSyncService:
    """获取文件同步服务实例"""
    return file_sync_service


def get_layered_sync_service() -> LayeredSyncService:
    """获取分层同步服务实例"""
    return layered_sync_service 