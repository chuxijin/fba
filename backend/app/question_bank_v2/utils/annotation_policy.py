from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.question_bank_v2.model.practice import QbPracticeSession

PERSISTENT_ANNOTATION_MODES = ('practice', 'exam', 'mock', 'adaptive')
TEMPORARY_ANNOTATION_SOURCES = ('wrong', 'favorite', 'note')


def persistent_annotations_enabled(session: 'QbPracticeSession | None') -> bool:
    """正式刷题保存标注，背题和用户内容临时重练不保存。"""
    return session is not None and (
        getattr(session, 'mode', 'practice') in PERSISTENT_ANNOTATION_MODES
        and getattr(session, 'source_type', 'bank') not in TEMPORARY_ANNOTATION_SOURCES
        and (getattr(session, 'delivery_config', None) or {}).get('annotations_enabled', True) is not False
    )
