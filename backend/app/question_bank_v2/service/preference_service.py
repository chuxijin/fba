from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.category import Category
from backend.app.question_bank_v2.crud.crud_preference import practice_preference_dao
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint
from backend.app.question_bank_v2.schema.preference import GetPracticePreferenceDetail, UpdatePracticePreferenceParam
from backend.common.exception import errors


class PreferenceService:
    """用户练习偏好服务类"""

    @staticmethod
    async def _validate_references(*, db: AsyncSession, data: dict) -> None:
        """校验偏好中的分类和知识点引用"""
        category_id = data.get('current_category_id')
        if category_id is not None:
            result = await db.execute(
                select(Category.id).where(
                    Category.id == category_id,
                    Category.deleted == 0,
                    Category.status.is_(True),
                )
            )
            if result.scalar_one_or_none() is None:
                raise errors.NotFoundError(msg='当前题库业务分类不存在或已停用')

        knowledge_point_id = data.get('current_knowledge_point_id')
        if knowledge_point_id is not None:
            result = await db.execute(
                select(QbKnowledgePoint.id).where(
                    QbKnowledgePoint.id == knowledge_point_id,
                    QbKnowledgePoint.deleted == 0,
                )
            )
            if result.scalar_one_or_none() is None:
                raise errors.NotFoundError(msg='当前知识点不存在')

    @staticmethod
    async def get(*, db: AsyncSession, user_id: int) -> GetPracticePreferenceDetail:
        """获取用户练习偏好，不存在时返回稳定默认值"""
        preference = await practice_preference_dao.get_by_user_id(db, user_id)
        if preference is None:
            return GetPracticePreferenceDetail()
        return GetPracticePreferenceDetail.model_validate(preference)

    @staticmethod
    async def update(
        *,
        db: AsyncSession,
        user_id: int,
        obj: UpdatePracticePreferenceParam,
    ) -> GetPracticePreferenceDetail:
        """创建或更新用户练习偏好"""
        data = obj.model_dump(exclude_unset=True)
        await PreferenceService._validate_references(db=db, data=data)
        preference = await practice_preference_dao.get_by_user_id(db, user_id)
        if preference is None:
            preference = await practice_preference_dao.create(db, user_id=user_id, data=data)
        elif data:
            await practice_preference_dao.update(db, preference.id, user_id=user_id, data=data)
            preference = await practice_preference_dao.get_by_user_id(db, user_id)
        return GetPracticePreferenceDetail.model_validate(preference)


preference_service: PreferenceService = PreferenceService()
