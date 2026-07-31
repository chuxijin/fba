from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_preference import practice_preference_dao
from backend.app.question_bank_v2.schema.preference import GetPracticePreferenceDetail, UpdatePracticePreferenceParam
from backend.common.exception import errors


class PreferenceService:
    """用户练习偏好服务类"""

    @staticmethod
    async def _check_timezone(*, data: dict) -> None:
        reminder_timezone = data.get('review_reminder_timezone')
        if reminder_timezone is not None:
            try:
                ZoneInfo(reminder_timezone)
            except ZoneInfoNotFoundError as exc:
                raise errors.RequestError(msg='提醒时区不是有效的 IANA 时区') from exc

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
        await PreferenceService._check_timezone(data=data)
        preference = await practice_preference_dao.get_by_user_id(db, user_id)
        if preference is None:
            preference = await practice_preference_dao.create(db, user_id=user_id, data=data)
        elif data:
            await practice_preference_dao.update(db, preference.id, user_id=user_id, data=data)
            preference = await practice_preference_dao.get_by_user_id(db, user_id)
        return GetPracticePreferenceDetail.model_validate(preference)


preference_service: PreferenceService = PreferenceService()
