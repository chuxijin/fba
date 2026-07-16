#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.mydrive.schema.relationship import GetMyDriveRelationshipDetail, GetMyDriveRelationshipShareDetail
from backend.app.mydrive.service.relationship_service import mydrive_relationship_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/accounts/{account_id}/relationships/{space_type}', summary='获取百度好友或群组', dependencies=[DependsJwtAuth])
async def get_mydrive_relationships(
    request: Request,
    db: CurrentSession,
    account_id: Annotated[int, Path(description='百度账户 ID')],
    space_type: Annotated[str, Path(description='关系类型：friend 或 group')],
    offset: Annotated[int, Query(description='偏移量', ge=0)] = 0,
    limit: Annotated[int, Query(description='单页数量', ge=1, le=100)] = 50,
) -> ResponseSchemaModel[list[GetMyDriveRelationshipDetail]]:
    """获取当前百度账户的好友或群组。"""
    relationships = await mydrive_relationship_service.list_relationships(
        db,
        account_id=account_id,
        owner_id=request.user.id,
        space_type=space_type,
        offset=offset,
        limit=limit,
    )
    return response_base.success(data=relationships)


@router.get('/accounts/{account_id}/relationships/{space_type}/{source_id}/shares', summary='获取百度关系分享', dependencies=[DependsJwtAuth])
async def get_mydrive_relationship_shares(
    request: Request,
    db: CurrentSession,
    account_id: Annotated[int, Path(description='百度账户 ID')],
    space_type: Annotated[str, Path(description='关系类型：friend 或 group')],
    source_id: Annotated[str, Path(description='好友 UK 或群组 ID')],
    refresh: Annotated[bool, Query(description='预留刷新参数')] = False,
) -> ResponseSchemaModel[list[GetMyDriveRelationshipShareDetail]]:
    """获取好友或群组的可挂载分享。"""
    _ = refresh
    shares = await mydrive_relationship_service.list_shares(
        db,
        account_id=account_id,
        owner_id=request.user.id,
        space_type=space_type,
        source_id=source_id,
    )
    return response_base.success(data=shares)
