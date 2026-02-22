#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.doc import JiaAsset, JiaDoc, JiaFolder
from backend.app.jia.schema.doc import (
    CreateAssetParam,
    CreateDocParam,
    CreateFolderParam,
    UpdateAssetParam,
    UpdateDocParam,
    UpdateFolderParam,
)


class CRUDFolder(CRUDPlus[JiaFolder]):
    """文件夹数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> JiaFolder | None:
        """
        获取文件夹

        :param db: 数据库会话
        :param pk: 文件夹 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_list(self, *, user_id: int) -> Select:
        """
        获取用户所有文件夹（用于构建树）

        :param user_id: 用户 ID
        :return:
        """
        return await self.select_order('sort_order', 'asc', user_id=user_id)

    async def create(self, db: AsyncSession, obj: CreateFolderParam, *, user_id: int) -> JiaFolder:
        """
        创建文件夹

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 用户 ID
        :return:
        """
        instance = self.model(**obj.model_dump(), user_id=user_id)
        db.add(instance)
        await db.flush()
        return instance

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFolderParam) -> int:
        """
        更新文件夹

        :param db: 数据库会话
        :param pk: 文件夹 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除文件夹

        :param db: 数据库会话
        :param pk: 文件夹 ID
        :return:
        """
        return await self.delete_model(db, pk)


class CRUDDoc(CRUDPlus[JiaDoc]):
    """文档数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> JiaDoc | None:
        """
        获取文档

        :param db: 数据库会话
        :param pk: 文档 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_list(
        self,
        *,
        user_id: int,
        folder_id: int | None = None,
        is_trashed: bool = False,
        is_pinned: bool | None = None,
        title: str | None = None,
    ) -> Select:
        """
        获取文档列表查询表达式

        :param user_id: 用户 ID
        :param folder_id: 文件夹 ID
        :param is_trashed: 是否回收站
        :param is_pinned: 是否置顶
        :param title: 标题搜索
        :return:
        """
        filters: dict = {'user_id': user_id, 'is_trashed': is_trashed, 'folder_id': folder_id}
        if is_pinned is not None:
            filters['is_pinned'] = is_pinned
        if title is not None:
            filters['title__like'] = f'%{title}%'
        return await self.select_order('updated_time', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateDocParam, *, user_id: int) -> JiaDoc:
        """
        创建文档

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 用户 ID
        :return:
        """
        instance = self.model(**obj.model_dump(), user_id=user_id)
        db.add(instance)
        await db.flush()
        return instance

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDocParam) -> int:
        """
        更新文档

        :param db: 数据库会话
        :param pk: 文档 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def update_raw(self, db: AsyncSession, pk: int, data: dict) -> int:
        """
        直接用 dict 更新文档（支持显式 NULL）

        :param db: 数据库会话
        :param pk: 文档 ID
        :param data: 更新数据字典
        :return:
        """
        return await self.update_model(db, pk, data)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除文档

        :param db: 数据库会话
        :param pk: 文档 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def update_folder(self, db: AsyncSession, doc_ids: list[int], folder_id: int | None, user_id: int) -> int:
        """
        移动文档到目标文件夹

        :param db: 数据库会话
        :param doc_ids: 文档 ID 列表
        :param folder_id: 目标文件夹 ID
        :param user_id: 用户 ID
        :return: 影响行数
        """
        stmt = (
            update(self.model)
            .where(self.model.id.in_(doc_ids), self.model.user_id == user_id)
            .values(folder_id=folder_id)
        )
        result = await db.execute(stmt)
        return result.rowcount


class CRUDAsset(CRUDPlus[JiaAsset]):
    """资源数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> JiaAsset | None:
        """
        获取资源

        :param db: 数据库会话
        :param pk: 资源 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_hash(self, db: AsyncSession, *, file_hash: str, user_id: int) -> JiaAsset | None:
        """
        根据文件哈希查找资源（去重）

        :param db: 数据库会话
        :param file_hash: 文件 SHA256
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, file_hash=file_hash, user_id=user_id)

    async def get_list(self, *, user_id: int, doc_id: int | None = None) -> Select:
        """
        获取资源列表查询表达式

        :param user_id: 用户 ID
        :param doc_id: 文档 ID
        :return:
        """
        filters: dict = {'user_id': user_id}
        if doc_id is not None:
            filters['doc_id'] = doc_id
        return await self.select_order('id', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateAssetParam, *, user_id: int) -> JiaAsset:
        """
        创建资源记录

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 用户 ID
        :return:
        """
        instance = self.model(**obj.model_dump(), user_id=user_id)
        db.add(instance)
        await db.flush()
        return instance

    async def update(self, db: AsyncSession, pk: int, obj: UpdateAssetParam) -> int:
        """
        更新资源

        :param db: 数据库会话
        :param pk: 资源 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除资源

        :param db: 数据库会话
        :param pk: 资源 ID
        :return:
        """
        return await self.delete_model(db, pk)


folder_dao: CRUDFolder = CRUDFolder(JiaFolder)
doc_dao: CRUDDoc = CRUDDoc(JiaDoc)
asset_dao: CRUDAsset = CRUDAsset(JiaAsset)
