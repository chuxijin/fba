#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.app.study_plan.model.item import StudyPlanItem


class CompletionCheckResult:
    """完成判定结果"""

    def __init__(self, ok: bool, reason: str | None = None) -> None:
        """
        构造判定结果

        :param ok: 是否通过完成判定
        :param reason: 未通过时的原因
        :return:
        """
        self.ok = ok
        self.reason = reason

    @classmethod
    def pass_(cls) -> 'CompletionCheckResult':
        """通过"""
        return cls(True)

    @classmethod
    def fail(cls, reason: str) -> 'CompletionCheckResult':
        """
        不通过

        :param reason: 失败原因
        :return:
        """
        return cls(False, reason)


def _check_review(item: StudyPlanItem, payload: dict[str, Any]) -> CompletionCheckResult:
    """
    学习类完成判定：必须显式确认已读

    :param item: 计划项
    :param payload: 完成提交参数
    :return:
    """
    if payload.get('read_acknowledged') is True:
        return CompletionCheckResult.pass_()
    return CompletionCheckResult.fail('请确认已读后再提交')


def _check_practice(item: StudyPlanItem, payload: dict[str, Any]) -> CompletionCheckResult:
    """
    刷题类完成判定：题目全做完且达到设定正确率

    :param item: 计划项
    :param payload: 完成提交参数
    :return:
    """
    correct_count = payload.get('correct_count')
    total_count = payload.get('total_count')

    if total_count is None or correct_count is None:
        return CompletionCheckResult.fail('刷题完成需要提交 correct_count 和 total_count')

    extra = item.extra or {}
    expected_total = extra.get('question_count') or len(extra.get('question_ids') or [])

    if expected_total and total_count < expected_total:
        return CompletionCheckResult.fail(
            f'未完成全部题目（{total_count}/{expected_total}）',
        )

    if total_count <= 0:
        return CompletionCheckResult.fail('题目总数无效')

    required_accuracy = float(extra.get('required_accuracy', 0.6))
    actual_accuracy = correct_count / total_count
    if actual_accuracy < required_accuracy:
        return CompletionCheckResult.fail(
            f'正确率 {actual_accuracy:.0%} 未达到要求 {required_accuracy:.0%}',
        )

    return CompletionCheckResult.pass_()


def _check_wrong_review(item: StudyPlanItem, payload: dict[str, Any]) -> CompletionCheckResult:
    """
    错题复盘类完成判定：所有动态错题都填了 reasons + summary

    :param item: 计划项
    :param payload: 完成提交参数
    :return:
    """
    extra = payload.get('extra_data') or {}
    reviewed_ids = extra.get('reviewed_question_ids') or []
    expected_ids = extra.get('expected_question_ids') or []

    if not expected_ids:
        return CompletionCheckResult.fail('错题列表缺失，请重新启动该模块')

    missing = [qid for qid in expected_ids if qid not in reviewed_ids]
    if missing:
        return CompletionCheckResult.fail(
            f'还有 {len(missing)} 道错题未填写 reasons 和 summary',
        )

    return CompletionCheckResult.pass_()


def _check_ability(item: StudyPlanItem, payload: dict[str, Any]) -> CompletionCheckResult:
    """
    能力提升类完成判定：配置题数或正确率时按训练结果校验

    :param item: 计划项
    :param payload: 完成提交参数
    :return:
    """
    extra = item.extra or {}
    expected_total = extra.get('question_count')
    required_accuracy = extra.get('required_accuracy')

    if not expected_total and required_accuracy is None:
        return CompletionCheckResult.pass_()

    correct_count = payload.get('correct_count')
    total_count = payload.get('total_count')
    if total_count is None or correct_count is None:
        return CompletionCheckResult.fail('能力练习完成需要提交 correct_count 和 total_count')

    if expected_total and total_count < expected_total:
        return CompletionCheckResult.fail(
            f'未完成全部训练（{total_count}/{expected_total}）',
        )

    if total_count <= 0:
        return CompletionCheckResult.fail('训练总数无效')

    if required_accuracy is None:
        return CompletionCheckResult.pass_()

    actual_accuracy = correct_count / total_count
    target_accuracy = float(required_accuracy)
    if actual_accuracy < target_accuracy:
        return CompletionCheckResult.fail(
            f'正确率 {actual_accuracy:.0%} 未达到要求 {target_accuracy:.0%}',
        )

    return CompletionCheckResult.pass_()


def _check_resource(item: StudyPlanItem, payload: dict[str, Any]) -> CompletionCheckResult:
    """
    资源模块完成判定：必须显式确认已读

    :param item: 计划项
    :param payload: 完成提交参数
    :return:
    """
    if payload.get('read_acknowledged') is True:
        return CompletionCheckResult.pass_()
    return CompletionCheckResult.fail('请确认已查阅资源后再提交')


_CHECKERS = {
    'review': _check_review,
    'practice': _check_practice,
    'wrong_review': _check_wrong_review,
    'ability': _check_ability,
    'resource': _check_resource,
}


def check_completion(item: StudyPlanItem, payload: dict[str, Any]) -> CompletionCheckResult:
    """
    根据计划项的 module_type 执行完成判定

    :param item: 计划项
    :param payload: 完成提交参数
    :return:
    """
    checker = _CHECKERS.get(item.module_type)
    if checker is None:
        return CompletionCheckResult.fail(f'未知模块类型: {item.module_type}')
    return checker(item, payload)
