import math

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.cache.knowledge_cache import points_tree_cache
from backend.app.question_bank_v2.crud.crud_bank import bank_revision_dao
from backend.app.question_bank_v2.crud.crud_knowledge import knowledge_point_dao, knowledge_system_dao
from backend.app.question_bank_v2.crud.crud_mastery import user_knowledge_mastery_dao
from backend.app.question_bank_v2.crud.crud_preference import practice_preference_dao
from backend.app.question_bank_v2.model.bank import QbBankItem
from backend.app.question_bank_v2.model.knowledge import (
    QbKnowledgePoint,
    QbKnowledgeSystem,
    QbQuestionKnowledgePoint,
)
from backend.app.question_bank_v2.model.mastery import QbQuestionAttemptKnowledgePoint
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.schema.knowledge import (
    CreateKnowledgePointParam,
    CreateKnowledgeSystemParam,
    GetKnowledgeMasteryRadar,
    GetKnowledgePointNode,
    GetKnowledgePointTreeNode,
    GetKnowledgePointTreeResult,
    GetKnowledgeSystemListItem,
    GetKnowledgeTreeDetail,
    KnowledgeMasteryRadarNode,
    UpdateKnowledgePointParam,
    UpdateKnowledgeSystemParam,
)
from backend.app.question_bank_v2.service.access_service import bank_access_service
from backend.app.question_bank_v2.service.knowledge_mastery_service import KnowledgeMasteryService
from backend.common.exception import errors
from backend.utils.timezone import timezone


