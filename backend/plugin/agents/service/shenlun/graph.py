#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.schema import AgentType, SectionName
from backend.plugin.agents.service.common.orchestrator import Node, ParallelGroup, Pipeline
from backend.plugin.agents.service.common.orchestrator.pipeline import CheckpointFunc
from backend.plugin.agents.service.shenlun.nodes import (
    analyze_answer,
    analyze_reference,
    analyze_structure,
    classify,
    diagnose,
    load_rubric,
    match_points,
    parse_material,
    review,
    rewrite,
    score,
    suggest,
)


def build_pipeline(on_checkpoint: CheckpointFunc | None = None) -> Pipeline:
    """构建申论批改 pipeline"""
    return Pipeline(
        agent_type=AgentType.shenlun,
        on_checkpoint=on_checkpoint,
        steps=[
            Node('classifier', 'classify', classify),
            Node('rubric_loader', 'load_rubric', load_rubric),
            ParallelGroup(
                nodes=[
                    Node('material_parser', 'parse_material', parse_material),
                    Node('reference_analyzer', 'analyze_reference', analyze_reference),
                    Node('answer_analyzer', 'analyze_answer', analyze_answer),
                ]
            ),
            Node('point_matcher', 'match_points', match_points, section=SectionName.key_points),
            Node('structure_analyzer', 'analyze_structure', analyze_structure),
            Node('scorer', 'score', score, section=SectionName.score_card),
            Node('diagnoser', 'diagnose', diagnose, section=SectionName.issues),
            Node('suggester', 'suggest', suggest, section=SectionName.suggestions),
            Node('rewriter', 'rewrite', rewrite, section=SectionName.rewritten_text),
            Node('reviewer', 'review', review, section=SectionName.qc),
        ],
    )
