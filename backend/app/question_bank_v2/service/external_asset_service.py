import hashlib
import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.service.wrong_review_recognition_service import wrong_review_recognition_service
from backend.app.question_bank_v2.crud.crud_asset import asset_dao
from backend.app.question_bank_v2.schema.review import (
    GetExternalQuestionAssetUploadResult,
    RecognizeExternalWrongQuestionParam,
    RecognizeExternalWrongQuestionResult,
)
from backend.common.exception import errors
from backend.plugin.oss.service.storage_service import storage_service
from backend.utils.file_ops import upload_file_verify


class ExternalAssetService:
    """用户外部错题图片托管与结构化识别服务"""

    @staticmethod
    async def upload_image(
        *, db: AsyncSession, user_id: int, file: UploadFile
    ) -> GetExternalQuestionAssetUploadResult:
        upload_file_verify(file)
        mime_type = str(file.content_type or '').lower()
        if not mime_type.startswith('image/'):
            raise errors.RequestError(msg='错题资产仅支持图片文件')

        content = await file.read()
        if not content:
            raise errors.RequestError(msg='上传图片不能为空')
        await file.seek(0)
        url, object_key = await storage_service.upload(
            db=db,
            file=file,
            path=f'qbank-v2/users/{user_id}/wrong-questions',
            use_signed_url=False,
        )
        asset = await asset_dao.create_private_image(
            db,
            asset_key=f'usr.{user_id}.{uuid.uuid4().hex}',
            content_hash=hashlib.sha256(content).hexdigest(),
            mime_type=mime_type,
            size_bytes=len(content),
            original_name=file.filename,
            owner_id=user_id,
            url=url,
            object_key=object_key,
        )
        return GetExternalQuestionAssetUploadResult(
            asset_id=asset.id,
            url=url,
            object_key=object_key,
            mime_type=mime_type,
            size_bytes=len(content),
        )

    @staticmethod
    async def recognize(
        *, db: AsyncSession, obj: RecognizeExternalWrongQuestionParam
    ) -> RecognizeExternalWrongQuestionResult:
        result = await wrong_review_recognition_service.recognize(db=db, images=obj.images)
        return RecognizeExternalWrongQuestionResult(
            stem=result.stem,
            options=[item.model_dump() for item in result.options],
            answer=result.answer,
            explanation=result.explanation,
            warnings=result.warnings,
        )


external_asset_service: ExternalAssetService = ExternalAssetService()
