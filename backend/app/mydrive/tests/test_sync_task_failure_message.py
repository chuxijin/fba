#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.task.tasks.mydrive.tasks import _build_sync_failure_message


def test_sync_failure_message_includes_config_name() -> None:
    """同步失败信息应包含同步配置名称。"""
    message = _build_sync_failure_message({
        'task_id': 3669,
        'config_name': '27张薇公专',
        'error': '无法解析百度分享上下文',
    })

    assert message == 'MyDrive 同步任务 3669（27张薇公专）执行失败: 无法解析百度分享上下文'


def test_sync_failure_message_without_config_name() -> None:
    """缺少配置名称时同步失败信息应保持原有格式。"""
    message = _build_sync_failure_message({'task_id': 1, 'config_name': None, 'error': '同步配置不存在或已停用'})

    assert message == 'MyDrive 同步任务 1 执行失败: 同步配置不存在或已停用'


def test_sync_failure_message_falls_back_to_unknown_error() -> None:
    """缺少错误信息时应回退为未知错误。"""
    message = _build_sync_failure_message({'task_id': 2, 'config_name': ' '})

    assert message == 'MyDrive 同步任务 2 执行失败: 未知错误'
