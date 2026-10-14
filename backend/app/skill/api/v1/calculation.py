#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill 计算练习端点：OpenAuth 认证 + 会员闸门 + 复用 gongkao 计算服务与 render_book 导出"""

import re
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.gongkao.schema.calculation_practice import (
    AdvancedQuestion,
    BasicCalculationSession,
    CalculationSession,
    DataPracticeQuestion,
    FillBlankQuestion,
    GenerateAdvancedCalculationParam,
    GenerateBasicCalculationParam,
    GenerateDataPracticeParam,
    GenerateFillBlankParam,
)
from backend.app.gongkao.service.calculation_practice_service import calculation_practice_service
from backend.app.skill.service import ensure_skill_access
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSessionTransaction
from backend.plugin.openauth.dependencies import RequireOpenAuth
from backend.plugin.openauth.schema.authorization import GetOpenAuthCheckResult

router = APIRouter()

CalcIdentity = Annotated[GetOpenAuthCheckResult, Depends(RequireOpenAuth('skill:use'))]


@router.get('/calculation/catalog', summary='获取计算练习题型目录')
async def skill_get_calculation_catalog(
    db: CurrentSessionTransaction,
    identity: CalcIdentity,
) -> ResponseSchemaModel:
    await ensure_skill_access(db, user_id=identity.user_id)
    return response_base.success(data=calculation_practice_service.get_catalog())


@router.post('/calculation/basic/generate', summary='生成基础计算题单', response_model_exclude_none=True)
async def skill_generate_basic(
    db: CurrentSessionTransaction,
    identity: CalcIdentity,
    obj: GenerateBasicCalculationParam,
) -> ResponseSchemaModel[BasicCalculationSession]:
    await ensure_skill_access(db, user_id=identity.user_id)
    return response_base.success(data=calculation_practice_service.generate_basic(obj=obj))


@router.post('/calculation/fill-blank/generate', summary='生成资料分析填空与比较题单')
async def skill_generate_fill_blank(
    db: CurrentSessionTransaction,
    identity: CalcIdentity,
    obj: GenerateFillBlankParam,
) -> ResponseSchemaModel[CalculationSession[FillBlankQuestion]]:
    await ensure_skill_access(db, user_id=identity.user_id)
    return response_base.success(data=calculation_practice_service.generate_fill_blank(obj=obj))


@router.post('/calculation/data-practice/generate', summary='生成资料分析实战选择题单')
async def skill_generate_data_practice(
    db: CurrentSessionTransaction,
    identity: CalcIdentity,
    obj: GenerateDataPracticeParam,
) -> ResponseSchemaModel[CalculationSession[DataPracticeQuestion]]:
    await ensure_skill_access(db, user_id=identity.user_id)
    return response_base.success(data=calculation_practice_service.generate_data_practice(obj=obj))


@router.post('/calculation/advanced/generate', summary='生成进阶计算题单')
async def skill_generate_advanced(
    db: CurrentSessionTransaction,
    identity: CalcIdentity,
    obj: GenerateAdvancedCalculationParam,
) -> ResponseSchemaModel[CalculationSession[AdvancedQuestion]]:
    await ensure_skill_access(db, user_id=identity.user_id)
    return response_base.success(data=calculation_practice_service.generate_advanced(obj=obj))


# ============================================================================
# PDF 导出：按 seed 重生成同一份题单 → render_book basic_calculation 模板
# ============================================================================


class SkillCalcExportParam(BaseModel):
    """计算练习导出参数：与生成参数同构，服务端按 seed 确定性重生成后排版"""

    kind: Literal['basic', 'advanced'] = Field(description='题单类型（v1 支持基础计算与进阶速算）')
    params: dict = Field(default_factory=dict, description='原生成参数（应含 seed 以复现同一份题单）')
    title: str = Field(default='计算练习', max_length=200, description='题本标题')
    answer_layout: Literal['inline', 'appendix', 'none'] | None = Field(
        default=None, description='答案排版：随题/附录/不含答案'
    )


