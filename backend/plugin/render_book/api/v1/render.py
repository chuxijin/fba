#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ipaddress

from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import anyio

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse

from backend.app.question_bank.service.membership_service import membership_service
from backend.common.exception import errors
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.plugin.render_book.schema.payload import RenderDocumentPayload
from backend.plugin.render_book.schema.render import (
    RenderArtifactKind,
    RenderFileKind,
    RenderJobCreate,
    RenderJobListParams,
    RenderJobRead,
    RenderJobValidationResult,
    RenderTemplateDetail,
    RenderTemplatePresetCreate,
    RenderTemplatePresetRead,
    RenderTemplatePresetUpdate,
    RenderTemplatePreviewRequest,
    RenderTemplatePreviewResponse,
    RenderTemplateSummary,
    RenderVariant,
)
from backend.plugin.render_book.service.preset_service import preset_service
from backend.plugin.render_book.service.quota_service import render_book_quota_service
from backend.plugin.render_book.service.render_service import render_service

router = APIRouter()

_INTERNAL_METADATA_KEYS = {
    'executor_mode',
    'executor_url',
    'user_id',
}


def _is_internal_url(value: str | None) -> bool:
    if not value:
        return False

    parsed = urlparse(value)
    hostname = parsed.hostname or ''
    if hostname in {'127.0.0.1', 'localhost'}:
        return True

    try:
        return ipaddress.ip_address(hostname).is_unspecified
    except ValueError:
        return False


def _is_public_url(value: str | None) -> bool:
    if not value:
        return False

    parsed = urlparse(value)
    return parsed.scheme in {'http', 'https'} and not _is_internal_url(value)


def _sanitize_render_job_for_client(job: RenderJobRead) -> RenderJobRead:
    record = job.model_copy(deep=True)
    metadata = dict(record.metadata or {})
    for key in _INTERNAL_METADATA_KEYS:
        metadata.pop(key, None)

    preview_urls = metadata.get('preview_urls')
    if isinstance(preview_urls, list):
        public_preview_urls = [url for url in preview_urls if isinstance(url, str) and _is_public_url(url)]
        if public_preview_urls:
            metadata['preview_urls'] = public_preview_urls
        else:
            metadata.pop('preview_urls', None)

    record.metadata = metadata
    if record.output_path and not _is_public_url(record.output_path):
        record.output_path = None

    for file_record in record.files:
        file_record.local_path = None
        if file_record.url and not _is_public_url(file_record.url):
            file_record.url = None

    return record


def _sanitize_render_page_for_client(page_data: dict) -> dict:
    page_data['items'] = [
        _sanitize_render_job_for_client(item) if isinstance(item, RenderJobRead) else item
        for item in page_data.get('items', [])
    ]
    return page_data


def _ensure_render_job_access(request: Request, job: RenderJobRead) -> None:
    current_user = getattr(request, 'user', None)
    if getattr(current_user, 'is_superuser', False):
        return

    owner_id = job.metadata.get('user_id')
    if owner_id is None:
        raise errors.AuthorizationError(msg='无权限访问未绑定用户的题本任务')

    current_user_id = getattr(current_user, 'id', None)
    if current_user_id is not None and str(owner_id) == str(current_user_id):
        return

    raise errors.AuthorizationError(msg='无权限访问其他用户的题本任务')


def _coerce_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _coerce_positive_int_list(value: object) -> list[int]:
    if isinstance(value, str):
        result: list[int] = []
        for item in value.split(','):
            parsed = _coerce_positive_int(item)
            if parsed is not None:
                result.append(parsed)
        return list(dict.fromkeys(result))

    if not isinstance(value, list):
        return []

    result: list[int] = []
    for item in value:
        parsed = _coerce_positive_int(item)
        if parsed is not None:
            result.append(parsed)
    return list(dict.fromkeys(result))


def _bind_payload_user(request: Request, payload: RenderJobCreate) -> int:
    current_user = getattr(request, 'user', None)
    current_user_id = _coerce_positive_int(getattr(current_user, 'id', None))
    if current_user_id is None:
        raise errors.AuthorizationError(msg='请先登录后再使用题本功能')

    if getattr(current_user, 'is_superuser', False):
        bound_user_id = _coerce_positive_int(payload.metadata.get('user_id')) or current_user_id
        payload.metadata['user_id'] = bound_user_id
        return bound_user_id

    payload.metadata['user_id'] = current_user_id
    return current_user_id


