#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.utils.password_security import get_hash_password, password_verify
from backend.app.jia.crud.crud_doc import asset_dao, doc_dao, folder_dao
from backend.app.jia.model.doc import JiaAsset, JiaDoc, JiaFolder
from backend.app.jia.schema.doc import (
    CreateAssetParam,
    CreateDocParam,
    CreateFolderParam,
    GetFolderTree,
    UpdateAssetParam,
    UpdateDocParam,
    UpdateFolderParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.core.conf import settings
from backend.utils.encrypt import AESCipher


class FolderService:
    """文件夹服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int, user_id: int) -> JiaFolder:
        """
        获取文件夹

        :param db: 数据库会话
        :param pk: 文件夹 ID
        :param user_id: 用户 ID
        :return:
        """
        folder = await folder_dao.get(db, pk)
        if not folder or folder.user_id != user_id:
            raise errors.NotFoundError(msg='文件夹不存在')
        return folder

    @staticmethod
    async def get_tree(*, db: AsyncSession, user_id: int) -> list[GetFolderTree]:
        """
        获取文件夹树形结构

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        select_stmt = await folder_dao.get_list(user_id=user_id)
        result = await db.execute(select_stmt)
        folders = result.scalars().all()

        # 构建树
        folder_map: dict[int, dict] = {}
        roots: list[dict] = []
        for f in folders:
            node = {
                'id': f.id,
                'name': f.name,
                'parent_id': f.parent_id,
                'icon': f.icon,
                'sort_order': f.sort_order,
                'children': [],
            }
            folder_map[f.id] = node

        for node in folder_map.values():
            pid = node['parent_id']
            if pid and pid in folder_map:
                folder_map[pid]['children'].append(node)
            else:
                roots.append(node)

        return [GetFolderTree.model_validate(r) for r in roots]

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateFolderParam, user_id: int) -> JiaFolder:
        """
        创建文件夹

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 用户 ID
        :return:
        """
        return await folder_dao.create(db, obj, user_id=user_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateFolderParam, user_id: int) -> int:
        """
        更新文件夹

        :param db: 数据库会话
        :param pk: 文件夹 ID
        :param obj: 更新参数
        :param user_id: 用户 ID
        :return:
        """
        folder = await folder_dao.get(db, pk)
        if not folder or folder.user_id != user_id:
            raise errors.NotFoundError(msg='文件夹不存在')
        return await folder_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int, user_id: int) -> int:
        """
        删除文件夹（级联删除子文件夹和文档）

        :param db: 数据库会话
        :param pk: 文件夹 ID
        :param user_id: 用户 ID
        :return:
        """
        folder = await folder_dao.get(db, pk)
        if not folder or folder.user_id != user_id:
            raise errors.NotFoundError(msg='文件夹不存在')
        return await folder_dao.delete(db, pk)


