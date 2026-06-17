#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import string

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.actcode.crud.crud_actcode import actcode_batch_dao, actcode_dao, actcode_usage_dao
from backend.app.actcode.schema.actcode import (
    CreateBatchParam,
    GetBatchDetail,
    RedeemCodeParam,
    RedeemCodeResult,
    UpdateBatchParam,
)
from backend.app.actcode.schema.code_config import CodeGeneratorConfig
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


class ActcodeService:
    """激活码服务类"""

    @staticmethod
    def _build_charset(config: CodeGeneratorConfig) -> str:
        """
        构建字符集

        :param config: 生成器配置
        :return:
        """
        charset = ''

        if config.use_digits:
            charset += string.digits

        if config.use_letters:
            if config.letter_case == 'upper':
                charset += string.ascii_uppercase
            elif config.letter_case == 'lower':
                charset += string.ascii_lowercase
            else:
                charset += string.ascii_letters

        if config.use_special and config.special_chars:
            charset += config.special_chars

        for char in config.exclude_chars:
            charset = charset.replace(char, '')

        if not charset:
            raise ValueError('字符集不能为空，请检查配置')

        return charset

    @staticmethod
    def _contains_excluded_words(code: str, exclude_words: list[str]) -> bool:
        """
        检测是否包含敏感词

        :param code: 激活码
        :param exclude_words: 敏感词列表
        :return:
        """
        if not exclude_words:
            return False

        code_upper = code.upper()
        for word in exclude_words:
            if word.upper() in code_upper:
                return True
        return False

    @staticmethod
    def _calculate_checksum(code: str) -> str:
        """
        计算校验位

        :param code: 激活码
        :return:
        """
        checksum = sum(ord(c) for c in code) % 36
        if checksum < 10:
            return str(checksum)
        return chr(ord('A') + checksum - 10)

    @staticmethod
    def _generate_code(config: CodeGeneratorConfig, max_attempts: int = 100) -> str:
        """
        根据配置生成激活码

        :param config: 生成器配置
        :param max_attempts: 最大尝试次数
        :return:
        """
        charset = ActcodeService._build_charset(config)

        for _ in range(max_attempts):
            code_parts = []
            for _ in range(config.groups):
                part = ''.join(random.choices(charset, k=config.group_length))
                code_parts.append(part)

            code_body = config.separator.join(code_parts)

            if ActcodeService._contains_excluded_words(code_body, config.exclude_words):
                continue

            if config.use_checksum:
                checksum = ActcodeService._calculate_checksum(code_body.replace(config.separator, ''))
                code = f'{config.prefix}{code_body}{config.separator}{checksum}{config.suffix}'
            else:
                code = f'{config.prefix}{code_body}{config.suffix}'

            return code

        raise ValueError(f'生成激活码失败，已尝试 {max_attempts} 次，请检查配置或减少敏感词数量')

    @staticmethod
    def _generate_batch_no() -> str:
        """生成批次编号"""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_str = ''.join(random.choices(string.digits, k=6))
        return f'BATCH{timestamp}{random_str}'

    @staticmethod
    def _get_default_config() -> CodeGeneratorConfig:
        """获取默认配置"""
        return CodeGeneratorConfig(
            groups=3,
            group_length=5,
            separator='-',
            use_digits=True,
            use_letters=True,
            letter_case='upper',
            exclude_chars=['O', '0', 'I', '1'],
        )

    @staticmethod
    async def create_batch(*, db: AsyncSession, obj: CreateBatchParam) -> GetBatchDetail:
        """
        创建批次并生成激活码

        :param db: 数据库会话
        :param obj: 批次创建参数
        :return:
        """
        batch_no = ActcodeService._generate_batch_no()

        config = obj.generator_config or ActcodeService._get_default_config()

        codes = []
        for _ in range(obj.total_count):
            code = ActcodeService._generate_code(config)
            codes.append(code)

        batch = await actcode_batch_dao.create(db, obj, batch_no)

        await actcode_dao.bulk_create(db, batch.id, codes)

        await db.commit()
        await db.refresh(batch)
        return GetBatchDetail.model_validate(batch)

    @staticmethod
    async def get_batch_list(
        *, db: AsyncSession, app_id: str | None = None, status: int | None = None, batch_no: str | None = None
    ) -> dict[str, Any]:
        """
        获取批次列表

        :param db: 数据库会话
        :param app_id: 应用 ID
        :param status: 状态
        :param batch_no: 批次编号
        :return:
        """
        batch_select = await actcode_batch_dao.get_select(app_id=app_id, status=status, batch_no=batch_no)
        return await paging_data(db, batch_select)

    @staticmethod
    async def get_batch(*, db: AsyncSession, pk: int) -> GetBatchDetail:
        """
        获取批次详情

        :param db: 数据库会话
        :param pk: 批次 ID
        :return:
        """
        batch = await actcode_batch_dao.select_model(db, pk)
        if not batch:
            raise errors.NotFoundError(msg='批次不存在')
        return GetBatchDetail.model_validate(batch)

    @staticmethod
    async def update_batch(*, db: AsyncSession, pk: int, obj: UpdateBatchParam) -> int:
        """
        更新批次

        :param db: 数据库会话
        :param pk: 批次 ID
        :param obj: 更新参数
        :return:
        """
        batch = await actcode_batch_dao.select_model(db, pk)
        if not batch:
            raise errors.NotFoundError(msg='批次不存在')
        count = await actcode_batch_dao.update_model(db, pk, obj)
        return count

    @staticmethod
    async def get_code_list(
        *, db: AsyncSession, batch_id: int | None = None, status: int | None = None
    ) -> dict[str, Any]:
        """
        获取激活码列表

        :param db: 数据库会话
        :param batch_id: 批次 ID
        :param status: 状态
        :return:
        """
        code_select = await actcode_dao.get_select(batch_id=batch_id, status=status)
        return await paging_data(db, code_select)

    @staticmethod
    async def query_code_info(*, db: AsyncSession, code: str, app_id: str) -> RedeemCodeResult:
        """
        查询激活码信息（不实际激活）

        :param db: 数据库会话
        :param code: 激活码
        :param app_id: 应用ID
        :return: 激活码信息
        """
        actcode = await actcode_dao.get_by_code(db, code)
        if not actcode:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码不存在')

        if actcode.status == 2:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码已过期')

        batch = await actcode_batch_dao.select_model(db, actcode.batch_id)
        if not batch:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='批次不存在')

        if batch.app_id != app_id:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码不属于当前应用')

        if batch.status == 0:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='批次已停用')

        now = timezone.now()
        if batch.valid_from and now < batch.valid_from:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码未到使用时间')

        if batch.valid_to and now > batch.valid_to:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码已过期')

        if actcode.used_count >= batch.max_use_per_code:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码已达最大使用次数')

        # 返回激活码信息，但不实际激活
        return RedeemCodeResult(
            success=True, reward_type=batch.reward_type, reward_data=batch.reward_data, message='激活码有效'
        )

    @staticmethod
    async def redeem_code(*, db: AsyncSession, obj: RedeemCodeParam) -> RedeemCodeResult:
        """
        兑换激活码

        :param db: 数据库会话
        :param obj: 兑换参数
        :return:
        """
        actcode = await actcode_dao.get_by_code(db, obj.code)
        if not actcode:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码不存在')

        if actcode.status == 2:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码已过期')

        batch = await actcode_batch_dao.select_model(db, actcode.batch_id)
        if not batch:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='批次不存在')

        if batch.app_id != obj.app_id:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码不属于当前应用')

        if batch.status == 0:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='批次已停用')

        now = timezone.now()
        if batch.valid_from and now < batch.valid_from:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码未到使用时间')

        if batch.valid_to and now > batch.valid_to:
            await actcode_dao.update_status(db, actcode.id, 2, actcode.used_count)
            await db.commit()
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码已过期')

        if actcode.used_count >= batch.max_use_per_code:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='激活码已达最大使用次数')

        is_used = await actcode_usage_dao.check_user_used(db, actcode.id, obj.user_id)
        if is_used:
            return RedeemCodeResult(success=False, reward_type='', reward_data={}, message='您已使用过该激活码')

        await actcode_usage_dao.create(db, obj, actcode.id)

        new_used_count = actcode.used_count + 1
        new_status = 1 if new_used_count >= batch.max_use_per_code else actcode.status
        await actcode_dao.update_status(db, actcode.id, new_status, new_used_count)

        await actcode_batch_dao.increment_used_count(db, batch.id)

        await db.commit()

        return RedeemCodeResult(
            success=True, reward_type=batch.reward_type, reward_data=batch.reward_data, message='兑换成功'
        )

    @staticmethod
    async def get_usage_list(
        *, db: AsyncSession, app_id: str | None = None, user_id: str | None = None, code_id: int | None = None
    ) -> dict[str, Any]:
        """
        获取使用记录列表

        :param db: 数据库会话
        :param app_id: 应用 ID
        :param user_id: 用户 ID
        :param code_id: 激活码 ID
        :return:
        """
        usage_select = await actcode_usage_dao.get_select(app_id=app_id, user_id=user_id, code_id=code_id)
        return await paging_data(db, usage_select)


actcode_service: ActcodeService = ActcodeService()
