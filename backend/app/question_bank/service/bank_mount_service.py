#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import defaultdict, deque
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_bank_mount import bank_mount_dao
from backend.app.question_bank.model.bank import QuestionBank
from backend.app.question_bank.schema.bank_mount import (
    CreateBankMountParam,
    DeleteBankMountParam,
    GetBankMountDetail,
    UpdateBankMountParam,
)
from backend.common.exception import errors

COLLECTION_BANK_TYPE = 3


class BankMountService:
    """刷题内容挂载服务类"""

    @staticmethod
    async def _get_bank_or_404(db: AsyncSession, bank_id: int, label: str) -> QuestionBank:
        """
        获取刷题内容

        :param db: 数据库会话
        :param bank_id: 内容 ID
        :param label: 错误提示标签
        :return:
        """
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg=f'{label}不存在')
        return bank

    @staticmethod
    async def _build_active_children_map(db: AsyncSession) -> dict[int, set[int]]:
        """构造启用挂载和兼容父级的子节点映射"""
        all_banks = await bank_dao.get_all_mappings(db, status=1)
        bank_ids = [int(item['id']) for item in all_banks]
        mount_rows = await bank_mount_dao.get_relation_mappings(db, bank_ids=bank_ids, status=1)

        children_map: dict[int, set[int]] = defaultdict(set)
        for row in mount_rows:
            children_map[int(row['collection_id'])].add(int(row['item_id']))

        for bank in all_banks:
            parent_id = bank.get('parent_id')
            if parent_id:
                children_map[int(parent_id)].add(int(bank['id']))

        return children_map

    @staticmethod
    async def _validate_mount(
        *,
        db: AsyncSession,
        collection_id: int,
        item_id: int,
        current_mount_id: int | None = None,
    ) -> None:
        """
        校验挂载关系

        :param db: 数据库会话
        :param collection_id: 合集 ID
        :param item_id: 内容 ID
        :param current_mount_id: 当前挂载 ID
        :return:
        """
        if collection_id == item_id:
            raise errors.ForbiddenError(msg='禁止将内容挂载到自身')

        collection = await BankMountService._get_bank_or_404(db, collection_id, '合集')
        if collection.bank_type != COLLECTION_BANK_TYPE:
            raise errors.ForbiddenError(msg='只能挂载到合集下')

        await BankMountService._get_bank_or_404(db, item_id, '被挂载内容')

        existed = await bank_mount_dao.get_by_collection_item(
            db,
            collection_id=collection_id,
            item_id=item_id,
        )
        if existed and (current_mount_id is None or existed.id != current_mount_id):
            raise errors.ConflictError(msg='当前合集已挂载该内容')

        children_map = await BankMountService._build_active_children_map(db)
        if current_mount_id is not None:
            current_mount = await bank_mount_dao.get(db, current_mount_id)
            if current_mount:
                children_map.get(current_mount.collection_id, set()).discard(current_mount.item_id)

        pending_ids: deque[int] = deque([item_id])
        visited_ids: set[int] = set()
        while pending_ids:
            current_id = pending_ids.popleft()
            if current_id in visited_ids:
                continue
            if current_id == collection_id:
                raise errors.ForbiddenError(msg='挂载关系存在循环')
            visited_ids.add(current_id)
            pending_ids.extend(children_map.get(current_id, set()))

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        collection_id: int | None = None,
        item_id: int | None = None,
        status: int | None = None,
    ) -> list[GetBankMountDetail]:
        """
        获取挂载列表

        :param db: 数据库会话
        :param collection_id: 合集 ID
        :param item_id: 内容 ID
        :param status: 状态
        :return:
        """
        rows = await bank_mount_dao.get_detail_mappings(
            db,
            collection_id=collection_id,
            item_id=item_id,
            status=status,
        )
        return [GetBankMountDetail(**row) for row in rows]

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateBankMountParam, created_by: int) -> None:
        """
        创建挂载

        :param db: 数据库会话
        :param obj: 创建挂载参数
        :param created_by: 创建者 ID
        :return:
        """
        await BankMountService._validate_mount(
            db=db,
            collection_id=obj.collection_id,
            item_id=obj.item_id,
        )
        await bank_mount_dao.create(db, obj, created_by=created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateBankMountParam, updated_by: int) -> int:
        """
        更新挂载

        :param db: 数据库会话
        :param pk: 挂载 ID
        :param obj: 更新挂载参数
        :param updated_by: 修改者 ID
        :return:
        """
        mount = await bank_mount_dao.get(db, pk)
        if not mount:
            raise errors.NotFoundError(msg='挂载不存在')

        collection_id = obj.collection_id if obj.collection_id is not None else mount.collection_id
        item_id = obj.item_id if obj.item_id is not None else mount.item_id
        await BankMountService._validate_mount(
            db=db,
            collection_id=collection_id,
            item_id=item_id,
            current_mount_id=pk,
        )

        return await bank_mount_dao.update(db, pk, obj, updated_by=updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteBankMountParam) -> int:
        """
        删除挂载

        :param db: 数据库会话
        :param obj: 删除挂载参数
        :return:
        """
        return await bank_mount_dao.delete(db, obj.ids)

    @staticmethod
    async def get_active_mount_mappings(db: AsyncSession, *, bank_ids: list[int]) -> list[dict[str, Any]]:
        """
        获取启用挂载映射

        :param db: 数据库会话
        :param bank_ids: 内容 ID 列表
        :return:
        """
        return await bank_mount_dao.get_relation_mappings(db, bank_ids=bank_ids, status=1)

    @staticmethod
    async def _expand_mount_tree_banks(
        *,
        db: AsyncSession,
        initial_bank_ids: set[int],
        status: int | None,
    ) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
        """
        递归扩展挂载树涉及的内容

        :param db: 数据库会话
        :param initial_bank_ids: 初始内容 ID
        :param status: 内容状态
        :return:
        """
        if not initial_bank_ids:
            return {}, []

        bank_rows = await bank_dao.get_mappings_by_ids(db, list(initial_bank_ids))
        bank_by_id = {
            int(row['id']): row
            for row in bank_rows
            if status is None or int(row.get('status') or 0) == status
        }
        known_ids = set(bank_by_id)
        pending_ids = set(bank_by_id)
        mount_by_id: dict[int, dict[str, Any]] = {}

        while pending_ids:
            mount_rows = await BankMountService.get_active_mount_mappings(db, bank_ids=list(pending_ids))
            pending_ids = set()
            missing_item_ids: set[int] = set()
            for row in mount_rows:
                mount_id = int(row['id'])
                if mount_id in mount_by_id:
                    continue
                mount_by_id[mount_id] = row
                collection_id = int(row['collection_id'])
                if collection_id not in known_ids:
                    continue
                item_id = int(row['item_id'])
                if item_id not in known_ids:
                    missing_item_ids.add(item_id)

            if not missing_item_ids:
                continue

            extra_rows = await bank_dao.get_mappings_by_ids(db, list(missing_item_ids))
            for row in extra_rows:
                if status is not None and int(row.get('status') or 0) != status:
                    continue
                bank_id = int(row['id'])
                bank_by_id[bank_id] = row
                known_ids.add(bank_id)
                pending_ids.add(bank_id)

        return bank_by_id, list(mount_by_id.values())

    @staticmethod
    def _build_tree_from_mounts(
        *,
        bank_by_id: dict[int, dict[str, Any]],
        mount_rows: list[dict[str, Any]],
        root_ids: list[int],
    ) -> list[dict[str, Any]]:
        """
        按挂载关系构造内容树

        :param bank_by_id: 内容映射
        :param mount_rows: 挂载映射
        :param root_ids: 根内容 ID
        :return:
        """
        children_map: dict[int, list[dict[str, Any]]] = {}
        for row in mount_rows:
            collection_id = int(row['collection_id'])
            if collection_id not in bank_by_id:
                continue
            item_id = int(row['item_id'])
            if item_id not in bank_by_id:
                continue
            children_map.setdefault(collection_id, []).append(row)

        for rows in children_map.values():
            rows.sort(key=lambda item: (int(item.get('sort_order') or 0), int(item.get('id') or 0)))

        def build_node(bank_id: int, path_ids: set[int]) -> dict[str, Any] | None:
            """构造内容节点"""
            bank = bank_by_id.get(bank_id)
            if not bank:
                return None

            node = dict(bank)
            node['children'] = []
            if bank_id in path_ids:
                return node

            next_path_ids = {*path_ids, bank_id}
            for mount in children_map.get(bank_id, []):
                child_node = build_node(int(mount['item_id']), next_path_ids)
                if child_node:
                    mount_id = int(mount.get('id') or 0)
                    if mount_id > 0:
                        child_node['mount_id'] = mount_id
                    node['children'].append(child_node)

            if node.get('bank_type') == COLLECTION_BANK_TYPE:
                node['q_count_cache'] = len(node['children'])

            return node

        result: list[dict[str, Any]] = []
        for root_id in root_ids:
            root_node = build_node(root_id, set())
            if root_node:
                result.append(root_node)

        return result

    @staticmethod
    def _merge_parent_relation_rows(
        *,
        bank_by_id: dict[int, dict[str, Any]],
        mount_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        合并显式挂载和兼容父级关系

        :param bank_by_id: 内容映射
        :param mount_rows: 显式挂载映射
        :return:
        """
        relation_rows = list(mount_rows)
        relation_pairs = {
            (int(row['collection_id']), int(row['item_id']))
            for row in mount_rows
        }

        for bank_id, bank in bank_by_id.items():
            parent_id = bank.get('parent_id')
            if not parent_id:
                continue

            parent_id = int(parent_id)
            if parent_id not in bank_by_id:
                continue

            pair = (parent_id, bank_id)
            if pair in relation_pairs:
                continue

            relation_pairs.add(pair)
            relation_rows.append({
                'id': 0,
                'collection_id': parent_id,
                'item_id': bank_id,
                'sort_order': int(bank.get('sort_order') or 0),
                'status': 1,
            })

        return relation_rows

    @staticmethod
    async def get_mount_tree(
        *,
        db: AsyncSession,
        bank_select: list[dict[str, Any]],
        status: int | None,
        parent_id: int | None,
    ) -> list[dict[str, Any]] | None:
        """
        获取挂载内容树

        :param db: 数据库会话
        :param bank_select: 初始内容列表
        :param status: 内容状态
        :param parent_id: 父合集 ID
        :return:
        """
        initial_bank_ids = {int(item['id']) for item in bank_select}
        if parent_id is not None:
            initial_bank_ids.add(parent_id)
        if not initial_bank_ids:
            return None

        bank_by_id, mount_rows = await BankMountService._expand_mount_tree_banks(
            db=db,
            initial_bank_ids=initial_bank_ids,
            status=status,
        )
        relation_rows = BankMountService._merge_parent_relation_rows(
            bank_by_id=bank_by_id,
            mount_rows=mount_rows,
        )
        if not relation_rows:
            return None

        if parent_id is not None:
            root_ids = [
                int(row['item_id'])
                for row in sorted(
                    relation_rows,
                    key=lambda item: (int(item.get('sort_order') or 0), int(item.get('id') or 0)),
                )
                if int(row['collection_id']) == parent_id
            ]
            return BankMountService._build_tree_from_mounts(
                bank_by_id=bank_by_id,
                mount_rows=relation_rows,
                root_ids=root_ids,
            )

        mounted_item_ids = {
            int(row['item_id'])
            for row in relation_rows
            if int(row['collection_id']) in bank_by_id
        }
        root_ids = [
            int(item['id'])
            for item in bank_select
            if int(item['id']) in bank_by_id and int(item['id']) not in mounted_item_ids
        ]
        root_ids.sort(key=lambda item_id: int(bank_by_id[item_id].get('sort_order') or 0))
        return BankMountService._build_tree_from_mounts(
            bank_by_id=bank_by_id,
            mount_rows=relation_rows,
            root_ids=root_ids,
        )

    @staticmethod
    async def get_active_descendant_item_ids(
        db: AsyncSession,
        *,
        collection_id: int,
        include_collections: bool = False,
    ) -> list[int]:
        """
        获取合集启用后代内容 ID

        :param db: 数据库会话
        :param collection_id: 合集 ID
        :param include_collections: 是否包含后代合集
        :return:
        """
        descendant_map = await BankMountService.get_active_descendant_item_ids_map(
            db,
            collection_ids=[collection_id],
            include_collections=include_collections,
        )
        return descendant_map.get(collection_id, [])

    @staticmethod
    def _resolve_descendant_item_ids(
        *,
        children_map: dict[int, set[int]],
        bank_type_map: dict[int, int],
        collection_id: int,
        include_collections: bool,
    ) -> list[int]:
        """
        解析单个合集的启用后代内容 ID

        :param children_map: 子节点映射
        :param bank_type_map: 内容类型映射
        :param collection_id: 合集 ID
        :param include_collections: 是否包含后代合集
        :return:
        """
        result: list[int] = []
        visited_ids: set[int] = set()
        pending_ids: deque[int] = deque(children_map.get(collection_id, set()))
        while pending_ids:
            item_id = pending_ids.popleft()
            if item_id in visited_ids:
                continue
            visited_ids.add(item_id)

            bank_type = bank_type_map.get(item_id)
            if bank_type is None:
                continue
            if include_collections or bank_type != COLLECTION_BANK_TYPE:
                result.append(item_id)
            if bank_type == COLLECTION_BANK_TYPE:
                pending_ids.extend(children_map.get(item_id, set()))

        return result

    @staticmethod
    async def get_active_descendant_item_ids_map(
        db: AsyncSession,
        *,
        collection_ids: list[int],
        include_collections: bool = False,
    ) -> dict[int, list[int]]:
        """
        批量获取合集启用后代内容 ID

        :param db: 数据库会话
        :param collection_ids: 合集 ID 列表
        :param include_collections: 是否包含后代合集
        :return:
        """
        normalized_collection_ids = list(dict.fromkeys(collection_id for collection_id in collection_ids if collection_id > 0))
        if not normalized_collection_ids:
            return {}

        all_banks = await bank_dao.get_all_mappings(db, status=1)
        bank_type_map = {int(item['id']): int(item.get('bank_type') or 1) for item in all_banks}
        children_map: dict[int, set[int]] = defaultdict(set)

        mount_rows = await bank_mount_dao.get_relation_mappings(
            db,
            bank_ids=list(bank_type_map),
            status=1,
        )
        for row in mount_rows:
            collection_id = int(row['collection_id'])
            item_id = int(row['item_id'])
            if collection_id in bank_type_map and item_id in bank_type_map:
                children_map[collection_id].add(item_id)

        for bank in all_banks:
            parent_id = bank.get('parent_id')
            bank_id = int(bank['id'])
            if parent_id and int(parent_id) in bank_type_map:
                children_map[int(parent_id)].add(bank_id)

        return {
            collection_id: BankMountService._resolve_descendant_item_ids(
                children_map=children_map,
                bank_type_map=bank_type_map,
                collection_id=collection_id,
                include_collections=include_collections,
            )
            for collection_id in normalized_collection_ids
        }


bank_mount_service: BankMountService = BankMountService()
