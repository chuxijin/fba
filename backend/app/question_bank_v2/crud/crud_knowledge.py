from collections.abc import Sequence
from typing import Any

from opentelemetry import trace
from sqlalchemy import BigInteger, Select, and_, case, column, func, select, values
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
tracer = trace.get_tracer(__name__)


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

    async def get_all(
        self, db: AsyncSession, system_id: int, *, root_id: int | None = None
    ) -> Sequence[QbKnowledgePoint]:
        stmt = (
            select(QbKnowledgePoint)
            .where(QbKnowledgePoint.system_id == system_id, QbKnowledgePoint.deleted == 0)
            .order_by(QbKnowledgePoint.depth, QbKnowledgePoint.sort_order, QbKnowledgePoint.id)
        )
        if root_id is not None:
            subtree = (
                select(QbKnowledgePoint.id)
                .where(
                    QbKnowledgePoint.id == root_id,
                    QbKnowledgePoint.system_id == system_id,
                    QbKnowledgePoint.deleted == 0,
                )
                .cte('point_subtree', recursive=True)
            )
            subtree = subtree.union_all(
                select(QbKnowledgePoint.id)
                .join(subtree, QbKnowledgePoint.parent_id == subtree.c.id)
                .where(QbKnowledgePoint.system_id == system_id, QbKnowledgePoint.deleted == 0)
            )
            stmt = stmt.where(QbKnowledgePoint.id.in_(select(subtree.c.id)))
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
        points: Sequence[QbKnowledgePoint],
        bank_revision_id: int | None,
        user_id: int,
    ) -> dict[int, dict[str, Any]]:
        """兼容调用：合并公共题量和实时用户进度。"""
        progress = await self.get_question_counts(db, points=points, bank_revision_id=bank_revision_id)
        user_progress = await self.get_user_progress(
            db, points=points, bank_revision_id=bank_revision_id, user_id=user_id
        )
        for point_id, data in user_progress.items():
            progress.setdefault(point_id, {}).update(data)
        return progress

    @staticmethod
    def _progress_scope(points: Sequence[Any], bank_revision_id: int | None) -> tuple[Any, list[Any]]:
        """构造题量与个人统计共用的子树祖先关系和题库范围。"""
        parent_by_id = {point.id: point.parent_id for point in points}
        ancestor_pairs: list[tuple[int, int]] = []
        for point_id in parent_by_id:
            ancestor_pairs.append((0, point_id))
            current = point_id
            visited: set[int] = set()
            while current in parent_by_id and current not in visited:
                visited.add(current)
                ancestor_pairs.append((current, point_id))
                current = parent_by_id[current]
        # 只传节点与祖先的少量关系；题目明细和逐题去重始终留在数据库。
        ancestors = (
            values(column('ancestor_id', BigInteger), column('point_id', BigInteger))
            .data(ancestor_pairs)
            .cte('point_ancestors')
        )
        bank_item_filters = [QbBankItem.is_active.is_(True), QbBankItem.deleted == 0]
        if bank_revision_id is not None:
            bank_item_filters.append(QbBankItem.bank_revision_id == bank_revision_id)
        return ancestors, bank_item_filters

    async def get_question_counts(
        self, db: AsyncSession, *, points: Sequence[Any], bank_revision_id: int | None
    ) -> dict[int, dict[str, Any]]:
        """公共题量，不连接任何用户表，可跨用户缓存。"""
        if not points:
            return {}
        ancestors, bank_item_filters = self._progress_scope(points, bank_revision_id)
        point_ids = [point.id for point in points]
        direct_stmt = select(
            QbQuestionKnowledgePoint.knowledge_point_id.label('point_id'),
            (QbBankItem.id if bank_revision_id is not None else QbQuestionKnowledgePoint.question_id).label('item_id'),
            QbQuestionKnowledgePoint.question_id,
        ).where(
            QbQuestionKnowledgePoint.knowledge_point_id.in_(point_ids),
            QbQuestionKnowledgePoint.deleted == 0,
        )
        if bank_revision_id is not None:
            direct_stmt = direct_stmt.join(
                QbBankItem,
                and_(QbBankItem.question_id == QbQuestionKnowledgePoint.question_id, *bank_item_filters),
            )
        else:
            # EXISTS 避免同一道题在多个题库中出现时放大关联行数。
            direct_stmt = direct_stmt.where(
                select(QbBankItem.id)
                .where(QbBankItem.question_id == QbQuestionKnowledgePoint.question_id, *bank_item_filters)
                .exists()
            )
        direct = direct_stmt.distinct().cte('direct_questions')
        tree_questions = (
            select(ancestors.c.ancestor_id, direct.c.item_id, direct.c.question_id)
            .join(direct, direct.c.point_id == ancestors.c.point_id)
            .distinct()
            .cte('tree_questions')
        )
        direct_counts = (
            select(direct.c.point_id, func.count().label('direct_question_count'))
            .group_by(direct.c.point_id)
            .cte('direct_counts')
        )
        count_stmt = (
            select(
                tree_questions.c.ancestor_id,
                func.count().label('question_count'),
                func.coalesce(func.max(direct_counts.c.direct_question_count), 0).label('direct_question_count'),
            )
            .outerjoin(direct_counts, direct_counts.c.point_id == tree_questions.c.ancestor_id)
            .group_by(tree_questions.c.ancestor_id)
        )
        with tracer.start_as_current_span('qbank.knowledge.question_counts') as span:
            count_rows = (await db.execute(count_stmt)).mappings().all()
            span.set_attribute('qbank.scope_points', len(points))
            span.set_attribute('qbank.result_rows', len(count_rows))
        return {int(row['ancestor_id']): dict(row) for row in count_rows}

    async def get_user_progress(
        self, db: AsyncSession, *, points: Sequence[Any], bank_revision_id: int | None, user_id: int
    ) -> dict[int, dict[str, Any]]:
        """实时个人作答与掌握度，不读取公共题量缓存中的用户数据。"""
        if not points:
            return {}
        ancestors, bank_item_filters = self._progress_scope(points, bank_revision_id)
        point_ids = [point.id for point in points]

        # 从该用户已有进度出发；跨题库按最近有效作答判断，不能任取某个题项的进度。
        item_column = (
            QbUserBankItemProgress.bank_item_id if bank_revision_id is not None else QbUserBankItemProgress.question_id
        )
        scoped_progress = (
            select(
                item_column.label('item_id'),
                QbUserBankItemProgress.last_is_correct,
                func
                .row_number()
                .over(
                    partition_by=item_column,
                    order_by=(
                        QbUserBankItemProgress.last_answered_time.desc().nulls_last(),
                        QbUserBankItemProgress.id.desc(),
                    ),
                )
                .label('position'),
            )
            .select_from(QbUserBankItemProgress)
            .join(
                QbBankItem,
                and_(QbBankItem.id == QbUserBankItemProgress.bank_item_id, *bank_item_filters),
            )
            .where(
                QbUserBankItemProgress.user_id == user_id,
                QbUserBankItemProgress.deleted == 0,
            )
            .cte('scoped_progress')
        )
        user_questions = select(
            QbQuestionKnowledgePoint.knowledge_point_id.label('point_id'),
            scoped_progress.c.item_id,
            scoped_progress.c.last_is_correct,
        ).select_from(QbQuestionKnowledgePoint)
        if bank_revision_id is not None:
            user_questions = user_questions.join(
                QbBankItem,
                and_(QbBankItem.question_id == QbQuestionKnowledgePoint.question_id, *bank_item_filters),
            )
        user_questions = (
            user_questions
            .join(
                scoped_progress,
                and_(
                    scoped_progress.c.item_id
                    == (QbBankItem.id if bank_revision_id is not None else QbQuestionKnowledgePoint.question_id),
                    scoped_progress.c.position == 1,
                ),
            )
            .where(
                QbQuestionKnowledgePoint.knowledge_point_id.in_(point_ids),
                QbQuestionKnowledgePoint.deleted == 0,
            )
            .subquery()
        )
        user_tree = (
            select(ancestors.c.ancestor_id, user_questions.c.item_id, user_questions.c.last_is_correct)
            .select_from(ancestors)
            .join(user_questions, user_questions.c.point_id == ancestors.c.point_id)
            .distinct()
            .cte('user_tree')
        )
        progress_stmt = select(
            user_tree.c.ancestor_id,
            func.count().label('answered_count'),
            func.sum(case((user_tree.c.last_is_correct.is_(True), 1), else_=0)).label('correct_count'),
        ).group_by(user_tree.c.ancestor_id)
        with tracer.start_as_current_span('qbank.knowledge.user_progress') as span:
            progress_rows = (await db.execute(progress_stmt)).mappings().all()
            span.set_attribute('qbank.result_rows', len(progress_rows))

        user_mastery = (
            select(
                QbQuestionKnowledgePoint.knowledge_point_id.label('point_id'),
                (QbBankItem.id if bank_revision_id is not None else QbQuestionKnowledgePoint.question_id).label(
                    'item_id'
                ),
                QbUserQuestionMastery.state,
                QbUserQuestionMastery.mastery_score,
            )
            .select_from(QbQuestionKnowledgePoint)
            .join(
                QbUserQuestionMastery,
                and_(
                    QbUserQuestionMastery.question_id == QbQuestionKnowledgePoint.question_id,
                    QbUserQuestionMastery.user_id == user_id,
                    QbUserQuestionMastery.deleted == 0,
                ),
            )
            .where(
                QbQuestionKnowledgePoint.knowledge_point_id.in_(point_ids),
                QbQuestionKnowledgePoint.deleted == 0,
            )
        )
        if bank_revision_id is not None:
            user_mastery = user_mastery.join(
                QbBankItem,
                and_(QbBankItem.question_id == QbQuestionKnowledgePoint.question_id, *bank_item_filters),
            )
        else:
            user_mastery = user_mastery.where(
                select(QbBankItem.id)
                .where(QbBankItem.question_id == QbQuestionKnowledgePoint.question_id, *bank_item_filters)
                .exists()
            )
        user_mastery = user_mastery.subquery()
        mastery_tree = (
            select(ancestors.c.ancestor_id, user_mastery.c.item_id, user_mastery.c.state, user_mastery.c.mastery_score)
            .join(user_mastery, user_mastery.c.point_id == ancestors.c.point_id)
            .distinct()
            .cte('mastery_tree')
        )
        mastery_stmt = select(
            mastery_tree.c.ancestor_id,
            func.sum(case((mastery_tree.c.state == 'mastered', 1), else_=0)).label('mastered_count'),
            func.sum(mastery_tree.c.mastery_score).label('mastery_sum'),
            func.count().label('mastery_sample_count'),
        ).group_by(mastery_tree.c.ancestor_id)
        with tracer.start_as_current_span('qbank.knowledge.user_mastery') as span:
            mastery_rows = (await db.execute(mastery_stmt)).mappings().all()
            span.set_attribute('qbank.result_rows', len(mastery_rows))
        progress: dict[int, dict[str, Any]] = {}
        for row in (*progress_rows, *mastery_rows):
            progress.setdefault(int(row['ancestor_id']), {}).update(row)
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
        system_id: int | None = None,
    ) -> None:
        """整体替换某题的知识点标注。

        ⚠️ `qbank_v2_question_knowledge_point` 本身**不带 knowledge_system_id**
        （体系挂在知识点侧），所以「该删哪些旧关联」必须由调用方说明：

        - 传入 `system_id`：**只替换该体系的标注**，其他体系的标注原样保留；
        - 不传（默认）：保持历史行为 —— 删除该题**全部体系**的关联再插入。

        历史行为在「客户端把各体系标注一起回传」时是无损的（读完再写回原样），
        但只回传单个体系时会把其他体系悄悄删光，且这里是**物理删除**不可恢复。
        所以新的按体系标注入口（如知识点标注页）**必须**传 `system_id`。
        """
        existing_stmt = (
            select(QbQuestionKnowledgePoint)
            .join(QbKnowledgePoint, QbKnowledgePoint.id == QbQuestionKnowledgePoint.knowledge_point_id)
            .where(
                QbQuestionKnowledgePoint.question_id == question_id,
                QbQuestionKnowledgePoint.deleted == 0,
            )
        )
        if system_id is not None:
            existing_stmt = existing_stmt.where(QbKnowledgePoint.system_id == system_id)
        existing = (await db.execute(existing_stmt)).scalars().all()
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
