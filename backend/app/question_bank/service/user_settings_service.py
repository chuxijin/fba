#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.schema.user_settings import CategoryCustomTabs, GetStudyPreferenceResponse
from backend.app.question_bank.service.category_filter_service import category_filter_service
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
    async def get_current_category_ids(*, db: AsyncSession, user_id: int) -> tuple[int | None, int | None]:
        """
        获取当前分类偏好

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        user = await user_account_dao.get_by_sys_user_id(db, user_id)
        if not user:
            return None, None

        settings = UserSettingsService._load_settings(user.study_preference_settings)
        return settings.get('current_cat_id'), settings.get('current_kp_cat_id')

    @staticmethod
    def _normalize_theme_mode(value: str | None) -> str:
        """规范化主题模式取值，非法值统一回落为 light"""
        if value in ('light', 'dark', 'auto'):
            return value
        return 'light'

    @staticmethod
    def _normalize_random_practice_count(value: int | str | None) -> int:
        """规范化随机练习题目数"""
        try:
            count = int(value or 20)
        except Exception:
            return 20
        return max(10, min(100, count))

    @staticmethod
    def _normalize_random_practice_year_range(value: str | None) -> str:
        """规范化随机练习年份范围"""
        if value in ('last_3_years', 'last_5_years'):
            return value
        return 'unlimited'

    @staticmethod
    def _normalize_category_custom_tabs(value: dict | None) -> dict:
        """
        规范化分类 Tab 配置

        :param value: 原始分类 Tab 配置
        :return:
        """
        if not isinstance(value, dict):
            return {}

        result: dict = {}
        for scope_key, tabs in value.items():
            if not isinstance(tabs, list):
                result[str(scope_key)] = []
                continue
            result[str(scope_key)] = tabs
        return result

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
        category_custom_tabs = UserSettingsService._normalize_category_custom_tabs(settings.get('category_custom_tabs'))
        mastery_threshold = settings.get('mastery_threshold', 3)
        theme_mode = UserSettingsService._normalize_theme_mode(settings.get('theme_mode'))
        random_practice_count = UserSettingsService._normalize_random_practice_count(
            settings.get('random_practice_count'),
        )
        random_practice_year_range = UserSettingsService._normalize_random_practice_year_range(
            settings.get('random_practice_year_range'),
        )

        return GetStudyPreferenceResponse(
            current_cat_id=settings.get('current_cat_id'),
            current_kp_cat_id=settings.get('current_kp_cat_id'),
            practice_mode=practice_mode,
            category_custom_tabs=category_custom_tabs,
            mastery_threshold=mastery_threshold,
            theme_mode=theme_mode,
            random_practice_count=random_practice_count,
            random_practice_year_range=random_practice_year_range,
        )

    @staticmethod
    async def update_study_preference(
        *,
        db: AsyncSession,
        user_id: int,
        current_cat_id: int | None,
        current_kp_cat_id: int | None,
        practice_mode: str | None,
        category_custom_tabs: CategoryCustomTabs | None,
        mastery_threshold: int | None,
        theme_mode: str | None,
        random_practice_count: int | None,
        random_practice_year_range: str | None,
    ) -> None:
        """
        更新学习偏好设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param practice_mode: 练习模式
        :param category_custom_tabs: 按分类范围隔离的自定义标签页
        :param mastery_threshold: 错题掌握阈值
        :param theme_mode: 主题模式（light/dark/auto）
        :param random_practice_count: 随机练习题目数
        :param random_practice_year_range: 随机练习年份范围
        """
        user = await user_account_dao.get_by_sys_user_id(db, user_id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')

        current_settings = UserSettingsService._load_settings(user.study_preference_settings)

        if current_cat_id is not None:
            current_settings['current_cat_id'] = current_cat_id

        if current_kp_cat_id is not None:
            current_settings['current_kp_cat_id'] = current_kp_cat_id

        if practice_mode is not None:
            current_settings['practice_mode'] = practice_mode

        if category_custom_tabs is not None:
            current_settings['category_custom_tabs'] = {
                str(scope_key): [tab.model_dump() for tab in tabs]
                for scope_key, tabs in category_custom_tabs.items()
            }

        if mastery_threshold is not None:
            current_settings['mastery_threshold'] = mastery_threshold

        if theme_mode is not None:
            current_settings['theme_mode'] = UserSettingsService._normalize_theme_mode(theme_mode)

        if random_practice_count is not None:
            current_settings['random_practice_count'] = UserSettingsService._normalize_random_practice_count(
                random_practice_count,
            )

        if random_practice_year_range is not None:
            current_settings['random_practice_year_range'] = UserSettingsService._normalize_random_practice_year_range(
                random_practice_year_range,
            )

        await user_account_dao.update_model(
            db,
            user.id,
            {'study_preference_settings': json.dumps(current_settings)},
        )

    @staticmethod
    async def initialize_category_preference(
        *,
        db: AsyncSession,
        user_id: int,
        cat_id: int,
        kp_cat_id: int | None,
    ) -> dict:
        """
        新用户选择分类后初始化默认偏好

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param cat_id: 题库目录分类 ID
        :param kp_cat_id: 知识点分类 ID
        :return:
        """
        user = await user_account_dao.get_by_sys_user_id(db, user_id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')

        current_settings = UserSettingsService._load_settings(user.study_preference_settings)
        category_custom_tabs = UserSettingsService._normalize_category_custom_tabs(
            current_settings.get('category_custom_tabs'),
        )
        scope_key = category_filter_service.build_scope_key(cat_id=cat_id, kp_cat_id=kp_cat_id)
        category_custom_tabs.setdefault(scope_key, [])
        current_settings['current_cat_id'] = cat_id
        current_settings['current_kp_cat_id'] = kp_cat_id
        current_settings['category_custom_tabs'] = category_custom_tabs

        await user_account_dao.update_model(
            db,
            user.id,
            {'study_preference_settings': json.dumps(current_settings)},
        )

        return category_custom_tabs


user_settings_service = UserSettingsService()
