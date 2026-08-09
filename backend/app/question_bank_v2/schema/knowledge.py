from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

KnowledgePointRole = Literal['primary', 'secondary', 'prerequisite']
KnowledgePointSource = Literal['manual', 'import', 'ai']


class CreateKnowledgeSystemParam(SchemaBase):
    domain_category_id: int = Field(gt=0, description='所属领域分类 ID')
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=32)
    description: str | None = None
    status: Literal['draft', 'active', 'archived'] = 'active'


class UpdateKnowledgeSystemParam(SchemaBase):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    status: Literal['draft', 'active', 'archived'] | None = None


class CreateKnowledgePointParam(SchemaBase):
    code: str = Field(min_length=1, max_length=96)
    name: str = Field(min_length=1, max_length=160)
    parent_id: int | None = Field(None, gt=0)
    sort_order: int = 0
    description: str | None = None


class UpdateKnowledgePointParam(SchemaBase):
    name: str | None = Field(None, min_length=1, max_length=160)
    parent_id: int | None = Field(None, gt=0)
    sort_order: int | None = None
    description: str | None = None


class KnowledgePointAssignmentParam(SchemaBase):
    """题目版本知识点标注参数"""

    knowledge_point_id: int = Field(gt=0, description='知识点 ID')
    role: KnowledgePointRole = Field(default='primary', description='知识点角色')
    weight: Decimal = Field(default=Decimal('1.0000'), gt=0, le=1, description='贡献权重')
    source: KnowledgePointSource = Field(default='manual', description='标注来源')
    confidence: Decimal | None = Field(None, ge=0, le=1, description='自动标注置信度')


class GetKnowledgePointAssignmentDetail(KnowledgePointAssignmentParam):
    """题目版本知识点标注详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='知识点标注 ID')
    question_id: int = Field(description='题目稳定身份 ID')
    knowledge_point_name: str = Field(description='知识点名称')


class GetKnowledgeSystemListItem(SchemaBase):
    """知识体系列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='知识体系 ID')
    domain_category_id: int = Field(description='所属领域分类 ID')
    code: str = Field(description='知识体系编码')
    name: str = Field(description='知识体系名称')
    version: str = Field(description='体系版本')
    description: str | None = Field(None, description='体系说明')
    status: str = Field(description='体系状态')


class GetKnowledgePointTreeNode(SchemaBase):
    """带题量和用户进度的知识点树节点"""

    id: int = Field(description='知识点 ID')
    system_id: int = Field(description='知识体系 ID')
    code: str = Field(description='体系内唯一编码')
    name: str = Field(description='知识点名称')
    parent_id: int | None = Field(None, description='父知识点 ID')
    path: str | None = Field(None, description='物化路径缓存')
    depth: int = Field(ge=0, description='树深度')
    sort_order: int = Field(description='同层排序')
    description: str | None = Field(None, description='知识点说明')
    direct_question_count: int = Field(ge=0, description='直接标注到当前节点的题数')
    question_count: int = Field(ge=0, description='包含后代节点的题数')
    answered_count: int = Field(ge=0, description='已作答题数')
    correct_count: int = Field(ge=0, description='最近一次答对题数')
    mastered_count: int = Field(ge=0, description='已掌握题数')
    correct_rate: Decimal = Field(ge=0, le=1, description='最近作答正确率')
    mastery_score: Decimal = Field(ge=0, le=1, description='平均掌握度')
    children: list[GetKnowledgePointTreeNode] = Field(default_factory=list, description='子知识点')


class GetKnowledgeTreeDetail(SchemaBase):
    """知识点树与用户进度；限定题库时为该题库范围，否则跨全部可用题库"""

    system: GetKnowledgeSystemListItem = Field(description='知识体系')
    bank_id: int | None = Field(None, description='题库稳定身份 ID；跨题库聚合时为空')
    bank_revision_id: int | None = Field(None, description='题库当前发布版本 ID；跨题库聚合时为空')
    root_id: int | None = Field(None, description='限定的知识点根节点 ID')
    total_question_count: int = Field(ge=0, description='当前树题目总数')
    total_answered_count: int = Field(ge=0, description='当前树已作答题数')
    total_correct_count: int = Field(ge=0, description='当前树最近一次答对题数')
    points: list[GetKnowledgePointTreeNode] = Field(default_factory=list, description='知识点树')


class GetKnowledgePointNode(SchemaBase):
    """知识点树节点（纯结构，不含题量统计与进度）"""

    id: int = Field(description='知识点 ID')
    system_id: int = Field(description='知识体系 ID')
    code: str = Field(description='体系内唯一编码')
    name: str = Field(description='知识点名称')
    parent_id: int | None = Field(None, description='父知识点 ID')
    path: str | None = Field(None, description='物化路径缓存')
    depth: int = Field(ge=0, description='树深度')
    sort_order: int = Field(description='同层排序')
    description: str | None = Field(None, description='知识点说明')
    children: list[GetKnowledgePointNode] = Field(default_factory=list, description='子知识点')


class GetKnowledgePointTreeResult(SchemaBase):
    """知识点纯树结果，不含题库统计"""

    system: GetKnowledgeSystemListItem = Field(description='知识体系')
    points: list[GetKnowledgePointNode] = Field(default_factory=list, description='知识点树')
