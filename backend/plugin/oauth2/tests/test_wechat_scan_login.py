# -*- coding: utf-8 -*-
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.anyio
async def test_wechat_scan_login_full_lifecycle():
    """测试微信小程序扫码登录全生命周期闭环"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. 客户端请求生成二维码
        res_qr = await client.get("/api/v1/oauth2/wechat/scan/qrcode")
        assert res_qr.status_code == 200
        qr_json = res_qr.json()
        assert qr_json["code"] == 200
        data = qr_json["data"]
        scene_id = data["scene_id"]
        assert scene_id.startswith("fba_")
        assert data["qrcode_data_url"].startswith("data:image/")
        assert data["expires_in"] == 300
        print(f"\n[✓] 成功生成扫码场景: {scene_id}, 图片有效")

        # 2. 轮询状态，应为 PENDING
        res_status_1 = await client.get(f"/api/v1/oauth2/wechat/scan/status?scene_id={scene_id}")
        assert res_status_1.status_code == 200
        status_json_1 = res_status_1.json()
        assert status_json_1["code"] == 200
        assert status_json_1["data"]["status"] == "PENDING"
        print("[✓] 初始轮询状态正常: PENDING")

        # 3. 模拟手机小程序端确认扫码
        res_confirm = await client.post(
            "/api/v1/oauth2/wechat/scan/mock_confirm",
            json={"scene_id": scene_id},
        )
        assert res_confirm.status_code == 200
        confirm_json = res_confirm.json()
        assert confirm_json["code"] == 200
        assert confirm_json["data"]["status"] == "CONFIRMED"
        print(f"[✓] 模拟手机微信确认登录成功，绑定用户: {confirm_json['data']['user']['username']}")

        # 4. 再次轮询状态，应为 CONFIRMED 并获取 Token
        res_status_2 = await client.get(f"/api/v1/oauth2/wechat/scan/status?scene_id={scene_id}")
        assert res_status_2.status_code == 200
        status_json_2 = res_status_2.json()
        assert status_json_2["code"] == 200
        assert status_json_2["data"]["status"] == "CONFIRMED"
        token_info = status_json_2["data"]["token"]
        assert "access_token" in token_info
        print("[✓] 插件轮询顺利获得登录 Token，全生命周期校验通过！")
