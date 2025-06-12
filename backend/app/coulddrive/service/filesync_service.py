#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple, Union

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.model.filesync import SyncConfig, SyncTask, SyncTaskItem
from backend.app.coulddrive.schema.enum import DriveType, ItemType, MatchMode, MatchTarget, RecursionSpeed, SyncMethod
from backend.app.coulddrive.schema.file import (
    BaseFileInfo,
    DiskTargetDefinition,
    ExclusionRuleDefinition,
    GetCompareDetail,
    RenameRuleDefinition,
    ShareSourceDefinition,
    ListFilesParam,
    ListShareFilesParam,
    TransferParam,
    RemoveParam,
    MkdirParam,
)
from backend.app.coulddrive.schema.filesync import (
    GetSyncConfigDetail, 
    UpdateSyncConfigParam, 
    CreateSyncTaskParam, 
    UpdateSyncTaskParam, 
    CreateSyncTaskItemParam,
    GetSyncTaskDetail,
    GetSyncTaskWithRelationDetail,
    GetSyncTaskItemDetail
)
from backend.app.coulddrive.schema.user import GetDriveAccountDetail
from backend.app.coulddrive.service.yp_service import get_drive_manager
from backend.app.coulddrive.crud.crud_filesync import sync_task_dao, sync_task_item_dao, sync_config_dao
from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.crud.crud_rule_template import rule_template_dao
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)

