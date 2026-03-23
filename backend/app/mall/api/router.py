#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.mall.api.v1 import group_buy, order, pay, product, team
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(product.router, prefix='/mall', tags=['商品管理'])
v1.include_router(group_buy.router, prefix='/mall', tags=['拼团活动'])
v1.include_router(team.router, prefix='/mall', tags=['拼团团队'])
v1.include_router(order.router, prefix='/mall', tags=['订单管理'])
v1.include_router(pay.router, prefix='/mall', tags=['支付管理'])
