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
from backend.app.coulddrive.schema.filesync import GetSyncConfigDetail
from backend.app.coulddrive.schema.user import GetDriveAccountDetail
from backend.app.coulddrive.service.yp_service import get_drive_manager

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
        
        if method_lower == "incremental":
            return SyncMethod.INCREMENTAL.value
        elif method_lower == "full":
            return SyncMethod.FULL.value
        elif method_lower == "overwrite":
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

    async def perform_sync(self, sync_config: GetSyncConfigDetail) -> Dict[str, Any]:
        """执行同步任务
        
        Args:
            sync_config: 同步配置
            
        Returns:
            Dict[str, Any]: 同步结果
        """
        start_time = time.time()
        logger.info(f"开始执行同步任务: {sync_config.id} - {sync_config.remark or '未命名任务'}")
        
        account_schema: Optional[GetDriveAccountDetail] = None
        try:
            from backend.database.db import async_db_session
            from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
            
            logger.info(f"尝试根据account_id={sync_config.account_id}从数据库获取账号")
            async with async_db_session() as db:
                account_schema = await drive_account_dao.get(db, sync_config.account_id)
                
                if not account_schema:
                    error_msg = f"未找到ID为{sync_config.account_id}的账号，无法执行同步任务"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "elapsed_time": time.time() - start_time
                    }
                
                logger.info(f"成功获取到账号: {account_schema.username or account_schema.user_id} (ID: {account_schema.id})")
        except Exception as e:
            error_msg = f"获取账号时发生错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }
        
        # 验证账号和配置关系
        if sync_config.account_id != account_schema.id:
            error_msg = f"严重的内部错误: 同步配置 {sync_config.id} 的账号ID({sync_config.account_id})与获取到的账号ID({account_schema.id})不匹配"
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
            
            # 解析排除和重命名规则
            exclude_rules = None
            if sync_config.exclude:
                try:
                    exclude_rules = json.loads(sync_config.exclude)
                except json.JSONDecodeError:
                    logger.warning(f"解析排除规则失败: {sync_config.exclude}")
            
            rename_rules = None
            if sync_config.rename:
                try:
                    rename_rules = json.loads(sync_config.rename)
                except json.JSONDecodeError:
                    logger.warning(f"解析重命名规则失败: {sync_config.rename}")
            
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
            
            # 映射账号类型到网盘类型
            drive_type_mapping = {
                "baidu": DriveType.BAIDU_DRIVE.value,
                "quark": DriveType.QUARK_DRIVE.value,
            }
            drive_type_str = drive_type_mapping.get(account_schema.type.lower(), DriveType.BAIDU_DRIVE.value)
            
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
                drive_type_str=drive_type_str
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
            logger.info(f"同步任务完成: ID={sync_config.id}, 耗时={elapsed_time:.2f}秒")
            
            return {
                "success": True,
                "stats": stats,
                "details": operation_results,
                "elapsed_time": elapsed_time
            }
            
        except Exception as e:
            error_msg = f"同步任务执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }

    async def create_and_execute_task(
        self, 
        sync_config: GetSyncConfigDetail, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """创建并执行同步任务，将结果写入数据库
        
        Args:
            sync_config: 同步配置
            db: 数据库会话
            
        Returns:
            Dict[str, Any]: 任务执行结果
        """
        start_time = time.time()
        logger.info(f"创建并执行同步任务: 配置ID={sync_config.id}")
        
        # 创建任务记录
        from backend.app.coulddrive.crud.crud_filesync import sync_task_dao
        from backend.app.coulddrive.schema.filesync import CreateSyncTaskParam, UpdateSyncTaskParam
        
        task_data = CreateSyncTaskParam(
            config_id=sync_config.id,
            status="pending"
        )
        task = await sync_task_dao.create(db, obj_in=task_data)
        task_id = task.id
        
        try:
            # 执行同步任务
            sync_result = await self.perform_sync(sync_config)
            
            if sync_result["success"]:
                # 更新任务状态为完成
                stats = sync_result.get("stats", {})
                update_data = UpdateSyncTaskParam(
                    status="completed",
                    total_items=stats.get("to_add_total", 0) + stats.get("to_delete_total", 0),
                    completed_items=stats.get("added_success", 0) + stats.get("deleted_success", 0),
                    failed_items=stats.get("added_fail", 0) + stats.get("deleted_fail", 0)
                )
                await sync_task_dao.update(db, pk=task_id, obj_in=update_data)
                
                return {
                    "success": True,
                    "task_id": task_id,
                    "stats": stats,
                    "elapsed_time": sync_result["elapsed_time"]
                }
            else:
                # 更新任务状态为失败
                update_data = UpdateSyncTaskParam(
                    status="failed",
                    error_message=sync_result.get("error", "Unknown error")
                )
                await sync_task_dao.update(db, pk=task_id, obj_in=update_data)
                
                return {
                    "success": False,
                    "error": sync_result.get("error", "Unknown error"),
                    "task_id": task_id,
                    "elapsed_time": sync_result["elapsed_time"]
                }
                
        except Exception as e:
            error_msg = f"同步任务执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # 更新任务状态为失败
            update_data = UpdateSyncTaskParam(
                status="failed",
                error_message=error_msg
            )
            await sync_task_dao.update(db, pk=task_id, obj_in=update_data)
            
            return {
                "success": False,
                "error": error_msg,
                "task_id": task_id,
                "elapsed_time": time.time() - start_time
            }

# 创建服务单例
file_sync_service = FileSyncService()

# 以下是文件比较和同步相关的类和函数

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
        if self.mode == MatchMode.EXACT:
            return value_to_match == self.pattern_str
        elif self.mode == MatchMode.CONTAINS:
            return self.pattern_str in value_to_match
        elif self.mode == MatchMode.REGEX or self.mode == MatchMode.WILDCARD:
            if self._compiled_regex:
                return bool(self._compiled_regex.search(value_to_match))
            return False # Should not happen if constructor worked for these modes

        return False

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
            results["to_add"].append(src_item)

    if mode == "full_sync":
        for target_rel_path, target_item in target_map_by_rel_path.items():
            if target_rel_path not in accounted_target_paths:
                results["to_delete_from_target"].append(target_item)
    
    return results

def _parse_exclusion_rules(rules_def: Optional[List[ExclusionRuleDefinition]]) -> Optional[ItemFilter]:
    if not rules_def:
        return None
    item_filter = ItemFilter()
    for i, rule_data in enumerate(rules_def):
        try:
            item_filter.add_rule(ExclusionRule(
                pattern=rule_data.pattern,
                target=rule_data.target,
                item_type=rule_data.item_type,
                mode=rule_data.mode,
                case_sensitive=rule_data.case_sensitive
            ))
        except ValueError as e:
            # 抛出一个特定的错误，可以被 API 层捕获
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
        
        # 使用统一的调用方式
        result_list = await drive_manager.get_share_list(x_token, params)
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
        
        # 使用统一的调用方式
        result_list = await drive_manager.get_disk_list(x_token, params)
    
    # 应用过滤器
    if item_filter_instance:
        result_list = [item for item in result_list if not item_filter_instance.should_exclude(item)]
    
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

    # compare_drive_lists 返回基础的比较结果字典
    comparison_result = compare_drive_lists(
        source_list=source_list,
        target_list=target_list,
        mode=comparison_mode,
        rename_rules=parsed_rename_rules,
        source_base_path=source_definition.file_path,
        target_base_path=target_definition.file_path
    )
    
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
    drive_type_str: str
) -> Dict[str, Dict[str, List[str]]]:
    """
    根据比较结果执行相应的操作（添加、删除、重命名、更新）

    :param drive_manager: 网盘管理器实例
    :param x_token: 认证令牌
    :param comparison_result: 比较结果，包含to_add、to_delete_from_target等操作列表
    :param drive_type_str: 网盘类型字符串
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

    # 处理添加操作
    if comparison_result.to_add:
        add_results = await _process_add_operations(
            drive_manager=drive_manager,
            x_token=x_token,
            to_add=comparison_result.to_add,
            source_definition=comparison_result.source_definition,
            target_definition=comparison_result.target_definition,
            drive_type_str=drive_type_str,
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
    to_add: List[BaseFileInfo],
    source_definition: ShareSourceDefinition,
    target_definition: DiskTargetDefinition,
    drive_type_str: str,
    ext_transfer_params: Optional[Dict[str, Any]] = None
) -> Dict[str, List[str]]:
    """
    处理添加操作，包括创建目录和传输文件
    
    :param drive_manager: 网盘管理器实例
    :param x_token: 认证令牌
    :param to_add: 要添加的文件/目录列表
    :param source_definition: 源定义
    :param target_definition: 目标定义
    :param drive_type_str: 网盘类型字符串
    :param ext_transfer_params: 额外的传输参数
    :return: 操作结果，包含succeeded和failed两个列表
    """
    operation_results = {'succeeded': [], 'failed': []}

    sorted_to_add = sorted(to_add, key=lambda item: item.file_path)

    # 第一阶段：创建所有文件夹
    for item in sorted_to_add:
        if item.is_folder:
            relative_path_to_source_base = ""
            try:
                if item.file_path == source_definition.file_path or not item.file_path.startswith(source_definition.file_path):
                    if item.file_path == source_definition.file_path and source_definition.file_path != "/":
                         relative_path_to_source_base = os.path.basename(source_definition.file_path)
                    elif item.file_path.startswith(source_definition.file_path) and len(item.file_path) > len(source_definition.file_path) :
                         relative_path_to_source_base = item.file_path[len(source_definition.file_path):].lstrip('/')
                    else: # 分享根目录或直接项目名称（如果路径不按预期对齐）
                        relative_path_to_source_base = item.file_name
                else:
                    relative_path_to_source_base = os.path.relpath(item.file_path, start=source_definition.file_path)
            except ValueError as ve_path_mkdir:
                operation_results['failed'].append(f"MKDIR_PATH_ERROR: Folder {item.file_path} (relative to {source_definition.file_path}) - {str(ve_path_mkdir)}")
                continue
            
            # 确保使用正斜杠构建路径
            target_folder_full_path = os.path.join(target_definition.file_path, relative_path_to_source_base)
            target_folder_full_path = os.path.normpath(target_folder_full_path).replace("\\", "/")

            if not target_folder_full_path or target_folder_full_path == "/" or target_folder_full_path == ".":
                continue
            
            logger.debug(f"尝试创建目录: '{target_folder_full_path}'")

            try:
                # 构建 MkdirParam
                mkdir_params = MkdirParam(
                    drive_type=drive_type_str,
                    file_path=target_folder_full_path,
                    return_if_exist=True
                )
                
                await drive_manager.create_mkdir(x_token, mkdir_params)
                operation_results['succeeded'].append(f"MKDIR_CREATED_OR_EXISTS: {target_folder_full_path}")
            except Exception as e:
                operation_results['failed'].append(f"MKDIR_ERROR: {target_folder_full_path} - {str(e)}")

    # 第二阶段：按目标父目录分组文件
    files_to_transfer_by_target_parent: Dict[str, List[BaseFileInfo]] = defaultdict(list)
    for item in sorted_to_add:
        if not item.is_folder:
            relative_path_to_source_base = ""
            try:
                if item.file_path == source_definition.file_path or not item.file_path.startswith(source_definition.file_path):
                    if item.file_path == source_definition.file_path and source_definition.file_path != "/":
                         relative_path_to_source_base = os.path.basename(source_definition.file_path)
                    elif item.file_path.startswith(source_definition.file_path) and len(item.file_path) > len(source_definition.file_path) :
                         relative_path_to_source_base = item.file_path[len(source_definition.file_path):].lstrip('/')
                    else:
                        relative_path_to_source_base = item.file_name
                else: # item.file_path 是 source_definition.file_path 的子路径
                    relative_path_to_source_base = os.path.relpath(item.file_path, start=source_definition.file_path)
            except ValueError as ve_path_file:
                operation_results['failed'].append(f"FILE_PATH_ERROR: {item.file_path} (relative to {source_definition.file_path}) - {str(ve_path_file)}")
                continue

            # 确保使用正斜杠构建路径
            target_item_full_path = os.path.join(target_definition.file_path, relative_path_to_source_base)
            target_item_full_path = os.path.normpath(target_item_full_path).replace("\\", "/")
            target_parent_dir = os.path.dirname(target_item_full_path)
            
            # 确保父目录路径使用正斜杠
            target_parent_dir = target_parent_dir.replace("\\", "/")
            
            files_to_transfer_by_target_parent[target_parent_dir].append(item)

    # 第三阶段：执行文件传输
    for target_parent_dir, files_in_group in files_to_transfer_by_target_parent.items():
        if not files_in_group:
            continue

        # 确保目标路径使用正斜杠
        normalized_target_parent_dir = os.path.normpath(target_parent_dir).replace("\\", "/")
        
        try:
            source_fs_ids_to_transfer = [f.file_id for f in files_in_group]
            current_transfer_ext_params = {}
            if ext_transfer_params:
                current_transfer_ext_params = {**ext_transfer_params}
            
            # 直接传递第一个文件的完整file_ext字典
            if files_in_group and hasattr(files_in_group[0], 'file_ext') and files_in_group[0].file_ext:
                file_ext = files_in_group[0].file_ext
                if isinstance(file_ext, dict):
                    # 将file_ext中的所有参数合并到current_transfer_ext_params
                    current_transfer_ext_params.update(file_ext)
            
            # 如果source_definition有ext_params，也一并加入
            if hasattr(source_definition, 'ext_params') and source_definition.ext_params:
                if isinstance(source_definition.ext_params, dict):
                    # 将source_definition.ext_params中的所有参数合并到current_transfer_ext_params
                    # 这些参数会覆盖file_ext中的同名参数
                    current_transfer_ext_params.update(source_definition.ext_params)
            
            # 构建transfer所需参数
            try:
                # 构建 TransferParam
                transfer_params = TransferParam(
                    drive_type=drive_type_str,
                    source_type=source_definition.source_type,
                    source_id=source_definition.source_id,
                    source_path=source_definition.file_path,
                    target_path=normalized_target_parent_dir,
                    file_ids=source_fs_ids_to_transfer,
                    ext=current_transfer_ext_params
                )
                
                # 使用统一架构的transfer方法
                success_count = await drive_manager.transfer_files(x_token, transfer_params)
                
                # 记录成功的传输
                for file_to_log in files_in_group[:success_count]:
                    target_path = os.path.join(normalized_target_parent_dir, file_to_log.file_name).replace("\\", "/")
                    operation_results['succeeded'].append(f"TRANSFER_SUCCESS: {file_to_log.file_path} -> {target_path}")
                
                # 如果有失败的，也记录下来
                if success_count < len(files_in_group):
                    for file_to_log in files_in_group[success_count:]:
                        target_path = os.path.join(normalized_target_parent_dir, file_to_log.file_name).replace("\\", "/")
                        operation_results['failed'].append(f"TRANSFER_FAIL: {file_to_log.file_path} -> {target_path}")
            except Exception as ex_transfer:
                # 记录所有文件传输失败
                for file_to_log in files_in_group:
                    target_path = os.path.join(normalized_target_parent_dir, file_to_log.file_name).replace("\\", "/")
                    operation_results['failed'].append(f"TRANSFER_ERROR: {file_to_log.file_path} -> {target_path} - {str(ex_transfer)}")
        except Exception as ex_group:
            # 整组处理出错
            for file_to_log in files_in_group:
                target_path = os.path.join(normalized_target_parent_dir, file_to_log.file_name).replace("\\", "/")
                operation_results['failed'].append(f"TRANSFER_GROUP_ERROR: {file_to_log.file_path} -> {target_path} - {str(ex_group)}")
    
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