class FileSyncService:
    """文件同步服务"""
    
    def __init__(self):
        """初始化文件同步服务"""
        # 移除重复的客户端缓存，直接使用全局管理器
        pass
    
    def _parse_sync_method(self, method_str: str) -> str:
        """解析同步方式
        
        Args:
            method_str: 同步方式字符串
            
        Returns:
            str: 标准化的同步方式
        """
        # 尝试匹配枚举值
        method_lower = method_str.lower() if method_str else ""
        
        if method_lower == SyncMethod.INCREMENTAL.value:
            return SyncMethod.INCREMENTAL.value
        elif method_lower == SyncMethod.FULL.value:
            return SyncMethod.FULL.value
        elif method_lower == SyncMethod.OVERWRITE.value:
            return SyncMethod.OVERWRITE.value
        else:
            # 默认使用增量同步
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
            # 默认使用正常速度
            return RecursionSpeed.NORMAL

    async def perform_sync(self, sync_config: GetSyncConfigDetail, db: AsyncSession = None) -> Dict[str, Any]:
        """执行同步任务
        
        Args:
            sync_config: 同步配置
            db: 数据库会话
            
        Returns:
            Dict[str, Any]: 同步结果
        """
        start_time = time.time()
        logger.info(f"开始执行同步任务: {sync_config.id} - {sync_config.remark or '未命名任务'}")
        
        # 创建同步任务记录
        sync_task = None
        if db:
            task_param = CreateSyncTaskParam(
                config_id=sync_config.id,
                status="running",
                start_time=datetime.now()
            )
            sync_task = await sync_task_dao.create(db, obj_in=task_param, current_user_id=getattr(sync_config, 'created_by', 1))
            await db.commit()
        
        account_schema: Optional[GetDriveAccountDetail] = None
        
        logger.info(f"尝试根据user_id={sync_config.user_id}从数据库获取账号")
        if db:
            account_schema = await drive_account_dao.get(db, sync_config.user_id)
        else:
            async with async_db_session() as temp_db:
                account_schema = await drive_account_dao.get(temp_db, sync_config.user_id)
            
        if not account_schema:
            error_msg = f"未找到ID为{sync_config.user_id}的账号，无法执行同步任务"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }
        
        logger.info(f"成功获取到账号: {account_schema.username or account_schema.user_id} (ID: {account_schema.id})")
        
        # 验证账号和配置关系
        if sync_config.user_id != account_schema.id:
            error_msg = f"严重的内部错误: 同步配置 {sync_config.id} 的账号ID({sync_config.user_id})与获取到的账号ID({account_schema.id})不匹配"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }
        
        # 验证账号参数
        if not hasattr(account_schema, "cookies") or not account_schema.cookies:
            error_msg = f"账号 {account_schema.id} 缺少cookies字段，无法执行同步"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }
        
        # 验证账号类型
        if not hasattr(account_schema, "type") or not account_schema.type:
            error_msg = f"账号 {account_schema.id} 缺少type字段，无法确定网盘类型"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }
        
        # 获取全局网盘管理器
        drive_manager = get_drive_manager()
        
        try:
            # 解析源信息
            src_meta = {}
            if sync_config.src_meta:
                try:
                    src_meta = json.loads(sync_config.src_meta)
                except json.JSONDecodeError:
                    logger.warning(f"解析源元数据失败: {sync_config.src_meta}")
            
            # 解析目标信息
            dst_meta = {}
            if sync_config.dst_meta:
                try:
                    dst_meta = json.loads(sync_config.dst_meta)
                except json.JSONDecodeError:
                    logger.warning(f"解析目标元数据失败: {sync_config.dst_meta}")
            
            # 解析规则模板
            exclude_rules, rename_rules = await self._parse_rule_templates(
                exclude_template_id=sync_config.exclude_template_id,
                rename_template_id=sync_config.rename_template_id,
                db=db
            )
            
            # 解析同步方式和递归速度
            sync_method = self._parse_sync_method(sync_config.method.value if hasattr(sync_config.method, 'value') else str(sync_config.method))
            recursion_speed = self._parse_recursion_speed(sync_config.speed)
            
            # 构建源定义
            source_definition = ShareSourceDefinition(
                source_type=src_meta.get("source_type", "friend"),
                source_id=src_meta.get("source_id", ""),
                file_path=sync_config.src_path,
                ext_params=src_meta.get("ext_params", {})
            )
            
            # 构建目标定义
            target_definition = DiskTargetDefinition(
                file_path=sync_config.dst_path,
                file_id=dst_meta.get("file_id", "")
            )
            
            # 获取网盘类型字符串
            if isinstance(sync_config.type, DriveType):
                drive_type_str = sync_config.type.value
            else:
                # 如果是字符串，直接使用
                drive_type_str = sync_config.type
            
            # 执行比较逻辑
            comparison_result = await perform_comparison_logic(
                drive_manager=drive_manager,
                x_token=account_schema.cookies,
                source_definition=source_definition,
                target_definition=target_definition,
                recursive=True,  # 始终递归处理
                recursion_speed=recursion_speed,
                comparison_mode=sync_method,
                exclude_rules_def=exclude_rules,
                rename_rules_def=rename_rules,
                drive_type_str=drive_type_str
            )
            
            # 应用比较结果
            operation_results = await apply_comparison_operations(
                drive_manager=drive_manager,
                x_token=account_schema.cookies,
                comparison_result=comparison_result,
                drive_type_str=drive_type_str,
                sync_mode=sync_method
            )
            
            # 计算统计数据
            stats = {
                "added_success": len(operation_results.get("add", {}).get("succeeded", [])),
                "added_fail": len(operation_results.get("add", {}).get("failed", [])),
                "deleted_success": len(operation_results.get("delete", {}).get("succeeded", [])),
                "deleted_fail": len(operation_results.get("delete", {}).get("failed", [])),
                "to_add_total": len(comparison_result.to_add),
                "to_delete_total": len(comparison_result.to_delete_from_target),
                "source_list_num": comparison_result.source_list_num,
                "target_list_num": comparison_result.target_list_num,
                "sync_method": sync_method,
                "recursion_speed": recursion_speed.value
            }
            
            elapsed_time = time.time() - start_time
            
            # 更新同步任务状态为成功
            if sync_task and db:
                task_update = UpdateSyncTaskParam(
                    status="completed",
                    dura_time=int(elapsed_time),
                    task_num=f"添加:{stats['added_success']}/{stats['to_add_total']}, 删除:{stats['deleted_success']}/{stats['to_delete_total']}"
                )
                await sync_task_dao.update(db, db_obj=sync_task, obj_in=task_update)
                
                # 创建任务项记录
                for result_type, results in operation_results.items():
                    for status, items in results.items():
                        for item_desc in items:
                            # 解析操作描述
                            parts = item_desc.split(": ")
                            if len(parts) >= 2:
                                operation_info = parts[1]
                                if " -> " in operation_info:
                                    src_path, dst_path = operation_info.split(" -> ", 1)
                                else:
                                    src_path = operation_info
                                    dst_path = operation_info
                                
                                file_name = src_path.split("/")[-1] if "/" in src_path else src_path
                                
                                item_param = CreateSyncTaskItemParam(
                                    task_id=sync_task.id,
                                    type=result_type,
                                    src_path=src_path,
                                    dst_path=dst_path,
                                    file_name=file_name,
                                    status="completed" if "SUCCESS" in item_desc else "failed",
                                    err_msg=item_desc if "ERROR" in item_desc or "FAIL" in item_desc else None
                                )
                                await sync_task_item_dao.create(db, obj_in=item_param)
                
                await db.commit()
            
            return {
                "success": True,
                "stats": stats,
                "details": operation_results,
                "elapsed_time": elapsed_time,
                "task_id": sync_task.id if sync_task else None
            }
            
        except Exception as e:
            # 更新同步任务状态为失败
            if sync_task and db:
                task_update = UpdateSyncTaskParam(
                    status="failed",
                    dura_time=int(time.time() - start_time),
                    err_msg=str(e)
                )
                await sync_task_dao.update(db, db_obj=sync_task, obj_in=task_update)
                await db.commit()
            
            return {
                "success": False,
                "error": f"同步任务执行失败: {str(e)}",
                "elapsed_time": time.time() - start_time,
                "task_id": sync_task.id if sync_task else None
            }

    async def execute_sync_by_config_id(self, config_id: int, db: AsyncSession) -> Dict[str, Any]:
        """根据配置ID执行同步任务"""
        # 使用 CRUD 层的验证方法
        sync_config, error_msg = await sync_config_dao.get_with_validation(db, config_id)
        if not sync_config:
            return {"success": False, "error": error_msg}
        
        if error_msg:  # 配置存在但被禁用
            return {"success": False, "error": error_msg}
        
        # 内联转换数据库模型到详情 Schema
        def get_drive_type_from_db_value(db_value: str) -> DriveType:
            """从数据库值获取 DriveType 枚举"""
            try:
                return DriveType[db_value]
            except KeyError:
                for drive_type in DriveType:
                    if drive_type.value == db_value:
                        return drive_type
                raise ValueError(f"无效的网盘类型: {db_value}，支持的类型: {[dt.value for dt in DriveType]}")
        
        # 使用字典方式创建 schema 对象，确保 field_validator 生效
        try:
            # 将 SQLAlchemy 对象转换为字典，触发 field_validator
            sync_config_dict = {
                'id': sync_config.id,
                'enable': sync_config.enable,
                'remark': sync_config.remark,
                'type': sync_config.type,  # 让 field_validator 处理类型转换
                'src_path': sync_config.src_path,
                'src_meta': sync_config.src_meta,
                'dst_path': sync_config.dst_path,
                'dst_meta': sync_config.dst_meta,
                'user_id': sync_config.user_id,
                'cron': sync_config.cron,
                'speed': sync_config.speed,
                'method': sync_config.method,  # 让 field_validator 处理类型转换
                'end_time': sync_config.end_time,
                'exclude_template_id': sync_config.exclude_template_id,
                'rename_template_id': sync_config.rename_template_id,
                'last_sync': sync_config.last_sync,
                'created_time': sync_config.created_time,
                'updated_time': sync_config.updated_time or sync_config.created_time,
                'created_by': getattr(sync_config, 'created_by', 1),
                'updated_by': getattr(sync_config, 'updated_by', 1)
            }
            sync_config_detail = GetSyncConfigDetail.model_validate(sync_config_dict)
        except Exception as e:
            # 使用手动映射
            sync_config_detail = GetSyncConfigDetail(
                id=sync_config.id,
                enable=sync_config.enable,
                remark=sync_config.remark,
                type=get_drive_type_from_db_value(sync_config.type),
                src_path=sync_config.src_path,
                src_meta=sync_config.src_meta,
                dst_path=sync_config.dst_path,
                dst_meta=sync_config.dst_meta,
                user_id=sync_config.user_id,
                cron=sync_config.cron,
                speed=sync_config.speed,
                method=SyncMethod(sync_config.method) if hasattr(SyncMethod, sync_config.method.upper()) else SyncMethod.INCREMENTAL,
                end_time=sync_config.end_time,
                exclude_template_id=sync_config.exclude_template_id,
                rename_template_id=sync_config.rename_template_id,
                last_sync=sync_config.last_sync,
                created_time=sync_config.created_time,
                updated_time=sync_config.updated_time or sync_config.created_time,
                created_by=getattr(sync_config, 'created_by', 1),
                updated_by=getattr(sync_config, 'updated_by', 1)
            )
        
        # 检查任务是否过期
        if sync_config_detail.end_time:
            current_time = datetime.now()
            if current_time > sync_config_detail.end_time:
                return {
                    "success": False,
                    "error": f"任务已过期，当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}, 结束时间: {sync_config_detail.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
                }
        
        # 执行同步任务
        sync_result = await self.perform_sync(sync_config_detail, db)

        if sync_result.get("success"):
            update_param = UpdateSyncConfigParam(last_sync=datetime.now())
            await sync_config_dao.update(db, db_obj=sync_config, obj_in=update_param)
            
        return sync_result

    async def _parse_rule_templates(
        self, 
        exclude_template_id: Optional[int], 
        rename_template_id: Optional[int],
        db: AsyncSession
    ) -> Tuple[Optional[List[ExclusionRuleDefinition]], Optional[List[RenameRuleDefinition]]]:
        """
        解析规则模板ID为具体的规则定义
        
        :param exclude_template_id: 排除规则模板ID
        :param rename_template_id: 重命名规则模板ID
        :param db: 数据库会话
        :return: (排除规则列表, 重命名规则列表)
        """
        from fastapi.concurrency import run_in_threadpool
        
        exclude_rules = None
        rename_rules = None
        
        # 解析排除规则模板
        if exclude_template_id:
            try:
                exclude_template = await rule_template_dao.get(db, exclude_template_id)
                if exclude_template:
                    # 使用 run_in_threadpool 处理可能的阻塞属性访问
                    is_active = await run_in_threadpool(lambda: exclude_template.is_active)
                    rule_config = await run_in_threadpool(lambda: exclude_template.rule_config)
                    
                    if is_active and isinstance(rule_config, dict) and 'rules' in rule_config:
                        exclude_rules = []
                        for rule_data in rule_config['rules']:
                            exclude_rule = ExclusionRuleDefinition(**rule_data)
                            exclude_rules.append(exclude_rule)
                    else:
                        if not is_active:
                            logger.warning(f"排除规则模板 {exclude_template_id} 已禁用")
                        else:
                            logger.warning(f"排除规则模板 {exclude_template_id} 配置格式不正确")
                else:
                    logger.warning(f"排除规则模板 {exclude_template_id} 不存在")
            except Exception as e:
                logger.error(f"解析排除规则模板 {exclude_template_id} 失败: {e}")
        
        # 解析重命名规则模板
        if rename_template_id:
            try:
                rename_template = await rule_template_dao.get(db, rename_template_id)
                if rename_template:
                    # 使用 run_in_threadpool 处理可能的阻塞属性访问
                    is_active = await run_in_threadpool(lambda: rename_template.is_active)
                    rule_config = await run_in_threadpool(lambda: rename_template.rule_config)
                    
                    if is_active and isinstance(rule_config, dict) and 'rules' in rule_config:
                        rename_rules = []
                        for rule_data in rule_config['rules']:
                            rename_rule = RenameRuleDefinition(**rule_data)
                            rename_rules.append(rename_rule)
                    else:
                        if not is_active:
                            logger.warning(f"重命名规则模板 {rename_template_id} 已禁用")
                        else:
                            logger.warning(f"重命名规则模板 {rename_template_id} 配置格式不正确")
                else:
                    logger.warning(f"重命名规则模板 {rename_template_id} 不存在")
            except Exception as e:
                logger.error(f"解析重命名规则模板 {rename_template_id} 失败: {e}")
        
        return exclude_rules, rename_rules

    async def get_sync_tasks_by_config_id(
        self, 
        config_id: int, 
        status: str | None = None, 
        db: AsyncSession = None
    ) -> list[GetSyncTaskDetail]:
        """
        根据配置ID获取同步任务列表
        
        :param config_id: 配置ID
        :param status: 任务状态筛选
        :param db: 数据库会话
        :return: 同步任务详情列表
        """
        tasks = await sync_task_dao.get_tasks_by_config_id(
            db, 
            config_id=config_id, 
            status=status
        )
        
        return [GetSyncTaskDetail.model_validate(task) for task in tasks]

    async def get_sync_task_detail(self, task_id: int, db: AsyncSession) -> GetSyncTaskWithRelationDetail | None:
        """
        获取同步任务详情（包含任务项）
        
        :param task_id: 任务ID
        :param db: 数据库会话
        :return: 同步任务详情
        """
        task = await sync_task_dao.get_task_with_items(db, task_id=task_id)
        
        if not task:
            return None
        
        # 获取任务统计信息
        stats = await sync_task_item_dao.get_task_statistics(db, task_id=task_id)
        
        # 转换任务项
        task_items = [GetSyncTaskItemDetail.model_validate(item) for item in task.task_items]
        
        # 创建任务详情
        task_detail = GetSyncTaskWithRelationDetail(
            id=task.id,
            config_id=task.config_id,
            status=task.status,
            err_msg=task.err_msg,
            start_time=task.start_time,
            task_num=task.task_num,
            dura_time=task.dura_time,
            created_time=task.created_time,
            updated_time=task.updated_time or task.created_time,
            created_by=getattr(task, 'created_by', 1),
            updated_by=getattr(task, 'updated_by', 1),
            task_items=task_items
        )
        
        # 添加统计信息到task_num字段
        if not task_detail.task_num:
            task_detail.task_num = json.dumps(stats, ensure_ascii=False)
        
        return task_detail

    async def get_sync_task_items(
        self, 
        task_id: int, 
        status: str | None = None,
        operation_type: str | None = None,
        db: AsyncSession = None
    ) -> list[GetSyncTaskItemDetail]:
        """
        根据任务ID获取同步任务项列表
        
        :param task_id: 任务ID
        :param status: 任务项状态筛选
        :param operation_type: 操作类型筛选
        :param db: 数据库会话
        :return: 同步任务项详情列表
        """
        task_items = await sync_task_item_dao.get_items_by_task_id(
            db,
            task_id=task_id,
            status=status,
            operation_type=operation_type
        )
        
        return [GetSyncTaskItemDetail.model_validate(item) for item in task_items]

    async def get_task_statistics(self, task_id: int, db: AsyncSession) -> dict[str, int]:
        """
        获取任务统计信息
        
        :param task_id: 任务ID
        :param db: 数据库会话
        :return: 统计信息
        """
        return await sync_task_item_dao.get_task_statistics(db, task_id=task_id)


