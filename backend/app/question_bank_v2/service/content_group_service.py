from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.model.bank import QbBankSection
from backend.app.question_bank_v2.model.catalog import QbCollection, QbCollectionBank
from backend.app.question_bank_v2.schema.user_content import ContentGroupNode


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
                count=direct_counts.get(int(row['id']), 0),
            )
            for row in section_rows
        }
        parent_by_id = {
            int(row['id']): int(row['parent_id']) if row['parent_id'] is not None else None
            for row in section_rows
        }
        keep = set(direct_counts)
        for section_id in list(keep):
            parent_id = parent_by_id.get(section_id)
            while parent_id is not None and parent_id not in keep:
                keep.add(parent_id)
                parent_id = parent_by_id.get(parent_id)
        depth_by_id = {int(row['id']): int(row['depth']) for row in section_rows}
        for section_id in sorted(keep, key=depth_by_id.get, reverse=True):
            parent_id = parent_by_id.get(section_id)
            if parent_id in keep:
                nodes[parent_id].count += nodes[section_id].count
        roots: list[ContentGroupNode] = []
        for row in section_rows:
            section_id = int(row['id'])
            if section_id not in keep:
                continue
            parent_id = parent_by_id.get(section_id)
            if parent_id in keep:
                nodes[parent_id].children.append(nodes[section_id])
            else:
                roots.append(nodes[section_id])
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

    @staticmethod
    async def _get_collection_rows(
        db: AsyncSession,
        bank_ids: set[int],
    ) -> Sequence[dict[str, Any]]:
        if not bank_ids:
            return []
        return (
            await db.execute(
                select(
                    QbCollection.id,
                    QbCollection.parent_id,
                    QbCollection.name,
                    QbCollection.sort_order,
                    QbCollectionBank.bank_id,
                    QbCollectionBank.sort_order.label('bank_sort_order'),
                )
                .select_from(QbCollection)
                .outerjoin(
                    QbCollectionBank,
                    and_(
                        QbCollectionBank.collection_id == QbCollection.id,
                        QbCollectionBank.bank_id.in_(bank_ids),
                        QbCollectionBank.is_active.is_(True),
                        QbCollectionBank.deleted == 0,
                    ),
                )
                .where(
                    QbCollection.visibility == 'public',
                    QbCollection.status == 'active',
                    QbCollection.deleted == 0,
                )
                .order_by(QbCollection.sort_order, QbCollection.id, QbCollectionBank.sort_order)
            )
        ).mappings().all()

    @staticmethod
    def _rollup_collection(node: ContentGroupNode) -> int:
        node.count += sum(
            ContentGroupService._rollup_collection(child)
            for child in node.children
            if child.type == 'collection'
        )
        return node.count

    @classmethod
    def _build_collection_roots(
        cls,
        collection_rows: Sequence[dict[str, Any]],
        banks: dict[int, ContentGroupNode],
    ) -> tuple[list[ContentGroupNode], set[int]]:
        collections = {
            int(row['id']): ContentGroupNode(
                id=int(row['id']),
                name=row['name'],
                count=0,
                type='collection',
            )
            for row in collection_rows
        }
        collection_ids = list(dict.fromkeys(int(row['id']) for row in collection_rows))
        collection_parent = {
            int(row['id']): int(row['parent_id']) if row['parent_id'] is not None else None
            for row in collection_rows
        }
        mounted_banks: set[int] = set()
        for row in collection_rows:
            if row['bank_id'] is None:
                continue
            bank_id = int(row['bank_id'])
            if bank_id in mounted_banks:
                continue
            collections[int(row['id'])].children.append(banks[bank_id])
            collections[int(row['id'])].count += banks[bank_id].count
            mounted_banks.add(bank_id)
        keep_collections = {cid for cid, node in collections.items() if node.count > 0}
        for collection_id in list(keep_collections):
            parent_id = collection_parent.get(collection_id)
            while parent_id is not None and parent_id not in keep_collections:
                keep_collections.add(parent_id)
                parent_id = collection_parent.get(parent_id)
        roots: list[ContentGroupNode] = []
        for collection_id in collection_ids:
            if collection_id not in keep_collections:
                continue
            parent_id = collection_parent.get(collection_id)
            if parent_id in keep_collections:
                collections[parent_id].children.append(collections[collection_id])
            else:
                roots.append(collections[collection_id])
        for root in roots:
            cls._rollup_collection(root)
        return roots, mounted_banks

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
        collection_rows = await cls._get_collection_rows(db, set(banks))
        roots, mounted_banks = cls._build_collection_roots(collection_rows, banks)
        roots.extend(bank for bank_id, bank in banks.items() if bank_id not in mounted_banks)
        ungrouped_count = sum(int(row['count'] or 0) for row in rows if row['bank_id'] is None)
        if ungrouped_count:
            roots.append(ContentGroupNode(id=0, name=ungrouped_name, count=ungrouped_count))
        return roots


content_group_service: ContentGroupService = ContentGroupService()
