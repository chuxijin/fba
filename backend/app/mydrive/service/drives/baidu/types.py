#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import PurePosixPath
from typing import Any

from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator
from backend.app.mydrive.service.filesystem.time_utils import parse_timestamp


def build_baidu_file(space: SpaceLocator, item: dict[str, Any], extra: dict[str, Any] | None = None) -> FileObject:
    """
    将百度原始文件转换为统一文件对象。

    :param space: 文件空间定位信息
    :param item: 百度原始文件信息
    :param extra: 附加上下文
    :return:
    """
    path = str(item.get('path') or '')
    return FileObject(
        space=space,
        file_id=str(item.get('fs_id') or ''),
        name=str(item.get('server_filename') or PurePosixPath(path).name),
        path=path,
        is_directory=bool(item.get('isdir', 0)),
        size=item.get('size'),
        parent_id=str(item.get('parent_path') or PurePosixPath(path).parent),
        created_at=parse_timestamp(item.get('server_ctime')),
        modified_at=parse_timestamp(item.get('server_mtime')),
        hash_value=item.get('md5'),
        extra={'category': item.get('category'), **(extra or {})},
    )