# 创建服务单例
file_sync_service = FileSyncService()

class ExclusionRule:
    def __init__(self,
                 pattern: str,
                 target: MatchTarget = MatchTarget.NAME,
                 item_type: ItemType = ItemType.ANY,
                 mode: MatchMode = MatchMode.CONTAINS,
                 case_sensitive: bool = False):
        self.pattern_str = pattern
        self.target = target
        self.item_type = item_type
        self.mode = mode
        self.case_sensitive = case_sensitive

        if not case_sensitive:
            self.pattern_str = self.pattern_str.lower()

        self._compiled_regex: Optional[Pattern] = None
        if self.mode == MatchMode.REGEX:
            try:
                self._compiled_regex = re.compile(self.pattern_str, 0 if self.case_sensitive else re.IGNORECASE)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{self.pattern_str}': {e}")
        elif self.mode == MatchMode.WILDCARD:
            # Convert wildcard to regex
            # Basic conversion: escape regex chars, then replace * with .* and ? with .
            regex_pattern = re.escape(self.pattern_str).replace(r'\*', '.*').replace(r'\?', '.')
            self._compiled_regex = re.compile(regex_pattern, 0 if self.case_sensitive else re.IGNORECASE)

    def _get_value_to_match(self, item: BaseFileInfo) -> Optional[str]:
        value: Optional[str] = None
        if self.target == MatchTarget.NAME:
            value = item.file_name
        elif self.target == MatchTarget.PATH:
            value = item.file_path
        elif self.target == MatchTarget.EXTENSION:
            if not item.is_folder and '.' in item.file_name:
                value = item.file_name.rsplit('.', 1)[-1]
            else: # Folders or files without extension
                return None # Cannot match extension

        if value is not None and not self.case_sensitive:
            return value.lower()
        return value

    def matches(self, item: BaseFileInfo) -> bool:
        # 1. Check item type
        if self.item_type == ItemType.FILE and item.is_folder:
            return False
        if self.item_type == ItemType.FOLDER and not item.is_folder:
            return False

        # 2. Get value to match based on target
        value_to_match = self._get_value_to_match(item)
        if value_to_match is None and self.target == MatchTarget.EXTENSION: # e.g. folder when matching extension
            return False # Cannot match if target value is not applicable
        if value_to_match is None: # Should ideally not happen for NAME/PATH if item is valid
            return False

        # 3. Perform match based on mode
        match_result = False
        if self.mode == MatchMode.EXACT:
            match_result = value_to_match == self.pattern_str
        elif self.mode == MatchMode.CONTAINS:
            match_result = self.pattern_str in value_to_match
        elif self.mode == MatchMode.REGEX or self.mode == MatchMode.WILDCARD:
            if self._compiled_regex:
                match_result = bool(self._compiled_regex.search(value_to_match))
            else:
                match_result = False # Should not happen if constructor worked for these modes
        
        return match_result

class ItemFilter:
    def __init__(self, exclusion_rules: Optional[List[ExclusionRule]] = None):
        self.exclusion_rules: List[ExclusionRule] = exclusion_rules or []

    def add_rule(self, rule: ExclusionRule):
        self.exclusion_rules.append(rule)

    def should_exclude(self, item: BaseFileInfo) -> bool:
        if not self.exclusion_rules:
            return False
        for rule in self.exclusion_rules:
            if rule.matches(item):
                return True
        return False

