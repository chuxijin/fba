from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.model.bank import QbBankSection
from backend.app.question_bank_v2.schema.user_content import ContentGroupNode


def _unique_ids(ids: list[int]) -> list[int]:
    """保持顺序去重题目 ID"""
    return list(dict.fromkeys(ids))


def _section_root_of(
    section_id: int,
    parent_by_id: dict[int, int | None],
) -> int:
    """沿章节父链上溯到根章节；父链断裂时返回当前可达的最上层。"""
    seen: set[int] = set()
    current = section_id
    parent_id = parent_by_id.get(current)
    while parent_id is not None and parent_id not in seen:
        seen.add(parent_id)
        current = parent_id
        parent_id = parent_by_id.get(current)
    return current


class ContentGroupService:
    """Build collection, bank, and section trees for user-content statistics."""

    @staticmethod
    async def _get_section_rows(
        db: AsyncSession,
        revision_ids: set[int],
    ) -> Sequence[dict[str, Any]]:
        if not revision_ids:
            return []
        return (
            await db.execute(
                select(
                    QbBankSection.id,
                    QbBankSection.bank_revision_id,
                    QbBankSection.parent_id,
                    QbBankSection.name,
                    QbBankSection.depth,
                    QbBankSection.sort_order,
                ).where(
                    QbBankSection.bank_revision_id.in_(revision_ids),
                ).order_by(QbBankSection.bank_revision_id, QbBankSection.sort_order, QbBankSection.id)
            )
        ).mappings().all()

    @staticmethod
    def _build_section_tree(
        bank_id: int,
        related_rows: Sequence[dict[str, Any]],
        section_rows: Sequence[dict[str, Any]],
    ) -> list[ContentGroupNode]:
        """把错题压到题库下的章节一层：子章节的错题归并到根章节，返回题库→章节两级。"""
        direct_counts = {
            int(row['section_id']): int(row['count'] or 0)
            for row in related_rows
            if row['section_id'] is not None
        }
        direct_ids: dict[int, list[int]] = {}
        for row in related_rows:
            if row['section_id'] is None:
                continue
            ids = [int(qid) for qid in (row.get('question_ids') or [])]
            if ids:
                direct_ids.setdefault(int(row['section_id']), []).extend(ids)
        nodes = {
            int(row['id']): ContentGroupNode(
                id=int(row['id']),
                bank_id=bank_id,
                name=row['name'],
                count=0,
                question_ids=[],
            )
            for row in section_rows
        }
        parent_by_id = {
            int(row['id']): int(row['parent_id']) if row['parent_id'] is not None else None
            for row in section_rows
        }

        for section_id, count in direct_counts.items():
            root_id = _section_root_of(section_id, parent_by_id)
            if root_id not in nodes:
                continue
            nodes[root_id].count += count
            nodes[root_id].question_ids.extend(direct_ids.get(section_id, []))

        roots: list[ContentGroupNode] = []
        for section_id, node in nodes.items():
            if parent_by_id.get(section_id) is not None:
                continue
            if node.count <= 0 and not node.question_ids:
                continue
            node.question_ids = _unique_ids(node.question_ids)
            roots.append(node)
        return roots

    @classmethod
    def _build_banks(
        cls,
        bank_rows: Sequence[dict[str, Any]],
        section_rows: Sequence[dict[str, Any]],
    ) -> dict[int, ContentGroupNode]:
        sections_by_revision: dict[int, list[dict[str, Any]]] = {}
        for row in section_rows:
            sections_by_revision.setdefault(int(row['bank_revision_id']), []).append(dict(row))
        rows_by_bank: dict[int, list[dict[str, Any]]] = {}
        banks: dict[int, ContentGroupNode] = {}
        for row in bank_rows:
            bank_id = int(row['bank_id'])
            rows_by_bank.setdefault(bank_id, []).append(row)
            bank = banks.setdefault(
                bank_id,
                ContentGroupNode(id=bank_id, name=row['bank_name'], count=0),
            )
            bank.count += int(row['count'] or 0)
        for bank_id, bank in banks.items():
            related_rows = rows_by_bank[bank_id]
            # 直接挂在题库下（无章节归属）的题目 ID
            bank_related_ids: list[int] = []
            for row in related_rows:
                if row['section_id'] is not None:
                    continue
                bank_related_ids.extend(int(qid) for qid in (row.get('question_ids') or []))
            bank.question_ids = _unique_ids(bank_related_ids)
            related_revision_ids = {int(row['bank_revision_id']) for row in related_rows}
            related_sections = [
                section
                for revision_id in related_revision_ids
                for section in sections_by_revision.get(revision_id, [])
            ]
            bank.children = cls._build_section_tree(
                bank_id,
                related_rows,
                related_sections,
            )
        return banks

    @classmethod
    async def build_bank_tree(
        cls,
        *,
        db: AsyncSession,
        rows: Sequence[dict[str, Any]],
        ungrouped_name: str,
    ) -> list[ContentGroupNode]:
        bank_rows = [row for row in rows if row['bank_id'] is not None]
        revision_ids = {int(row['bank_revision_id']) for row in bank_rows}
        section_rows = await cls._get_section_rows(db, revision_ids)
        banks = cls._build_banks(bank_rows, section_rows)
        # 层级收敛为两级：题库直接作顶层，章节归并到题库下（不再按专区分组）
        roots = list(banks.values())
        ungrouped_count = 0
        ungrouped_ids: list[int] = []
        for row in rows:
            if row['bank_id'] is not None:
                continue
            ungrouped_count += int(row['count'] or 0)
            ungrouped_ids.extend(int(qid) for qid in (row.get('question_ids') or []))
        if ungrouped_count:
            roots.append(
                ContentGroupNode(
                    id=0,
                    name=ungrouped_name,
                    count=ungrouped_count,
                    question_ids=_unique_ids(ungrouped_ids),
                )
            )
        return roots


content_group_service: ContentGroupService = ContentGroupService()
