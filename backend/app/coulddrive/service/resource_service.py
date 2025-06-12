#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_resource import resource_dao, resource_view_history_dao
from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
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
    GetResourceViewTrendParam
)
from backend.app.coulddrive.schema.file import ListShareInfoParam
from backend.app.coulddrive.service.yp_service import get_drive_manager
from backend.common.exception.errors import NotFoundError, ForbiddenError
from backend.common.pagination import paging_data, paging_list_data, _CustomPageParams


class ResourceService:
    """资源服务类"""

    @staticmethod
    async def get_resource_detail(db: AsyncSession, resource_id: int) -> GetResourceDetail:
        """
        获取资源详情

        :param db: 数据库会话
        :param resource_id: 资源ID
        :return:
        """
        resource = await resource_dao.get(db, resource_id)
        if not resource:
            raise NotFoundError(msg="资源不存在")
        return GetResourceDetail.model_validate(resource)

    @staticmethod
    async def get_resource(db: AsyncSession, resource_id: int) -> Resource:
        """
        获取资源详情

        :param db: 数据库会话
        :param resource_id: 资源ID
        :return:
        """
        resource = await resource_dao.get(db, resource_id)
        if not resource:
            raise NotFoundError(msg="资源不存在")
        return resource

    @staticmethod
    async def get_resource_by_pwd_id(db: AsyncSession, pwd_id: str) -> Resource:
        """
        通过密码ID获取资源详情

        :param db: 数据库会话
        :param pwd_id: 密码ID
        :return:
        """
        resource = await resource_dao.get_by_pwd_id(db, pwd_id)
        if not resource:
            raise NotFoundError(msg="资源不存在")
        return resource

    @staticmethod
    async def get_resource_by_share_id(db: AsyncSession, share_id: str) -> Resource:
        """
        通过分享ID获取资源详情

        :param db: 数据库会话
        :param share_id: 分享ID
        :return:
        """
        resource = await resource_dao.get_by_share_id(db, share_id)
        if not resource:
            raise NotFoundError(msg="资源不存在")
        return resource

    @staticmethod
    async def get_resource_list(
        db: AsyncSession, 
        params: GetResourceListParam
    ) -> dict:
        """
        获取资源列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        stmt = await resource_dao.get_list(params)
        return await paging_data(db, stmt)

    @staticmethod
    async def create_resource(db: AsyncSession, obj: CreateResourceParam, created_by: int) -> GetResourceDetail:
        """
        创建资源

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        # 检查用户是否存在
        user = await drive_account_dao.get(db, obj.user_id)
        if not user:
            raise NotFoundError(msg="网盘用户不存在")

        try:
            # 调用 yp_service 获取分享信息
            drive_manager = get_drive_manager()
            share_info_params = ListShareInfoParam(
                drive_type=user.type,
                source_type="link",
                source_id=obj.url,
                page=1,
                size=1
            )
            
            # 获取分享信息
            share_info_list = await drive_manager.get_share_info(
                user.cookies, 
                share_info_params
            )
            
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
            resource_data.update(share_data)
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
                    "domain", "subject", "main_name", "resource_type", "description", 
                    "resource_intro", "resource_image", "url", "url_type", "extract_code",
                    "is_temp_file", "price", "suggested_price", "sort", "remark",
                    "title", "share_id", "pwd_id", "expired_type", "view_count",
                    "expired_at", "expired_left", "audit_status", "status",
                    "file_only_num", "file_size", "path_info", "file_id", "content", "uk_uid"
                }
                
                for field in allowed_update_fields:
                    if field in resource_data:
                        update_data[field] = resource_data[field]
                
                update_param = UpdateResourceParam(**update_data)
                await resource_dao.update(db, existing_resource.id, update_param, created_by)
                
                # 重新获取更新后的资源
                updated_resource = await resource_dao.get(db, existing_resource.id)
                return GetResourceDetail.model_validate(updated_resource)

        # 检查分享ID是否已存在，如果存在则更新现有记录
        if resource_data.get("share_id"):
            existing_resource = await resource_dao.get_by_share_id(db, resource_data["share_id"])
            if existing_resource:
                # 更新现有记录 - 只更新允许的字段
                update_data = {}
                allowed_update_fields = {
                    "domain", "subject", "main_name", "resource_type", "description", 
                    "resource_intro", "resource_image", "url", "url_type", "extract_code",
                    "is_temp_file", "price", "suggested_price", "sort", "remark",
                    "title", "share_id", "pwd_id", "expired_type", "view_count",
                    "expired_at", "expired_left", "audit_status", "status",
                    "file_only_num", "file_size", "path_info", "file_id", "content", "uk_uid"
                }
                
                for field in allowed_update_fields:
                    if field in resource_data:
                        update_data[field] = resource_data[field]
                
                update_param = UpdateResourceParam(**update_data)
                await resource_dao.update(db, existing_resource.id, update_param, created_by)
                
                # 重新获取更新后的资源
                updated_resource = await resource_dao.get(db, existing_resource.id)
                return GetResourceDetail.model_validate(updated_resource)

        # 创建新的资源记录
        resource = Resource(**resource_data)
        db.add(resource)
        await db.commit()
        await db.refresh(resource)
        
        return GetResourceDetail.model_validate(resource)

    @staticmethod
    async def update_resource(
        db: AsyncSession, 
        resource_id: int, 
        obj: UpdateResourceParam, 
        updated_by: int,
        auto_refresh: bool = False
    ) -> GetResourceDetail:
        """
        更新资源

        :param db: 数据库会话
        :param resource_id: 资源ID
        :param obj: 更新参数
        :param updated_by: 更新者ID
        :param auto_refresh: 是否自动刷新分享信息
        :return:
        """
        # 检查资源是否存在
        resource = await resource_dao.get(db, resource_id)
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
                    # 调用 yp_service 获取最新分享信息
                    drive_manager = get_drive_manager()
                    share_info_params = ListShareInfoParam(
                        drive_type=user.type,
                        source_type="link",
                        source_id=resource.url,
                        page=1,
                        size=1
                    )
                    
                    # 获取分享信息
                    share_info_list = await drive_manager.get_share_info(
                        user.cookies, 
                        share_info_params
                    )
                    
                    # 如果获取到分享信息，更新相关字段
                    if share_info_list:
                        share_info = share_info_list[0]
                        share_data = share_info.model_dump()
                        # 只更新分享相关的字段，不覆盖用户手动输入的字段
                        share_fields = {
                            "title", "share_id", "pwd_id", "expired_type", "view_count",
                            "expired_at", "expired_left", "audit_status", "status",
                            "file_only_num", "file_size", "path_info"
                        }
                        for field in share_fields:
                            if field in share_data:
                                update_data[field] = share_data[field]
                        
            except Exception as e:
                # 如果获取分享信息失败，继续执行更新操作
                pass

        # 执行更新
        update_param = UpdateResourceParam(**update_data)
        await resource_dao.update(db, resource_id, update_param, updated_by)
        
        # 重新获取更新后的资源
        updated_resource = await resource_dao.get(db, resource_id)
        if not updated_resource:
            raise NotFoundError(msg="更新后获取资源失败")
            
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
        
        # 调用网盘API获取分享信息
        drive_manager = get_drive_manager()
        share_info_params = ListShareInfoParam(
            drive_type=user.type,
            source_type="link",
            source_id=resource.url,
            page=1,
            size=1
        )
        
        # 获取分享信息
        share_info_list = await drive_manager.get_share_info(
            user.cookies, 
            share_info_params
        )
        
        if not share_info_list:
            raise NotFoundError(msg="未获取到分享信息")
        
        share_info = share_info_list[0]
        
        # 检查哪些字段需要更新
        update_fields = {}
        share_data = share_info.model_dump()
        
        for field in ['view_count', 'expired_left', 'file_size', 'expired_at', 'path_info', 'expired_type', 'file_only_num']:
            if hasattr(resource, field):
                old_value = getattr(resource, field)
                new_value = share_data.get(field)
                
                if new_value is not None and old_value != new_value:
                    update_fields[field] = new_value
        
        # 如果有字段需要更新，执行更新
        if update_fields:
            update_param = UpdateResourceParam(**update_fields)
            await resource_dao.update(db, resource_id, update_param, updated_by)
        
        # 返回更新后的资源详情
        return await ResourceService.get_resource_detail(db, resource_id)

    @staticmethod
    async def delete_resource(db: AsyncSession, resource_id: int, deleted_by: int) -> None:
        """
        删除资源

        :param db: 数据库会话
        :param resource_id: 资源ID
        :param deleted_by: 删除者ID
        :return:
        """
        resource = await ResourceService.get_resource(db, resource_id)
        
        count = await resource_dao.delete(db, [resource_id])
        if count == 0:
            raise NotFoundError(msg="删除失败，资源不存在")

    @staticmethod
    async def delete_resources(db: AsyncSession, resource_ids: list[int]) -> None:
        """
        批量删除资源

        :param db: 数据库会话
        :param resource_ids: 资源ID列表
        :return:
        """
        # 检查资源是否存在
        for resource_id in resource_ids:
            await ResourceService.get_resource(db, resource_id)
        
        count = await resource_dao.delete(db, resource_ids)
        if count == 0:
            raise NotFoundError(msg="删除失败，资源不存在")

    @staticmethod
    async def soft_delete_resource(db: AsyncSession, resource_id: int) -> None:
        """
        软删除资源

        :param db: 数据库会话
        :param resource_id: 资源ID
        :return:
        """
        resource = await ResourceService.get_resource(db, resource_id)
        
        count = await resource_dao.soft_delete(db, [resource_id])
        if count == 0:
            raise NotFoundError(msg="删除失败，资源不存在")

    @staticmethod
    async def soft_delete_resources(db: AsyncSession, resource_ids: list[int]) -> None:
        """
        批量软删除资源

        :param db: 数据库会话
        :param resource_ids: 资源ID列表
        :return:
        """
        # 检查资源是否存在
        for resource_id in resource_ids:
            await ResourceService.get_resource(db, resource_id)
        
        count = await resource_dao.soft_delete(db, resource_ids)
        if count == 0:
            raise NotFoundError(msg="删除失败，资源不存在")

    @staticmethod
    async def update_resource_view_count(db: AsyncSession, pwd_id: str, increment: int = 1) -> None:
        """
        更新资源浏览量

        :param db: 数据库会话
        :param pwd_id: 密码ID
        :param increment: 增量
        :return:
        """
        resource = await ResourceService.get_resource_by_pwd_id(db, pwd_id)
        
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
    async def update_resource_audit_status(db: AsyncSession, resource_id: int, audit_status: int) -> None:
        """
        更新资源审核状态

        :param db: 数据库会话
        :param resource_id: 资源ID
        :param audit_status: 审核状态
        :return:
        """
        resource = await ResourceService.get_resource(db, resource_id)
        
        count = await resource_dao.update_audit_status(db, resource_id, audit_status)
        if count == 0:
            raise NotFoundError(msg="更新失败，资源不存在")

    @staticmethod
    async def update_resource_status(db: AsyncSession, resource_id: int, status: int) -> None:
        """
        更新资源状态

        :param db: 数据库会话
        :param resource_id: 资源ID
        :param status: 状态
        :return:
        """
        resource = await ResourceService.get_resource(db, resource_id)
        
        count = await resource_dao.update_status(db, resource_id, status)
        if count == 0:
            raise NotFoundError(msg="更新失败，资源不存在")

    @staticmethod
    async def get_resource_statistics(db: AsyncSession, user_id: int | None = None) -> ResourceStatistics:
        """
        获取资源统计信息

        :param db: 数据库会话
        :param user_id: 用户ID
        :return:
        """
        stats = await resource_dao.get_statistics(db, user_id)
        return ResourceStatistics(**stats)

    @staticmethod
    async def get_resources_by_user_id(db: AsyncSession, user_id: int) -> Sequence[Resource]:
        """
        通过用户ID获取资源列表

        :param db: 数据库会话
        :param user_id: 用户ID
        :return:
        """
        # 检查用户是否存在
        user = await drive_account_dao.get(db, user_id)
        if not user:
            raise NotFoundError(msg="网盘用户不存在")

        return await resource_dao.get_by_user_id(db, user_id)