class RenameRule:
    def __init__(self,
                 match_regex: str,
                 replace_string: str,
                 target_scope: MatchTarget = MatchTarget.NAME, # NAME or PATH
                 case_sensitive: bool = False):
        self.match_regex_str = match_regex
        self.replace_string = replace_string # For re.sub()
        
        if target_scope not in [MatchTarget.NAME, MatchTarget.PATH]:
            raise ValueError("RenameRule target_scope must be MatchTarget.NAME or MatchTarget.PATH")
        self.target_scope = target_scope
        self.case_sensitive = case_sensitive
        
        try:
            self.compiled_regex = re.compile(
                self.match_regex_str, 0 if self.case_sensitive else re.IGNORECASE
            )
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{self.match_regex_str}' in RenameRule: {e}")

    def generate_new_path(self, item: BaseFileInfo) -> Optional[str]:
        """
        Applies the rename rule to an item and returns the new potential full path.
        Returns None if the rule doesn't change the relevant part or scope is not applicable.
        """
        original_path = item.file_path
        original_name = item.file_name

        if self.target_scope == MatchTarget.NAME:
            new_name = self.compiled_regex.sub(self.replace_string, original_name)
            if new_name == original_name:
                return None # No change in name

            # Reconstruct the full path if name changed
            if original_path == original_name: # Item is at root, path is just its name
                return new_name.replace("\\", "/") 
            
            try:
                # Use PurePosixPath for robust parent path detection and joining
                # Assumes item.file_path is in POSIX format or convertible
                path_obj = PurePosixPath(original_path)
                base_path = path_obj.parent
                # str(base_path) might be '.' if original_path has no directory part (e.g. "file.txt")
                # In such a case, new_path should just be new_name.
                if str(base_path) == "." and not '/' in original_path:
                    return new_name.replace("\\", "/")
                return str(base_path / new_name).replace("\\", "/")
            except Exception:
                 # Fallback for any path manipulation issue (should be rare with PurePosixPath)
                if original_path.endswith(original_name):
                    base_path_str = original_path[:-len(original_name)]
                    if not base_path_str and original_path != original_name: 
                        return new_name.replace("\\", "/")
                    # Ensure base_path_str ends with a slash if it's not empty and not already ending with slash
                    if base_path_str and not base_path_str.endswith('/'):
                         base_path_str += '/'
                    return (base_path_str + new_name).replace("\\", "/")
                return None # Cannot reliably determine base path

        elif self.target_scope == MatchTarget.PATH:
            new_path = self.compiled_regex.sub(self.replace_string, original_path)
            if new_path == original_path:
                return None # No change in path
            return new_path.replace("\\", "/")
        
        return None # Should not be reached if target_scope is validated

def compare_drive_lists(
    source_list: List[BaseFileInfo],
    target_list: List[BaseFileInfo],
    mode: str = "incremental",  
    rename_rules: Optional[List[RenameRule]] = None,
    source_base_path: str = "",  # 源目录基础路径参数
    target_base_path: str = "",  # 目标目录基础路径参数
) -> Dict[str, Any]: 
    """
    比较两个文件列表，识别添加、更新、删除和重命名操作
    
    :param source_list: 源目录文件列表
    :param target_list: 目标目录文件列表
    :param mode: 比较模式，"incremental" 或 "full_sync"
    :param rename_rules: 重命名规则列表
    :param source_base_path: 源目录的基础路径，用于计算相对路径
    :param target_base_path: 目标目录的基础路径，用于计算相对路径
    :return: 比较结果字典，包含 to_add, to_update_in_target, to_delete_from_target, to_rename_in_target 字段
    """
    def get_relative_path(full_path: str, base_path: str) -> str:
        """获取相对路径"""
        if not base_path:
            return full_path
        # 确保路径以/开头
        full_path = full_path if full_path.startswith('/') else '/' + full_path
        base_path = base_path if base_path.startswith('/') else '/' + base_path
        # 移除结尾的/
        base_path = base_path.rstrip('/')
        if full_path.startswith(base_path):
            return full_path[len(base_path):]
        return full_path

    def calculate_target_path(source_item: BaseFileInfo) -> str:
        """
        计算源文件在目标位置的完整路径（简化版，只计算路径不计算file_id）
        
        :param source_item: 源文件信息
        :return: 目标完整路径
        """
        # 使用 get_relative_path 函数获取相对路径
        relative_path = get_relative_path(source_item.file_path, source_base_path)
        
        # 构建目标完整路径 - 使用POSIX路径拼接
        if relative_path:
            target_full_path = f"{target_base_path}/{relative_path}".replace("//", "/")
        else:
            target_full_path = target_base_path
        
        return target_full_path

    # 规范化基础路径
    source_base_path = source_base_path.rstrip('/')
    target_base_path = target_base_path.rstrip('/')

    results: Dict[str, List[Any]] = {
        "to_add": [],
        "to_update_in_target": [],
        "to_delete_from_target": [],
        "to_rename_in_target": []
    }

    # 创建相对路径映射
    source_map_by_rel_path: Dict[str, BaseFileInfo] = {
        get_relative_path(item.file_path, source_base_path): item 
        for item in source_list
    }
    target_map_by_rel_path: Dict[str, BaseFileInfo] = {
        get_relative_path(item.file_path, target_base_path): item 
        for item in target_list
    }

    accounted_source_paths: Set[str] = set()
    accounted_target_paths: Set[str] = set()

    # 1. First Pass: Exact path matches (for updates)
    for src_rel_path, src_item in source_map_by_rel_path.items():
        if src_rel_path in target_map_by_rel_path:
            target_item = target_map_by_rel_path[src_rel_path]
            
            is_different = False
            if src_item.is_folder != target_item.is_folder:
                is_different = True
            elif not src_item.is_folder: # If they are both files, compare size
                if src_item.file_size != target_item.file_size:
                    is_different = True

            if is_different:
                results["to_update_in_target"].append({"source": src_item, "target": target_item})
            
            accounted_source_paths.add(src_rel_path)
            accounted_target_paths.add(src_rel_path)

    # 2. Second Pass: Rename detection (using remaining unaccounted items)
    if rename_rules:
        unaccounted_src_items = [(p, i) for p, i in source_map_by_rel_path.items() if p not in accounted_source_paths]
        unaccounted_tgt_items = [(p, i) for p, i in target_map_by_rel_path.items() if p not in accounted_target_paths]
        

        for src_rel_path, src_item in unaccounted_src_items:
            if src_rel_path in accounted_source_paths:
                continue
            
            found_rename_for_current_source = False
            for target_rel_path, target_item in unaccounted_tgt_items:
                if target_rel_path in accounted_target_paths:
                    continue

                # Basic compatibility check (type and size for files)
                if src_item.is_folder == target_item.is_folder and \
                   (src_item.is_folder or src_item.file_size == target_item.file_size):
                    
                    for rule in rename_rules:
                        suggested_new_path = rule.generate_new_path(target_item)
                        if suggested_new_path and suggested_new_path == src_item.file_path:
                            results["to_rename_in_target"].append({
                                'target_item': target_item,
                                'suggested_new_path': src_item.file_path,
                                'source_item': src_item,
                                'applied_rule_pattern': rule.match_regex_str
                            })
                            accounted_source_paths.add(src_rel_path)
                            accounted_target_paths.add(target_rel_path)
                            found_rename_for_current_source = True
                            break
                
                if found_rename_for_current_source:
                    break

    # 3. Third Pass: Remaining items are true adds/deletes
    for src_rel_path, src_item in source_map_by_rel_path.items():
        if src_rel_path not in accounted_source_paths:
            # 简化的添加项信息，只包含源文件和目标路径
            target_full_path = calculate_target_path(src_item)
            
            add_item = {
                "source_item": src_item,
                "target_path": target_full_path
            }
            results["to_add"].append(add_item)

    # 根据同步模式处理删除操作
    if mode == SyncMethod.FULL.value:
        # 完全同步：删除目标中多余的文件（源中不存在的文件）
        for target_rel_path, target_item in target_map_by_rel_path.items():
            if target_rel_path not in accounted_target_paths:
                results["to_delete_from_target"].append(target_item)
    elif mode == SyncMethod.OVERWRITE.value:
        # 覆盖同步：删除目标目录里的所有文件，然后保存源目录里的所有文件
        # 1. 将所有目标文件标记为删除
        for target_rel_path, target_item in target_map_by_rel_path.items():
            results["to_delete_from_target"].append(target_item)
        
        # 2. 将所有源文件标记为添加（清空之前的添加列表，重新添加所有源文件）
        results["to_add"] = []  # 清空之前的添加列表
        results["to_update_in_target"] = []  # 清空更新列表，覆盖模式不需要更新
        results["to_rename_in_target"] = []  # 清空重命名列表，覆盖模式不需要重命名
        
        for src_rel_path, src_item in source_map_by_rel_path.items():
            # 计算目标路径信息
            target_full_path = calculate_target_path(src_item)
            
            # 构建添加项信息
            add_item = {
                "source_item": src_item,
                "target_path": target_full_path
            }
            results["to_add"].append(add_item)
    
    return results

