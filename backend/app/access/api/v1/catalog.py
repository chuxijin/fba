#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.access.schema.catalog import GetSubscriptionCatalog
from backend.app.access.service.catalog_service import subscription_catalog_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('', summary='获取公开在售套餐与权益对比')
async def get_subscription_catalog(db: CurrentSession) -> ResponseSchemaModel[GetSubscriptionCatalog]:
    data = await subscription_catalog_service.get_catalog(db=db)
    return response_base.success(data=data)
