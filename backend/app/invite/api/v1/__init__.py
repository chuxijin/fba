#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.invite.api.v1.invite_code import router as invite_code_router
from backend.app.invite.api.v1.invite_relation import router as invite_relation_router
from backend.app.invite.api.v1.reward_rule import router as reward_rule_router

v1 = APIRouter(prefix='/v1')

v1.include_router(invite_code_router)
v1.include_router(invite_relation_router)
v1.include_router(reward_rule_router)