def _parse_exclusion_rules(rules_def: Optional[List[ExclusionRuleDefinition]]) -> Optional[ItemFilter]:
    if not rules_def:
        return None
    
    item_filter = ItemFilter()
    
    for i, rule_data in enumerate(rules_def):
        try:
            # 确保枚举类型正确转换
            target_enum = rule_data.target if isinstance(rule_data.target, MatchTarget) else MatchTarget(rule_data.target)
            item_type_enum = rule_data.item_type if isinstance(rule_data.item_type, ItemType) else ItemType(rule_data.item_type)
            mode_enum = rule_data.mode if isinstance(rule_data.mode, MatchMode) else MatchMode(rule_data.mode)
            
            exclusion_rule = ExclusionRule(
                pattern=rule_data.pattern,
                target=target_enum,
                item_type=item_type_enum,
                mode=mode_enum,
                case_sensitive=rule_data.case_sensitive
            )
            item_filter.add_rule(exclusion_rule)
            
        except ValueError as e:
            # 抛出一个特定的错误，可以被 API 层捕获
            logger.error(f"[ExclusionRules] 规则 #{i+1} 解析失败: {e}")
            raise ValueError(f"排除规则 #{i+1} ('{rule_data.pattern}') 格式错误: {e}")
    
    return item_filter

def _parse_rename_rules(rules_def: Optional[List[RenameRuleDefinition]]) -> Optional[List[RenameRule]]:
    if not rules_def:
        return None
    parsed_rules = []
    for i, rule_data in enumerate(rules_def):
        try:
            parsed_rules.append(RenameRule(
                match_regex=rule_data.match_regex,
                replace_string=rule_data.replace_string,
                target_scope=rule_data.target_scope,
                case_sensitive=rule_data.case_sensitive
            ))
        except ValueError as e:
            # Raise a specific error that can be caught by the API layer
            raise ValueError(f"重命名规则 #{i+1} ('{rule_data.match_regex}') 格式错误: {e}")
    return parsed_rules

async def _create_directories_intelligently(
    drive_manager: Any,
    x_token: str,
    to_add: List[Dict[str, Any]],
    target_definition: DiskTargetDefinition,
    drive_type_str: str,
    existing_path_mapping: Dict[str, str]
) -> Dict[str, str]:
    """
    智能分析并创建所需目录，返回完整的路径映射
    
    :param drive_manager: 网盘管理器实例
    :param x_token: 认证令牌
    :param to_add: 待添加项目列表
    :param target_definition: 目标定义
    :param drive_type_str: 网盘类型字符串
    :param existing_path_mapping: 现有的路径到file_id映射
    :return: 完整的路径到file_id映射（包含新创建的目录）
    """
    # 复制现有映射，避免修改原始数据
    complete_path_mapping = existing_path_mapping.copy()
    
    # 1. 收集所有需要的目录路径
    required_dirs = set()
    for add_item in to_add:
        target_path = add_item.get("target_path", "")
        if target_path:
            # 对于文件，需要其父目录；对于文件夹，需要其本身的父目录
            source_item = add_item.get("source_item")
            if source_item and not source_item.is_folder:
                # 文件：需要其父目录
                parent_dir = os.path.dirname(target_path).replace("\\", "/")
                if parent_dir and parent_dir != "/" and parent_dir != target_definition.file_path:
                    required_dirs.add(parent_dir)
            else:
                # 文件夹：需要其父目录（文件夹本身会在转存时创建）
                parent_dir = os.path.dirname(target_path).replace("\\", "/")
                if parent_dir and parent_dir != "/" and parent_dir != target_definition.file_path:
                    required_dirs.add(parent_dir)
    
    # 2. 过滤掉已存在的目录
    missing_dirs = [d for d in required_dirs if d not in complete_path_mapping]
    
    if not missing_dirs:
        logger.info("所有需要的目录都已存在，无需创建新目录")
        return complete_path_mapping
    
    # 3. 按深度排序，确保先创建父目录
    sorted_dirs = sorted(missing_dirs, key=lambda x: x.count('/'))
    
    logger.info(f"需要创建 {len(sorted_dirs)} 个目录: {sorted_dirs}")
    
    # 4. 逐个创建目录并更新映射
    created_count = 0
    for dir_path in sorted_dirs:
        try:
            # 确保路径格式正确
            normalized_dir_path = dir_path.replace("\\", "/")
            
            # 计算父目录路径和目录名
            path_parts = normalized_dir_path.strip("/").split("/")
            if len(path_parts) <= 1:
                logger.warning(f"跳过根目录或无效路径: {normalized_dir_path}")
                continue
                
            parent_path_parts = path_parts[:-1]
            parent_path = "/" + "/".join(parent_path_parts) if parent_path_parts else "/"
            dir_name = path_parts[-1]
            
            # 查找父目录的file_id
            parent_file_id = None
            
            if parent_path == target_definition.file_path:
                # 父目录是根目录
                parent_file_id = target_definition.file_id
            elif parent_path in complete_path_mapping:
                # 父目录在映射中（可能是已存在的或刚创建的）
                parent_file_id = complete_path_mapping[parent_path]
            else:
                logger.warning(f"无法找到父目录 {parent_path} 的file_id，跳过创建 {normalized_dir_path}")
                continue
            
            # 构建 MkdirParam
            mkdir_params = MkdirParam(
                drive_type=drive_type_str,
                file_path=normalized_dir_path,
                parent_id=parent_file_id,
                file_name=dir_name
            )
            
            # 创建目录
            new_dir_info = await drive_manager.create_mkdir(x_token, mkdir_params)
            if new_dir_info and hasattr(new_dir_info, 'file_id'):
                complete_path_mapping[normalized_dir_path] = new_dir_info.file_id
                created_count += 1
                logger.info(f"创建目录成功: {normalized_dir_path} (file_id: {new_dir_info.file_id})")
            else:
                logger.warning(f"创建目录失败: {normalized_dir_path}")
                
        except Exception as e:
            logger.error(f"创建目录 {dir_path} 时发生错误: {e}")
            continue
    
    logger.info(f"智能目录创建完成，成功创建 {created_count}/{len(sorted_dirs)} 个目录")
    return complete_path_mapping

