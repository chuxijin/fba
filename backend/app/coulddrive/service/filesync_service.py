#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
import time
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

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
        
        try:
            # 获取并验证配置
            config, error_msg = await sync_config_dao.get_with_validation(db, config_id)
            if not config:
                return {"success": False, "error": error_msg, "config_id": config_id, "elapsed_time": 0}
            
            # 检查任务是否过期 - 先转换为Python datetime进行比较
            if config.end_time:
                end_time_dt = config.end_time if isinstance(config.end_time, datetime) else datetime.fromisoformat(str(config.end_time))
                if datetime.now() > end_time_dt:
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
            #logger.info(f"同步任务记录创建成功，任务ID: {task_id}")
            
            # 立即更新配置的最后同步时间，防止并发执行
            try:
                config_update = UpdateSyncConfigParam(last_sync=datetime.now())
                await sync_config_dao.update(db, db_obj=config, obj_in=config_update)
                await db.commit()
                #logger.info(f"配置 {config_id} 的last_sync已在任务开始时更新")
            except Exception as update_error:
                logger.error(f"更新配置last_sync失败: {update_error}")
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
            
            #logger.info(f"开始执行同步 - 任务ID: {task_id}, 方式: {sync_method}, 源: {source_definition.file_path}, 目标: {target_definition.file_path}")
            
            # 执行同步
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
                db=db
            )
            
            # 计算执行时间并更新任务状态
            elapsed_time = int(time.time() - start_time)
            
            if sync_result.get("success", False):
                # 更新任务为成功状态
                start_time_dt = sync_task.start_time if isinstance(sync_task.start_time, datetime) else None
                update_params = UpdateSyncTaskParam(
                    status="completed",
                    dura_time=elapsed_time,
                    task_num=json.dumps(sync_result.get("stats", {})),
                    err_msg=None,
                    start_time=start_time_dt
                )
                await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)
                await db.commit()
                #logger.info(f"任务 {task_id} 状态更新为成功")
                
                # last_sync 已在任务开始时更新，无需重复更新
                
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
                start_time_dt = sync_task.start_time if isinstance(sync_task.start_time, datetime) else None
                update_params = UpdateSyncTaskParam(
                    status="failed",
                    dura_time=elapsed_time,
                    err_msg=error_msg,
                    task_num=json.dumps(sync_result.get("stats", {})),
                    start_time=start_time_dt
                )
                await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)
                await db.commit()
                #logger.info(f"任务 {task_id} 状态更新为失败")
                
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
            logger.warning(f"未知的同步方式: {method_str}，使用默认增量同步")
            return SyncMethod.INCREMENTAL.value

    def _parse_recursion_speed(self, speed_value: int) -> RecursionSpeed:
        """解析递归速度"""
        if speed_value == 1:
            return RecursionSpeed.SLOW
        elif speed_value == 2:
            return RecursionSpeed.FAST
        else:
            return RecursionSpeed.NORMAL
    
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
        start_time = time.time()
        
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
            "start_time": datetime.fromtimestamp(start_time).isoformat(),
        }
        
        try:
            #self.logger.info(f"[任务{task_id or 'unknown'}] 开始执行同步 - 方式: {sync_method}, 源: {source_definition.file_path}, 目标: {target_definition.file_path}")
            
            # 根据同步方式选择处理逻辑
            if sync_method == "overwrite":
                # 覆盖同步：先删除目标目录所有文件，再转存源目录所有文件
                await self._handle_overwrite_sync(
                    x_token, drive_type, source_definition, target_definition,
                    recursion_speed, item_filter, stats, task_id, db
                )
            else:
                # 增量同步和完全同步：使用标准递归逻辑
                await self.sync_with_have(
                    x_token, drive_type, source_definition, target_definition,
                    source_definition.file_path, target_definition.file_path, target_definition.file_id,
                    sync_method, recursion_speed, item_filter, 0, max_depth, stats, task_id, db
                )
            
        except Exception as e:
            error_msg = f"同步失败: {str(e)}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)
        
        # 计算总耗时
        elapsed_time = time.time() - start_time
        stats["elapsed_time"] = elapsed_time
        stats["end_time"] = datetime.fromtimestamp(time.time()).isoformat()
        
        # 判断同步是否成功 - 有错误就是失败
        success = len(stats["errors"]) == 0
        
        #self.logger.info(f"[任务{task_id or 'unknown'}] 同步完成 - 成功: {success}, 错误数: {len(stats['errors'])}, 统计: {stats}")
        
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
        if current_depth >= max_depth:
            self.logger.warning(f"[任务{task_id or 'unknown'}] 达到最大递归深度 {max_depth}，停止递归")
            return
        
        try:
            #self.logger.info(f"[任务{task_id or 'unknown'}] sync_with_have - 源: {source_path}, 目标: {target_path}, 深度: {current_depth}")
            
            # 获取源文件和目标文件映射（文件名 -> 文件大小）
            source_file_map = await self.list_dir(
                source_path, True, item_filter, True, x_token, drive_type, source_definition, task_id=task_id, db=db
        )
            target_file_map = await self.list_dir(
                target_path, False, item_filter, False, x_token, drive_type, target_definition, target_id, task_id, db
            )
            
            #self.logger.info(f"[任务{task_id or 'unknown'}] 源目录文件数: {len(source_file_map)}, 目标目录文件数: {len(target_file_map)}")
            
        except Exception as e:
            error_msg = f"扫描目录失败: {source_path} -> {target_path}, 错误: {str(e)}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)
            return
        
        # 收集当前目录下需要转存的文件
        files_to_transfer = []
        
        # 处理源目录中的每个文件/目录
        for file_name, file_info in source_file_map.items():
            # 如果是文件
            if not file_name.endswith('/'):
                stats["files_processed"] += 1  # 增加文件处理计数
                # 目标目录没有这个文件或文件大小不匹配(即需要同步)
                target_file_info = target_file_map.get(file_name, {})
                source_file_size = file_info.get("file_size", 0)
                target_file_size = target_file_info.get("file_size", -1)  # 用-1表示不存在
                
                if file_name not in target_file_map or target_file_size != source_file_size:
                    #self.logger.info(f"[任务{task_id or 'unknown'}] 需要转存文件: {file_name} (大小: {source_file_size})")
                    
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
                else:
                    stats["files_skipped"] += 1
                    #self.logger.debug(f"[任务{task_id or 'unknown'}] 跳过相同文件: {file_name}")
                    # 跳过的文件不需要记录到数据库任务项
                    # 只在日志中记录即可
            # 如果是目录
            elif file_name.endswith('/'):
                dir_name = file_name.rstrip('/')
                source_sub_path = source_path.rstrip('/') + '/' + dir_name + '/'
                target_sub_path = target_path.rstrip('/') + '/' + dir_name + '/'
                
                #self.logger.info(f"[任务{task_id or 'unknown'}] 处理目录: {dir_name}, 源子路径: {source_sub_path}, 目标子路径: {target_sub_path}")
                
                # 目标目录没有这个目录
                if file_name not in target_file_map:
                    #self.logger.info(f"[任务{task_id or 'unknown'}] 目标不存在目录，使用sync_without_have: {dir_name}")
                    await self.sync_without_have(
                        x_token, drive_type, source_definition, target_definition,
                        source_sub_path, target_sub_path,
                        sync_method, recursion_speed, item_filter, current_depth + 1, max_depth, stats, task_id, db
                    )
                # 目标目录有这个目录，继续递归
                else:
                    #self.logger.info(f"[任务{task_id or 'unknown'}] 目标存在目录，继续递归: {dir_name}")
                    # 获取子目录的file_id
                    target_sub_file_id = target_file_map.get(file_name, {}).get("file_id", "")
                    await self.sync_with_have(
                        x_token, drive_type, source_definition, target_definition,
                        source_sub_path, target_sub_path, target_sub_file_id,  # 使用子目录的file_id
                        sync_method, recursion_speed, item_filter, current_depth + 1, max_depth, stats, task_id, db
                    )
        
        # 批量转存当前目录下需要同步的文件
        if files_to_transfer:
            #self.logger.info(f"[任务{task_id or 'unknown'}] 批量转存当前目录 {len(files_to_transfer)} 个文件: {[f['file_name'] for f in files_to_transfer]}")
            transfer_result = await self.transfer_files(
                x_token, drive_type, source_definition, target_definition,
                files_to_transfer,
                recursion_speed, stats, task_id, db
            )
            
            # 智能错误处理：根据错误类型决定是否继续
            if not transfer_result:
                should_continue = await self._handle_transfer_error(stats, task_id, target_path)
                if not should_continue:
                    self.logger.warning(f"[任务{task_id or 'unknown'}] 检测到严重错误，终止同步任务")
                    return
        
        # 如果是完全同步，删除目标目录中多余的文件
        if sync_method == "full":
            files_to_delete = []
            for target_file_name, target_file_info in target_file_map.items():
                if target_file_name not in source_file_map:
                    target_file_size = target_file_info.get("file_size", 0)
                    target_file_id = target_file_info.get("file_id", "")
                    files_to_delete.append({
                        "file_name": target_file_name,
                        "file_size": target_file_size,
                        "target_path": target_path,
                        "file_id": target_file_id  # 添加file_id信息
                    })
            
            if files_to_delete:
                #self.logger.info(f"[任务{task_id or 'unknown'}] 完全同步模式，需要删除 {len(files_to_delete)} 个多余文件")
                await self.delete_files(
                    x_token, drive_type, target_definition, files_to_delete,
                    recursion_speed, stats, task_id, db
                )
    
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
        if current_depth >= max_depth:
            self.logger.warning(f"[任务{task_id or 'unknown'}] 达到最大递归深度 {max_depth}，停止递归")
            return
        
        #self.logger.info(f"[任务{task_id or 'unknown'}] sync_without_have - 源: {source_path}, 目标: {target_path}, 深度: {current_depth}")
        
        # 创建目标目录
        dir_name = target_path.rstrip('/').split('/')[-1]
        created_dir_info = await self.create_directory(
            x_token, drive_type, target_definition, dir_name, task_id, db
        )
        if not created_dir_info:
            error_msg = f"创建目录失败: {target_path}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}")
            stats["errors"].append(error_msg)
            return
        
        stats["folder_created"] += 1
        #self.logger.info(f"[任务{task_id or 'unknown'}] 成功创建目录: {dir_name}, file_id: {created_dir_info.file_id}")
        
        # 记录创建目录的任务项
        if task_id and db:
            await self.record_task_item(
                task_id, "create", source_path, target_path, dir_name, 0, 
                "completed", None, db
            )
        
        # 更新target_definition为新创建的目录
        target_definition = DiskTargetDefinition(
            file_path=target_path,
            file_id=created_dir_info.file_id
        )
        
        try:
            # 获取源目录文件列表
            source_file_map = await self.list_dir(
                source_path, True, item_filter, True, x_token, drive_type, source_definition, task_id=task_id, db=db
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
                
                #self.logger.info(f"[任务{task_id or 'unknown'}] 递归处理子目录: {dir_name}, 源: {source_sub_path}, 目标: {target_sub_path}")
                await self.sync_without_have(
                    x_token, drive_type, source_definition, target_definition,
                    source_sub_path, target_sub_path,
                    sync_method, recursion_speed, item_filter, current_depth + 1, max_depth, stats, task_id, db
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
            #self.logger.info(f"[任务{task_id or 'unknown'}] 批量转存当前目录 {len(files_to_transfer)} 个文件: {[f['file_name'] for f in files_to_transfer]}")
            transfer_result = await self.transfer_files(
                x_token, drive_type, source_definition, target_definition,
                files_to_transfer,
                recursion_speed, stats, task_id, db
            )
            
            # 智能错误处理：根据错误类型决定是否继续
            if not transfer_result:
                should_continue = await self._handle_transfer_error(stats, task_id, target_path)
                if not should_continue:
                    self.logger.warning(f"[任务{task_id or 'unknown'}] 检测到严重错误，终止同步任务")
                    return

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
        try:
            #self.logger.info(f"[任务{task_id or 'unknown'}] 开始扫描目录: {path}, 是否源目录: {is_src}")
            
            if is_src:
                # 获取源文件列表
                from backend.app.coulddrive.schema.file import ListShareFilesParam
                params = ListShareFilesParam(
                drive_type=drive_type,
                    source_type=definition.source_type,
                    source_id=definition.source_id,
                    file_path=path
                )
                #self.logger.info(f"[任务{task_id or 'unknown'}] 调用get_share_list - 参数: drive_type={drive_type}, source_type={definition.source_type}, source_id={definition.source_id}, file_path={path}")
                
                files = await self.drive_manager.get_share_list(x_token, params, db=db, **kwargs)
                #self.logger.info(f"[任务{task_id or 'unknown'}] get_share_list返回 {len(files)} 个文件")
                
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
                #self.logger.info(f"[任务{task_id or 'unknown'}] 调用get_disk_list - 参数: drive_type={drive_type}, file_path={path}, file_id={target_id or ''}")
                
                files = await self.drive_manager.get_disk_list(x_token, params, db=db, **kwargs)
                #self.logger.info(f"[任务{task_id or 'unknown'}] get_disk_list返回 {len(files)} 个文件")
            
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
            
            #self.logger.info(f"[任务{task_id or 'unknown'}] 目录扫描完成: {path}, 有效文件数: {len(file_map)}")
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
        **kwargs
    ) -> bool:
        """
        批量转存文件 - 构建正确的扩展参数对应关系
        
        Args:
            files: 文件列表，格式：[{"file_name": "xxx", "file_size": 123, "source_path": "xxx", "target_path": "xxx", "file_id": "xxx", "share_fid_token": "xxx", ...}]
        """
        if not files:
            return True
        
        try:
            #self.logger.info(f"[任务{task_id or 'unknown'}] 开始批量转存 {len(files)} 个文件")
            
            # 提取文件ID列表
            file_ids = []
            for file_info in files:
                file_id = file_info.get("file_id", "")
                if not file_id:
                    error_msg = f"文件 {file_info.get('file_name', '')} 缺少file_id"
                    self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}")
                    stats["errors"].append(error_msg)
                    if task_id and db:
                        await self.record_task_item(
                            task_id, "copy", file_info.get("source_path", ""), file_info.get("target_path", ""),
                            file_info.get("file_name", ""), file_info.get("file_size", 0), "failed", error_msg, db
                        )
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
                    if key not in ["file_name", "file_size", "source_path", "target_path", "file_id"]:
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
            
            #self.logger.info(f"[任务{task_id or 'unknown'}] 文件列表: {[f['file_name'] for f in files]}")
            #self.logger.info(f"[任务{task_id or 'unknown'}] 构建了 {len(files_ext_info)} 个文件的扩展信息")
            
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
            
            result = await self.drive_manager.transfer_files(x_token, params, db=db, **kwargs)
            
            if result:
                stats["files_transferred"] += len(files)
                #self.logger.info(f"[任务{task_id or 'unknown'}] 批量转存成功: {len(files)} 个文件")
                
                # 记录成功的文件
                for file_info in files:
                    if task_id and db:
                        await self.record_task_item(
                            task_id, "copy", file_info.get("source_path", ""), file_info.get("target_path", ""),
                            file_info.get("file_name", ""), file_info.get("file_size", 0), "completed", None, db
                        )
            else:
                error_msg = f"批量转存失败：API返回False，涉及 {len(files)} 个文件"
                self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}")
                stats["errors"].append(error_msg)
                
                # 记录失败的文件
                for file_info in files:
                    if task_id and db:
                        await self.record_task_item(
                            task_id, "copy", file_info.get("source_path", ""), file_info.get("target_path", ""),
                            file_info.get("file_name", ""), file_info.get("file_size", 0), "failed", error_msg, db
                        )
            
            # 速度控制
            if recursion_speed == RecursionSpeed.SLOW:
                await asyncio.sleep(2)
            elif recursion_speed == RecursionSpeed.NORMAL:
                await asyncio.sleep(1)
            # 快速模式不暂停
            
            return result
            
        except Exception as e:
            error_msg = f"批量转存异常: {str(e)}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)
            
            # 记录所有文件失败
            for file_info in files:
                if task_id and db:
                    await self.record_task_item(
                        task_id, "copy", file_info.get("source_path", ""), file_info.get("target_path", ""),
                        file_info.get("file_name", ""), file_info.get("file_size", 0), "failed", error_msg, db
                    )
            
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
        **kwargs
    ) -> bool:
        """
        批量删除文件 - 保持技术优势
        
        Args:
            files: 文件列表，格式：[{"file_name": "xxx", "file_size": 123, "target_path": "xxx"}]
        """
        if not files:
            return True
            
        try:
            #self.logger.info(f"[任务{task_id or 'unknown'}] 开始批量删除 {len(files)} 个文件")
            
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
            
            # 打印删除请求的详细参数
            #self.logger.info(f"[任务{task_id or 'unknown'}] 调用remove_files - 参数: drive_type={drive_type}, file_paths={file_paths}, file_ids={file_ids}, parent_id={target_definition.file_id}, file_name=None")
            #self.logger.info(f"[任务{task_id or 'unknown'}] 删除文件详情: {files}")
            
            result = await self.drive_manager.remove_files(x_token, params, db=db, **kwargs)
            
            #self.logger.info(f"[任务{task_id or 'unknown'}] remove_files返回结果: {result}")
            
            if result:
                stats["files_deleted"] += len(files)
                # 记录删除的文件
                for file_info in files:
                    self.logger.debug(f"删除成功: {file_info['file_name']}")
                    # 记录任务项
                    if task_id and db:
                        await self.record_task_item(
                            task_id, "delete", "", file_info["target_path"],
                            file_info["file_name"], file_info["file_size"], "completed", None, db
                        )
            else:
                error_msg = f"批量删除失败，涉及 {len(files)} 个文件"
                self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}")
                stats["errors"].append(error_msg)
                # 记录失败的文件
                for file_info in files:
                    if task_id and db:
                        await self.record_task_item(
                            task_id, "delete", "", file_info["target_path"],
                            file_info["file_name"], file_info["file_size"], "failed", error_msg, db
                        )
            
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
                if task_id and db:
                    await self.record_task_item(
                        task_id, "delete", "", file_info["target_path"],
                        file_info["file_name"], file_info["file_size"], "failed", error_msg, db
                    )
            
            return False
    
    async def create_directory(
        self,
        x_token: str,
        drive_type: DriveType,
        target_definition: DiskTargetDefinition,
        dir_name: str,
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
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
            result = await self.drive_manager.create_mkdir(x_token, params, db=db, **kwargs)
            
            # create_mkdir返回BaseFileInfo对象，如果成功创建则有file_id
            if result is not None and result.file_id is not None:
                return result
            else:
                self.logger.error(f"创建目录失败: {dir_name}")
                return None
            
        except Exception as e:
            self.logger.error(f"创建目录失败: {e}")
            return None

    async def record_task_item(
        self,
        task_id: int,
        operation_type: str,
        src_path: str,
        dst_path: str,
        file_name: str,
        file_size: int,
        status: str,
        err_msg: Optional[str],
        db: AsyncSession
    ) -> None:
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
            db: 数据库会话
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
            
            await sync_task_item_dao.create(db, obj_in=task_item_params)
            # 注意：这里不提交事务，由上层统一提交
            
        except Exception as e:
            self.logger.error(f"记录任务项失败: {e}")
    
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
        **kwargs
    ) -> None:
        """
        处理覆盖同步：先删除目标目录所有文件，再一次性转存源目录所有内容
        """
        try:
            # 1. 获取目标目录所有文件
            target_file_map = await self.list_dir(
                target_definition.file_path, False, item_filter, False, 
                x_token, drive_type, target_definition, target_definition.file_id, task_id, db
            )
            
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
                await self.delete_files(
                    x_token, drive_type, target_definition, files_to_delete,
                    recursion_speed, stats, task_id, db
                )
            
            # 3. 一次性转存整个源目录的所有内容
            # 获取源目录的第一层文件列表
            source_file_map = await self.list_dir(
                source_definition.file_path, True, item_filter, True, 
                x_token, drive_type, source_definition, task_id=task_id, db=db
            )
            
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
                
                # 批量转存所有内容（正确构建参数对应关系）
                #self.logger.info(f"[任务{task_id or 'unknown'}] 覆盖同步：批量转存 {len(all_files_to_transfer)} 个项目")
                transfer_result = await self.transfer_files(
                    x_token, drive_type, source_definition, target_definition,
                    all_files_to_transfer, recursion_speed, stats, task_id, db
                )
                
                # 智能错误处理：根据错误类型决定是否继续
                if not transfer_result:
                    should_continue = await self._handle_transfer_error(stats, task_id, target_definition.file_path)
                    if not should_continue:
                        self.logger.warning(f"[任务{task_id or 'unknown'}] 覆盖同步检测到严重错误，终止任务")
                        return
                
        except Exception as e:
            error_msg = f"覆盖同步失败: {str(e)}"
            self.logger.error(f"[任务{task_id or 'unknown'}] {error_msg}")
            stats["errors"].append(error_msg)

    async def _handle_transfer_error(
        self,
        stats: Dict[str, Any],
        task_id: Optional[int],
        current_path: str
    ) -> bool:
        """
        智能错误处理：根据错误类型决定是否继续执行
        
        Args:
            stats: 任务统计信息
            task_id: 任务ID
            current_path: 当前处理的路径
            
        Returns:
            bool: True=继续执行, False=终止任务
        """
        if not stats.get("errors"):
            return True
        
        # 检查总错误数量 - 超过5个就终止
        if len(stats["errors"]) >= 5:
            logger.error(f"[任务{task_id or 'unknown'}] 总错误数量达到5个，终止任务")
            stats["errors"].append(f"任务终止：总错误数量达到{len(stats['errors'])}个")
            return False
        
        # 获取最近的错误信息
        latest_error = stats["errors"][-1] if stats["errors"] else ""
        
        # 错误类型分析
        if "error_code: 111" in latest_error or "当前还有未完成的任务" in latest_error:
            # 账户冲突错误：当前还有未完成的任务，需完成后才能操作
            logger.warning(f"[任务{task_id or 'unknown'}] 检测到账户冲突错误，暂停30秒后重试")
            await asyncio.sleep(30)
            
            # 检查连续冲突次数
            conflict_count = sum(1 for error in stats["errors"] 
                               if "error_code: 111" in error or "当前还有未完成的任务" in error)
            if conflict_count >= 3:
                logger.error(f"[任务{task_id or 'unknown'}] 连续3次账户冲突，终止任务避免资源浪费")
                stats["errors"].append(f"任务终止：连续{conflict_count}次账户冲突")
                return False
            
            return True  # 继续重试
            
        elif "批量转存失败：API返回False" in latest_error or "转存失败" in latest_error:
            # 转存失败：暂停30秒后重试
            logger.warning(f"[任务{task_id or 'unknown'}] 转存失败，暂停30秒后重试")
            await asyncio.sleep(30)
            
            # 检查连续转存失败次数
            transfer_fail_count = sum(1 for error in stats["errors"] 
                                    if "批量转存失败" in error or "转存失败" in error)
            if transfer_fail_count >= 3:
                logger.error(f"[任务{task_id or 'unknown'}] 连续3次转存失败，终止任务")
                stats["errors"].append(f"任务终止：连续{transfer_fail_count}次转存失败")
                return False
                
            return True
            
        elif "批量删除失败" in latest_error or "删除失败" in latest_error or "error_code: 31066" in latest_error:
            # 删除失败：直接跳过，不影响任务继续
            logger.info(f"[任务{task_id or 'unknown'}] 删除失败，跳过继续处理: {current_path}")
            return True
            
        elif ("error_code: 6" in latest_error or "网络" in latest_error or 
              "timeout" in latest_error.lower() or "Expecting value" in latest_error):
            # 网络相关错误：等10秒，最多两次
            logger.warning(f"[任务{task_id or 'unknown'}] 检测到网络错误，暂停10秒后继续")
            await asyncio.sleep(10)
            
            # 检查网络错误次数
            network_error_count = sum(1 for error in stats["errors"] 
                                    if ("error_code: 6" in error or "网络" in error or 
                                        "timeout" in error.lower() or "Expecting value" in error))
            if network_error_count >= 2:
                logger.error(f"[任务{task_id or 'unknown'}] 网络错误达到2次，终止任务")
                stats["errors"].append(f"任务终止：网络错误达到{network_error_count}次")
                return False
                
            return True
            
        else:
            # 其他未知错误：记录但继续执行
            logger.warning(f"[任务{task_id or 'unknown'}] 未知错误类型，继续执行: {latest_error[:100]}...")
            return True


# 全局实例
file_sync_service = FileSyncService()


def get_file_sync_service() -> FileSyncService:
    """获取文件同步服务实例"""
    return file_sync_service