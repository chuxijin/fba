#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import secrets

import bcrypt

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTasks

from backend.app.access.constants import SubscriptionSource
from backend.app.access.crud.crud_template import subscription_template_dao
from backend.app.access.model.subscription import Subscription
from backend.app.access.service.subscription_service import subscription_service
from backend.app.actcode.crud.crud_actcode import actcode_batch_dao, actcode_dao, actcode_usage_dao
from backend.app.actcode.model.actcode import Actcode, ActcodeBatch, ActcodeUsage
from backend.app.actcode.schema.actcode import OrderCodeActivateResult, OrderCodeLoginResult, OrderCodeVerifyResult
from backend.app.admin.crud.crud_user import user_dao
from backend.app.admin.model.user import User
from backend.app.admin.service.auth_service import auth_service
from backend.app.admin.utils.password_security import get_hash_password
from backend.app.question_bank.service.user_account_service import user_account_service
from backend.common.exception import errors
from backend.common.log import log
from backend.utils.timezone import timezone


class ActivateService:
    """订单号激活与登录服务"""

    ORDER_SOURCE = 'actcode_order'
    ORDER_SOURCE_PREFIX = 'actcode_order:'
    ORDER_REFUND_SOURCE_PREFIX = 'actcode_order_refund:'
    ORDER_REGISTER_CHANNEL = 'agiso_order'
    ORDER_USERNAME_PREFIX = 'ag'
    ORDER_DEFAULT_PASSWORD = '123456'

    @classmethod
    def _build_source_key(cls, order_no: str) -> str:
        """
        构建订单号幂等键

        :param order_no: 订单号
        :return:
        """
        source_key = f'{cls.ORDER_SOURCE_PREFIX}{order_no}'
        if len(source_key) <= 64:
            return source_key
        digest = hashlib.sha1(order_no.encode('utf-8'), usedforsecurity=False).hexdigest()[:24]
        return f'{cls.ORDER_SOURCE_PREFIX}{digest}'

    @classmethod
    def _build_refund_source_key(cls, order_no: str) -> str:
        """
        构建退款回收幂等键

        :param order_no: 订单号
        :return:
        """
        source_key = f'{cls.ORDER_REFUND_SOURCE_PREFIX}{order_no}'
        if len(source_key) <= 64:
            return source_key
        digest = hashlib.sha1(order_no.encode('utf-8'), usedforsecurity=False).hexdigest()[:24]
        return f'{cls.ORDER_REFUND_SOURCE_PREFIX}{digest}'

    @staticmethod
    def _normalize_order_input(order_input: str) -> str:
        """
        清洗订单号输入

        :param order_input: 原始文本
        :return:
        """
        normalized = order_input.strip()
        if not normalized:
            raise errors.RequestError(msg='请输入订单号')
        return normalized

    @staticmethod
    def _resolve_template_code(batch: ActcodeBatch) -> str | None:
        """
        从批次配置解析订阅模板编码

        :param batch: 激活码批次
        :return:
        """
        reward_data = batch.reward_data or {}
        template_code = reward_data.get('template_code')
        if template_code is None:
            return None

        value = str(template_code).strip()
        if not value:
            raise errors.RequestError(msg='批次 reward_data.template_code 配置错误')
        return value

    @classmethod
    def _safe_resolve_template_code(cls, batch: ActcodeBatch) -> str | None:
        """
        宽容获取模板编码

        :param batch: 激活码批次
        :return:
        """
        try:
            return cls._resolve_template_code(batch)
        except errors.BaseError:
            return None

    @classmethod
    async def _load_order_context(
        cls,
        db: AsyncSession,
        *,
        order_input: str,
        for_update: bool = False,
    ) -> tuple[Actcode, ActcodeBatch, ActcodeUsage | None]:
        """
        加载订单号上下文

        :param db: 数据库会话
        :param order_input: 原始输入
        :param for_update: 是否加行锁
        :return:
        """
        normalized_input = cls._normalize_order_input(order_input)
        matched = await actcode_dao.find_code_in_text(db, normalized_input)
        if not matched:
            raise errors.NotFoundError(msg='未识别到有效的订单号')

        stmt = select(Actcode).where(Actcode.id == matched.id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        actcode = result.scalar_one_or_none()
        if not actcode:
            raise errors.NotFoundError(msg='订单号不存在')

        batch = await actcode_batch_dao.select_model(db, actcode.batch_id)
        if not batch:
            raise errors.NotFoundError(msg='订单号所属批次不存在')

        usage = await actcode_usage_dao.get_by_code_id(db, actcode.id)
        return actcode, batch, usage

    @staticmethod
    def _ensure_batch_active(batch: ActcodeBatch) -> None:
        """
        检查批次是否可用

        :param batch: 激活码批次
        :return:
        """
        if batch.status != 1:
            raise errors.RequestError(msg='该订单号批次已停用')

        now = timezone.now()
        if batch.valid_from and now < batch.valid_from:
            raise errors.RequestError(msg='该订单号尚未到可使用时间')
        if batch.valid_to and now > batch.valid_to:
            raise errors.RequestError(msg='该订单号已过期')

    @classmethod
    def _ensure_order_consumable(
        cls,
        *,
        actcode: Actcode,
        batch: ActcodeBatch,
        usage: ActcodeUsage | None,
    ) -> None:
        """
        检查订单号是否可以消耗

        :param actcode: 激活码
        :param batch: 激活码批次
        :param usage: 使用记录
        :return:
        """
        if usage:
            return

        if actcode.status == 2:
            raise errors.RequestError(msg='该订单号已过期')
        if actcode.status == 1:
            raise errors.RequestError(msg='该订单号已被使用')

        cls._ensure_batch_active(batch)

        if actcode.used_count >= batch.max_use_per_code:
            raise errors.RequestError(msg='该订单号已被使用')

    @staticmethod
    async def _get_bound_user(db: AsyncSession, usage: ActcodeUsage | None) -> User | None:
        """
        获取订单号绑定的用户

        :param db: 数据库会话
        :param usage: 使用记录
        :return:
        """
        if not usage:
            return None

        try:
            user_id = int(usage.user_id)
        except (TypeError, ValueError) as exc:
            raise errors.RequestError(msg='订单号绑定账号数据异常') from exc

        user = await user_dao.get(db, user_id)
        if not user:
            raise errors.RequestError(msg='订单号绑定账号不存在')
        return user

    @classmethod
    async def _generate_username(cls, db: AsyncSession) -> str:
        """
        生成唯一用户名

        :param db: 数据库会话
        :return:
        """
        for _ in range(20):
            username = f'{cls.ORDER_USERNAME_PREFIX}{secrets.token_hex(4)}'
            existing = await user_dao.get_by_username(db, username)
            if not existing:
                return username
        raise errors.ServerError(msg='自动生成用户名失败')

    @classmethod
    async def _create_order_user(cls, db: AsyncSession, *, order_no: str) -> User:
        """
        为订单号自动创建用户

        :param db: 数据库会话
        :param order_no: 订单号
        :return:
        """
        username = await cls._generate_username(db)
        salt = bcrypt.gensalt()
        password = get_hash_password(cls.ORDER_DEFAULT_PASSWORD, salt)
        nickname = f'用户{order_no[-6:]}' if len(order_no) >= 6 else username

        return await user_dao.create_user_with_roles(
            db,
            user_data={
                'username': username,
                'nickname': nickname,
                'password': password,
                'salt': salt,
            },
        )

    @classmethod
    async def _grant_membership(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        batch: ActcodeBatch,
        order_no: str,
    ) -> Subscription:
        """
        根据订单号发放订阅

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param batch: 激活码批次
        :param order_no: 订单号
        :return:
        """
        template_code = cls._resolve_template_code(batch)
        if template_code is None:
            raise errors.RequestError(msg='该订单号未配置订阅模板')

        return await subscription_service.create_from_template(
            db,
            user_id=user_id,
            template_code=template_code,
            source=SubscriptionSource.ACTCODE,
            source_ref=cls._build_source_key(order_no),
        )

    @classmethod
    async def _get_membership_snapshot(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        batch: ActcodeBatch,
        order_no: str,
    ) -> Subscription | None:
        """
        获取订单号对应的订阅快照

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param batch: 激活码批次
        :param order_no: 订单号
        :return:
        """
        template_code = cls._resolve_template_code(batch)
        if template_code is None:
            return None

        from sqlalchemy import select as sa_select

        stmt = (
            sa_select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.source == SubscriptionSource.ACTCODE,
                Subscription.source_ref == cls._build_source_key(order_no),
            )
            .order_by(Subscription.id.desc())
        )
        return (await db.execute(stmt)).scalars().first()

    @classmethod
    async def _resolve_template_meta(
        cls,
        db: AsyncSession,
        *,
        subscription: Subscription | None,
    ) -> tuple[str | None, str | None]:
        """
        解析订阅关联的模板编码与名称

        :param db: 数据库会话
        :param subscription: 订阅
        :return:
        """
        if subscription is None:
            return None, None
        template = await subscription_template_dao.select_model(db, subscription.template_id)
        if template is None:
            return None, None
        return template.code, template.name

    @classmethod
    async def _consume_for_user(
        cls,
        db: AsyncSession,
        *,
        actcode: Actcode,
        batch: ActcodeBatch,
        usage: ActcodeUsage | None,
        user: User,
    ) -> tuple[bool, Subscription | None]:
        """
        将订单号消耗到指定用户

        :param db: 数据库会话
        :param actcode: 激活码
        :param batch: 激活码批次
        :param usage: 使用记录
        :param user: 用户
        :return:
        """
        if usage:
            if usage.user_id != str(user.id):
                raise errors.ConflictError(msg='该订单号已绑定其他账号')

            subscription = await cls._get_membership_snapshot(
                db, user_id=user.id, batch=batch, order_no=actcode.code
            )
            return False, subscription

        cls._ensure_order_consumable(actcode=actcode, batch=batch, usage=usage)
        subscription = await cls._grant_membership(db, user_id=user.id, batch=batch, order_no=actcode.code)
        await user_account_service.ensure_by_sys_user_id(
            db=db,
            sys_user_id=user.id,
            register_channel=cls.ORDER_REGISTER_CHANNEL,
        )

        db.add(
            ActcodeUsage(
                code_id=actcode.id,
                app_id=batch.app_id,
                user_id=str(user.id),
            )
        )

        new_used_count = actcode.used_count + 1
        new_status = 1 if new_used_count >= batch.max_use_per_code else actcode.status
        await actcode_dao.update_status(db, actcode.id, status=new_status, used_count=new_used_count)
        await actcode_batch_dao.increment_used_count(db, batch.id)
        return True, subscription

    @classmethod
    async def activate_current_user(
        cls,
        db: AsyncSession,
        *,
        order_input: str,
        current_user: User,
    ) -> OrderCodeActivateResult:
        """
        已登录用户将订单号绑定到当前账号

        :param db: 数据库会话
        :param order_input: 包含订单号的原始文本
        :param current_user: 当前用户
        :return:
        """
        actcode, batch, usage = await cls._load_order_context(db, order_input=order_input, for_update=True)
        just_activated, subscription = await cls._consume_for_user(
            db,
            actcode=actcode,
            batch=batch,
            usage=usage,
            user=current_user,
        )

        await user_account_service.ensure_by_sys_user_id(
            db=db,
            sys_user_id=current_user.id,
            register_channel=cls.ORDER_REGISTER_CHANNEL,
        )

        template_code, template_name = await cls._resolve_template_meta(db, subscription=subscription)

        log.info(
            'order activate success: order_no=%s, user_id=%s, just_activated=%s',
            actcode.code,
            current_user.id,
            just_activated,
        )
        return OrderCodeActivateResult(
            order_no=actcode.code,
            user_id=current_user.id,
            username=current_user.username,
            just_activated=just_activated,
            membership_plan_id=None,
            template_code=template_code,
            template_name=template_name,
            subscription_valid_to=subscription.valid_period.upper if subscription else None,
            message='订单号激活成功'
            if just_activated
            else '订单号已绑定当前账号',
        )

    @classmethod
    async def login_by_order(
        cls,
        db: AsyncSession,
        *,
        order_input: str,
        response: Response,
        background_tasks: BackgroundTasks,
    ) -> OrderCodeLoginResult:
        """
        通过订单号直接登录

        :param db: 数据库会话
        :param order_input: 包含订单号的原始文本
        :param response: FastAPI 响应对象
        :param background_tasks: 后台任务
        :return:
        """
        actcode, batch, usage = await cls._load_order_context(db, order_input=order_input, for_update=True)
        bound_user = await cls._get_bound_user(db, usage)

        auto_created = False
        if bound_user is None:
            cls._ensure_order_consumable(actcode=actcode, batch=batch, usage=usage)
            bound_user = await cls._create_order_user(db, order_no=actcode.code)
            auto_created = True

        just_activated, subscription = await cls._consume_for_user(
            db,
            actcode=actcode,
            batch=batch,
            usage=usage,
            user=bound_user,
        )
        await user_account_service.ensure_by_sys_user_id(
            db=db,
            sys_user_id=bound_user.id,
            register_channel=cls.ORDER_REGISTER_CHANNEL,
        )

        token_data = await auth_service.issue_login_token(
            db=db,
            response=response,
            user=bound_user,
            background_tasks=background_tasks,
            success_msg='订单号登录成功'
        )

        template_code, template_name = await cls._resolve_template_meta(db, subscription=subscription)

        log.info(
            'order login success: order_no=%s, user_id=%s, auto_created=%s, just_activated=%s',
            actcode.code,
            bound_user.id,
            auto_created,
            just_activated,
        )
        return OrderCodeLoginResult(
            **token_data.model_dump(),
            order_no=actcode.code,
            auto_created=auto_created,
            just_activated=just_activated,
            membership_plan_id=None,
            template_code=template_code,
            template_name=template_name,
            subscription_valid_to=subscription.valid_period.upper if subscription else None,
        )

    @classmethod
    async def verify_order(
        cls,
        db: AsyncSession,
        *,
        order_input: str,
    ) -> OrderCodeVerifyResult:
        """
        验证用户输入中是否包含有效的订单号

        :param db: 数据库会话
        :param order_input: 用户输入的原始文本
        :return:
        """
        try:
            actcode, batch, usage = await cls._load_order_context(db, order_input=order_input, for_update=False)
        except errors.BaseError as exc:
            return OrderCodeVerifyResult(
                valid=False,
                order_no=None,
                is_bound=False,
                can_login=False,
                username=None,
                message=exc.msg,
            )

        bound_user = await cls._get_bound_user(db, usage)
        try:
            template_code = cls._resolve_template_code(batch)
        except errors.BaseError as exc:
            return OrderCodeVerifyResult(
                valid=False,
                order_no=actcode.code,
                is_bound=bound_user is not None,
                can_login=False,
                username=bound_user.username if bound_user else None,
                message=exc.msg,
            )

        if bound_user:
            return OrderCodeVerifyResult(
                valid=True,
                order_no=actcode.code,
                is_bound=True,
                can_login=True,
                username=bound_user.username,
                message='订单号已绑定，可直接登录',
            )

        try:
            cls._ensure_order_consumable(actcode=actcode, batch=batch, usage=usage)
        except errors.BaseError as exc:
            return OrderCodeVerifyResult(
                valid=False,
                order_no=actcode.code,
                is_bound=False,
                can_login=False,
                username=None,
                message=exc.msg,
            )

        return OrderCodeVerifyResult(
            valid=True,
            order_no=actcode.code,
            is_bound=False,
            can_login=True,
            username=None,
            membership_plan_id=None,
            message=f'订单号有效，模板: {template_code}',
        )


activate_service: ActivateService = ActivateService()
