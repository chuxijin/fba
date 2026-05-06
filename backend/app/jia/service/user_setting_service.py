
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_user_setting import user_setting_dao
from backend.app.jia.model.user_setting import JiaUserSetting
from backend.app.jia.schema.user_setting import UpdateUserSettingParam


class UserSettingService:
    """用户设置服务"""
    
    @staticmethod
    async def get_my_settings(*, db: AsyncSession, user_id: int) -> JiaUserSetting:
        """
        获取我的设置 (不存在则创建默认)
        """
        settings = await user_setting_dao.get_by_user_id(db, user_id)
        if not settings:
            settings = await user_setting_dao.create_default(db, user_id)
        return settings

    @staticmethod
    async def update_my_settings(*, db: AsyncSession, user_id: int, obj: UpdateUserSettingParam) -> JiaUserSetting:
        """
        更新我的设置
        """
        settings = await user_setting_dao.get_by_user_id(db, user_id)
        if not settings:
            settings = await user_setting_dao.create_default(db, user_id)
        
        # 更新
        # 使用 CRUDPlus 的 update_model 需要主键，或者我们手动把 obj 的字段赋给 settings
        update_data = obj.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(settings, key, value)
            
        await db.flush()
        await db.refresh(settings)
        return settings

user_setting_service: UserSettingService = UserSettingService()
