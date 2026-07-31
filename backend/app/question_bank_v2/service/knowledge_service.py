from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.cache.knowledge_cache import points_tree_cache
from backend.app.question_bank_v2.crud.crud_bank import bank_revision_dao
from backend.app.question_bank_v2.crud.crud_knowledge import knowledge_point_dao, knowledge_system_dao
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint, QbKnowledgeSystem
from backend.app.question_bank_v2.schema.knowledge import (
    CreateKnowledgePointParam,
    CreateKnowledgeSystemParam,
    GetKnowledgePointNode,
    GetKnowledgePointTreeNode,
    GetKnowledgePointTreeResult,
    GetKnowledgeSystemListItem,
    GetKnowledgeTreeDetail,
    UpdateKnowledgePointParam,
    UpdateKnowledgeSystemParam,
)
from backend.app.question_bank_v2.service.access_service import bank_access_service
from backend.common.exception import errors


class KnowledgeService:
    """知识体系、题量和用户学习进度服务类"""

    @staticmethod
    async def get_systems(*, db: AsyncSession) -> list[GetKnowledgeSystemListItem]:
        systems = await knowledge_system_dao.get_all(db)
        return [GetKnowledgeSystemListItem.model_validate(item) for item in systems]

    @staticmethod
    def get_systems_select() -> Select:
        return knowledge_system_dao.get_select()

    @staticmethod
    async def create_system(
        *, db: AsyncSession, obj: CreateKnowledgeSystemParam, user_id: int
    ) -> GetKnowledgeSystemListItem:
        system = QbKnowledgeSystem(created_by=user_id, **obj.model_dump())
        db.add(system)
        await db.flush()
        return GetKnowledgeSystemListItem.model_validate(system)

    @staticmethod
    async def update_system(
        *, db: AsyncSession, system_id: int, obj: UpdateKnowledgeSystemParam, user_id: int
    ) -> GetKnowledgeSystemListItem:
        system = await db.get(QbKnowledgeSystem, system_id)
        if system is None or system.deleted:
            raise errors.NotFoundError(msg='知识体系不存在')
        for key, value in obj.model_dump(exclude_unset=True).items():
            setattr(system, key, value)
        system.updated_by = user_id
        await db.flush()
        return GetKnowledgeSystemListItem.model_validate(system)

    @staticmethod
    async def create_point(
        *, db: AsyncSession, system_id: int, obj: CreateKnowledgePointParam, user_id: int
    ) -> GetKnowledgePointNode:
        system = await db.get(QbKnowledgeSystem, system_id)
        if system is None or system.deleted:
            raise errors.NotFoundError(msg='知识体系不存在')
        parent = None
        if obj.parent_id is not None:
            parent = await knowledge_point_dao.get(db, obj.parent_id)
            if parent is None or parent.system_id != system_id:
                raise errors.NotFoundError(msg='父知识点不存在')
        point = QbKnowledgePoint(
            system_id=system_id,
            created_by=user_id,
            depth=(parent.depth + 1) if parent else 0,
            path=None,
            **obj.model_dump(),
        )
        db.add(point)
        await db.flush()
        point.path = f'{parent.path}.{point.id}' if parent and parent.path else str(point.id)
        await db.flush()
        await KnowledgeService.invalidate_points_tree_cache(system_id)
        return GetKnowledgePointNode.model_validate(point)

    @staticmethod
    async def update_point(
        *, db: AsyncSession, point_id: int, obj: UpdateKnowledgePointParam, user_id: int
    ) -> GetKnowledgePointNode:
        point = await knowledge_point_dao.get(db, point_id)
        if point is None:
            raise errors.NotFoundError(msg='知识点不存在')
        data = obj.model_dump(exclude_unset=True)
        if 'parent_id' in data and data['parent_id'] != point.parent_id:
            raise errors.RequestError(msg='暂不支持移动知识点，请新建节点后调整题目标注')
        for key, value in data.items():
            setattr(point, key, value)
        point.updated_by = user_id
        await db.flush()
        await KnowledgeService.invalidate_points_tree_cache(point.system_id)
        return GetKnowledgePointNode.model_validate(point)

    @staticmethod
    async def delete_point(*, db: AsyncSession, point_id: int) -> None:
        point = await knowledge_point_dao.get(db, point_id)
        if point is None:
            return
        children = await knowledge_point_dao.get_all(db, point.system_id)
        if any(item.parent_id == point.id for item in children):
            raise errors.ConflictError(msg='知识点存在子节点，不能删除')
        await knowledge_point_dao.delete_model(db, point.id)
        await KnowledgeService.invalidate_points_tree_cache(point.system_id)

    @staticmethod
    async def ensure_point_ids(*, db: AsyncSession, point_ids: Sequence[int]) -> set[int]:
        normalized = set(point_ids)
        existing = await knowledge_point_dao.get_existing_ids(db, list(normalized))
        missing = normalized - existing
        if missing:
            raise errors.NotFoundError(msg=f'知识点不存在或所属体系未启用: {sorted(missing)}')
        return existing

    @staticmethod
    async def resolve_point_ids(
        *,
        db: AsyncSession,
        point_ids: Sequence[int],
        include_descendants: bool,
    ) -> set[int]:
        existing = await KnowledgeService.ensure_point_ids(db=db, point_ids=point_ids)
        if not include_descendants or not existing:
            return existing
        return await knowledge_point_dao.expand_descendant_ids(db, list(existing))

    @staticmethod
    def _ratio(numerator: int | Decimal, denominator: int) -> Decimal:
        if denominator <= 0:
            return Decimal('0.0000')
        return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal('0.0001'))

    @staticmethod
    def _build_tree(
        *,
        points: Sequence[Any],
        progress: dict[int, dict[str, Any]],
        root_id: int | None,
    ) -> list[GetKnowledgePointTreeNode]:
        point_by_id = {item.id: item for item in points}
        children_by_parent: dict[int | None, list[Any]] = {}
        for point in points:
            children_by_parent.setdefault(point.parent_id, []).append(point)
        for children in children_by_parent.values():
            children.sort(key=lambda item: (item.sort_order, item.id))

        def build(point: Any) -> GetKnowledgePointTreeNode:
            children = [build(child) for child in children_by_parent.get(point.id, [])]
            aggregate = progress.get(point.id, {})
            direct_questions = int(aggregate.get('direct_question_count') or 0)
            question_count = int(aggregate.get('question_count') or 0)
            answered_count = int(aggregate.get('answered_count') or 0)
            correct_count = int(aggregate.get('correct_count') or 0)
            mastered_count = int(aggregate.get('mastered_count') or 0)
            mastery_sum = Decimal(aggregate.get('mastery_sum') or 0)
            mastery_samples = int(aggregate.get('mastery_sample_count') or 0)
            node = GetKnowledgePointTreeNode(
                id=point.id,
                system_id=point.system_id,
                code=point.code,
                name=point.name,
                parent_id=point.parent_id,
                path=point.path,
                depth=point.depth,
                sort_order=point.sort_order,
                description=point.description,
                direct_question_count=direct_questions,
                question_count=question_count,
                answered_count=answered_count,
                correct_count=correct_count,
                mastered_count=mastered_count,
                correct_rate=KnowledgeService._ratio(correct_count, answered_count),
                mastery_score=KnowledgeService._ratio(mastery_sum, mastery_samples),
                children=children,
            )
            return node

        if root_id is not None:
            root = point_by_id.get(root_id)
            return [build(root)] if root is not None else []
        roots = [item for item in points if item.parent_id is None or item.parent_id not in point_by_id]
        roots.sort(key=lambda item: (item.sort_order, item.id))
        return [build(item) for item in roots]

    @staticmethod
    async def get_tree(
        *,
        db: AsyncSession,
        user_id: int,
        system_id: int,
        bank_id: int,
        root_id: int | None = None,
    ) -> GetKnowledgeTreeDetail:
        system = await knowledge_system_dao.get(db, system_id)
        if system is None:
            raise errors.NotFoundError(msg='知识体系不存在或未启用')
        bank, _ = await bank_access_service.ensure_bank_access(db=db, user_id=user_id, bank_id=bank_id)
        revision = await bank_revision_dao.get(db, bank.current_revision_id, bank_id=bank.id)
        if revision is None or revision.status != 'published':
            raise errors.NotFoundError(msg='题库当前发布版本不存在')

        points = await knowledge_point_dao.get_all(db, system.id)
        if root_id is not None and not any(item.id == root_id for item in points):
            raise errors.NotFoundError(msg='知识点不存在或不属于当前知识体系')
        progress = await knowledge_point_dao.get_progress(
            db,
            system_id=system.id,
            bank_revision_id=revision.id,
            user_id=user_id,
        )
        tree = KnowledgeService._build_tree(points=points, progress=progress, root_id=root_id)
        totals = progress.get(root_id or 0, {})
        return GetKnowledgeTreeDetail(
            system=GetKnowledgeSystemListItem.model_validate(system),
            bank_id=bank.id,
            bank_revision_id=revision.id,
            root_id=root_id,
            total_question_count=int(totals.get('question_count') or 0),
            total_answered_count=int(totals.get('answered_count') or 0),
            total_correct_count=int(totals.get('correct_count') or 0),
            points=tree,
        )

    @staticmethod
    async def get_point_tree(
        *,
        db: AsyncSession,
        user_id: int,
        point_id: int,
        bank_id: int,
    ) -> GetKnowledgeTreeDetail:
        point = await knowledge_point_dao.get(db, point_id)
        if point is None:
            raise errors.NotFoundError(msg='知识点不存在')
        return await KnowledgeService.get_tree(
            db=db,
            user_id=user_id,
            system_id=point.system_id,
            bank_id=bank_id,
            root_id=point.id,
        )

    @staticmethod
    def _build_pure_tree(
        *,
        points: Sequence[Any],
        root_id: int | None,
    ) -> list[GetKnowledgePointNode]:
        children_by_parent: dict[int | None, list[Any]] = {}
        for point in points:
            children_by_parent.setdefault(point.parent_id, []).append(point)
        for children in children_by_parent.values():
            children.sort(key=lambda item: (item.sort_order, item.id))

        def build(point: Any) -> GetKnowledgePointNode:
            children = [build(child) for child in children_by_parent.get(point.id, [])]
            return GetKnowledgePointNode(
                id=point.id,
                system_id=point.system_id,
                code=point.code,
                name=point.name,
                parent_id=point.parent_id,
                path=point.path,
                depth=point.depth,
                sort_order=point.sort_order,
                description=point.description,
                children=children,
            )

        if root_id is not None:
            point_by_id = {item.id: item for item in points}
            root = point_by_id.get(root_id)
            return [build(root)] if root is not None else []
        roots = [item for item in points if item.parent_id is None or item.parent_id not in {p.id for p in points}]
        roots.sort(key=lambda item: (item.sort_order, item.id))
        return [build(item) for item in roots]

    @staticmethod
    async def get_points_tree(
        *,
        db: AsyncSession,
        system_id: int,
    ) -> GetKnowledgePointTreeResult:
        async def factory() -> GetKnowledgePointTreeResult | None:
            system = await knowledge_system_dao.get(db, system_id)
            if system is None:
                raise errors.NotFoundError(msg='知识体系不存在或未启用')
            points = await knowledge_point_dao.get_all(db, system.id)
            tree = KnowledgeService._build_pure_tree(points=points, root_id=None)
            return GetKnowledgePointTreeResult(
                system=GetKnowledgeSystemListItem.model_validate(system),
                points=tree,
            )

        return await points_tree_cache.get_or_set(system_id, factory=factory)

    @staticmethod
    async def invalidate_points_tree_cache(system_id: int) -> None:
        await points_tree_cache.invalidate(system_id)


knowledge_service: KnowledgeService = KnowledgeService()
