#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.category import Category
from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.schema.user_settings import CustomTab, GetStudyPreferenceResponse
from backend.app.question_bank.service.study_domain_config import (
    get_study_domain_default_tab_codes,
    normalize_study_domain_code,
)
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
    def _normalize_theme_mode(value: str | None) -> str:
        """规范化主题模式取值，非法值统一回落为 light"""
        if value in ('light', 'dark', 'auto'):
            return value
        return 'light'

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
        theme_mode = UserSettingsService._normalize_theme_mode(settings.get('theme_mode'))

        return GetStudyPreferenceResponse(
            current_domain=current_domain,
            practice_mode=practice_mode,
            custom_tabs=custom_tabs,
            mastery_threshold=mastery_threshold,
            theme_mode=theme_mode,
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
        theme_mode: str | None,
    ) -> None:
        """
        更新学习偏好设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param practice_mode: 练习模式
        :param custom_tabs: 自定义标签页
        :param mastery_threshold: 错题掌握阈值
        :param theme_mode: 主题模式（light/dark/auto）
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

        if theme_mode is not None:
            current_settings['theme_mode'] = UserSettingsService._normalize_theme_mode(theme_mode)

        await user_account_dao.update_model(
            db,
            user.id,
            {'study_preference_settings': json.dumps(current_settings)},
        )

    @staticmethod
    async def initialize_domain_preference(*, db: AsyncSession, user_id: int, domain_code: str) -> list[dict]:
        """
        新用户选择领域后初始化默认偏好（current_domain + 默认 custom_tabs）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param domain_code: 学习领域编码
        :return:
        """
        user = await user_account_dao.get_by_sys_user_id(db, user_id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')

        normalized_domain = normalize_study_domain_code(domain_code)
        tab_codes = get_study_domain_default_tab_codes(normalized_domain)

        # 根据 code 从分类表批量查出 id 和 name
        custom_tabs: list[dict] = []
        if tab_codes:
            stmt = (
                select(Category.id, Category.name, Category.code, Category.sort_order)
                .where(Category.code.in_(tab_codes))
                .order_by(Category.sort_order)
            )
            rows = (await db.execute(stmt)).all()

            # 按 tab_codes 的顺序排列
            code_order = {code: idx for idx, code in enumerate(tab_codes)}
            sorted_rows = sorted(rows, key=lambda r: code_order.get(r.code, 999))

            custom_tabs = [
                {
                    'id': str(row.id),
                    'name': row.name,
                    'category_id': row.id,
                    'category_name': row.name,
                    'bank_id': None,
                    'bank_name': None,
                    'is_fixed': False,
                    'order': idx,
                }
                for idx, row in enumerate(sorted_rows)
            ]

        current_settings = UserSettingsService._load_settings(user.study_preference_settings)
        current_settings['current_domain'] = normalized_domain
        current_settings['custom_tabs'] = custom_tabs

        await user_account_dao.update_model(
            db,
            user.id,
            {'study_preference_settings': json.dumps(current_settings)},
        )

        return custom_tabs


user_settings_service = UserSettingsService()
