from datetime import date
from typing import Any

from sqlalchemy import and_, case, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.model.practice_log import GongkaoPracticeLog as Log
from backend.app.question_bank_v2.model.practice import QbPracticeSession as Session
from backend.app.question_bank_v2.model.practice import QbPracticeSessionItem as Item
from backend.app.question_bank_v2.utils.external_practice import EXTERNAL_PRACTICE_ORIGIN

MAX_REFERENCE_RECORDS = 1000
MAX_REFERENCE_QUESTIONS = 50_000


class CRUDPracticeReference:
    @staticmethod
    async def get_records(
        db: AsyncSession, *, user_id: int, subject_name: str, material_type: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """同时列出旧报告，防止把「没有新统计」误报为「没有练习」。"""
        stmt = (
            select(
                Log.id.label('record_id'),
                Log.material_title.label('record_title'),
                Log.practiced_at,
                Session.id.label('session_id'),
                Session.total_items,
                Session.source_snapshot,
            )
            .outerjoin(
                Session,
                and_(
                    Session.source_snapshot['practice_log_id'].as_integer() == Log.id,
                    Session.source_snapshot['origin'].as_string() == EXTERNAL_PRACTICE_ORIGIN,
                    Session.user_id == user_id,
                    Session.deleted == 0,
                ),
            )
            .where(
                Log.user_id == user_id,
                Log.deleted == 0,
                Log.source_platform == 'fenbi',
                Log.subject_name == subject_name,
                Log.material_type == material_type,
                Log.practiced_at >= start_date,
                Log.practiced_at <= end_date,
            )
            .order_by(Log.practiced_at, Log.id)
            .limit(MAX_REFERENCE_RECORDS + 1)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings()]

    @staticmethod
    async def get_questions(db: AsyncSession, *, user_id: int, session_ids: list[int]) -> list[dict[str, Any]]:
        if not session_ids:
            return []
        data = Item.display_config['external_practice']
        # 不拉题干、解析或材料正文；身份指纹已在导入时固定到当次快照。
        stmt = (
            select(
                Item.session_id,
                Item.position,
                data['source_question_key'].as_string().label('source_question_key'),
                data['module_path'].label('module_path'),
                data['status'].as_string().label('status'),
                data['question_type'].as_string().label('question_type'),
                case(
                    (Item.display_config['reference_backfilled'].as_boolean().is_(True),
                     Item.display_config['reference_original']),
                    else_=data['platform_reference'],
                ).label('platform_reference'),
                Item.display_config['reference_content_hash'].as_string().label('content_hash'),
            )
            .join(Session, Session.id == Item.session_id)
            .where(
                Item.session_id.in_(session_ids),
                Item.deleted == 0,
                Session.user_id == user_id,
                Session.deleted == 0,
                Session.source_snapshot['origin'].as_string() == EXTERNAL_PRACTICE_ORIGIN,
                Session.source_snapshot['reference_policy'].as_integer() == 1,
            )
            .order_by(Item.session_id, Item.position)
            .limit(MAX_REFERENCE_QUESTIONS + 1)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings()]


practice_reference_dao = CRUDPracticeReference()
