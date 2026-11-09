from pydantic import Field

from backend.common.schema import SchemaBase


class HighErrorSection(SchemaBase):
    id: int
    name: str
    parent_id: int | None = None
    depth: int = Field(ge=0)
    sort_order: int
    question_count: int = Field(ge=0, description='包含后代的去重题量')
    low_accuracy_count: int = Field(ge=0)
    slow_count: int = Field(ge=0)
    children: list['HighErrorSection'] = Field(default_factory=list)


class GetBankHighErrorSections(SchemaBase):
    bank_id: int
    bank_revision_id: int
    total_count: int = Field(ge=0)
    low_accuracy_count: int = Field(ge=0)
    slow_count: int = Field(ge=0)
    unsectioned_count: int = Field(ge=0)
    sections: list[HighErrorSection] = Field(default_factory=list)
