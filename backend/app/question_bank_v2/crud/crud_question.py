from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.question import (
    QbQuestion,
    QbQuestionAnswer,
    QbQuestionExplanation,
    QbQuestionExternalRef,
    QbQuestionRevision,
)
from backend.app.question_bank_v2.schema.question import (
    CreateQuestionRevisionParam,
    QuestionAnswerParam,
    QuestionExplanationParam,
)


class CRUDQuestion(CRUDPlus[QbQuestion]):
    """题目稳定身份数据库操作类"""

    @staticmethod
    def _active_stmt() -> Select[tuple[QbQuestion]]:
        return select(QbQuestion).where(QbQuestion.deleted == 0)

    async def get(self, db: AsyncSession, pk: int, *, for_update: bool = False) -> QbQuestion | None:
        """获取题目稳定身份"""
        stmt = self._active_stmt().where(QbQuestion.id == pk)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_code(self, db: AsyncSession, code: str) -> QbQuestion | None:
        """通过业务编码获取题目"""
        result = await db.execute(self._active_stmt().where(QbQuestion.code == code))
        return result.scalars().first()

    async def get_list(
        self,
        db: AsyncSession,
        *,
        question_type: str | None = None,
        revision_status: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """获取题目管理列表，展示每题最近版本"""
        latest_revision = (
            select(
                QbQuestionRevision.question_id,
                func.max(QbQuestionRevision.revision_no).label('revision_no'),
            )
            .where(QbQuestionRevision.deleted == 0)
            .group_by(QbQuestionRevision.question_id)
            .subquery()
        )
        stmt = (
            select(
                QbQuestion.id,
                QbQuestion.code,
                QbQuestion.visibility,
                QbQuestion.origin_type,
                QbQuestion.status,
                QbQuestionRevision.id.label('revision_id'),
                QbQuestionRevision.revision_no,
                QbQuestionRevision.status.label('revision_status'),
                QbQuestionRevision.stem,
                QbQuestionRevision.question_type,
                QbQuestionRevision.difficulty,
                QbQuestionRevision.updated_time,
            )
            .join(latest_revision, latest_revision.c.question_id == QbQuestion.id)
            .join(
                QbQuestionRevision,
                and_(
                    QbQuestionRevision.question_id == latest_revision.c.question_id,
                    QbQuestionRevision.revision_no == latest_revision.c.revision_no,
                    QbQuestionRevision.deleted == 0,
                ),
            )
            .where(QbQuestion.deleted == 0)
        )
        if question_type is not None:
            stmt = stmt.where(QbQuestionRevision.question_type == question_type)
        if revision_status is not None:
            stmt = stmt.where(QbQuestionRevision.status == revision_status)
        if keyword:
            stmt = stmt.where(QbQuestionRevision.stem.ilike(f'%{keyword}%'))
        stmt = stmt.order_by(QbQuestionRevision.updated_time.desc(), QbQuestion.id.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def create(
        self,
        db: AsyncSession,
        *,
        code: str,
        owner_id: int | None,
        visibility: str,
        origin_type: str,
        status: str,
        created_by: int,
    ) -> QbQuestion:
        """创建题目稳定身份"""
        question = QbQuestion(
            code=code,
            owner_id=owner_id,
            visibility=visibility,
            origin_type=origin_type,
            status=status,
            created_by=created_by,
        )
        db.add(question)
        await db.flush()
        return question

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """更新题目稳定身份"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0)


class CRUDQuestionRevision(CRUDPlus[QbQuestionRevision]):
    """题目版本数据库操作类"""

    async def get(
        self,
        db: AsyncSession,
        pk: int,
        *,
        question_id: int | None = None,
        for_update: bool = False,
    ) -> QbQuestionRevision | None:
        """获取题目版本"""
        stmt = select(QbQuestionRevision).where(QbQuestionRevision.id == pk, QbQuestionRevision.deleted == 0)
        if question_id is not None:
            stmt = stmt.where(QbQuestionRevision.question_id == question_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_latest(self, db: AsyncSession, question_id: int) -> QbQuestionRevision | None:
        """获取题目最近版本"""
        stmt = (
            select(QbQuestionRevision)
            .where(QbQuestionRevision.question_id == question_id, QbQuestionRevision.deleted == 0)
            .order_by(QbQuestionRevision.revision_no.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all(self, db: AsyncSession, question_id: int) -> Sequence[QbQuestionRevision]:
        """获取题目全部版本"""
        stmt = (
            select(QbQuestionRevision)
            .where(QbQuestionRevision.question_id == question_id, QbQuestionRevision.deleted == 0)
            .order_by(QbQuestionRevision.revision_no.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_next_revision_no(self, db: AsyncSession, question_id: int) -> int:
        """获取下一个题目版本号"""
        result = await db.execute(
            select(func.coalesce(func.max(QbQuestionRevision.revision_no), 0) + 1).where(
                QbQuestionRevision.question_id == question_id
            )
        )
        return int(result.scalar_one())

    async def create(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        revision_no: int,
        obj: CreateQuestionRevisionParam,
        created_by: int,
    ) -> QbQuestionRevision:
        """创建题目草稿版本"""
        revision_data = obj.model_dump(exclude={'answer', 'explanations', 'options'})
        revision_data['option_data'] = [item.model_dump() for item in obj.options]
        revision = QbQuestionRevision(
            question_id=question_id,
            revision_no=revision_no,
            created_by=created_by,
            **revision_data,
        )
        db.add(revision)
        await db.flush()
        return revision

    async def create_data(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        revision_no: int,
        data: dict[str, Any],
        created_by: int,
    ) -> QbQuestionRevision:
        """通过已规范化数据创建可不完整的个人题目草稿版本"""
        revision = QbQuestionRevision(
            question_id=question_id,
            revision_no=revision_no,
            created_by=created_by,
            **data,
        )
        db.add(revision)
        await db.flush()
        return revision

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """更新题目草稿版本"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0, status='draft')


class CRUDQuestionAnswer(CRUDPlus[QbQuestionAnswer]):
    """题目权威答案数据库操作类"""

    async def get_by_revision(self, db: AsyncSession, revision_id: int) -> QbQuestionAnswer | None:
        """获取题目版本权威答案"""
        stmt = select(QbQuestionAnswer).where(
            QbQuestionAnswer.question_revision_id == revision_id,
            QbQuestionAnswer.deleted == 0,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def upsert(
        self,
        db: AsyncSession,
        *,
        revision_id: int,
        obj: QuestionAnswerParam,
        user_id: int,
    ) -> QbQuestionAnswer:
        """创建或更新题目版本权威答案"""
        answer = await self.get_by_revision(db, revision_id)
        data = obj.model_dump()
        if answer is None:
            answer = QbQuestionAnswer(
                question_revision_id=revision_id,
                created_by=user_id,
                **data,
            )
            db.add(answer)
            await db.flush()
        else:
            data['updated_by'] = user_id
            await self.update_model_by_column(db, data, id=answer.id, deleted=0)
            answer = await self.get_by_revision(db, revision_id)
        return answer


class CRUDQuestionExplanation(CRUDPlus[QbQuestionExplanation]):
    """题目解析数据库操作类"""

    async def get_all(self, db: AsyncSession, revision_id: int) -> Sequence[QbQuestionExplanation]:
        """获取题目版本全部解析"""
        stmt = (
            select(QbQuestionExplanation)
            .where(
                QbQuestionExplanation.question_revision_id == revision_id,
                QbQuestionExplanation.deleted == 0,
            )
            .order_by(QbQuestionExplanation.is_default.desc(), QbQuestionExplanation.id)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def replace(
        self,
        db: AsyncSession,
        *,
        revision_id: int,
        items: list[QuestionExplanationParam],
        user_id: int,
    ) -> None:
        """全量替换题目草稿版本解析"""
        existing = await self.get_all(db, revision_id)
        for item in existing:
            await self.delete_model(db, item.id)
        for item in items:
            db.add(
                QbQuestionExplanation(
                    question_revision_id=revision_id,
                    created_by=user_id,
                    **item.model_dump(),
                )
            )
        await db.flush()


class CRUDQuestionExternalRef(CRUDPlus[QbQuestionExternalRef]):
    """题目外部来源数据库操作类"""

    async def get_by_source(
        self,
        db: AsyncSession,
        *,
        owner_id: int | None,
        source_system: str,
        external_key: str,
    ) -> QbQuestionExternalRef | None:
        """按系统或用户私有来源键获取题目映射"""
        stmt = select(QbQuestionExternalRef).where(
            QbQuestionExternalRef.source_system == source_system,
            QbQuestionExternalRef.external_key == external_key,
            QbQuestionExternalRef.deleted == 0,
        )
        if owner_id is None:
            stmt = stmt.where(QbQuestionExternalRef.owner_id.is_(None))
        else:
            stmt = stmt.where(QbQuestionExternalRef.owner_id == owner_id)
        return (await db.execute(stmt)).scalars().first()

    async def create(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        owner_id: int | None,
        source_system: str,
        external_key: str,
        source_url: str | None,
        metadata: dict[str, Any],
        created_by: int,
    ) -> QbQuestionExternalRef:
        """创建题目来源映射"""
        external_ref = QbQuestionExternalRef(
            question_id=question_id,
            owner_id=owner_id,
            source_system=source_system,
            external_key=external_key,
            source_url=source_url,
            metadata_json=metadata,
            created_by=created_by,
        )
        db.add(external_ref)
        await db.flush()
        return external_ref


question_dao: CRUDQuestion = CRUDQuestion(QbQuestion)
question_revision_dao: CRUDQuestionRevision = CRUDQuestionRevision(QbQuestionRevision)
question_answer_dao: CRUDQuestionAnswer = CRUDQuestionAnswer(QbQuestionAnswer)
question_explanation_dao: CRUDQuestionExplanation = CRUDQuestionExplanation(QbQuestionExplanation)
question_external_ref_dao: CRUDQuestionExternalRef = CRUDQuestionExternalRef(QbQuestionExternalRef)
