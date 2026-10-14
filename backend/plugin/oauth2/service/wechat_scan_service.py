# -*- coding: utf-8 -*-
"""
微信小程序扫码登录服务
用于支持浏览器扩展、PC Web 端与微信小程序的多端打通闭环：
1. 动态生成带 scene_id 的微信官方小程序码；
2. Redis 原子化状态流转与轮询监听；
3. 微信端扫码确认后，自动下发 JWT 凭证，同步打通用户题库资产。
"""

import base64
import json
import logging
from uuid import uuid4

import httpx
from fastapi import BackgroundTasks, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_user import user_dao
from backend.common.exception import errors
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.plugin.oauth2.service.oauth2_service import oauth2_service

logger = logging.getLogger(__name__)

SCAN_REDIS_PREFIX = "fba:oauth2:wechat_scan:"
ACCESS_TOKEN_CACHE_KEY = "fba:oauth2:miniapp_access_token"
DEFAULT_EXPIRES_SECONDS = 300


class WechatScanService:
    """微信小程序扫码登录中枢"""

    @staticmethod
    async def get_access_token() -> str:
        """获取并缓存微信小程序全局 access_token"""
        # 1. 尝试从 Redis 缓存获取
        cached = await redis_client.get(ACCESS_TOKEN_CACHE_KEY)
        if cached:
            return cached

        appid = getattr(settings, "WX_MINIAPP_APPID", "")
        secret = getattr(settings, "WX_MINIAPP_SECRET", "")
        if not appid or not secret:
            raise errors.ServerError(msg="微信小程序配置缺失，缺少 WX_MINIAPP_APPID 或 WX_MINIAPP_SECRET")

        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": appid,
            "secret": secret,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

            if "access_token" not in data:
                errcode = data.get("errcode")
                errmsg = data.get("errmsg", "未知错误")
                logger.error(f"获取微信小程序 access_token 失败 [{errcode}]: {errmsg}")
                raise errors.GatewayError(msg=f"微信接口授权失败: {errmsg}")

            token = data["access_token"]
            expires_in = int(data.get("expires_in", 7200))
            # 提前 300 秒刷新缓存，避免临界过期
            cache_ttl = max(60, expires_in - 300)
            await redis_client.set(ACCESS_TOKEN_CACHE_KEY, token, ex=cache_ttl)
            return token

    @staticmethod
    async def generate_scan_qrcode(page: str = "pages/index/index") -> dict:
        """
        生成带有唯一 scene_id 的微信官方小程序码
        """
        scene_id = f"fba_{uuid4().hex[:16]}"
        redis_key = f"{SCAN_REDIS_PREFIX}{scene_id}"

        # 初始状态设为 PENDING
        init_state = {"status": "PENDING", "created_at": settings.DATETIME_TIMEZONE}
        await redis_client.set(redis_key, json.dumps(init_state), ex=DEFAULT_EXPIRES_SECONDS)

        try:
            access_token = await WechatScanService.get_access_token()
            api_url = f"https://api.weixin.qq.com/wxa/getwxacodeunlimit?access_token={access_token}"
            payload = {
                "scene": scene_id,
                "page": page,
                "check_path": False,
                "width": 280,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(api_url, json=payload)
                content_type = resp.headers.get("content-type", "")

                # 微信接口返回二进制图片
                if "image" in content_type and len(resp.content) > 1000:
                    b64_img = base64.b64encode(resp.content).decode("utf-8")
                    qrcode_data_url = f"data:image/jpeg;base64,{b64_img}"
                else:
                    # 接口返回了 JSON 错误信息
                    try:
                        err_data = resp.json()
                        logger.warning(f"生成微信小程序码失败，微信返回: {err_data}")
                    except Exception:
                        pass
                    qrcode_data_url = WechatScanService._build_fallback_svg_qr(scene_id)
        except Exception as e:
            logger.warning(f"生成小程序码异常，降级为矢量扫码图: {e}")
            qrcode_data_url = WechatScanService._build_fallback_svg_qr(scene_id)

        return {
            "scene_id": scene_id,
            "qrcode_data_url": qrcode_data_url,
            "expires_in": DEFAULT_EXPIRES_SECONDS,
        }

    @staticmethod
    def _build_fallback_svg_qr(scene_id: str) -> str:
        """在外部接口异常时的轻量矢量扫码回退卡片"""
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="280" height="280" viewBox="0 0 280 280">
          <rect width="280" height="280" fill="#f8fafc" rx="16"/>
          <rect x="20" y="20" width="240" height="240" fill="#ffffff" rx="12" stroke="#e2e8f0" stroke-width="2"/>
          <circle cx="140" cy="115" r="48" fill="#ecfdf5"/>
          <path d="M125 115l10 10 25-25" stroke="#10b981" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          <text x="140" y="190" text-anchor="middle" font-family="sans-serif" font-size="15" font-weight="bold" fill="#0f172a">微信扫码快捷登录</text>
          <text x="140" y="215" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#64748b">小程序授权直登 · 资产实时同步</text>
          <text x="140" y="240" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#94a3b8">标识: {scene_id[:12]}</text>
        </svg>"""
        b64_svg = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64_svg}"

    @staticmethod
    async def get_scan_status(scene_id: str) -> dict:
        """插件端轮询检查扫码状态"""
        redis_key = f"{SCAN_REDIS_PREFIX}{scene_id}"
        val = await redis_client.get(redis_key)
        if not val:
            return {"status": "EXPIRED", "msg": "二维码已失效或过期，请刷新"}

        data = json.loads(val)
        status = data.get("status", "PENDING")

        if status == "CONFIRMED":
            # 确认登录后，返回 Token 并清理临时 Redis 锁
            await redis_client.delete(redis_key)
            return {
                "status": "CONFIRMED",
                "token": data.get("token"),
                "user": data.get("user"),
            }

        return {"status": status}

    @staticmethod
    async def confirm_scan(
        *,
        db: AsyncSession,
        response: Response,
        background_tasks: BackgroundTasks,
        scene_id: str,
        code: str,
        nickname: str | None = None,
        avatar: str | None = None,
    ) -> bool:
        """小程序端扫码后确认授权登录"""
        redis_key = f"{SCAN_REDIS_PREFIX}{scene_id}"
        val = await redis_client.get(redis_key)
        if not val:
            raise errors.NotFoundError(msg="扫码场景已过期或不存在，请在电脑端重新刷新二维码")

        # 调取微信标准登录流程，创建/关联用户并生成 Token
        token_info = await oauth2_service.wechat_miniapp_login(
            db=db,
            response=response,
            background_tasks=background_tasks,
            code=code,
            nickname=nickname,
            avatar=avatar,
        )

        # 回传给浏览器展示的真实账号资料，必须取登录结果里的昵称，
        # 否则扫码端会显示「微信用户」而库里是自动生成的默认昵称，两边对不上
        user_info = {
            "nickname": token_info.user.nickname,
            "avatar": str(token_info.user.avatar) if token_info.user.avatar else (avatar or ""),
        }

        # 更新 Redis 状态为 CONFIRMED
        confirmed_data = {
            "status": "CONFIRMED",
            "token": token_info.model_dump(),
            "user": user_info,
        }
        await redis_client.set(redis_key, json.dumps(confirmed_data), ex=120)
        return True

    @staticmethod
    async def mock_confirm_scan(
        *,
        scene_id: str,
        username: str | None = None,
        db: AsyncSession | None = None,
    ) -> dict:
        """
        开发与自动化测试专用：模拟手机微信扫码一键确认
        """
        redis_key = f"{SCAN_REDIS_PREFIX}{scene_id}"
        val = await redis_client.get(redis_key)
        if not val:
            raise errors.NotFoundError(msg="扫码场景已过期或不存在")

        # 获取任意测试用户或超级管理员
        user = None
        if db is not None:
            try:
                if username:
                    user = await user_dao.get_by_username(db, username)
                if not user:
                    from sqlalchemy import select
                    from backend.app.admin.model import User
                    res = await db.execute(select(User).limit(1))
                    user = res.scalar_one_or_none()
            except Exception as e:
                logger.warning(f"获取测试用户失败，采用虚拟测试账号兜底: {e}")
                user = None

        user_id = user.id if user else 9999
        is_multi_login = user.is_multi_login if user else True
        username_val = user.username if user else (username or "wx_test_student")
        nickname_val = (user.nickname or user.username) if user else "微信测试考生"
        avatar_val = (user.avatar or "") if user else ""

        from backend.common.security.token import create_access_token, create_refresh_token

        access_token_data = await create_access_token(user_id, multi_login=is_multi_login)
        refresh_token_data = await create_refresh_token(
            access_token_data.session_uuid,
            user_id,
            multi_login=is_multi_login,
        )

        token_dict = {
            "access_token": access_token_data.access_token,
            "access_token_expire_time": access_token_data.access_token_expire_time.isoformat(),
            "refresh_token": refresh_token_data.refresh_token,
            "refresh_token_expire_time": refresh_token_data.refresh_token_expire_time.isoformat(),
            "token_type": "Bearer",
        }

        user_dict = {
            "id": user_id,
            "username": username_val,
            "nickname": nickname_val,
            "avatar": avatar_val,
        }

        confirmed_data = {
            "status": "CONFIRMED",
            "token": token_dict,
            "user": user_dict,
        }
        await redis_client.set(redis_key, json.dumps(confirmed_data), ex=120)
        return {"status": "CONFIRMED", "user": user_dict}


wechat_scan_service = WechatScanService()
