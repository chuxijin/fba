#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import StrEnum


class NodeRole(StrEnum):
    """节点 LLM 角色"""

    primary = 'primary'
    mini = 'mini'
    embedding = 'embedding'
