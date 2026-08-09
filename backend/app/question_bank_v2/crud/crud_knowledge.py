from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.bank import QbBankItem
from backend.app.question_bank_v2.model.knowledge import (
    QbKnowledgePoint,
    QbKnowledgeSystem,
    QbQuestionKnowledgePoint,
)
from backend.app.question_bank_v2.model.statistics import QbUserBankItemProgress, QbUserQuestionMastery
from backend.app.question_bank_v2.schema.knowledge import KnowledgePointAssignmentParam

DEFAULT_KNOWLEDGE_SYSTEM_VERSION = 'default'


class CRUDKnowledgeSystem(CRUDPlus[QbKnowledgeSystem]):
    """知识体系数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> QbKnowledgeSystem | None:
        stmt = select(QbKnowledgeSystem).where(
            QbKnowledgeSystem.id == pk,
            QbKnowledgeSystem.deleted == 0,
            QbKnowledgeSystem.status == 'active',
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_all(
        self,
        db: AsyncSession,
        *,
        domain_category_id: int | None = None,
        code: str | None = None,
    ) -> Sequence[QbKnowledgeSystem]:
        stmt = self.get_select(domain_category_id=domain_category_id, code=code)
        return (await db.execute(stmt)).scalars().all()

    def get_select(self, *, domain_category_id: int | None = None, code: str | None = None) -> Select:
        stmt = (
            select(QbKnowledgeSystem)
            .where(QbKnowledgeSystem.deleted == 0, QbKnowledgeSystem.status == 'active')
            .order_by(QbKnowledgeSystem.name, QbKnowledgeSystem.version, QbKnowledgeSystem.id)
        )
        if domain_category_id is not None:
            stmt = stmt.where(QbKnowledgeSystem.domain_category_id == domain_category_id)
        if code is not None:
            stmt = stmt.where(QbKnowledgeSystem.code == code)
        return stmt

    async def get_default_system_id(
        self,
        db: AsyncSession,
        *,
        domain_category_id: int,
        code: str | None = None,
    ) -> int | None:
        """解析指定领域（可选科目）下 version 为默认标记的启用体系"""
        stmt = (
            select(QbKnowledgeSystem.id)
            .where(
                QbKnowledgeSystem.deleted == 0,
                QbKnowledgeSystem.status == 'active',
                QbKnowledgeSystem.domain_category_id == domain_category_id,
                QbKnowledgeSystem.version == DEFAULT_KNOWLEDGE_SYSTEM_VERSION,
            )
            .order_by(QbKnowledgeSystem.id)
            .limit(1)
        )
        if code is not None:
            stmt = stmt.where(QbKnowledgeSystem.code == code)
        return (await db.execute(stmt)).scalars().first()

    async def get_codes(self, db: AsyncSession, *, domain_category_id: int) -> list[str]:
        """获取指定领域下所有启用体系的科目编码"""
        stmt = (
            select(QbKnowledgeSystem.code)
            .where(
                QbKnowledgeSystem.deleted == 0,
                QbKnowledgeSystem.status == 'active',
                QbKnowledgeSystem.domain_category_id == domain_category_id,
            )
            .distinct()
            .order_by(QbKnowledgeSystem.code)
        )
        return list((await db.execute(stmt)).scalars().all())


class CRUDKnowledgePoint(CRUDPlus[QbKnowledgePoint]):
    """知识点及其学习进度数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> QbKnowledgePoint | None:
        stmt = select(QbKnowledgePoint).where(QbKnowledgePoint.id == pk, QbKnowledgePoint.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def get_all(self, db: AsyncSession, system_id: int) -> Sequence[QbKnowledgePoint]:
        stmt = (
            select(QbKnowledgePoint)
            .where(QbKnowledgePoint.system_id == system_id, QbKnowledgePoint.deleted == 0)
            .order_by(QbKnowledgePoint.depth, QbKnowledgePoint.sort_order, QbKnowledgePoint.id)
        )
        return (await db.execute(stmt)).scalars().all()

    async def get_existing_ids(self, db: AsyncSession, point_ids: Sequence[int]) -> set[int]:
        if not point_ids:
            return set()
        result = await db.execute(
            select(QbKnowledgePoint.id)
            .join(QbKnowledgeSystem, QbKnowledgeSystem.id == QbKnowledgePoint.system_id)
            .where(
                QbKnowledgePoint.id.in_(point_ids),
                QbKnowledgePoint.deleted == 0,
                QbKnowledgeSystem.deleted == 0,
                QbKnowledgeSystem.status == 'active',
            )
        )
        return set(result.scalars().all())

    async def get_system_ids(self, db: AsyncSession, point_ids: Sequence[int]) -> set[int]:
        """获取一批知识点所属的体系 ID 集合，用于拒绝跨版本混选"""
        if not point_ids:
            return set()
        result = await db.execute(
            select(QbKnowledgePoint.system_id)
            .where(QbKnowledgePoint.id.in_(point_ids), QbKnowledgePoint.deleted == 0)
            .distinct()
        )
        return set(result.scalars().all())

    async def expand_descendant_ids(self, db: AsyncSession, point_ids: Sequence[int]) -> set[int]:
        """使用递归 CTE 展开多个知识点的全部后代"""
        if not point_ids:
            return set()
        tree = (
            select(QbKnowledgePoint.id, QbKnowledgePoint.system_id)
            .where(QbKnowledgePoint.id.in_(point_ids), QbKnowledgePoint.deleted == 0)
            .cte('knowledge_tree', recursive=True)
        )
        tree = tree.union_all(
            select(QbKnowledgePoint.id, QbKnowledgePoint.system_id)
            .join(
                tree,
                and_(
                    QbKnowledgePoint.system_id == tree.c.system_id,
                    QbKnowledgePoint.parent_id == tree.c.id,
                ),
            )
            .where(QbKnowledgePoint.deleted == 0)
        )
        result = await db.execute(select(tree.c.id).distinct())
        return set(result.scalars().all())

    async def get_progress(
        self,
        db: AsyncSession,
        *,
        system_id: int,
        bank_revision_id: int | None,
        user_id: int,
    ) -> dict[int, dict[str, Any]]:
        """按知识点聚合题量与当前用户进度

        bank_revision_id 为空时不限定题库，跨全部启用的题库版本聚合，
        供知识点详情页这类没有题库上下文的场景使用。
        """
        bank_item_filters = [
            QbBankItem.is_active.is_(True),
            QbBankItem.deleted == 0,
        ]
        if bank_revision_id is not None:
            bank_item_filters.append(QbBankItem.bank_revision_id == bank_revision_id)

        direct_stmt = (
            select(
                QbQuestionKnowledgePoint.knowledge_point_id,
                func.count(
                    func.distinct(QbBankItem.id if bank_revision_id is not None else QbBankItem.question_id)
                ).label('direct_question_count'),
            )
            .select_from(QbQuestionKnowledgePoint)
            .join(
                QbKnowledgePoint,
                and_(
                    QbKnowledgePoint.id == QbQuestionKnowledgePoint.knowledge_point_id,
                    QbKnowledgePoint.system_id == system_id,
                    QbKnowledgePoint.deleted == 0,
                ),
            )
            .join(
                QbBankItem,
                and_(
                    QbBankItem.question_id == QbQuestionKnowledgePoint.question_id,
                    *bank_item_filters,
                ),
            )
            .where(QbQuestionKnowledgePoint.deleted == 0)
            .group_by(QbQuestionKnowledgePoint.knowledge_point_id)
        )
        direct_rows = (await db.execute(direct_stmt)).mappings().all()

        point_rows = (
            await db.execute(
                select(QbKnowledgePoint.id, QbKnowledgePoint.parent_id).where(
                    QbKnowledgePoint.system_id == system_id,
                    QbKnowledgePoint.deleted == 0,
                )
            )
        ).all()
        parent_by_id = dict(point_rows)
        ancestor_cache: dict[int, tuple[int, ...]] = {}

        def ancestors(point_id: int) -> tuple[int, ...]:
            if point_id in ancestor_cache:
                return ancestor_cache[point_id]
            chain: list[int] = []
            current: int | None = point_id
            visited: set[int] = set()
            while current is not None and current not in visited:
                visited.add(current)
                chain.append(current)
                current = parent_by_id.get(current)
            ancestor_cache[point_id] = tuple(chain)
            return ancestor_cache[point_id]

        fact_stmt = (
            select(
                QbQuestionKnowledgePoint.knowledge_point_id,
                QbBankItem.id.label('bank_item_id'),
                QbBankItem.question_id,
                QbUserBankItemProgress.id.label('progress_id'),
                QbUserBankItemProgress.last_is_correct,
                QbUserQuestionMastery.id.label('mastery_id'),
                QbUserQuestionMastery.state.label('mastery_state'),
                QbUserQuestionMastery.mastery_score,
            )
            .select_from(QbQuestionKnowledgePoint)
            .join(
                QbKnowledgePoint,
                and_(
                    QbKnowledgePoint.id == QbQuestionKnowledgePoint.knowledge_point_id,
                    QbKnowledgePoint.system_id == system_id,
                    QbKnowledgePoint.deleted == 0,
                ),
            )
            .join(
                QbBankItem,
                and_(
                    QbBankItem.question_id == QbQuestionKnowledgePoint.question_id,
                    *bank_item_filters,
                ),
            )
            .outerjoin(
                QbUserBankItemProgress,
                and_(
                    QbUserBankItemProgress.user_id == user_id,
                    QbUserBankItemProgress.bank_item_id == QbBankItem.id,
                    QbUserBankItemProgress.deleted == 0,
                ),
            )
            .outerjoin(
                QbUserQuestionMastery,
                and_(
                    QbUserQuestionMastery.user_id == user_id,
                    QbUserQuestionMastery.question_id == QbBankItem.question_id,
                    QbUserQuestionMastery.deleted == 0,
                ),
            )
            .where(QbQuestionKnowledgePoint.deleted == 0)
        )
        facts = (await db.execute(fact_stmt)).mappings().all()
        # 限定单一题库版本时按编排项计数；跨题库聚合时同一道题会出现在多个题库，
        # 必须按题目去重，否则题量和作答数会被重复计算。
        dedupe_field = 'bank_item_id' if bank_revision_id is not None else 'question_id'
        buckets: dict[int, dict[int, Any]] = {0: {}}
        for fact in facts:
            for ancestor_id in (*ancestors(int(fact['knowledge_point_id'])), 0):
                buckets.setdefault(ancestor_id, {}).setdefault(int(fact[dedupe_field]), fact)

        progress: dict[int, dict[str, Any]] = {}
        for point_id, item_facts in buckets.items():
            values = item_facts.values()
            mastery_values = [fact['mastery_score'] for fact in values if fact['mastery_id'] is not None]
            progress[point_id] = {
                'question_count': len(item_facts),
                'answered_count': sum(fact['progress_id'] is not None for fact in values),
                'correct_count': sum(fact['last_is_correct'] is True for fact in values),
                'mastered_count': sum(fact['mastery_state'] == 'mastered' for fact in values),
                'mastery_sum': sum(mastery_values),
                'mastery_sample_count': len(mastery_values),
            }
        for row in direct_rows:
            progress.setdefault(int(row['knowledge_point_id']), {})['direct_question_count'] = int(
                row['direct_question_count']
            )
        return progress


class CRUDQuestionKnowledgePoint(CRUDPlus[QbQuestionKnowledgePoint]):
    """题目知识点标注数据库操作类"""

    async def get_all(
        self,
        db: AsyncSession,
        question_id: int,
        *,
        system_id: int | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                QbQuestionKnowledgePoint.id,
                QbQuestionKnowledgePoint.question_id,
                QbQuestionKnowledgePoint.knowledge_point_id,
                QbQuestionKnowledgePoint.role,
                QbQuestionKnowledgePoint.weight,
                QbQuestionKnowledgePoint.source,
                QbQuestionKnowledgePoint.confidence,
                QbKnowledgePoint.name.label('knowledge_point_name'),
            )
            .join(QbKnowledgePoint, QbKnowledgePoint.id == QbQuestionKnowledgePoint.knowledge_point_id)
            .where(
                QbQuestionKnowledgePoint.question_id == question_id,
                QbQuestionKnowledgePoint.deleted == 0,
                QbKnowledgePoint.deleted == 0,
            )
            .order_by(QbQuestionKnowledgePoint.role, QbKnowledgePoint.sort_order, QbKnowledgePoint.id)
        )
        if system_id is not None:
            stmt = stmt.where(QbKnowledgePoint.system_id == system_id)
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    async def replace(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        items: Sequence[KnowledgePointAssignmentParam],
        user_id: int,
    ) -> None:
        existing = (
            await db.execute(
                select(QbQuestionKnowledgePoint).where(
                    QbQuestionKnowledgePoint.question_id == question_id,
                    QbQuestionKnowledgePoint.deleted == 0,
                )
            )
        ).scalars().all()
        for item in existing:
            await self.delete_model(db, item.id)
        db.add_all([
            QbQuestionKnowledgePoint(
                question_id=question_id,
                created_by=user_id,
                **item.model_dump(),
            )
            for item in items
        ])
        await db.flush()


knowledge_system_dao: CRUDKnowledgeSystem = CRUDKnowledgeSystem(QbKnowledgeSystem)
knowledge_point_dao: CRUDKnowledgePoint = CRUDKnowledgePoint(QbKnowledgePoint)
question_knowledge_point_dao: CRUDQuestionKnowledgePoint = CRUDQuestionKnowledgePoint(QbQuestionKnowledgePoint)