@router.post('/calculation/export', summary='导出计算练习题单为 PDF')
async def export_calculation(
    db: CurrentSessionTransaction,
    identity: CalcIdentity,
    obj: SkillCalcExportParam,
) -> ResponseSchemaModel:
    """
    skill 会员闸门 + render_book 导出配额双重校验后，
    同步渲染并返回下载路径。
    """
    from backend.common.exception import errors

    await ensure_skill_access(db, user_id=identity.user_id)

    questions = _regenerate_questions(obj)
    if not questions:
        raise errors.ValidationError(msg='未生成可导出的题目，请检查生成参数')

    from backend.plugin.render_book.schema.render import RenderJobCreate
    from backend.plugin.render_book.service.quota_service import render_book_quota_service
    from backend.plugin.render_book.service.render_service import render_service

    # render_book 导出配额（与站内 PDF 导出同一本账：免费试看 + 会员配额）
    await render_book_quota_service.ensure_quota(db, user_id=identity.user_id)

    payload = RenderJobCreate(
        template_key='basic_calculation',
        title=obj.title,
        book_kind='custom',
        answer_layout=None,  # basic_calculation 模板仅支持 questions_only，不置 answer_layout
        metadata={
            'source_type': 'skill_calculation',
            'user_id': identity.user_id,
            'questions': questions,
        },
    )
    try:
        job = await render_service.create_job(payload, db=db)
        job = await render_service.execute_job(db=db, job_id=job.job_id, upload_to_oss=False)
        await db.commit()
    except ValueError as exc:
        raise errors.ValidationError(msg=f'题本渲染失败: {exc}') from exc

    if job.status != 'succeeded':
        raise errors.ServerError(msg='题本渲染未成功完成，请稍后重试或减少题量')

    return response_base.success(
        data={
            'job_id': job.job_id,
            'title': obj.title,
            'question_count': len(questions),
            'download_path': f"{_api_prefix()}/skill/calculation/export/{job.job_id}/pdf",
        }
    )


@router.get('/calculation/export/{job_id}/pdf', summary='下载计算练习导出 PDF')
async def download_calculation_export_pdf(
    job_id: str,
    db: CurrentSessionTransaction,
    identity: CalcIdentity,
) -> FileResponse:
    """OpenAuth Bearer 下载本人导出的题本 PDF（文件由 render_book job 产物目录提供）"""
    from backend.common.exception import errors
    from backend.plugin.render_book.service.render_service import render_service

    job = await render_service.get_job(job_id, db=db)
    if job is None:
        raise errors.NotFoundError(msg='导出任务不存在')
    owner_id = job.metadata.get('user_id')
    if owner_id != identity.user_id:
        raise errors.ForbiddenError(msg='只能下载本人导出的题本')
    if job.status != 'succeeded':
        raise errors.NotFoundError(msg='题本尚未渲染完成或已失败，请重新导出')

    candidate = _local_artifact_pdf(job_id)
    if candidate is None or not candidate.is_file():
        raise errors.NotFoundError(msg='PDF 产物不存在或已清理，请重新导出')

    safe_title = re.sub(r'[\\/:*?"<>|\r\n]+', '_', str(job.title or 'calculation')).strip('_') or 'calculation'
    return FileResponse(
        candidate,
        media_type='application/pdf',
        filename=f'{safe_title}.pdf',
        content_disposition_type='attachment',
    )


def _local_artifact_pdf(job_id: str) -> Path | None:
    """定位 render_book 本地产物 PDF（复用 render_service.jobs_root 的根目录）"""
    from backend.plugin.render_book.service.render_service import render_service

    base = render_service.jobs_root / job_id / 'artifacts'
    if not base.is_dir():
        return None
    for name in (f'{job_id}_questions_only.pdf', f'{job_id}_combined.pdf', f'{job_id}_solution_only.pdf'):
        path = base / name
        if path.is_file():
            return path
    pdfs = sorted(base.glob('*.pdf'))
    return pdfs[0] if pdfs else None


def _api_prefix() -> str:
    from backend.core.conf import settings

    return settings.FASTAPI_API_V1_PATH


def _regenerate_questions(obj: SkillCalcExportParam) -> list[dict]:
    """按 kind 与 params（含 seed）重生成题单，归一化为 render_book 消费的题目结构"""
    kind, params = obj.kind, dict(obj.params or {})

    if kind == 'basic':
        param = GenerateBasicCalculationParam(**params)
        session = calculation_practice_service.generate_basic(obj=param)
        return [
            {
                'number': index,
                'expression': item.expression,
                'answer': item.answer,
                'section_title': '基础计算',
            }
            for index, item in enumerate(session.questions, start=1)
        ]

    param = GenerateAdvancedCalculationParam(**params)
    session = calculation_practice_service.generate_advanced(obj=param)
    return [
        {
            'number': index,
            'expression': f'{item.material} {item.question}'.strip(),
            'answer': item.answer_text,
            'section_title': '进阶速算',
        }
        for index, item in enumerate(session.questions, start=1)
    ]
