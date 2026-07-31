from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from backend.common.schema import SchemaBase

FavoriteFolderStatus = Literal['active', 'archived']
NoteContentFormat = Literal['markdown', 'html', 'plain']
NoteVisibility = Literal['private', 'public']
NoteStatus = Literal['draft', 'published', 'hidden', 'rejected']


class ContentGroupNode(SchemaBase):
    """收藏或笔记统计分组节点"""

    id: int | None = Field(None, description='分组节点 ID')
    name: str = Field(description='分组名称')
    count: int = Field(ge=0, description='题目数量')
    bank_id: int | None = Field(None, description='章节节点所属题库 ID')
    type: Literal['collection'] | None = Field(None, description='合集节点类型；题库和章节为空')
    children: list['ContentGroupNode'] = Field(default_factory=list, description='子分组')


class CreateFavoriteFolderParam(SchemaBase):
    """创建收藏夹参数"""

    name: str = Field(min_length=1, max_length=100, description='收藏夹名称')
    description: str | None = Field(None, max_length=500, description='收藏夹说明')
    sort_order: int = Field(default=0, ge=0, description='用户内排序')


class UpdateFavoriteFolderParam(SchemaBase):
    """更新收藏夹参数"""

    name: str | None = Field(None, min_length=1, max_length=100, description='收藏夹名称')
    description: str | None = Field(None, max_length=500, description='收藏夹说明')
    sort_order: int | None = Field(None, ge=0, description='用户内排序')
    status: FavoriteFolderStatus | None = Field(None, description='收藏夹状态')


class GetFavoriteFolderDetail(SchemaBase):
    """收藏夹详情"""

    id: int = Field(description='收藏夹 ID')
    name: str = Field(description='收藏夹名称')
    description: str | None = Field(None, description='收藏夹说明')
    sort_order: int = Field(ge=0, description='用户内排序')
    status: FavoriteFolderStatus = Field(description='收藏夹状态')
    favorite_count: int = Field(default=0, ge=0, description='收藏数量')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class CreateQuestionFavoriteParam(SchemaBase):
    """收藏题目参数"""

    question_id: int = Field(gt=0, description='稳定题目 ID')
    folder_id: int | None = Field(None, gt=0, description='收藏夹 ID')
    bank_item_id: int | None = Field(None, gt=0, description='收藏时的题库编排项 ID')
    tags: list[str] = Field(default_factory=list, max_length=20, description='用户标签')
    remark: str | None = Field(None, max_length=500, description='收藏备注')
    is_pinned: bool = Field(default=False, description='是否置顶')

    @model_validator(mode='after')
    def normalize_tags(self) -> 'CreateQuestionFavoriteParam':
        """清理空标签并保持用户输入顺序去重"""
        self.tags = list(dict.fromkeys(item.strip() for item in self.tags if item.strip()))
        return self


class UpdateQuestionFavoriteParam(SchemaBase):
    """更新收藏参数"""

    folder_id: int | None = Field(None, gt=0, description='收藏夹 ID；显式传空表示移出收藏夹')
    tags: list[str] | None = Field(None, max_length=20, description='用户标签')
    remark: str | None = Field(None, max_length=500, description='收藏备注')
    is_pinned: bool | None = Field(None, description='是否置顶')

    @model_validator(mode='after')
    def normalize_tags(self) -> 'UpdateQuestionFavoriteParam':
        """清理空标签并保持用户输入顺序去重"""
        if self.tags is not None:
            self.tags = list(dict.fromkeys(item.strip() for item in self.tags if item.strip()))
        return self


class GetQuestionFavoriteDetail(SchemaBase):
    """题目收藏详情"""

    id: int = Field(description='收藏 ID')
    question_id: int = Field(description='稳定题目 ID')
    folder_id: int | None = Field(None, description='收藏夹 ID')
    folder_name: str | None = Field(None, description='收藏夹名称')
    bank_item_id: int | None = Field(None, description='题库编排项 ID')
    tags: list[str] = Field(default_factory=list, description='用户标签')
    remark: str | None = Field(None, description='收藏备注')
    is_pinned: bool = Field(description='是否置顶')
    pinned_time: datetime | None = Field(None, description='置顶时间')
    stem: str = Field(description='收藏时题干快照')
    question_type: str = Field(description='题型')
    difficulty: Decimal | None = Field(None, description='题目难度')
    created_time: datetime = Field(description='收藏时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class FavoriteStatistics(SchemaBase):
    """用户收藏统计"""

    total_count: int = Field(ge=0, description='收藏总数')
    folder_count: int = Field(ge=0, description='启用收藏夹数量')
    groups: list[ContentGroupNode] = Field(default_factory=list, description='题库或知识点分组')


class CreateQuestionNoteParam(SchemaBase):
    """创建题目笔记参数"""

    question_id: int = Field(gt=0, description='稳定题目 ID')
    bank_item_id: int | None = Field(None, gt=0, description='创建笔记时的题库编排项 ID')
    content: str = Field(min_length=1, description='笔记正文')
    content_format: NoteContentFormat = Field(default='markdown', description='正文格式')
    visibility: NoteVisibility = Field(default='private', description='可见范围')


class UpdateQuestionNoteParam(SchemaBase):
    """更新题目笔记参数"""

    content: str | None = Field(None, min_length=1, description='笔记正文')
    content_format: NoteContentFormat | None = Field(None, description='正文格式')
    visibility: NoteVisibility | None = Field(None, description='可见范围')


class GetQuestionNoteDetail(SchemaBase):
    """题目笔记详情"""

    id: int = Field(description='笔记 ID')
    user_id: int = Field(description='作者用户 ID')
    user_nickname: str | None = Field(None, description='作者昵称')
    question_id: int = Field(description='稳定题目 ID')
    bank_item_id: int | None = Field(None, description='题库编排项 ID')
    content: str = Field(description='笔记正文')
    content_format: NoteContentFormat = Field(description='正文格式')
    visibility: NoteVisibility = Field(description='可见范围')
    is_public: bool = Field(description='是否公开，供客户端直接展示')
    status: NoteStatus = Field(description='笔记状态')
    like_count: int = Field(ge=0, description='点赞数')
    dislike_count: int = Field(ge=0, description='点踩数')
    view_count: int = Field(ge=0, description='浏览数')
    is_featured: bool = Field(description='是否精选')
    my_vote: int | None = Field(None, description='当前用户投票：1 点赞，-1 点踩')
    stem: str | None = Field(None, description='笔记针对的题干')
    question_type: str | None = Field(None, description='题型')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class QuestionNoteVoteParam(SchemaBase):
    """公开笔记投票参数"""

    vote_value: Literal[-1, 0, 1] = Field(description='1 点赞，-1 点踩，0 取消投票')


class NoteStatistics(SchemaBase):
    """用户笔记统计"""

    total_count: int = Field(ge=0, description='笔记总数')
    public_count: int = Field(ge=0, description='公开笔记数')
    featured_count: int = Field(ge=0, description='精选笔记数')
    groups: list[ContentGroupNode] = Field(default_factory=list, description='题库或知识点分组')
