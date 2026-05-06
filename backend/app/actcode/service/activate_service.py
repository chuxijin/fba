#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import secrets

import bcrypt

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTasks

from backend.app.actcode.crud.crud_actcode import actcode_batch_dao, actcode_dao, actcode_usage_dao
from backend.app.actcode.model.actcode import Actcode, ActcodeBatch, ActcodeUsage
from backend.app.actcode.schema.actcode import OrderCodeActivateResult, OrderCodeLoginResult, OrderCodeVerifyResult
from backend.app.admin.crud.crud_user import user_dao
from backend.app.admin.model.user import User
from backend.app.admin.service.auth_service import auth_service
from backend.app.admin.utils.password_security import get_hash_password
from backend.app.membership.crud.crud_membership import user_membership_dao
from backend.app.membership.crud.crud_plan import membership_plan_dao
from backend.app.membership.crud.crud_tier import membership_tier_dao
from backend.app.membership.model.membership import UserMembership
from backend.app.membership.service.membership_service import membership_service
from backend.app.question_bank.service.user_account_service import user_account_service
from backend.common.exception import errors
from backend.common.log import log
from backend.utils.timezone import timezone


class ActivateService:
    """订单号激活与登录服务"""

    ORDER_SOURCE = 'actcode_order'
    ORDER_SOURCE_PREFIX = 'actcode_order:'
    ORDER_REGISTER_CHANNEL = 'agiso_order'
    ORDER_USERNAME_PREFIX = 'ag'

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
    def _resolve_plan_id(batch: ActcodeBatch) -> int | None:
        """
        从批次配置解析会员计划 ID

        :param batch: 激活码批次
        :return:
        """
        reward_data = batch.reward_data or {}
        plan_id = reward_data.get('membership_plan_id')
        if plan_id is None:
            return None

        try:
            plan_value = int(plan_id)
        except (TypeError, ValueError) as exc:
            raise errors.RequestError(msg='批次 reward_data.membership_plan_id 配置错误') from exc

        if plan_value <= 0:
            raise errors.RequestError(msg='批次 reward_data.membership_plan_id 配置错误')
        return plan_value

    @classmethod
    def _safe_resolve_plan_id(cls, batch: ActcodeBatch) -> int | None:
        """
        宽容获取会员计划 ID

        :param batch: 激活码批次
        :return:
        """
        try:
            return cls._resolve_plan_id(batch)
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
        password = get_hash_password(secrets.token_urlsafe(18), salt)
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
    ) -> UserMembership:
        """
        根据订单号发放会员

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param batch: 激活码批次
        :param order_no: 订单号
        :return:
        """
        plan_id = cls._resolve_plan_id(batch)
        if plan_id is None:
            raise errors.RequestError(msg='该订单号未配置会员计划')

        return await membership_service.grant_by_plan(
            db,
            user_id=user_id,
            plan_id=plan_id,
            source=cls.ORDER_SOURCE,
            source_key=cls._build_source_key(order_no),
            op_type='open',
            source_detail=f'order_no={order_no}',
            remark='订单号激活'
        )

    @classmethod
    async def _get_membership_snapshot(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        batch: ActcodeBatch,
        order_no: str,
    ) -> UserMembership | None:
        """
        获取订单号对应的会员快照

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param batch: 激活码批次
        :param order_no: 订单号
        :return:
        """
        plan_id = cls._resolve_plan_id(batch)
        if plan_id is None:
            return None

        plan = await membership_plan_dao.select_model(db, plan_id)
        if not plan:
            return None

        tier = await membership_tier_dao.select_model(db, plan.tier_id)
        if not tier:
            return None

        membership = await user_membership_dao.get_by_user_and_family(db, user_id, tier.family_code)
        if membership:
            return membership

        return await user_membership_dao.select_model_by_column(
            db,
            user_id__eq=user_id,
            source__eq=cls.ORDER_SOURCE,
            source_key__eq=cls._build_source_key(order_no),
        )

    @classmethod
    async def _consume_for_user(
        cls,
        db: AsyncSession,
        *,
        actcode: Actcode,
        batch: ActcodeBatch,
        usage: ActcodeUsage | None,
        user: User,
    ) -> tuple[bool, UserMembership | None]:
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

            membership = await cls._get_membership_snapshot(db, user_id=user.id, batch=batch, order_no=actcode.code)
            return False, membership

        cls._ensure_order_consumable(actcode=actcode, batch=batch, usage=usage)
        membership = await cls._grant_membership(db, user_id=user.id, batch=batch, order_no=actcode.code)
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
        return True, membership

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
        just_activated, membership = await cls._consume_for_user(
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
            membership_plan_id=cls._safe_resolve_plan_id(batch),
            tier_code=membership.tier_code if membership else None,
            tier_name=membership.tier_name if membership else None,
            membership_valid_to=membership.valid_to if membership else None,
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

        just_activated, membership = await cls._consume_for_user(
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
            membership_plan_id=cls._safe_resolve_plan_id(batch),
            tier_code=membership.tier_code if membership else None,
            tier_name=membership.tier_name if membership else None,
            membership_valid_to=membership.valid_to if membership else None,
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
                membership_plan_id=None,
                message=exc.msg,
            )

        bound_user = await cls._get_bound_user(db, usage)
        try:
            plan_id = cls._resolve_plan_id(batch)
        except errors.BaseError as exc:
            return OrderCodeVerifyResult(
                valid=False,
                order_no=actcode.code,
                is_bound=bound_user is not None,
                can_login=False,
                username=bound_user.username if bound_user else None,
                membership_plan_id=None,
                message=exc.msg,
            )

        if bound_user:
            return OrderCodeVerifyResult(
                valid=True,
                order_no=actcode.code,
                is_bound=True,
                can_login=True,
                username=bound_user.username,
                membership_plan_id=plan_id,
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
                membership_plan_id=plan_id,
                message=exc.msg,
            )

        return OrderCodeVerifyResult(
            valid=True,
            order_no=actcode.code,
            is_bound=False,
            can_login=True,
            username=None,
            membership_plan_id=plan_id,
            message='订单号有效，可直接登录或绑定当前账号',
        )


activate_service: ActivateService = ActivateService()
