#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud import item_dao
from backend.app.jia.model import JiaItem
from backend.app.jia.schema import CreateItemParam, UpdateItemParam, GetItemList
from backend.app.jia.service.push_service import push_service
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.plugin.ai.service.chat_service import ai_chat_service
from backend.utils.file_ops import delete_files

# 向量化配置
PROVIDER_ID = 2
EMBED_MODEL = 'text-embedding-3-small'

# 状态优先级（数值越小越紧急，需要提醒）
STATUS_PRIORITY = {
    '已过期': 0,
    '即将过期': 1,
    '缺失': 2,
    '即将用完': 3,
    '待补货': 4,
    '充足': 5,
}


def is_status_worse(old_status: str, new_status: str) -> bool:
    """判断状态是否变差（向下变更）"""
    old_priority = STATUS_PRIORITY.get(old_status, 99)
    new_priority = STATUS_PRIORITY.get(new_status, 99)
    return new_priority < old_priority


class ItemService:
    """物品服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int, user_id: int) -> JiaItem:
        """
        获取物品

        :param db: 数据库会话
        :param pk: 物品 ID
        :param user_id: 用户 ID
        :return:
        """
        item = await item_dao.get_by_user(db, user_id, pk)
        if not item:
            raise errors.NotFoundError(msg='物品不存在')
        return item

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        user_id: int,
        ids: list[int] | None = None,
        name: str | None = None,
        category: str | None = None,
        status: str | None = None,
        location: str | None = None,
        semantic: bool = False,
        limit: int = 20,
    ) -> dict[str, Any] | list[JiaItem]:
        """
        获取物品列表（支持普通搜索和语义搜索）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ids: 物品 ID 列表
        :param name: 名称/搜索关键词
        :param category: 分类
        :param status: 状态
        :param location: 存放位置
        :param semantic: 是否启用语义搜索
        :param limit: 语义搜索返回数量
        :return:
        """
        if semantic and name:
            # 语义搜索模式
            try:
                vector = await ai_chat_service.embedding(
                    db=db,
                    provider_id=PROVIDER_ID,
                    model_id=EMBED_MODEL,
                    text=name,
                )
                return await item_dao.search_by_vector(db, vector, user_id, limit)
            except Exception as e:
                log.error(f'语义搜索向量化失败: {e}')
                # 降级为普通搜索

        # 普通分页搜索
        select_stmt = await item_dao.get_list(
            user_id=user_id,
            ids=ids,
            name=name,
            category=category,
            status=status,
            location=location,
        )
        return await paging_data(db, select_stmt, schema_cls=GetItemList)

    @staticmethod
    async def get_categories(*, db: AsyncSession, user_id: int) -> list[str]:
        """
        获取用户的所有分类

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await item_dao.get_categories(db, user_id)

    @staticmethod
    async def get_status_stats(*, db: AsyncSession, user_id: int) -> dict[str, int]:
        """
        获取物品状态统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        from sqlalchemy import select, func

        stmt = (
            select(JiaItem.status, func.count(JiaItem.id))
            .where(JiaItem.created_by == user_id)
            .group_by(JiaItem.status)
        )
        result = await db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateItemParam, user_id: int) -> JiaItem:
        """
        创建物品

        :param db: 数据库会话
        :param obj: 创建物品参数
        :param user_id: 用户 ID
        :return:
        """
        # 生成向量
        vector = None
        # 优化：采用带标签的结构化文本，增加 category 和 location
        text_parts = []
        if obj.category: text_parts.append(f"分类: {obj.category}")
        text_parts.append(f"名称: {obj.name or ''}")
        if obj.description: text_parts.append(f"描述: {obj.description}")
        if obj.location: text_parts.append(f"位置: {obj.location}")
        if obj.notes: text_parts.append(f"备注: {obj.notes}")
        
        text_to_embed = ", ".join(text_parts).strip()
        
        if text_to_embed:
            try:
                vector = await ai_chat_service.embedding(
                    db=db,
                    provider_id=PROVIDER_ID,
                    model_id=EMBED_MODEL,
                    text=text_to_embed,
                )
            except Exception as e:
                log.error(f'创建物品向量化失败: {e}')

        return await item_dao.create(db, obj, user_id, vector=vector)



    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateItemParam, user_id: int) -> int:
        """
        更新物品

        :param db: 数据库会话
        :param pk: 物品 ID
        :param obj: 更新物品参数
        :param user_id: 用户 ID
        :return:
        """
        item = await item_dao.get_by_user(db, user_id, pk)
        if not item:
            raise errors.NotFoundError(msg='物品不存在')

        # 检查是否需要更新向量
        vector = None
        update_data = obj.model_dump(exclude_unset=True)
        if any(k in update_data for k in ['name', 'description', 'notes', 'category', 'location']):
            # 组合新的文本用于向量化
            # 合并新旧值以确保上下文完整
            new_name = obj.name if obj.name is not None else item.name
            new_cat = obj.category if obj.category is not None else item.category
            new_desc = obj.description if obj.description is not None else item.description
            new_loc = obj.location if obj.location is not None else item.location
            new_notes = obj.notes if obj.notes is not None else item.notes

            text_parts = []
            if new_cat: text_parts.append(f"分类: {new_cat}")
            text_parts.append(f"名称: {new_name or ''}")
            if new_desc: text_parts.append(f"描述: {new_desc}")
            if new_loc: text_parts.append(f"位置: {new_loc}")
            if new_notes: text_parts.append(f"备注: {new_notes}")
            
            text_to_embed = ", ".join(text_parts).strip()
            
            if text_to_embed:
                try:
                    vector = await ai_chat_service.embedding(
                        db=db,
                        provider_id=PROVIDER_ID,
                        model_id=EMBED_MODEL,
                        text=text_to_embed,
                    )
                except Exception as e:
                    log.error(f'更新物品向量化失败: {e}')

        return await item_dao.update(db, pk, obj, user_id, vector=vector)

    @staticmethod
    async def delete(*, db: AsyncSession, pks: list[int], user_id: int) -> int:
        """
        删除物品（支持单个和批量），同时删除关联的图片文件

        :param db: 数据库会话
        :param pks: 物品 ID 列表
        :param user_id: 用户 ID
        :return: 删除数量
        """
        if not pks:
            return 0

        # 删除数据库记录并获取图片路径
        count, image_paths = await item_dao.delete_items(db, pks, user_id)

        # 删除关联的图片文件
        if count > 0 and image_paths:
            delete_files(image_paths)

        return count

    @staticmethod
    async def update_all_status(*, db: AsyncSession) -> dict[str, Any]:
        """
        更新所有物品的状态，状态变更时推送通知

        :param db: 数据库会话
        :return: 更新统计
        """
        # 查询所有物品
        stmt = select(JiaItem)
        result = await db.execute(stmt)
        items = result.scalars().all()

        updated_count = 0
        status_stats: dict[str, int] = defaultdict(int)
        user_changes: dict[int, list[dict]] = defaultdict(list)

        for item in items:
            old_status = item.status
            new_status = item.calculate_status()

            if old_status != new_status:
                item.status = new_status
                updated_count += 1
                log.info(f'物品 [{item.name}] 状态变更: {old_status} -> {new_status}')

                # 只对状态变差（向下变更）发送通知
                if is_status_worse(old_status, new_status):
                    user_changes[item.user_id].append({
                        'id': item.id,
                        'name': item.name,
                        'old_status': old_status,
                        'new_status': new_status,
                    })

            status_stats[new_status] += 1

        # 发送推送通知
        push_count = 0
        if push_service.is_available():
            for user_id, changes in user_changes.items():
                await ItemService._send_status_notification(db, user_id, changes)
                push_count += 1

        log.info(f'物品状态更新完成: 共 {len(items)} 件, 变更 {updated_count} 件, 推送 {push_count} 人')

        return {
            'total_count': len(items),
            'updated_count': updated_count,
            'push_count': push_count,
            'status_stats': dict(status_stats),
        }

    @staticmethod
    async def _send_status_notification(db: AsyncSession, user_id: int, changes: list[dict]) -> None:
        """发送状态变更通知"""
        try:
            if len(changes) == 1:
                change = changes[0]
                title = '物品状态提醒'
                body = f'「{change["name"]}」状态变为: {change["new_status"]}'
            else:
                title = f'{len(changes)} 件物品状态变更'
                sorted_changes = sorted(
                    changes,
                    key=lambda x: STATUS_PRIORITY.get(x['new_status'], 99)
                )
                items_preview = ', '.join([c['name'] for c in sorted_changes[:3]])
                if len(changes) > 3:
                    items_preview += f' 等{len(changes)}件'
                body = items_preview

            # 传递变更的物品 ID 列表
            item_ids = ','.join([str(c['id']) for c in changes])

            await push_service.send_to_user(
                db=db,
                user_id=user_id,
                title=title,
                body=body,
                data={
                    'type': 'status_change',
                    'item_ids': item_ids,
                },
            )
        except Exception as e:
            log.error(f'发送状态变更通知失败 (user_id={user_id}): {e}')


item_service = ItemService()
