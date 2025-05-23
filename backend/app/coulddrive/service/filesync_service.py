"""
文件名: fileSync.py
描述: 网盘文件同步服务，处理文件同步操作
作者: PanMaster团队
创建日期: 2024-07-20
版本: 1.0.0
"""

import logging
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.coulddrive.service.drivebase_service import BaseDrive, get_drive_client
from app.coulddrive.service.utils import parse_cookie_string
from app.coulddrive.service.server import (
    perform_comparison_logic, apply_comparison_operations
)
from app.coulddrive.schema.enum import DriveType, RecursionSpeed, SyncMethod
from app.coulddrive.schema.file import (
    ShareSourceDefinition, DiskTargetDefinition,
    CompareResultData, BaseFileInfo
)
from app.schemas.sync.sync_config import SyncConfigInDB
from app.schemas.drive_accounts import DriveAccount

# 导入模型
from app.models.sync.sync_task import SyncTask
from app.models.sync.sync_task_item import SyncTaskItem

# 导入CRUD操作
from app.db.crud.sync.sync_task_crud import (
    create_sync_task, start_sync_task, complete_sync_task, 
    fail_sync_task, update_sync_task_status
)
from app.db.crud.sync.sync_task_item_crud import (
    batch_create_sync_task_items, update_sync_task_item_status
)

logger = logging.getLogger(__name__)

