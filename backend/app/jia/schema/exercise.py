from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ExerciseSchemaBase(SchemaBase):
    name_zh: str | None = Field(default=None, description="动作名称(中文)")
    name_en: str | None = Field(default=None, description="动作名称(英文)")
    category: str | None = Field(default=None, description="分类")
    difficulty: str | None = Field(default=None, description="难度")
    mechanic: str | None = Field(default=None, description="动作机制")
    force: str | None = Field(default=None, description="发力方向")
    equipment: str | None = Field(default=None, description="器材")
    met_value: float | None = Field(default=None, description="代谢当量(MET)")
    primary_muscles: list[str] | None = Field(default=None, description="主要肌肉群(中文)")
    secondary_muscles: list[str] | None = Field(default=None, description="次要肌肉群(中文)")
    images: list[str] | None = Field(default=None, description="动作图片")
    instructions: list[str] | None = Field(default=None, description="中文说明")
    instructions_en: list[str] | None = Field(default=None, description="英文说明")

class CreateExerciseParam(ExerciseSchemaBase):
    name_zh: str = Field(..., description="动作名称(中文)")
    category: str = Field(..., description="分类")

class UpdateExerciseParam(ExerciseSchemaBase):
    pass

class GetExerciseListResponse(ExerciseSchemaBase):
    id: int
    created_time: datetime
    updated_time: datetime | None = None
    
    model_config = ConfigDict(from_attributes=True)
