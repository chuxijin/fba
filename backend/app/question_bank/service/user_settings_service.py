#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.schema.user_settings import CustomTab, GetStudyPreferenceResponse
from backend.app.question_bank.service.study_domain_config import normalize_study_domain_code
from backend.common.exception import errors


class UserSettingsService:
    """用户设置服务类"""

    @staticmethod
    def _load_settings(raw_settings: str | None) -> dict:
        """
        解析学习偏好设置

        :param raw_settings: 原始设置 JSON
        :return:
        """
        try:
            return json.loads(raw_settings or '{}')
        except Exception:
            return {}

    @staticmethod
    async def get_mastery_threshold(*, db: AsyncSession, user_id: int) -> int:
        """获取用户错题掌握阈值（轻量读取，供判题流程调用）"""
        user = await user_account_dao.get_by_sys_user_id(db, user_id)
        if not user:
            return 3

        settings = UserSettingsService._load_settings(user.study_preference_settings)
        try:
            value = settings.get('mastery_threshold', 3)
            return max(1, min(20, int(value)))
        except Exception:
            return 3

    @staticmethod
    async def get_current_domain(*, db: AsyncSession, user_id: int) -> str:
        """
        获取当前学习领域

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        user = await user_account_dao.get_by_sys_user_id(db, user_id)
        if not user:
            return normalize_study_domain_code(None)

        settings = UserSettingsService._load_settings(user.study_preference_settings)
        return normalize_study_domain_code(settings.get('current_domain'))

    @staticmethod
    async def get_study_preference(*, db: AsyncSession, user_id: int) -> GetStudyPreferenceResponse:
        """
        获取学习偏好设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 学习偏好设置
        """
        user = await user_account_dao.get_by_sys_user_id(db, user_id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')

        settings = UserSettingsService._load_settings(user.study_preference_settings)
        practice_mode = settings.get('practice_mode', 'practice')
        custom_tabs = settings.get('custom_tabs', [])
        mastery_threshold = settings.get('mastery_threshold', 3)
        current_domain = normalize_study_domain_code(settings.get('current_domain'))

        return GetStudyPreferenceResponse(
            current_domain=current_domain,
            practice_mode=practice_mode,
            custom_tabs=custom_tabs,
            mastery_threshold=mastery_threshold,
        )

    @staticmethod
    async def update_study_preference(
        *,
        db: AsyncSession,
        user_id: int,
        current_domain: str | None,
        practice_mode: str | None,
        custom_tabs: list[CustomTab] | None,
        mastery_threshold: int | None,
    ) -> None:
        """
        更新学习偏好设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param practice_mode: 练习模式
        :param custom_tabs: 自定义标签页
        :param mastery_threshold: 错题掌握阈值
        """
        user = await user_account_dao.get_by_sys_user_id(db, user_id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')

        current_settings = UserSettingsService._load_settings(user.study_preference_settings)

        if current_domain is not None:
            current_settings['current_domain'] = normalize_study_domain_code(current_domain)

        if practice_mode is not None:
            current_settings['practice_mode'] = practice_mode

        if custom_tabs is not None:
            current_settings['custom_tabs'] = [tab.model_dump() for tab in custom_tabs]

        if mastery_threshold is not None:
            current_settings['mastery_threshold'] = mastery_threshold

        await user_account_dao.update_model(
            db,
            user.id,
            {'study_preference_settings': json.dumps(current_settings)},
        )


user_settings_service = UserSettingsService()
