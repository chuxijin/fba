#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文件系统领域模型和协议。"""

from backend.app.mydrive.service.filesystem.capabilities import FileCapability
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType

__all__ = ['FileCapability', 'FileObject', 'SpaceLocator', 'SpaceType']
