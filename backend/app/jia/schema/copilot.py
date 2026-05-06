from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.common.schema import SchemaBase

# --- Session Schemas ---

class CopilotSessionSchemaBase(SchemaBase):
    title: str | None = Field(default=None, description="会话标题")
    model: str | None = Field(default="gpt-5.1", description="模型")
    assistant_type: str | None = Field(default="home", description="助手类型: home/food/exercise")

class CreateSessionParam(CopilotSessionSchemaBase):
    pass

class UpdateSessionParam(CopilotSessionSchemaBase):
    pass

class GetSessionListResponse(CopilotSessionSchemaBase):
    id: int
    user_id: int
    created_time: datetime
    updated_time: datetime | None = None
    
    model_config = ConfigDict(from_attributes=True)


# --- Chat/Message Schemas ---

# --- Chat/Message Schemas ---

class ChatAttachment(BaseModel):
    type: str = Field(..., description="类型: image, file")
    url: str = Field(..., description="文件URL")
    name: str | None = None

class MessageSchema(BaseModel):
    id: int | None = None
    role: str = Field(..., description="角色: user/assistant/tool")
    content: str | None = Field(default=None, description="内容")
    
    attachments: list[ChatAttachment] | None = Field(default=None, description="附件")
    tool_calls: list[dict] | None = Field(default=None, description="工具调用请求")
    tool_call_id: str | None = Field(default=None, description="工具调用ID")
    
    meta: dict | None = Field(default=None, description="元数据")
    created_time: datetime | None = None
    
    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    session_id: int | None = Field(default=None, description="会话ID (新会话可不传)")
    query: str | None = Field(default=None, description="用户问题")
    attachments: list[ChatAttachment] | None = Field(default=None, description="包含图片/文件")
    model: str | None = Field(default="gpt-5.1", description="模型")
    assistant_type: str | None = Field(default="home", description="助手类型: home/food/exercise")
    context_count: int | None = Field(default=10, description="上下文轮数")

class ChatResponse(BaseModel):
    session_id: int
    text: str | None = Field(default=None, description="AI 回复文本")
    meta: dict | None = Field(default=None, description="结构化数据 (如生成的计划)")

    tool_calls: list[dict] | None = Field(default=None, description="工具调用")

    # 方便前端展示历史
    message_id: int | None = None


# --- 智能识别物品 Schemas ---

class AnalyzeItemRequest(BaseModel):
    image_url: str | None = Field(default=None, description="图片完整URL")
    text: str | None = Field(default=None, description="用户语音/文字描述")
    audio_path: str | None = Field(default=None, description="音频文件路径（用于语音识别）")


class AnalyzeItemResponse(BaseModel):
    name: str | None = Field(default=None, description="物品名称")
    category: str | None = Field(default=None, description="分类")
    description: str | None = Field(default=None, description="描述（外观、用途、使用场景）")
    quantity: int | None = Field(default=None, description="数量")
    standard_quantity: int | None = Field(default=None, description="标准数量（一个人建议拥有几个）")
    consume_days: int | None = Field(default=None, description="消耗/更换周期（天）")
    price: float | None = Field(default=None, description="市场参考价格")
    expire_date: str | None = Field(default=None, description="保质期 (YYYY-MM-DD)")
    notes: str | None = Field(default=None, description="备注")


# --- 公式识别 Schemas ---

class RecognizeFormulaRequest(BaseModel):
    image_url: str = Field(..., description="公式图片完整URL")


class RecognizeFormulaResponse(BaseModel):
    formula: str = Field(default='', description="识别出的 LaTeX 公式")
    confidence: str | None = Field(default=None, description="置信度描述")


# --- 智能识别食物 Schemas ---

class AnalyzeFoodRequest(BaseModel):
    image_url: str | None = Field(default=None, description="图片完整URL")
    text: str | None = Field(default=None, description="用户文字描述")


class AnalyzeFoodResponse(BaseModel):
    name: str | None = Field(default=None, description="食物名称")
    alias: str | None = Field(default=None, description="别名（逗号分隔）")
    description: str | None = Field(default=None, description="详细描述")
    serving_size: float | None = Field(default=None, description="份量大小")
    serving_unit: str | None = Field(default=None, description="份量单位 (g/ml)")
    energy: float | None = Field(default=None, description="能量 (kcal)")
    protein: float | None = Field(default=None, description="蛋白质 (g)")
    carbohydrate: float | None = Field(default=None, description="碳水化合物 (g)")
    fat: float | None = Field(default=None, description="脂肪 (g)")
    water: float | None = Field(default=None, description="水分 (g)")
    fiber: float | None = Field(default=None, description="膳食纤维 (g)")
    sodium: float | None = Field(default=None, description="钠 (mg)")
    notes: str | None = Field(default=None, description="备注")
