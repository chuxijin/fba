#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator
from backend.app.mydrive.service.filesystem.time_utils import parse_timestamp


def build_quark_file(
    space: SpaceLocator,
    item: dict[str, Any],
    parent_path: str = '/',
    extra: dict[str, Any] | None = None,
) -> FileObject:
    """
    将夸克原始文件转换为统一文件对象。

    :param space: 文件空间定位信息
    :param item: 夸克原始文件信息
    :param parent_path: 父目录路径
    :param extra: 附加上下文
    :return:
    """
    name = str(item.get('file_name') or '')
    normalized_parent_path = parent_path.rstrip('/') or '/'
    path = f'/{name}' if normalized_parent_path == '/' else f'{normalized_parent_path}/{name}'
    return FileObject(
        space=space,
        file_id=str(item.get('fid') or ''),
        name=name,
        path=path,
        is_directory=bool(item.get('dir', False)),
        size=item.get('size'),
        parent_id=str(item.get('pdir_fid') or ''),
        created_at=parse_timestamp(item.get('created_at')),
        modified_at=parse_timestamp(item.get('updated_at')),
        hash_value=item.get('md5') or item.get('sha1'),
        extra={
            'category': item.get('category'),
            'thumbnail': item.get('thumbnail'),
            'file_type': item.get('file_type'),
            'format_type': item.get('format_type'),
            'obj_category': item.get('obj_category'),
            **(extra or {}),
        },
    )