async def _ensure_render_payload_access(
    *,
    request: Request,
    db: CurrentSession,
    payload: RenderJobCreate,
) -> int:
    """
    归一化题本请求上下文

    :param request: 当前请求
    :param db: 数据库会话
    :param payload: 题本请求参数
    :return:
    """
    bound_user_id = _bind_payload_user(request, payload)

    filters = payload.filters
    bank_id = _coerce_positive_int(filters.get('bank_id'))
    chapter_id = _coerce_positive_int(filters.get('chapter_id'))
    if chapter_id is not None:
        filters['bank_id'] = await membership_service.resolve_bank_context_for_chapter(
            db=db,
            chapter_id=chapter_id,
            bank_id=bank_id,
        )
    return bound_user_id


async def _ensure_render_quota(*, db: CurrentSession, user_id: int) -> None:
    await render_book_quota_service.ensure_quota(db, user_id=user_id)


def _get_job_quota_user_id(job: RenderJobRead) -> int | None:
    return _coerce_positive_int(job.metadata.get('user_id'))


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


@router.get('/presets', summary='获取模板预设列表')
async def get_render_template_presets(
    db: CurrentSession,
    template_key: str | None = None,
    is_active: bool | None = None,
) -> ResponseSchemaModel[list[RenderTemplatePresetRead]]:
    presets = await preset_service.list_presets(db=db, template_key=template_key, is_active=is_active)
    return response_base.success(data=presets)


@router.get('/presets/{preset_id}', summary='获取模板预设详情')
async def get_render_template_preset(
    preset_id: int,
    db: CurrentSession,
) -> ResponseSchemaModel[RenderTemplatePresetRead]:
    preset = await preset_service.get_preset(db=db, preset_id=preset_id)
    return response_base.success(data=preset)


@router.post('/presets', summary='创建模板预设')
async def create_render_template_preset(
    payload: RenderTemplatePresetCreate,
    db: CurrentSession,
) -> ResponseSchemaModel[RenderTemplatePresetRead]:
    preset = await preset_service.create_preset(db=db, payload=payload)
    return response_base.success(data=preset)


@router.put('/presets/{preset_id}', summary='更新模板预设')
async def update_render_template_preset(
    preset_id: int,
    payload: RenderTemplatePresetUpdate,
    db: CurrentSession,
) -> ResponseSchemaModel[RenderTemplatePresetRead]:
    preset = await preset_service.update_preset(db=db, preset_id=preset_id, payload=payload)
    return response_base.success(data=preset)


@router.delete('/presets/{preset_id}', summary='删除模板预设')
async def delete_render_template_preset(
    preset_id: int,
    db: CurrentSession,
) -> ResponseSchemaModel[None]:
    await preset_service.delete_preset(db=db, preset_id=preset_id)
    return response_base.success()


@router.post('/jobs/validate', summary='校验题本渲染参数')
async def validate_render_job(payload: RenderJobCreate) -> ResponseSchemaModel[RenderJobValidationResult]:
    result = await render_service.validate_job(payload)
    return response_base.success(data=result)


