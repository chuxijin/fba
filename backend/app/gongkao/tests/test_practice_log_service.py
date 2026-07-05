#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.gongkao.schema.practice_log import CreatePracticeModuleParam
from backend.app.gongkao.service.practice_log_service import PracticeLogService


def test_build_modules_data_assigns_seq_no_by_order_when_missing() -> None:
    """未传排序号时按列表顺序生成"""
    modules = [
        CreatePracticeModuleParam(module_name='政治理论', total_questions=20, correct_count=8),
        CreatePracticeModuleParam(module_name='常识判断', total_questions=15, correct_count=9),
        CreatePracticeModuleParam(module_name='言语理解与表达', total_questions=30, correct_count=21),
    ]

    modules_data = PracticeLogService._build_modules_data(modules)

    assert [module['seq_no'] for module in modules_data] == [0, 1, 2]


def test_build_modules_data_rewrites_duplicate_seq_no() -> None:
    """重复排序号应自动修正"""
    modules = [
        CreatePracticeModuleParam(module_name='政治理论', total_questions=20, correct_count=8, seq_no=0),
        CreatePracticeModuleParam(module_name='常识判断', total_questions=15, correct_count=9, seq_no=0),
        CreatePracticeModuleParam(module_name='言语理解与表达', total_questions=30, correct_count=21, seq_no=0),
    ]

    modules_data = PracticeLogService._build_modules_data(modules)

    assert [module['seq_no'] for module in modules_data] == [0, 1, 2]


def test_build_modules_data_preserves_unique_seq_no() -> None:
    """唯一排序号应保留"""
    modules = [
        CreatePracticeModuleParam(module_name='政治理论', total_questions=20, correct_count=8, seq_no=10),
        CreatePracticeModuleParam(module_name='常识判断', total_questions=15, correct_count=9, seq_no=11),
    ]

    modules_data = PracticeLogService._build_modules_data(modules)

    assert [module['seq_no'] for module in modules_data] == [10, 11]
