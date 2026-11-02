"""只提醒已复盘且到期的全部题目，复用站内信与练习进度。"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_message import message_dao
from backend.app.admin.model.message import Message, MessageTargetType, MessageType
from backend.app.admin.schema.message import PublishMessageParam
from backend.app.admin.service.message_service import message_service
from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao, practice_session_item_dao
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.model.review import QbWrongQuestionState
from backend.app.question_bank_v2.model.user import QbUserPracticePreference
from backend.app.question_bank_v2.schema.practice import CreateRecallSessionParam, GetPracticeSessionDetail
from backend.app.question_bank_v2.utils.practice_lock import lock_practice_user
from backend.common.exception import errors
from backend.utils.timezone import timezone

BIZ_SOURCE = 'question_bank_v2'
RECALL_ACTION = 'practice_due'


class QbankNotificationService:
    @staticmethod
    def due_queue(user_id: int, cutoff: datetime) -> Select:
        """只处理消息截止前已到期且尚未独立提交的已复盘题。"""
        return (
            select(QbWrongQuestionState.question_id)
            .join(QbQuestion, QbQuestion.id == QbWrongQuestionState.question_id)
            .where(
                *QbankNotificationService._eligible(user_id, cutoff),
                or_(
                    QbWrongQuestionState.last_practice_time.is_(None), QbWrongQuestionState.last_practice_time <= cutoff
                ),
                ~exists().where(
                    QbQuestionAttempt.user_id == user_id,
                    QbQuestionAttempt.question_id == QbWrongQuestionState.question_id,
                    QbQuestionAttempt.deleted == 0,
                    QbQuestionAttempt.submitted_time > cutoff,
                    func.coalesce(QbQuestionAttempt.response_data['mode'].as_string(), '') != 'memorize',
                ),
            )
        )

    @staticmethod
    async def _unfinished(db: AsyncSession, user_id: int) -> QbPracticeSession | None:
        return await db.scalar(
            select(QbPracticeSession)
            .where(
                QbPracticeSession.user_id == user_id,
                QbPracticeSession.deleted == 0,
                QbPracticeSession.status.in_({'created', 'in_progress'}),
                QbPracticeSession.delivery_config['recall_message_id'].as_string().is_not(None),
                QbPracticeSession.answered_items < QbPracticeSession.total_items,
                exists(
                    select(QbPracticeSessionItem.id)
                    .join(QbWrongQuestionState, QbWrongQuestionState.question_id == QbPracticeSessionItem.question_id)
                    .join(QbQuestion, QbQuestion.id == QbPracticeSessionItem.question_id)
                    .outerjoin(
                        QbPracticeSessionResponse, QbPracticeSessionResponse.session_item_id == QbPracticeSessionItem.id
                    )
                    .where(
                        QbPracticeSessionItem.session_id == QbPracticeSession.id,
                        QbPracticeSessionItem.deleted == 0,
                        *QbankNotificationService._eligible(user_id, timezone.now()),
                        ~exists()
                        .where(
                            QbQuestionAttempt.user_id == user_id,
                            QbQuestionAttempt.question_id == QbPracticeSessionItem.question_id,
                            QbQuestionAttempt.deleted == 0,
                            QbQuestionAttempt.submitted_time > QbPracticeSession.created_time,
                            func.coalesce(QbQuestionAttempt.response_data['mode'].as_string(), '') != 'memorize',
                        )
                        .correlate(QbPracticeSession, QbPracticeSessionItem),
                        or_(
                            QbPracticeSessionResponse.id.is_(None),
                            QbPracticeSessionResponse.status.not_in({'submitted', 'graded', 'review_required'}),
                        ),
                    )
                ),
            )
            .order_by(QbPracticeSession.id)
            .limit(1)
        )

    @staticmethod
    def _eligible(user_id: int, now: datetime) -> tuple:
        return (
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.deleted == 0,
            QbWrongQuestionState.status.in_({'active', 'resolved'}),
            QbWrongQuestionState.review_count > 0,
            QbWrongQuestionState.next_practice_time <= now,
            QbQuestion.deleted == 0,
            QbQuestion.status == 'active',
            or_(QbQuestion.visibility != 'private', QbQuestion.owner_id == user_id),
            ~exists().where(
                QbQuestionAttempt.user_id == user_id,
                QbQuestionAttempt.question_id == QbWrongQuestionState.question_id,
                QbQuestionAttempt.deleted == 0,
                QbQuestionAttempt.grading_status == 'pending',
                QbQuestionAttempt.is_correct.is_(None),
            ),
        )

    @staticmethod
    async def candidate_users(db: AsyncSession, *, after: int, now: datetime, limit: int = 200) -> list[int]:
        """有到期题的已订阅用户；有界keyset遍历，不载入全站题目。"""
        return list(
            (
                await db.scalars(
                    select(QbUserPracticePreference.user_id)
                    .where(
                        QbUserPracticePreference.deleted == 0,
                        QbUserPracticePreference.review_reminder_enabled.is_(True),
                        QbUserPracticePreference.user_id > after,
                        exists().where(
                            QbWrongQuestionState.user_id == QbUserPracticePreference.user_id,
                            QbWrongQuestionState.deleted == 0,
                            QbWrongQuestionState.status.in_({'active', 'resolved'}),
                            QbWrongQuestionState.review_count > 0,
                            QbWrongQuestionState.next_practice_time <= now,
                        ),
                    )
                    .order_by(QbUserPracticePreference.user_id)
                    .limit(limit)
                )
            ).all()
        )

    @staticmethod
    async def notify_practice_due(*, db: AsyncSession, user_id: int, now: datetime) -> bool:
        # 与创建练习、提交作答共用用户锁，重复beat/worker不能同日重复发送。
        await lock_practice_user(db, user_id)
        preference = await db.scalar(
            select(QbUserPracticePreference).where(
                QbUserPracticePreference.user_id == user_id,
                QbUserPracticePreference.deleted == 0,
            )
        )
        if preference is None or not preference.review_reminder_enabled:
            return False
        local = now.astimezone(ZoneInfo(preference.review_reminder_timezone))
        if local.time().replace(tzinfo=None) < preference.review_reminder_time:
            return False
        local_date: date = local.date()
        biz_id = f'practice_due:{user_id}:{local_date.isoformat()}'
        if await db.scalar(select(Message.id).where(Message.biz_source == BIZ_SOURCE, Message.biz_id == biz_id)):
            return False
        ids = list(
            (
                await db.scalars(
                    QbankNotificationService.due_queue(user_id, now).order_by(
                        QbWrongQuestionState.next_practice_time, QbWrongQuestionState.id
                    )
                )
            ).all()
        )
        if not ids:
            return False
        due_count = len(ids)
        unfinished = await QbankNotificationService._unfinished(db, user_id)
        session_key = unfinished.session_key if unfinished is not None else None
        message = await message_service.publish(
            db=db,
            obj=PublishMessageParam(
                title='复盘回测提醒',
                content=f'你已复盘的题目中，有 {due_count} 道已到回测时间。'
                '全部到期题均已列出，请量力而行，未完成可随时继续。先独立作答，提交后再对照解析与原复盘。',
                target_type=MessageTargetType.USER,
                user_id=user_id,
                message_type=MessageType.PERSONAL,
                biz_source=BIZ_SOURCE,
                biz_id=biz_id,
                payload={
                    'action': RECALL_ACTION,
                    'question_ids': ids,
                    'due_before': now.isoformat(),
                    'session_key': session_key,
                    'due_count': due_count,
                },
            ),
        )
        message.link_url = f'/pkg/practice/session/index?recallMessageId={message.id}&mode=practice'
        await db.flush()
        return True

    @staticmethod
    async def _resume(
        *,
        db: AsyncSession,
        user_id: int,
        message: Message,
        session_key: str,
    ) -> GetPracticeSessionDetail:
        """新旧消息共享未答卷；队列截止时间跟随当前打开的提醒。"""
        from backend.app.question_bank_v2.service.practice_service import practice_service

        session = await practice_session_dao.get_by_key(db, session_key, user_id=user_id)
        if session is None or session.deleted:
            raise errors.ConflictError(msg='这次回测已从练习记录移除，请使用新的回测提醒')
        if session.status not in {'created', 'in_progress'}:
            return await QbankNotificationService._create_for_message(
                db=db,
                user_id=user_id,
                message=message,
                previous=session,
            )
        cutoff = datetime.fromisoformat(message.payload['due_before'])
        previous_cutoff = (session.delivery_config or {}).get('recall_due_before')
        if previous_cutoff:
            cutoff = max(cutoff, datetime.fromisoformat(previous_cutoff))
        session.delivery_config = {
            **(session.delivery_config or {}),
            'recall_message_id': message.id,
            'recall_due_before': cutoff.isoformat(),
        }
        message.payload = {**message.payload, 'session_key': session_key}
        await QbankNotificationService._include_due_questions(db=db, user_id=user_id, session=session)
        await db.flush()
        return await practice_service.get(db=db, session_key=session_key, user_id=user_id)

    @staticmethod
    async def _include_due_questions(
        *,
        db: AsyncSession,
        user_id: int,
        session: QbPracticeSession,
    ) -> None:
        """旧限量卷和跨日未答卷补入全部到期题，已答题与原作答事实保持不变。"""
        items = await practice_session_item_dao.get_all(db, session.id)
        existing_ids = {item['question_id'] for item in items}
        ids = list(
            (
                await db.scalars(
                    QbankNotificationService
                    .due_queue(user_id, datetime.fromisoformat(session.delivery_config['recall_due_before']))
                    .where(QbWrongQuestionState.question_id.not_in(existing_ids))
                    .order_by(QbWrongQuestionState.next_practice_time, QbWrongQuestionState.id)
                )
            ).all()
        )
        if not ids:
            return
        candidates = await practice_session_item_dao.get_user_candidates(
            db,
            user_id=user_id,
            source_type='custom',
            question_ids=ids,
            limit=len(ids),
            bank_id=None,
            section_ids=[],
            favorite_folder_id=None,
            knowledge_point_ids=[],
            question_types=[],
            year_start=None,
            year_end=None,
            shuffle=False,
        )
        await practice_session_item_dao.create_all(
            db,
            session_id=session.id,
            candidates=candidates,
            start_position=max((item['position'] for item in items), default=-1) + 1,
        )
        session.total_items += len(candidates)

    @staticmethod
    async def open_practice(
        *,
        db: AsyncSession,
        user_id: int,
        message_id: int,
    ) -> GetPracticeSessionDetail:
        """按服务端截止时间投递全部符合条件的题，重复点击续接同卷。"""
        await lock_practice_user(db, user_id)
        message = await message_dao.get_for_user(db, message_id, user_id)
        if (
            message is None
            or message.user_id != user_id
            or message.biz_source != BIZ_SOURCE
            or (message.payload or {}).get('action') != RECALL_ACTION
        ):
            raise errors.NotFoundError(msg='回测消息不存在或不可访问')
        payload = message.payload or {}
        key = f'recall-message-{message.id}'
        saved_key = payload.get('session_key')
        if saved_key:
            return await QbankNotificationService._resume(
                db=db,
                user_id=user_id,
                message=message,
                session_key=saved_key,
            )
        existing = await db.scalar(
            select(QbPracticeSession).where(
                QbPracticeSession.user_id == user_id,
                QbPracticeSession.session_key == key,
            )
        )
        if existing is not None:
            return await QbankNotificationService._resume(
                db=db,
                user_id=user_id,
                message=message,
                session_key=key,
            )
        unfinished = await QbankNotificationService._unfinished(db, user_id)
        if unfinished is not None:
            # 跨日提醒、旧消息并发打开也续接未完成会话，不给相同题目再建一卷。
            return await QbankNotificationService._resume(
                db=db,
                user_id=user_id,
                message=message,
                session_key=unfinished.session_key,
            )
        return await QbankNotificationService._create_for_message(db=db, user_id=user_id, message=message)

    @staticmethod
    async def _create_for_message(
        *,
        db: AsyncSession,
        user_id: int,
        message: Message,
        previous: QbPracticeSession | None = None,
    ) -> GetPracticeSessionDetail:
        """一次投递全部到期题；旧已结束限量卷的事实不改动，剩余题独立续接。"""
        from backend.app.question_bank_v2.service.practice_service import practice_service

        payload = message.payload or {}
        cutoff = datetime.fromisoformat(payload['due_before'])
        key = f'recall-message-{message.id}' + (f'-resume-{previous.id}' if previous is not None else '')
        # 在其他入口已回测、已暂停/删除/失效的题不强制再做，也不改变新到期时间。
        ids = list(
            (
                await db.scalars(
                    QbankNotificationService.due_queue(user_id, cutoff).order_by(
                        QbWrongQuestionState.next_practice_time, QbWrongQuestionState.id
                    )
                )
            ).all()
        )
        if not ids:
            if previous is not None:
                return await practice_service.get(db=db, session_key=previous.session_key, user_id=user_id)
            raise errors.ConflictError(msg='本次提醒中已没有符合条件的已复盘到期题')
        detail = await practice_service.create(
            db=db,
            user_id=user_id,
            obj=CreateRecallSessionParam(
                source_type='custom',
                question_ids=ids,
                mode='practice',
                annotations_enabled=False,
                title='复盘回测',
                session_key=key,
                limit=len(ids),
                shuffle=False,
            ),
            recall_message_id=message.id,
        )
        session = await practice_session_dao.get_by_key(db, key, user_id=user_id)
        session.delivery_config = {**(session.delivery_config or {}), 'recall_message_id': message.id}
        session.delivery_config = {
            **session.delivery_config,
            'recall_due_before': cutoff.isoformat(),
        }
        message.payload = {**payload, 'session_key': key}
        await db.flush()
        return await practice_service.get(db=db, session_key=detail.session_key, user_id=user_id)


qbank_notification_service = QbankNotificationService()
