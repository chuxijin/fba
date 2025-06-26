#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence, Tuple
from datetime import datetime, timedelta, time

from sqlalchemy import Select, and_, desc, select, func, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.coulddrive.model.resource import Resource, ResourceViewHistory
from backend.app.coulddrive.schema.resource import (
    CreateResourceParam, 
    UpdateResourceParam,
    GetResourceListParam,
    CreateResourceViewHistoryParam,
    GetResourceViewHistoryListParam
)
from backend.utils.timezone import timezone


class CRUDResource(CRUDPlus[Resource]):
    """资源数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> Resource | None:
        """
        获取资源详情

        :param db: 数据库会话
        :param pk: 资源 ID
        :return:
        """
        return await self.select_model(db, pk)

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

    async def get_list(self, params: GetResourceListParam) -> Select:
        """
        获取资源列表查询语句

        :param params: 查询参数
        :return:
        """
        stmt = select(self.model).order_by(desc(self.model.created_time))

        filters = []
        
        if params.domain is not None:
            filters.append(self.model.domain == params.domain)
        if params.subject is not None:
            filters.append(self.model.subject == params.subject)
        if params.resource_type is not None:
            filters.append(self.model.resource_type == params.resource_type)
        if params.url_type is not None:
            filters.append(self.model.url_type == params.url_type)
        if params.status is not None:
            filters.append(self.model.status == params.status)
        if params.audit_status is not None:
            filters.append(self.model.audit_status == params.audit_status)
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

        # 避免加载关联数据，防止懒加载导致的异步问题
        stmt = stmt.options(noload(Resource.user), noload(Resource.view_history))
        
        return stmt

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
            self.model.is_deleted == False
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
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pk)

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
        from datetime import datetime, time
        from backend.app.coulddrive.model.resource import ResourceViewHistory
        
        # 基础统计查询
        stmt = select(
            func.count().label('total_count'),
            func.sum(case((self.model.status == 1, 1), else_=0)).label('active_count'),
            func.sum(case((self.model.audit_status == 0, 1), else_=0)).label('pending_audit_count'),
            func.sum(case((self.model.audit_status == 1, 1), else_=0)).label('approved_count'),
            func.sum(case((self.model.audit_status == 2, 1), else_=0)).label('rejected_count'),
            func.sum(case((self.model.is_deleted == True, 1), else_=0)).label('deleted_count'),
            func.sum(self.model.view_count).label('total_views')
        )
        
        if user_id is not None:
            stmt = stmt.where(self.model.user_id == user_id)
        
        result = await db.execute(stmt)
        row = result.first()
        
        # 简化今日增长计算：获取今日0点前的总浏览量
        today = datetime.now().date()
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
        cutoff_date = datetime.now() - timedelta(days=days)
        result = await self.delete_model_by_column(
            db, 
            allow_multiple=True, 
            record_time__lt=cutoff_date
        )
        await db.commit()
        return result


# 创建 DAO 实例
resource_dao = CRUDResource(Resource)
resource_view_history_dao = CRUDResourceViewHistory(ResourceViewHistory) 