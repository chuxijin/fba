from typing import Literal

from pydantic import Field, model_validator

from backend.common.schema import SchemaBase


class TextAnnotation(SchemaBase):
    """文字范围使用渲染片段内 UTF-16 偏移，文本摘要防止内容变化后错位。"""

    id: str = Field(min_length=8, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    target: Literal['stem', 'material']
    material_id: int | None = Field(None, gt=0)
    material_revision_id: int | None = Field(None, gt=0)
    segment: int = Field(ge=0, le=10000)
    start: int = Field(ge=0, le=4_000_000)
    end: int = Field(gt=0, le=4_000_000)
    quote: str = Field(min_length=1, max_length=5000)
    text_hash: str = Field(pattern=r'^[0-9a-f]{8}$')
    note: str = Field(default='', max_length=500)

    @model_validator(mode='after')
    def validate_range(self) -> 'TextAnnotation':
        if self.end <= self.start:
            raise ValueError('标注结束位置必须大于起始位置')
        if (self.end - self.start) != len(self.quote.encode('utf-16-le')) // 2:
            raise ValueError('标注文字与范围长度不一致')
        if self.target == 'material' and (self.material_id is None or self.material_revision_id is None):
            raise ValueError('材料标注必须关联具体材料版本')
        if self.target == 'stem' and (self.material_id is not None or self.material_revision_id is not None):
            raise ValueError('题干标注不能关联材料')
        return self


class AnnotationContext(SchemaBase):
    session_key: str | None = Field(None, min_length=8, max_length=64)
    session_item_id: int | None = Field(None, gt=0)
    source: Literal['latest', 'wrong'] = 'latest'

    @model_validator(mode='after')
    def validate_context(self) -> 'AnnotationContext':
        if (self.session_key is None) != (self.session_item_id is None):
            raise ValueError('练习会话与投递题必须同时提供')
        return self


class SaveAnnotationsParam(AnnotationContext):
    owner_key: str | None = Field(
        None, pattern=r'^user:\d+$', description='读取时验证的账号，用于阻止切换账号后的迟到写入'
    )
    annotations: list[TextAnnotation] = Field(default_factory=list, max_length=100)
    save_version: int = Field(default=0, ge=0)
    context_key: str = Field(min_length=1, max_length=80)

    @model_validator(mode='after')
    def validate_ids(self) -> 'SaveAnnotationsParam':
        if len({item.id for item in self.annotations}) != len(self.annotations):
            raise ValueError('标注标识不能重复')
        return self


class GetAnnotationsDetail(SchemaBase):
    enabled: bool = Field(default=True, description='当前场景是否支持永久标注')
    owner_key: str = Field(description='已验证的所有者标识，用于隔离本机未同步草稿')
    context_key: str
    annotations: list[TextAnnotation] = Field(default_factory=list)
    original_annotations: list[TextAnnotation] = Field(
        default_factory=list, description='练习中为此前保存的标注，复盘中为当时作答快照'
    )
    save_version: int = 0
