#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_dict_region import dict_region_dao
from backend.app.gongkao.model.dict_region import GkDictRegion
from backend.app.gongkao.schema.dict_region import (
    CreateDictRegionParam,
    DictRegionParam,
    UpdateDictRegionParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class DictRegionService:
    """地区字典服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkDictRegion:
        """
        获取地区详情

        :param db: 数据库会话
        :param pk: 地区 ID
        :return:
        """
        region = await dict_region_dao.get(db, pk)
        if not region:
            raise errors.NotFoundError(msg='地区不存在')
        return region

    @staticmethod
    async def get_by_code(*, db: AsyncSession, code: str) -> GkDictRegion:
        """
        通过代码获取地区

        :param db: 数据库会话
        :param code: 地区代码
        :return:
        """
        region = await dict_region_dao.get_by_code(db, code)
        if not region:
            raise errors.NotFoundError(msg='地区不存在')
        return region

    @staticmethod
    async def get_list(*, db: AsyncSession, params: DictRegionParam) -> dict[str, Any]:
        """
        获取地区列表（分页）

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        region_select = await dict_region_dao.get_select(
            name=params.name,
            level=params.level,
            parent_code=params.parent_code,
        )
        return await paging_data(db, region_select)

    @staticmethod
    async def get_children(*, db: AsyncSession, parent_code: str | None = None) -> Sequence[GkDictRegion]:
        """
        获取子地区列表

        :param db: 数据库会话
        :param parent_code: 父级代码
        :return:
        """
        return await dict_region_dao.get_children(db, parent_code)

    @staticmethod
    async def get_tree(*, db: AsyncSession) -> list[dict[str, Any]]:
        """
        获取地区树形结构

        :param db: 数据库会话
        :return:
        """
        regions = await dict_region_dao.get_all(db)
        
        # 转换为字典列表
        nodes = []
        for region in regions:
            nodes.append({
                'id': region.id,
                'code': region.code,
                'name': region.name,
                'level': region.level,
                'parent_code': region.parent_code,
                'short_name': region.short_name,
                'is_remote_area': region.is_remote_area,
                'sort_order': region.sort_order,
            })
        
        # 按 sort_order 排序
        nodes.sort(key=lambda x: x.get('sort_order', 0))
        
        # 构建树形结构（使用 code/parent_code）
        node_dict = {node['code']: node for node in nodes}
        tree: list[dict[str, Any]] = []
        
        for node in nodes:
            parent_code = node.get('parent_code')
            if parent_code is None:
                tree.append(node)
            else:
                parent_node = node_dict.get(parent_code)
                if parent_node is not None:
                    if 'children' not in parent_node:
                        parent_node['children'] = []
                    parent_node['children'].append(node)
                else:
                    tree.append(node)
        
        return tree

    @staticmethod
    async def get_provinces(*, db: AsyncSession) -> Sequence[GkDictRegion]:
        """
        获取所有省份

        :param db: 数据库会话
        :return:
        """
        return await dict_region_dao.get_by_level(db, 1)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateDictRegionParam) -> GkDictRegion:
        """
        创建地区

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        existing = await dict_region_dao.get_by_code(db, obj.code)
        if existing:
            raise errors.ConflictError(msg='地区代码已存在')
        return await dict_region_dao.create(db, obj)

    @staticmethod
    async def bulk_create(*, db: AsyncSession, objs: list[CreateDictRegionParam]) -> int:
        """
        批量创建地区

        :param db: 数据库会话
        :param objs: 创建参数列表
        :return:
        """
        return await dict_region_dao.bulk_create(db, objs)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateDictRegionParam) -> int:
        """
        更新地区

        :param db: 数据库会话
        :param pk: 地区 ID
        :param obj: 更新参数
        :return:
        """
        region = await dict_region_dao.get(db, pk)
        if not region:
            raise errors.NotFoundError(msg='地区不存在')
        return await dict_region_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pks: list[int]) -> int:
        """
        删除地区

        :param db: 数据库会话
        :param pks: 地区 ID 列表
        :return:
        """
        return await dict_region_dao.delete(db, pks)


dict_region_service: DictRegionService = DictRegionService()
