import base64
import json
import time

from io import BytesIO

import pytest

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import UploadFile

from backend.common.exception.errors import AuthorizationError, RequestError
from backend.core.conf import settings
from backend.plugin.wechat_media.service.media_service import WechatMediaService

TEST_SECRET_KEY = 'PxeCKsYCVMEItOMnluEkOFdG0/IDbOD4Vgws4hwWNBQ='


def _encrypt_payload(
    appid: str,
    appsecret: str,
    iat: int | None = None,
    key: str = TEST_SECRET_KEY,
) -> str:
    plaintext = json.dumps({
        'appid': appid,
        'appsecret': appsecret,
        'iat': int(time.time()) if iat is None else iat,
    }).encode('utf-8')
    nonce = b'0' * 12
    ciphertext = AESGCM(base64.b64decode(key)).encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode('utf-8')


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> WechatMediaService:
    monkeypatch.setattr(settings, 'WECHAT_MEDIA_SECRET_KEY', TEST_SECRET_KEY)
    return WechatMediaService()


def test_validate_image_accepts_jpg_and_png() -> None:
    WechatMediaService._validate_image(UploadFile(file=BytesIO(b'image'), filename='article.png'))
    WechatMediaService._validate_image(UploadFile(file=BytesIO(b'image'), filename='article.jpg'))


def test_validate_image_rejects_unsupported_extension() -> None:
    with pytest.raises(RequestError):
        WechatMediaService._validate_image(UploadFile(file=BytesIO(b'image'), filename='article.webp'))


def test_decrypt_credentials_roundtrip(service: WechatMediaService) -> None:
    payload = _encrypt_payload('wx123', 'secret456')
    assert service.decrypt_credentials(payload) == {'appid': 'wx123', 'appsecret': 'secret456'}


def test_decrypt_credentials_rejects_wrong_key(service: WechatMediaService) -> None:
    wrong_key = 'A' * 43 + '='
    payload = _encrypt_payload('wx123', 'secret456', key=wrong_key)
    with pytest.raises(AuthorizationError):
        service.decrypt_credentials(payload)


def test_decrypt_credentials_rejects_expired(service: WechatMediaService) -> None:
    payload = _encrypt_payload('wx123', 'secret456', iat=int(time.time()) - 3600)
    with pytest.raises(AuthorizationError):
        service.decrypt_credentials(payload)
