from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request

from backend.app.question_bank_v2.schema.autolabel import (
    AutolabelParam,
    AutolabelResult,
    CandidatePointItem,
    CandidatePointList,
    ChapterTreeGroup,
    ChatModelItem,
    DecisionModelItem,
    PreviewParam,
    PreviewResult,
)
from backend.app.question_bank_v2.service.ai_label_service import (
    _build_where,
    count_questions,
    fetch_bank_summary,
    fetch_candidate_points,
    fetch_chapter_tree,
    list_chat_models,
    list_decision_models,
    run_autolabel,
)
from backend.common.response.response_schema import ResponseBase, ResponseModel
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

response_base: ResponseBase = ResponseBase()

# ⚠️ **路径前缀约定**：本 router 在 `api/v1/__init__.py` 里以
# `include_router(autolabel_router, prefix='/autolabels')` 挂载，所以这里
# **一律只写前缀之后的部分**（`/notes`、`/candidates`、POST 用 `''`）。
# 早期版本有三个路由误写成 `/autolabels/notes`，最终路径叠成
# `/qbank-v2/autolabels/autolabels/notes` ⇒ 前端 404。别再带这个前缀。
#
# ⚠️⚠️ **返回格式约定**：前端 `defaultResponseInterceptor` 配的是
# `codeField:'code'` / `dataField:'data'` / `successCode:200`，且状态码 2xx 时若
# `responseData.code !== 200` 会**直接 throw**（连 200 的裸数组/裸对象都会被抛掉）。
# 所以本文件所有接口**必须**用 `response_base.success(data=...)` 包成
# `{"code":200,"msg":...,"data":...}`，不能裸返回 list/dict。
router = APIRouter(dependencies=[DependsJwtAuth])

ReadPerm = [Depends(RequestPermission('qbank_v2:autolabel:read')), DependsRBAC]
WritePerm = [Depends(RequestPermission('qbank_v2:autolabel:write')), DependsRBAC]


@router.get(
    '/decision-models',
    summary='获取可用的决策模型通道',
    dependencies=ReadPerm,
)
async def get_decision_models(db: CurrentSession) -> ResponseModel:
    """给页面的模型下拉用。API Key 不返回。"""
    rows = [DecisionModelItem(**row) for row in await list_decision_models(db)]
    return response_base.success(data=rows)


@router.get(
    '/chat-models',
    summary='获取可用的对话模型通道（主引擎=对话模型 / 兜底用）',
    dependencies=ReadPerm,
)
async def get_chat_models(db: CurrentSession) -> ResponseModel:
    """给页面的「对话模型」下拉用。API Key 不返回。

    ⚠️ 兜底引擎原来是 `order_by(AIModel.id.desc()).limit(1)` 静默挑一条 ——
    用户不知道自己到底用的哪个模型。这个接口让它变成页面上可显式选择。
    """
    rows = [ChatModelItem(**row) for row in await list_chat_models(db)]
    return response_base.success(data=rows)


@router.get(
    '/chapters',
    summary='获取题库章节树（带题量）',
    dependencies=ReadPerm,
)
async def get_chapters(
    db: CurrentSession,
    bank_ids: Annotated[list[int] | None, Query(description='限定题库；留空取全部')] = None,
) -> ResponseModel:
    """⚠️ **不是所有题库都有章节记录**（考研政治那 12 个题库一行都没有），
    页面上要同时提供「按题库勾选」才不漏。"""
    rows = [ChapterTreeGroup(**row) for row in await fetch_chapter_tree(db, bank_ids=bank_ids)]
    return response_base.success(data=rows)