class DocService:
    """文档服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int, user_id: int) -> JiaDoc:
        """
        获取文档详情

        :param db: 数据库会话
        :param pk: 文档 ID
        :param user_id: 用户 ID
        :return:
        """
        doc = await doc_dao.get(db, pk)
        if not doc or doc.user_id != user_id:
            raise errors.NotFoundError(msg='文档不存在')

        # 存储加密：服务端解密还原 content（仅返回值，不修改数据库）
        if doc.storage_encrypted and doc.content_encrypted:
            cipher = AESCipher(settings.DOC_ENCRYPT_SECRET_KEY)
            plaintext = cipher.decrypt(doc.content_encrypted)
            doc.content = json.loads(plaintext)
            doc.content_encrypted = None  # 不暴露密文

        # 访问加密：隐藏 content（需 verify_access 验证后才返回）
        if doc.access_encrypted:
            doc.content = None

        return doc

    @staticmethod
    async def verify_access(*, db: AsyncSession, pk: int, user_id: int, password: str) -> JiaDoc:
        """
        验证文档访问密码并返回完整内容

        :param db: 数据库会话
        :param pk: 文档 ID
        :param user_id: 用户 ID
        :param password: 访问密码
        :return:
        """
        doc = await doc_dao.get(db, pk)
        if not doc or doc.user_id != user_id:
            raise errors.NotFoundError(msg='文档不存在')
        if not doc.access_encrypted or not doc.access_password_hash:
            raise errors.RequestError(msg='该文档未设置访问加密')
        if not password_verify(password, doc.access_password_hash):
            raise errors.ForbiddenError(msg='密码错误')

        # 存储加密：解密
        if doc.storage_encrypted and doc.content_encrypted:
            cipher = AESCipher(settings.DOC_ENCRYPT_SECRET_KEY)
            plaintext = cipher.decrypt(doc.content_encrypted)
            doc.content = json.loads(plaintext)
            doc.content_encrypted = None

        return doc

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        user_id: int,
        folder_id: int | None = None,
        is_trashed: bool = False,
        is_pinned: bool | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """
        获取文档列表（分页）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param folder_id: 文件夹 ID
        :param is_trashed: 是否回收站
        :param is_pinned: 是否置顶
        :param title: 标题搜索
        :return:
        """
        select_stmt = await doc_dao.get_list(
            user_id=user_id,
            folder_id=folder_id,
            is_trashed=is_trashed,
            is_pinned=is_pinned,
            title=title,
        )
        return await paging_data(db, select_stmt)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateDocParam, user_id: int) -> JiaDoc:
        """
        创建文档

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 用户 ID
        :return:
        """
        data = obj.model_dump(exclude={'access_password'})

        # 访问加密：hash 密码
        if obj.access_encrypted and obj.access_password:
            data['access_password_hash'] = get_hash_password(obj.access_password, salt=None)

        # 存储加密：加密 content
        if obj.storage_encrypted and data.get('content'):
            cipher = AESCipher(settings.DOC_ENCRYPT_SECRET_KEY)
            plaintext = json.dumps(data['content'], ensure_ascii=False)
            encrypted_bytes = cipher.encrypt(plaintext)
            data['content_encrypted'] = encrypted_bytes.hex()
            data['content'] = None

        instance = JiaDoc(**data, user_id=user_id)
        db.add(instance)
        await db.flush()
        return instance

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateDocParam, user_id: int) -> int:
        """
        更新文档

        :param db: 数据库会话
        :param pk: 文档 ID
        :param obj: 更新参数
        :param user_id: 用户 ID
        :return:
        """
        doc = await doc_dao.get(db, pk)
        if not doc or doc.user_id != user_id:
            raise errors.NotFoundError(msg='文档不存在')

        data = obj.model_dump(exclude_unset=True, exclude={'access_password'})

        # 访问加密处理
        if obj.access_password is not None:
            data['access_password_hash'] = get_hash_password(obj.access_password, salt=None)
        if 'access_encrypted' in data and not data['access_encrypted']:
            data['access_password_hash'] = None

        # 确定最终 storage_encrypted 状态
        will_storage_encrypt = data.get('storage_encrypted', doc.storage_encrypted)

        # 有新 content 传入
        if 'content' in data and data['content'] is not None:
            if will_storage_encrypt:
                cipher = AESCipher(settings.DOC_ENCRYPT_SECRET_KEY)
                plaintext = json.dumps(data['content'], ensure_ascii=False)
                encrypted_bytes = cipher.encrypt(plaintext)
                data['content_encrypted'] = encrypted_bytes.hex()
                data['content'] = None
            else:
                data['content_encrypted'] = None
        # 没有新 content 但 storage_encrypted 状态变化
        elif 'storage_encrypted' in data:
            if data['storage_encrypted'] and not doc.storage_encrypted:
                # 开启存储加密：加密当前明文
                if doc.content:
                    cipher = AESCipher(settings.DOC_ENCRYPT_SECRET_KEY)
                    plaintext = json.dumps(doc.content, ensure_ascii=False)
                    encrypted_bytes = cipher.encrypt(plaintext)
                    data['content_encrypted'] = encrypted_bytes.hex()
                    data['content'] = None
            elif not data['storage_encrypted'] and doc.storage_encrypted:
                # 关闭存储加密：解密当前密文
                if doc.content_encrypted:
                    cipher = AESCipher(settings.DOC_ENCRYPT_SECRET_KEY)
                    plaintext = cipher.decrypt(doc.content_encrypted)
                    data['content'] = json.loads(plaintext)
                    data['content_encrypted'] = None

        return await doc_dao.update_raw(db, pk, data)

    @staticmethod
    async def move_to_trash(*, db: AsyncSession, pk: int, user_id: int) -> int:
        """
        移入回收站

        :param db: 数据库会话
        :param pk: 文档 ID
        :param user_id: 用户 ID
        :return:
        """
        doc = await doc_dao.get(db, pk)
        if not doc or doc.user_id != user_id:
            raise errors.NotFoundError(msg='文档不存在')
        return await doc_dao.update(db, pk, UpdateDocParam(is_trashed=True))

    @staticmethod
    async def restore(*, db: AsyncSession, pk: int, user_id: int) -> int:
        """
        从回收站恢复

        :param db: 数据库会话
        :param pk: 文档 ID
        :param user_id: 用户 ID
        :return:
        """
        doc = await doc_dao.get(db, pk)
        if not doc or doc.user_id != user_id:
            raise errors.NotFoundError(msg='文档不存在')
        return await doc_dao.update(db, pk, UpdateDocParam(is_trashed=False))

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int, user_id: int) -> int:
        """
        永久删除文档

        :param db: 数据库会话
        :param pk: 文档 ID
        :param user_id: 用户 ID
        :return:
        """
        doc = await doc_dao.get(db, pk)
        if not doc or doc.user_id != user_id:
            raise errors.NotFoundError(msg='文档不存在')
        return await doc_dao.delete(db, pk)

    @staticmethod
    async def move(*, db: AsyncSession, doc_ids: list[int], target_folder_id: int | None, user_id: int) -> int:
        """
        移动文档到目标文件夹

        :param db: 数据库会话
        :param doc_ids: 文档 ID 列表
        :param target_folder_id: 目标文件夹 ID
        :param user_id: 用户 ID
        :return: 影响行数
        """
        if target_folder_id is not None:
            folder = await folder_dao.get(db, target_folder_id)
            if not folder or folder.user_id != user_id:
                raise errors.NotFoundError(msg='目标文件夹不存在')
        return await doc_dao.update_folder(db, doc_ids, target_folder_id, user_id)


class AssetService:
    """资源服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int, user_id: int) -> JiaAsset:
        """
        获取资源

        :param db: 数据库会话
        :param pk: 资源 ID
        :param user_id: 用户 ID
        :return:
        """
        asset = await asset_dao.get(db, pk)
        if not asset or asset.user_id != user_id:
            raise errors.NotFoundError(msg='资源不存在')
        return asset

    @staticmethod
    async def get_list(*, db: AsyncSession, user_id: int, doc_id: int | None = None) -> dict[str, Any]:
        """
        获取资源列表（分页）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param doc_id: 文档 ID
        :return:
        """
        select_stmt = await asset_dao.get_list(user_id=user_id, doc_id=doc_id)
        return await paging_data(db, select_stmt)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateAssetParam, user_id: int) -> JiaAsset:
        """
        创建资源记录（去重：同 hash 直接返回已有记录）

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 用户 ID
        :return:
        """
        if obj.file_hash:
            existing = await asset_dao.get_by_hash(db, file_hash=obj.file_hash, user_id=user_id)
            if existing:
                return existing
        return await asset_dao.create(db, obj, user_id=user_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateAssetParam, user_id: int) -> int:
        """
        更新资源

        :param db: 数据库会话
        :param pk: 资源 ID
        :param obj: 更新参数
        :param user_id: 用户 ID
        :return:
        """
        asset = await asset_dao.get(db, pk)
        if not asset or asset.user_id != user_id:
            raise errors.NotFoundError(msg='资源不存在')
        return await asset_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int, user_id: int) -> int:
        """
        删除资源

        :param db: 数据库会话
        :param pk: 资源 ID
        :param user_id: 用户 ID
        :return:
        """
        asset = await asset_dao.get(db, pk)
        if not asset or asset.user_id != user_id:
            raise errors.NotFoundError(msg='资源不存在')
        return await asset_dao.delete(db, pk)


folder_service: FolderService = FolderService()
doc_service: DocService = DocService()
asset_service: AssetService = AssetService()
