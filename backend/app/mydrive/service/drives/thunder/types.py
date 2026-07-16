#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator


def build_thunder_file(space: SpaceLocator, item: dict[str, Any], parent_path: str = '/') -> FileObject:
    """
    将迅雷原始文件转换为统一文件对象。

    :param space: 文件空间定位信息
    :param item: 迅雷原始文件信息
    :param parent_path: 父目录路径
    :return:
    """
    name = str(item.get('name') or '')
    normalized_parent_path = parent_path.rstrip('/') or '/'
    path = f'/{name}' if normalized_parent_path == '/' else f'{normalized_parent_path}/{name}'
    return FileObject(
        space=space,
        file_id=str(item.get('id') or ''),
        name=name,
        path=path,
        is_directory=item.get('kind') == 'drive#folder',
        size=_to_int(item.get('size')),
        parent_id=str(item.get('parent_id') or ''),
        created_at=_parse_datetime(item.get('created_time')),
        modified_at=_parse_datetime(item.get('modified_time')),
        hash_value=item.get('hash'),
        extra={'thumbnail': item.get('thumbnail_link'), 'icon': item.get('icon_link')},
    )


def _to_int(value: Any) -> int | None:
    """
    转换文件大小。

    :param value: 原始文件大小
    :return:
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    """
    解析迅雷 ISO 时间。

    :param value: 原始时间
    :return:
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
