from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.schema.study_goal import EXAM_TARGET_DICT_CODE
from backend.plugin.dict.model.dict_data import DictData
from backend.plugin.dict.model.dict_type import DictType


class CRUDStudyGoal:
    """读取有效字典目录；不缓存 ORM，避免配置编辑后仍用旧模板开考。"""

    @staticmethod
    async def get_targets(db: AsyncSession, code: str | None = None) -> Sequence[DictData]:
        stmt = (
            select(DictData)
            .join(DictType, DictType.id == DictData.type_id)
            .where(
                DictType.code == EXAM_TARGET_DICT_CODE,
                DictType.deleted == 0,
                DictData.type_code == EXAM_TARGET_DICT_CODE,
                DictData.deleted == 0,
                DictData.status == 1,
            )
            .order_by(DictData.sort, DictData.id)
        )
        if code is not None:
            stmt = stmt.where(DictData.value == code)
        return (await db.execute(stmt)).scalars().all()


study_goal_dao = CRUDStudyGoal()