@router.post('/jobs/payload-preview', summary='预览题本标准化渲染数据', dependencies=[DependsJwtAuth])
async def preview_render_payload(
    request: Request,
    payload: RenderJobCreate,
    db: CurrentSession,
) -> ResponseSchemaModel[RenderDocumentPayload]:
    try:
        current_user_id = await _ensure_render_payload_access(request=request, db=db, payload=payload)
        await _ensure_render_quota(db=db, user_id=current_user_id)
        document = await render_service.preview_payload(db=db, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return response_base.success(data=document)


@router.post('/templates/preview', summary='生成模板预览 PDF', dependencies=[DependsJwtAuth])
async def preview_render_template_pdf(
    request: Request,
    payload: RenderTemplatePreviewRequest,
    db: CurrentSession,
) -> ResponseSchemaModel[RenderTemplatePreviewResponse]:
    try:
        current_user_id = await _ensure_render_payload_access(request=request, db=db, payload=payload)
        await _ensure_render_quota(db=db, user_id=current_user_id)
        preview = await render_service.preview_template_pdf(db=db, payload=payload)
        preview.job = _sanitize_render_job_for_client(preview.job)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return response_base.success(data=preview)


import asyncio

import httpx


async def _fetch_bing_image_url() -> str | None:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get('https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1')
            if resp.status_code == 200:
                data = resp.json()
                if 'images' in data and len(data['images']) > 0:
                    # 获取高质量基础图片并加上基础域名
                    return f'https://www.bing.com{data["images"][0]["url"]}'
    except Exception:
        pass
    return None


async def _fetch_hitokoto() -> str | None:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get('https://v1.hitokoto.cn/?c=k')
            if resp.status_code == 200:
                return resp.json().get('hitokoto')
    except Exception:
        pass
    return None


@router.post('/jobs', summary='创建题本渲染任务', dependencies=[DependsJwtAuth])
async def create_render_job(
    request: Request,
    payload: RenderJobCreate,
    db: CurrentSession,
) -> ResponseSchemaModel[RenderJobRead]:
    try:
        current_user_id = await _ensure_render_payload_access(request=request, db=db, payload=payload)
        await _ensure_render_quota(db=db, user_id=current_user_id)
        user = getattr(request, 'user', None)
        if 'practice_cover_username' not in payload.metadata:
            payload.metadata['practice_cover_username'] = getattr(user, 'nickname', None) or getattr(
                user, 'username', '编者'
            )
        if 'practice_cover_avatar' not in payload.metadata:
            avatar = getattr(user, 'avatar', '')
            payload.metadata['practice_cover_avatar'] = str(avatar) if avatar else ''

        if payload.template_key == 'practice':
            tasks = []
            if not payload.metadata.get('practice_cover_img'):
                tasks.append(_fetch_bing_image_url())
            else:
                tasks.append(asyncio.sleep(0))

            if not payload.metadata.get('practice_cover_motto'):
                tasks.append(_fetch_hitokoto())
            else:
                tasks.append(asyncio.sleep(0))

            results = await asyncio.gather(*tasks)
            if results and len(results) == 2:
                bing_url, motto = results[0], results[1]
                if bing_url:
                    payload.metadata['practice_cover_img'] = bing_url
                if motto:
                    payload.metadata['practice_cover_motto'] = motto

        job = await render_service.create_job(payload, db=db)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return response_base.success(data=_sanitize_render_job_for_client(job))


@router.get('/jobs', summary='分页查询题本渲染任务', dependencies=[DependsJwtAuth, DependsPagination])
async def list_render_jobs(
    request: Request,
    params: Annotated[RenderJobListParams, Depends()],
    db: CurrentSession,
) -> ResponseSchemaModel[PageData[RenderJobRead]]:
    # 非超级管理员：只能查看自己的任务，避免越权查询。
    current_user = getattr(request, 'user', None)
    if current_user and not current_user.is_superuser:
        if params.user_id is not None and params.user_id != current_user.id:
            raise errors.AuthorizationError(msg='无权限查看其他用户的题本任务')
        params.user_id = current_user.id
    page_data = await render_service.list_jobs(db=db, params=params)
    page_data = _sanitize_render_page_for_client(page_data)
    return response_base.success(data=page_data)


@router.post('/jobs/{job_id}/execute', summary='执行题本渲染任务', dependencies=[DependsJwtAuth])
async def execute_render_job(
    request: Request,
    job_id: str,
    db: CurrentSession,
    upload_to_oss: bool = True,
) -> ResponseSchemaModel[RenderJobRead]:
    existing_job = await render_service.get_job(job_id, db=db)
    if existing_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Render job '{job_id}' not found.",
        )
    _ensure_render_job_access(request, existing_job)
    quota_user_id = _get_job_quota_user_id(existing_job)
    if quota_user_id is not None:
        await _ensure_render_quota(db=db, user_id=quota_user_id)

    try:
        job = await render_service.execute_job(db=db, job_id=job_id, upload_to_oss=upload_to_oss)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return response_base.success(data=_sanitize_render_job_for_client(job))


@router.post('/jobs/{job_id}/dispatch', summary='后台触发题本渲染任务', dependencies=[DependsJwtAuth])
async def dispatch_render_job(
    request: Request,
    job_id: str,
    db: CurrentSession,
    upload_to_oss: bool = True,
) -> ResponseSchemaModel[RenderJobRead]:
    job = await render_service.get_job(job_id, db=db)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Render job '{job_id}' not found.",
        )
    _ensure_render_job_access(request, job)
    quota_user_id = _get_job_quota_user_id(job)
    if quota_user_id is not None:
        await _ensure_render_quota(db=db, user_id=quota_user_id)
    job = await render_service.mark_job_running(db=db, job_id=job_id)
    await db.commit()
    await render_service.dispatch_job(job_id=job_id, upload_to_oss=upload_to_oss)
    return response_base.success(data=_sanitize_render_job_for_client(job))


@router.get('/jobs/{job_id}', summary='查询题本渲染任务', dependencies=[DependsJwtAuth])
async def get_render_job(
    request: Request,
    job_id: str,
    db: CurrentSession,
) -> ResponseSchemaModel[RenderJobRead]:
    job = await render_service.get_job(job_id, db=db)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Render job '{job_id}' not found.",
        )
    _ensure_render_job_access(request, job)
    return response_base.success(data=_sanitize_render_job_for_client(job))


