"""简历 API"""

from fastapi import APIRouter, Request

from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.plugin.oc.service.resume_service import resume_service
from backend.plugin.oc.schema.resume import SaveResumeParam, IdentifyFieldsParam, SelectorFillParam, ParsePdfParam


router = APIRouter()


@router.get('', summary='获取简历', dependencies=[DependsJwtAuth])
async def get_resume(
    request: Request,
    db: CurrentSession,
) -> ResponseModel:
    """获取当前用户的简历（加密数据）"""
    data = await resume_service.get(db, request.user.id)
    return response_base.success(data=data)


@router.post('', summary='保存简历', dependencies=[DependsJwtAuth])
async def save_resume(
    request: Request,
    db: CurrentSession,
    obj: SaveResumeParam,
) -> ResponseModel:
    """保存简历（加密数据）"""
    await resume_service.save(db, request.user.id, obj)
    return response_base.success()


@router.delete('', summary='删除简历', dependencies=[DependsJwtAuth])
async def delete_resume(
    request: Request,
    db: CurrentSession,
) -> ResponseModel:
    """删除当前用户的简历"""
    await resume_service.delete(db, request.user.id)
    return response_base.success()


@router.post('/identify', summary='AI 识别表单字段')
async def identify_fields(
    obj: IdentifyFieldsParam,
) -> ResponseModel:
    """
    使用 AI 识别表单字段类型
    公开接口，用于浏览器扩展调用
    """
    mappings = await resume_service.identify_fields(obj.fields)
    return response_base.success(data=mappings)


@router.get('/formatter', summary='获取 formatter 配置')
async def get_formatter() -> ResponseModel:
    """
    获取字段格式化配置
    公开接口，用于浏览器扩展调用
    """
    formatter = resume_service.get_formatter()
    return response_base.success(data=formatter)


@router.post('/selector_fill', summary='AI 选择下拉选项')
async def selector_fill(
    obj: SelectorFillParam,
) -> ResponseModel:
    """
    在下拉选项中选择最匹配的值

    1. 先使用本地 mapping 匹配
    2. 本地匹配失败，调用 AI 匹配

    公开接口，用于浏览器扩展调用
    """
    matched = await resume_service.selector_fill(obj)
    return response_base.success(data=matched)


@router.post('/parse_pdf', summary='AI 解析 PDF 简历')
async def parse_pdf(
    obj: ParsePdfParam,
) -> ResponseModel:
    """
    使用 AI 解析 PDF 简历文本

    前端提取 PDF 文本后发送到此接口，由后端调用 AI 解析
    公开接口，用于浏览器扩展调用
    """
    data = await resume_service.parse_pdf(obj.text)
    return response_base.success(data=data)
