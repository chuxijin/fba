#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import json # 导入 json 模块
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.schema.enum import DriveType, RecursionSpeed, SyncMethod
from backend.app.coulddrive.schema.file import (
    BaseFileInfo, BatchRenameParam, CreateSyncTaskItemParam, DiskTargetDefinition, 
    ExclusionRuleDefinition, ListFilesParam, RenameParam, RenameRuleDefinition,
    ShareSourceDefinition
)
from backend.app.coulddrive.service.rule_template_service import ItemFilter, MatchTarget, RenameRule, parse_rename_rules
from backend.app.coulddrive.service.yp_service import get_drive_manager


logger = logging.getLogger(__name__)


class FileOperateService:
    """文件操作服务，包含批量重命名等"""

    def __init__(self):
        self.drive_manager = get_drive_manager()
        # 存储批量重命名进度信息
        self.batch_rename_progress = {}

    async def batch_rename_files_with_progress(
        self,
        x_token: str,
        params: BatchRenameParam,
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        progress_callback=None,
        template_data: Optional[Any] = None,
        stats: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        批量重命名文件或文件夹（支持进度回调）

        :param x_token: 认证令牌
        :param params: 批量重命名参数
        :param task_id: 任务ID
        :param db: 数据库会话
        :param account_key: 账户key
        :param progress_callback: 进度回调函数
        :param template_data: 预获取的模板数据
        :param stats: 统计数据字典
        :return: 批量重命名结果统计
        """
        return await self._batch_rename_files_impl(
            x_token, params, task_id, db, account_key, progress_callback, template_data, stats, **kwargs
        )

    async def batch_rename_files(
        self,
        x_token: str,
        params: BatchRenameParam,
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        批量重命名文件或文件夹

        :param x_token: 认证令牌
        :param params: 批量重命名参数
        :param task_id: 任务ID
        :param db: 数据库会话
        :param account_key: 账户key
        :param stats: 统计数据字典
        :return: 批量重命名结果统计
        """
        return await self._batch_rename_files_impl(
            x_token, params, task_id, db, account_key, None, stats, **kwargs
        )

    async def _batch_rename_files_impl(
        self,
        x_token: str,
        params: BatchRenameParam,
        task_id: Optional[int],
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        progress_callback=None,
        template_data: Optional[Any] = None,
        stats: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        批量重命名文件或文件夹的内部实现

        :param x_token: 认证令牌
        :param params: 批量重命名参数
        :param task_id: 任务ID
        :param db: 数据库会话
        :param account_key: 账户key
        :param progress_callback: 进度回调函数
        :param stats: 统计数据字典
        :return: 批量重命名结果统计
        """
        if stats is None:
            stats = {
                "renamed_success": 0,
                "renamed_failed": 0,
                "errors": [],
                "pending_task_items": [],
            }
        
        # 解析重命名规则
        rename_rules: Optional[List[RenameRule]] = None
        has_rules_to_apply = False

        if params.template_id and template_data:
            # 使用预获取的模板数据
            try:
                rules_data = template_data
                # 如果 rule_config 是字符串，需要解析 JSON
                if isinstance(rules_data, str):
                    try:
                        rules_data = json.loads(rules_data)
                    except json.JSONDecodeError as e:
                        error_msg = f"[任务{task_id or 'unknown'}] 模板 {params.template_id} 的规则配置 JSON 解析失败: {e}"
                        logger.error(error_msg, exc_info=True)
                        stats["errors"].append(error_msg)
                        return stats

                template_rules_def = [RenameRuleDefinition(**r) for r in rules_data.get("rules", [])]
                parsed_rules = parse_rename_rules(template_rules_def)
                if parsed_rules:
                    rename_rules = parsed_rules
                    has_rules_to_apply = True
            except Exception as e:
                error_msg = f"[任务{task_id or 'unknown'}] 从模板 {params.template_id} 解析重命名规则失败: {e}"
                logger.error(error_msg, exc_info=True)
                stats["errors"].append(error_msg)
                return stats
        elif params.rename_rules:
            parsed_rules = parse_rename_rules(params.rename_rules)
            if parsed_rules:
                rename_rules = parsed_rules
                has_rules_to_apply = True

        if not has_rules_to_apply:
            if params.template_id is None:
                logger.info(f"[任务{task_id or 'unknown'}] 未选择重命名模板或未提供重命名规则，将不进行重命名操作。")
                return stats
            else:
                # params.template_id 被提供，但未找到有效的活动规则，或者 rule_config 为空
                logger.info(f"[任务{task_id or 'unknown'}] 已选择重命名模板 {params.template_id}，但未找到有效的重命名规则，将不进行重命名操作。")
                return stats

        # 验证账户信息
        if not account_key:
            error_msg = f"[任务{task_id or 'unknown'}] 缺少账户信息"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return stats
        
        logger.info(f"[任务{task_id or 'unknown'}] 使用账户ID: {account_key}")

        # 第一步：收集所有需要处理的文件/文件夹
        all_items_to_process = []
        
        # 发送开始收集进度
        if progress_callback:
            await progress_callback({
                'type': 'progress',
                'message': '开始收集文件列表...',
                'current_folder': '',
                'current_file': '',
                'completed': 0,
                'total': len(params.file_infos)
            })
        
        for file_info_item in params.file_infos:
            file_id = file_info_item.file_id
            file_path = file_info_item.file_path
            is_folder = file_info_item.is_folder
            
            # 根据 recursive 参数决定处理方式
            if params.recursive:
                # 遍历模式：如果是文件夹，展开其内部内容
                if is_folder:
                    try:
                        # 发送遍历文件夹进度
                        if progress_callback:
                            await progress_callback({
                                'type': 'progress',
                                'message': f'正在遍历文件夹: {file_path}',
                                'current_folder': file_path,
                                'current_file': '',
                                'completed': len(all_items_to_process),
                                'total': len(params.file_infos)
                            })
                        
                        folder_items = await self._recursively_list_all_items(
                            x_token, params.drive_type, file_id, file_path, db, account_key, True
                        )
                        all_items_to_process.extend(folder_items)
                    except Exception as e:
                        error_msg = f"[任务{task_id or 'unknown'}] 列出目录 {file_path} 失败: {e}"
                        logger.error(error_msg, exc_info=True)
                        stats["errors"].append(error_msg)
                else:
                    # 直接文件，添加到处理列表
                    file_info_dict = {
                        "file_id": file_info_item.file_id,
                        "file_path": file_info_item.file_path,
                        "file_name": file_info_item.file_name,
                        "is_folder": file_info_item.is_folder,
                        "parent_id": file_info_item.parent_id,
                        "file_size": getattr(file_info_item, 'file_size', 0)
                    }
                    all_items_to_process.append(file_info_dict)
            else:
                # 非遍历模式：只处理选中的项目本身
                file_info_dict = {
                    "file_id": file_info_item.file_id,
                    "file_path": file_info_item.file_path,
                    "file_name": file_info_item.file_name,
                    "is_folder": file_info_item.is_folder,
                    "parent_id": file_info_item.parent_id,
                    "file_size": getattr(file_info_item, 'file_size', 0)
                }
                all_items_to_process.append(file_info_dict)
        
        # 第二步：根据 target_scope 过滤出符合条件的文件
        filtered_items = []
        for item in all_items_to_process:
            is_folder = item.get("is_folder", False)
            
            # 根据 target_scope 过滤
            if params.target_scope == "file" and is_folder:
                continue  # 跳过文件夹
            if params.target_scope == "folder" and not is_folder:
                continue  # 跳过文件
            # target_scope == "all" 时不过滤
            
            filtered_items.append(item)
        
        # 发送过滤完成进度
        if progress_callback:
            await progress_callback({
                'type': 'progress',
                'message': f'遍历完成，找到 {len(filtered_items)} 个符合条件的项目',
                'current_folder': '',
                'current_file': '',
                'completed': len(filtered_items),
                'total': len(filtered_items)
            })
        
        # 第三步：预先筛选出需要重命名的文件
        items_to_rename = []
        items_to_skip = []
        
        for item in filtered_items:
            # 检查是否需要重命名
            original_name = item.get("file_name", "")
            original_path = item.get("file_path", "")
            file_id = item.get("file_id", "")
            is_folder = item.get("is_folder", False)

            new_name = original_name
            new_path = original_path

            temp_file_info = BaseFileInfo(
                file_id=file_id,
                file_name=original_name,
                file_path=original_path,
                is_folder=is_folder
            )

            # 应用重命名规则
            for rule in rename_rules:
                generated_new_value = rule.generate_new_path(temp_file_info)
                if generated_new_value:
                    if rule.target_scope == MatchTarget.NAME:
                        new_name = generated_new_value
                        parent_path = original_path.rsplit('/', 1)[0] if '/' in original_path else ''
                        new_path = f"{parent_path}/{new_name}"
                    elif rule.target_scope == MatchTarget.PATH:
                        new_path = generated_new_value
                        new_name = new_path.rsplit('/', 1)[-1]
                    break

            # 判断是否需要重命名
            if new_name != original_name or new_path != original_path:
                items_to_rename.append(item)
            else:
                items_to_skip.append(item)
        
        # 发送筛选完成进度
        if progress_callback:
            await progress_callback({
                'type': 'progress',
                'message': f'筛选完成，找到 {len(items_to_rename)} 个需要重命名的文件',
                'current_folder': '',
                'current_file': '',
                'completed': len(items_to_rename),
                'total': len(items_to_rename)
            })
        
        # 第四步：创建重命名任务
        tasks = []
        file_infos = []  # 保存文件信息用于进度显示
        
        for item in items_to_rename:
            tasks.append(self._apply_and_execute_rename(
                x_token, params.drive_type, item, rename_rules, task_id, db, account_key, stats
            ))
            file_infos.append(item)  # 保存文件信息
        
        # 预先记录跳过的文件
        for item in items_to_skip:
            stats["pending_task_items"].append(
                self._record_task_item(
                    task_id,
                    "无需重命名",
                    item.get("file_path", ""),
                    item.get("file_path", ""),
                    item.get("file_name", ""),
                    item.get("file_size", 0),
                    "skipped",
                    "文件名无需修改",
                )
            )
        
        # 发送开始重命名进度
        if progress_callback:
            await progress_callback({
                'type': 'progress',
                'message': f'开始重命名 {len(tasks)} 个文件...',
                'current_folder': '',
                'current_file': '',
                'completed': 0,
                'total': len(tasks)
            })
        
        # 控制并发数量，避免过快处理
        semaphore = asyncio.Semaphore(4)  # 最多同时处理4个重命名任务
        
        async def limited_task_with_progress(task, index):
            async with semaphore:
                # 获取当前处理的文件信息
                current_file_info = file_infos[index] if index < len(file_infos) else {}
                current_file_name = current_file_info.get('file_name', '')
                current_file_path = current_file_info.get('file_path', '')
                
                # 发送当前重命名项目进度
                if progress_callback:
                    await progress_callback({
                        'type': 'progress',
                        'message': f'正在重命名第 {index + 1}/{len(tasks)} 个文件...',
                        'current_folder': current_file_path.rsplit('/', 1)[0] if current_file_path else '',
                        'current_file': current_file_name,
                        'completed': index,
                        'total': len(tasks)
                    })
                
                await task
                # 每个重命名操作之间间隔3-4秒
                await asyncio.sleep(3.5)
        
        # 创建带进度的任务列表
        progress_tasks = [limited_task_with_progress(task, i) for i, task in enumerate(tasks)]
        await asyncio.gather(*progress_tasks)

        return stats
    
    async def _recursively_list_all_items(
        self,
        x_token: str,
        drive_type: DriveType,
        parent_id: Optional[str],
        parent_path: Optional[str],
        db: Optional[AsyncSession],
        account_key: Optional[str],
        recursive: bool = True
    ) -> List[Dict[str, Any]]:
        """递归列出目录下的所有文件和文件夹"""
        all_items = []
        # 实例化 ListFilesParam，注意要指定 file_path 或 file_id
        list_params = ListFilesParam(
            drive_type=drive_type,
            file_id=parent_id, 
            file_path=parent_path,
            page=1,
            size=1000 # 假设一次性获取足够多的文件，实际可能需要分页或迭代
        )
        try:
            # 调用 drive_manager 获取文件列表
            file_list_result = await self.drive_manager.get_disk_list(
                x_token, list_params, db=db, drive_account_id=account_key
            )
            # 处理不同的返回格式
            if hasattr(file_list_result, 'data'):
                file_list = file_list_result.data
            else:
                # 如果直接返回列表
                file_list = file_list_result

            for item in file_list:
                all_items.append(item.model_dump()) # 将 BaseFileInfo 转换为字典
                if item.is_folder and recursive:
                    # 每层遍历之间停2-3秒
                    await asyncio.sleep(2.5)
                    # 只有在 recursive=True 时才递归处理子文件夹
                    sub_folder_items = await self._recursively_list_all_items(
                        x_token, drive_type, item.file_id, item.file_path, db, account_key, recursive
                    )
                    all_items.extend(sub_folder_items)
        except Exception as e:
            logger.error(f"递归列出目录 {parent_path or parent_id} 失败: {e}", exc_info=True)
            # 这里可以选择重新抛出异常或记录并继续
            raise

        return all_items

    async def _apply_and_execute_rename(
        self,
        x_token: str,
        drive_type: DriveType,
        file_info: Dict[str, Any],
        rename_rules: List[RenameRule],
        task_id: Optional[int],
        db: Optional[AsyncSession],
        account_key: Optional[str],
        stats: Dict[str, Any]
    ) -> None:
        """应用重命名规则并执行重命名操作"""
        original_name = file_info.get("file_name", "")
        original_path = file_info.get("file_path", "")
        file_id = file_info.get("file_id", "")
        is_folder = file_info.get("is_folder", False)

        new_name = original_name
        new_path = original_path

        temp_file_info = BaseFileInfo(
            file_id=file_id,
            file_name=original_name,
            file_path=original_path,
            is_folder=is_folder
        )

        for rule in rename_rules:
            generated_new_value = rule.generate_new_path(temp_file_info)
            if generated_new_value:
                if rule.target_scope == MatchTarget.NAME:
                    new_name = generated_new_value
                    # 如果只修改了文件名，需要重新构建完整的 new_path
                    parent_path = original_path.rsplit('/', 1)[0] if '/' in original_path else ''
                    new_path = f"{parent_path}/{new_name}"
                elif rule.target_scope == MatchTarget.PATH:
                    new_path = generated_new_value
                    # 如果修改了路径，需要从新路径中提取新的文件名
                    new_name = new_path.rsplit('/', 1)[-1]
                break # 假设只应用第一个匹配的规则

        # 现在传入的都是确定需要重命名的文件，直接执行重命名
        rename_params = RenameParam(
            drive_type=drive_type,
            file_id=file_id,
            file_path=original_path,
            new_name=new_name,
            new_path=new_path,
            file_name=original_name,
            parent_id=file_info.get("parent_id")
        )
        
        try:
            success = await self.drive_manager.rename_files(x_token, rename_params, db=db, account_key=account_key)
            if success:
                stats["renamed_success"] += 1
                stats["pending_task_items"].append(
                    self._record_task_item(
                        task_id,
                        "重命名成功",
                        original_path,
                        new_path,
                        original_name,
                        file_info.get("file_size", 0),
                        "success",
                        None,
                    )
                )
            else:
                stats["renamed_failed"] += 1
                stats["errors"].append(f"重命名 {original_name} 为 {new_name} 失败")
                stats["pending_task_items"].append(
                    self._record_task_item(
                        task_id,
                        "重命名失败",
                        original_path,
                        new_path,
                        original_name,
                        file_info.get("file_size", 0),
                        "failed",
                        f"重命名失败",
                    )
                )
        except Exception as e:
            stats["renamed_failed"] += 1
            error_msg = f"执行重命名异常: {original_name} -> {new_name}, 错误: {e}"
            logger.error(error_msg, exc_info=True)
            stats["errors"].append(error_msg)
            stats["pending_task_items"].append(
                self._record_task_item(
                    task_id,
                    "重命名异常",
                    original_path,
                    new_path,
                    original_name,
                    file_info.get("file_size", 0),
                    "failed",
                    str(e),
                )
            )
    
    def _record_task_item(
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
        记录同步任务项

        :param task_id: 同步任务ID
        :param operation_type: 操作类型
        :param src_path: 源路径
        :param dst_path: 目标路径
        :param file_name: 文件名称
        :param file_size: 文件大小
        :param status: 状态
        :param err_msg: 错误信息
        :return: 创建同步任务项参数
        """
        return CreateSyncTaskItemParam(
            task_id=task_id,
            operation_type=operation_type,
            src_path=src_path,
            dst_path=dst_path,
            file_name=file_name,
            file_size=file_size,
            status=status,
            err_msg=err_msg,
        )

    async def progress_stream_generator(self, task_id: str):
        """生成SSE进度流"""
        try:
            while True:
                # 检查进度信息
                if task_id in self.batch_rename_progress:
                    progress_data = self.batch_rename_progress[task_id]
                    
                    # 发送进度数据
                    yield f"data: {json.dumps(progress_data, ensure_ascii=False)}\n\n"
                    
                    # 如果任务完成，发送完成消息并退出
                    if progress_data.get('type') == 'complete':
                        # 清理进度数据
                        self.batch_rename_progress.pop(task_id, None)
                        break
                    elif progress_data.get('type') == 'error':
                        # 清理进度数据
                        self.batch_rename_progress.pop(task_id, None)
                        break
                else:
                    # 发送心跳
                    yield f"data: {json.dumps({'type': 'heartbeat', 'message': '连接正常'}, ensure_ascii=False)}\n\n"
                
                # 等待1秒
                await asyncio.sleep(1)
                
        except Exception as e:
            # 发送错误信息
            error_data = {
                'type': 'error',
                'message': f'连接错误: {str(e)}'
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    def update_progress(self, task_id: str, progress_data: Dict[str, Any]):
        """更新进度信息"""
        self.batch_rename_progress[task_id] = progress_data

    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取进度信息"""
        return self.batch_rename_progress.get(task_id)