@router.delete('/jobs/{job_id}', summary='删除题本渲染任务（软删除）', dependencies=[DependsJwtAuth])
async def delete_render_job(
    request: Request,
    job_id: str,
    db: CurrentSession,
) -> ResponseSchemaModel[None]:
    job = await render_service.get_job(job_id, db=db)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Render job '{job_id}' not found.",
        )
    _ensure_render_job_access(request, job)
    await render_service.soft_delete_job(db=db, job_id=job_id)
    await db.commit()
    return response_base.success()


@router.get('/jobs/{job_id}/files/{file_kind}', summary='下载题本正式文件', dependencies=[DependsJwtAuth])
async def download_render_job_file(
    request: Request,
    job_id: str,
    file_kind: RenderFileKind,
    db: CurrentSession,
    render_variant: Annotated[RenderVariant | None, Query(description='指定渲染变体')] = None,
    inline: Annotated[bool, Query(description='是否以内联方式打开')] = False,
    prefer_url: Annotated[bool, Query(description='若存在 OSS 地址，是否优先跳转到 OSS')] = False,
):
    job = await render_service.get_job(job_id, db=db)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Render job '{job_id}' not found.",
        )
    _ensure_render_job_access(request, job)

    try:
        file_record = await render_service.get_job_file(
            db=db,
            job_id=job_id,
            file_kind=file_kind,
            render_variant=render_variant,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if prefer_url and file_record.url:
        return RedirectResponse(url=file_record.url, status_code=status.HTTP_302_FOUND)

    file_path = Path(file_record.local_path or '')
    async_file_path = anyio.Path(file_path)
    if not await async_file_path.exists() or not await async_file_path.is_file():
        if file_record.url:
            return RedirectResponse(url=file_record.url, status_code=status.HTTP_302_FOUND)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='文件不存在，请重新执行渲染任务。')

    return FileResponse(
        path=file_path,
        media_type=file_record.content_type or 'application/pdf',
        filename=file_record.filename,
        content_disposition_type='inline' if inline else 'attachment',
    )


@router.get(
    '/jobs/{job_id}/artifacts/{render_variant}/{artifact_kind}',
    summary='获取渲染执行产物',
    dependencies=[DependsJwtAuth],
)
async def get_render_job_artifact(
    request: Request,
    job_id: str,
    render_variant: RenderVariant,
    artifact_kind: RenderArtifactKind,
    db: CurrentSession,
):
    job = await render_service.get_job(job_id, db=db)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Render job '{job_id}' not found.",
        )
    _ensure_render_job_access(request, job)

    artifact_path = await render_service.get_job_artifact_path(
        db=db,
        job_id=job_id,
        render_variant=render_variant,
        artifact_kind=artifact_kind,
    )
    media_type = 'application/pdf' if artifact_kind == 'pdf' else 'text/plain; charset=utf-8'
    return FileResponse(
        path=artifact_path,
        media_type=media_type,
        filename=artifact_path.name,
        content_disposition_type='attachment',
    )


@router.get('/jobs/{job_id}/preview.pdf', summary='获取题本预览 PDF', dependencies=[DependsJwtAuth])
async def get_render_job_preview_pdf(
    request: Request,
    job_id: str,
    db: CurrentSession,
    render_variant: Annotated[RenderVariant | None, Query(description='指定预览渲染变体')] = None,
    prefer_url: Annotated[bool, Query(description='若存在 OSS 地址，是否优先跳转到 OSS')] = False,
):
    job = await render_service.get_job(job_id, db=db)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Render job '{job_id}' not found.",
        )
    _ensure_render_job_access(request, job)

    try:
        file_record = await render_service.get_preview_pdf_file(
            db=db,
            job_id=job_id,
            render_variant=render_variant,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if prefer_url and file_record.url:
        return RedirectResponse(url=file_record.url, status_code=status.HTTP_302_FOUND)

    file_path = Path(file_record.local_path or '')
    async_file_path = anyio.Path(file_path)
    if not await async_file_path.exists() or not await async_file_path.is_file():
        if file_record.url:
            return RedirectResponse(url=file_record.url, status_code=status.HTTP_302_FOUND)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='预览 PDF 文件不存在，请重新生成预览。')

    return FileResponse(
        path=file_path,
        media_type=file_record.content_type or 'application/pdf',
        filename=file_record.filename,
        content_disposition_type='inline',
    )
