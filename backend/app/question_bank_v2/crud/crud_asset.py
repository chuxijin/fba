from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.asset import QbAsset, QbAssetLocation


class CRUDAsset(CRUDPlus[QbAsset]):
    """V2 题库资产数据库操作类"""

    async def create_private_image(
        self,
        db: AsyncSession,
        *,
        asset_key: str,
        content_hash: str,
        mime_type: str,
        size_bytes: int,
        original_name: str | None,
        owner_id: int,
        url: str,
        object_key: str,
    ) -> QbAsset:
        asset = QbAsset(
            asset_key=asset_key,
            content_hash=content_hash,
            mime_type=mime_type,
            size_bytes=size_bytes,
            owner_id=owner_id,
            original_name=original_name,
            visibility='private',
            status='ready',
            metadata_json={'url': url},
            created_by=owner_id,
        )
        db.add(asset)
        await db.flush()
        db.add(
            QbAssetLocation(
                asset_id=asset.id,
                provider='oss',
                object_key=object_key,
                namespace='',
                is_primary=True,
                status='available',
                created_by=owner_id,
            )
        )
        await db.flush()
        return asset


asset_dao: CRUDAsset = CRUDAsset(QbAsset)
