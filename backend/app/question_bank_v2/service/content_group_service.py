import re

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.model.bank import QbBankSection
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint
from backend.app.question_bank_v2.schema.user_content import ContentGroupNode


def _unique_ids(ids: list[int]) -> list[int]:
    """保持顺序去重题目 ID"""
    return list(dict.fromkeys(ids))


def _point_ids_from_path(path: str | None) -> set[int]:
    """从物化路径里解析祖先知识点 ID。

    线上数据的 path 是点分隔的 ID 链（如 ``588.589``），也兼容斜杠写法。
    """
    if not path:
        return set()
    return {int(part) for part in re.split(r'[^0-9]+', str(path)) if part}


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

    #: 命中节点同时有子节点时，直属题挂到这个虚拟叶子下，保证可练
    DIRECT_POINT_LABEL = '本级题目'

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
        """把错题压到题库下的章节一层：子章节的错题归并到根章节，返回题库→章节两级。

        题库章节节点只做统计展示，不下发题目 ID；
        具体题目按节点上下文（bank_id/section_id）由会话/采集接口现查。
        """
        direct_counts = {
            int(row['section_id']): int(row['count'] or 0)
            for row in related_rows
            if row['section_id'] is not None
        }
        nodes = {
            int(row['id']): ContentGroupNode(
                id=int(row['id']),
                bank_id=bank_id,
                name=row['name'],
                count=0,
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

        roots: list[ContentGroupNode] = []
        for section_id, node in nodes.items():
            if parent_by_id.get(section_id) is not None:
                continue
            if node.count <= 0:
                continue
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
        ungrouped_children: dict[str, ContentGroupNode] = {}
        for row in rows:
            if row['bank_id'] is not None:
                continue
            count = int(row['count'] or 0)
            question_ids = [int(qid) for qid in (row.get('question_ids') or [])]
            ungrouped_count += count
            ungrouped_ids.extend(question_ids)
            source_name = str(row.get('external_source') or '').strip()
            if source_name:
                child = ungrouped_children.setdefault(
                    source_name,
                    ContentGroupNode(id=None, name=source_name, count=0, question_ids=[]),
                )
                child.count += count
                child.question_ids.extend(question_ids)
        if ungrouped_count:
            for child in ungrouped_children.values():
                child.question_ids = _unique_ids(child.question_ids)
            roots.append(
                ContentGroupNode(
                    id=0,
                    name=ungrouped_name,
                    count=ungrouped_count,
                    question_ids=[] if ungrouped_children else _unique_ids(ungrouped_ids),
                    children=list(ungrouped_children.values()),
                )
            )
        return roots

    @staticmethod
    async def _get_knowledge_point_rows(
        db: AsyncSession,
        point_ids: set[int],
    ) -> Sequence[dict[str, Any]]:
        if not point_ids:
            return []
        return (
            await db.execute(
                select(
                    QbKnowledgePoint.id,
                    QbKnowledgePoint.name,
                    QbKnowledgePoint.parent_id,
                    QbKnowledgePoint.path,
                    QbKnowledgePoint.sort_order,
                ).where(
                    QbKnowledgePoint.id.in_(point_ids),
                    QbKnowledgePoint.deleted == 0,
                )
            )
        ).mappings().all()

    @classmethod
    async def _load_knowledge_point_closure(
        cls,
        db: AsyncSession,
        tagged_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        """加载命中的知识点及其全部祖先，让统计结果能连回知识体系根节点。

        优先用物化路径一次性补齐；路径缺失或断裂时再按 parent_id 逐层上溯。
        """
        points: dict[int, dict[str, Any]] = {
            int(row['id']): dict(row) for row in await cls._get_knowledge_point_rows(db, tagged_ids)
        }
        pending: set[int] = set()
        for point in points.values():
            pending.update(_point_ids_from_path(point.get('path')))
            parent_id = point.get('parent_id')
            if parent_id is not None:
                pending.add(int(parent_id))
        pending -= points.keys()

        while pending:
            batch = await cls._get_knowledge_point_rows(db, pending)
            next_pending: set[int] = set()
            for row in batch:
                point_id = int(row['id'])
                if point_id in points:
                    continue
                points[point_id] = dict(row)
                parent_id = row.get('parent_id')
                if parent_id is not None:
                    next_pending.add(int(parent_id))
                next_pending.update(_point_ids_from_path(row.get('path')))
            pending = next_pending - points.keys()
        return points

    @staticmethod
    def _knowledge_direct_sets(
        *,
        points: dict[int, dict[str, Any]],
        tagged: dict[int, dict[str, Any]],
    ) -> tuple[dict[int, set[int]], dict[int, int]]:
        """整理命中知识点的直属题目 ID；数量兜底避免节点被当成 0 题丢弃"""
        direct_ids: dict[int, set[int]] = {}
        direct_extra: dict[int, int] = {}
        for point_id, row in tagged.items():
            if point_id not in points:
                continue
            question_ids = {int(qid) for qid in (row.get('question_ids') or [])}
            direct_ids[point_id] = question_ids
            direct_extra[point_id] = max(0, int(row.get('count') or 0) - len(question_ids))
        return direct_ids, direct_extra

    @staticmethod
    def _knowledge_children_index(points: dict[int, dict[str, Any]]) -> dict[int | None, list[int]]:
        """按 parent_id 建索引，同层按 sort_order 排序"""
        children_by_parent: dict[int | None, list[int]] = {}
        for point_id, point in points.items():
            parent_id = point.get('parent_id')
            parent = int(parent_id) if parent_id is not None and int(parent_id) in points else None
            children_by_parent.setdefault(parent, []).append(point_id)
        for child_ids in children_by_parent.values():
            child_ids.sort(key=lambda pid: (int(points[pid].get('sort_order') or 0), pid))
        return children_by_parent

    @classmethod
    def _aggregate_knowledge_questions(
        cls,
        point_id: int,
        *,
        children_by_parent: dict[int | None, list[int]],
        direct_ids: dict[int, set[int]],
        direct_extra: dict[int, int],
        memo: dict[int, tuple[set[int], int]],
    ) -> tuple[set[int], int]:
        """记忆化汇总某节点及其后代的题目 ID 去重并集"""
        if point_id in memo:
            return memo[point_id]
        merged = set(direct_ids.get(point_id, set()))
        extra = direct_extra.get(point_id, 0)
        for child_id in children_by_parent.get(point_id, []):
            child_ids, child_extra = cls._aggregate_knowledge_questions(
                child_id,
                children_by_parent=children_by_parent,
                direct_ids=direct_ids,
                direct_extra=direct_extra,
                memo=memo,
            )
            merged.update(child_ids)
            extra += child_extra
        memo[point_id] = (merged, extra)
        return memo[point_id]

    @classmethod
    def _build_knowledge_nodes(
        cls,
        *,
        points: dict[int, dict[str, Any]],
        tagged: dict[int, dict[str, Any]],
    ) -> list[ContentGroupNode]:
        """把知识点闭包组装成树；父节点题数取后代命中题的去重并集"""
        direct_ids, direct_extra = cls._knowledge_direct_sets(points=points, tagged=tagged)
        children_by_parent = cls._knowledge_children_index(points)
        memo: dict[int, tuple[set[int], int]] = {}
        nodes: dict[int, ContentGroupNode] = {}

        def build(point_id: int) -> ContentGroupNode:
            if point_id in nodes:
                return nodes[point_id]
            question_ids, extra = cls._aggregate_knowledge_questions(
                point_id,
                children_by_parent=children_by_parent,
                direct_ids=direct_ids,
                direct_extra=direct_extra,
                memo=memo,
            )
            node = ContentGroupNode(
                id=point_id,
                name=str(points[point_id].get('name') or ''),
                count=len(question_ids) + extra,
            )
            nodes[point_id] = node
            child_ids = children_by_parent.get(point_id, [])
            if not child_ids:
                node.question_ids = sorted(direct_ids.get(point_id, set()))
                return node

            children: list[ContentGroupNode] = []
            own_ids = direct_ids.get(point_id, set())
            if own_ids or direct_extra.get(point_id, 0) > 0:
                # 父节点自己也被命中：单开一个虚拟叶子承接直属题，否则展开后练不到
                children.append(
                    ContentGroupNode(
                        id=point_id,
                        name=cls.DIRECT_POINT_LABEL,
                        count=len(own_ids) + direct_extra.get(point_id, 0),
                        question_ids=sorted(own_ids),
                    )
                )
            children.extend(build(child_id) for child_id in child_ids)
            node.children = children
            return node

        roots = [build(point_id) for point_id in children_by_parent.get(None, [])]
        roots = [root for root in roots if root.count > 0]
        # 单一根节点只是体系壳（如「政治」），直接下钻一层，避免首屏只有一行
        if len(roots) == 1 and roots[0].children:
            return roots[0].children
        return roots

    @classmethod
    async def build_knowledge_tree(
        cls,
        *,
        db: AsyncSession,
        rows: Sequence[dict[str, Any]],
    ) -> list[ContentGroupNode]:
        """把命中的知识点补成可逐级展开的知识体系树。

        父节点只作分组（题数=后代命中题去重后的总数），叶子保留题目 ID 供练习；
        父节点自身也有直属命中题时，额外挂一个「本级题目」叶子。
        """
        tagged = {
            int(row['id']): dict(row)
            for row in rows
            if row.get('id') is not None and int(row.get('count') or 0) > 0
        }
        if not tagged:
            return []
        points = await cls._load_knowledge_point_closure(db, set(tagged))
        return cls._build_knowledge_nodes(points=points, tagged=tagged)


content_group_service: ContentGroupService = ContentGroupService()
