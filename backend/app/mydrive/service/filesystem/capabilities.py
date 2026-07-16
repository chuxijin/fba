#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import Enum


class FileCapability(str, Enum):
    """文件空间能力。"""

    LIST = 'list'
    GET = 'get'
    TRANSFER_TO_TARGET = 'transfer_to_target'
    MAKE_DIRECTORY = 'make_directory'
    COPY = 'copy'
    MOVE = 'move'
    RENAME = 'rename'
    REMOVE = 'remove'
    CREATE_SHARE = 'create_share'
    MANAGE_SHARES = 'manage_shares'
