from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, and_, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.material import (
    QbMaterial,
    QbMaterialAnchor,
    QbMaterialRevision,
    QbQuestionInteraction,
    QbQuestionInteractionCandidate,
    QbQuestionMaterial,
)
from backend.app.question_bank_v2.schema.material import (
    CreateMaterialAnchorParam,
    CreateMaterialRevisionParam,
    CreateQuestionInteractionParam,
    QuestionMaterialParam,
)


class CRUDMaterial(CRUDPlus[QbMaterial]):
    """材料稳定身份数据库操作类"""

    @staticmethod
    def _active_stmt() -> Select[tuple[QbMaterial]]:
        return select(QbMaterial).where(QbMaterial.deleted == 0)

    async def get(self, db: AsyncSession, pk: int, *, for_update: bool = False) -> QbMaterial | None:
        """获取材料稳定身份"""
        stmt = self._active_stmt().where(QbMaterial.id == pk)
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def get_by_code(self, db: AsyncSession, code: str) -> QbMaterial | None:
        """通过稳定业务编码获取材料"""
        return (await db.execute(self._active_stmt().where(QbMaterial.code == code))).scalars().first()

    async def get_list(
        self,
        db: AsyncSession,
        *,
        status: str | None = None,
        revision_status: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """获取材料管理列表，展示每份材料最近版本"""
        latest_revision = (
            select(
                QbMaterialRevision.material_id,
                func.max(QbMaterialRevision.revision_no).label('revision_no'),
            )
            .where(QbMaterialRevision.deleted == 0)
            .group_by(QbMaterialRevision.material_id)
            .subquery()
        )
        stmt = (
            select(
                QbMaterial.id,
                QbMaterial.code,
                QbMaterial.status,
                QbMaterialRevision.id.label('revision_id'),
                QbMaterialRevision.revision_no,
                QbMaterialRevision.status.label('revision_status'),
                QbMaterialRevision.title,
                QbMaterialRevision.content_format,
                QbMaterialRevision.source_name,
                QbMaterialRevision.updated_time,
            )
            .join(latest_revision, latest_revision.c.material_id == QbMaterial.id)
            .join(
                QbMaterialRevision,
                and_(
                    QbMaterialRevision.material_id == latest_revision.c.material_id,
                    QbMaterialRevision.revision_no == latest_revision.c.revision_no,
                    QbMaterialRevision.deleted == 0,
                ),
            )
            .where(QbMaterial.deleted == 0)
        )
        if status is not None:
            stmt = stmt.where(QbMaterial.status == status)
        if revision_status is not None:
            stmt = stmt.where(QbMaterialRevision.status == revision_status)
        if keyword:
            stmt = stmt.where(QbMaterial.code.ilike(f'%{keyword}%') | QbMaterialRevision.title.ilike(f'%{keyword}%'))
        stmt = stmt.order_by(QbMaterialRevision.updated_time.desc(), QbMaterial.id.desc()).offset(offset).limit(limit)
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    def get_list_select(
        self,
        *,
        status: str | None = None,
        revision_status: str | None = None,
        keyword: str | None = None,
    ) -> Select:
        """构建材料管理列表 Select 表达句，供给 paging_data 使用"""
        latest_revision = (
            select(
                QbMaterialRevision.material_id,
                func.max(QbMaterialRevision.revision_no).label('revision_no'),
            )
            .where(QbMaterialRevision.deleted == 0)
            .group_by(QbMaterialRevision.material_id)
            .subquery()
        )
        stmt = (
            select(
                QbMaterial.id,
                QbMaterial.code,
                QbMaterial.status,
                QbMaterialRevision.id.label('revision_id'),
                QbMaterialRevision.revision_no,
                QbMaterialRevision.status.label('revision_status'),
                QbMaterialRevision.title,
                QbMaterialRevision.content_format,
                QbMaterialRevision.source_name,
                QbMaterialRevision.updated_time,
            )
            .join(latest_revision, latest_revision.c.material_id == QbMaterial.id)
            .join(
                QbMaterialRevision,
                and_(
                    QbMaterialRevision.material_id == latest_revision.c.material_id,
                    QbMaterialRevision.revision_no == latest_revision.c.revision_no,
                    QbMaterialRevision.deleted == 0,
                ),
            )
            .where(QbMaterial.deleted == 0)
        )
        if status is not None:
            stmt = stmt.where(QbMaterial.status == status)
        if revision_status is not None:
            stmt = stmt.where(QbMaterialRevision.status == revision_status)
        if keyword:
            stmt = stmt.where(QbMaterial.code.ilike(f'%{keyword}%') | QbMaterialRevision.title.ilike(f'%{keyword}%'))
        return stmt.order_by(QbMaterialRevision.updated_time.desc(), QbMaterial.id.desc())

    async def create(self, db: AsyncSession, *, code: str, status: str, created_by: int) -> QbMaterial:
        """创建材料稳定身份"""
        material = QbMaterial(code=code, status=status, created_by=created_by)
        db.add(material)
        await db.flush()
        return material

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """更新材料稳定身份"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0)


class CRUDMaterialRevision(CRUDPlus[QbMaterialRevision]):
    """材料版本数据库操作类"""

    async def get(
        self,
        db: AsyncSession,
        pk: int,
        *,
        material_id: int | None = None,
        for_update: bool = False,
    ) -> QbMaterialRevision | None:
        """获取材料版本"""
        stmt = select(QbMaterialRevision).where(QbMaterialRevision.id == pk, QbMaterialRevision.deleted == 0)
        if material_id is not None:
            stmt = stmt.where(QbMaterialRevision.material_id == material_id)
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def get_latest(self, db: AsyncSession, material_id: int) -> QbMaterialRevision | None:
        """获取材料最近版本"""
        stmt = (
            select(QbMaterialRevision)
            .where(QbMaterialRevision.material_id == material_id, QbMaterialRevision.deleted == 0)
            .order_by(QbMaterialRevision.revision_no.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_all(self, db: AsyncSession, material_id: int) -> Sequence[QbMaterialRevision]:
        """获取材料全部版本"""
        stmt = (
            select(QbMaterialRevision)
            .where(QbMaterialRevision.material_id == material_id, QbMaterialRevision.deleted == 0)
            .order_by(QbMaterialRevision.revision_no.desc())
        )
        return (await db.execute(stmt)).scalars().all()

    def get_list_select(self, *, material_id: int) -> Select:
        """构建材料版本游标分页查询"""
        return (
            select(QbMaterialRevision)
            .where(QbMaterialRevision.material_id == material_id, QbMaterialRevision.deleted == 0)
            .order_by(QbMaterialRevision.revision_no.desc(), QbMaterialRevision.id.desc())
        )

    async def get_next_revision_no(self, db: AsyncSession, material_id: int) -> int:
        """获取下一个材料版本号"""
        result = await db.execute(
            select(func.coalesce(func.max(QbMaterialRevision.revision_no), 0) + 1).where(
                QbMaterialRevision.material_id == material_id
            )
        )
        return int(result.scalar_one())

    async def get_reference_states(
        self,
        db: AsyncSession,
        references: Sequence[tuple[int, int]],
    ) -> dict[tuple[int, int], dict[str, Any]]:
        """批量获取材料身份与固定版本状态"""
        keys = set(references)
        if not keys:
            return {}
        stmt = (
            select(
                QbMaterialRevision.material_id,
                QbMaterialRevision.id.label('material_revision_id'),
                QbMaterial.status.label('material_status'),
                QbMaterialRevision.status.label('revision_status'),
                QbMaterialRevision.content_hash,
            )
            .join(
                QbMaterial,
                and_(QbMaterial.id == QbMaterialRevision.material_id, QbMaterial.deleted == 0),
            )
            .where(
                QbMaterialRevision.deleted == 0,
                tuple_(QbMaterialRevision.material_id, QbMaterialRevision.id).in_(keys),
            )
        )
        rows = [dict(row) for row in (await db.execute(stmt)).mappings().all()]
        return {(row['material_id'], row['material_revision_id']): row for row in rows}

    async def create(
        self,
        db: AsyncSession,
        *,
        material_id: int,
        revision_no: int,
        obj: CreateMaterialRevisionParam,
        created_by: int,
    ) -> QbMaterialRevision:
        """创建材料草稿版本"""
        revision = QbMaterialRevision(
            material_id=material_id,
            revision_no=revision_no,
            created_by=created_by,
            **obj.model_dump(),
        )
        db.add(revision)
        await db.flush()
        return revision

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """更新材料草稿版本"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0, status='draft')


class CRUDQuestionMaterial(CRUDPlus[QbQuestionMaterial]):
    """题目材料关联数据库操作类"""

    @staticmethod
    def _detail_stmt() -> Select:
        return (
            select(
                QbQuestionMaterial.id,
                QbQuestionMaterial.question_id,
                QbQuestionMaterial.material_id,
                QbQuestionMaterial.material_revision_id,
                QbQuestionMaterial.role,
                QbQuestionMaterial.sort_order,
                QbQuestionMaterial.display_config,
                QbMaterial.status.label('material_status'),
                QbMaterialRevision.status.label('revision_status'),
                QbMaterialRevision.title,
                QbMaterialRevision.content,
                QbMaterialRevision.content_format,
                QbMaterialRevision.structured_data,
                QbMaterialRevision.source_name,
                QbMaterialRevision.source_url,
                QbMaterialRevision.content_hash,
            )
            .join(
                QbMaterial,
                and_(QbMaterial.id == QbQuestionMaterial.material_id, QbMaterial.deleted == 0),
            )
            .join(
                QbMaterialRevision,
                and_(
                    QbMaterialRevision.id == QbQuestionMaterial.material_revision_id,
                    QbMaterialRevision.material_id == QbQuestionMaterial.material_id,
                    QbMaterialRevision.deleted == 0,
                ),
            )
            .where(QbQuestionMaterial.deleted == 0)
        )

    async def get_all(self, db: AsyncSession, question_id: int) -> list[dict[str, Any]]:
        """获取一个题目的有序材料"""
        stmt = (
            self
            ._detail_stmt()
            .where(QbQuestionMaterial.question_id == question_id)
            .order_by(QbQuestionMaterial.sort_order, QbQuestionMaterial.id)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    async def get(self, db: AsyncSession, pk: int, *, question_id: int) -> QbQuestionMaterial | None:
        """获取题目的一条材料关联"""
        stmt = select(QbQuestionMaterial).where(
            QbQuestionMaterial.id == pk,
            QbQuestionMaterial.question_id == question_id,
            QbQuestionMaterial.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_all_by_questions(
        self,
        db: AsyncSession,
        question_ids: Sequence[int],
    ) -> list[dict[str, Any]]:
        """批量获取多个题目的有序材料"""
        if not question_ids:
            return []
        stmt = (
            self
            ._detail_stmt()
            .where(QbQuestionMaterial.question_id.in_(set(question_ids)))
            .order_by(
                QbQuestionMaterial.question_id,
                QbQuestionMaterial.sort_order,
                QbQuestionMaterial.id,
            )
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    async def replace(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        items: list[QuestionMaterialParam],
        user_id: int,
    ) -> None:
        """全量替换题目材料关联"""
        existing = await db.execute(
            select(QbQuestionMaterial).where(
                QbQuestionMaterial.question_id == question_id,
                QbQuestionMaterial.deleted == 0,
            )
        )
        for item in existing.scalars().all():
            await self.delete_model(db, item.id)
        db.add_all([
            QbQuestionMaterial(
                question_id=question_id,
                created_by=user_id,
                **item.model_dump(),
            )
            for item in items
        ])
        await db.flush()


class CRUDMaterialAnchor(CRUDPlus[QbMaterialAnchor]):
    """材料版本锚点数据库操作类"""

    async def get(
        self,
        db: AsyncSession,
        pk: int,
        *,
        material_id: int,
        material_revision_id: int,
    ) -> QbMaterialAnchor | None:
        """获取材料版本锚点"""
        stmt = select(QbMaterialAnchor).where(
            QbMaterialAnchor.id == pk,
            QbMaterialAnchor.material_id == material_id,
            QbMaterialAnchor.material_revision_id == material_revision_id,
            QbMaterialAnchor.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_by_key(
        self,
        db: AsyncSession,
        *,
        material_revision_id: int,
        anchor_key: str,
    ) -> QbMaterialAnchor | None:
        """按材料版本内稳定键获取锚点"""
        stmt = select(QbMaterialAnchor).where(
            QbMaterialAnchor.material_revision_id == material_revision_id,
            QbMaterialAnchor.anchor_key == anchor_key,
            QbMaterialAnchor.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_existing_keys(
        self,
        db: AsyncSession,
        *,
        material_revision_id: int,
        anchor_keys: Sequence[str],
    ) -> set[str]:
        """批量获取材料版本中已存在的锚点键"""
        if not anchor_keys:
            return set()
        rows = await db.execute(
            select(QbMaterialAnchor.anchor_key).where(
                QbMaterialAnchor.material_revision_id == material_revision_id,
                QbMaterialAnchor.anchor_key.in_(anchor_keys),
                QbMaterialAnchor.deleted == 0,
            )
        )
        return set(rows.scalars().all())

    async def get_all(self, db: AsyncSession, *, material_revision_id: int) -> Sequence[QbMaterialAnchor]:
        """获取材料版本全部锚点"""
        stmt = (
            select(QbMaterialAnchor)
            .where(
                QbMaterialAnchor.material_revision_id == material_revision_id,
                QbMaterialAnchor.deleted == 0,
            )
            .order_by(QbMaterialAnchor.anchor_type, QbMaterialAnchor.anchor_key, QbMaterialAnchor.id)
        )
        return (await db.execute(stmt)).scalars().all()

    def get_list_select(self, *, material_revision_id: int) -> Select:
        """构建材料锚点游标分页查询"""
        return (
            select(QbMaterialAnchor)
            .where(
                QbMaterialAnchor.material_revision_id == material_revision_id,
                QbMaterialAnchor.deleted == 0,
            )
            .order_by(QbMaterialAnchor.anchor_type, QbMaterialAnchor.anchor_key, QbMaterialAnchor.id)
        )

    async def get_many(
        self,
        db: AsyncSession,
        *,
        material_revision_id: int,
        anchor_ids: Sequence[int],
    ) -> Sequence[QbMaterialAnchor]:
        """批量获取同一材料版本的候选锚点"""
        if not anchor_ids:
            return []
        stmt = select(QbMaterialAnchor).where(
            QbMaterialAnchor.id.in_(set(anchor_ids)),
            QbMaterialAnchor.material_revision_id == material_revision_id,
            QbMaterialAnchor.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().all()

    async def create(
        self,
        db: AsyncSession,
        *,
        material_id: int,
        material_revision_id: int,
        content_hash: str | None,
        obj: CreateMaterialAnchorParam,
        user_id: int,
    ) -> QbMaterialAnchor:
        """创建材料锚点"""
        anchor = QbMaterialAnchor(
            material_id=material_id,
            material_revision_id=material_revision_id,
            content_hash=content_hash,
            created_by=user_id,
            **obj.model_dump(),
        )
        db.add(anchor)
        await db.flush()
        return anchor

    async def create_all(
        self,
        db: AsyncSession,
        *,
        material_id: int,
        material_revision_id: int,
        content_hash: str | None,
        items: Sequence[CreateMaterialAnchorParam],
        user_id: int,
    ) -> list[QbMaterialAnchor]:
        """批量创建锚点并只 flush 一次"""
        anchors = [
            QbMaterialAnchor(
                material_id=material_id,
                material_revision_id=material_revision_id,
                content_hash=content_hash,
                created_by=user_id,
                **item.model_dump(),
            )
            for item in items
        ]
        db.add_all(anchors)
        await db.flush()
        return anchors

    async def update(self, db: AsyncSession, pk: int, *, data: dict[str, Any]) -> int:
        """更新材料锚点"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0)

    async def is_referenced(self, db: AsyncSession, *, anchor_id: int) -> bool:
        """判断锚点是否仍被交互定义引用"""
        count = await db.scalar(
            select(func.count(QbQuestionInteractionCandidate.id)).where(
                QbQuestionInteractionCandidate.anchor_id == anchor_id,
                QbQuestionInteractionCandidate.deleted == 0,
            )
        )
        return int(count or 0) > 0


class CRUDQuestionInteraction(CRUDPlus[QbQuestionInteraction]):
    """题目交互定义数据库操作类"""

    async def get(self, db: AsyncSession, pk: int, *, question_id: int) -> QbQuestionInteraction | None:
        """获取题目交互定义"""
        stmt = select(QbQuestionInteraction).where(
            QbQuestionInteraction.id == pk,
            QbQuestionInteraction.question_id == question_id,
            QbQuestionInteraction.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_by_key(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        interaction_key: str,
    ) -> QbQuestionInteraction | None:
        """按题目内稳定键获取交互定义"""
        stmt = select(QbQuestionInteraction).where(
            QbQuestionInteraction.question_id == question_id,
            QbQuestionInteraction.interaction_key == interaction_key,
            QbQuestionInteraction.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    def _detail_stmt() -> Select:
        """构建交互定义与候选锚点聚合查询"""
        return (
            select(
                QbQuestionInteraction.id,
                QbQuestionInteraction.question_id,
                QbQuestionInteraction.interaction_key,
                QbQuestionInteraction.interaction_type,
                QbQuestionInteraction.instruction,
                QbQuestionInteraction.question_material_id,
                QbQuestionInteraction.material_revision_id,
                QbQuestionInteraction.title,
                QbQuestionInteraction.selection_mode,
                QbQuestionInteraction.min_selections,
                QbQuestionInteraction.max_selections,
                QbQuestionInteraction.config,
                QbQuestionInteraction.status,
                QbQuestionInteractionCandidate.id.label('candidate_id'),
                QbQuestionInteractionCandidate.anchor_id,
                QbQuestionInteractionCandidate.candidate_role,
                QbQuestionInteractionCandidate.label.label('candidate_label'),
                QbQuestionInteractionCandidate.sort_order.label('candidate_sort_order'),
                QbMaterialAnchor.material_id.label('anchor_material_id'),
                QbMaterialAnchor.anchor_key,
                QbMaterialAnchor.anchor_type,
                QbMaterialAnchor.text.label('anchor_text'),
                QbMaterialAnchor.semantic_role,
                QbMaterialAnchor.block_id,
                QbMaterialAnchor.start_offset,
                QbMaterialAnchor.end_offset,
                QbMaterialAnchor.asset_id,
                QbMaterialAnchor.bbox,
                QbMaterialAnchor.polygon,
                QbMaterialAnchor.table_cell,
                QbMaterialAnchor.source.label('anchor_source'),
                QbMaterialAnchor.confidence,
                QbMaterialAnchor.content_hash.label('anchor_content_hash'),
                QbMaterialAnchor.status.label('anchor_status'),
                QbMaterialAnchor.extra_data,
            )
            .select_from(QbQuestionInteraction)
            .outerjoin(
                QbQuestionInteractionCandidate,
                and_(
                    QbQuestionInteractionCandidate.interaction_id == QbQuestionInteraction.id,
                    QbQuestionInteractionCandidate.deleted == 0,
                ),
            )
            .outerjoin(
                QbMaterialAnchor,
                and_(
                    QbMaterialAnchor.id == QbQuestionInteractionCandidate.anchor_id,
                    QbMaterialAnchor.material_revision_id == QbQuestionInteractionCandidate.material_revision_id,
                    QbMaterialAnchor.deleted == 0,
                ),
            )
            .where(QbQuestionInteraction.deleted == 0)
        )

    async def get_all(
        self,
        db: AsyncSession,
        *,
        question_ids: Sequence[int] | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """批量获取题目交互定义和候选锚点"""
        stmt = self._detail_stmt()
        if question_ids:
            stmt = stmt.where(QbQuestionInteraction.question_id.in_(set(question_ids)))
        if active_only:
            stmt = stmt.where(QbQuestionInteraction.status == 'active')
        stmt = stmt.order_by(
            QbQuestionInteraction.question_id,
            QbQuestionInteraction.id,
            QbQuestionInteractionCandidate.candidate_role,
            QbQuestionInteractionCandidate.sort_order,
            QbQuestionInteractionCandidate.id,
        )
        rows = (await db.execute(stmt)).mappings().all()
        interactions: dict[int, dict[str, Any]] = {}
        for row in rows:
            interaction = interactions.setdefault(
                int(row['id']),
                {
                    key: row[key]
                    for key in (
                        'id',
                        'question_id',
                        'interaction_key',
                        'interaction_type',
                        'instruction',
                        'question_material_id',
                        'material_revision_id',
                        'title',
                        'selection_mode',
                        'min_selections',
                        'max_selections',
                        'config',
                        'status',
                    )
                }
                | {'candidates': []},
            )
            if row['candidate_id'] is not None:
                interaction['candidates'].append({
                    'id': row['candidate_id'],
                    'anchor_id': row['anchor_id'],
                    'candidate_role': row['candidate_role'],
                    'label': row['candidate_label'],
                    'sort_order': row['candidate_sort_order'],
                    'material_revision_id': row['material_revision_id'],
                    'anchor': {
                        'id': row['anchor_id'],
                        'material_id': row['anchor_material_id'],
                        'material_revision_id': row['material_revision_id'],
                        'anchor_key': row['anchor_key'],
                        'anchor_type': row['anchor_type'],
                        'text': row['anchor_text'],
                        'semantic_role': row['semantic_role'],
                        'block_id': row['block_id'],
                        'start_offset': row['start_offset'],
                        'end_offset': row['end_offset'],
                        'asset_id': row['asset_id'],
                        'bbox': row['bbox'],
                        'polygon': row['polygon'],
                        'table_cell': row['table_cell'],
                        'source': row['anchor_source'],
                        'confidence': row['confidence'],
                        'content_hash': row['anchor_content_hash'],
                        'status': row['anchor_status'],
                        'extra_data': row['extra_data'],
                    },
                })
        return list(interactions.values())

    async def create(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        material_revision_id: int | None,
        obj: CreateQuestionInteractionParam,
        user_id: int,
    ) -> QbQuestionInteraction:
        """创建交互定义及候选锚点"""
        data = obj.model_dump(exclude={'candidates'})
        interaction = QbQuestionInteraction(
            question_id=question_id,
            material_revision_id=material_revision_id,
            created_by=user_id,
            **data,
        )
        db.add(interaction)
        await db.flush()
        await self.replace_candidates(
            db,
            interaction=interaction,
            items=obj.candidates,
            user_id=user_id,
        )
        return interaction

    async def update_definition(
        self,
        db: AsyncSession,
        *,
        interaction: QbQuestionInteraction,
        material_revision_id: int | None,
        obj: CreateQuestionInteractionParam,
        user_id: int,
    ) -> None:
        """全量更新交互定义及候选锚点"""
        data = obj.model_dump(exclude={'candidates'})
        data.update({'material_revision_id': material_revision_id, 'updated_by': user_id})
        await self.update_model_by_column(db, data, id=interaction.id, deleted=0)
        interaction.material_revision_id = material_revision_id
        await self.replace_candidates(db, interaction=interaction, items=obj.candidates, user_id=user_id)

    async def replace_candidates(
        self,
        db: AsyncSession,
        *,
        interaction: QbQuestionInteraction,
        items: Sequence[Any],
        user_id: int,
    ) -> None:
        """全量替换交互候选锚点"""
        existing = await db.execute(
            select(QbQuestionInteractionCandidate).where(
                QbQuestionInteractionCandidate.interaction_id == interaction.id,
                QbQuestionInteractionCandidate.deleted == 0,
            )
        )
        for item in existing.scalars().all():
            await db.delete(item)
        db.add_all([
            QbQuestionInteractionCandidate(
                interaction_id=interaction.id,
                material_revision_id=interaction.material_revision_id,
                created_by=user_id,
                **item.model_dump(),
            )
            for item in items
        ])
        await db.flush()


material_dao: CRUDMaterial = CRUDMaterial(QbMaterial)
material_revision_dao: CRUDMaterialRevision = CRUDMaterialRevision(QbMaterialRevision)
question_material_dao: CRUDQuestionMaterial = CRUDQuestionMaterial(QbQuestionMaterial)
material_anchor_dao: CRUDMaterialAnchor = CRUDMaterialAnchor(QbMaterialAnchor)
question_interaction_dao: CRUDQuestionInteraction = CRUDQuestionInteraction(QbQuestionInteraction)
