from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from backend.common.schema import SchemaBase

BankKind = Literal['practice', 'paper', 'mock']
BankStatus = Literal['active', 'disabled', 'archived']
BankVisibility = Literal['private', 'internal', 'public']
RevisionStatus = Literal['draft', 'published', 'retired']


class BankRevisionSchemaBase(SchemaBase):
    """题库版本内容基础模型"""

    name: str = Field(min_length=1, max_length=160, description='题库名称')
    bank_kind: BankKind = Field(default='practice', description='题库用途类型')
    description: str | None = Field(None, description='题库描述')
    cover_asset_id: int | None = Field(None, gt=0, description='托管封面资产 ID')
    cover_url: str | None = Field(None, max_length=1024, description='题库封面地址')
    duration_minutes: int | None = Field(None, gt=0, description='限时分钟数')
    pass_score: Decimal | None = Field(None, ge=0, description='及格分')
    settings: dict[str, Any] = Field(default_factory=dict, description='版本级抽题、展示和交卷策略')


class CreateBankRevisionParam(BankRevisionSchemaBase):
    """创建题库草稿版本参数"""


class UpdateBankRevisionParam(SchemaBase):
    """更新题库草稿版本参数"""

    name: str | None = Field(None, min_length=1, max_length=160, description='题库名称')
    bank_kind: BankKind | None = Field(None, description='题库用途类型')
    description: str | None = Field(None, description='题库描述')
    cover_asset_id: int | None = Field(None, gt=0, description='托管封面资产 ID')
    cover_url: str | None = Field(None, max_length=1024, description='题库封面地址')
    duration_minutes: int | None = Field(None, gt=0, description='限时分钟数')
    pass_score: Decimal | None = Field(None, ge=0, description='及格分')
    settings: dict[str, Any] | None = Field(None, description='版本级抽题、展示和交卷策略')


class CreateBankParam(SchemaBase):
    """创建题库及首个草稿版本参数"""

    code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$', description='稳定业务编码')
    visibility: BankVisibility = Field(default='public', description='题库可见范围')
    status: BankStatus = Field(default='active', description='题库身份状态')
    revision: CreateBankRevisionParam = Field(description='首个草稿版本')
    category_ids: list[int] = Field(default_factory=list, description='题库所属业务分类 ID 列表')
    primary_category_id: int | None = Field(None, gt=0, description='题库主分类 ID')

    @model_validator(mode='after')
    def validate_categories(self) -> 'CreateBankParam':
        """校验主分类属于分类列表并去重"""
        self.category_ids = list(dict.fromkeys(self.category_ids))
        if self.primary_category_id is not None and self.primary_category_id not in self.category_ids:
            raise ValueError('主分类必须包含在分类列表中')
        return self


class UpdateBankParam(SchemaBase):
    """更新题库稳定身份参数"""

    code: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$',
        description='稳定业务编码',
    )
    visibility: BankVisibility | None = Field(None, description='题库可见范围')
    status: BankStatus | None = Field(None, description='题库身份状态')


class SetBankCategoriesParam(SchemaBase):
    """设置题库业务分类参数"""

    category_ids: list[int] = Field(default_factory=list, description='题库所属业务分类 ID 列表')
    primary_category_id: int | None = Field(None, gt=0, description='题库主分类 ID')

    @model_validator(mode='after')
    def validate_categories(self) -> 'SetBankCategoriesParam':
        """校验主分类属于分类列表并去重"""
        self.category_ids = list(dict.fromkeys(self.category_ids))
        if self.primary_category_id is not None and self.primary_category_id not in self.category_ids:
            raise ValueError('主分类必须包含在分类列表中')
        return self


class GetBankCategoryDetail(SchemaBase):
    """题库分类关联详情"""

    category_id: int = Field(description='系统业务分类 ID')
    category_name: str = Field(description='系统业务分类名称')
    is_primary: bool = Field(description='是否题库主分类')
    sort_order: int = Field(description='分类内题库排序')


class GetBankRevisionDetail(BankRevisionSchemaBase):
    """题库版本详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题库版本 ID')
    bank_id: int = Field(description='题库稳定身份 ID')
    revision_no: int = Field(description='题库版本号')
    question_count: int = Field(description='发布题量快照')
    total_score: Decimal = Field(description='发布总分快照')
    content_hash: str | None = Field(None, description='编排内容 SHA-256')
    status: RevisionStatus = Field(description='版本状态')
    published_by: int | None = Field(None, description='发布人 ID')
    published_time: datetime | None = Field(None, description='发布时间')
    created_by: int = Field(description='创建者 ID')
    updated_by: int | None = Field(None, description='修改者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetBankDetail(SchemaBase):
    """题库聚合详情"""

    id: int = Field(description='题库稳定身份 ID')
    code: str = Field(description='稳定业务编码')
    owner_id: int | None = Field(None, description='私有题库所有者 ID')
    current_revision_id: int | None = Field(None, description='当前发布版本 ID')
    visibility: BankVisibility = Field(description='题库可见范围')
    status: BankStatus = Field(description='题库身份状态')
    current_revision: GetBankRevisionDetail | None = Field(None, description='当前发布版本')
    categories: list[GetBankCategoryDetail] = Field(default_factory=list, description='题库业务分类列表')
    created_by: int = Field(description='创建者 ID')
    updated_by: int | None = Field(None, description='修改者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetBankListItem(SchemaBase):
    """题库列表项"""

    id: int = Field(description='题库稳定身份 ID')
    code: str = Field(description='稳定业务编码')
    visibility: BankVisibility = Field(description='题库可见范围')
    status: BankStatus = Field(description='题库身份状态')
    revision_id: int = Field(description='当前发布版本 ID')
    revision_no: int = Field(description='当前发布版本号')
    name: str = Field(description='题库名称')
    bank_kind: BankKind = Field(description='题库用途类型')
    description: str | None = Field(None, description='题库描述')
    cover_url: str | None = Field(None, description='题库封面地址')
    duration_minutes: int | None = Field(None, description='限时分钟数')
    pass_score: Decimal | None = Field(None, description='及格分')
    question_count: int = Field(description='题量快照')
    total_score: Decimal = Field(description='总分快照')
    primary_category_id: int | None = Field(None, description='主分类 ID')
    primary_category_name: str | None = Field(None, description='主分类名称')