async def _create_missing_target_directories(
    drive_manager: Any,
    x_token: str,
    to_add: List[Dict[str, Any]],
    target_definition: DiskTargetDefinition,
    drive_type_str: str,
    target_path_to_file_id: Optional[Dict[str, str]] = None
) -> None:
    """
    在比较阶段创建缺失的目标目录（保留向后兼容，但内部使用新的智能创建逻辑）
    
    :param drive_manager: 网盘管理器实例
    :param x_token: 认证令牌
    :param to_add: 待添加项目列表
    :param target_definition: 目标定义
    :param drive_type_str: 网盘类型字符串
    :param target_path_to_file_id: 目标路径到file_id的映射，用于查找已存在的目录
    """
    logger.warning("使用了已废弃的 _create_missing_target_directories 函数，建议使用 _create_directories_intelligently")
    
    # 使用新的智能创建逻辑
    existing_mapping = target_path_to_file_id or {}
    updated_mapping = await _create_directories_intelligently(
        drive_manager=drive_manager,
        x_token=x_token,
        to_add=to_add,
        target_definition=target_definition,
        drive_type_str=drive_type_str,
        existing_path_mapping=existing_mapping
    )
    
    # 更新to_add中的信息（为了向后兼容）
    for add_item in to_add:
        target_path = add_item.get("target_path", "")
        if target_path:
            source_item = add_item.get("source_item")
            if source_item and not source_item.is_folder:
                parent_path = os.path.dirname(target_path).replace("\\", "/")
                if parent_path in updated_mapping:
                    # 添加兼容字段
                    add_item["target_parent_path"] = parent_path
                    add_item["target_parent_file_id"] = updated_mapping[parent_path]
                    add_item["target_full_path"] = target_path

async def _get_list_for_compare_op(
    drive_manager: Any,
    x_token: str,
    is_source: bool,
    definition: Union[ShareSourceDefinition, DiskTargetDefinition],
    top_level_recursive: bool,
    top_level_recursion_speed: RecursionSpeed,
    item_filter_instance: Optional[ItemFilter],
    drive_type_str: str
) -> Tuple[List[BaseFileInfo], float]:
    """
    获取列表数据用于比较操作
    
    :param drive_manager: 网盘管理器实例
    :param x_token: 认证令牌
    :param is_source: 是否为源端数据
    :param definition: 路径定义（源或目标）
    :param top_level_recursive: 是否递归
    :param top_level_recursion_speed: 递归速度
    :param item_filter_instance: 项目过滤器实例
    :param drive_type_str: 网盘类型字符串
    :return: 文件列表和耗时
    """
    start_time = time.time()
    result_list: List[BaseFileInfo] = []
    
    # 确保异步方法使用 await 调用
    if is_source:
        source_def = definition
        
        # 构建 ListShareFilesParam
        params = ListShareFilesParam(
            drive_type=drive_type_str,
            source_type=source_def.source_type,
            source_id=source_def.source_id,
            file_path=source_def.file_path,
            recursive=top_level_recursive,
            recursion_speed=top_level_recursion_speed
        )
        
        # 使用统一的调用方式，传递 item_filter
        result_list = await drive_manager.get_share_list(x_token, params, item_filter=item_filter_instance)
    else:
        target_def = definition
        
        # 构建 ListFilesParam
        params = ListFilesParam(
            drive_type=drive_type_str,
            file_path=target_def.file_path,
            file_id=target_def.file_id,
            recursive=top_level_recursive,
            recursion_speed=top_level_recursion_speed
        )
        
        # 使用统一的调用方式，传递 item_filter
        result_list = await drive_manager.get_disk_list(x_token, params, item_filter=item_filter_instance)
    
    # 应用过滤器（双重保险，虽然客户端已经应用了过滤器）
    if item_filter_instance:
        original_count = len(result_list)
        result_list = [item for item in result_list if not item_filter_instance.should_exclude(item)]
        filtered_count = original_count - len(result_list)
        if filtered_count > 0:
            logger.info(f"[ItemFilter] 在服务层额外过滤了 {filtered_count} 个项目")
    
    elapsed_time = time.time() - start_time
    return result_list, elapsed_time

async def perform_comparison_logic(
    drive_manager: Any,
    x_token: str,
    source_definition: ShareSourceDefinition,
    target_definition: DiskTargetDefinition,
    recursive: bool,
    recursion_speed: RecursionSpeed,
    comparison_mode: str, 
    exclude_rules_def: Optional[List[ExclusionRuleDefinition]],
    rename_rules_def: Optional[List[RenameRuleDefinition]],
    drive_type_str: str
) -> GetCompareDetail:
    """
    执行比较逻辑
    
    :param drive_manager: 网盘管理器实例
    :param x_token: 认证令牌
    :param source_definition: 源定义
    :param target_definition: 目标定义
    :param recursive: 是否递归
    :param recursion_speed: 递归速度
    :param comparison_mode: 比较模式
    :param exclude_rules_def: 排除规则定义
    :param rename_rules_def: 重命名规则定义
    :param drive_type_str: 网盘类型字符串
    :return: 比较结果详情
    """
    
    common_item_filter = _parse_exclusion_rules(exclude_rules_def)
    
    # 覆盖模式的简化处理：只处理一层目录，不递归
    if comparison_mode == SyncMethod.OVERWRITE.value:
        # 1. 只获取源目录下的一层文件列表（不递归）
        source_list, source_time = await _get_list_for_compare_op(
            drive_manager=drive_manager,
            x_token=x_token,
            is_source=True,
            definition=source_definition,
            top_level_recursive=False,  # 覆盖模式不递归
            top_level_recursion_speed=recursion_speed,
            item_filter_instance=common_item_filter,
            drive_type_str=drive_type_str
        )
        
        # 2. 只获取目标目录下的一层文件列表（不递归，用于删除）
        target_list, target_time = await _get_list_for_compare_op(
            drive_manager=drive_manager,
            x_token=x_token,
            is_source=False,
            definition=target_definition,
            top_level_recursive=False,  # 覆盖模式不递归
            top_level_recursion_speed=recursion_speed,
            item_filter_instance=None,  # 删除时不应用过滤器，删除所有文件
            drive_type_str=drive_type_str
        )
        
        # 3. 构建简化的比较结果：删除所有目标文件，添加所有源文件
        comparison_result = {
            "to_add": [],
            "to_update_in_target": [],
            "to_delete_from_target": target_list,  # 删除所有目标文件
            "to_rename_in_target": []
        }
        
        # 4. 将所有源文件标记为添加（只处理一层，直接转存到目标目录）
        for src_item in source_list:
            # 覆盖模式：直接将源文件转存到目标目录，使用原文件名
            target_full_path = target_definition.file_path + "/" + src_item.file_name
            
            add_item = {
                "source_item": src_item,
                "target_path": target_full_path
            }
            comparison_result["to_add"].append(add_item)
        
        # 5. 构建返回数据
        compare_detail_data = {
            "drive_type": drive_type_str,
            "source_list_num": len(source_list),
            "target_list_num": len(target_list),
            "source_list_time": source_time,
            "target_list_time": target_time,
            "source_definition": source_definition,
            "target_definition": target_definition,
            **comparison_result
        }
        
        return GetCompareDetail(**compare_detail_data)
    
    # 增量同步和完全同步的正常比较逻辑
    source_list, source_time = await _get_list_for_compare_op(
        drive_manager=drive_manager,
        x_token=x_token,
        is_source=True,
        definition=source_definition,
        top_level_recursive=recursive,
        top_level_recursion_speed=recursion_speed,
        item_filter_instance=common_item_filter,
        drive_type_str=drive_type_str
    )
    
    target_list, target_time = await _get_list_for_compare_op(
        drive_manager=drive_manager,
        x_token=x_token,
        is_source=False,
        definition=target_definition,
        top_level_recursive=recursive,
        top_level_recursion_speed=recursion_speed,
        item_filter_instance=common_item_filter,
        drive_type_str=drive_type_str
    )
    
    parsed_rename_rules = _parse_rename_rules(rename_rules_def)

    # 构建目标路径到file_id的映射
    target_path_to_file_id = {}
    for target_item in target_list:
        if target_item.file_path and target_item.file_id:
            target_path_to_file_id[target_item.file_path] = target_item.file_id

    # compare_drive_lists 返回基础的比较结果字典（简化版）
    comparison_result = compare_drive_lists(
        source_list=source_list,
        target_list=target_list,
        mode=comparison_mode,
        rename_rules=parsed_rename_rules,
        source_base_path=source_definition.file_path,
        target_base_path=target_definition.file_path
    )
    
    # 使用新的智能目录创建逻辑
    complete_path_mapping = await _create_directories_intelligently(
        drive_manager=drive_manager,
        x_token=x_token,
        to_add=comparison_result.get('to_add', []),
        target_definition=target_definition,
        drive_type_str=drive_type_str,
        existing_path_mapping=target_path_to_file_id
    )
    
    # 为了保持向后兼容，更新 to_add 中的信息
    for add_item in comparison_result.get('to_add', []):
        target_path = add_item.get("target_path", "")
        if target_path:
            source_item = add_item.get("source_item")
            if source_item and not source_item.is_folder:
                parent_path = os.path.dirname(target_path).replace("\\", "/")
                if parent_path in complete_path_mapping:
                    # 添加兼容字段
                    add_item["target_parent_path"] = parent_path
                    add_item["target_parent_file_id"] = complete_path_mapping[parent_path]
                    add_item["target_full_path"] = target_path
    
    # 构建完整的 GetCompareDetail 对象所需的数据
    compare_detail_data = {
        "drive_type": drive_type_str,
        "source_list_num": len(source_list),
        "target_list_num": len(target_list),
        "source_list_time": source_time,
        "target_list_time": target_time,
        "source_definition": source_definition,
        "target_definition": target_definition,
        # 添加比较结果的核心字段
        **comparison_result
    }
    
    # 返回 GetCompareDetail 模型实例
    return GetCompareDetail(**compare_detail_data)