class FileSyncService:
    """文件同步服务类
    
    基于同步配置(SyncConfigInDB)执行文件同步操作
    """
    
    def __init__(self):
        """初始化文件同步服务"""
        self.clients = {}  # 客户端缓存
        self.type_mappings = {
            "baidu": DriveType.BAIDU_DRIVE,
            # 移除 baidu_drive 映射，只保留小写的 baidu
        }
    
    def _map_account_type_to_drive_type(self, account_type: str) -> Optional[DriveType]:
        """将账号类型映射到驱动类型
        
        Args:
            account_type: 账号类型字符串
            
        Returns:
            Optional[DriveType]: 对应的驱动类型，如果不支持则返回None
        """
        account_type_lower = account_type.lower()
        drive_type = self.type_mappings.get(account_type_lower)
        
        # 兼容处理，对于不支持的类型但是以"baidu"开头的，尝试使用BAIDU_DRIVE
        if drive_type is None and account_type_lower.startswith("baidu"):
            logger.warning(f"账号类型 '{account_type}' 不在支持列表中，但以'baidu'开头，尝试使用BAIDU_DRIVE")
            return DriveType.BAIDU_DRIVE
            
        return drive_type
    
    def _get_drive_client(self, account: DriveAccount) -> Optional[BaseDrive]:
        """获取网盘客户端实例
        
        Args:
            account: 网盘账号信息
            
        Returns:
            Optional[BaseDrive]: 网盘客户端实例
        """
        client_key = f"account_{account.id}"
        
        # 检查缓存
        if client_key in self.clients:
            logger.debug(f"使用缓存的网盘客户端: {client_key}")
            return self.clients[client_key]
        
        # 解析网盘类型
        drive_type = self._map_account_type_to_drive_type(account.type)
        
        if not drive_type:
            logger.error(f"不支持的网盘类型: {account.type}，支持的类型: {list(self.type_mappings.keys())}")
            return None
        
        logger.debug(f"账号类型 {account.type} 映射到驱动类型 {drive_type.name}")
        
        try:
            # 使用通用的cookie解析函数，传入网盘类型
            auth_info = parse_cookie_string(account.cookies, "baidu")  # 固定使用 "baidu" 类型进行解析
            logger.debug(f"解析cookie获取到的认证信息包含字段: {', '.join(auth_info.keys())}")
            
            # 构建客户端配置，添加账号ID
            client_config = {
                **auth_info,  # 展开auth_info中的所有键值对
                "user_id": account.accountId
            }
            logger.debug(f"客户端配置包含字段: {', '.join(client_config.keys())}")
            
            # 创建客户端
            logger.debug(f"创建客户端时使用的驱动类型: {drive_type.name}, 驱动值: {drive_type.value}")
            client = get_drive_client(drive_type, **client_config)
            if client:
                self.clients[client_key] = client
                logger.info(f"已创建网盘客户端: {client_key}, 类型: {client.__class__.__name__}")
            else:
                logger.error(f"创建网盘客户端失败: {account.type}")
            
            return client
        except Exception as e:
            logger.error(f"处理网盘客户端时发生错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _parse_sync_method(self, method_str: str) -> str:
        """解析同步方式
        
        Args:
            method_str: 同步方式字符串
            
        Returns:
            str: 标准化的同步方式
        """
        # 尝试匹配枚举值
        method_lower = method_str.lower() if method_str else ""
        
        if method_lower == "copy" or method_lower == "incremental":
            return SyncMethod.INCREMENTAL.value
        elif method_lower == "full" or method_lower == "mirror":
            return SyncMethod.FULL.value
        elif method_lower == "overwrite" or method_lower == "replace":
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

    async def perform_sync(self, sync_config: SyncConfigInDB) -> Dict[str, Any]:
        """执行同步任务
        
        Args:
            sync_config: 同步配置
            
        Returns:
            Dict[str, Any]: 同步结果
        """
        start_time = time.time()
        logger.info(f"开始执行同步任务: {sync_config.id} - {sync_config.remark or '未命名任务'}")
        
        account_schema: Optional[DriveAccount] = None # Changed name for clarity
        try:
            from app.db.session import AsyncSessionLocal
            # Use the existing CRUD function
            from app.db.crud.drive_accounts_crud import get_drive_account as crud_get_drive_account
            from app.schemas.drive_accounts import DriveAccount as DriveAccountSchema # Pydantic schema
            
            logger.info(f"尝试根据accountId={sync_config.accountId}从数据库获取账号")
            async with AsyncSessionLocal() as db:
                account_schema = await crud_get_drive_account(db, sync_config.accountId)
                
                if not account_schema:
                    error_msg = f"未找到ID为{sync_config.accountId}的账号，无法执行同步任务"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "elapsed_time": time.time() - start_time
                    }
                
                # 不需要再次转换，account_schema已经是Pydantic模型
                logger.info(f"成功获取到账号: {account_schema.nickname} (ID: {account_schema.id})")
        except Exception as e:
            error_msg = f"获取账号时发生错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }
        
        # account_schema is now the Pydantic model, use it below
        # Verification of account and config relationship
        if sync_config.accountId != account_schema.id:
            error_msg = f"严重的内部错误: 同步配置 {sync_config.id} 的账号ID({sync_config.accountId})与获取到的账号ID({account_schema.id})不匹配"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }
        
        # Validate account parameters (now using account_schema)
        if not hasattr(account_schema, "cookies") or not account_schema.cookies:
            error_msg = f"账号 {account_schema.id} 缺少cookies字段，无法执行同步"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }
        
        # Validate account type (now using account_schema)
        if not hasattr(account_schema, "type") or not account_schema.type:
            error_msg = f"账号 {account_schema.id} 缺少type字段，无法确定网盘类型"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }
        
        # Get cloud drive client (passing the Pydantic model)
        drive_client = self._get_drive_client(account_schema)
        if not drive_client:
            error_msg = f"获取网盘客户端失败，账号ID: {account_schema.id}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "elapsed_time": time.time() - start_time
            }
        
        try:
            # 解析源信息
            src_meta = {}
            if sync_config.srcMeta:
                try:
                    src_meta = json.loads(sync_config.srcMeta)
                except json.JSONDecodeError:
                    logger.warning(f"解析源元数据失败: {sync_config.srcMeta}")
            
            # 解析目标信息
            dst_meta = {}
            if sync_config.dstMeta:
                try:
                    dst_meta = json.loads(sync_config.dstMeta)
                except json.JSONDecodeError:
                    logger.warning(f"解析目标元数据失败: {sync_config.dstMeta}")
            
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
            sync_method = self._parse_sync_method(sync_config.method)
            recursion_speed = self._parse_recursion_speed(sync_config.speed)
            
            # 构建源定义
            source_definition = ShareSourceDefinition(
                source_type=src_meta.get("source_type", "friend"),
                source_id=src_meta.get("source_id", ""),
                file_path=sync_config.srcPath,
                ext_params=src_meta.get("ext_params", {})
            )
            
            # 构建目标定义
            target_definition = DiskTargetDefinition(
                file_path=sync_config.dstPath,
                file_id=dst_meta.get("file_id", "")
            )
            
            # 执行比较逻辑
            comparison_result = await perform_comparison_logic(
                drive_client=drive_client,
                source_definition=source_definition,
                target_definition=target_definition,
                recursive=True,  # 始终递归处理
                recursion_speed=recursion_speed,
                comparison_mode=sync_method,
                exclude_rules_def=exclude_rules,
                rename_rules_def=rename_rules,
                drive_type_str=drive_client.drive_type
            )
            
            # 应用比较结果
            operation_results = await apply_comparison_operations(
                drive_client=drive_client,
                comparison_result=comparison_result
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
        sync_config: SyncConfigInDB, 
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
        task_data = {
            "configId": sync_config.id,
            "status": "pending",
        }
        task = await create_sync_task(db, task_data)
        task_id = task.id
        
        try:
            # 获取账号信息
            from app.db.crud.drive_accounts_crud import get_drive_account as crud_get_drive_account
            from app.schemas.drive_accounts import DriveAccount as DriveAccountSchema # Pydantic schema
            
            account_schema = await crud_get_drive_account(db, sync_config.accountId)
            
            if not account_schema:
                error_msg = f"未找到ID为{sync_config.accountId}的关联账号，无法执行同步任务"
                logger.error(error_msg)
                await fail_sync_task(db, task_id, error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "task_id": task_id,
                    "elapsed_time": time.time() - start_time
                }
            
            logger.info(f"任务 {task_id}: 成功获取并转换账号 {account_schema.nickname} (ID: {account_schema.id}) for config {sync_config.id}")
            
            # 获取网盘客户端
            drive_client = self._get_drive_client(account_schema)
            if not drive_client:
                error_msg = f"获取网盘客户端失败，账号ID: {account_schema.id}"
                logger.error(error_msg)
                await fail_sync_task(db, task_id, error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "task_id": task_id,
                    "elapsed_time": time.time() - start_time
                }
            
            # 解析配置信息
            src_meta = {}
            if sync_config.srcMeta:
                try:
                    src_meta = json.loads(sync_config.srcMeta)
                except json.JSONDecodeError:
                    logger.warning(f"解析源元数据失败: {sync_config.srcMeta}")
            
            dst_meta = {}
            if sync_config.dstMeta:
                try:
                    dst_meta = json.loads(sync_config.dstMeta)
                except json.JSONDecodeError:
                    logger.warning(f"解析目标元数据失败: {sync_config.dstMeta}")
            
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
            sync_method = self._parse_sync_method(sync_config.method)
            recursion_speed = self._parse_recursion_speed(sync_config.speed)
            
            # 构建源定义和目标定义
            source_definition = ShareSourceDefinition(
                source_type=src_meta.get("source_type", "friend"),
                source_id=src_meta.get("source_id", ""),
                file_path=sync_config.srcPath,
                ext_params=src_meta.get("ext_params", {})
            )
            
            target_definition = DiskTargetDefinition(
                file_path=sync_config.dstPath,
                file_id=dst_meta.get("file_id", "")
            )
            
            # 执行比较逻辑
            comparison_result = await perform_comparison_logic(
                drive_client=drive_client,
                source_definition=source_definition,
                target_definition=target_definition,
                recursive=True,
                recursion_speed=recursion_speed,
                comparison_mode=sync_method,
                exclude_rules_def=exclude_rules,
                rename_rules_def=rename_rules,
                drive_type_str=drive_client.drive_type
            )
            
            # 准备任务项记录
            task_items_data = []
            
            # 添加操作的任务项
            for item in comparison_result.to_add:
                task_items_data.append({
                    "taskId": task_id,
                    "type": "copy",
                    "srcPath": item.file_path,
                    "dstPath": f"{comparison_result.target_definition.file_path}/{item.file_name}",
                    "fileName": item.file_name,
                    "fileSize": item.file_size or 0,
                    "status": "pending"
                })
            
            # 删除操作的任务项
            for item in comparison_result.to_delete_from_target:
                task_items_data.append({
                    "taskId": task_id,
                    "type": "delete",
                    "srcPath": "",
                    "dstPath": item.file_path,
                    "fileName": item.file_name,
                    "fileSize": item.file_size or 0,
                    "status": "pending"
                })
            
            # 创建任务项记录
            total_items = len(task_items_data)
            if task_items_data:
                await batch_create_sync_task_items(db, task_items_data)
            
            # 更新任务状态为运行中
            await start_sync_task(db, task_id, total_items)
            
            # 执行同步操作
            operation_results = await apply_comparison_operations(
                drive_client=drive_client,
                comparison_result=comparison_result
            )
            
            # 更新任务项状态
            added_success = 0
            added_fail = 0
            deleted_success = 0
            deleted_fail = 0
            
            # 处理添加操作的结果
            add_results = operation_results.get("add", {})
            
            # 成功添加的文件
            for file_info in add_results.get("succeeded", []):
                if ":" in file_info:
                    file_path = file_info.split(":", 1)[1].strip()
                    file_name = file_path.split("/")[-1] if "/" in file_path else file_path
                    
                    # 使用ORM方式更新
                    result = await db.execute(
                        select(SyncTaskItem).where(
                            (SyncTaskItem.taskId == task_id) &
                            (SyncTaskItem.type == "copy") &
                            (SyncTaskItem.fileName == file_name)
                        )
                    )
                    item = result.scalars().first()
                    if item:
                        item.status = "completed"
                        added_success += 1
            
            # 失败添加的文件
            for file_info in add_results.get("failed", []):
                if ":" in file_info:
                    file_path = file_info.split(":", 1)[1].strip()
                    error_msg = file_info.split(":", 1)[0].strip()
                    file_name = file_path.split("/")[-1] if "/" in file_path else file_path
                    
                    # 使用ORM方式更新
                    result = await db.execute(
                        select(SyncTaskItem).where(
                            (SyncTaskItem.taskId == task_id) &
                            (SyncTaskItem.type == "copy") &
                            (SyncTaskItem.fileName == file_name)
                        )
                    )
                    item = result.scalars().first()
                    if item:
                        item.status = "failed"
                        item.errMsg = error_msg
                        added_fail += 1
            
            # 处理删除操作的结果
            delete_results = operation_results.get("delete", {})
            
            # 成功删除的文件
            for file_info in delete_results.get("succeeded", []):
                if ":" in file_info:
                    file_path = file_info.split(":", 1)[1].strip()
                    file_name = file_path.split("/")[-1] if "/" in file_path else file_path
                    
                    # 使用ORM方式更新
                    result = await db.execute(
                        select(SyncTaskItem).where(
                            (SyncTaskItem.taskId == task_id) &
                            (SyncTaskItem.type == "delete") &
                            (SyncTaskItem.fileName == file_name)
                        )
                    )
                    item = result.scalars().first()
                    if item:
                        item.status = "completed"
                        deleted_success += 1
            
            # 失败删除的文件
            for file_info in delete_results.get("failed", []):
                if ":" in file_info:
                    file_path = file_info.split(":", 1)[1].strip()
                    error_msg = file_info.split(":", 1)[0].strip()
                    file_name = file_path.split("/")[-1] if "/" in file_path else file_path
                    
                    # 使用ORM方式更新
                    result = await db.execute(
                        select(SyncTaskItem).where(
                            (SyncTaskItem.taskId == task_id) &
                            (SyncTaskItem.type == "delete") &
                            (SyncTaskItem.fileName == file_name)
                        )
                    )
                    item = result.scalars().first()
                    if item:
                        item.status = "failed"
                        item.errMsg = error_msg
                        deleted_fail += 1
            
            # 提交所有更改
            await db.commit()
            
            # 移除冗余的手动更新任务状态的代码，直接使用complete_sync_task函数，
            # 它会获取最新的任务项统计数据并更新任务状态
            await complete_sync_task(db, task_id)
            
            # 计算统计数据
            stats = {
                "added_success": added_success,
                "added_fail": added_fail,
                "deleted_success": deleted_success,
                "deleted_fail": deleted_fail,
                "to_add_total": len(comparison_result.to_add),
                "to_delete_total": len(comparison_result.to_delete_from_target),
                "source_list_num": comparison_result.source_list_num,
                "target_list_num": comparison_result.target_list_num,
                "total_items": total_items
            }
            
            elapsed_time = time.time() - start_time
            logger.info(f"同步任务执行完成: ID={task_id}, 耗时={elapsed_time:.2f}秒")
            
            return {
                "success": True,
                "task_id": task_id,
                "stats": stats,
                "elapsed_time": elapsed_time
            }
            
        except Exception as e:
            error_msg = f"同步任务执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # 更新任务状态为失败
            await fail_sync_task(db, task_id, error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "task_id": task_id,
                "elapsed_time": time.time() - start_time
            }

# 创建服务单例
file_sync_service = FileSyncService()
