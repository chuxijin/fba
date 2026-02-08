#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_dict_major import dict_major_dao
from backend.app.gongkao.model.dict_major import GkDictMajor
from backend.app.gongkao.schema.dict_major import (
    CreateDictMajorParam,
    DictMajorParam,
    MajorMatchResult,
    UpdateDictMajorParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class DictMajorService:
    """专业目录服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkDictMajor:
        """
        获取专业详情

        :param db: 数据库会话
        :param pk: 专业 ID
        :return:
        """
        major = await dict_major_dao.get(db, pk)
        if not major:
            raise errors.NotFoundError(msg='专业不存在')
        return major

    @staticmethod
    async def get_by_code(*, db: AsyncSession, code: str) -> GkDictMajor:
        """
        通过代码获取专业

        :param db: 数据库会话
        :param code: 专业代码
        :return:
        """
        major = await dict_major_dao.get_by_code(db, code)
        if not major:
            raise errors.NotFoundError(msg='专业不存在')
        return major

    @staticmethod
    async def get_list(*, db: AsyncSession, params: DictMajorParam) -> dict[str, Any]:
        """
        获取专业列表（分页）

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        major_select = await dict_major_dao.get_select(
            name=params.name,
            level=params.level,
            parent_code=params.parent_code,
            edu_level=params.edu_level,
            is_active=params.is_active,
        )
        return await paging_data(db, major_select)

    @staticmethod
    async def get_children(*, db: AsyncSession, parent_code: str | None = None) -> Sequence[GkDictMajor]:
        """
        获取子专业列表

        :param db: 数据库会话
        :param parent_code: 父级代码
        :return:
        """
        return await dict_major_dao.get_children(db, parent_code)

    @staticmethod
    async def get_tree(*, db: AsyncSession, edu_level: str | None = None) -> list[dict[str, Any]]:
        """
        获取专业树形结构

        :param db: 数据库会话
        :param edu_level: 学历层次
        :return:
        """
        majors = await dict_major_dao.get_all(db, edu_level)
        
        # 转换为字典列表
        nodes = []
        for major in majors:
            nodes.append({
                'id': major.id,
                'code': major.code,
                'name': major.name,
                'level': major.level,
                'parent_code': major.parent_code,
                'edu_level': major.edu_level,
                'sort_order': major.sort_order,
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
    async def search(*, db: AsyncSession, keyword: str, edu_level: str | None = None) -> Sequence[GkDictMajor]:
        """
        搜索专业（名称或别名）

        :param db: 数据库会话
        :param keyword: 搜索关键词
        :param edu_level: 学历层次
        :return:
        """
        return await dict_major_dao.search_by_name_or_alias(db, keyword, edu_level)

    @staticmethod
    async def match_major(*, db: AsyncSession, major_name: str, edu_level: str = '本科') -> MajorMatchResult | None:
        """
        匹配专业（返回匹配结果和匹配类型）

        :param db: 数据库会话
        :param major_name: 专业名称
        :param edu_level: 学历层次
        :return:
        """
        # 1. 精确匹配
        major = await dict_major_dao.get_by_name(db, major_name, edu_level)
        if major:
            parent = await dict_major_dao.get_by_code(db, major.parent_code) if major.parent_code else None
            discipline = await dict_major_dao.get_by_code(db, parent.parent_code) if parent and parent.parent_code else None
            return MajorMatchResult(
                major_code=major.code,
                major_name=major.name,
                category_code=parent.code if parent else None,
                category_name=parent.name if parent else None,
                discipline_code=discipline.code if discipline else None,
                discipline_name=discipline.name if discipline else None,
                match_type='exact',
                match_score=100,
            )

        # 2. 别名匹配
        results = await dict_major_dao.search_by_name_or_alias(db, major_name, edu_level)
        for result in results:
            if result.aliases and major_name in result.aliases:
                parent = await dict_major_dao.get_by_code(db, result.parent_code) if result.parent_code else None
                discipline = await dict_major_dao.get_by_code(db, parent.parent_code) if parent and parent.parent_code else None
                return MajorMatchResult(
                    major_code=result.code,
                    major_name=result.name,
                    category_code=parent.code if parent else None,
                    category_name=parent.name if parent else None,
                    discipline_code=discipline.code if discipline else None,
                    discipline_name=discipline.name if discipline else None,
                    match_type='alias',
                    match_score=80,
                )

        return None

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateDictMajorParam) -> GkDictMajor:
        """
        创建专业

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        existing = await dict_major_dao.get_by_code(db, obj.code)
        if existing:
            raise errors.ConflictError(msg='专业代码已存在')
        return await dict_major_dao.create(db, obj)

    @staticmethod
    async def bulk_create(*, db: AsyncSession, objs: list[CreateDictMajorParam]) -> int:
        """
        批量创建专业

        :param db: 数据库会话
        :param objs: 创建参数列表
        :return:
        """
        return await dict_major_dao.bulk_create(db, objs)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateDictMajorParam) -> int:
        """
        更新专业

        :param db: 数据库会话
        :param pk: 专业 ID
        :param obj: 更新参数
        :return:
        """
        major = await dict_major_dao.get(db, pk)
        if not major:
            raise errors.NotFoundError(msg='专业不存在')
        return await dict_major_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pks: list[int]) -> int:
        """
        删除专业

        :param db: 数据库会话
        :param pks: 专业 ID 列表
        :return:
        """
        return await dict_major_dao.delete(db, pks)


dict_major_service: DictMajorService = DictMajorService()
