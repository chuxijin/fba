
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.user_setting import JiaUserSetting
from backend.app.jia.schema.user_setting import UpdateUserSettingParam


class CRUDUserSetting(CRUDPlus[JiaUserSetting]):
    """用户设置 CRUD"""
    
    async def get_by_user_id(self, db: AsyncSession, user_id: int) -> JiaUserSetting | None:
        """
        根据用户ID获取设置
        """
        stmt = select(self.model).where(self.model.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create_default(self, db: AsyncSession, user_id: int) -> JiaUserSetting:
        """
        创建默认设置
        """
        obj = self.model(user_id=user_id)
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update_by_user_id(self, db: AsyncSession, user_id: int, obj: UpdateUserSettingParam) -> int:
        """
        根据用户ID更新设置
        """
        # 注意：这里需要先查出来ID再更新，或者直接 update(where user_id=...)
        # CRUDPlus 的 update_model 通常按主键更新
        # 这里为了简单，我们可以先获取对象，再更新。或者直接手写 update 语句。
        # 考虑到 Service 层逻辑，还是在 Service 处理“获取不到则创建”比较好。
        # 这里仅提供基于主键的 update (继承自 CRUDPlus) 
        # 但我们需要一个根据 user_id 更新的方法
        return await self.update_model(db, {'user_id': user_id}, obj)

user_setting_dao: CRUDUserSetting = CRUDUserSetting(JiaUserSetting)
