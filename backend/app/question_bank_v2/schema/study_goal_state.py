"""在原 study_goal JSON 中兼容保存当前目标与有序目标列表，不新增数据库字段。"""

import hashlib
import json

from typing import Any

from backend.app.question_bank_v2.schema.study_goal import StudyGoal


def current_study_goal(raw: Any) -> dict | None:
    if not raw:
        return None
    if isinstance(raw, StudyGoal):
        return raw.model_dump(mode='json')
    return raw.get('current') if 'current' in raw else raw


def saved_study_goals(raw: Any) -> list[StudyGoal]:
    if not raw:
        return []
    if 'current' in raw:
        return [StudyGoal.model_validate(item) for item in raw.get('saved', [])]
    return [StudyGoal.model_validate(raw)]


def study_goal_key(goal: StudyGoal) -> tuple[str, int, str | None]:
    return goal.exam_target_code, goal.exam_year, goal.category_code


def study_goals_revision(raw: Any) -> str:
    canonical = json.dumps(raw or {}, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def pack_study_goals(current: dict | None, saved: list[StudyGoal]) -> dict:
    # 空状态保留旧契约 {}；单目标也写版本化结构，读取继续兼容旧扁平 JSON。
    if not current and not saved:
        return {}
    return {'current': current, 'saved': [item.model_dump(mode='json') for item in saved], 'version': 1}
