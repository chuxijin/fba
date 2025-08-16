#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, Any
import json
import os

if TYPE_CHECKING:
    from backend.app.social.model.account import SocialAccount
    from backend.app.social.model.work import SocialWork


class WorkMetrics(TypedDict, total=False):
    """作品指标"""

    view_count: int
    like_count: int
    favorite_count: int
    comment_count: int


async def fetch_metrics_for_work(*, account: 'SocialAccount', work: 'SocialWork') -> WorkMetrics | None:
    """预留：拉取作品初始数据快照

    :param account: 账号对象
    :param work: 作品对象
    :return:
    """
    # 优先使用 Coze 工作流（需安装 cozepy，并配置环境变量）
    # 硬编码默认（可被环境变量覆盖）
    token = os.getenv('COZE_API_TOKEN', 'pat_BlIZrZATpxzAURJb76EGKbBUZeiVUpANMJU1e2i7czeuGhlYMkyOh3Wt4pxmxVSW')
    workflow_id = os.getenv('COZE_WORKFLOW_ID', '7538417342105288750')
    space_id = os.getenv('COZE_SPACE_ID', '7456235812326670363')  # 共组/空间 OID（当前 SDK 不强制使用，保留以便扩展）
    base_url = os.getenv('COZE_API_BASE', 'https://api.coze.cn')

    if not token or not workflow_id:
        return None

    try:
        from cozepy import Coze, TokenAuth
        coze = Coze(auth=TokenAuth(token=token), base_url=base_url)
        # 作品地址作为输入参数（具体 key 视工作流而定）
        # 常见写法：inputs={'url': work.work_url}
        workflow = coze.workflows.runs.create(workflow_id=workflow_id, inputs={'url': work.work_url})  # type: ignore[arg-type]
        data: Any = getattr(workflow, 'data', None)

        # data 可能为字符串或字典
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                pass

        if isinstance(data, dict):
            # 只会有一个 output 不为空，取第一个非空 output
            output_val = None
            for key, val in data.items():
                if key.startswith('output') and val:
                    output_val = val
                    break
            # output 可能仍是字符串 JSON
            if isinstance(output_val, str):
                try:
                    output_val = json.loads(output_val)
                except Exception:
                    pass

            # 期望是列表[{}]或字典
            payload = None
            if isinstance(output_val, list) and output_val:
                payload = output_val[0]
            elif isinstance(output_val, dict):
                payload = output_val

            if isinstance(payload, dict):
                def to_int(v: Any) -> int:
                    # 有些字段可能是字符串或 'false'
                    try:
                        if isinstance(v, bool):
                            return int(v)
                        if v in ('false', 'False'):
                            return 0
                        return int(v)
                    except Exception:
                        return 0

                return WorkMetrics(
                    view_count=to_int(payload.get('view_count', 0)),
                    like_count=to_int(payload.get('like_count', 0)),
                    favorite_count=to_int(payload.get('favorite_count', 0)),
                    comment_count=to_int(payload.get('comment_count', 0)),
                )

    except Exception:
        # 任意异常直接回退为 None，由调用方写入 0 值
        return None

    return None