class ResourceViewHistoryService:
    """资源浏览量历史记录服务类"""

    @staticmethod
    async def create_view_history(db: AsyncSession, params: CreateResourceViewHistoryParam) -> GetResourceViewHistoryDetail:
        """
        创建浏览量历史记录

        :param db: 数据库会话
        :param params: 创建参数
        :return:
        """
        history = await resource_view_history_dao.create(db, params)
        return GetResourceViewHistoryDetail.model_validate(history)

    @staticmethod
    async def get_view_history(db: AsyncSession, history_id: int) -> ResourceViewHistory:
        """
        获取浏览量历史记录详情

        :param db: 数据库会话
        :param history_id: 历史记录ID
        :return:
        """
        history = await resource_view_history_dao.get(db, history_id)
        if not history:
            raise NotFoundError(msg="浏览量历史记录不存在")
        return history

    @staticmethod
    async def get_view_history_list(
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
    async def get_view_history_by_pwd_id(db: AsyncSession, pwd_id: str) -> Sequence[ResourceViewHistory]:
        """
        通过密码ID获取浏览量历史记录

        :param db: 数据库会话
        :param pwd_id: 密码ID
        :return:
        """
        # 检查资源是否存在
        await ResourceService.get_resource_by_pwd_id(db, pwd_id)
        
        return await resource_view_history_dao.get_by_pwd_id(db, pwd_id)

    @staticmethod
    async def get_view_trend(
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
        resource = await ResourceService.get_resource_by_pwd_id(db, params.pwd_id)
        
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
        resource = await ResourceService.get_resource_by_pwd_id(db, params.pwd_id)
        
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
    async def clean_old_view_history(db: AsyncSession, days: int = 30) -> int:
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