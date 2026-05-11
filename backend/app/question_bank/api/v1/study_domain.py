#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.question_bank.schema.study_domain import (
    StudyDomainOptionResponse,
    StudyDomainScopeResponse,
)
from backend.app.question_bank.service.study_domain_service import study_domain_service

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/options', summary='获取学习领域选项', name='qbank_get_study_domain_options', dependencies=[DependsJwtAuth])
async def get_study_domain_options() -> ResponseSchemaModel[list[StudyDomainOptionResponse]]:
    """获取学习领域选项"""
    data = await study_domain_service.get_options()
    return response_base.success(data=data)


@router.get('/scope', summary='获取学习领域分类范围', name='qbank_get_study_domain_scope')
async def get_study_domain_scope(
    db: CurrentSession,
    code: Annotated[str, Query(description='领域编码')],
) -> ResponseSchemaModel[StudyDomainScopeResponse]:
    """
    获取学习领域分类范围

    :param db: 数据库会话
    :param code: 领域编码
    :return:
    """
    data = await study_domain_service.get_scope(db=db, code=code)
    return response_base.success(data=data)
