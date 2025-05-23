from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import logging
from datetime import datetime

from .api import QuarkApi
from .errors import QuarkApiError
from .schemas import FileInfo, StorageInfo, CopyTask

class QuarkClient:
    """夸克网盘客户端"""

    def __init__(self, base_url: str):
        self.api = QuarkApi(base_url)
        self.logger = logging.getLogger('QuarkClient')

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """登录"""
        return self.api.login(username, password)

    def list_files(self, path: str, refresh: bool = False, page: int = 1, per_page: int = 0) -> List[FileInfo]:
        """列出目录下的文件"""
        return self.api.list_files(path, refresh, page, per_page)

    def create_directory(self, path: str) -> Dict[str, Any]:
        """创建目录"""
        return self.api.create_directory(path)

    def rename_file(self, path: str, new_name: str) -> Dict[str, Any]:
        """重命名文件"""
        return self.api.rename_file(path, new_name)

    def copy_files(self, src_dir: str, dst_dir: str, names: List[str]) -> Dict[str, Any]:
        """复制文件"""
        return self.api.copy_files(src_dir, dst_dir, names)

    def move_files(self, src_dir: str, dst_dir: str, names: List[str]) -> Dict[str, Any]:
        """移动文件"""
        return self.api.move_files(src_dir, dst_dir, names)

    def delete_files(self, dir_path: str, file_names: List[str]) -> Dict[str, Any]:
        """删除文件"""
        return self.api.delete_files(dir_path, file_names)

    def get_copy_tasks(self, done: bool = False) -> List[CopyTask]:
        """获取复制任务列表"""
        if done:
            return self.api.get_done_copy_tasks()
        return self.api.get_undone_copy_tasks()

    def cancel_copy_task(self, task_id: int) -> Dict[str, Any]:
        """取消复制任务"""
        return self.api.cancel_copy_task(task_id)

    def retry_copy_task(self, task_id: int) -> Dict[str, Any]:
        """重试复制任务"""
        return self.api.retry_copy_task(task_id)

    def delete_copy_task(self, task_id: int) -> Dict[str, Any]:
        """删除复制任务"""
        return self.api.delete_copy_task(task_id)

    def clear_done_copy_tasks(self) -> Dict[str, Any]:
        """清除已完成的复制任务"""
        return self.api.clear_done_copy_tasks()

    def get_storage_info(self, storage_id: int) -> StorageInfo:
        """获取存储信息"""
        return self.api.get_storage_info(storage_id)

    def list_storages(self, page: int = 1, per_page: int = 20) -> List[StorageInfo]:
        """列出存储列表"""
        return self.api.list_storages(page, per_page)

    def create_storage(self, driver: str, mount_path: str, additional_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建存储"""
        return self.api.create_storage(driver, mount_path, additional_params)

    def update_storage(self, storage_id: int, modified_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """更新存储"""
        return self.api.update_storage(storage_id, modified_params)

    def delete_storage(self, storage_id: int) -> Dict[str, Any]:
        """删除存储"""
        return self.api.delete_storage(storage_id) 