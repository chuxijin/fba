#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile

from backend.common.exception.errors import NotFoundError
from backend.core.path_conf import UPLOAD_DIR
from backend.utils.file_ops import upload_file, upload_file_verify
from backend.utils.timezone import timezone


class FileService:
    @staticmethod
    async def upload(file: UploadFile, folder: str | None = None) -> str:
        """
        上传文件

        :param file: 文件对象
        :param folder: 目标文件夹
        :return: 文件名
        """
        upload_file_verify(file)
        return await upload_file(file, folder=folder)

    @staticmethod
    def list(
        page: int,
        size: int,
        base_url: str,
        keyword: str | None = None,
        file_type: str | None = None,
        folder: str | None = None,
    ) -> dict:
        """
        获取文件列表

        :param page: 页码
        :param size: 每页数量
        :param base_url: 基础 URL
        :param keyword: 关键词
        :param file_type: 文件类型
        :param folder: 文件夹名称
        :return: 文件列表
        """
        upload_dir = UPLOAD_DIR

        # 确定当前目录
        if folder:
            # 安全检查：防止路径穿越
            folder = folder.strip('/').replace('\\', '/')
            if '..' in folder:
                raise NotFoundError(msg='非法的文件夹路径')
            current_dir = upload_dir / folder
        else:
            current_dir = upload_dir

        if not current_dir.exists():
            return {
                'items': [],
                'total': 0,
                'page': page,
                'size': size,
                'current_folder': folder or '',
            }

        # 获取所有文件和文件夹
        all_items = []

        for item_path in current_dir.iterdir():
            # 跳过隐藏文件
            if item_path.name.startswith('.'):
                continue

            if item_path.is_dir():
                # 文件夹
                folder_info = {
                    'name': item_path.name,
                    'type': 'folder',
                    'is_folder': True,
                    'created_time': datetime.fromtimestamp(item_path.stat().st_ctime, tz=timezone.tz_info).isoformat(),
                }
                all_items.append(folder_info)

            elif item_path.is_file():
                # 文件
                stat = item_path.stat()
                try:
                    relative_path = item_path.relative_to(upload_dir).as_posix()
                except ValueError:
                    # 如果相对路径计算失败，回退到 safe path
                    continue
                
                file_info = {
                    'name': item_path.name,
                    'url': f'{base_url}/static/upload/{relative_path}',
                    'size': stat.st_size,
                    'created_time': datetime.fromtimestamp(stat.st_ctime, tz=timezone.tz_info).isoformat(),
                    'type': FileService._get_file_type(item_path.name),
                    'is_folder': False,
                }

                # 关键词过滤
                if keyword and keyword.lower() not in item_path.name.lower():
                    continue

                # 文件类型过滤
                if file_type and file_info['type'] != file_type:
                    continue

                all_items.append(file_info)

        # 排序：文件夹在前，然后按创建时间倒序
        all_items.sort(key=lambda x: (not x['is_folder'], x['created_time']), reverse=True)

        # 分页
        total = len(all_items)
        start = (page - 1) * size
        end = start + size
        items = all_items[start:end]

        return {
            'items': items,
            'total': total,
            'page': page,
            'size': size,
            'current_folder': folder or '',
        }

    @staticmethod
    def delete(filename: str) -> None:
        """
        删除文件

        :param filename: 文件名
        """
        upload_dir = UPLOAD_DIR
        file_path = upload_dir / filename

        if not file_path.exists():
            raise NotFoundError(msg='文件不存在')

        # 安全检查：确保文件在上传目录内
        try:
            if not str(file_path.resolve()).startswith(str(upload_dir.resolve())):
                raise NotFoundError(msg='非法的文件路径')
        except Exception:
            raise NotFoundError(msg='非法的文件路径')

        if file_path.is_dir():
            try:
                file_path.rmdir()
            except OSError as exc:
                raise NotFoundError(msg='文件夹不为空或无法删除') from exc
            return

        file_path.unlink()

    @staticmethod
    def create_folder(folder_name: str, parent_folder: str | None = None) -> dict:
        """
        创建文件夹

        :param folder_name: 文件夹名称
        :param parent_folder: 父文件夹路径
        :return: 创建结果
        """
        upload_dir = UPLOAD_DIR

        if not folder_name or folder_name.strip() == '':
            raise NotFoundError(msg='文件夹名称不能为空')

        # 移除危险字符
        folder_name = folder_name.strip().replace('/', '').replace('\\', '').replace('..', '')
        if not folder_name:
            raise NotFoundError(msg='文件夹名称不合法')

        # 确定父目录
        if parent_folder:
            parent_folder = parent_folder.strip('/').replace('\\', '/')
            if '..' in parent_folder:
                raise NotFoundError(msg='非法的文件夹路径')
            parent_dir = upload_dir / parent_folder
        else:
            parent_dir = upload_dir

        # 创建文件夹
        new_folder_path = parent_dir / folder_name

        if new_folder_path.exists():
            raise NotFoundError(msg='文件夹已存在')

        # 安全检查
        try:
            if not str(new_folder_path.resolve()).startswith(str(upload_dir.resolve())):
                raise NotFoundError(msg='非法的文件夹路径')
        except Exception as exc:
            raise NotFoundError(msg='非法的文件夹路径') from exc

        new_folder_path.mkdir(parents=True, exist_ok=False)

        return {
            'name': folder_name,
            'path': str(new_folder_path.relative_to(upload_dir).as_posix()) if parent_folder else folder_name,
        }

    @staticmethod
    def _get_file_type(filename: str) -> str:
        """
        根据文件扩展名判断文件类型

        :param filename: 文件名
        :return: 文件类型
        """
        ext = Path(filename).suffix.lower()

        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.bmp'}
        video_exts = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm'}
        document_exts = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md'}

        if ext in image_exts:
            return 'image'
        elif ext in video_exts:
            return 'video'
        elif ext in document_exts:
            return 'document'
        else:
            return 'other'

file_service = FileService()
