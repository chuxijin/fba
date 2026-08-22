from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_bank_v2.schema.knowledge import (
    CreateKnowledgePointParam,
    CreateKnowledgeSystemParam,
    GetKnowledgeMasteryRadar,
    GetKnowledgePointTreeResult,
    GetKnowledgeSystemListItem,
    GetKnowledgeTreeDetail,
    UpdateKnowledgePointParam,
    UpdateKnowledgeSystemParam,
)
from backend.app.question_bank_v2.service.knowledge_service import knowledge_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


@router.get(
    '/knowledge-systems',
    summary='获取可用知识体系',
    name='qbank_v2_get_knowledge_systems',
    dependencies=[DependsPagination],
)
async def get_knowledge_systems(
    request: Request,
    db: CurrentSession,
    domain_category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID；默认取用户当前领域')] = None,
    code: Annotated[str | None, Query(max_length=64, description='科目编码，如 xingce')] = None,
) -> ResponseSchemaModel[PageData[GetKnowledgeSystemListItem]]:
    """获取可用知识体系（分页）；始终限定在单一领域内，避免跨领域串体系"""
    resolved_domain_id = await knowledge_service.resolve_domain_category_id(
        db=db,
        user_id=request.user.id,
        domain_category_id=domain_category_id,
    )
    stmt = knowledge_service.get_systems_select(domain_category_id=resolved_domain_id, code=code)
    page_data = await paging_data(db, stmt, GetKnowledgeSystemListItem)
    return response_base.success(data=page_data)


@router.post(
    '/knowledge-systems',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def create_knowledge_system(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateKnowledgeSystemParam,
) -> ResponseSchemaModel[GetKnowledgeSystemListItem]:
    data = await knowledge_service.create_system(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/knowledge-systems/{system_id}',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def update_knowledge_system(
    request: Request,
    db: CurrentSessionTransaction,
    system_id: int,
    obj: UpdateKnowledgeSystemParam,
) -> ResponseSchemaModel[GetKnowledgeSystemListItem]:
    data = await knowledge_service.update_system(db=db, system_id=system_id, obj=obj, user_id=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/knowledge-systems/{system_id}/tree',
    summary='获取知识点树与用户进度',
    name='qbank_v2_get_knowledge_tree',
)
async def get_knowledge_tree(
    request: Request,
    db: CurrentSession,
    system_id: Annotated[int, Path(gt=0, description='知识体系 ID')],
    bank_id: Annotated[int | None, Query(gt=0, description='题库稳定身份 ID；不传则跨全部可用题库聚合')] = None,
    root_id: Annotated[int | None, Query(gt=0, description='限定知识点根节点 ID')] = None,
) -> ResponseSchemaModel[GetKnowledgeTreeDetail]:
    data = await knowledge_service.get_tree(
        db=db,
        user_id=request.user.id,
        system_id=system_id,
        bank_id=bank_id,
        root_id=root_id,
    )
    return response_base.success(data=data)


@router.get(
    '/knowledge-systems/{system_id}/mastery/radar',
    summary='获取知识点掌握度雷达图',
    name='qbank_v2_get_knowledge_mastery_radar',
)
async def get_knowledge_mastery_radar(
    request: Request,
    db: CurrentSession,
    system_id: Annotated[int, Path(gt=0, description='知识体系 ID')],
    bank_id: Annotated[int | None, Query(gt=0, description='题库 ID；不传则跨题库聚合')] = None,
) -> ResponseSchemaModel[GetKnowledgeMasteryRadar]:
    """当前阶段默认由前端传入 default system_id，后续可开放用户版本选择。"""
    data = await knowledge_service.get_mastery_radar(
        db=db,
        user_id=request.user.id,
        system_id=system_id,
        bank_id=bank_id,
    )
    return response_base.success(data=data)


@router.get(
    '/knowledge-points/{point_id}',
    summary='获取知识点详情与后代进度',
    name='qbank_v2_get_knowledge_point',
)
async def get_knowledge_point(
    request: Request,
    db: CurrentSession,
    point_id: Annotated[int, Path(gt=0, description='知识点 ID')],
    bank_id: Annotated[int | None, Query(gt=0, description='题库稳定身份 ID；不传则跨全部可用题库聚合')] = None,
) -> ResponseSchemaModel[GetKnowledgeTreeDetail]:
    data = await knowledge_service.get_point_tree(
        db=db,
        user_id=request.user.id,
        point_id=point_id,
        bank_id=bank_id,
    )
    return response_base.success(data=data)


@router.get(
    '/knowledge-systems/{system_id}/points',
    summary='获取知识点纯树结构（无统计）',
    name='qbank_v2_get_points_tree',
)
async def get_knowledge_points_tree(
    db: CurrentSession,
    system_id: Annotated[int, Path(gt=0, description='知识体系 ID')],
) -> ResponseSchemaModel[GetKnowledgePointTreeResult]:
    data = await knowledge_service.get_points_tree(
        db=db,
        system_id=system_id,
    )
    return response_base.success(data=data)


@router.post(
    '/knowledge-systems/{system_id}/points',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def create_knowledge_point(
    request: Request,
    db: CurrentSessionTransaction,
    system_id: int,
    obj: CreateKnowledgePointParam,
) -> ResponseSchemaModel:
    data = await knowledge_service.create_point(db=db, system_id=system_id, obj=obj, user_id=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/knowledge-points/{point_id}',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def update_knowledge_point(
    request: Request,
    db: CurrentSessionTransaction,
    point_id: int,
    obj: UpdateKnowledgePointParam,
) -> ResponseSchemaModel:
    data = await knowledge_service.update_point(db=db, point_id=point_id, obj=obj, user_id=request.user.id)
    return response_base.success(data=data)


@router.delete(
    '/knowledge-points/{point_id}',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def delete_knowledge_point(db: CurrentSessionTransaction, point_id: int) -> ResponseSchemaModel:
    await knowledge_service.delete_point(db=db, point_id=point_id)
    return response_base.success()
