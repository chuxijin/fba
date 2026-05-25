#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta
from typing import Sequence

from sqlalchemy import Select, and_, case, desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload, noload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.category import Category
from backend.app.coulddrive.model.resource import Resource, ResourceViewHistory
from backend.app.coulddrive.schema.resource import (
    CreateResourceParam,
    CreateResourceViewHistoryParam,
    GetResourceListParam,
    GetResourceViewHistoryListParam,
    UpdateResourceParam,
)
from backend.common.log import log
from backend.utils.embedding import batch_embed, embed
from backend.utils.timezone import timezone


class CRUDResource(CRUDPlus[Resource]):
    """资源数据库操作类"""

    @staticmethod
    def _apply_resource_type_filter(
        stmt: Select,
        resource_types: list[str] | None = None,
        resource_type: str | None = None,
    ) -> Select:
        """
        应用资源类型筛选条件

        :param stmt: 查询语句
        :param resource_types: 资源类型列表
        :param resource_type: 单个资源类型
        :return:
        """
        if resource_types:
            return stmt.where(Resource.resource_type.in_(resource_types))

        if resource_type:
            return stmt.where(Resource.resource_type == resource_type)

        return stmt

    async def get(self, db: AsyncSession, pk: int) -> Resource | None:
        """获取资源详情"""
        stmt = select(self.model).where(self.model.id == pk).options(joinedload(self.model.category))
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_pwd_id(self, db: AsyncSession, pwd_id: str) -> Resource | None:
        """
        通过密码ID获取资源

        :param db: 数据库会话
        :param pwd_id: 密码ID
        :return:
        """
        return await self.select_model_by_column(db, pwd_id=pwd_id)

    async def get_by_share_id(self, db: AsyncSession, share_id: str) -> Resource | None:
        """
        通过分享ID获取资源

        :param db: 数据库会话
        :param share_id: 分享ID
        :return:
        """
        return await self.select_model_by_column(db, share_id=share_id)

    async def get_list(self, params: GetResourceListParam, category_ids: list[int] | None = None) -> Select:
        """
        获取资源列表查询语句

        :param params: 查询参数
        :param category_ids: 分类 ID 列表（包含子分类）
        :return:
        """
        stmt = (
            select(self.model)
            .outerjoin(Category, self.model.category_id == Category.id)
            .options(contains_eager(self.model.category))
            .order_by(desc(self.model.created_time))
        )

        filters = []

        if params.category_id is not None:
            if category_ids:
                filters.append(self.model.category_id.in_(category_ids))
            else:
                filters.append(self.model.category_id == params.category_id)
        if params.resource_type is not None:
            filters.append(self.model.resource_type == params.resource_type)
        if params.url_type is not None:
            filters.append(self.model.url_type == params.url_type)
        if params.status is not None:
            filters.append(self.model.status == params.status)
        if params.expired_type is not None:
            filters.append(self.model.expired_type == params.expired_type)
        if params.user_id is not None:
            filters.append(self.model.user_id == params.user_id)
        if params.is_deleted is not None:
            filters.append(self.model.is_deleted == params.is_deleted)

        # 关键词搜索
        if params.keyword:
            keyword_filter = or_(
                self.model.title.ilike(f'%{params.keyword}%'),
                self.model.main_name.ilike(f'%{params.keyword}%')
            )
            filters.append(keyword_filter)

        if filters:
            stmt = stmt.where(and_(*filters))

        # 不加载关联对象和 deferred 字段
        stmt = stmt.options(noload(Resource.user), noload(Resource.view_history))

        return stmt

    async def get_hot_list(
        self,
        db: AsyncSession,
        category_ids: list[int] | None = None,
        resource_type: str | None = None,
        resource_types: list[str] | None = None,
        limit: int = 20
    ) -> Sequence[Resource]:
        """
        获取热门资源列表（按 hot 快照降序）

        :param db: 数据库会话
        :param category_ids: 分类 ID 列表（包含子分类）
        :param resource_type: 资源类型
        :param resource_types: 资源类型列表
        :param limit: 数量限制
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                and_(
                    self.model.is_deleted.is_(False),
                    self.model.status == 1
                )
            )
            .order_by(desc(self.model.hot))
            .limit(limit)
            .options(noload(Resource.user), noload(Resource.view_history))
        )

        if category_ids:
            stmt = stmt.where(self.model.category_id.in_(category_ids))

        stmt = self._apply_resource_type_filter(
            stmt,
            resource_types=resource_types,
            resource_type=resource_type,
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_active_resources(
        self,
        db: AsyncSession,
        category_ids: list[int] | None = None,
        resource_type: str | None = None,
        resource_types: list[str] | None = None,
    ) -> Sequence[Resource]:
        """
        获取所有活跃资源（未删除且状态正常）

        :param db: 数据库会话
        :param category_ids: 分类 ID 列表（包含子分类）
        :param resource_type: 资源类型
        :param resource_types: 资源类型列表
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                and_(
                    self.model.is_deleted.is_(False),
                    self.model.status == 1
                )
            )
            .options(noload(Resource.user), noload(Resource.view_history))
        )

        if category_ids:
            stmt = stmt.where(self.model.category_id.in_(category_ids))

        stmt = self._apply_resource_type_filter(
            stmt,
            resource_types=resource_types,
            resource_type=resource_type,
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_all(self, db: AsyncSession) -> Sequence[Resource]:
        """
        获取所有资源

        :param db: 数据库会话
        :return:
        """
        stmt = select(self.model).options(
            noload(Resource.user), 
            noload(Resource.view_history)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_by_user_id(self, db: AsyncSession, user_id: int) -> Sequence[Resource]:
        """
        通过用户ID获取资源列表

        :param db: 数据库会话
        :param user_id: 用户ID
        :return:
        """
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.is_deleted.is_(False)
        ).options(noload(Resource.user), noload(Resource.view_history))
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj: CreateResourceParam, current_user_id: int | None = None) -> Resource:
        """
        创建资源

        :param db: 数据库会话
        :param obj: 创建资源参数
        :param current_user_id: 当前用户ID
        :return:
        """
        if current_user_id and not obj.created_by:
            obj.created_by = current_user_id
        resource = await self.create_model(db, obj)
        await db.commit()
        return resource

    async def update(self, db: AsyncSession, pk: int, obj: UpdateResourceParam, current_user_id: int | None = None) -> int:
        """
        更新资源

        :param db: 数据库会话
        :param pk: 资源 ID
        :param obj: 更新参数
        :param current_user_id: 当前用户 ID
        :return:
        """
        # 将 schema 对象转换为字典，并添加 updated_by
        update_data = obj.model_dump(exclude_unset=True)
        if current_user_id:
            update_data["updated_by"] = current_user_id
        
        # 确保不会更新 created_time 和 created_by 字段
        update_data.pop("created_time", None)
        update_data.pop("created_by", None)
        
        # 手动设置 updated_time
        update_data["updated_time"] = timezone.now()
        
        # 使用 update_model_by_column 方法，只更新指定的字段
        result = await self.update_model_by_column(db, update_data, id=pk)
        await db.commit()
        return result

    async def delete(self, db: AsyncSession, pk: list[int]) -> int:
        """
        删除资源

        :param db: 数据库会话
        :param pk: 资源 ID 列表
        :return:
        """
        result = await self.delete_model_by_column(db, allow_multiple=True, id__in=pk)
        await db.commit()
        return result

    async def soft_delete(self, db: AsyncSession, pk: list[int]) -> int:
        """
        软删除资源

        :param db: 数据库会话
        :param pk: 资源 ID 列表
        :return:
        """
        result = await self.update_model_by_column(
            db, 
            {"is_deleted": True}, 
            allow_multiple=True, 
            id__in=pk
        )
        await db.commit()
        return result

    async def get_expiring_resources(
        self, 
        db: AsyncSession, 
        current_time: datetime,
        expiring_threshold: datetime
    ) -> list[Resource]:
        """
        获取即将过期的资源列表

        :param db: 数据库会话
        :param current_time: 当前时间
        :param expiring_threshold: 过期时间阈值
        :return: 即将过期的资源列表
        """
        stmt = (
            select(self.model)
            .where(
                and_(
                    # 资源未删除且状态正常
                    self.model.is_deleted.is_(False),
                    self.model.status == 1,
                    # 有过期时间设置
                    self.model.expired_at.is_not(None),
                    # 过期时间在当前时间和阈值时间之间
                    self.model.expired_at > current_time,
                    self.model.expired_at <= expiring_threshold,
                    # 非永久分享
                    self.model.expired_type > 0
                )
            )
            .order_by(self.model.expired_at.asc())
        )
        
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_expired_resources(
        self, 
        db: AsyncSession, 
        current_time: datetime
    ) -> list[Resource]:
        """
        获取已经过期的资源列表

        :param db: 数据库会话
        :param current_time: 当前时间
        :return: 已经过期的资源列表
        """
        stmt = (
            select(self.model)
            .where(
                and_(
                    # 资源未删除且状态正常
                    self.model.is_deleted.is_(False),
                    self.model.status == 1,
                    # 有过期时间设置
                    self.model.expired_at.is_not(None),
                    # 过期时间小于等于当前时间
                    self.model.expired_at <= current_time,
                    # 非永久分享
                    self.model.expired_type > 0
                )
            )
            .order_by(self.model.expired_at.asc())
        )
        
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_resources_by_temp_mode(
        self,
        db: AsyncSession,
        temp_mode: int,
    ) -> list[Resource]:
        """
        获取指定临时处理模式的资源列表

        :param db: 数据库会话
        :param temp_mode: 临时处理模式（0无操作 1定时删除 2定时刷新 3定时更新）
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                and_(
                    self.model.is_deleted.is_(False),
                    self.model.status == 1,
                    self.model.is_temp_file == temp_mode,
                )
            )
            .order_by(self.model.updated_time.desc())
            .options(noload(Resource.user), noload(Resource.view_history))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_view_count(self, db: AsyncSession, pwd_id: str, increment: int = 1) -> int:
        """
        更新资源浏览量

        :param db: 数据库会话
        :param pwd_id: 密码ID
        :param increment: 增量
        :return:
        """
        result = await self.update_model_by_column(
            db,
            {"view_count": self.model.view_count + increment},
            pwd_id=pwd_id
        )
        await db.commit()
        return result

    async def update_audit_status(self, db: AsyncSession, pk: int, audit_status: int) -> int:
        """
        更新资源审核状态

        :param db: 数据库会话
        :param pk: 资源 ID
        :param audit_status: 审核状态
        :return:
        """
        result = await self.update_model(db, pk, {"audit_status": audit_status})
        await db.commit()
        return result

    async def update_status(self, db: AsyncSession, pk: int, status: int) -> int:
        """
        更新资源状态

        :param db: 数据库会话
        :param pk: 资源 ID
        :param status: 状态
        :return:
        """
        result = await self.update_model(db, pk, {"status": status})
        await db.commit()
        return result

    async def get_statistics(self, db: AsyncSession, user_id: int | None = None) -> dict:
        """
        获取资源统计信息

        :param db: 数据库会话
        :param user_id: 用户ID
        :return:
        """
        from datetime import datetime

        from backend.app.coulddrive.model.resource import ResourceViewHistory
        
        # 基础统计查询
        stmt = select(
            func.count().label('total_count'),
            func.sum(case((self.model.status == 1, 1), else_=0)).label('active_count'),
            func.sum(case((self.model.audit_status == 0, 1), else_=0)).label('pending_audit_count'),
            func.sum(case((self.model.audit_status == 1, 1), else_=0)).label('approved_count'),
            func.sum(case((self.model.audit_status == 2, 1), else_=0)).label('rejected_count'),
            func.sum(case((self.model.is_deleted.is_(True), 1), else_=0)).label('deleted_count'),
            func.sum(self.model.view_count).label('total_views')
        )
        
        if user_id is not None:
            stmt = stmt.where(self.model.user_id == user_id)
        
        result = await db.execute(stmt)
        row = result.first()
        
        # 简化今日增长计算：获取今日0点前的总浏览量
        today = timezone.now().date()
        today_start = datetime.combine(today, time.min)
        
        # 查询今日0点前的总浏览量（简化版本）
        today_start_stmt = select(
            func.coalesce(func.sum(ResourceViewHistory.view_count), 0).label('today_start_views')
        ).where(
            ResourceViewHistory.record_time < today_start
        )
        
        # 如果指定了用户ID，需要通过资源表过滤
        if user_id is not None:
            today_start_stmt = today_start_stmt.where(
                ResourceViewHistory.pwd_id.in_(
                    select(self.model.pwd_id).where(self.model.user_id == user_id)
                )
            )
        
        # 获取每个pwd_id的最新记录（今日0点前）
        subquery = select(
            ResourceViewHistory.pwd_id,
            func.max(ResourceViewHistory.view_count).label('latest_views')
        ).where(
            ResourceViewHistory.record_time < today_start
        ).group_by(ResourceViewHistory.pwd_id).subquery()
        
        today_start_stmt = select(
            func.coalesce(func.sum(subquery.c.latest_views), 0).label('today_start_views')
        ).select_from(subquery)
        
        # 如果指定了用户ID，需要过滤
        if user_id is not None:
            today_start_stmt = today_start_stmt.where(
                subquery.c.pwd_id.in_(
                    select(self.model.pwd_id).where(self.model.user_id == user_id)
                )
            )
        
        today_start_result = await db.execute(today_start_stmt)
        today_start_row = today_start_result.first()
        
        total_views = row.total_views or 0
        today_start_views = today_start_row.today_start_views or 0
        today_growth = max(0, total_views - today_start_views)
        
        return {
            'total_count': row.total_count or 0,
            'active_count': row.active_count or 0,
            'pending_audit_count': row.pending_audit_count or 0,
            'approved_count': row.approved_count or 0,
            'rejected_count': row.rejected_count or 0,
            'deleted_count': row.deleted_count or 0,
            'total_views': total_views,
            'today_start_views': today_start_views,
            'today_growth': today_growth
        }

    async def check_pwd_id_exists(self, db: AsyncSession, pwd_id: str, exclude_id: int | None = None) -> bool:
        """
        检查密码ID是否已存在

        :param db: 数据库会话
        :param pwd_id: 密码ID
        :param exclude_id: 排除的资源ID
        :return:
        """
        stmt = select(func.count(self.model.id)).where(self.model.pwd_id == pwd_id)
        if exclude_id:
            stmt = stmt.where(self.model.id != exclude_id)
        
        result = await db.execute(stmt)
        count = result.scalar()
        return count > 0

    async def check_share_id_exists(self, db: AsyncSession, share_id: str, exclude_id: int | None = None) -> bool:
        """
        检查分享ID是否已存在

        :param db: 数据库会话
        :param share_id: 分享ID
        :param exclude_id: 排除的资源ID
        :return:
        """
        stmt = select(func.count(self.model.id)).where(self.model.share_id == share_id)
        if exclude_id:
            stmt = stmt.where(self.model.id != exclude_id)
        
        result = await db.execute(stmt)
        count = result.scalar()
        return count > 0

    async def count_resources_by_date(self, db: AsyncSession, date_end: datetime) -> int:
        """
        获取指定日期前的资源总数

        :param db: 数据库会话
        :param date_end: 截止日期
        :return:
        """
        stmt = select(func.count(self.model.id)).where(
            self.model.created_time <= date_end,
            self.model.is_deleted.is_(False)
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def count_active_resources_by_date(self, db: AsyncSession, date_end: datetime) -> int:
        """
        获取指定日期前的活跃资源数

        :param db: 数据库会话
        :param date_end: 截止日期
        :return:
        """
        stmt = select(func.count(self.model.id)).where(
            self.model.created_time <= date_end,
            self.model.is_deleted.is_(False),
            self.model.status == 1
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def count_new_resources_by_date(self, db: AsyncSession, date_start: datetime, date_end: datetime) -> int:
        """
        获取指定日期范围内的新增资源数

        :param db: 数据库会话
        :param date_start: 开始日期
        :param date_end: 结束日期
        :return:
        """
        stmt = select(func.count(self.model.id)).where(
            self.model.created_time >= date_start,
            self.model.created_time <= date_end,
            self.model.is_deleted.is_(False)
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def vector_search(
        self,
        db: AsyncSession,
        query_text: str,
        limit: int = 20,
        similarity_threshold: float = 0.7,
        category_id: int | None = None,
        category_ids: list[int] | None = None
    ) -> list[tuple[Resource, float]]:
        """
        向量搜索资源

        :param db: 数据库会话
        :param query_text: 搜索查询文本（在资源介绍和描述中搜索）
        :param limit: 返回结果数量限制
        :param similarity_threshold: 相似度阈值 (0-1)，只返回大于此阈值的结果
        :param category_id: 分类过滤
        :param category_ids: 分类 ID 列表（包含子分类）
        :return: (资源对象, 相似度分数) 列表，按相似度降序排列
        """
        # 将查询文本转换为向量
        query_vector = await embed(query_text)

        # 使用 pgvector 的余弦距离运算符 (<=>)
        # 余弦距离: 0 表示完全相同，2 表示完全相反
        # 我们将其转换为相似度分数: 1 - (距离 / 2)
        distance_expr = text("content_vector <=> :query_vector")

        # 构建过滤条件
        filters = [
            self.model.is_deleted.is_(False),
            self.model.status == 1,
            self.model.content_vector.isnot(None)
        ]

        # 只保留分类过滤
        if category_id is not None:
            if category_ids:
                filters.append(self.model.category_id.in_(category_ids))
            else:
                filters.append(self.model.category_id == category_id)

        stmt = (
            select(
                self.model,
                text("(1 - (content_vector <=> :query_vector) / 2) AS similarity")
            )
            .where(and_(*filters))
            .order_by(distance_expr)
            .limit(limit)
            .params(query_vector=str(query_vector))
        )

        result = await db.execute(stmt)
        rows = result.all()

        # 过滤低于相似度阈值的结果
        filtered_results = [
            (row[0], float(row[1]))
            for row in rows
            if float(row[1]) >= similarity_threshold
        ]

        return filtered_results

    async def update_resource_vector(self, db: AsyncSession, resource_id: int) -> bool:
        """
        更新单个资源的向量

        :param db: 数据库会话
        :param resource_id: 资源ID
        :return: 是否更新成功
        """
        # 获取资源
        resource = await self.get(db, resource_id)
        if not resource:
            log.warning(f"资源 {resource_id} 不存在")
            return False

        # 转换为字典格式（只包含向量化需要的字段）
        resource_data = {
            "id": resource.id,
            "description": resource.description,
            "resource_intro": resource.resource_intro,
        }

        # 生成向量
        # 拼接向量化文本
        text_parts = []
        resource_intro = (resource_data.get("resource_intro") or "").strip()
        if resource_intro:
            text_parts.append(resource_intro)
        description = (resource_data.get("description") or "").strip()
        if description:
            text_parts.append(description)
        combined_text = "\n".join(text_parts)

        if not combined_text:
            log.warning(f"资源 {resource_data.get('id')} 没有可向量化的文本内容")
            vector = [0.0] * 1536
        else:
            vector = await embed(combined_text)

        # 更新向量
        await self.update_model_by_column(
            db,
            {"content_vector": vector},
            id=resource_id
        )
        await db.commit()

        log.info(f"成功更新资源 {resource_id} 的向量")
        return True

    async def batch_update_vectors(self, db: AsyncSession, batch_size: int = 50) -> int:
        """
        批量更新所有资源的向量

        :param db: 数据库会话
        :param batch_size: 每批次处理数量
        :return: 成功更新的数量
        """
        # 获取所有需要向量化的资源（未删除且向量为空）
        stmt = select(self.model).where(
            and_(
                self.model.is_deleted.is_(False),
                self.model.content_vector.is_(None)
            )
        )
        result = await db.execute(stmt)
        resources = result.scalars().all()

        if not resources:
            log.info("没有需要向量化的资源")
            return 0

        total_count = len(resources)
        log.info(f"开始批量向量化 {total_count} 个资源")

        success_count = 0

        for i in range(0, total_count, batch_size):
            batch = resources[i : i + batch_size]

            try:
                # 拼接向量化文本
                texts = []
                for resource in batch:
                    text_parts = []
                    if resource.resource_intro:
                        text_parts.append(resource.resource_intro.strip())
                    if resource.description:
                        text_parts.append(resource.description.strip())
                    texts.append("\n".join(text_parts))

                vectors = await batch_embed(texts, batch_size=batch_size)

                # 批量更新
                for resource, vector in zip(batch, vectors):
                    await self.update_model_by_column(
                        db,
                        {"content_vector": vector},
                        id=resource.id
                    )
                    success_count += 1

                await db.commit()
                log.info(f"批量向量化进度: {min(i + batch_size, total_count)}/{total_count}")

            except Exception as e:
                log.error(f"批量向量化失败 (批次 {i // batch_size + 1}): {e}")
                await db.rollback()
                continue

        log.info(f"批量向量化完成，成功: {success_count}/{total_count}")
        return success_count


class CRUDResourceViewHistory(CRUDPlus[ResourceViewHistory]):
    """资源浏览量历史记录数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> ResourceViewHistory | None:
        """
        获取浏览量历史记录详情

        :param db: 数据库会话
        :param pk: 历史记录 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_pwd_id(self, db: AsyncSession, pwd_id: str) -> Sequence[ResourceViewHistory]:
        """
        通过密码ID获取浏览量历史记录

        :param db: 数据库会话
        :param pwd_id: 密码ID
        :return:
        """
        stmt = select(self.model).where(
            self.model.pwd_id == pwd_id
        ).order_by(desc(self.model.record_time))
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_list(self, params: GetResourceViewHistoryListParam) -> Select:
        """
        获取浏览量历史记录列表查询语句

        :param params: 查询参数
        :return:
        """
        stmt = select(self.model).order_by(desc(self.model.record_time))
        
        filters = []
        if params.pwd_id is not None:
            filters.append(self.model.pwd_id == params.pwd_id)
        if params.start_time is not None:
            filters.append(self.model.record_time >= params.start_time)
        if params.end_time is not None:
            filters.append(self.model.record_time <= params.end_time)
        
        if filters:
            stmt = stmt.where(and_(*filters))
        
        # 避免加载关联数据，防止懒加载导致的异步问题
        stmt = stmt.options(noload(ResourceViewHistory.resource))
        
        return stmt

    async def get_trend_data(
        self, 
        db: AsyncSession, 
        pwd_id: str, 
        start_time: datetime | None = None,
        end_time: datetime | None = None
    ) -> Sequence[ResourceViewHistory]:
        """
        获取资源浏览量趋势数据

        :param db: 数据库会话
        :param pwd_id: 密码ID
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return:
        """
        stmt = select(self.model).where(
            self.model.pwd_id == pwd_id
        ).order_by(self.model.record_time)
        
        if start_time:
            stmt = stmt.where(self.model.record_time >= start_time)
        if end_time:
            stmt = stmt.where(self.model.record_time <= end_time)
        
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj: CreateResourceViewHistoryParam) -> ResourceViewHistory:
        """
        创建浏览量历史记录

        :param db: 数据库会话
        :param obj: 创建浏览量历史记录参数
        :return:
        """
        history = await self.create_model(db, obj)
        await db.commit()
        return history

    async def delete_old_records(self, db: AsyncSession, days: int = 30) -> int:
        """
        删除旧的浏览量历史记录

        :param db: 数据库会话
        :param days: 保留天数
        :return:
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        result = await self.delete_model_by_column(
            db, 
            allow_multiple=True, 
            record_time__lt=cutoff_date
        )
        await db.commit()
        return result

    async def get_total_views_by_date(self, db: AsyncSession, date_end: datetime) -> int:
        """
        获取指定日期前的总浏览量

        :param db: 数据库会话
        :param date_end: 截止日期
        :return:
        """
        # 获取每个pwd_id在指定日期前的最新浏览量记录
        subquery = select(
            self.model.pwd_id,
            func.max(self.model.view_count).label('latest_views')
        ).where(
            self.model.record_time <= date_end
        ).group_by(self.model.pwd_id).subquery()
        
        # 计算总浏览量
        stmt = select(
            func.coalesce(func.sum(subquery.c.latest_views), 0).label('total_views')
        ).select_from(subquery)
        
        result = await db.execute(stmt)
        row = result.first()
        return row.total_views or 0


# 创建 DAO 实例
resource_dao = CRUDResource(Resource)
resource_view_history_dao = CRUDResourceViewHistory(ResourceViewHistory) 
