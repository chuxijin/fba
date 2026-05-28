#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

import httpx

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import SubscriptionSource
from backend.app.access.service.subscription_service import subscription_service
from backend.app.growth.service import experience_service
from backend.common.log import log
from backend.core.conf import settings


class BaseRewardFulfiller(ABC):
    """权益履约基类"""

    @abstractmethod
    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """

    async def revoke(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        撤销权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        log.warning(f'{self.__class__.__name__} 不支持撤销权益')
        return False


def _parse_positive_int(value: object) -> int | None:
    """
    解析正整数

    :param value: 原始值
    :return:
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        if parsed > 0:
            return parsed
    return None


class VipFulfiller(BaseRewardFulfiller):
    """会员订阅履约(基于 access.subscription)"""

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放会员订阅(reward_data: {template_code, days?, source_key, ...})

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        template_code = str(reward_data.get('template_code') or '').strip()
        days = _parse_positive_int(reward_data.get('days'))
        source = str(reward_data.get('source') or 'reward').strip() or 'reward'
        source_key = str(reward_data.get('source_key') or '').strip()

        if not template_code:
            log.warning(f'会员发放失败: user_id={user_id}, reason=missing_template_code')
            return False
        if not source_key:
            log.warning(f'会员发放失败: user_id={user_id}, reason=missing_source_key')
            return False

        try:
            if days is None:
                await subscription_service.create_from_template(
                    db,
                    user_id=user_id,
                    template_code=template_code,
                    source=SubscriptionSource(source) if source in {s.value for s in SubscriptionSource} else SubscriptionSource.GIFT,
                    source_ref=source_key,
                )
            else:
                await subscription_service.extend_by_days(
                    db,
                    user_id=user_id,
                    template_code=template_code,
                    days=days,
                    source=SubscriptionSource(source) if source in {s.value for s in SubscriptionSource} else SubscriptionSource.GIFT,
                    source_ref=source_key,
                )
        except Exception as exc:
            log.warning(
                f'会员发放失败: user_id={user_id}, template={template_code}, error={exc!s}'
            )
            return False

        log.info(
            f'会员发放成功: user_id={user_id}, template={template_code}, '
            f'days={days}, source={source}, source_key={source_key}'
        )
        return True

    async def revoke(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        撤销会员订阅

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        source = str(reward_data.get('source') or 'reward').strip() or 'reward'
        source_key = str(reward_data.get('source_key') or '').strip()
        reason = reward_data.get('reason') or '权益撤销'

        if not source_key:
            log.warning(f'会员撤销失败: user_id={user_id}, reason=missing_source_key')
            return False

        try:
            count = await subscription_service.revoke_by_source(
                db,
                user_id=user_id,
                source=source,
                source_ref=source_key,
                reason=reason,
            )
        except Exception as exc:
            log.warning(f'会员撤销失败: user_id={user_id}, source_key={source_key}, error={exc!s}')
            return False

        log.info(f'会员撤销成功: user_id={user_id}, source_key={source_key}, count={count}')
        return True


class PointsFulfiller(BaseRewardFulfiller):
    """经验值履约(基于 growth.experience)"""

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放经验值

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        amount = _parse_positive_int(reward_data.get('amount'))
        source = str(reward_data.get('source') or 'reward').strip() or 'reward'
        source_key = str(reward_data.get('source_key') or '').strip()
        reason = reward_data.get('reason') or '经验奖励'

        if amount is None:
            log.warning(f'经验发放失败: user_id={user_id}, reason=invalid_amount')
            return False
        if not source_key:
            log.warning(f'经验发放失败: user_id={user_id}, reason=missing_source_key')
            return False

        family_code = await experience_service.resolve_reward_family(db, user_id=user_id)
        try:
            await experience_service.add_experience(
                db,
                user_id=user_id,
                family_code=str(family_code),
                exp_delta=amount,
                source=source,
                source_key=source_key,
                reason=reason,
            )
        except Exception as exc:
            log.warning(f'经验发放失败: user_id={user_id}, amount={amount}, error={exc!s}')
            return False

        log.info(
            f'经验发放成功: user_id={user_id}, amount={amount}, '
            f'family={family_code}, source={source}, source_key={source_key}'
        )
        return True

    async def revoke(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        撤销经验值(从可用经验中扣回)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        amount = _parse_positive_int(reward_data.get('amount'))
        source_key = str(reward_data.get('source_key') or '').strip()
        reason = reward_data.get('reason') or '权益撤销'

        if amount is None:
            log.warning(f'经验撤销失败: user_id={user_id}, reason=invalid_amount')
            return False
        if not source_key:
            log.warning(f'经验撤销失败: user_id={user_id}, reason=missing_source_key')
            return False

        family_code = await experience_service.resolve_reward_family(db, user_id=user_id)
        try:
            await experience_service.consume_experience(
                db,
                user_id=user_id,
                family_code=str(family_code),
                exp_delta=amount,
                source='reward_revoke',
                source_key=f'revoke:{source_key}',
                reason=reason,
            )
        except Exception as exc:
            log.warning(f'经验撤销失败: user_id={user_id}, amount={amount}, error={exc!s}')
            return False

        log.info(
            f'经验撤销成功: user_id={user_id}, amount={amount}, '
            f'family={family_code}, source_key={source_key}'
        )
        return True


class FeatureFulfiller(BaseRewardFulfiller):
    """功能权益履约(占位, 后续接 access.direct_grant)"""

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放功能权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        feature_key = reward_data.get('feature_key', '')
        days = reward_data.get('days', 0)
        log.info(f'发放功能权益: user_id={user_id}, feature={feature_key}, days={days}')
        return True


class ChaojiCourseFulfiller(BaseRewardFulfiller):
    """超级考研课程开通履约"""

    # 该履约器配合 quest 使用:
    # - quest_task.review_strategy 一般配置为 order_phone_required, 先校验用户提交的 order_no / phone
    # - quest_task.reward_type 配置为 chaoji_course
    # - quest_task.reward_data 配置 product_id / type / product_name
    # - 用户提交的手机号来自 quest_claim.submission_data.phone
    #
    # 新增其它超级考研商品时, 不需要改代码, 只新增/复制任务并替换 reward_data.product_id。
    # 新增其它第三方平台时, 不要复用本类, 应新增独立 Fulfiller 并在 dispatcher.py 注册。
    _session_id: str | None = None

    @staticmethod
    def _base_url() -> str:
        """获取超级考研基础地址"""
        return settings.CHAOJI_KAOYAN_BASE_URL.rstrip('/')

    @staticmethod
    def _get_submission_phone(reward_data: dict) -> str:
        """
        获取用户提交手机号

        :param reward_data: 权益数据
        :return:
        """
        submission_data = reward_data.get('claim_submission_data') or {}
        phone = str(submission_data.get('phone') or '').strip()
        return phone

    @staticmethod
    def _get_product_id(reward_data: dict) -> int | None:
        """
        获取超级考研商品 ID

        :param reward_data: 权益数据
        :return:
        """
        return _parse_positive_int(reward_data.get('product_id'))

    @staticmethod
    async def _login(client: httpx.AsyncClient) -> str | None:
        """
        登录超级考研代理后台

        :param client: HTTP 客户端
        :return:
        """
        if not settings.CHAOJI_KAOYAN_AGENT_TEL or not settings.CHAOJI_KAOYAN_AGENT_KEY:
            log.warning('超级考研开通失败: 未配置代理账号')
            return None

        response = await client.post(
            f'{ChaojiCourseFulfiller._base_url()}/index.php/DitfIdentifyLogin',
            data={
                'method': '1',
                'tel': settings.CHAOJI_KAOYAN_AGENT_TEL,
                'key': settings.CHAOJI_KAOYAN_AGENT_KEY,
            },
            headers={
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f'{ChaojiCourseFulfiller._base_url()}/index.php/PageIdentifyLogin',
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get('code') != 1:
            log.warning(f'超级考研登录失败: response={payload}')
            return None

        session_id = client.cookies.get('PHPSESSID')
        if not session_id:
            log.warning('超级考研登录失败: 未返回 PHPSESSID')
            return None

        ChaojiCourseFulfiller._session_id = session_id
        return session_id

    @staticmethod
    async def _submit_order(
        *,
        client: httpx.AsyncClient,
        product_id: int,
        phone: str,
        order_type: int,
    ) -> dict:
        """
        提交超级考研开通订单

        :param client: HTTP 客户端
        :param product_id: 商品 ID
        :param phone: 开通手机号
        :param order_type: 订单类型
        :return:
        """
        response = await client.post(
            f'{ChaojiCourseFulfiller._base_url()}/DitfAgentSubMitOutLineOrder',
            data={
                'productId': str(product_id),
                'tel': phone,
                'type': str(order_type),
            },
            headers={
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f'{ChaojiCourseFulfiller._base_url()}/view/agent_store.html',
            },
        )
        response.raise_for_status()
        return response.json()

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        开通超级考研课程

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        product_id = self._get_product_id(reward_data)
        phone = self._get_submission_phone(reward_data)
        order_type = _parse_positive_int(reward_data.get('type')) or settings.CHAOJI_KAOYAN_ORDER_TYPE

        if product_id is None:
            raise RuntimeError('超级考研开通失败: 缺少 product_id')
        if not phone:
            raise RuntimeError('超级考研开通失败: 缺少开通手机号')

        timeout = httpx.Timeout(float(settings.CHAOJI_KAOYAN_REQUEST_TIMEOUT))
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                if not self._session_id:
                    session_id = await self._login(client)
                    if not session_id:
                        raise RuntimeError('超级考研登录失败')
                else:
                    client.cookies.set('PHPSESSID', self._session_id, domain='www.chaojikaoyan.com')

                response_data = await self._submit_order(
                    client=client,
                    product_id=product_id,
                    phone=phone,
                    order_type=order_type,
                )
                if response_data.get('code') != 1:
                    session_id = await self._login(client)
                    if not session_id:
                        raise RuntimeError(f'超级考研重新登录失败: response={response_data}')
                    response_data = await self._submit_order(
                        client=client,
                        product_id=product_id,
                        phone=phone,
                        order_type=order_type,
                    )
        except Exception as exc:
            log.warning(f'超级考研开通异常: user_id={user_id}, product_id={product_id}, phone={phone}, error={exc!s}')
            raise

        success = response_data.get('code') == 1
        if not success:
            raise RuntimeError(f'超级考研开通失败: response={response_data}')

        log.info(f'超级考研开通成功: user_id={user_id}, product_id={product_id}, phone={phone}')
        return True
