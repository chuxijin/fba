#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import random
from typing import Sequence, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_resource import resource_dao, resource_view_history_dao
from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.admin.crud.crud_category import category_dao
from backend.app.coulddrive.model.resource import Resource, ResourceViewHistory
from backend.app.coulddrive.schema.resource import (
    CreateResourceParam,
    UpdateResourceParam,
    GetResourceListParam,
    ResourceStatistics,
    CreateResourceViewHistoryParam,
    GetResourceViewHistoryListParam,
    ResourceViewTrendResponse,
    ResourceViewTrendData,
    UpdateResourceViewCountParam,
    GetResourceDetail,
    ResourceListItem,
    GetResourceViewHistoryDetail,
    GetResourceViewTrendParam,
    OverallStatisticsTrendResponse,
    OverallStatisticsTrendData,
    GetOverallStatisticsTrendParam,
    ResourceKnowledgeItem,
    VectorSearchResultItem,
    VectorSearchKnowledgeResultItem
)
from backend.app.coulddrive.schema.file import ListShareInfoParam, ShareParam
from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService
from backend.common.exception.errors import NotFoundError, ForbiddenError
from backend.common.pagination import paging_data, paging_list_data, _CustomPageParams
from backend.utils.sensitive_words import contains_sensitive_words


class ResourceService:
    """资源服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GetResourceDetail:
        """
        获取资源详情

        :param db: 数据库会话
        :param pk: 资源 ID
        :return:
        """
        resource = await resource_dao.get(db, pk)
        if not resource:
            raise NotFoundError(msg="资源不存在")
        return GetResourceDetail.model_validate(resource)

    @staticmethod
    async def get_model(*, db: AsyncSession, pk: int) -> Resource:
        """
        获取资源模型对象

        :param db: 数据库会话
        :param pk: 资源 ID
        :return:
        """
        resource = await resource_dao.get(db, pk)
        if not resource:
            raise NotFoundError(msg="资源不存在")
        return resource

    @staticmethod
    async def get_by_pwd_id(*, db: AsyncSession, pwd_id: str) -> Resource:
        """
        通过密码 ID 获取资源

        :param db: 数据库会话
        :param pwd_id: 密码 ID
        :return:
        """
        resource = await resource_dao.get_by_pwd_id(db, pwd_id)
        if not resource:
            raise NotFoundError(msg="资源不存在")
        return resource

    @staticmethod
    async def get_by_share_id(*, db: AsyncSession, share_id: str) -> Resource:
        """
        通过分享 ID 获取资源

        :param db: 数据库会话
        :param share_id: 分享 ID
        :return:
        """
        resource = await resource_dao.get_by_share_id(db, share_id)
        if not resource:
            raise NotFoundError(msg="资源不存在")
        return resource

    @staticmethod
    async def get_hot_list(
        *,
        db: AsyncSession,
        category_id: int | None = None,
        limit: int = 20
    ) -> Sequence[ResourceListItem]:
        """
        获取热门资源列表

        :param db: 数据库会话
        :param category_id: 分类 ID
        :param limit: 获取数量
        :return:
        """
        category_ids = None
        if category_id:
            category_ids = await category_dao.get_all_children_ids(db, category_id)
        
        resources = await resource_dao.get_hot_list(db, category_ids, limit)
        return [ResourceListItem.model_validate(r) for r in resources]

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        params: GetResourceListParam
    ) -> dict[str, Any]:
        """
        获取资源列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        # 如果提供了分类过滤，获取该分类下的所有子分类ID
        category_ids = None
        if params.category_id is not None:
            category_ids = await category_dao.get_all_children_ids(db, params.category_id)
        
        stmt = await resource_dao.get_list(params, category_ids=category_ids)
        # 传入 ResourceListItem 类，让 paging_data 在序列化前转换 ORM 对象
        return await paging_data(db, stmt, schema_cls=ResourceListItem)

    @staticmethod
    async def create(
        *,
        db: AsyncSession,
        obj: CreateResourceParam,
        created_by: int,
        auto_vectorize: bool = False
    ) -> GetResourceDetail:
        """
        创建资源

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :param auto_vectorize: 是否自动向量化
        :return:
        """
        # 检查用户是否存在
        user = await drive_account_dao.get(db, obj.user_id)
        if not user:
            raise NotFoundError(msg="网盘用户不存在")

        try:
            # 直接使用外部模式创建服务实例（避免重复查询数据库）
            service = CouldDriveService(auth_data=user.cookies, drive_type=DriveType(user.type))

            # 获取分享信息参数
            share_info_params = ListShareInfoParam(
                drive_type=DriveType(user.type),
                source_type="link",
                source_id=obj.url,
                page=1,
                size=1
            )

            # 获取分享信息
            share_info_list = await service.get_share_info(params=share_info_params)

            # 如果获取到分享信息，使用第一个
            share_info = share_info_list[0] if share_info_list else None

        except Exception as e:
            # 如果获取分享信息失败，使用默认值
            share_info = None

        # 创建完整的资源数据
        resource_data = obj.model_dump()
        resource_data["created_by"] = created_by

        # 如果获取到分享信息，添加分享相关字段
        if share_info:
            share_data = share_info.model_dump()
            # 将password字段映射到extract_code字段
            if 'password' in share_data:
                share_data['extract_code'] = share_data.pop('password')
            
            # 保存用户输入的extract_code，避免被API返回的数据覆盖
            user_extract_code = resource_data.get('extract_code')
            resource_data.update(share_data)
            # 如果用户输入了extract_code，使用用户输入的值
            if user_extract_code:
                resource_data['extract_code'] = user_extract_code
        else:
            # 使用默认值
            resource_data.update({
                "title": obj.main_name,
                "share_id": None,
                "pwd_id": None,
                "expired_type": 0,
                "view_count": 0,
                "expired_at": None,
                "expired_left": None,
                "audit_status": 0,
                "status": 1,
                "file_only_num": None,
                "file_size": None,
                "path_info": None,
            })

        # 检查密码ID是否已存在，如果存在则更新现有记录
        if resource_data.get("pwd_id"):
            existing_resource = await resource_dao.get_by_pwd_id(db, resource_data["pwd_id"])
            if existing_resource:
                # 更新现有记录 - 只更新允许的字段
                update_data = {}
                allowed_update_fields = {
                    "category_id", "main_name", "resource_type", "description", 
                    "resource_intro", "resource_image", "url", "url_type", "extract_code",
                    "is_temp_file", "price", "suggested_price", "sort", "remark",
                    "title", "share_id", "pwd_id", "expired_type", "view_count",
                    "expired_at", "expired_left", "audit_status", "status",
                    "file_only_num", "file_size", "path_info", "file_id", "content", "uk_uid",
                    "local_file_path", "file_type"
                }
                
                for field in allowed_update_fields:
                    if field in resource_data:
                        update_data[field] = resource_data[field]
                
                update_param = UpdateResourceParam(**update_data)
                await resource_dao.update(db, existing_resource.id, update_param, created_by)
                
                # 重新获取更新后的资源
                updated_resource = await resource_dao.get(db, existing_resource.id)
                
                # 如果浏览量有变化且有pwd_id，记录浏览量历史
                if (updated_resource.pwd_id and
                    'view_count' in update_data and
                    update_data['view_count'] != existing_resource.view_count):
                    try:
                        history_param = CreateResourceViewHistoryParam(
                            pwd_id=updated_resource.pwd_id,
                            view_count=updated_resource.view_count
                        )
                        await resource_view_history_dao.create(db, history_param)
                    except Exception as e:
                        # 记录浏览量历史失败不影响资源创建
                        pass

                # 自动向量化（如果启用）
                if auto_vectorize:
                    try:
                        await resource_dao.update_resource_vector(db, updated_resource.id)
                    except Exception as e:
                        # 向量化失败不影响资源创建
                        pass

                return GetResourceDetail.model_validate(updated_resource)

        # 检查分享ID是否已存在，如果存在则更新现有记录
        if resource_data.get("share_id"):
            existing_resource = await resource_dao.get_by_share_id(db, resource_data["share_id"])
            if existing_resource:
                # 更新现有记录 - 只更新允许的字段
                update_data = {}
                allowed_update_fields = {
                    "category_id", "main_name", "resource_type", "description", 
                    "resource_intro", "resource_image", "url", "url_type", "extract_code",
                    "is_temp_file", "price", "suggested_price", "sort", "remark",
                    "title", "share_id", "pwd_id", "expired_type", "view_count",
                    "expired_at", "expired_left", "audit_status", "status",
                    "file_only_num", "file_size", "path_info", "file_id", "content", "uk_uid",
                    "local_file_path", "file_type"
                }
                
                for field in allowed_update_fields:
                    if field in resource_data:
                        update_data[field] = resource_data[field]
                
                update_param = UpdateResourceParam(**update_data)
                await resource_dao.update(db, existing_resource.id, update_param, created_by)
                
                # 重新获取更新后的资源
                updated_resource = await resource_dao.get(db, existing_resource.id)
                
                # 如果浏览量有变化且有pwd_id，记录浏览量历史
                if (updated_resource.pwd_id and
                    'view_count' in update_data and
                    update_data['view_count'] != existing_resource.view_count):
                    try:
                        history_param = CreateResourceViewHistoryParam(
                            pwd_id=updated_resource.pwd_id,
                            view_count=updated_resource.view_count
                        )
                        await resource_view_history_dao.create(db, history_param)
                    except Exception as e:
                        # 记录浏览量历史失败不影响资源创建
                        pass

                # 自动向量化（如果启用）
                if auto_vectorize:
                    try:
                        await resource_dao.update_resource_vector(db, updated_resource.id)
                    except Exception as e:
                        # 向量化失败不影响资源创建
                        pass

                return GetResourceDetail.model_validate(updated_resource)

        # 创建新的资源记录
        resource = Resource(**resource_data)
        db.add(resource)
        await db.commit()
        await db.refresh(resource)
        
        # 记录初始浏览量历史（如果有pwd_id）
        if resource.pwd_id:
            try:
                history_param = CreateResourceViewHistoryParam(
                    pwd_id=resource.pwd_id,
                    view_count=resource.view_count or 0
                )
                await resource_view_history_dao.create(db, history_param)
            except Exception as e:
                # 记录浏览量历史失败不影响资源创建
                pass

        # 自动向量化（如果启用）
        if auto_vectorize:
            try:
                await resource_dao.update_resource_vector(db, resource.id)
            except Exception as e:
                # 向量化失败不影响资源创建
                pass

        return GetResourceDetail.model_validate(resource)

    @staticmethod
    async def update(
        *,
        db: AsyncSession,
        pk: int,
        obj: UpdateResourceParam,
        updated_by: int,
        auto_refresh: bool = False
    ) -> GetResourceDetail:
        """
        更新资源

        :param db: 数据库会话
        :param pk: 资源ID
        :param obj: 更新参数
        :param updated_by: 更新者ID
        :param auto_refresh: 是否自动刷新分享信息
        :return:
        """
        # 检查资源是否存在
        resource = await resource_dao.get(db, pk)
        if not resource:
            raise NotFoundError(msg="资源不存在")

        # 准备更新数据
        update_data = obj.model_dump(exclude_unset=True)
        update_data["updated_by"] = updated_by

        # 如果需要自动刷新分享信息
        if auto_refresh and resource.url:
            try:
                # 获取用户信息
                user = await drive_account_dao.get(db, resource.user_id)
                if user:
                    # 直接使用外部模式创建服务实例（避免重复查询数据库）
                    service = CouldDriveService(auth_data=user.cookies, drive_type=DriveType(user.type))

                    # 获取分享信息参数
                    share_info_params = ListShareInfoParam(
                        drive_type=DriveType(user.type),
                        source_type="link",
                        source_id=resource.url,
                        page=1,
                        size=1
                    )

                    # 获取分享信息
                    share_info_list = await service.get_share_info(params=share_info_params)

                    # 如果获取到分享信息，更新相关字段
                    if share_info_list:
                        share_info = share_info_list[0]
                        share_data = share_info.model_dump()
                        # 将password字段映射到extract_code字段
                        if 'password' in share_data:
                            share_data['extract_code'] = share_data.pop('password')
                        # 只更新分享相关的字段，不覆盖用户手动输入的字段
                        share_fields = {
                            "title", "share_id", "pwd_id", "expired_type", "view_count",
                            "expired_at", "expired_left", "audit_status", "status",
                            "file_only_num", "file_size", "path_info", "extract_code"
                        }
                        for field in share_fields:
                            if field in share_data:
                                update_data[field] = share_data[field]

            except Exception as e:
                # 如果获取分享信息失败，继续执行更新操作
                pass

        # 执行更新
        update_param = UpdateResourceParam(**update_data)
        await resource_dao.update(db, pk, update_param, updated_by)

        # 重新获取更新后的资源
        updated_resource = await resource_dao.get(db, pk)
        if not updated_resource:
            raise NotFoundError(msg="更新后获取资源失败")
        
        # 如果浏览量有变化且有pwd_id，记录浏览量历史
        if (updated_resource.pwd_id and 
            'view_count' in update_data and 
            update_data['view_count'] != resource.view_count):
            try:
                history_param = CreateResourceViewHistoryParam(
                    pwd_id=updated_resource.pwd_id,
                    view_count=updated_resource.view_count
                )
                await resource_view_history_dao.create(db, history_param)
            except Exception as e:
                # 记录浏览量历史失败不影响资源更新
                pass
            
        return GetResourceDetail.model_validate(updated_resource)

    @staticmethod
    async def refresh_share_info(db: AsyncSession, resource_id: int, updated_by: int) -> GetResourceDetail:
        """
        刷新资源分享信息
        
        :param db: 数据库会话
        :param resource_id: 资源ID
        :param updated_by: 更新者ID
        :return: 更新后的资源详情
        """
        # 获取资源
        resource = await resource_dao.get(db, resource_id)
        if not resource:
            raise NotFoundError(msg="资源不存在")
        
        # 获取关联的网盘用户
        user = await drive_account_dao.get(db, resource.user_id)
        if not user:
            raise NotFoundError(msg="关联的网盘用户不存在")

        # 直接使用外部模式创建服务实例（避免重复查询数据库）
        service = CouldDriveService(auth_data=user.cookies, drive_type=DriveType(user.type))

        # 获取分享信息参数
        share_info_params = ListShareInfoParam(
            drive_type=DriveType(user.type),
            source_type="link",
            source_id=resource.url,
            page=1,
            size=1
        )

        # 获取分享信息
        share_info_list = await service.get_share_info(params=share_info_params)
        
        if not share_info_list:
            raise NotFoundError(msg="未获取到分享信息")
        
        share_info = share_info_list[0]
        
        # 检查哪些字段需要更新
        update_fields = {}
        share_data = share_info.model_dump()
        # 将password字段映射到extract_code字段
        if 'password' in share_data:
            share_data['extract_code'] = share_data.pop('password')
        
        # 刷新分享信息时，同步核心分享字段与展示字段（不覆盖用户手动维护的提取码）
        for field in [
            'title', 'share_id', 'pwd_id', 'url',
            'audit_status', 'status', 'file_id',
            'view_count', 'expired_left', 'file_size', 'expired_at', 'path_info', 'expired_type', 'file_only_num'
        ]:
            if hasattr(resource, field):
                old_value = getattr(resource, field)
                new_value = share_data.get(field)
                
                if new_value is not None and old_value != new_value:
                    update_fields[field] = new_value
        
        # 如果有字段需要更新，执行更新
        if update_fields:
            update_param = UpdateResourceParam(**update_fields)
            await resource_dao.update(db, resource_id, update_param, updated_by)
        
        # 获取最新的资源信息（用于记录浏览量历史）
        updated_resource = await resource_dao.get(db, resource_id)
        if not updated_resource:
            raise NotFoundError(msg="获取更新后的资源失败")
        
        # 如果有pwd_id，记录浏览量历史（无论浏览量是否变化）
        if updated_resource.pwd_id:
            try:
                history_param = CreateResourceViewHistoryParam(
                    pwd_id=updated_resource.pwd_id,
                    view_count=updated_resource.view_count or 0
                )
                await resource_view_history_dao.create(db, history_param)
            except Exception as e:
                # 记录浏览量历史失败不影响分享信息刷新
                pass
        
        # 返回更新后的资源详情
        return GetResourceDetail.model_validate(updated_resource)

    @staticmethod
    async def delete(
        *,
        db: AsyncSession,
        ids: list[int],
        deleted_by: int
    ) -> int:
        """
        批量删除资源（软删除）

        :param db: 数据库会话
        :param ids: 资源ID列表
        :param deleted_by: 删除者ID
        :return: 删除数量
        """
        # 检查资源是否存在
        for pk in ids:
            await ResourceService.get_model(db=db, pk=pk)

        count = await resource_dao.soft_delete(db, ids)
        if count == 0:
            raise NotFoundError(msg="删除失败，资源不存在")

        return count

    @staticmethod
    async def soft_delete_resource(*, db: AsyncSession, pk: int) -> None:
        """
        软删除资源

        :param db: 数据库会话
        :param pk: 资源 ID
        :return:
        """
        resource = await ResourceService.get_model(db=db, pk=pk)

        count = await resource_dao.soft_delete(db, [pk])
        if count == 0:
            raise NotFoundError(msg="删除失败，资源不存在")

    @staticmethod
    async def soft_delete_resources(*, db: AsyncSession, pks: list[int]) -> None:
        """
        批量软删除资源

        :param db: 数据库会话
        :param pks: 资源 ID 列表
        :return:
        """
        # 检查资源是否存在
        for pk in pks:
            await ResourceService.get_model(db=db, pk=pk)

        count = await resource_dao.soft_delete(db, pks)
        if count == 0:
            raise NotFoundError(msg="删除失败，资源不存在")

    @staticmethod
    async def update_view_count(*, db: AsyncSession, pwd_id: str, increment: int = 1) -> None:
        """
        更新资源浏览量

        :param db: 数据库会话
        :param pwd_id: 密码 ID
        :param increment: 增量
        :return:
        """
        resource = await ResourceService.get_by_pwd_id(db=db, pwd_id=pwd_id)

        count = await resource_dao.update_view_count(db, pwd_id, increment)
        if count == 0:
            raise NotFoundError(msg="更新失败，资源不存在")

        # 记录浏览量历史
        history_param = CreateResourceViewHistoryParam(
            pwd_id=pwd_id,
            view_count=resource.view_count + increment
        )
        await resource_view_history_dao.create(db, history_param)

    @staticmethod
    async def update_audit_status(*, db: AsyncSession, pk: int, audit_status: int) -> None:
        """
        更新资源审核状态

        :param db: 数据库会话
        :param pk: 资源 ID
        :param audit_status: 审核状态
        :return:
        """
        resource = await ResourceService.get_model(db=db, pk=pk)

        count = await resource_dao.update_audit_status(db, pk, audit_status)
        if count == 0:
            raise NotFoundError(msg="更新失败，资源不存在")

    @staticmethod
    async def update_status(*, db: AsyncSession, pk: int, status: int) -> None:
        """
        更新资源状态

        :param db: 数据库会话
        :param pk: 资源 ID
        :param status: 状态
        :return:
        """
        resource = await ResourceService.get_model(db=db, pk=pk)

        count = await resource_dao.update_status(db, pk, status)
        if count == 0:
            raise NotFoundError(msg="更新失败，资源不存在")

    @staticmethod
    async def get_statistics(*, db: AsyncSession, user_id: int | None = None) -> ResourceStatistics:
        """
        获取资源统计信息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stats = await resource_dao.get_statistics(db, user_id)
        return ResourceStatistics(**stats)

    @staticmethod
    async def get_by_user_id(*, db: AsyncSession, user_id: int) -> Sequence[Resource]:
        """
        通过用户 ID 获取资源列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        # 检查用户是否存在
        user = await drive_account_dao.get(db, user_id)
        if not user:
            raise NotFoundError(msg="网盘用户不存在")

        return await resource_dao.get_by_user_id(db, user_id)

    @staticmethod
    async def get_overall_statistics_trend(
        *,
        db: AsyncSession,
        params: GetOverallStatisticsTrendParam
    ) -> OverallStatisticsTrendResponse:
        """
        获取整体统计趋势

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_
        
        # 确定查询的日期范围
        if params.start_date and params.end_date:
            start_date = datetime.strptime(params.start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(params.end_date, '%Y-%m-%d').date()
        else:
            # 默认获取最近7天的数据
            days = params.days or 7
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days-1)
        
        # 生成日期列表
        date_list = []
        current_date = start_date
        while current_date <= end_date:
            date_list.append(current_date)
            current_date += timedelta(days=1)
        
        trend_data = []
        
        # 为每个日期获取统计数据
        for date in date_list:
            date_start = datetime.combine(date, datetime.min.time())
            date_end = datetime.combine(date, datetime.max.time())
            
            # 获取当日的资源统计
            total_count = await resource_dao.count_resources_by_date(db, date_end)
            active_count = await resource_dao.count_active_resources_by_date(db, date_end)
            new_resources = await resource_dao.count_new_resources_by_date(db, date_start, date_end)
            
            # 获取当日的总浏览量（从浏览量历史记录中获取）
            total_views = await resource_view_history_dao.get_total_views_by_date(db, date_end)
            
            trend_data.append(
                OverallStatisticsTrendData(
                    date=date.strftime('%Y-%m-%d'),
                    total_count=total_count,
                    total_views=total_views,
                    active_count=active_count,
                    new_resources=new_resources
                )
            )
        
        # 计算汇总信息
        if trend_data:
            summary = {
                "total_resources_growth": trend_data[-1].total_count - trend_data[0].total_count if len(trend_data) > 1 else 0,
                "total_views_growth": trend_data[-1].total_views - trend_data[0].total_views if len(trend_data) > 1 else 0,
                "average_daily_new_resources": sum(item.new_resources for item in trend_data) / len(trend_data),
                "period_days": len(trend_data)
            }
        else:
            summary = {}
        
        return OverallStatisticsTrendResponse(
            trend_data=trend_data,
            summary=summary
        )

    @staticmethod
    async def refresh_by_id(
        *,
        db: AsyncSession,
        pk: int,
        expired_type: int = 7,
        updated_by: int | None = None,
        set_permanent: bool = False
    ) -> Dict[str, Any]:
        """
        刷新资源分享链接

        :param db: 数据库会话
        :param pk: 资源 ID
        :param expired_type: 新分享的过期天数，默认 7 天，0 表示永久
        :param updated_by: 更新者 ID
        :param set_permanent: 是否设为永久并清空临时模式
        :return: 执行结果
        """
        try:
            # 获取资源信息
            resource = await resource_dao.get(db, pk)
            if not resource:
                return {
                    "success": False,
                    "error": "资源不存在",
                    "resource_id": pk
                }

            # 检查资源状态
            if resource.is_deleted or resource.status != 1:
                return {
                    "success": False,
                    "error": "资源已删除或停用",
                    "resource_id": pk
                }

            # 获取用户网盘账户信息
            drive_account = await drive_account_dao.get(db, resource.user_id)
            if not drive_account or not drive_account.is_valid:
                return {
                    "success": False,
                    "error": "网盘账户不存在或无效",
                    "resource_id": pk
                }

            # 检查 cookies 是否存在
            if not drive_account.cookies:
                return {
                    "success": False,
                    "error": "网盘账户缺少认证信息",
                    "resource_id": pk
                }

            # 检查是否有文件ID
            if not resource.file_id:
                return {
                    "success": False,
                    "error": "缺少文件ID，无法重新分享",
                    "resource_id": pk
                }

            # 直接使用外部模式创建服务实例（避免重复查询数据库）
            service = CouldDriveService(auth_data=drive_account.cookies, drive_type=DriveType(drive_account.type))

            # 创建新的分享参数
            share_params = ShareParam(
                drive_type=DriveType(drive_account.type),
                file_name=resource.title or resource.main_name,
                file_ids=[resource.file_id],
                expired_type=expired_type,
                password=resource.extract_code
            )

            # 调用分享服务
            new_share_info = await service.create_share(params=share_params)

            # 创建更新参数，只设置需要更新的字段
            update_data = {
                "url": new_share_info.url,
                "share_id": new_share_info.share_id,
                "pwd_id": new_share_info.pwd_id,
                "expired_at": new_share_info.expired_at,
                "expired_left": new_share_info.expired_left,
                "expired_type": new_share_info.expired_type,
                "extract_code": resource.extract_code or "",
                "view_count": 0
            }

            # 如果需要设为永久模式，清空临时文件标记
            if set_permanent:
                update_data["is_temp_file"] = 0

            update_params = UpdateResourceParam(**update_data)

            # 更新数据库
            await resource_dao.update(db, pk, update_params, updated_by)

            # 记录初始浏览量历史
            if new_share_info.pwd_id:
                try:
                    history_param = CreateResourceViewHistoryParam(
                        pwd_id=new_share_info.pwd_id,
                        view_count=0
                    )
                    await resource_view_history_dao.create(db, history_param)
                except Exception:
                    # 记录浏览量历史失败不影响资源刷新
                    pass

            return {
                "success": True,
                "resource_id": pk,
                "resource_title": resource.title or resource.main_name,
                "old_url": resource.url,
                "new_url": new_share_info.url,
                "new_expired_at": new_share_info.expired_at.isoformat() if new_share_info.expired_at else None
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "resource_id": pk
            }

    @staticmethod
    async def refresh_to_permanent(
        *,
        db: AsyncSession,
        category_id: int,
        updated_by: int | None = None
    ) -> Dict[str, Any]:
        """
        刷新分类资源为永久链接

        :param db: 数据库会话
        :param category_id: 分类ID
        :param updated_by: 更新者 ID
        :return: 执行结果统计
        """
        summary: Dict[str, Any] = {
            "category_id": category_id,
            "checked_resources": 0,
            "refreshed_resources": 0,
            "failed_resources": 0,
            "skipped_resources": 0,
            "details": [],
        }

        try:
            # 取出临时模式为 2 的资源，再根据 category_id 过滤
            resources = await resource_dao.get_resources_by_temp_mode(db, temp_mode=2)
            filtered_resources = [r for r in resources if r.category_id == category_id]
            summary["checked_resources"] = len(filtered_resources)

            if not filtered_resources:
                return summary

            for res in filtered_resources:
                try:
                    # 跳过已删除或停用
                    if res.is_deleted or res.status != 1:
                        summary["skipped_resources"] += 1
                        summary["details"].append({
                            "resource_id": res.id,
                            "status": "skipped",
                            "reason": "资源已删除或停用",
                        })
                        continue

                    # 调用单资源刷新方法，设为永久
                    refresh_result = await ResourceService.refresh_by_id(
                        db=db,
                        pk=res.id,
                        expired_type=0,  # 永久分享
                        set_permanent=True,  # 清空临时模式
                        updated_by=updated_by
                    )

                    if refresh_result.get("success"):
                        summary["refreshed_resources"] += 1
                        summary["details"].append({
                            "resource_id": res.id,
                            "resource_title": refresh_result.get("resource_title"),
                            "status": "success",
                            "old_url": refresh_result.get("old_url"),
                            "new_url": refresh_result.get("new_url"),
                            "new_expired_at": refresh_result.get("new_expired_at"),
                        })
                    else:
                        summary["failed_resources"] += 1
                        summary["details"].append({
                            "resource_id": res.id,
                            "resource_title": res.title or res.main_name,
                            "status": "failed",
                            "reason": refresh_result.get("error"),
                        })

                    # 随机间隔，避免频繁请求
                    wait_time = random.randint(3, 6)
                    await asyncio.sleep(wait_time)

                except Exception as e:
                    summary["failed_resources"] += 1
                    summary["details"].append({
                        "resource_id": res.id,
                        "resource_title": res.title or res.main_name,
                        "status": "error",
                        "error": str(e),
                    })

        except Exception as e:
            summary["error"] = str(e)

        return summary

    @staticmethod
    async def refresh_expiring_resources(
        *,
        db: AsyncSession,
        hours: int = 24,
        expired_type: int = 7,
        updated_by: int | None = None,
        include_expired: bool = True
    ) -> Dict[str, Any]:
        """
        刷新即将过期资源

        :param db: 数据库会话
        :param hours: 过期时间阈值（小时）
        :param expired_type: 重新创建分享的过期天数
        :param updated_by: 更新者 ID
        :param include_expired: 是否包含已过期的资源
        :return: 执行结果统计
        """
        result = {
            "checked_resources": 0,
            "refreshed_resources": 0,
            "failed_resources": 0,
            "skipped_resources": 0,
            "refresh_details": []
        }

        try:
            current_time = datetime.now()

            # 1. 获取24小时内即将过期的资源
            expiring_threshold = current_time + timedelta(hours=hours)
            expiring_resources = await resource_dao.get_expiring_resources(
                db,
                current_time=current_time,
                expiring_threshold=expiring_threshold,
            )

            # 2. 获取已经过期的资源（如果需要）
            expired_resources = []
            if include_expired:
                expired_resources = await resource_dao.get_expired_resources(
                    db,
                    current_time=current_time
                )

            # 合并所有需要处理的资源
            all_resources = []

            # 添加24小时内即将过期的资源
            for resource in expiring_resources:
                if getattr(resource, 'is_temp_file', 0) == 2:
                    resource.expiry_category = "24h_expiring"
                    all_resources.append(resource)

            # 添加已经过期的资源
            for resource in expired_resources:
                if getattr(resource, 'is_temp_file', 0) == 2:
                    resource.expiry_category = "expired"
                    all_resources.append(resource)

            # 按过期时间排序，优先处理已过期的资源
            all_resources.sort(key=lambda x: (x.expired_at or datetime.max, getattr(x, 'expiry_category', '')))

            result["checked_resources"] = len(all_resources)

            for resource in all_resources:
                try:
                    # 跳过永久分享的资源（expired_type = 0）或非定时刷新模式
                    if resource.expired_type == 0 or resource.is_temp_file != 2:
                        result["skipped_resources"] += 1
                        result["refresh_details"].append({
                            "resource_id": resource.id,
                            "status": "skipped",
                            "reason": "非定时刷新模式或永久分享",
                            "expiry_category": getattr(resource, 'expiry_category', 'unknown')
                        })
                        continue

                    # 调用单资源刷新方法
                    expiry_category = getattr(resource, 'expiry_category', '24h_expiring')
                    refresh_result = await ResourceService.refresh_by_id(
                        db=db,
                        pk=resource.id,
                        expired_type=expired_type,
                        updated_by=updated_by
                    )

                    if refresh_result.get("success"):
                        result["refreshed_resources"] += 1
                        log_message = "已过期资源重新分享" if expiry_category == "expired" else "即将过期资源刷新"
                        result["refresh_details"].append({
                            "resource_id": resource.id,
                            "resource_title": refresh_result.get("resource_title"),
                            "status": "success",
                            "old_url": refresh_result.get("old_url"),
                            "new_url": refresh_result.get("new_url"),
                            "new_expired_at": refresh_result.get("new_expired_at"),
                            "expiry_category": expiry_category,
                            "log_message": log_message
                        })
                    else:
                        result["failed_resources"] += 1
                        result["refresh_details"].append({
                            "resource_id": resource.id,
                            "resource_title": resource.title or resource.main_name,
                            "status": "failed",
                            "reason": refresh_result.get("error"),
                            "expiry_category": expiry_category
                        })

                    # 添加随机间隔时间，避免频繁请求
                    wait_time = random.randint(5, 10)
                    await asyncio.sleep(wait_time)

                except Exception as e:
                    result["failed_resources"] += 1
                    result["refresh_details"].append({
                        "resource_id": resource.id,
                        "resource_title": resource.title or resource.main_name,
                        "status": "error",
                        "error": str(e),
                        "expiry_category": getattr(resource, 'expiry_category', 'unknown')
                    })

        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    async def vector_search(
        *,
        db: AsyncSession,
        query_text: str,
        limit: int = 20,
        similarity_threshold: float = 0.7,
        include_content: bool = False,
        category_id: int | None = None
    ) -> list[dict]:
        """
        向量搜索资源

        :param db: 数据库会话
        :param query_text: 搜索查询文本（在资源介绍和描述中搜索）
        :param limit: 返回结果数量限制
        :param similarity_threshold: 相似度阈值
        :param include_content: 是否包含完整内容
        :param category_id: 分类过滤
        :return: 搜索结果列表
        """
        # 如果提供了分类过滤，获取该分类下的所有子分类ID
        category_ids = None
        if category_id is not None:
            category_ids = await category_dao.get_all_children_ids(db, category_id)

        results = await resource_dao.vector_search(
            db,
            query_text,
            limit,
            similarity_threshold,
            category_id=category_id,
            category_ids=category_ids
        )

        # 根据 include_content 参数返回不同格式
        if include_content:
            # AI知识库模式：返回完整内容
            return [
                {
                    "resource": ResourceKnowledgeItem.model_validate(resource),
                    "similarity": similarity,
                    "has_sensitive_words": contains_sensitive_words(resource.resource_intro)
                }
                for resource, similarity in results
            ]
        else:
            # 搜索框模式：返回基础信息
            return [
                {
                    "resource": ResourceListItem.model_validate(resource),
                    "similarity": similarity,
                    "has_sensitive_words": contains_sensitive_words(resource.resource_intro)
                }
                for resource, similarity in results
            ]

    @staticmethod
    async def update_vector(*, db: AsyncSession, pk: int) -> bool:
        """
        更新单个资源的向量

        :param db: 数据库会话
        :param pk: 资源 ID
        :return: 是否更新成功
        """
        return await resource_dao.update_resource_vector(db, pk)

    @staticmethod
    async def batch_update_vectors(*, db: AsyncSession, batch_size: int = 50) -> int:
        """
        批量更新所有资源的向量

        :param db: 数据库会话
        :param batch_size: 每批次处理数量
        :return: 成功更新的数量
        """
        return await resource_dao.batch_update_vectors(db, batch_size)


class ResourceViewHistoryService:
    """资源浏览量历史记录服务类"""

    @staticmethod
    async def create(*, db: AsyncSession, params: CreateResourceViewHistoryParam) -> GetResourceViewHistoryDetail:
        """创建浏览量历史记录"""
        history = await resource_view_history_dao.create(db, params)
        return GetResourceViewHistoryDetail.model_validate(history)

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> ResourceViewHistory:
        """
        获取浏览量历史记录详情

        :param db: 数据库会话
        :param pk: 历史记录 ID
        :return:
        """
        history = await resource_view_history_dao.get(db, pk)
        if not history:
            raise NotFoundError(msg="浏览量历史记录不存在")
        return history

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        params: GetResourceViewHistoryListParam
    ) -> dict:
        """
        获取浏览量历史记录列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        stmt = await resource_view_history_dao.get_list(params)
        return await paging_data(db, stmt)

    @staticmethod
    async def get_by_pwd_id(*, db: AsyncSession, pwd_id: str) -> Sequence[ResourceViewHistory]:
        """
        通过密码 ID 获取浏览量历史记录

        :param db: 数据库会话
        :param pwd_id: 密码 ID
        :return:
        """
        # 检查资源是否存在
        await ResourceService.get_by_pwd_id(db=db, pwd_id=pwd_id)

        return await resource_view_history_dao.get_by_pwd_id(db, pwd_id)

    @staticmethod
    async def get_view_trend(
        *,
        db: AsyncSession,
        params: GetResourceViewTrendParam
    ) -> ResourceViewTrendResponse:
        """
        获取资源浏览量趋势

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        # 检查资源是否存在
        resource = await ResourceService.get_by_pwd_id(db=db, pwd_id=params.pwd_id)

        # 获取趋势数据
        trend_records = await resource_view_history_dao.get_trend_data(
            db, params.pwd_id, params.start_time, params.end_time
        )

        trend_data = [
            ResourceViewTrendData(
                record_time=record.record_time,
                view_count=record.view_count
            )
            for record in trend_records
        ]

        return ResourceViewTrendResponse(
            pwd_id=params.pwd_id,
            current_view_count=resource.view_count,
            trend_data=trend_data
        )

    @staticmethod
    async def update_view_count(
        *,
        db: AsyncSession,
        params: UpdateResourceViewCountParam
    ) -> None:
        """
        更新资源浏览量并记录历史

        :param db: 数据库会话
        :param params: 更新参数
        :return:
        """
        # 检查资源是否存在
        resource = await ResourceService.get_by_pwd_id(db=db, pwd_id=params.pwd_id)

        # 更新浏览量
        count = await resource_dao.update_view_count(db, params.pwd_id, params.view_count - resource.view_count)
        if count == 0:
            raise NotFoundError(msg="更新失败，资源不存在")

        # 记录浏览量历史
        history_param = CreateResourceViewHistoryParam(
            pwd_id=params.pwd_id,
            view_count=params.view_count
        )
        await resource_view_history_dao.create(db, history_param)

    @staticmethod
    async def clean_old(*, db: AsyncSession, days: int = 30) -> int:
        """
        清理旧的浏览量历史记录

        :param db: 数据库会话
        :param days: 保留天数
        :return:
        """
        return await resource_view_history_dao.delete_old_records(db, days)


# 创建服务实例
resource_service = ResourceService()
resource_view_history_service = ResourceViewHistoryService() 