#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import json
import logging

from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.schema.file import (
    BaseFileInfo,
    BatchRenameParam,
    CreateSyncTaskItemParam,
    ListFilesParam,
    RenameParam,
    RenameRuleDefinition,
)
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService
from backend.app.coulddrive.service.rule_template_service import (
    MatchTarget,
    RenameRule,
    parse_rename_rules,
)
from backend.app.coulddrive.service.utils_service import build_full_path, get_filename, get_parent_path

logger = logging.getLogger(__name__)


class FileOperateService:
    """文件操作服务"""

    def __init__(self):
        self.batch_rename_progress: Dict[str, Dict[str, Any]] = {}

    # ========== 公开方法 ==========

    async def batch_rename_files(
        self,
        x_token: str,
        params: BatchRenameParam,
        task_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
        account_key: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        template_data: Optional[Any] = None,
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
        :param progress_callback: 进度回调函数
        :param template_data: 预获取的模板数据
        :param stats: 统计数据字典
        :return: 批量重命名结果统计
        """
        # 初始化统计
        if stats is None:
            stats = self._init_stats()

        task_label = f"[任务{task_id or 'unknown'}]"

        # 解析重命名规则
        rename_rules = self._parse_rules(params, template_data, task_label, stats)
        if not rename_rules:
            return stats

        # 验证账户
        if not account_key:
            self._log_error(f"{task_label} 缺少账户信息", stats)
            return stats

        logger.info(f"{task_label} 使用账户ID: {account_key}")

        # 创建统一的服务实例，在整个批量重命名过程中复用
        service = CouldDriveService(auth_data=x_token, drive_type=params.drive_type)

        # 收集文件
        await self._send_progress(progress_callback, "开始收集文件列表...", 0, len(params.file_infos))
        all_items = await self._collect_items(service, params, task_label, stats, progress_callback)

        # 过滤文件
        filtered_items = self._filter_by_scope(all_items, params.target_scope)
        await self._send_progress(progress_callback, f"遍历完成，找到 {len(filtered_items)} 个符合条件的项目", len(filtered_items), len(filtered_items))

        # 分类需要重命名的文件
        items_to_rename, items_to_skip = self._classify_items(filtered_items, rename_rules)
        await self._send_progress(progress_callback, f"筛选完成，{len(items_to_rename)} 个需要重命名", len(items_to_rename), len(items_to_rename))

        # 记录跳过的文件
        for item in items_to_skip:
            stats["pending_task_items"].append(self._create_task_item(
                task_id, "无需重命名", item["file_path"], item["file_path"],
                item["file_name"], item.get("file_size", 0), "skipped", "文件名无需修改"
            ))

        # 执行重命名
        await self._execute_renames(
            service, items_to_rename, rename_rules,
            task_id, db, account_key, stats, progress_callback
        )

        return stats

    # 向后兼容别名
    async def batch_rename_files_with_progress(self, *args, **kwargs) -> Dict[str, Any]:
        """批量重命名（带进度回调）- 向后兼容"""
        return await self.batch_rename_files(*args, **kwargs)

    # ========== 进度管理 ==========

    def update_progress(self, task_id: str, progress_data: Dict[str, Any]):
        """更新进度信息"""
        self.batch_rename_progress[task_id] = progress_data

    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取进度信息"""
        return self.batch_rename_progress.get(task_id)

    async def progress_stream_generator(self, task_id: str):
        """生成 SSE 进度流"""
        try:
            while True:
                if task_id in self.batch_rename_progress:
                    progress_data = self.batch_rename_progress[task_id]
                    yield f"data: {json.dumps(progress_data, ensure_ascii=False)}\n\n"

                    if progress_data.get("type") in ("complete", "error"):
                        self.batch_rename_progress.pop(task_id, None)
                        break
                else:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'message': '连接正常'}, ensure_ascii=False)}\n\n"

                await asyncio.sleep(1)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'连接错误: {e}'}, ensure_ascii=False)}\n\n"

    # ========== 私有方法：规则解析 ==========

    def _parse_rules(
        self,
        params: BatchRenameParam,
        template_data: Optional[Any],
        task_label: str,
        stats: Dict[str, Any]
    ) -> Optional[List[RenameRule]]:
        """解析重命名规则"""
        # 从模板数据解析
        if params.template_id and template_data:
            try:
                rules_data = template_data
                if isinstance(rules_data, str):
                    rules_data = json.loads(rules_data)

                rule_defs = [RenameRuleDefinition(**r) for r in rules_data.get("rules", [])]
                rules = parse_rename_rules(rule_defs)
                if rules:
                    return rules
            except json.JSONDecodeError as e:
                self._log_error(f"{task_label} 模板 {params.template_id} JSON 解析失败: {e}", stats)
                return None
            except Exception as e:
                self._log_error(f"{task_label} 解析模板 {params.template_id} 失败: {e}", stats)
                return None

        # 从参数解析
        if params.rename_rules:
            rules = parse_rename_rules(params.rename_rules)
            if rules:
                return rules

        # 无规则
        msg = f"{task_label} 未找到有效的重命名规则"
        if params.template_id:
            msg = f"{task_label} 模板 {params.template_id} 无有效规则"
        logger.info(msg)
        return None

    # ========== 私有方法：文件收集 ==========

    async def _collect_items(
        self,
        service: CouldDriveService,
        params: BatchRenameParam,
        task_label: str,
        stats: Dict[str, Any],
        progress_callback: Optional[Callable]
    ) -> List[Dict[str, Any]]:
        """收集所有需要处理的文件"""
        all_items = []

        for file_info in params.file_infos:
            item_dict = self._to_dict(file_info)

            if params.recursive and file_info.is_folder:
                await self._send_progress(
                    progress_callback,
                    f"正在遍历: {file_info.file_path}",
                    len(all_items),
                    len(params.file_infos),
                    current_folder=file_info.file_path
                )
                try:
                    folder_items = await self._list_recursive(
                        service, file_info.file_id, file_info.file_path
                    )
                    all_items.extend(folder_items)
                except Exception as e:
                    self._log_error(f"{task_label} 列出目录 {file_info.file_path} 失败: {e}", stats)
            else:
                all_items.append(item_dict)

        return all_items

    async def _list_recursive(
        self,
        service: CouldDriveService,
        parent_id: str,
        parent_path: str
    ) -> List[Dict[str, Any]]:
        """递归列出目录下所有文件"""
        all_items = []

        list_params = ListFilesParam(
            drive_type=service._client.drive_type if hasattr(service._client, 'drive_type') else DriveType.QUARK_DRIVE,
            file_id=parent_id,
            file_path=parent_path,
            page=1,
            size=1000
        )

        try:
            file_list = await service.get_disk_list(params=list_params)

            for item in file_list:
                all_items.append(item.model_dump())

                if item.is_folder:
                    await asyncio.sleep(2.5)
                    sub_items = await self._list_recursive(
                        service, item.file_id, item.file_path
                    )
                    all_items.extend(sub_items)

        except Exception as e:
            logger.error(f"递归列出 {parent_path} 失败: {e}", exc_info=True)
            raise

        return all_items

    # ========== 私有方法：文件过滤与分类 ==========

    def _filter_by_scope(self, items: List[Dict], target_scope: str) -> List[Dict]:
        """根据目标范围过滤文件"""
        if target_scope == "all":
            return items

        return [
            item for item in items
            if (target_scope == "file" and not item.get("is_folder", False)) or
               (target_scope == "folder" and item.get("is_folder", False))
        ]

    def _classify_items(
        self,
        items: List[Dict],
        rules: List[RenameRule]
    ) -> tuple[List[Dict], List[Dict]]:
        """分类需要重命名和跳过的文件"""
        to_rename = []
        to_skip = []

        for item in items:
            new_name, new_path = self._apply_rules(item, rules)

            if new_name != item["file_name"] or new_path != item["file_path"]:
                to_rename.append(item)
            else:
                to_skip.append(item)

        return to_rename, to_skip

    def _apply_rules(self, item: Dict, rules: List[RenameRule]) -> tuple[str, str]:
        """应用重命名规则，返回新名称和新路径"""
        original_name = item["file_name"]
        original_path = item["file_path"]

        temp_info = BaseFileInfo(
            file_id=item["file_id"],
            file_name=original_name,
            file_path=original_path,
            is_folder=item.get("is_folder", False)
        )

        for rule in rules:
            new_value = rule.generate_new_path(temp_info)
            if new_value:
                if rule.target_scope == MatchTarget.NAME:
                    parent = get_parent_path(original_path)
                    return new_value, build_full_path(parent, new_value)
                elif rule.target_scope == MatchTarget.PATH:
                    return get_filename(new_value), new_value
                break

        return original_name, original_path

    # ========== 私有方法：执行重命名 ==========

    async def _execute_renames(
        self,
        service: CouldDriveService,
        items: List[Dict],
        rules: List[RenameRule],
        task_id: Optional[int],
        db: Optional[AsyncSession],
        account_key: Optional[str],
        stats: Dict[str, Any],
        progress_callback: Optional[Callable]
    ):
        """执行重命名操作"""
        if not items:
            return

        await self._send_progress(progress_callback, f"开始重命名 {len(items)} 个文件...", 0, len(items))

        semaphore = asyncio.Semaphore(4)

        async def rename_with_limit(item: Dict, index: int):
            async with semaphore:
                await self._send_progress(
                    progress_callback,
                    f"正在重命名 {index + 1}/{len(items)}",
                    index,
                    len(items),
                    current_file=item["file_name"]
                )

                await self._do_rename(service, item, rules, task_id, db, account_key, stats)
                await asyncio.sleep(3.5)

        tasks = [rename_with_limit(item, i) for i, item in enumerate(items)]
        await asyncio.gather(*tasks)

    async def _do_rename(
        self,
        service: CouldDriveService,
        item: Dict,
        rules: List[RenameRule],
        task_id: Optional[int],
        db: Optional[AsyncSession],
        account_key: Optional[str],
        stats: Dict[str, Any]
    ):
        """执行单个重命名"""
        original_name = item["file_name"]
        original_path = item["file_path"]
        new_name, new_path = self._apply_rules(item, rules)

        rename_params = RenameParam(
            drive_type=service._client.drive_type if hasattr(service._client, 'drive_type') else DriveType.QUARK_DRIVE,
            file_id=item["file_id"],
            file_path=original_path,
            new_name=new_name,
            new_path=new_path,
            file_name=original_name,
            parent_id=item.get("parent_id")
        )

        try:
            result = await service.rename(params=rename_params)

            if result:
                stats["renamed_success"] += 1
                status, err_msg = "success", None
            else:
                stats["renamed_failed"] += 1
                stats["errors"].append(f"重命名 {original_name} 为 {new_name} 失败")
                status, err_msg = "failed", "重命名失败"

        except Exception as e:
            stats["renamed_failed"] += 1
            err_msg = f"重命名异常: {original_name} -> {new_name}: {e}"
            logger.error(err_msg, exc_info=True)
            stats["errors"].append(err_msg)
            status = "failed"

        stats["pending_task_items"].append(self._create_task_item(
            task_id, f"重命名{'成功' if status == 'success' else '失败'}",
            original_path, new_path, original_name, item.get("file_size", 0), status, err_msg
        ))

    # ========== 工具方法 ==========

    @staticmethod
    def _init_stats() -> Dict[str, Any]:
        """初始化统计字典"""
        return {
            "renamed_success": 0,
            "renamed_failed": 0,
            "errors": [],
            "pending_task_items": [],
        }

    @staticmethod
    def _to_dict(file_info) -> Dict[str, Any]:
        """将文件信息转为字典"""
        return {
            "file_id": file_info.file_id,
            "file_path": file_info.file_path,
            "file_name": file_info.file_name,
            "is_folder": file_info.is_folder,
            "parent_id": file_info.parent_id,
            "file_size": getattr(file_info, "file_size", 0)
        }

    @staticmethod
    def _create_task_item(
        task_id: int,
        operation_type: str,
        src_path: str,
        dst_path: str,
        file_name: str,
        file_size: int,
        status: str,
        err_msg: Optional[str]
    ) -> CreateSyncTaskItemParam:
        """创建任务项"""
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

    @staticmethod
    def _log_error(msg: str, stats: Dict[str, Any]):
        """记录错误"""
        logger.error(msg)
        stats["errors"].append(msg)

    @staticmethod
    async def _send_progress(
        callback: Optional[Callable],
        message: str,
        completed: int,
        total: int,
        current_folder: str = "",
        current_file: str = ""
    ):
        """发送进度回调"""
        if callback:
            await callback({
                "type": "progress",
                "message": message,
                "current_folder": current_folder,
                "current_file": current_file,
                "completed": completed,
                "total": total
            })
