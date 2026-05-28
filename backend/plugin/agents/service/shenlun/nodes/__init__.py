#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.service.shenlun.nodes.answer_analyzer import analyze_answer
from backend.plugin.agents.service.shenlun.nodes.classifier import classify
from backend.plugin.agents.service.shenlun.nodes.diagnoser import diagnose
from backend.plugin.agents.service.shenlun.nodes.material_parser import parse_material
from backend.plugin.agents.service.shenlun.nodes.point_matcher import match_points
from backend.plugin.agents.service.shenlun.nodes.reference_analyzer import analyze_reference
from backend.plugin.agents.service.shenlun.nodes.reviewer import review
from backend.plugin.agents.service.shenlun.nodes.rewriter import rewrite
from backend.plugin.agents.service.shenlun.nodes.rubric_loader import load_rubric
from backend.plugin.agents.service.shenlun.nodes.scorer import score
from backend.plugin.agents.service.shenlun.nodes.structure_analyzer import analyze_structure
from backend.plugin.agents.service.shenlun.nodes.suggester import suggest

__all__ = [
    'analyze_answer',
    'analyze_reference',
    'analyze_structure',
    'classify',
    'diagnose',
    'load_rubric',
    'match_points',
    'parse_material',
    'review',
    'rewrite',
    'score',
    'suggest',
]
