#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.schema.user_settings import CustomTab, GetStudyPreferenceResponse
from backend.common.exception import errors


class UserSettingsService:
    """用户设置服务类"""

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

        try:
            settings = json.loads(user.study_preference_settings or '{}')
            practice_mode = settings.get('practice_mode', 'practice')
            custom_tabs = settings.get('custom_tabs', [])
        except Exception:
            practice_mode = 'practice'
            custom_tabs = []

        return GetStudyPreferenceResponse(practice_mode=practice_mode, custom_tabs=custom_tabs)

    @staticmethod
    async def update_study_preference(
        *,
        db: AsyncSession,
        user_id: int,
        practice_mode: str | None,
        custom_tabs: list[CustomTab] | None,
    ) -> None:
        """
        更新学习偏好设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param practice_mode: 练习模式
        :param custom_tabs: 自定义标签页
        """
        user = await user_account_dao.get_by_sys_user_id(db, user_id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')

        try:
            current_settings = json.loads(user.study_preference_settings or '{}')
        except Exception:
            current_settings = {}

        if practice_mode is not None:
            current_settings['practice_mode'] = practice_mode

        if custom_tabs is not None:
            current_settings['custom_tabs'] = [tab.model_dump() for tab in custom_tabs]

        await user_account_dao.update_model(
            db,
            user.id,
            {'study_preference_settings': json.dumps(current_settings)},
        )


user_settings_service = UserSettingsService()
