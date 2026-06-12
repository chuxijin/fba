#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path

import yaml

from backend.common.exception import errors
from backend.plugin.agents.service.common.orchestrator import NodeContext


async def load_profile(ctx: NodeContext) -> None:
    """加载命题规则画像"""
    state = ctx.state
    if getattr(state, 'profile', None):
        return

    base_dir = Path(__file__).resolve().parents[1]
    profile_path = base_dir / 'profiles' / f'{state.exam}_{state.subject}_{state.section}_base.yaml'
    if not profile_path.exists():
        raise errors.NotFoundError(msg=f'命题规则画像不存在: {profile_path.name}')

    try:
        data = yaml.safe_load(profile_path.read_text(encoding='utf-8'))
    except yaml.YAMLError as e:
        raise errors.ServerError(msg=f'命题规则画像解析失败: {e!s}') from e

    if not isinstance(data, dict):
        raise errors.ServerError(msg='命题规则画像根节点必须是对象')
    state.profile = data

