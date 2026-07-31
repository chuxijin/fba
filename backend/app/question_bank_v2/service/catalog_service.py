from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.category import Category
from backend.app.question_bank_v2.cache.catalog_cache import (
    catalog_from_cache,
    catalog_to_cache,
    public_catalog_cache,
)
from backend.app.question_bank_v2.crud.crud_bank import bank_dao, bank_revision_dao
from backend.app.question_bank_v2.crud.crud_catalog import collection_bank_dao, collection_dao
from backend.app.question_bank_v2.schema.bank import GetBankListItem
from backend.app.question_bank_v2.schema.catalog import (
    CreateCollectionBankMountParam,
    CreateCollectionParam,
    GetCollectionBankMountDetail,
    GetCollectionCatalogItem,
    GetCollectionDetail,
    UpdateCollectionBankMountParam,
    UpdateCollectionParam,
)
from backend.common.exception import errors


class CatalogService:
    """题库合集与挂载服务类"""

    @staticmethod
    async def _validate_parent(
        *,
        db: AsyncSession,
        parent_id: int | None,
        current_id: int | None = None,
    ) -> None:
        """校验合集父子关系不存在循环"""
        if parent_id is None:
            return
        if current_id is not None and parent_id == current_id:
            raise errors.ConflictError(msg='合集不能以自身作为父级')
        visited: set[int] = set()
        node_id: int | None = parent_id
        while node_id is not None:
            if node_id in visited:
                raise errors.ConflictError(msg='合集父子关系存在循环')
            visited.add(node_id)
            node = await collection_dao.get(db, node_id)
            if node is None:
                raise errors.NotFoundError(msg='父合集不存在')
            if current_id is not None and node.id == current_id:
                raise errors.ConflictError(msg='不能将合集移动到自己的子孙节点下')
            node_id = node.parent_id

    @staticmethod
    async def _validate_mount_mode(
        *,
        db: AsyncSession,
        bank_id: int,
        follow_latest: bool,
        bank_revision_id: int | None,
    ) -> None:
        """校验题库挂载的版本选择模式"""
        if await bank_dao.get(db, bank_id) is None:
            raise errors.NotFoundError(msg='题库不存在')
        if follow_latest and bank_revision_id is not None:
            raise errors.RequestError(msg='跟随最新版时不能指定固定版本')
        if not follow_latest and bank_revision_id is None:
            raise errors.RequestError(msg='固定版本模式必须指定题库版本')
        if bank_revision_id is not None:
            revision = await bank_revision_dao.get(db, bank_revision_id, bank_id=bank_id)
            if revision is None:
                raise errors.NotFoundError(msg='固定题库版本不存在或不属于该题库')
            if revision.status not in {'published', 'retired'}:
                raise errors.ConflictError(msg='固定挂载只能选择已发布版本')

    @staticmethod
    async def get_all(*, db: AsyncSession) -> list[GetCollectionDetail]:
        """获取全部题库合集"""
        return [GetCollectionDetail.model_validate(item) for item in await collection_dao.get_all(db)]

    @staticmethod
    def get_select() -> Select:
        """获取合集 Select 查询句"""
        return collection_dao.get_select()

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GetCollectionDetail:
        """获取题库合集详情"""
        collection = await collection_dao.get(db, pk)
        if collection is None:
            raise errors.NotFoundError(msg='题库合集不存在')
        return GetCollectionDetail.model_validate(collection)

    @staticmethod
    async def create(
        *,
        db: AsyncSession,
        obj: CreateCollectionParam,
        created_by: int,
    ) -> GetCollectionDetail:
        """创建题库合集"""
        if await collection_dao.get_by_code(db, obj.code):
            raise errors.ConflictError(msg='合集编码已存在')
        await CatalogService._validate_parent(db=db, parent_id=obj.parent_id)
        data = obj.model_dump()
        data['owner_id'] = created_by if obj.visibility == 'private' else None
        data['created_by'] = created_by
        collection = await collection_dao.create(db, data)
        await CatalogService.invalidate_public_catalog_cache()
        return GetCollectionDetail.model_validate(collection)

    @staticmethod
    async def update(
        *,
        db: AsyncSession,
        pk: int,
        obj: UpdateCollectionParam,
        updated_by: int,
    ) -> GetCollectionDetail:
        """更新题库合集"""
        collection = await collection_dao.get(db, pk, for_update=True)
        if collection is None:
            raise errors.NotFoundError(msg='题库合集不存在')
        data = obj.model_dump(exclude_unset=True)
        if 'code' in data and data['code'] != collection.code:
            existing = await collection_dao.get_by_code(db, data['code'])
            if existing is not None and existing.id != pk:
                raise errors.ConflictError(msg='合集编码已存在')
        if 'parent_id' in data:
            await CatalogService._validate_parent(db=db, parent_id=data['parent_id'], current_id=pk)
        if data.get('visibility') == 'private' and collection.owner_id is None:
            data['owner_id'] = updated_by
        elif data.get('visibility') in {'public', 'internal'}:
            data['owner_id'] = None
        if data:
            data['updated_by'] = updated_by
            await collection_dao.update(db, pk, data)
        collection = await collection_dao.get(db, pk)
        await CatalogService.invalidate_public_catalog_cache()
        return GetCollectionDetail.model_validate(collection)

    @staticmethod
    async def _resolve_category_ids(
        db: AsyncSession,
        cat_id: int,
    ) -> set[int]:
        """递归查询 cat_id 及其所有子分类的 ID"""
        ids = {cat_id}
        rows = (
            await db.execute(
                select(Category.id, Category.parent_id).where(Category.deleted == 0)
            )
        ).all()
        parent_map: dict[int, list[int]] = {}
        for row in rows:
            parent_map.setdefault(row.parent_id, []).append(row.id)
        stack = [cat_id]
        while stack:
            pid = stack.pop()
            for child_id in parent_map.get(pid, []):
                if child_id not in ids:
                    ids.add(child_id)
                    stack.append(child_id)
        return ids

    @staticmethod
    async def _filter_mounts(
        db: AsyncSession,
        mount_rows: Sequence[dict[str, Any]],
        cat_id: int | None,
    ) -> dict[int, list[GetBankListItem]]:
        category_ids: set[int] | None = None
        if cat_id is not None:
            category_ids = await CatalogService._resolve_category_ids(db, cat_id)
        banks_by_collection: dict[int, list[GetBankListItem]] = {}
        for row in mount_rows:
            data = dict(row)
            collection_id = int(data.pop('collection_id'))
            data.pop('mount_sort_order', None)
            display_name = data.pop('display_name', None)
            if display_name:
                data['name'] = display_name
            pcid = data.get('primary_category_id')
            if category_ids is not None and pcid is not None and pcid not in category_ids:
                continue
            banks_by_collection.setdefault(collection_id, []).append(GetBankListItem(**data))
        return banks_by_collection

    @staticmethod
    def _prune_collections(
        collection_rows: list[dict[str, Any]],
        keep_set: set[int],
    ) -> list[dict[str, Any]]:
        parents: dict[int, int | None] = {int(r['id']): r.get('parent_id') for r in collection_rows}
        keep = set(keep_set)
        for cid in list(keep):
            pid = parents.get(cid)
            while pid is not None and pid not in keep:
                keep.add(pid)
                pid = parents.get(pid)
        return [row for row in collection_rows if int(row['id']) in keep]

    @staticmethod
    def _build_tree(
        collection_rows: list[dict[str, Any]],
        banks_by_collection: dict[int, list[GetBankListItem]],
    ) -> list[GetCollectionCatalogItem]:
        nodes: dict[int, GetCollectionCatalogItem] = {}
        for row in collection_rows:
            cid = int(row['id'])
            data = dict(row)
            nodes[cid] = GetCollectionCatalogItem(
                **data,
                banks=banks_by_collection.get(cid, []),
            )
        roots: list[GetCollectionCatalogItem] = []
        for node in nodes.values():
            if node.parent_id is not None and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                roots.append(node)
        return roots

    @staticmethod
    async def get_public_catalog(
        *,
        db: AsyncSession,
        cat_id: int | None = None,
    ) -> list[GetCollectionCatalogItem]:
        """获取公开题库合集目录树"""
        async def factory() -> list[dict[str, Any]]:
            collection_rows, mount_rows = await collection_dao.get_public_catalog(db)
            banks_by_collection = await CatalogService._filter_mounts(db, mount_rows, cat_id)
            if cat_id is not None:
                collection_rows = CatalogService._prune_collections(
                    list(collection_rows), set(banks_by_collection.keys())
                )
            return catalog_to_cache(CatalogService._build_tree(collection_rows, banks_by_collection))

        cached = await public_catalog_cache.get_or_set(cat_id or 'all', factory=factory)
        return catalog_from_cache(cached or [])

    @staticmethod
    async def invalidate_public_catalog_cache() -> None:
        await public_catalog_cache.invalidate_prefix()

    @staticmethod
    async def get_mounts(*, db: AsyncSession, collection_id: int) -> list[GetCollectionBankMountDetail]:
        """获取合集全部题库挂载"""
        if await collection_dao.get(db, collection_id) is None:
            raise errors.NotFoundError(msg='题库合集不存在')
        stmt = collection_bank_dao.get_select_by_collection(collection_id)
        result = await db.execute(stmt)
        return [GetCollectionBankMountDetail.model_validate(row._mapping) for row in result.all()]

    @staticmethod
    async def get_mounts_select(*, db: AsyncSession, collection_id: int) -> Select:
        """校验合集并构建题库挂载游标分页查询"""
        if await collection_dao.get(db, collection_id) is None:
            raise errors.NotFoundError(msg='题库合集不存在')
        return collection_bank_dao.get_select_by_collection(collection_id)

    @staticmethod
    async def create_mount(
        *,
        db: AsyncSession,
        collection_id: int,
        obj: CreateCollectionBankMountParam,
        created_by: int,
    ) -> GetCollectionBankMountDetail:
        """创建合集题库挂载"""
        if await collection_dao.get(db, collection_id) is None:
            raise errors.NotFoundError(msg='题库合集不存在')
        if await collection_bank_dao.get_by_bank(db, collection_id=collection_id, bank_id=obj.bank_id):
            raise errors.ConflictError(msg='该题库已挂载到当前合集')
        await CatalogService._validate_mount_mode(
            db=db,
            bank_id=obj.bank_id,
            follow_latest=obj.follow_latest,
            bank_revision_id=obj.bank_revision_id,
        )
        data = obj.model_dump()
        data['collection_id'] = collection_id
        data['created_by'] = created_by
        mount = await collection_bank_dao.create(db, data)
        await CatalogService.invalidate_public_catalog_cache()
        return GetCollectionBankMountDetail.model_validate(mount)

    @staticmethod
    async def update_mount(
        *,
        db: AsyncSession,
        collection_id: int,
        mount_id: int,
        obj: UpdateCollectionBankMountParam,
        updated_by: int,
    ) -> GetCollectionBankMountDetail:
        """更新合集题库挂载"""
        mount = await collection_bank_dao.get(db, mount_id)
        if mount is None or mount.collection_id != collection_id:
            raise errors.NotFoundError(msg='题库挂载不存在')
        data: dict[str, Any] = obj.model_dump(exclude_unset=True)
        follow_latest = data.get('follow_latest', mount.follow_latest)
        bank_revision_id = data.get('bank_revision_id', mount.bank_revision_id)
        if follow_latest and 'follow_latest' in data and 'bank_revision_id' not in data:
            bank_revision_id = None
            data['bank_revision_id'] = None
        await CatalogService._validate_mount_mode(
            db=db,
            bank_id=mount.bank_id,
            follow_latest=follow_latest,
            bank_revision_id=bank_revision_id,
        )
        if data:
            data['updated_by'] = updated_by
            await collection_bank_dao.update(db, mount_id, data)
        mount = await collection_bank_dao.get(db, mount_id)
        await CatalogService.invalidate_public_catalog_cache()
        return GetCollectionBankMountDetail.model_validate(mount)

    @staticmethod
    async def delete_mount(*, db: AsyncSession, collection_id: int, mount_id: int) -> int:
        """删除合集题库挂载"""
        mount = await collection_bank_dao.get(db, mount_id)
        if mount is None or mount.collection_id != collection_id:
            raise errors.NotFoundError(msg='题库挂载不存在')
        deleted = await collection_bank_dao.delete(db, mount_id)
        await CatalogService.invalidate_public_catalog_cache()
        return deleted


catalog_service: CatalogService = CatalogService()