async def apply_comparison_operations(
    drive_manager: Any,
    x_token: str,
    comparison_result: GetCompareDetail,
    drive_type_str: str,
    sync_mode: str = "incremental"
) -> Dict[str, Dict[str, List[str]]]:
    """
    根据比较结果执行相应的操作（添加、删除、重命名、更新）

    :param drive_manager: 网盘管理器实例
    :param x_token: 认证令牌
    :param comparison_result: 比较结果，包含to_add、to_delete_from_target等操作列表
    :param drive_type_str: 网盘类型字符串
    :param sync_mode: 同步模式
    :return: 各类操作的结果，格式为:
        {
            "add": {"succeeded": [...], "failed": [...]},
            "delete": {"succeeded": [...], "failed": [...]}
        }
    """
    operation_results = {
        "add": {"succeeded": [], "failed": []},
        "delete": {"succeeded": [], "failed": []}
    }

    # 根据同步模式确定执行顺序
    if sync_mode == SyncMethod.OVERWRITE.value:
        # 覆盖模式：必须先删除，再添加，确保顺序执行
        # logger.info("覆盖模式：开始执行删除操作...")
        
        # 1. 先处理删除操作
        if comparison_result.to_delete_from_target:
            delete_results = await _process_delete_operations(
                drive_manager=drive_manager,
                x_token=x_token,
                to_delete=comparison_result.to_delete_from_target,
                drive_type_str=drive_type_str
            )
            operation_results["delete"] = delete_results
            
            # 检查删除操作是否成功
            delete_failed_count = len(delete_results.get("failed", []))
            delete_success_count = len(delete_results.get("succeeded", []))
            
            # logger.info(f"删除操作完成：成功 {delete_success_count} 个，失败 {delete_failed_count} 个")
            
            # 如果删除操作有失败，记录警告但继续执行添加操作
            if delete_failed_count > 0:
                logger.warning(f"覆盖模式：有 {delete_failed_count} 个文件删除失败，可能影响后续转存操作")
        
        # logger.info("覆盖模式：开始执行添加操作...")
        
        # 2. 再处理添加操作
        if comparison_result.to_add:
            add_results = await _process_add_operations(
                drive_manager=drive_manager,
                x_token=x_token,
                to_add=comparison_result.to_add,
                source_definition=comparison_result.source_definition,
                target_definition=comparison_result.target_definition,
                drive_type_str=drive_type_str,
                sync_mode=sync_mode
            )
            operation_results["add"] = add_results
            
            add_failed_count = len(add_results.get("failed", []))
            add_success_count = len(add_results.get("succeeded", []))
            # logger.info(f"添加操作完成：成功 {add_success_count} 个，失败 {add_failed_count} 个")
    
    else:
        # 增量同步和完全同步：可以并发执行，先添加后删除（保持原有逻辑）
        # logger.info(f"{sync_mode}模式：并发执行添加和删除操作...")
        
        # 处理添加操作
        if comparison_result.to_add:
            add_results = await _process_add_operations(
                drive_manager=drive_manager,
                x_token=x_token,
                to_add=comparison_result.to_add,
                source_definition=comparison_result.source_definition,
                target_definition=comparison_result.target_definition,
                drive_type_str=drive_type_str,
                sync_mode=sync_mode
            )
            operation_results["add"] = add_results

        # 处理删除操作
        if comparison_result.to_delete_from_target:
            delete_results = await _process_delete_operations(
                drive_manager=drive_manager,
                x_token=x_token,
                to_delete=comparison_result.to_delete_from_target,
                drive_type_str=drive_type_str
            )
            operation_results["delete"] = delete_results

    return operation_results

