from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from backend.app.question_bank_v2.model.bank import QbBank, QbBankItem, QbBankRevision
from backend.app.question_bank_v2.model.user_content import QbQuestionFavorite, QbQuestionNote


def content_bank_item_condition(
    model: type[QbQuestionFavorite] | type[QbQuestionNote], *, per_bank: bool = True
) -> ColumnElement[bool]:
    """沿用保存的题库上下文；未保存或关联已不存在时按稳定题目回查。

    分组与指定题库练习每库只选一个编排，优先当前版本；无题库过滤的练习
    只选一个编排，避免同一笔记因题目挂载多个题库而重复投递。
    """
    saved_item = QbBankItem.__table__.alias('saved_content_bank_item')
    has_saved_item = exists(select(saved_item.c.id).where(saved_item.c.id == model.bank_item_id).correlate(model))
    ranked_items = (
        select(
            QbBankItem.id,
            QbBankItem.question_id,
            func
            .row_number()
            .over(
                partition_by=(QbBankItem.question_id, QbBankRevision.bank_id) if per_bank else QbBankItem.question_id,
                order_by=(
                    (QbBankItem.bank_revision_id == QbBank.current_revision_id).desc(),
                    QbBankRevision.revision_no.desc(),
                    QbBankItem.id.desc(),
                ),
            )
            .label('rank'),
        )
        .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
        .join(QbBank, QbBank.id == QbBankRevision.bank_id)
        .subquery()
    )
    fallback_item_ids = (
        select(ranked_items.c.id)
        .where(ranked_items.c.question_id == model.question_id, ranked_items.c.rank == 1)
        .correlate(model)
    )
    return or_(
        QbBankItem.id == model.bank_item_id,
        and_(QbBankItem.id.in_(fallback_item_ids), ~has_saved_item),
    )
