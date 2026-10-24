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

from http.cookies import SimpleCookie
from uuid import uuid4

import httpx

from fastapi import BackgroundTasks, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_user import user_dao
from backend.app.admin.schema.token import GetLoginToken
from backend.app.admin.service.auth_service import auth_service
from backend.common.context import ctx
from backend.common.exception import errors
from backend.common.security.client import LoginClientType, refresh_cookie_key, set_refresh_cookie
from backend.common.security.jwt import jwt_decode
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
    async def generate_scan_qrcode(
        page: str = 'pages/index/index', *, client_type: LoginClientType = LoginClientType.web
    ) -> dict:
        """
        生成带有唯一 scene_id 的微信官方小程序码
        """
        scene_id = f"fba_{uuid4().hex[:16]}"
        redis_key = f"{SCAN_REDIS_PREFIX}{scene_id}"

        # 初始状态设为 PENDING
        if client_type not in {LoginClientType.web, LoginClientType.extension, LoginClientType.admin}:
            raise errors.RequestError(msg='该客户端不支持电脑扫码登录')
        init_state = {
            'status': 'PENDING', 'client_type': client_type.value,
            'session_info': {'ip': ctx.ip, 'os': ctx.os, 'browser': ctx.browser, 'device': ctx.device},
        }
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
          <path d="M125 115l10 10 25-25" stroke="#10b981" stroke-width="6"
                stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          <text x="140" y="190" text-anchor="middle" font-family="sans-serif"
                font-size="15" font-weight="bold" fill="#0f172a">微信扫码快捷登录</text>
          <text x="140" y="215" text-anchor="middle" font-family="sans-serif"
                font-size="11" fill="#64748b">小程序授权直登 · 资产实时同步</text>
          <text x="140" y="240" text-anchor="middle" font-family="sans-serif"
                font-size="10" fill="#94a3b8">标识: {scene_id[:12]}</text>
        </svg>"""
        b64_svg = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64_svg}"

    @staticmethod
    async def get_scan_status(
        scene_id: str, *, response: Response, client_type: LoginClientType = LoginClientType.web
    ) -> dict:
        """插件端轮询检查扫码状态"""
        redis_key = f"{SCAN_REDIS_PREFIX}{scene_id}"
        val = await redis_client.get(redis_key)
        if not val:
            return {"status": "EXPIRED", "msg": "二维码已失效或过期，请刷新"}

        data = json.loads(val)
        if data.get('client_type') != client_type:
            raise errors.RequestError(msg='扫码客户端不匹配，请刷新二维码')
        status = data.get("status", "PENDING")

        if status == "CONFIRMED":
            # 确认登录后，返回 Token 并清理临时 Redis 锁
            if await redis_client.getdel(redis_key) != val:
                return {'status': 'EXPIRED', 'msg': '二维码已被领取，请重新扫码'}
            refresh_token = data['refresh_token']
            payload = jwt_decode(refresh_token)
            set_refresh_cookie(response, client_type, refresh_token, payload.expire_time)
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
        async with redis_client.lock(f'{SCAN_REDIS_PREFIX}{scene_id}:lock', timeout=60, blocking_timeout=10):
            return await WechatScanService._confirm_scan(
                db=db, background_tasks=background_tasks, scene_id=scene_id,
                code=code, nickname=nickname, avatar=avatar,
            )

    @staticmethod
    async def _save_scan_result(scene_id: str, token_info: GetLoginToken, response: Response) -> None:
        cookies = SimpleCookie()
        for cookie in response.headers.getlist('set-cookie'):
            cookies.load(cookie)
        refresh_token = cookies[refresh_cookie_key(token_info.client_type)].value
        confirmed = {
            'status': 'CONFIRMED', 'client_type': str(token_info.client_type),
            'token': token_info.model_dump(mode='json'), 'refresh_token': refresh_token,
            'user': token_info.user.model_dump(mode='json', include={'id', 'username', 'nickname', 'avatar'}),
        }
        await redis_client.set(f'{SCAN_REDIS_PREFIX}{scene_id}', json.dumps(confirmed), ex=120)

    @staticmethod
    async def _confirm_scan(
        *, db: AsyncSession, background_tasks: BackgroundTasks, scene_id: str, code: str,
        nickname: str | None = None, avatar: str | None = None,
    ) -> bool:
        """小程序端扫码后确认授权登录"""
        redis_key = f"{SCAN_REDIS_PREFIX}{scene_id}"
        val = await redis_client.get(redis_key)
        if not val:
            raise errors.NotFoundError(msg="扫码场景已过期或不存在，请在电脑端重新刷新二维码")
        scene = json.loads(val)
        if scene.get('status') == 'CONFIRMED':
            return True
        if not scene.get('client_type'):
            raise errors.RequestError(msg='二维码版本已更新，请在电脑端刷新')
        client_type = LoginClientType(scene['client_type'])
        # 目标端刷新 Cookie 交给电脑轮询领取，不能写进手机的确认响应。
        login_response = Response()

        # 调取微信标准登录流程，创建/关联用户并生成 Token
        token_info = await oauth2_service.wechat_miniapp_login(
            db=db,
            response=login_response,
            background_tasks=background_tasks,
            code=code,
            nickname=nickname,
            avatar=avatar,
            client_type=client_type,
            session_info=scene.get('session_info'),
        )
        await WechatScanService._save_scan_result(scene_id, token_info, login_response)
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
        # 生产环境禁止使用：否则任何人无需真实微信授权即可拿到有效令牌
        if settings.ENVIRONMENT == 'prod':
            raise errors.NotFoundError(msg='扫码模拟接口仅用于开发与测试环境')

        redis_key = f"{SCAN_REDIS_PREFIX}{scene_id}"
        val = await redis_client.get(redis_key)
        if not val:
            raise errors.NotFoundError(msg="扫码场景已过期或不存在")

        # 必须解析到真实用户：不允许用不存在的 user_id 兜底签 token
        if db is None:
            raise errors.RequestError(msg='扫码模拟接口缺少数据库会话')
        user = None
        if username:
            user = await user_dao.get_by_username(db, username)
        if not user:
            from sqlalchemy import select

            from backend.app.admin.model import User
            res = await db.execute(select(User).limit(1))
            user = res.scalar_one_or_none()
        if user is None:
            raise errors.NotFoundError(msg='未找到可用于模拟登录的测试用户')

        async with redis_client.lock(f'{redis_key}:lock', timeout=60, blocking_timeout=10):
            current = await redis_client.get(redis_key)
            if not current:
                raise errors.NotFoundError(msg='扫码场景已过期')
            scene = json.loads(current)
            if scene.get('status') == 'CONFIRMED':
                return {'status': 'CONFIRMED', 'user': scene['user']}
            response = Response()
            token_info = await auth_service.issue_login_token(
                db=db, response=response, user=user,
                client_type=LoginClientType(scene['client_type']), session_info=scene.get('session_info'),
            )
            await WechatScanService._save_scan_result(scene_id, token_info, response)
        return {'status': 'CONFIRMED', 'user': {'id': user.id, 'username': user.username}}


wechat_scan_service = WechatScanService()