async def _process_add_operations(
    drive_manager: Any,
    x_token: str,
    to_add: List[Dict[str, Any]],  # 修改类型，现在是包含完整信息的字典列表
    source_definition: ShareSourceDefinition,
    target_definition: DiskTargetDefinition,
    drive_type_str: str,
    sync_mode: str = "incremental",
    ext_transfer_params: Optional[Dict[str, Any]] = None
) -> Dict[str, List[str]]:
    """
    处理添加操作，包括创建目录和传输文件（优化版）
    
    :param drive_manager: 网盘管理器实例
    :param x_token: 认证令牌
    :param to_add: 要添加的文件/目录列表，每个元素包含source_item、target_path等信息
    :param source_definition: 源定义
    :param target_definition: 目标定义
    :param drive_type_str: 网盘类型字符串
    :param ext_transfer_params: 额外的传输参数
    :return: 操作结果，包含succeeded和failed两个列表
    """
    operation_results = {'succeeded': [], 'failed': []}

    # 提取source_item进行排序
    sorted_to_add = sorted(to_add, key=lambda add_item: add_item["source_item"].file_path)

    # 按目标父目录分组文件
    files_to_transfer_by_target_parent: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for add_item in sorted_to_add:
        source_item = add_item["source_item"]
        target_path = add_item.get("target_path", "")
        
        # 覆盖模式处理所有类型的文件，其他模式只处理非文件夹
        if sync_mode == SyncMethod.OVERWRITE.value or not source_item.is_folder:
            # 计算父目录路径
            if source_item.is_folder:
                # 文件夹：父目录是其上级目录
                parent_path = os.path.dirname(target_path).replace("\\", "/")
            else:
                # 文件：父目录是其所在目录
                parent_path = os.path.dirname(target_path).replace("\\", "/")
            
            # 确保父目录路径不为空
            if not parent_path or parent_path == ".":
                parent_path = target_definition.file_path
            
            # 添加计算出的父目录信息到add_item中（兼容旧逻辑）
            add_item["target_parent_path"] = parent_path
            add_item["target_full_path"] = target_path
            
            files_to_transfer_by_target_parent[parent_path].append(add_item)
    
    for target_parent_dir, add_items_in_group in files_to_transfer_by_target_parent.items():
        if not add_items_in_group:
            continue

        # 确保目标路径使用正斜杠
        normalized_target_parent_dir = os.path.normpath(target_parent_dir).replace("\\", "/")
        
        try:
            source_fs_ids_to_transfer = [add_item["source_item"].file_id for add_item in add_items_in_group]
            
            current_transfer_ext_params = {}
            if ext_transfer_params:
                current_transfer_ext_params = {**ext_transfer_params}
                        
            # 传递所有文件的完整信息，让具体的网盘客户端处理
            # 将所有文件的 file_ext 信息传递给客户端
            files_ext_info = []
            for add_item in add_items_in_group:
                source_item = add_item["source_item"]
                file_ext_info = {
                    'file_id': source_item.file_id,
                    'file_ext': source_item.file_ext if hasattr(source_item, 'file_ext') else {},
                    'parent_id': source_item.parent_id
                }
                files_ext_info.append(file_ext_info)
            
            # 将文件扩展信息传递给客户端
            current_transfer_ext_params['files_ext_info'] = files_ext_info
            
            # 使用第一个文件的公共参数作为基础参数
            first_source_item = add_items_in_group[0]["source_item"]
            if hasattr(first_source_item, 'file_ext') and first_source_item.file_ext:
                file_ext = first_source_item.file_ext
                if isinstance(file_ext, dict):
                    # 只传递公共参数，不传递特定文件的参数
                    common_params = {k: v for k, v in file_ext.items() 
                                   if k not in ['share_fid_token']}
                    current_transfer_ext_params.update(common_params)
                    
                    # 添加分享文件的父目录ID
                    if first_source_item.parent_id:
                        current_transfer_ext_params['share_parent_fid'] = first_source_item.parent_id
            
            # 如果source_definition有ext_params，也一并加入
            if hasattr(source_definition, 'ext_params') and source_definition.ext_params:
                if isinstance(source_definition.ext_params, dict):
                    # 将source_definition.ext_params中的所有参数合并到current_transfer_ext_params
                    current_transfer_ext_params.update(source_definition.ext_params)
            
            # 获取目标目录的file_id
            target_dir_file_id = None
            
            # 1. 优先使用比较结果中的file_id（兼容字段）
            if add_items_in_group:
                target_dir_file_id = add_items_in_group[0].get("target_parent_file_id")
            
            # 2. 如果是根目录，使用target_definition中的file_id
            if not target_dir_file_id and normalized_target_parent_dir == target_definition.file_path:
                target_dir_file_id = target_definition.file_id
            
            if not target_dir_file_id:
                error_msg = f"无法获取目标目录的file_id: {normalized_target_parent_dir}"
                for add_item in add_items_in_group:
                    source_item = add_item["source_item"]
                    target_path = add_item.get("target_path", add_item.get("target_full_path", ""))
                    operation_results['failed'].append(f"TRANSFER_ERROR: {source_item.file_path} -> {target_path} - {error_msg}")
                continue
            
            # 构建transfer所需参数
            try:
                # 构建 TransferParam
                transfer_params = TransferParam(
                    drive_type=drive_type_str,
                    source_type=source_definition.source_type,
                    source_id=source_definition.source_id,
                    source_path=source_definition.file_path,
                    target_path=normalized_target_parent_dir,
                    target_id=target_dir_file_id,  # 使用获取到的具体目录file_id
                    file_ids=source_fs_ids_to_transfer,
                    ext=current_transfer_ext_params
                )
                
                # 使用统一架构的transfer方法
                transfer_success = await drive_manager.transfer_files(x_token, transfer_params)
                
                if transfer_success:
                    # 转存成功，记录所有文件为成功
                    for add_item in add_items_in_group:
                        source_item = add_item["source_item"]
                        target_path = add_item.get("target_path", add_item.get("target_full_path", ""))
                        operation_results['succeeded'].append(f"TRANSFER_SUCCESS: {source_item.file_path} -> {target_path}")
                else:
                    # 转存失败，记录所有文件为失败
                    for add_item in add_items_in_group:
                        source_item = add_item["source_item"]
                        target_path = add_item.get("target_path", add_item.get("target_full_path", ""))
                        operation_results['failed'].append(f"TRANSFER_FAIL: {source_item.file_path} -> {target_path}")
            except Exception as ex_transfer:
                # 记录所有文件传输失败
                for add_item in add_items_in_group:
                    source_item = add_item["source_item"]
                    target_path = add_item.get("target_path", add_item.get("target_full_path", ""))
                    operation_results['failed'].append(f"TRANSFER_ERROR: {source_item.file_path} -> {target_path} - {str(ex_transfer)}")
        except Exception as ex_group:
            # 整组处理出错
            for add_item in add_items_in_group:
                source_item = add_item["source_item"]
                target_path = add_item.get("target_path", add_item.get("target_full_path", ""))
                operation_results['failed'].append(f"TRANSFER_GROUP_ERROR: {source_item.file_path} -> {target_path} - {str(ex_group)}")
    
    return operation_results

async def _process_delete_operations(
    drive_manager: Any,
    x_token: str,
    to_delete: List[BaseFileInfo],
    drive_type_str: str
) -> Dict[str, List[str]]:
    """
    处理删除操作
    
    :param drive_manager: 网盘管理器实例
    :param x_token: 认证令牌
    :param to_delete: 要删除的文件/目录列表
    :param drive_type_str: 网盘类型字符串
    :return: 操作结果，包含succeeded和failed两个列表
    """
    operation_results = {'succeeded': [], 'failed': []}
    
    # 收集所有要删除的文件路径和ID
    file_paths = []
    file_ids = []
    
    for item in to_delete:
        if item.file_path:
            # 确保路径是以/开头的绝对路径
            path = item.file_path
            if not path.startswith("/"):
                path = "/" + path
            file_paths.append(path)
        if item.file_id:
            file_ids.append(item.file_id)
    
    # 构建 RemoveParam
    try:
        remove_params = RemoveParam(
            drive_type=drive_type_str,
            file_paths=file_paths,
            file_ids=file_ids
        )
        
        result = await drive_manager.remove_files(x_token, remove_params)
        if result:
            for item in to_delete:
                operation_results['succeeded'].append(f"DELETE_SUCCESS: {item.file_path} (ID: {item.file_id})")
        else:
            for item in to_delete:
                operation_results['failed'].append(f"DELETE_FAILED: {item.file_path} (ID: {item.file_id})")
    except Exception as e:
        for item in to_delete:
            operation_results['failed'].append(f"DELETE_ERROR: {item.file_path} (ID: {item.file_id}) - {str(e)}")
    
    return operation_results 