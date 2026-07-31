from sqlalchemy.orm import configure_mappers

from backend.app.question_bank_v2.model import (
    QbBank,
    QbBankCategory,
    QbPracticeSession,
    QbQuestionFavorite,
    QbQuestionNote,
    QbQuestionReview,
    QbUserBankItemProgress,
    QbUserDailyStatistics,
    QbUserPracticePreference,
    QbUserPracticeStatistics,
    QbUserQuestionMastery,
    QbWrongQuestionState,
)


def _constraint_names(model: type) -> set[str]:
    return {constraint.name for constraint in model.__table__.constraints if constraint.name}


def _index_names(model: type) -> set[str]:
    return {index.name for index in model.__table__.indexes}


def test_question_bank_v2_mappers_configure() -> None:
    configure_mappers()


def test_bank_category_uses_real_foreign_keys_and_primary_guard() -> None:
    foreign_keys = {
        foreign_key.target_fullname
        for column in QbBankCategory.__table__.columns
        for foreign_key in column.foreign_keys
    }

    assert 'qbank_v2_bank.id' in foreign_keys
    assert 'sys_category.id' in foreign_keys
    assert 'uq_qbv2_bank_category' in _constraint_names(QbBankCategory)
    assert 'uq_qbv2_bank_category_primary' in _index_names(QbBankCategory)
    assert 'category_memberships' in QbBank.__mapper__.relationships


def test_mini_program_read_models_keep_required_query_indexes() -> None:
    assert 'uq_qbv2_preference_user' in _constraint_names(QbUserPracticePreference)
    assert 'ix_qbv2_ubip_bank_progress' in _index_names(QbUserBankItemProgress)
    assert 'ix_qbv2_user_stats_graded' in _index_names(QbUserPracticeStatistics)
    assert 'ix_qbv2_user_stats_streak' in _index_names(QbUserPracticeStatistics)
    assert 'ix_qbv2_user_daily_rank' in _index_names(QbUserDailyStatistics)
    assert 'ix_qbv2_session_user_created' in _index_names(QbPracticeSession)
    assert 'ix_qbv2_favorite_user_page' in _index_names(QbQuestionFavorite)
    assert {'ix_qbv2_note_user_page', 'ix_qbv2_note_public_page'} <= _index_names(QbQuestionNote)


def test_wrong_review_models_keep_scope_constraints_and_due_indexes() -> None:
    """错题复盘模型必须保留来源完整性和重练到期扫描索引"""
    assert 'ck_qbv2_wrong_entry_source' in _constraint_names(QbWrongQuestionState)
    assert 'ix_qbv2_wrong_user_status' in _index_names(QbWrongQuestionState)
    # 重练调度与复盘档案的索引都落在错题本小表上，推送扫描无需 join 掌握度大表
    assert {
        'ix_qbv2_wrong_push_due',
        'ix_qbv2_wrong_user_due',
        'ix_qbv2_wrong_reviewed',
        'ix_qbv2_wrong_unreviewed',
    } <= _index_names(QbWrongQuestionState)
    assert {
        'ck_qbv2_review_event_type',
        'uq_qbv2_review_idempotency',
    } <= _constraint_names(QbQuestionReview)
    assert 'ix_qbv2_review_user_review_time' in _index_names(QbQuestionReview)
    assert 'ix_qbv2_review_wrong_state_page' in _index_names(QbQuestionReview)
    assert 'ix_qbv2_mastery_state' in _index_names(QbUserQuestionMastery)
    assert 'ck_qbv2_preference_review_limit' in _constraint_names(QbUserPracticePreference)
