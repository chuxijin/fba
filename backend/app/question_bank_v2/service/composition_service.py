from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.cache.composition_cache import composition_cache
from backend.app.question_bank_v2.crud.crud_bank import bank_revision_dao
from backend.app.question_bank_v2.crud.crud_composition import bank_item_dao, bank_section_dao
from backend.app.question_bank_v2.crud.crud_question import question_dao
from backend.app.question_bank_v2.schema.composition import (
    CreateBankItemParam,
    CreateBankSectionParam,
    GetBankCompositionDetail,
    GetBankItemDetail,
    GetBankSectionDetail,
    UpdateBankItemParam,
    UpdateBankSectionParam,
)
from backend.common.exception import errors


class CompositionService:
    """题库版本章节与题目编排服务类"""

    @staticmethod
    async def _get_bank_revision(*, db: AsyncSession, bank_id: int, revision_id: int, draft_only: bool) -> Any:
        """获取并校验题库版本"""
        revision = await bank_revision_dao.get(db, revision_id, bank_id=bank_id)
        if revision is None:
            raise errors.NotFoundError(msg='题库版本不存在')
        if draft_only and revision.status != 'draft':
            raise errors.ConflictError(msg='已发布或已退役题库版本不可修改编排')
        return revision

    @staticmethod
    async def _validate_section_parent(
        *,
        db: AsyncSession,
        revision_id: int,
        parent_id: int | None,
        current_id: int | None = None,
    ) -> int:
        """校验章节父子关系并返回节点深度"""
        if parent_id is None:
            return 0
        if current_id is not None and parent_id == current_id:
            raise errors.ConflictError(msg='章节不能以自身作为父级')
        visited: set[int] = set()
        node_id: int | None = parent_id
        parent_depth = 0
        while node_id is not None:
            if node_id in visited:
                raise errors.ConflictError(msg='章节父子关系存在循环')
            visited.add(node_id)
            node = await bank_section_dao.get(db, node_id, revision_id=revision_id)
            if node is None:
                raise errors.NotFoundError(msg='父章节不存在或不属于当前题库版本')
            if node.id == parent_id:
                parent_depth = node.depth
            if current_id is not None and node.id == current_id:
                raise errors.ConflictError(msg='不能将章节移动到自己的子孙节点下')
            node_id = node.parent_id
        return parent_depth + 1

    @staticmethod
    async def _validate_question(
        *,
        db: AsyncSession,
        question_id: int,
    ) -> None:
        """校验题目存在且可用"""
        question = await question_dao.get(db, question_id)
        if question is None or question.status != 'active':
            raise errors.NotFoundError(msg='题目不存在或不可用')

    @staticmethod
    def _build_section_tree(sections: list[Any]) -> list[GetBankSectionDetail]:
        """构建题库版本章节树"""
        nodes = {
            item.id: GetBankSectionDetail(
                id=item.id,
                bank_revision_id=item.bank_revision_id,
                code=item.code,
                name=item.name,
                parent_id=item.parent_id,
                depth=item.depth,
                sort_order=item.sort_order,
            )
            for item in sections
        }
        roots: list[GetBankSectionDetail] = []
        for node in nodes.values():
            if node.parent_id is not None and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                roots.append(node)
        return roots

    @staticmethod
    async def _recalculate_section_depths(
        *,
        db: AsyncSession,
        revision_id: int,
        updated_by: int,
    ) -> None:
        """章节移动后重算整棵树的深度缓存"""
        sections = list(await bank_section_dao.get_all(db, revision_id))
        nodes = {item.id: item for item in sections}
        children: dict[int | None, list[Any]] = {}
        for item in sections:
            children.setdefault(item.parent_id, []).append(item)

        visited: set[int] = set()

        async def walk(parent_id: int | None, depth: int) -> None:
            for item in children.get(parent_id, []):
                if item.id in visited:
                    raise errors.ConflictError(msg='章节父子关系存在循环')
                visited.add(item.id)
                if item.depth != depth:
                    await bank_section_dao.update(
                        db,
                        item.id,
                        {'depth': depth, 'updated_by': updated_by},
                    )
                await walk(item.id, depth + 1)

        await walk(None, 0)
        if len(visited) != len(nodes):
            raise errors.ConflictError(msg='章节树存在孤立节点或循环')

    @staticmethod
    async def get(*, db: AsyncSession, bank_id: int, revision_id: int) -> GetBankCompositionDetail:
        """获取题库版本轻量章节大纲，题项通过游标接口分页读取"""
        async def factory() -> GetBankCompositionDetail:
            revision = await CompositionService._get_bank_revision(
                db=db,
                bank_id=bank_id,
                revision_id=revision_id,
                draft_only=False,
            )
            sections = list(await bank_section_dao.get_all(db, revision_id))
            return GetBankCompositionDetail(
                bank_id=bank_id,
                bank_revision_id=revision_id,
                revision_status=revision.status,
                sections=CompositionService._build_section_tree(sections),
                items=[],
            )
        return await composition_cache.get_or_set(
            bank_id,
            revision_id,
            factory=factory,
            should_cache=lambda data: data.revision_status in {'published', 'retired'},
        )

    @staticmethod
    async def invalidate_cache(*, bank_id: int, revision_id: int) -> None:
        await composition_cache.invalidate(bank_id, revision_id)

    @staticmethod
    async def get_items_select(
        *,
        db: AsyncSession,
        bank_id: int,
        revision_id: int,
        section_id: int | None,
    ) -> Any:
        """校验题库版本并构建题项游标分页查询"""
        await CompositionService._get_bank_revision(
            db=db,
            bank_id=bank_id,
            revision_id=revision_id,
            draft_only=False,
        )
        if section_id is not None and await bank_section_dao.get(db, section_id, revision_id=revision_id) is None:
            raise errors.NotFoundError(msg='题库章节不存在')
        return bank_item_dao.get_list_select(revision_id=revision_id, section_id=section_id)

    @staticmethod
    async def create_section(
        *,
        db: AsyncSession,
        bank_id: int,
        revision_id: int,
        obj: CreateBankSectionParam,
        created_by: int,
    ) -> GetBankSectionDetail:
        """创建题库版本章节"""
        await CompositionService._get_bank_revision(
            db=db,
            bank_id=bank_id,
            revision_id=revision_id,
            draft_only=True,
        )
        if await bank_section_dao.get_by_code(db, revision_id, obj.code):
            raise errors.ConflictError(msg='题库版本内章节编码已存在')
        depth = await CompositionService._validate_section_parent(
            db=db,
            revision_id=revision_id,
            parent_id=obj.parent_id,
        )
        section = await bank_section_dao.create(
            db,
            {
                **obj.model_dump(),
                'bank_revision_id': revision_id,
                'depth': depth,
                'created_by': created_by,
            },
        )
        return GetBankSectionDetail.model_validate(section)

    @staticmethod
    async def update_section(
        *,
        db: AsyncSession,
        bank_id: int,
        revision_id: int,
        section_id: int,
        obj: UpdateBankSectionParam,
        updated_by: int,
    ) -> GetBankSectionDetail:
        """更新题库版本章节"""
        await CompositionService._get_bank_revision(
            db=db,
            bank_id=bank_id,
            revision_id=revision_id,
            draft_only=True,
        )
        section = await bank_section_dao.get(db, section_id, revision_id=revision_id)
        if section is None:
            raise errors.NotFoundError(msg='题库章节不存在')
        data = obj.model_dump(exclude_unset=True)
        if 'code' in data and data['code'] != section.code:
            existing = await bank_section_dao.get_by_code(db, revision_id, data['code'])
            if existing is not None and existing.id != section_id:
                raise errors.ConflictError(msg='题库版本内章节编码已存在')
        if 'parent_id' in data:
            data['depth'] = await CompositionService._validate_section_parent(
                db=db,
                revision_id=revision_id,
                parent_id=data['parent_id'],
                current_id=section_id,
            )
        if data:
            data['updated_by'] = updated_by
            await bank_section_dao.update(db, section_id, data)
        if 'parent_id' in data:
            await CompositionService._recalculate_section_depths(
                db=db,
                revision_id=revision_id,
                updated_by=updated_by,
            )
        section = await bank_section_dao.get(db, section_id, revision_id=revision_id)
        return GetBankSectionDetail.model_validate(section)

    @staticmethod
    async def create_item(
        *,
        db: AsyncSession,
        bank_id: int,
        revision_id: int,
        obj: CreateBankItemParam,
        created_by: int,
    ) -> GetBankItemDetail:
        """创建题库版本题目编排"""
        await CompositionService._get_bank_revision(
            db=db,
            bank_id=bank_id,
            revision_id=revision_id,
            draft_only=True,
        )
        await CompositionService._validate_question(
            db=db,
            question_id=obj.question_id,
        )
        if (
            obj.section_id is not None
            and await bank_section_dao.get(db, obj.section_id, revision_id=revision_id) is None
        ):
            raise errors.NotFoundError(msg='题库章节不存在或不属于当前题库版本')
        if await bank_item_dao.get_by_item_key(db, revision_id, obj.item_key):
            raise errors.ConflictError(msg='题库版本内题目业务键已存在')
        if await bank_item_dao.get_by_question(db, revision_id, obj.question_id):
            raise errors.ConflictError(msg='同一题目不能重复编排到一个题库版本')
        item = await bank_item_dao.create(
            db,
            {
                **obj.model_dump(),
                'bank_revision_id': revision_id,
                'created_by': created_by,
            },
        )
        rows = await bank_item_dao.get_all(db, revision_id)
        row = next(data for data in rows if data['id'] == item.id)
        return GetBankItemDetail(**row)

    @staticmethod
    async def update_item(
        *,
        db: AsyncSession,
        bank_id: int,
        revision_id: int,
        item_id: int,
        obj: UpdateBankItemParam,
        updated_by: int,
    ) -> GetBankItemDetail:
        """更新题库版本题目编排"""
        await CompositionService._get_bank_revision(
            db=db,
            bank_id=bank_id,
            revision_id=revision_id,
            draft_only=True,
        )
        item = await bank_item_dao.get(db, item_id, revision_id=revision_id)
        if item is None:
            raise errors.NotFoundError(msg='题目编排不存在')
        data = obj.model_dump(exclude_unset=True)
        target_question_id = data.get('question_id', item.question_id)
        if 'question_id' in data:
            await CompositionService._validate_question(
                db=db,
                question_id=target_question_id,
            )
            existing = await bank_item_dao.get_by_question(db, revision_id, target_question_id)
            if existing is not None and existing.id != item_id:
                raise errors.ConflictError(msg='同一题目不能重复编排到一个题库版本')
        if 'item_key' in data and data['item_key'] != item.item_key:
            existing = await bank_item_dao.get_by_item_key(db, revision_id, data['item_key'])
            if existing is not None and existing.id != item_id:
                raise errors.ConflictError(msg='题库版本内题目业务键已存在')
        if (
            'section_id' in data
            and data['section_id'] is not None
            and await bank_section_dao.get(db, data['section_id'], revision_id=revision_id) is None
        ):
            raise errors.NotFoundError(msg='题库章节不存在或不属于当前题库版本')
        if data:
            data['updated_by'] = updated_by
            await bank_item_dao.update(db, item_id, data)
        rows = await bank_item_dao.get_all(db, revision_id)
        row = next(data for data in rows if data['id'] == item_id)
        return GetBankItemDetail(**row)

    @staticmethod
    async def delete_item(*, db: AsyncSession, bank_id: int, revision_id: int, item_id: int) -> int:
        """删除题库版本题目编排"""
        await CompositionService._get_bank_revision(
            db=db,
            bank_id=bank_id,
            revision_id=revision_id,
            draft_only=True,
        )
        if await bank_item_dao.get(db, item_id, revision_id=revision_id) is None:
            raise errors.NotFoundError(msg='题目编排不存在')
        return await bank_item_dao.delete(db, item_id)


composition_service: CompositionService = CompositionService()
