#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any, TypeVar

from pydantic import BaseModel

from backend.plugin.agents.service.common.llm import LLMCallStats, NodeRole

T = TypeVar('T', bound=BaseModel)


# 通过 system_prompt 的独特短语识别节点
_KEYWORD_TO_NODE = [
    ('识别题型', 'classifier'),
    ('从给定材料中提取', 'material_parser'),
    ('多份参考答案', 'reference_analyzer'),
    ('从**考生答案**中提取', 'answer_analyzer'),
    ('与参考答案要点做', 'point_matcher'),
    ('分析议论文', 'structure_analyzer'),
    ('严格按评分细则给分', 'scorer'),
    ('基于评分结果和缺失要点', 'diagnoser'),
    ('针对诊断出的每个问题', 'suggester'),
    ('产出 A 档', 'rewriter'),
    ('质检员', 'reviewer'),
]


_FAKE_RESPONSES: dict[str, dict[str, Any]] = {
    'classifier': {
        'question_type': '大作文',
        'confidence': 0.95,
        'reason': 'mock 题干含写作类关键词',
    },
    'material_parser': {
        'points': [
            {'text': 'mock 材料要点 1, 涉及区域协同', 'weight': 1.8, 'source_excerpt': '材料 1 第二段'},
            {'text': 'mock 材料要点 2, 涉及制度建设', 'weight': 1.5, 'source_excerpt': '材料 2'},
            {'text': 'mock 材料要点 3, 涉及民生导向', 'weight': 1.2, 'source_excerpt': '材料 3'},
        ],
    },
    'reference_analyzer': {
        'points': [
            {'text': 'mock 共识要点: 加强制度协同', 'consensus_count': 3, 'consensus_level': 'high', 'weight': 2.0},
            {'text': 'mock 共识要点: 推进产业协同', 'consensus_count': 3, 'consensus_level': 'high', 'weight': 2.0},
            {'text': 'mock 中等共识: 完善民生保障', 'consensus_count': 2, 'consensus_level': 'medium', 'weight': 1.5},
            {'text': 'mock 低共识: 优化生态治理', 'consensus_count': 1, 'consensus_level': 'unique', 'weight': 1.0},
        ],
    },
    'answer_analyzer': {
        'points': [
            {'text': 'mock 用户提到的要点: 制度协同', 'original_excerpt': '考生答案第二段', 'weight': 1.0},
            {'text': 'mock 用户提到的要点: 产业协同', 'original_excerpt': '考生答案第三段', 'weight': 1.0},
        ],
    },
    'point_matcher': {
        'matched': [
            {'reference_point_text': 'mock 共识要点: 加强制度协同', 'matched_user_text': '考生答案第二段'},
            {'reference_point_text': 'mock 共识要点: 推进产业协同', 'matched_user_text': '考生答案第三段'},
        ],
        'missing': [
            {'reference_point_text': 'mock 中等共识: 完善民生保障', 'consensus_level': 'medium'},
            {'reference_point_text': 'mock 低共识: 优化生态治理', 'consensus_level': 'unique'},
        ],
    },
    'structure_analyzer': {
        'paragraph_count': 5,
        'structure_type': '总分总',
        'has_intro': True,
        'has_conclusion': True,
        'intro_quality': 'good',
        'conclusion_quality': 'fair',
        'transition_issues': ['第 2 段到第 3 段过渡略生硬'],
        'summary': 'mock 结构总分总, 5 段, 头尾完整',
    },
    'scorer': {
        'score_total': 28.0,
        'level': 'B',
        'level_label': '二类卷',
        'summary': 'mock 总评: 立意基本符合题旨, 结构层次清晰, 但论证深度有待加强。',
        'rubric_scores': [
            {
                'name': '立意',
                'score': 9,
                'max_score': 12,
                'level': 'B',
                'level_label': '良',
                'comment': 'mock 立意明确',
            },
            {'name': '结构', 'score': 6, 'max_score': 8, 'level': 'B', 'level_label': '良', 'comment': 'mock 层次清晰'},
            {
                'name': '论证',
                'score': 6,
                'max_score': 10,
                'level': 'C',
                'level_label': '中',
                'comment': 'mock 论据偏少',
            },
            {'name': '文采', 'score': 4, 'max_score': 6, 'level': 'B', 'level_label': '良', 'comment': 'mock 语言通顺'},
            {'name': '规范', 'score': 3, 'max_score': 4, 'level': 'B', 'level_label': '良', 'comment': 'mock 格式规范'},
        ],
    },
    'diagnoser': {
        'issues': [
            {
                'category': '论证',
                'severity': 'major',
                'description': 'mock 第二段提出制度协同后, 仅用结论性表述, 缺乏论据支撑',
                'location': '第 2 段',
                'related_section': 'score_card',
            },
            {
                'category': '缺失要点',
                'severity': 'major',
                'description': 'mock 未提及"完善民生保障"这一重要参考要点',
                'related_section': 'key_points',
            },
            {
                'category': '结构',
                'severity': 'minor',
                'description': 'mock 第 2 段到第 3 段过渡缺少承上启下句',
                'location': '第 2-3 段',
            },
        ],
    },
    'suggester': {
        'suggestions': [
            {
                'target_issue': '论证浅',
                'action': 'mock 在第 2 段制度协同下补充长三角一体化政策数据作为论据',
                'priority': 'high',
            },
            {
                'target_issue': '缺失民生要点',
                'action': 'mock 在三段中加入民生保障维度, 与制度/产业并列形成完整逻辑',
                'priority': 'high',
            },
            {
                'target_issue': '段落过渡',
                'action': 'mock 在第 3 段开头加"制度协同之外, 产业协同同样关键..."',
                'priority': 'medium',
            },
        ],
    },
    'rewriter': {
        'revised': 'mock 改写示范: 协同发展之要义, 在制度先行、产业同频、民生为本。首先制度协同……(略 800 字)',
        'diff_summary': 'mock 1. 第二段补充长三角数据案例; 2. 新增民生保障段落; 3. 优化第 2-3 段过渡',
        'changes': [
            {
                'original': 'mock 原文片段 1',
                'revised': 'mock 改写片段 1',
                'reason': 'mock 补充论据',
            },
            {
                'original': 'mock 原文片段 2',
                'revised': 'mock 改写片段 2',
                'reason': 'mock 强化逻辑',
            },
        ],
    },
    'reviewer': {
        'passed': True,
        'confidence': 0.85,
        'notes': [
            'mock 评分 28/40 与扣分点对齐',
            'mock 缺失要点已被建议覆盖',
            'mock 改写示范长度合理, 保留考生思路',
        ],
    },
}


