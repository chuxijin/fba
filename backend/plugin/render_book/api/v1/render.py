#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, status

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.plugin.render_book.schema.render import (
    RenderJobCreate,
    RenderJobRead,
    RenderJobValidationResult,
    RenderTemplateDetail,
    RenderTemplateSummary,
)
from backend.plugin.render_book.service.render_service import render_service

router = APIRouter()


@router.get('/templates', summary='获取题本模板列表')
async def get_render_templates() -> ResponseSchemaModel[list[RenderTemplateSummary]]:
    templates = await render_service.list_templates()
    return response_base.success(data=templates)


@router.get('/templates/{template_key}', summary='获取题本模板详情')
async def get_render_template(template_key: str) -> ResponseSchemaModel[RenderTemplateDetail]:
    template = await render_service.get_template(template_key)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Render template '{template_key}' not found.",
        )
    return response_base.success(data=template)


@router.post('/jobs/validate', summary='校验题本渲染参数')
async def validate_render_job(payload: RenderJobCreate) -> ResponseSchemaModel[RenderJobValidationResult]:
    result = await render_service.validate_job(payload)
    return response_base.success(data=result)


@router.post('/jobs', summary='创建题本渲染任务')
async def create_render_job(payload: RenderJobCreate) -> ResponseSchemaModel[RenderJobRead]:
    try:
        job = await render_service.create_job(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return response_base.success(data=job)


@router.get('/jobs/{job_id}', summary='查询题本渲染任务')
async def get_render_job(job_id: str) -> ResponseSchemaModel[RenderJobRead]:
    job = await render_service.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Render job '{job_id}' not found.",
        )
    return response_base.success(data=job)
