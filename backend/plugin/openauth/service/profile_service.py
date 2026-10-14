from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.security.jwt import get_current_user
from backend.plugin.openauth.schema.profile import GetOpenAuthProfile


class OpenAuthProfileService:
    @staticmethod
    async def get_profile(db: AsyncSession, *, user_id: int) -> GetOpenAuthProfile:
        user = await get_current_user(db, user_id)

        # 会员闸门状态：延迟导入避免 plugin → app 反向硬依赖；
        # app.skill 未注册（被裁剪部署）时降级为未开通，不阻断资料返回
        can_use, deny_message = False, None
        try:
            from backend.app.skill.service import get_skill_entitlement_status

            can_use, deny_message = await get_skill_entitlement_status(db, user_id=user_id)
        except Exception:  # noqa: PERF203
            deny_message = None

        return GetOpenAuthProfile(
            user_id=user.id,
            nickname=user.nickname or '用户',
            avatar=user.avatar,
            can_use_skill=can_use,
            skill_deny_message=deny_message,
        )


openauth_profile_service = OpenAuthProfileService()