class FakeLLMClient:
    """Mock LLM 客户端, 按 system_prompt 关键词路由到预设响应"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.provider_id = 0
        self.primary_model_id = 'mock-model'
        self.mini_model_id = 'mock-mini'

    def resolve_model(self, role: NodeRole) -> str:
        """模拟 LLMClient 的角色路由"""
        if role == NodeRole.mini:
            return self.mini_model_id
        return self.primary_model_id

    async def invoke_json(
        self,
        db: Any,
        *,
        role: NodeRole,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4000,
        timeout: float = 120,
    ) -> tuple[dict[str, Any], LLMCallStats]:
        """模拟 LLM JSON 调用 (兼容旧路径)"""
        node = self._detect_node(system_prompt)
        response = _FAKE_RESPONSES.get(node, {})
        self.calls.append({
            'node': node,
            'role': role.value,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'mode': 'json',
        })
        stats = LLMCallStats(
            model=self.resolve_model(role),
            tokens_in=len(system_prompt) // 3 + len(user_prompt) // 3,
            tokens_out=200,
            duration_ms=1,
        )
        return response, stats

    async def invoke_structured(
        self,
        db: Any,
        *,
        role: NodeRole,
        system_prompt: str,
        user_prompt: str,
        output_type: type[T],
        temperature: float = 0.2,
        max_tokens: int = 4000,
        timeout: float = 120,
        output_retries: int = 2,
    ) -> tuple[T, LLMCallStats]:
        """模拟 LLM 结构化调用, 把 mock dict 转 Pydantic Output 强类型"""
        node = self._detect_node(system_prompt)
        raw = _FAKE_RESPONSES.get(node, {})
        self.calls.append({
            'node': node,
            'role': role.value,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'mode': 'structured',
            'output_type': output_type.__name__,
        })
        try:
            output = output_type.model_validate(raw)
        except Exception as e:
            raise ValueError(f'FakeLLMClient: mock 数据无法 validate 为 {output_type.__name__}: {e}') from e
        stats = LLMCallStats(
            model=self.resolve_model(role),
            tokens_in=len(system_prompt) // 3 + len(user_prompt) // 3,
            tokens_out=200,
            duration_ms=1,
        )
        return output, stats

    async def invoke_text(
        self,
        db: Any,
        *,
        role: NodeRole,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.6,
        max_tokens: int = 4000,
        timeout: float = 120,
    ) -> tuple[str, LLMCallStats]:
        """模拟 LLM 纯文本调用"""
        text = '[mock text response]'
        stats = LLMCallStats(
            model=self.resolve_model(role),
            tokens_in=len(system_prompt) // 3 + len(user_prompt) // 3,
            tokens_out=len(text) // 3,
            duration_ms=1,
        )
        return text, stats

    @staticmethod
    def _detect_node(system_prompt: str) -> str:
        """通过 system_prompt 关键词识别节点"""
        for keyword, node in _KEYWORD_TO_NODE:
            if keyword in system_prompt:
                return node
        raise ValueError(f'FakeLLMClient 无法识别 system_prompt 对应节点: {system_prompt[:120]}')
