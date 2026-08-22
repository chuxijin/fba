from backend.plugin.agent.service.coach_intent import build_intent_plan, classify_module, requested_recent_limit


def test_coach_intent_routes_next_question_recommendation() -> None:
    plan = build_intent_plan(text='下一题我想练归纳概括', has_attempt=True)

    assert plan['action'] == 'recommend'
    assert plan['scope'] == 'candidate_questions'
    assert plan['module'] == 'summary'


def test_coach_intent_keeps_current_attempt_for_rewrite() -> None:
    plan = build_intent_plan(text='复盘刚才这题并帮我改写', has_attempt=True, subject_ids=[12])

    assert plan['action'] == 'rewrite'
    assert plan['scope'] == 'current_attempt'


def test_coach_module_and_recent_limit_match_yanshen_rules() -> None:
    assert classify_module('这篇公开信格式有什么问题') == 'document'
    assert requested_recent_limit('复盘最近三道题') == 3
