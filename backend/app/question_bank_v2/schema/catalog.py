from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from backend.app.question_bank_v2.schema.bank import GetBankListItem
from backend.common.schema import SchemaBase

CollectionStatus = Literal['draft', 'active', 'archived']
CollectionVisibility = Literal['private', 'internal', 'public']


class CollectionSchemaBase(SchemaBase):
    """题库合集基础模型"""

    code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$', description='合集业务编码')
    name: str = Field(min_length=1, max_length=128, description='合集名称')
    parent_id: int | None = Field(None, gt=0, description='父合集 ID')
    description: str | None = Field(None, description='合集描述')
    visibility: CollectionVisibility = Field(default='public', description='合集可见范围')
    status: CollectionStatus = Field(default='draft', description='合集状态')
    sort_order: int = Field(default=0, description='同层排序')


class CreateCollectionParam(CollectionSchemaBase):
    """创建题库合集参数"""


class UpdateCollectionParam(SchemaBase):
    """更新题库合集参数"""

    code: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$',
        description='合集业务编码',
    )
    name: str | None = Field(None, min_length=1, max_length=128, description='合集名称')
    parent_id: int | None = Field(None, gt=0, description='父合集 ID')
    description: str | None = Field(None, description='合集描述')
    visibility: CollectionVisibility | None = Field(None, description='合集可见范围')
    status: CollectionStatus | None = Field(None, description='合集状态')
    sort_order: int | None = Field(None, description='同层排序')


class GetCollectionDetail(CollectionSchemaBase):
    """题库合集详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='合集 ID')
    owner_id: int | None = Field(None, description='私有合集所有者 ID')
    created_by: int = Field(description='创建者 ID')
    updated_by: int | None = Field(None, description='修改者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class CollectionBankMountSchemaBase(SchemaBase):
    """合集题库挂载基础模型"""

    bank_id: int = Field(gt=0, description='题库稳定身份 ID')
    bank_revision_id: int | None = Field(None, gt=0, description='固定展示的题库版本 ID')
    follow_latest: bool = Field(default=True, description='是否跟随题库当前发布版本')
    display_name: str | None = Field(None, max_length=128, description='合集内展示别名')
    sort_order: int = Field(default=0, description='合集内排序')
    is_active: bool = Field(default=True, description='是否启用此挂载')


class CreateCollectionBankMountParam(CollectionBankMountSchemaBase):
    """创建合集题库挂载参数"""


class UpdateCollectionBankMountParam(SchemaBase):
    """更新合集题库挂载参数"""

    bank_revision_id: int | None = Field(None, gt=0, description='固定展示的题库版本 ID')
    follow_latest: bool | None = Field(None, description='是否跟随题库当前发布版本')
    display_name: str | None = Field(None, max_length=128, description='合集内展示别名')
    sort_order: int | None = Field(None, description='合集内排序')
    is_active: bool | None = Field(None, description='是否启用此挂载')


class GetCollectionBankMountDetail(CollectionBankMountSchemaBase):
    """合集题库挂载详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='挂载 ID')
    collection_id: int = Field(description='合集 ID')
    created_by: int = Field(description='创建者 ID')
    updated_by: int | None = Field(None, description='修改者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetCollectionCatalogItem(SchemaBase):
    """公开题库合集目录项"""

    id: int = Field(description='合集 ID')
    code: str = Field(description='合集业务编码')
    name: str = Field(description='合集名称')
    parent_id: int | None = Field(None, description='父合集 ID')
    description: str | None = Field(None, description='合集描述')
    sort_order: int = Field(description='同层排序')
    banks: list[GetBankListItem] = Field(default_factory=list, description='合集内可用题库列表')
    children: list['GetCollectionCatalogItem'] = Field(default_factory=list, description='子合集列表')
