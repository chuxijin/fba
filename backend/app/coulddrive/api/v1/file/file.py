#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, Header
from fastapi.security import HTTPBasicCredentials
from fastapi_limiter.depends import RateLimiter
from starlette.background import BackgroundTasks

from backend.app.coulddrive.service.drivebase_service import drivebase_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth

router = APIRouter()

@router.get('/list', summary='获取文件列表', description='获取文件列表', dependencies=[DependsJwtAuth])
async def get_file_list(request: Request, response: Response, x_token: str = Header(...)) -> ResponseModel:
    await drivebase_service.get_file_list(request=request, response=response)
    return response_base.success()
