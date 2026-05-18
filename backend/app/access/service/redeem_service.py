#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.crud.crud_template import subscription_template_dao
from backend.app.access.schema.redeem import (
    AgisoBatchRuleParam,
    CreateRedeemBatchParam,
    GetRedeemBatchDetail,
    SetAgisoBatchRulesParam,
    UpdateRedeemBatchParam,
)
from backend.app.actcode.crud.crud_actcode import actcode_batch_dao
from backend.app.actcode.model import ActcodeBatch
from backend.app.actcode.service.actcode_service import actcode_service
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.core.conf import settings
from backend.plugin.config.crud.crud_config import config_dao
from backend.plugin.config.schema.config import CreateConfigParam, UpdateConfigParam

AGISO_BATCH_RULES_KEY = 'AGISO_BATCH_RULES'
AGISO_CONFIG_TYPE = 'AGISO'


class AccessRedeemService:
    """兑换配置服务"""

    @staticmethod
    def _to_batch_detail(batch: ActcodeBatch | dict[str, Any]) -> GetRedeemBatchDetail:
        """
        转换兑换批次详情

        :param batch: 激活码批次
        :return:
        """
        if isinstance(batch, dict):
            data = batch
        else:
            data = {
                'id': batch.id,
                'app_id': batch.app_id,
                'batch_no': batch.batch_no,
                'name': batch.name,
                'reward_type': batch.reward_type,
                'reward_data': batch.reward_data,
                'total_count': batch.total_count,
                'used_count': batch.used_count,
                'valid_from': batch.valid_from,
                'valid_to': batch.valid_to,
                'max_use_per_code': batch.max_use_per_code,
                'status': batch.status,
                'created_time': batch.created_time,
                'updated_time': batch.updated_time,
            }

        reward_data = data.get('reward_data') or {}
        template_code = reward_data.get('template_code')
        if template_code is not None:
            template_code = str(template_code)

        return GetRedeemBatchDetail(
            id=data['id'],
            app_id=data['app_id'],
            batch_no=data['batch_no'],
            name=data['name'],
            reward_type=data['reward_type'],
            reward_data=reward_data,
            template_code=template_code,
            total_count=data['total_count'],
            used_count=data['used_count'],
            valid_from=data.get('valid_from'),
            valid_to=data.get('valid_to'),
            max_use_per_code=data['max_use_per_code'],
            status=data['status'],
            created_time=data['created_time'],
            updated_time=data.get('updated_time'),
        )

    @staticmethod
    async def _ensure_template(db: AsyncSession, template_code: str) -> None:
        """
        确认订阅模板存在

        :param db: 数据库会话
        :param template_code: 模板编码
        :return:
        """
        template = await subscription_template_dao.get_by_code(db, template_code)
        if not template:
            raise errors.NotFoundError(msg=f'订阅模板不存在: {template_code}')

    @staticmethod
    def _normalize_rule(rule: AgisoBatchRuleParam) -> dict[str, int | str]:
        """
        规范化阿奇索规则

        :param rule: 规则参数
        :return:
        """
        platform = rule.platform.strip()
        keyword = rule.keyword.strip()
        if not platform:
            raise errors.RequestError(msg='阿奇索规则平台不能为空')
        if not keyword:
            raise errors.RequestError(msg='阿奇索规则关键词不能为空')
        return {
            'platform': platform,
            'keyword': keyword,
            'batch_id': rule.batch_id,
        }

    @staticmethod
    def _parse_rules(value: str) -> list[AgisoBatchRuleParam]:
        """
        解析阿奇索批次规则

        :param value: JSON 字符串
        :return:
        """
        try:
            raw_rules = json.loads(value)
        except json.JSONDecodeError as exc:
            raise errors.ServerError(msg='阿奇索批次规则 JSON 配置错误') from exc

        if not isinstance(raw_rules, list):
            raise errors.ServerError(msg='阿奇索批次规则必须是数组')

        rules: list[AgisoBatchRuleParam] = []
        for item in raw_rules:
            if not isinstance(item, dict):
                continue
            rules.append(AgisoBatchRuleParam.model_validate(item))
        return rules

    @staticmethod
    async def create_batch(db: AsyncSession, *, obj: CreateRedeemBatchParam) -> GetRedeemBatchDetail:
        """
        创建订单号兑换批次

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await AccessRedeemService._ensure_template(db, obj.template_code)
        batch = ActcodeBatch(
            app_id=obj.app_id,
            batch_no=actcode_service._generate_batch_no(),
            name=obj.name,
            reward_type='subscription',
            reward_data={'template_code': obj.template_code},
            generator_config=None,
            total_count=obj.total_count,
            used_count=0,
            valid_from=obj.valid_from,
            valid_to=obj.valid_to,
            max_use_per_code=obj.max_use_per_code,
            status=1,
        )
        db.add(batch)
        await db.flush()
        return AccessRedeemService._to_batch_detail(batch)

    @staticmethod
    async def get_batch(db: AsyncSession, *, pk: int) -> GetRedeemBatchDetail:
        """
        获取订单号兑换批次

        :param db: 数据库会话
        :param pk: 批次 ID
        :return:
        """
        batch = await actcode_batch_dao.select_model(db, pk)
        if not batch:
            raise errors.NotFoundError(msg='兑换批次不存在')
        return AccessRedeemService._to_batch_detail(batch)

    @staticmethod
    async def get_batch_list(
        *,
        db: AsyncSession,
        app_id: str | None = None,
        status: int | None = None,
        batch_no: str | None = None,
    ) -> dict[str, Any]:
        """
        获取订单号兑换批次列表

        :param db: 数据库会话
        :param app_id: 应用 ID
        :param status: 状态
        :param batch_no: 批次编号
        :return:
        """
        batch_select = await actcode_batch_dao.get_select(
            app_id=app_id,
            status=status,
            batch_no=batch_no,
            reward_type='subscription',
        )
        page_data = await paging_data(db, batch_select)
        page_data['items'] = [AccessRedeemService._to_batch_detail(item) for item in page_data['items']]
        return page_data

    @staticmethod
    async def update_batch(db: AsyncSession, *, pk: int, obj: UpdateRedeemBatchParam) -> int:
        """
        更新订单号兑换批次

        :param db: 数据库会话
        :param pk: 批次 ID
        :param obj: 更新参数
        :return:
        """
        batch = await actcode_batch_dao.select_model(db, pk)
        if not batch:
            raise errors.NotFoundError(msg='兑换批次不存在')

        data = obj.model_dump(exclude_unset=True, exclude={'template_code'})
        if obj.template_code is not None:
            await AccessRedeemService._ensure_template(db, obj.template_code)
            reward_data = dict(batch.reward_data or {})
            reward_data['template_code'] = obj.template_code
            data['reward_data'] = reward_data

        total_count = data.get('total_count')
        if total_count is not None and int(total_count) > 0 and int(total_count) < batch.used_count:
            raise errors.RequestError(msg='订单容量不能小于已写入订单数')

        return await actcode_batch_dao.update_model(db, pk, data)

    @staticmethod
    async def get_agiso_rules(db: AsyncSession) -> list[AgisoBatchRuleParam]:
        """
        获取阿奇索批次匹配规则

        :param db: 数据库会话
        :return:
        """
        config = await config_dao.get_by_key(db, AGISO_BATCH_RULES_KEY)
        if config and config.value:
            return AccessRedeemService._parse_rules(config.value)

        rules: list[AgisoBatchRuleParam] = []
        for item in settings.AGISO_BATCH_RULES:
            if not isinstance(item, dict):
                continue
            rules.append(AgisoBatchRuleParam.model_validate(item))
        return rules

    @staticmethod
    async def set_agiso_rules(db: AsyncSession, *, obj: SetAgisoBatchRulesParam) -> list[AgisoBatchRuleParam]:
        """
        设置阿奇索批次匹配规则

        :param db: 数据库会话
        :param obj: 规则参数
        :return:
        """
        normalized_rules = [AccessRedeemService._normalize_rule(rule) for rule in obj.rules]
        for rule in normalized_rules:
            batch = await actcode_batch_dao.select_model(db, int(rule['batch_id']))
            if not batch:
                raise errors.NotFoundError(msg=f'激活码批次不存在: {rule["batch_id"]}')

        value = json.dumps(normalized_rules, ensure_ascii=False)
        config = await config_dao.get_by_key(db, AGISO_BATCH_RULES_KEY)
        if config:
            await config_dao.update(
                db,
                config.id,
                UpdateConfigParam(
                    name='阿奇索批次匹配规则',
                    type=AGISO_CONFIG_TYPE,
                    key=AGISO_BATCH_RULES_KEY,
                    value=value,
                    is_frontend=False,
                    remark='阿奇索按平台和商品关键词匹配激活码批次',
                ),
            )
        else:
            await config_dao.create(
                db,
                CreateConfigParam(
                    name='阿奇索批次匹配规则',
                    type=AGISO_CONFIG_TYPE,
                    key=AGISO_BATCH_RULES_KEY,
                    value=value,
                    is_frontend=False,
                    remark='阿奇索按平台和商品关键词匹配激活码批次',
                ),
            )
        return [AgisoBatchRuleParam.model_validate(rule) for rule in normalized_rules]

    @staticmethod
    async def resolve_agiso_batch_id(
        db: AsyncSession,
        *,
        platform: str | None,
        goods_name: str | None,
        spec_name: str | None,
    ) -> int | None:
        """
        匹配阿奇索激活码批次 ID

        :param db: 数据库会话
        :param platform: 来源平台
        :param goods_name: 商品名称
        :param spec_name: 规格名称
        :return:
        """
        search_text = f'{goods_name or ""} {spec_name or ""}'
        rules = await AccessRedeemService.get_agiso_rules(db)
        for rule in rules:
            if platform != rule.platform:
                continue
            if rule.keyword in search_text:
                return rule.batch_id
        return None


access_redeem_service: AccessRedeemService = AccessRedeemService()
