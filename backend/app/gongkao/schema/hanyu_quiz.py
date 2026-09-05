#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel, ConfigDict, Field
from backend.app.gongkao.schema.hanyu_review import HanyuGroupOut


class QuizOption(BaseModel):
    """测验选项"""
    model_config = ConfigDict(from_attributes=True)

    key: str = Field(description='选项标识 (A/B/C/D)')
    content: str = Field(description='选项文本（成语词名或释义文本）')
    hanyu_id: int | None = Field(default=None, description='关联词汇 ID')
    is_correct: bool = Field(description='是否为正确答案')


class QuizQuestion(BaseModel):
    """测验题目"""
    model_config = ConfigDict(from_attributes=True)

    question_id: int = Field(description='题号索引 (1, 2, ...)')
    quiz_type: str = Field(description='模式: meaning_to_word (看释义选成语) 或 word_to_meaning (看成语选释义)')
    target_hanyu_id: int = Field(description='目标词汇 ID')
    target_word: str = Field(description='目标词汇')
    target_pinyin: str | None = Field(default=None, description='拼音')
    target_meaning: str = Field(description='标准核心释义')
    stem: str = Field(description='题干展示内容')
    options: list[QuizOption] = Field(description='4个选项')
    correct_key: str = Field(description='正确选项标识 (A/B/C/D)')
    commentary: str | None = Field(default=None, description='名师考点/辨析提示')
    bianxi_groups: list[HanyuGroupOut] = Field(default_factory=list, description='关联的近义辨析组')


class GetQuizSession(BaseModel):
    """获取测验会话响应"""
    model_config = ConfigDict(from_attributes=True)

    quiz_type: str = Field(description='测验模式')
    total_count: int = Field(description='总题数')
    questions: list[QuizQuestion] = Field(description='题目列表')


class SubmitQuizItem(BaseModel):
    """单题答题记录"""
    target_hanyu_id: int = Field(description='考查词汇 ID')
    user_choice: str = Field(description='用户选择的选项 (A/B/C/D)')
    is_correct: bool = Field(description='是否答对')
    duration_ms: int = Field(default=0, description='答题耗时(毫秒)')


class SubmitQuizParam(BaseModel):
    """提交测验结果参数"""
    quiz_type: str = Field(description='测验模式')
    total_count: int = Field(description='总题数')
    correct_count: int = Field(description='答对题数')
    duration_ms: int = Field(description='总耗时(毫秒)')
    items: list[SubmitQuizItem] = Field(default_factory=list, description='各题明细')


class SubmitQuizResult(BaseModel):
    """提交测验结果响应"""
    model_config = ConfigDict(from_attributes=True)

    score_percent: int = Field(description='正确率 (0-100)')
    evaluation: str = Field(description='成绩评价')
    correct_count: int = Field(description='答对题数')
    total_count: int = Field(description='总题数')
