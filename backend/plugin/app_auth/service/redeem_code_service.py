#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import Request

from backend.common.exception import errors
from backend.common.security.jwt import superuser_verify
from backend.database.db import async_db_session
from backend.plugin.app_auth.crud import application_dao, redeem_code_dao
from backend.plugin.app_auth.model import AppRedeemCode
from backend.plugin.app_auth.schema.card_key import BatchCreateRedeemCodeWithGeneration
from backend.plugin.app_auth.schema.redeem_code import BatchCreateRedeemCodeParam, CreateRedeemCodeParam
from backend.plugin.app_auth.service.card_key_service import card_key_service


class RedeemCodeService:
    """兑换码服务类"""

    @staticmethod
    async def create(*, request: Request, obj: CreateRedeemCodeParam, code: str) -> AppRedeemCode:
        """
        创建兑换码

        :param request: FastAPI 请求对象
        :param obj: 创建参数
        :param code: 兑换码
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            # 检查应用是否存在
            app = await application_dao.get(db, obj.application_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')
            
            # 检查兑换码是否已存在
            existing_code = await redeem_code_dao.get_by_code(db, code)
            if existing_code:
                raise errors.ForbiddenError(msg='兑换码已存在')
            
            return await redeem_code_dao.create(db, obj, code)

    @staticmethod
    async def batch_create(*, obj: BatchCreateRedeemCodeParam) -> list[AppRedeemCode]:
        """
        批量生成并创建兑换码

        :param obj: 批量创建参数
        :return:
        """
        async with async_db_session.begin() as db:
            # 检查应用是否存在
            app = await application_dao.get(db, obj.application_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')
            
            # 生成兑换码
            generated_codes = card_key_service.generate_card_keys(obj.generation_params)
            
            # 检查生成的兑换码是否有重复
            for code in generated_codes:
                existing_code = await redeem_code_dao.get_by_code(db, code)
                if existing_code:
                    raise errors.ForbiddenError(msg=f'兑换码 {code} 已存在，请重新生成')
            
            # 批量创建兑换码
            created_codes = []
            for code in generated_codes:
                code_param = CreateRedeemCodeParam(
                    application_id=obj.application_id,
                    batch_no=obj.batch_no,
                    duration_days=obj.duration_days,
                    max_devices=obj.max_devices,
                    remark=obj.remark
                )
                created_code = await redeem_code_dao.create(db, code_param, code)
                created_codes.append(created_code)
            
            return created_codes

    @staticmethod
    async def batch_create_with_generation(*, request: Request, obj: BatchCreateRedeemCodeWithGeneration) -> list[AppRedeemCode]:
        """
        批量生成并创建兑换码

        :param request: FastAPI 请求对象
        :param obj: 批量创建参数
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            # 检查应用是否存在
            app = await application_dao.get(db, obj.application_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')
            
            # 生成兑换码
            generated_codes = card_key_service.generate_card_keys(obj.generation_params)
            
            # 检查生成的兑换码是否有重复
            for code in generated_codes:
                existing_code = await redeem_code_dao.get_by_code(db, code)
                if existing_code:
                    raise errors.ForbiddenError(msg=f'兑换码 {code} 已存在，请重新生成')
            
            # 批量创建兑换码
            created_codes = []
            for code in generated_codes:
                code_param = CreateRedeemCodeParam(
                    application_id=obj.application_id,
                    batch_no=obj.batch_no,
                    duration_days=obj.duration_days,
                    max_devices=obj.max_devices,
                    remark=obj.remark
                )
                created_code = await redeem_code_dao.create(db, code_param, code)
                created_codes.append(created_code)
            
            return created_codes

    @staticmethod
    async def delete(*, request: Request, code_id: int) -> int:
        """
        删除兑换码

        :param request: FastAPI 请求对象
        :param code_id: 兑换码 ID
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            code = await redeem_code_dao.get(db, code_id)
            if not code:
                raise errors.NotFoundError(msg='兑换码不存在')
            
            if code.is_used:
                raise errors.ForbiddenError(msg='已使用的兑换码不能删除')
            
            return await redeem_code_dao.delete(db, code_id)

    @staticmethod
    async def get(code_id: int) -> AppRedeemCode:
        """
        获取兑换码详情

        :param code_id: 兑换码 ID
        :return:
        """
        async with async_db_session() as db:
            code = await redeem_code_dao.get(db, code_id)
            if not code:
                raise errors.NotFoundError(msg='兑换码不存在')
            return code

    @staticmethod
    async def get_list(application_id: int = None, batch_no: str = None, 
                      is_used: bool = None) -> list[AppRedeemCode]:
        """获取兑换码列表"""
        async with async_db_session() as db:
            return await redeem_code_dao.get_list(
                db, application_id=application_id, batch_no=batch_no, is_used=is_used
            )

    @staticmethod
    def get_select(application_id: int = None, batch_no: str = None, is_used: bool = None):
        """
        获取兑换码查询语句用于分页

        :param application_id: 应用 ID
        :param batch_no: 批次号
        :param is_used: 是否已使用
        :return:
        """
        return redeem_code_dao.get_select(
            application_id=application_id, batch_no=batch_no, is_used=is_used
        )


redeem_code_service = RedeemCodeService()