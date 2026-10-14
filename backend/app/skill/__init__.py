#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill 业务薄层

面向 OpenAuth 授权的 CLI / Agent 开放业务能力的适配层：
- 认证与 scope：backend/plugin/openauth 的 RequireOpenAuth
- 会员权益闸门：backend/app/access 决策引擎（resource_access_service）
- 业务逻辑：复用既有各业务 service，不重复实现
"""
