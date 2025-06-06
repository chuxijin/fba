#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.coulddrive.api.v1.template.rule_template import router as rule_template_router

router = APIRouter(prefix='/template')

router.include_router(rule_template_router, tags=['规则模板管理'])
