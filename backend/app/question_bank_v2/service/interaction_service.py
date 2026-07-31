from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_material import (
    material_anchor_dao,
    question_interaction_dao,
    question_material_dao,
)
from backend.app.question_bank_v2.schema.material import (
    CreateQuestionInteractionParam,
    GetQuestionInteractionDetail,
    UpdateQuestionInteractionParam,
)
from backend.common.exception import errors


class InteractionService:
    """题目交互定义服务类"""

    @staticmethod
    async def _resolve_material_revision(
        *,
        db: AsyncSession,
        question_id: int,
        obj: CreateQuestionInteractionParam,
    ) -> int | None:
        """校验题目材料上下文和同版本候选锚点"""
        if obj.question_material_id is None:
            return None
        relation = await question_material_dao.get(db, obj.question_material_id, question_id=question_id)
        if relation is None:
            raise errors.NotFoundError(msg='题目材料关联不存在')
        anchor_ids = [item.anchor_id for item in obj.candidates]
        anchors = await material_anchor_dao.get_many(
            db,
            material_revision_id=relation.material_revision_id,
            anchor_ids=anchor_ids,
        )
        if len(anchors) != len(set(anchor_ids)):
            raise errors.NotFoundError(msg='部分候选锚点不存在或不属于题目材料版本')
        if any(anchor.status == 'retired' for anchor in anchors):
            raise errors.ConflictError(msg='已退役材料锚点不能用于交互定义')
        return relation.material_revision_id

    @staticmethod
    async def get_all(
        *,
        db: AsyncSession,
        question_id: int | None = None,
    ) -> list[GetQuestionInteractionDetail]:
        """获取题目交互定义"""
        q_ids = [question_id] if question_id is not None else None
        rows = await question_interaction_dao.get_all(db, question_ids=q_ids)
        return [GetQuestionInteractionDetail(**row) for row in rows]

    @staticmethod
    async def create(
        *,
        db: AsyncSession,
        question_id: int,
        obj: CreateQuestionInteractionParam,
        user_id: int,
    ) -> GetQuestionInteractionDetail:
        """创建题目交互定义"""
        if await question_interaction_dao.get_by_key(
            db,
            question_id=question_id,
            interaction_key=obj.interaction_key,
        ):
            raise errors.ConflictError(msg='题目内交互键已存在')
        material_revision_id = await InteractionService._resolve_material_revision(
            db=db,
            question_id=question_id,
            obj=obj,
        )
        interaction = await question_interaction_dao.create(
            db,
            question_id=question_id,
            material_revision_id=material_revision_id,
            obj=obj,
            user_id=user_id,
        )
        rows = await question_interaction_dao.get_all(db, question_ids=[question_id])
        row = next(item for item in rows if item['id'] == interaction.id)
        return GetQuestionInteractionDetail(**row)

    @staticmethod
    async def update(
        *,
        db: AsyncSession,
        question_id: int,
        interaction_id: int,
        obj: UpdateQuestionInteractionParam,
        user_id: int,
    ) -> GetQuestionInteractionDetail:
        """全量更新题目交互定义"""
        interaction = await question_interaction_dao.get(db, interaction_id, question_id=question_id)
        if interaction is None:
            raise errors.NotFoundError(msg='交互定义不存在')
        duplicate = await question_interaction_dao.get_by_key(
            db,
            question_id=question_id,
            interaction_key=obj.interaction_key,
        )
        if duplicate is not None and duplicate.id != interaction_id:
            raise errors.ConflictError(msg='题目内交互键已存在')
        material_revision_id = await InteractionService._resolve_material_revision(
            db=db,
            question_id=question_id,
            obj=obj,
        )
        await question_interaction_dao.update_definition(
            db,
            interaction=interaction,
            material_revision_id=material_revision_id,
            obj=obj,
            user_id=user_id,
        )
        rows = await question_interaction_dao.get_all(db, question_ids=[question_id])
        row = next(item for item in rows if item['id'] == interaction_id)
        return GetQuestionInteractionDetail(**row)

    @staticmethod
    async def delete(
        *,
        db: AsyncSession,
        question_id: int,
        interaction_id: int,
    ) -> None:
        """删除题目交互定义"""
        interaction = await question_interaction_dao.get(db, interaction_id, question_id=question_id)
        if interaction is not None:
            await question_interaction_dao.delete_model(db, interaction_id)

    @staticmethod
    async def ensure_publishable(
        *,
        db: AsyncSession,
        question_id: int,
        question_type: str,
    ) -> list[GetQuestionInteractionDetail]:
        """校验交互定义完整并返回纳入内容哈希的数据"""
        rows = await question_interaction_dao.get_all(db, question_ids=[question_id])
        interactions = [GetQuestionInteractionDetail(**row) for row in rows]
        if any(item.status == 'draft' for item in interactions):
            raise errors.ConflictError(msg='题目仍有未启用的草稿交互定义')
        active = [item for item in interactions if item.status == 'active']
        if question_type == 'interactive' and not active:
            raise errors.ConflictError(msg='交互题至少需要一个已启用交互定义')
        for interaction in active:
            if len(interaction.candidates) < interaction.min_selections:
                raise errors.ConflictError(msg='交互定义候选数量少于最少选择数')
            if any(candidate.anchor.status != 'active' for candidate in interaction.candidates):
                raise errors.ConflictError(msg='交互定义包含未启用的材料锚点')
        return active


interaction_service: InteractionService = InteractionService()