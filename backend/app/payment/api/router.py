#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.payment.api.v1 import group_buy, my_orders, pay
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(pay.router, prefix='/payment', tags=['支付管理'])
v1.include_router(my_orders.router, prefix='/payment', tags=['我的订单'])
v1.include_router(group_buy.router, prefix='/payment', tags=['订阅拼团'])