class KnowledgeService:
    """知识体系、题量和用户学习进度服务类"""

    @staticmethod
    async def get_systems(
        *,
        db: AsyncSession,
        domain_category_id: int | None = None,
        code: str | None = None,
    ) -> list[GetKnowledgeSystemListItem]:
        systems = await knowledge_system_dao.get_all(db, domain_category_id=domain_category_id, code=code)
        return [GetKnowledgeSystemListItem.model_validate(item) for item in systems]

    @staticmethod
    def get_systems_select(*, domain_category_id: int | None = None, code: str | None = None) -> Select:
        return knowledge_system_dao.get_select(domain_category_id=domain_category_id, code=code)

    @staticmethod
    async def resolve_domain_category_id(
        *,
        db: AsyncSession,
        user_id: int,
        domain_category_id: int | None = None,
    ) -> int:
        """解析当前领域分类 ID

        显式传入优先；否则取用户偏好里的 current_category_id（小程序切换领域时会写入领域根分类）。
        两者都没有时无法判断领域，直接报错而不是猜一个，避免跨领域串体系。
        """
        if domain_category_id is not None:
            return domain_category_id
        preference = await practice_preference_dao.get_by_user_id(db, user_id)
        current = getattr(preference, 'current_category_id', None)
        if not current:
            raise errors.RequestError(msg='未设置当前领域，请先选择学习领域')
        return int(current)

    @staticmethod
    async def resolve_system(
        *,
        db: AsyncSession,
        domain_category_id: int,
        code: str,
        system_id: int | None = None,
        user_id: int | None = None,
        preference_choice: dict[str, int] | None = None,
    ) -> QbKnowledgeSystem:
        """解析当前生效的知识体系

        解析顺序：显式 system_id → 用户偏好中该 code 的选择 → 该领域该 code 的 default 兜底。
        任一来源都必须归属传入的领域，否则视为无效并继续向下回落；全部落空时报错而非静默返回空结果。

        preference_choice 已读取时直接复用，避免批量解析多个科目时重复查询偏好。
        """
        if system_id is not None:
            system = await knowledge_system_dao.get(db, system_id)
            if system is None:
                raise errors.NotFoundError(msg='知识体系不存在或未启用')
            if system.domain_category_id != domain_category_id:
                raise errors.RequestError(msg='知识体系不属于当前领域')
            return system

        choice = preference_choice
        if choice is None and user_id is not None:
            preference = await practice_preference_dao.get_by_user_id(db, user_id)
            choice = getattr(preference, 'knowledge_system_choice', None) or {}
        chosen_id = (choice or {}).get(code)
        if chosen_id:
            chosen = await knowledge_system_dao.get(db, int(chosen_id))
            # 偏好可能指向已归档或跨领域的体系，此时静默回落 default 而不是报错
            if chosen is not None and chosen.domain_category_id == domain_category_id:
                return chosen

        default_id = await knowledge_system_dao.get_default_system_id(
            db,
            domain_category_id=domain_category_id,
            code=code,
        )
        if default_id is None:
            raise errors.NotFoundError(msg=f'当前领域未配置 {code} 的默认知识体系')
        default_system = await knowledge_system_dao.get(db, default_id)
        if default_system is None:
            raise errors.NotFoundError(msg=f'当前领域未配置 {code} 的默认知识体系')
        return default_system

    @staticmethod
    async def resolve_system_ids(
        *,
        db: AsyncSession,
        domain_category_id: int,
        system_id: int | None = None,
        user_id: int | None = None,
    ) -> list[int]:
        """解析当前领域下所有科目各自生效的体系 ID，用于跨科目的分布统计"""
        if system_id is not None:
            system = await knowledge_system_dao.get(db, system_id)
            if system is None:
                raise errors.NotFoundError(msg='知识体系不存在或未启用')
            if system.domain_category_id != domain_category_id:
                raise errors.RequestError(msg='知识体系不属于当前领域')
            return [system.id]
        codes = await knowledge_system_dao.get_codes(db, domain_category_id=domain_category_id)
        if not codes:
            raise errors.NotFoundError(msg='当前领域未配置知识体系')
        choice: dict[str, int] = {}
        if user_id is not None:
            preference = await practice_preference_dao.get_by_user_id(db, user_id)
            choice = getattr(preference, 'knowledge_system_choice', None) or {}
        resolved: list[int] = []
        for item in codes:
            system = await KnowledgeService.resolve_system(
                db=db,
                domain_category_id=domain_category_id,
                code=item,
                user_id=user_id,
                preference_choice=choice,
            )
            resolved.append(system.id)
        return resolved

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
    async def ensure_point_ids(
        *,
        db: AsyncSession,
        point_ids: Sequence[int],
        system_id: int | None = None,
    ) -> set[int]:
        normalized = set(point_ids)
        existing = await knowledge_point_dao.get_existing_ids(db, list(normalized))
        missing = normalized - existing
        if missing:
            raise errors.NotFoundError(msg=f'知识点不存在或所属体系未启用: {sorted(missing)}')
        if not existing:
            return existing
        # 一次请求内混入多个体系会让"当前版本"失去意义，直接拒绝
        system_ids = await knowledge_point_dao.get_system_ids(db, list(existing))
        if len(system_ids) > 1:
            raise errors.RequestError(msg='不能同时选择多个知识体系版本的知识点')
        if system_id is not None and system_ids and system_id not in system_ids:
            raise errors.RequestError(msg='知识点不属于当前知识体系版本')
        return existing

    @staticmethod
    async def resolve_point_system_id(*, db: AsyncSession, point_ids: Sequence[int]) -> int | None:
        """取一组知识点所属的体系 ID；调用前应已通过 ensure_point_ids 校验同体系"""
        if not point_ids:
            return None
        system_ids = await knowledge_point_dao.get_system_ids(db, list(set(point_ids)))
        return next(iter(system_ids), None)

    @staticmethod
    async def resolve_point_ids(
        *,
        db: AsyncSession,
        point_ids: Sequence[int],
        include_descendants: bool,
        system_id: int | None = None,
    ) -> set[int]:
        existing = await KnowledgeService.ensure_point_ids(db=db, point_ids=point_ids, system_id=system_id)
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
        bank_id: int | None = None,
        root_id: int | None = None,
    ) -> GetKnowledgeTreeDetail:
        system = await knowledge_system_dao.get(db, system_id)
        if system is None:
            raise errors.NotFoundError(msg='知识体系不存在或未启用')

        # bank_id 为空时跨领域内全部题库聚合，供知识点详情页使用
        bank_pk: int | None = None
        revision_id: int | None = None
        if bank_id is not None:
            bank, _ = await bank_access_service.ensure_bank_access(db=db, user_id=user_id, bank_id=bank_id)
            revision = await bank_revision_dao.get(db, bank.current_revision_id, bank_id=bank.id)
            if revision is None or revision.status != 'published':
                raise errors.NotFoundError(msg='题库当前发布版本不存在')
            bank_pk = bank.id
            revision_id = revision.id

        points = await knowledge_point_dao.get_all(db, system.id)
        if root_id is not None and not any(item.id == root_id for item in points):
            raise errors.NotFoundError(msg='知识点不存在或不属于当前知识体系')
        progress = await knowledge_point_dao.get_progress(
            db,
            system_id=system.id,
            bank_revision_id=revision_id,
            user_id=user_id,
        )
        tree = KnowledgeService._build_tree(points=points, progress=progress, root_id=root_id)
        totals = progress.get(root_id or 0, {})
        return GetKnowledgeTreeDetail(
            system=GetKnowledgeSystemListItem.model_validate(system),
            bank_id=bank_pk,
            bank_revision_id=revision_id,
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
        bank_id: int | None = None,
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

    @staticmethod
    async def get_mastery_radar(  # noqa: C901
        *,
        db: AsyncSession,
        user_id: int,
        system_id: int,
        bank_id: int | None = None,
    ) -> GetKnowledgeMasteryRadar:
        """获取当前知识体系顶层知识点掌握度雷达图。"""
        system = await knowledge_system_dao.get(db, system_id)
        if system is None:
            raise errors.NotFoundError(msg='知识体系不存在或未启用')
        points = list(await knowledge_point_dao.get_all(db, system_id))
        point_by_id = {point.id: point for point in points}
        children: dict[int | None, list[int]] = {}
        for point in points:
            children.setdefault(point.parent_id, []).append(point.id)

        def subtree_ids(point_id: int) -> set[int]:
            result = {point_id}
            for child_id in children.get(point_id, []):
                result.update(subtree_ids(child_id))
            return result

        bank_revision_id: int | None = None
        if bank_id is not None:
            bank, _ = await bank_access_service.ensure_bank_access(db=db, user_id=user_id, bank_id=bank_id)
            revision = await bank_revision_dao.get(db, bank.current_revision_id, bank_id=bank.id)
            if revision is None or revision.status != 'published':
                raise errors.NotFoundError(msg='题库当前发布版本不存在')
            bank_revision_id = revision.id

        question_filters = [QbQuestion.deleted == 0, QbQuestion.status == 'active']
        if bank_revision_id is not None:
            question_filters.append(
                QbQuestion.id.in_(
                    select(QbBankItem.question_id).where(
                        QbBankItem.bank_revision_id == bank_revision_id,
                        QbBankItem.is_active.is_(True),
                        QbBankItem.deleted == 0,
                    )
                )
            )
        qpoint_rows = (
            await db.execute(
                select(QbQuestionKnowledgePoint.knowledge_point_id, QbQuestionKnowledgePoint.question_id)
                .join(QbKnowledgePoint, QbKnowledgePoint.id == QbQuestionKnowledgePoint.knowledge_point_id)
                .join(QbQuestion, QbQuestion.id == QbQuestionKnowledgePoint.question_id)
                .where(
                    QbQuestionKnowledgePoint.deleted == 0,
                    QbKnowledgePoint.deleted == 0,
                    QbKnowledgePoint.system_id == system_id,
                    *question_filters,
                )
            )
        ).all()
        question_ids_by_point: dict[int, set[int]] = {point.id: set() for point in points}
        mapped_question_ids: set[int] = set()
        for point_id, question_id in qpoint_rows:
            question_ids_by_point.setdefault(point_id, set()).add(int(question_id))
            mapped_question_ids.add(int(question_id))
        all_question_count = int(
            (
                await db.execute(
                    select(sa.func.count(QbQuestion.id)).where(*question_filters)
                )
            ).scalar_one()
        )
        snapshots = (
            await db.execute(
                select(
                    QbQuestionAttemptKnowledgePoint.knowledge_point_id,
                    QbQuestionAttemptKnowledgePoint.question_id,
                )
                .join(QbQuestion, QbQuestion.id == QbQuestionAttemptKnowledgePoint.question_id)
                .where(
                    QbQuestionAttemptKnowledgePoint.user_id == user_id,
                    QbQuestionAttemptKnowledgePoint.system_id == system_id,
                    QbQuestionAttemptKnowledgePoint.deleted == 0,
                    QbQuestionAttemptKnowledgePoint.evidence_applied.is_(True),
                    *question_filters,
                )
            )
        ).all()
        answered_question_ids_by_point: dict[int, set[int]] = {point.id: set() for point in points}
        for point_id, question_id in snapshots:
            answered_question_ids_by_point.setdefault(point_id, set()).add(int(question_id))
        mastery_rows = await user_knowledge_mastery_dao.get_scope(
            db,
            user_id=user_id,
            system_id=system_id,
        )
        mastery_by_point = {row.knowledge_point_id: row for row in mastery_rows}

        def aggregate(point_id: int) -> dict[str, Any]:
            ids = subtree_ids(point_id)
            rows = [mastery_by_point[item_id] for item_id in ids if item_id in mastery_by_point]
            now = timezone.now()
            decayed_rows: list[tuple[Any, Decimal, Decimal]] = []
            for row in rows:
                elapsed_days = Decimal(0)
                if row.last_attempt_time is not None:
                    elapsed_days = max(
                        Decimal(0),
                        Decimal(str((now - row.last_attempt_time).total_seconds())) / Decimal(86400),
                    )
                decay = KnowledgeMasteryService._decay(elapsed_days=elapsed_days)
                decayed_effective = Decimal(row.effective_sample_size or 0) * decay
                decayed_correct = Decimal(row.weighted_correct or 0) * decay
                decayed_wrong = Decimal(row.weighted_wrong or 0) * decay
                score = (Decimal(1) + decayed_correct) / (Decimal(2) + decayed_correct + decayed_wrong)
                decayed_rows.append((row, decayed_effective, score))
            effective = sum((item[1] for item in decayed_rows), Decimal(0))
            score = (
                sum(
                    (row_score * row_effective for _, row_effective, row_score in decayed_rows),
                    Decimal(0),
                )
                / effective
                if effective > 0
                else None
            )
            question_ids = set().union(*(question_ids_by_point.get(item_id, set()) for item_id in ids))
            answered_ids = set().union(*(answered_question_ids_by_point.get(item_id, set()) for item_id in ids))
            last_attempt = max(
                (row.last_attempt_time for row in rows if row.last_attempt_time is not None),
                default=None,
            )
            display_score = score if effective >= Decimal(1) else None
            state = KnowledgeMasteryService._refresh_state(
                score=score if score is not None else Decimal('0.5'),
                effective_sample_size=effective,
            )
            return {
                'mastery_score': display_score,
                'confidence_score': Decimal(str(1 - math.exp(-float(effective) / 5))) if effective > 0 else Decimal(0),
                'effective_sample_size': effective,
                'attempt_count': sum(row.attempt_count for row in rows),
                'correct_count': sum(row.correct_count for row in rows),
                'question_count': len(question_ids),
                'answered_question_count': len(answered_ids),
                'coverage_rate': KnowledgeService._ratio(len(answered_ids), len(question_ids)),
                'state': state,
                'last_attempt_time': last_attempt,
            }

        def build(point_id: int) -> KnowledgeMasteryRadarNode:
            point = point_by_id[point_id]
            return KnowledgeMasteryRadarNode(
                id=point.id,
                system_id=point.system_id,
                name=point.name,
                parent_id=point.parent_id,
                depth=point.depth,
                children=[build(child_id) for child_id in children.get(point_id, [])],
                **aggregate(point_id),
            )

        roots = [point.id for point in points if point.parent_id is None or point.parent_id not in point_by_id]
        roots.sort(key=lambda point_id: (point_by_id[point_id].sort_order, point_id))
        mapped_count = len(mapped_question_ids)
        # Without a bank revision there is no authoritative, deduplicated
        # denominator: questions may belong to multiple banks and the caller
        # did not specify which published scope should define coverage.
        scoped_question_count = all_question_count if bank_revision_id is not None else None
        return GetKnowledgeMasteryRadar(
            system=GetKnowledgeSystemListItem.model_validate(system),
            bank_id=bank_id,
            bank_revision_id=bank_revision_id,
            points=[build(point_id) for point_id in roots],
            question_count=scoped_question_count,
            mapped_question_count=mapped_count,
            unmapped_question_count=(
                max(0, all_question_count - mapped_count) if scoped_question_count is not None else None
            ),
            coverage_rate=(
                KnowledgeService._ratio(mapped_count, all_question_count)
                if scoped_question_count is not None
                else None
            ),
        )


knowledge_service: KnowledgeService = KnowledgeService()
