from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_bank_high_error import bank_high_error_dao
from backend.app.question_bank_v2.crud.crud_composition import bank_section_dao
from backend.app.question_bank_v2.crud.crud_practice import PracticeCandidate
from backend.app.question_bank_v2.schema.bank_high_error import GetBankHighErrorSections, HighErrorSection

MIN_SAMPLES = 5
SLOW_MULTIPLIER = Decimal('1.5')


class BankHighErrorService:
    """试卷高频易错，与首页知识点 high_error 策略相互独立。"""

    @staticmethod
    def select_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """同章节同题型以样本充足题目的均时作等权基线，不混入缺失／零用时。"""
        groups: dict[tuple[int | None, str], list[Decimal]] = defaultdict(list)
        for row in rows:
            if row.get('duration_count', 0) >= MIN_SAMPLES and row.get('avg_duration_ms'):
                groups[row['section_id'], row['question_type']].append(Decimal(str(row['avg_duration_ms'])))
        baselines = {key: sum(values) / len(values) for key, values in groups.items()}
        selected = []
        for row in rows:
            graded = row.get('graded_count') or 0
            low_accuracy = graded >= MIN_SAMPLES and (row.get('correct_count') or 0) * 2 < graded
            baseline = baselines.get((row['section_id'], row['question_type']))
            duration = Decimal(str(row.get('avg_duration_ms') or 0))
            slow = bool(
                baseline and row.get('duration_count', 0) >= MIN_SAMPLES and duration > baseline * SLOW_MULTIPLIER
            )
            if low_accuracy or slow:
                selected.append({
                    **row,
                    'low_accuracy': low_accuracy,
                    'slow': slow,
                    'correct_rate': float(Decimal(row.get('correct_count') or 0) / graded) if graded else None,
                    'avg_duration_ms': float(duration) if duration else None,
                })
        return selected

    @staticmethod
    async def get_sections(*, db: AsyncSession, user_id: int, bank_id: int) -> GetBankHighErrorSections:
        """检查题库权益后返回章节与原因计数，不暴露其他用户的记录。"""
        from backend.app.question_bank_v2.service.analytics_service import analytics_service

        _, revision = await analytics_service._get_bank_context(db=db, user_id=user_id, bank_id=bank_id)
        rows = BankHighErrorService.select_rows(
            await bank_high_error_dao.get_rows(db, revision_id=revision.id, user_id=user_id)
        )
        sections = list(await bank_section_dao.get_all(db, revision_id=revision.id))
        direct: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            direct[row['section_id']].append(row)
        children: dict[int | None, list[Any]] = defaultdict(list)
        section_ids = {section.id for section in sections}
        for section in sections:
            children[section.parent_id if section.parent_id in section_ids else None].append(section)

        def build(section: Any) -> HighErrorSection:
            descendants = [build(child) for child in children[section.id]]
            own = direct[section.id]
            return HighErrorSection(
                id=section.id,
                name=section.name,
                parent_id=section.parent_id,
                depth=section.depth,
                sort_order=section.sort_order,
                question_count=len(own) + sum(child.question_count for child in descendants),
                low_accuracy_count=sum(row['low_accuracy'] for row in own)
                + sum(child.low_accuracy_count for child in descendants),
                slow_count=sum(row['slow'] for row in own) + sum(child.slow_count for child in descendants),
                children=[child for child in descendants if child.question_count],
            )

        roots = [build(section) for section in children[None]]
        return GetBankHighErrorSections(
            bank_id=bank_id,
            bank_revision_id=revision.id,
            total_count=len(rows),
            low_accuracy_count=sum(row['low_accuracy'] for row in rows),
            slow_count=sum(row['slow'] for row in rows),
            unsectioned_count=len(direct[None]),
            sections=[node for node in roots if node.question_count],
        )

    @staticmethod
    async def get_candidates(
        *, db: AsyncSession, user_id: int, revision_id: int, section_id: int | None, limit: int
    ) -> list[PracticeCandidate]:
        """先计算整卷基线再筛章节，保持章节树与实际投递的一致性。"""
        rows = BankHighErrorService.select_rows(
            await bank_high_error_dao.get_rows(db, revision_id=revision_id, user_id=user_id)
        )
        if section_id is not None:
            section_ids = set(await bank_section_dao.resolve_ids_with_descendants(db, revision_id, section_id))
            rows = [row for row in rows if row['section_id'] in section_ids]
        return [
            PracticeCandidate(
                question_id=row['question_id'],
                bank_item_id=row['bank_item_id'],
                max_score=row['score'],
                display_config={
                    **(row['settings'] or {}),
                    'bank_high_error': {
                        key: row[key] for key in ('low_accuracy', 'slow', 'correct_rate', 'avg_duration_ms')
                    },
                },
            )
            for row in rows[:limit]
        ]


bank_high_error_service = BankHighErrorService()