@router.get(
    '/candidates',
    summary='预览候选知识点',
    dependencies=ReadPerm,
)
async def preview_candidates(
    db: CurrentSession,
    system_id: Annotated[int, Query(gt=0, description='知识体系 ID')],
    point_ids: Annotated[list[int] | None, Query(description='指定知识点；留空按 root/leaves 取')] = None,
    root_point_id: Annotated[int | None, Query(gt=0, description='限定子树')] = None,
    *,
    leaves_only: Annotated[bool, Query(description='只取叶子')] = True,
) -> ResponseModel:
    """返回候选知识点 + 它们的说明。

    **「说明」就是页面上维护的特征描述** —— 决策模型是直觉模型，判定质量靠这个字段，
    改完立即生效，不用重启也不用清缓存（它不走知识点树缓存）。
    """
    points = await fetch_candidate_points(
        db,
        system_id=system_id,
        point_ids=point_ids,
        root_point_id=root_point_id,
        leaves_only=leaves_only,
    )
    return response_base.success(
        data=CandidatePointList(
            points=[CandidatePointItem(**p) for p in points],
            total=len(points),
        )
    )


@router.post(
    '/preview',
    summary='标注前预览：只算命中数与题库分布，不调模型',
    dependencies=ReadPerm,
)
async def preview_autolabel(
    db: CurrentSession,
    params: Annotated[PreviewParam, Body()],
) -> ResponseModel:
    """零成本预览 —— 落库前先确认「这批题有多少、都是什么域的」。"""
    where, sql_params = _build_where(
        system_id=params.system_id,
        section_ids=params.section_ids,
        bank_ids=params.bank_ids,
        question_ids=params.question_ids,
        include_labeled=params.include_labeled,
        overwrite_manual=params.overwrite_manual,
    )
    return response_base.success(
        data=PreviewResult(
            total_matched=await count_questions(db, where=where, params=sql_params),
            bank_summary=await fetch_bank_summary(db, where=where, params=sql_params),
            payload={'where': where},
        )
    )


@router.post(
    '',
    summary='执行 AI 自动标注',
    dependencies=WritePerm,
)
async def create_autolabel(
    request: Request,
    db: CurrentSessionTransaction,
    params: Annotated[AutolabelParam, Body()],
) -> ResponseModel:
    """**同步执行**，跑完才返回。

    ⚠️ 单次上限 2000 题 —— 再多会 HTTP 超时，要跑更多请分批。
    `write=false` 是干跑（只统计不落库），建议先跑一次看统计再落库。
    低于阈值的题会被直接丢弃，不落库也不返回明细。
    """
    result = await run_autolabel(
        db,
        system_id=params.system_id,
        user_id=request.user.id,
        engine=params.engine,
        section_ids=params.section_ids,
        bank_ids=params.bank_ids,
        question_ids=params.question_ids,
        point_ids=params.point_ids,
        root_point_id=params.root_point_id,
        leaves_only=params.leaves_only,
        include_labeled=params.include_labeled,
        overwrite_manual=params.overwrite_manual,
        use_description=params.use_description,
        with_other=params.with_other,
        threshold=params.threshold,
        limit=params.limit,
        write=params.write,
        provider_id=params.provider_id,
        model_id=params.model_id,
        fallback_engine=params.fallback_engine,
        fallback_model_id=params.fallback_model_id,
        sleep=params.sleep,
    )
    result['truncated'] = result['total_matched'] > result['processed']
    return response_base.success(data=AutolabelResult(**result))


@router.get(
    '/notes',
    summary='引擎实测结论（前端提示文案）',
    dependencies=ReadPerm,
)
async def get_engine_notes() -> ResponseModel:
    """把几条实测结论直接吐给前端，避免把经验写死在页面里。"""
    return response_base.success(
        data={
            'jev': (
                '决策模型是 System 1 直觉模型，不做推理链。候选越少越准 —— '
                '建议先限定到某棵子树（如只跑数量关系），别把全体系的知识点都塞给它。'
            ),
            'confidence': (
                '置信度是分布集中度，不是正确率。题在两个类之间摇摆时它会掉到 0.5 附近，'
                '哪怕最终选对了 —— 别用它当准确率读。'
            ),
            'description': (
                '候选的「说明」字段就是特征描述，在「知识体系 → 知识点编辑」里改即可立即生效。'
                '实测：每条只说一件事、类与类之间不重叠才有好效果；写得越宽反而越差。'
            ),
            'manual': '人工标注（source=manual）默认受保护，不会被覆盖 —— 要覆盖得单独勾选。',
        }
    )
