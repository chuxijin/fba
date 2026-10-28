import re

from collections.abc import Collection, Sequence
from typing import Any

from sqlalchemy import Select, Text, and_, case, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.bank import QbBank, QbBankItem, QbBankRevision, QbBankSection
from backend.app.question_bank_v2.model.catalog import QbBankCategory
from backend.app.question_bank_v2.model.knowledge import QbQuestionKnowledgePoint
from backend.app.question_bank_v2.model.material import QbQuestionMaterial
from backend.app.question_bank_v2.model.question import (
    QbQuestion,
    QbQuestionAnswer,
    QbQuestionExplanation,
)
from backend.app.question_bank_v2.schema.question import (
    QuestionAnswerParam,
    QuestionExplanationParam,
)


class CRUDQuestion(CRUDPlus[QbQuestion]):
    """题目数据库操作类"""

    @staticmethod
    def _active_stmt() -> Select[tuple[QbQuestion]]:
        return select(QbQuestion).where(QbQuestion.deleted == 0)

    async def get(self, db: AsyncSession, pk: int, *, for_update: bool = False) -> QbQuestion | None:
        stmt = self._active_stmt().where(QbQuestion.id == pk)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_code(self, db: AsyncSession, code: str) -> QbQuestion | None:
        result = await db.execute(self._active_stmt().where(QbQuestion.code == code))
        return result.scalars().first()

    async def get_list(
        self,
        db: AsyncSession,
        *,
        bank_id: int | None = None,
        bank_revision_id: int | None = None,
        question_type: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        stmt = self.get_list_select(
            bank_id=bank_id,
            bank_revision_id=bank_revision_id,
            question_type=question_type,
            keyword=keyword,
        ).offset(offset).limit(limit)
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    def get_list_select(
        self,
        *,
        bank_id: int | None = None,
        bank_revision_id: int | None = None,
        question_type: str | None = None,
        keyword: str | None = None,
        knowledge_labeled: bool | None = None,
        section_ids: Sequence[int] | None = None,
        knowledge_point_ids: Sequence[int] | None = None,
    ) -> Select:
        """构建题目列表分页查询，交给 API 层 paging_data 处理"""
        stmt = select(
            QbQuestion.id,
            QbQuestion.code,
            QbQuestion.visibility,
            QbQuestion.origin_type,
            QbQuestion.status,
            QbQuestion.stem,
            QbQuestion.question_type,
            QbQuestion.default_score,
            QbQuestion.difficulty,
            QbQuestion.created_time,
            QbQuestion.updated_time,
        ).where(QbQuestion.deleted == 0)
        if bank_id is not None or bank_revision_id is not None or section_ids is not None:
            stmt = (
                stmt.join(QbBankItem, QbBankItem.question_id == QbQuestion.id)
                .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
                .where(
                    QbBankItem.deleted == 0,
                    QbBankRevision.deleted == 0,
                )
                .distinct()
            )
            if bank_id is not None:
                stmt = stmt.where(QbBankRevision.bank_id == bank_id)
            if bank_revision_id is not None:
                stmt = stmt.where(QbBankRevision.id == bank_revision_id)
            if section_ids is not None:
                # 章节筛选：调用方需先展开子孙章节；空列表语义为「无匹配」而非「不过滤」
                stmt = stmt.where(QbBankItem.section_id.in_(section_ids))
        if question_type is not None:
            stmt = stmt.where(QbQuestion.question_type == question_type)
        if keyword:
            stmt = stmt.where(QbQuestion.stem.ilike(f'%{keyword}%'))
        if knowledge_labeled is not None:
            # True 只保留已挂知识点的题，False 只保留未标注的题
            linked = select(QbQuestionKnowledgePoint.id).where(
                QbQuestionKnowledgePoint.question_id == QbQuestion.id,
                QbQuestionKnowledgePoint.deleted == 0,
            )
            stmt = stmt.where(linked.exists() if knowledge_labeled else ~linked.exists())
        if knowledge_point_ids is not None:
            # 知识点筛选：题目标注的知识点至少命中一个即可；空列表语义为「无匹配」而非「不过滤」
            stmt = (
                stmt.join(QbQuestionKnowledgePoint)
                .where(QbQuestionKnowledgePoint.knowledge_point_id.in_(knowledge_point_ids))
                .distinct()
            )
        return stmt.order_by(QbQuestion.updated_time.desc(), QbQuestion.id.desc())

    def get_public_search_select(
        self,
        *,
        keyword: str,
        domain_category_ids: Collection[int] | None = None,
    ) -> Select:
        """构建公开题目检索查询

        命中口径：题干、有序选项、已发布解析任一处包含关键词；空格分隔的多个关键词
        之间是「与」关系，与题库名检索保持一致。
        题目必须挂在公开、启用且已发布的题库上，避免把后台草稿或下架内容搜出来；
        传入领域分类时按分类子树收窄，只搜当前领域的题。
        """
        terms = [term for term in re.split(r'\s+', keyword.strip()) if term] or [keyword.strip()]

        def match_condition(term: str) -> Any:
            """单个关键词的命中条件：题干 / 选项 / 解析任一命中即可"""
            pattern = f'%{term}%'
            matched_explanation = select(QbQuestionExplanation.id).where(
                QbQuestionExplanation.question_id == QbQuestion.id,
                QbQuestionExplanation.deleted == 0,
                QbQuestionExplanation.status == 'published',
                QbQuestionExplanation.content.ilike(pattern),
            )
            return or_(
                QbQuestion.stem.ilike(pattern),
                cast(QbQuestion.option_data, Text).ilike(pattern),
                matched_explanation.exists(),
            )

        source_stmt = (
            select(
                QbBankItem.question_id.label('question_id'),
                QbBank.id.label('bank_id'),
                QbBankRevision.name.label('bank_name'),
                QbBankSection.name.label('section_name'),
            )
            .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
            .join(QbBank, QbBank.id == QbBankRevision.bank_id)
            .outerjoin(
                QbBankSection,
                and_(QbBankSection.id == QbBankItem.section_id, QbBankSection.deleted == 0),
            )
            .where(
                QbBankItem.deleted == 0,
                QbBankRevision.deleted == 0,
                QbBankRevision.status == 'published',
                QbBank.deleted == 0,
                QbBank.visibility == 'public',
                QbBank.status == 'active',
            )
        )
        if domain_category_ids:
            source_stmt = source_stmt.join(
                QbBankCategory,
                and_(QbBankCategory.bank_id == QbBank.id, QbBankCategory.deleted == 0),
            ).where(QbBankCategory.category_id.in_(list(domain_category_ids)))

        # 同一道题可能挂在多份试卷里，这里只保留最早的一条挂载作为来源上下文
        source = (
            source_stmt.distinct(QbBankItem.question_id)
            .order_by(QbBankItem.question_id, QbBankItem.id)
            .subquery('public_question_source')
        )

        default_explanation = (
            select(QbQuestionExplanation.content)
            .where(
                QbQuestionExplanation.question_id == QbQuestion.id,
                QbQuestionExplanation.deleted == 0,
                QbQuestionExplanation.status == 'published',
                QbQuestionExplanation.is_default.is_(True),
            )
            .order_by(QbQuestionExplanation.id)
            .limit(1)
            .scalar_subquery()
        )

        return (
            select(
                QbQuestion.id,
                QbQuestion.question_type,
                QbQuestion.stem,
                QbQuestion.content_format,
                QbQuestion.option_data,
                QbQuestion.difficulty,
                default_explanation.label('explanation'),
                source.c.bank_id,
                source.c.bank_name,
                source.c.section_name,
            )
            .join(source, source.c.question_id == QbQuestion.id)
            .where(
                QbQuestion.deleted == 0,
                QbQuestion.status == 'active',
                QbQuestion.visibility == 'public',
                and_(*[match_condition(term) for term in terms]),
            )
            # 题干命中排在仅选项或解析命中的前面，其余按题目 ID 保持同卷聚拢
            .order_by(
                case(
                    (and_(*[QbQuestion.stem.ilike(f'%{term}%') for term in terms]), 0),
                    else_=1,
                ),
                QbQuestion.id,
            )
        )

    async def get_by_material(self, db: AsyncSession, *, material_id: int) -> Sequence[dict[str, Any]]:
        """获取关联指定材料的所有题目"""
        stmt = (
            select(
                QbQuestion.id,
                QbQuestion.code,
                QbQuestion.stem,
                QbQuestion.question_type,
            )
            .join(
                QbQuestionMaterial,
                QbQuestionMaterial.question_id == QbQuestion.id,
            )
            .where(
                QbQuestionMaterial.material_id == material_id,
                QbQuestion.deleted == 0,
                QbQuestionMaterial.deleted == 0,
            )
            .order_by(QbQuestion.id)
        )
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    def get_by_material_select(self, *, material_id: int) -> Select:
        """构建材料关联题目游标分页查询"""
        return (
            select(
                QbQuestion.id,
                QbQuestion.code,
                QbQuestion.stem,
                QbQuestion.question_type,
            )
            .join(QbQuestionMaterial, QbQuestionMaterial.question_id == QbQuestion.id)
            .where(
                QbQuestionMaterial.material_id == material_id,
                QbQuestion.deleted == 0,
                QbQuestionMaterial.deleted == 0,
            )
            .order_by(QbQuestion.id)
        )

    async def create(
        self,
        db: AsyncSession,
        *,
        code: str,
        owner_id: int | None,
        visibility: str,
        origin_type: str,
        status: str,
        stem: str,
        content_format: str,
        question_type: str,
        option_data: list[dict[str, Any]],
        default_score: Any,
        difficulty: Any | None,
        content_hash: str | None,
        created_by: int,
    ) -> QbQuestion:
        question = QbQuestion(
            code=code,
            owner_id=owner_id,
            visibility=visibility,
            origin_type=origin_type,
            status=status,
            stem=stem,
            content_format=content_format,
            question_type=question_type,
            option_data=option_data,
            default_score=default_score,
            difficulty=difficulty,
            content_hash=content_hash,
            created_by=created_by,
        )
        db.add(question)
        await db.flush()
        return question

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        return await self.update_model_by_column(db, data, id=pk, deleted=0)


class CRUDQuestionAnswer(CRUDPlus[QbQuestionAnswer]):
    """题目权威答案数据库操作类"""

    async def get_by_question(self, db: AsyncSession, question_id: int) -> QbQuestionAnswer | None:
        stmt = select(QbQuestionAnswer).where(
            QbQuestionAnswer.question_id == question_id,
            QbQuestionAnswer.deleted == 0,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def upsert(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        obj: QuestionAnswerParam,
        user_id: int,
    ) -> QbQuestionAnswer:
        answer = await self.get_by_question(db, question_id)
        data = obj.model_dump()
        if answer is None:
            answer = QbQuestionAnswer(
                question_id=question_id,
                created_by=user_id,
                **data,
            )
            db.add(answer)
            await db.flush()
        else:
            data['updated_by'] = user_id
            await self.update_model_by_column(db, data, id=answer.id, deleted=0)
            answer = await self.get_by_question(db, question_id)
        return answer


class CRUDQuestionExplanation(CRUDPlus[QbQuestionExplanation]):
    """题目解析数据库操作类"""

    async def get_all(self, db: AsyncSession, question_id: int) -> Sequence[QbQuestionExplanation]:
        stmt = (
            select(QbQuestionExplanation)
            .where(
                QbQuestionExplanation.question_id == question_id,
                QbQuestionExplanation.deleted == 0,
            )
            .order_by(QbQuestionExplanation.is_default.desc(), QbQuestionExplanation.id)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_published_by_question(self, db: AsyncSession, question_id: int) -> list[dict[str, Any]]:
        """按题读取已发布解析，默认解析在前。

        只取展示需要的三列，且把 `status` 过滤下推到 SQL，避免把草稿解析带给学习者。
        """
        stmt = (
            select(
                QbQuestionExplanation.content,
                QbQuestionExplanation.explanation_type,
                QbQuestionExplanation.is_default,
            )
            .where(
                QbQuestionExplanation.question_id == question_id,
                QbQuestionExplanation.deleted == 0,
                QbQuestionExplanation.status == 'published',
            )
            .order_by(QbQuestionExplanation.is_default.desc(), QbQuestionExplanation.id)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    async def get_all_by_questions(
        self,
        db: AsyncSession,
        question_ids: Sequence[int],
    ) -> Sequence[QbQuestionExplanation]:
        """批量获取多个题目的解析"""
        if not question_ids:
            return []
        stmt = (
            select(QbQuestionExplanation)
            .where(
                QbQuestionExplanation.question_id.in_(question_ids),
                QbQuestionExplanation.deleted == 0,
            )
            .order_by(
                QbQuestionExplanation.question_id,
                QbQuestionExplanation.is_default.desc(),
                QbQuestionExplanation.id,
            )
        )
        return (await db.execute(stmt)).scalars().all()

    async def replace(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        items: list[QuestionExplanationParam],
        user_id: int,
        status: str = 'draft',
    ) -> None:
        existing = await self.get_all(db, question_id)
        for item in existing:
            await self.delete_model(db, item.id)
        for item in items:
            db.add(
                QbQuestionExplanation(
                    question_id=question_id,
                    created_by=user_id,
                    status=status,
                    **item.model_dump(exclude={'version_no'}),
                )
            )
        await db.flush()


question_dao: CRUDQuestion = CRUDQuestion(QbQuestion)
question_answer_dao: CRUDQuestionAnswer = CRUDQuestionAnswer(QbQuestionAnswer)
question_explanation_dao: CRUDQuestionExplanation = CRUDQuestionExplanation(QbQuestionExplanation)
