from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.bank import QbBankItem, QbBankRevision
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
        question_type: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        stmt = self.get_list_select(
            bank_id=bank_id,
            question_type=question_type,
            keyword=keyword,
        ).offset(offset).limit(limit)
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    def get_list_select(
        self,
        *,
        bank_id: int | None = None,
        question_type: str | None = None,
        keyword: str | None = None,
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
        if bank_id is not None:
            stmt = (
                stmt.join(QbBankItem, QbBankItem.question_id == QbQuestion.id)
                .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
                .where(
                    QbBankRevision.bank_id == bank_id,
                    QbBankItem.deleted == 0,
                    QbBankRevision.deleted == 0,
                )
                .distinct()
            )
        if question_type is not None:
            stmt = stmt.where(QbQuestion.question_type == question_type)
        if keyword:
            stmt = stmt.where(QbQuestion.stem.ilike(f'%{keyword}%'))
        return stmt.order_by(QbQuestion.updated_time.desc(), QbQuestion.id.desc())

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
    ) -> None:
        existing = await self.get_all(db, question_id)
        for item in existing:
            await self.delete_model(db, item.id)
        for item in items:
            db.add(
                QbQuestionExplanation(
                    question_id=question_id,
                    created_by=user_id,
                    **item.model_dump(),
                )
            )
        await db.flush()


question_dao: CRUDQuestion = CRUDQuestion(QbQuestion)
question_answer_dao: CRUDQuestionAnswer = CRUDQuestionAnswer(QbQuestionAnswer)
question_explanation_dao: CRUDQuestionExplanation = CRUDQuestionExplanation(QbQuestionExplanation)
