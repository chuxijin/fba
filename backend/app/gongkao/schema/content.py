from backend.app.content.schema.content import (
    ContentSchemaBase,
    CreateContentParam,
    GetContentDetail,
    UpdateContentParam,
)
from backend.app.content.schema.content import GetContentListDetails as GetContentListDetail  # 兼容旧名

__all__ = [
    'ContentSchemaBase',
    'CreateContentParam',
    'UpdateContentParam',
    'GetContentDetail',
    'GetContentListDetail',
]
