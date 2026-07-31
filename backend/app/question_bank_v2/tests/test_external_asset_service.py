import asyncio

from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest

from fastapi import UploadFile

from backend.app.question_bank_v2.schema.review import RecognizeExternalWrongQuestionParam
from backend.app.question_bank_v2.service import external_asset_service as service_module
from backend.app.question_bank_v2.service.external_asset_service import ExternalAssetService


def test_upload_external_image_creates_v2_asset(monkeypatch: pytest.MonkeyPatch) -> None:
    """上传错题图片应同时写入对象存储和 V2 资产元数据。"""
    captured: dict[str, Any] = {}

    async def fake_upload(**kwargs: Any) -> tuple[str, str]:
        await asyncio.sleep(0)
        captured['upload'] = kwargs
        return 'https://cdn.example.com/wrong.png', 'qbank-v2/wrong.png'

    async def fake_create(_db: object, **kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0)
        captured['asset'] = kwargs
        return SimpleNamespace(id=91)

    monkeypatch.setattr(service_module.storage_service, 'upload', fake_upload)
    monkeypatch.setattr(service_module.asset_dao, 'create_private_image', fake_create)
    file = UploadFile(filename='wrong.png', file=BytesIO(b'png-content'), size=11)
    file.headers = {'content-type': 'image/png'}

    result = asyncio.run(ExternalAssetService.upload_image(db=None, user_id=7, file=file))

    assert result.asset_id == 91
    assert result.url == 'https://cdn.example.com/wrong.png'
    assert result.size_bytes == 11
    assert captured['asset']['owner_id'] == 7
    assert captured['asset']['content_hash']


def test_recognize_external_image_reuses_structured_vision(monkeypatch: pytest.MonkeyPatch) -> None:
    """V2 OCR 接口只适配识别草稿，不写 V1 错题数据。"""

    async def fake_recognize(**_kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(
            stem='题干',
            options=[SimpleNamespace(model_dump=lambda: {'option_code': 'A', 'content': '选项'})],
            answer='A',
            explanation='解析',
            warnings=[],
        )

    monkeypatch.setattr(service_module.wrong_review_recognition_service, 'recognize', fake_recognize)
    result = asyncio.run(
        ExternalAssetService.recognize(
            db=None,
            obj=RecognizeExternalWrongQuestionParam(images=['data:image/png;base64,YQ==']),
        )
    )

    assert result.stem == '题干'
    assert result.options[0].option_code == 'A'
    assert result.answer == 'A'
