#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.schema import AgentType
from backend.plugin.agents.service.common.orchestrator import Node, Pipeline
from backend.plugin.agents.service.common.orchestrator.pipeline import CheckpointFunc
from backend.plugin.agents.service.question_generation.nodes import (
    analyze_article,
    design_options,
    draft_questions,
    load_profile,
    mine_passages,
    plan_blueprints,
    plan_question_types,
    review_generation,
    review_passages,
    review_question_types,
)


def build_pipeline(on_checkpoint: CheckpointFunc | None = None) -> Pipeline:
    """构建 AI 出题 pipeline"""
    return Pipeline(
        agent_type=AgentType.question_generation,
        on_checkpoint=on_checkpoint,
        steps=[
            Node('profile_loader', 'load_profile', load_profile),
            Node('article_analyzer', 'analyze_article', analyze_article),
            Node('passage_miner', 'mine_passages', mine_passages),
            Node('passage_reviewer', 'review_passages', review_passages),
            Node('question_type_planner', 'plan_question_types', plan_question_types),
            Node('type_reviewer', 'review_question_types', review_question_types),
            Node('blueprint_planner', 'plan_blueprints', plan_blueprints),
            Node('question_drafter', 'draft_questions', draft_questions),
            Node('option_designer', 'design_options', design_options),
            Node('reviewer', 'review_generation', review_generation),
        ],
    )
