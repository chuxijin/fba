#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mydrive.crud.crud_account import mydrive_account_dao
from backend.app.mydrive.crud.crud_resource import (
    mydrive_resource_dao,
    mydrive_resource_share_dao,
    mydrive_resource_view_history_dao,
)
from backend.app.mydrive.model.resource import MyDriveResource, MyDriveResourceShare, MyDriveResourceViewHistory
from backend.app.mydrive.model.space import MyDriveSpace
from backend.app.mydrive.schema.resource import (
    CreateMyDriveResourceParam,
    GetMyDriveResourceListParam,
    GetMyDriveResourceStatistics,
    GetMyDriveResourceViewTrendParam,
    MyDriveResourceShareParam,
    UpdateMyDriveResourceParam,
)
from backend.app.mydrive.service.filesystem.factory import create_file_space
from backend.app.mydrive.service.filesystem.exceptions import ShareExpiredError
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import ShareableFileSpace
from backend.app.mydrive.service.drives.quark.client import QuarkRequest, QuarkRequestError
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


class MyDriveResourceService:
    """MyDrive 资源服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int, owner_id: int) -> MyDriveResource:
        """
        获取资源。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        resource = await mydrive_resource_dao.get(db, pk, owner_id)
        if resource is None:
            raise errors.NotFoundError(msg='资源不存在')
        return resource

    @staticmethod
    async def get_select(owner_id: int, params: GetMyDriveResourceListParam):
        """获取资源查询语句。"""
        return await mydrive_resource_dao.get_select(owner_id, params)

    @staticmethod
    async def get_list(db: AsyncSession, *, owner_id: int, params: GetMyDriveResourceListParam) -> dict[str, Any]:
        """
        获取资源列表。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param params: 查询参数
        :return:
        """
        stmt = await MyDriveResourceService.get_select(owner_id, params)
        return await paging_data(db, stmt)

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        owner_id: int,
        created_by: int,
        obj: CreateMyDriveResourceParam,
    ) -> MyDriveResource:
        """
        创建资源。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param created_by: 创建者 ID
        :param obj: 创建参数
        :return:
        """
        await MyDriveResourceService._validate_share_refs(db, owner_id, obj.share)
        values = obj.model_dump(exclude={'share'})
        resource = MyDriveResource(owner_id=owner_id, created_by=created_by, **values)
        db.add(resource)
        await db.flush()
        share_values = MyDriveResourceService._normalize_share_values(obj.share)
        share = MyDriveResourceShare(resource_id=resource.id, **share_values)
        db.add(share)
        await db.flush()
        if share.account_id is not None and share.share_url:
            await MyDriveResourceService.refresh_share_info(db, pk=resource.id, owner_id=owner_id)
        return await MyDriveResourceService.get(db, pk=resource.id, owner_id=owner_id)

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        updated_by: int,
        obj: UpdateMyDriveResourceParam,
    ) -> MyDriveResource:
        """
        更新资源。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :param updated_by: 更新者 ID
        :param obj: 更新参数
        :return:
        """
        resource = await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)
        values = obj.model_dump(exclude_unset=True, exclude={'share'})
        if values:
            values['updated_by'] = updated_by
            await mydrive_resource_dao.update_model(db, resource.id, values)
        if obj.share is not None:
            await MyDriveResourceService._validate_share_refs(db, owner_id, obj.share)
            share = await mydrive_resource_share_dao.get_by_resource_id(db, resource.id)
            share_values = MyDriveResourceService._normalize_share_values(obj.share)
            if share is None:
                db.add(MyDriveResourceShare(resource_id=resource.id, **share_values))
            else:
                await mydrive_resource_share_dao.update_model(db, share.id, share_values)
        await db.flush()
        if obj.share is not None and obj.share.account_id is not None and obj.share.share_url:
            await MyDriveResourceService.refresh_share_info(db, pk=resource.id, owner_id=owner_id)
        return await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int, owner_id: int) -> None:
        """
        删除资源。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        resource = await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)
        await mydrive_resource_dao.update_model(
            db,
            resource.id,
            {'deleted': resource.id, 'deleted_time': timezone.now()},
        )

    @staticmethod
    async def record_view(db: AsyncSession, *, pk: int, owner_id: int) -> MyDriveResource:
        """
        记录浏览。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        resource = await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)
        count = await mydrive_resource_dao.increment_view(db, resource.id, owner_id, 1)
        if count == 0:
            raise errors.NotFoundError(msg='资源不存在')
        await db.flush()
        resource = await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)
        db.add(MyDriveResourceViewHistory(resource_id=resource.id, view_count=resource.view_count, record_time=timezone.now()))
        await db.flush()
        return resource

    @staticmethod
    async def record_search_click(db: AsyncSession, *, pk: int, owner_id: int) -> MyDriveResource:
        """
        记录搜索点击。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        resource = await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)
        count = await mydrive_resource_dao.increment_search(db, resource.id, owner_id, 1)
        if count == 0:
            raise errors.NotFoundError(msg='资源不存在')
        await db.flush()
        return await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)

    @staticmethod
    async def get_view_trend(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        params: GetMyDriveResourceViewTrendParam,
    ) -> dict[str, Any]:
        """
        获取浏览趋势。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :param params: 查询参数
        :return:
        """
        resource = await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)
        stmt = await mydrive_resource_view_history_dao.get_select(resource.id, params.start_time, params.end_time)
        return await paging_data(db, stmt)

    @staticmethod
    async def get_statistics(db: AsyncSession, *, owner_id: int) -> GetMyDriveResourceStatistics:
        """
        获取资源统计。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :return:
        """
        return GetMyDriveResourceStatistics(**await mydrive_resource_dao.get_statistics(db, owner_id))

    @staticmethod
    async def refresh_share_info(db: AsyncSession, *, pk: int, owner_id: int) -> MyDriveResource:
        """
        刷新资源分享信息。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        resource = await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)
        share = await MyDriveResourceService._get_share_or_error(db, resource.id)
        if share.share_id or share.share_key:
            current_share = await MyDriveResourceService._get_personal_share(db, resource, share)
            if current_share is not None:
                await MyDriveResourceService._update_share_from_link(db, share, current_share)
                await mydrive_resource_share_dao.update_model(db, share.id, {'source_type': 'local_share'})
                await db.flush()
                return await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)
        await MyDriveResourceService._parse_imported_share(db, resource, share)
        await db.flush()
        return await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)

    @staticmethod
    async def rebuild_share(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        expires_in_days: int | None = None,
    ) -> MyDriveResource:
        """
        根据文件 ID 重新创建分享。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :param expires_in_days: 新分享有效期天数，为空时沿用当前设置
        :return:
        """
        resource = await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)
        share = await MyDriveResourceService._get_share_or_error(db, resource.id)
        if not share.file_id:
            raise errors.ForbiddenError(msg='缺少文件 ID，无法重新创建分享')
        new_share = await MyDriveResourceService._create_personal_share(
            db,
            resource,
            share,
            expires_in_days=share.expires_in_days if expires_in_days is None else expires_in_days,
        )
        values = MyDriveResourceService._share_link_to_values(new_share)
        values['extract_code'] = share.extract_code or values['extract_code']
        values['source_type'] = 'local_share'
        await mydrive_resource_share_dao.update_model(db, share.id, values)
        await db.flush()
        return await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)

    @staticmethod
    async def cancel_share(db: AsyncSession, *, pk: int, owner_id: int) -> MyDriveResource:
        """
        取消资源关联的个人分享链接。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        resource = await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)
        share = await MyDriveResourceService._get_share_or_error(db, resource.id)
        if not share.share_id:
            raise errors.ForbiddenError(msg='缺少本地分享 ID，请先刷新分享信息')
        file_space = await MyDriveResourceService._create_personal_file_space(db, resource, share)
        try:
            if not isinstance(file_space, ShareableFileSpace):
                raise errors.ForbiddenError(msg='当前网盘不支持取消分享链接')
            try:
                await file_space.cancel_shares([share.share_id])
            except QuarkRequestError as exc:
                raise errors.ForbiddenError(msg=str(exc)) from exc
        finally:
            await file_space.aclose()
        await mydrive_resource_share_dao.update_model(
            db,
            share.id,
            {'share_status': 'cancelled', 'share_expired_at': timezone.now(), 'source_type': 'local_share'},
        )
        await db.flush()
        return await MyDriveResourceService.get(db, pk=pk, owner_id=owner_id)

    @staticmethod
    async def process_temp_policy_resources(db: AsyncSession) -> dict[str, Any]:
        """处理资源临时策略。"""
        expiration_result = await MyDriveResourceService.process_expired_resource_policies(db)
        refresh_result = await MyDriveResourceService.refresh_scheduled_resource_shares(db)
        return {
            'checked': expiration_result['checked'] + refresh_result['checked'],
            'deleted': expiration_result['deleted'],
            'failed': expiration_result['failed'] + refresh_result['failed'],
            'rebuilt': expiration_result['rebuilt'],
            'refreshed': refresh_result['refreshed'],
            'details': expiration_result['details'] + refresh_result['details'],
        }

    @staticmethod
    async def process_expired_resource_policies(db: AsyncSession) -> dict[str, Any]:
        """处理到期资源的删除和七天刷新策略。"""
        result: dict[str, Any] = {'checked': 0, 'deleted': 0, 'rebuilt': 0, 'failed': 0, 'details': []}
        current_time = timezone.now()
        for policy in [1, 2]:
            resources = await mydrive_resource_dao.list_by_temp_policy(db, policy)
            result['checked'] += len(resources)
            for resource in resources:
                try:
                    share = await MyDriveResourceService._get_share_or_error(db, resource.id)
                    if policy == 1:
                        if share.share_expired_at is None or share.share_expired_at > current_time:
                            continue
                        await mydrive_resource_dao.update_model(
                            db,
                            resource.id,
                            {'deleted': resource.id, 'deleted_time': current_time},
                        )
                        result['deleted'] += 1
                        continue
                    refresh_deadline = current_time + timedelta(hours=24)
                    if share.share_expired_at is None or share.share_expired_at > refresh_deadline:
                        continue
                    await MyDriveResourceService.rebuild_share(
                        db,
                        pk=resource.id,
                        owner_id=resource.owner_id,
                        expires_in_days=7,
                    )
                    result['rebuilt'] += 1
                except Exception as exc:
                    result['failed'] += 1
                    result['details'].append({'resource_id': resource.id, 'error': str(exc)})
        return result

    @staticmethod
    async def refresh_scheduled_resource_shares(db: AsyncSession) -> dict[str, Any]:
        """刷新定时更新策略的资源分享信息。"""
        result: dict[str, Any] = {'checked': 0, 'refreshed': 0, 'failed': 0, 'details': []}
        resources = await mydrive_resource_dao.list_by_temp_policy(db, 3)
        result['checked'] = len(resources)
        for resource in resources:
            try:
                await MyDriveResourceService.refresh_share_info(db, pk=resource.id, owner_id=resource.owner_id)
                result['refreshed'] += 1
            except Exception as exc:
                result['failed'] += 1
                result['details'].append({'resource_id': resource.id, 'error': str(exc)})
        return result

    @staticmethod
    async def _validate_share_refs(db: AsyncSession, owner_id: int, share: MyDriveResourceShareParam) -> None:
        """
        验证分享关联对象。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param share: 分享参数
        :return:
        """
        if share.account_id is not None and await mydrive_account_dao.get(db, share.account_id, owner_id) is None:
            raise errors.NotFoundError(msg='关联网盘账户不存在')

    @staticmethod
    def _normalize_share_values(share: MyDriveResourceShareParam) -> dict[str, Any]:
        """
        规范化分享入库值。

        :param share: 分享参数
        :return:
        """
        values = share.model_dump()
        if share.provider != 'quark':
            return values
        raw_share_id = share.share_key or share.share_url or share.share_id
        try:
            share_id = QuarkRequest.normalize_share_id(raw_share_id)
        except QuarkRequestError as exc:
            raise errors.ForbiddenError(msg=str(exc)) from exc
        values['share_id'] = ''
        values['share_key'] = share_id
        values['source_ref'] = {'share_id': share_id, 'passcode': share.extract_code}
        return values

    @staticmethod
    async def _get_share_or_error(db: AsyncSession, resource_id: int) -> MyDriveResourceShare:
        """获取资源分享记录。"""
        share = await mydrive_resource_share_dao.get_by_resource_id(db, resource_id)
        if share is None:
            raise errors.NotFoundError(msg='资源分享信息不存在')
        return share

    @staticmethod
    async def _parse_imported_share(db: AsyncSession, resource: MyDriveResource, share: MyDriveResourceShare) -> None:
        """解析导入分享链接的根目录信息。"""
        if share.account_id is None:
            raise errors.ForbiddenError(msg='缺少关联网盘账户，无法解析分享链接')
        account = await mydrive_account_dao.get(db, share.account_id, resource.owner_id)
        if account is None:
            raise errors.NotFoundError(msg='关联网盘账户不存在')

        source_ref = MyDriveResourceService._build_share_source_ref(share)
        temporary_space = MyDriveSpace(
            account_id=account.id,
            capabilities=[],
            name='resource-preview',
            owner_id=resource.owner_id,
            provider=share.provider,
            root_id=None,
            root_path='/',
            source_key=share.share_url,
            source_ref=source_ref,
            space_type=SpaceType.SHARE_LINK.value,
        )
        file_space = await create_file_space(db, temporary_space)
        try:
            try:
                items = await file_space.list(None)
            except ShareExpiredError as exc:
                await mydrive_resource_share_dao.update_model(
                    db,
                    share.id,
                    {'share_status': 'expired', 'share_meta': {'parse_error': str(exc)}},
                )
                log.info('MyDrive 资源分享已过期 resource_id={} provider={}', resource.id, share.provider)
                return
            except QuarkRequestError as exc:
                raise errors.ForbiddenError(msg=str(exc)) from exc
            first = items[0] if items else None
            values: dict[str, Any] = {
                'share_status': 'active',
                'share_title': share.share_title or resource.title,
            }
            local_share = await MyDriveResourceService._get_personal_share(db, resource, share)
            if local_share is not None:
                values.update(MyDriveResourceService._share_link_to_values(local_share))
                values['source_type'] = 'local_share'
            if first is not None:
                values.update({
                    'file_id': first.file_id,
                    'file_name': first.name,
                    'file_path': first.path,
                    'file_size': first.size,
                    'is_directory': first.is_directory,
                    'share_meta': {'root_files': [MyDriveResourceService._file_to_dict(item) for item in items[:20]]},
                })
            await mydrive_resource_share_dao.update_model(db, share.id, values)
        finally:
            await file_space.aclose()

    @staticmethod
    async def _get_personal_share(
        db: AsyncSession, resource: MyDriveResource, share: MyDriveResourceShare
    ) -> Any | None:
        """从个人分享列表获取分享详情。"""
        if share.account_id is None:
            return None
        file_space = await MyDriveResourceService._create_personal_file_space(db, resource, share)
        try:
            if not isinstance(file_space, ShareableFileSpace):
                return None
            return await file_space.get_share(share.share_id or share.share_key)
        finally:
            await file_space.aclose()

    @staticmethod
    async def _create_personal_share(
        db: AsyncSession,
        resource: MyDriveResource,
        share: MyDriveResourceShare,
        *,
        expires_in_days: int,
    ) -> Any:
        """
        创建个人盘分享。

        :param db: 数据库会话
        :param resource: 资源记录
        :param share: 分享记录
        :param expires_in_days: 分享有效期天数
        :return:
        """
        file_space = await MyDriveResourceService._create_personal_file_space(db, resource, share)
        try:
            if not isinstance(file_space, ShareableFileSpace):
                raise errors.ForbiddenError(msg='当前网盘不支持创建分享')
            file = FileObject(
                space=SpaceLocator(provider=share.provider, space_type=SpaceType.PERSONAL, account_id=str(share.account_id)),
                file_id=share.file_id,
                name=share.file_name or resource.title,
                path=share.file_path or '/',
                is_directory=share.is_directory,
                size=share.file_size,
            )
            return await file_space.create_share([file], share.share_title or resource.title, expires_in_days, share.extract_code)
        finally:
            await file_space.aclose()

    @staticmethod
    async def _create_personal_file_space(db: AsyncSession, resource: MyDriveResource, share: MyDriveResourceShare) -> Any:
        """创建个人文件空间实例。"""
        if share.account_id is None:
            raise errors.ForbiddenError(msg='缺少关联网盘账户')
        account = await mydrive_account_dao.get(db, share.account_id, resource.owner_id)
        if account is None:
            raise errors.NotFoundError(msg='关联网盘账户不存在')
        temporary_space = MyDriveSpace(
            account_id=account.id,
            capabilities=[],
            name='resource-personal',
            owner_id=resource.owner_id,
            provider=share.provider,
            root_id='0' if share.provider == 'quark' else None,
            root_path='/',
            source_key=f'account:{account.id}',
            source_ref={},
            space_type=SpaceType.PERSONAL.value,
        )
        return await create_file_space(db, temporary_space)

    @staticmethod
    async def _update_share_from_link(db: AsyncSession, share: MyDriveResourceShare, link: Any) -> None:
        """使用分享链接对象更新分享记录。"""
        values = MyDriveResourceService._share_link_to_values(link)
        if share.provider == 'quark' and share.share_key:
            values['share_key'] = share.share_key
        await mydrive_resource_share_dao.update_model(db, share.id, values)

    @staticmethod
    def _share_link_to_values(link: Any) -> dict[str, Any]:
        """转换分享链接对象。"""
        return {
            'share_url': link.url,
            'share_id': link.share_id,
            'share_key': MyDriveResourceService._get_share_key(link),
            'extract_code': link.password,
            'share_title': link.title,
            'share_status': 'active',
            'share_expired_at': link.expired_at,
            'expires_in_days': link.expires_in_days,
        }

    @staticmethod
    def _build_share_source_ref(share: MyDriveResourceShare) -> dict[str, Any]:
        """构造分享空间 source_ref。"""
        if share.provider == 'quark':
            raw_share_id = share.share_key or share.share_url or share.share_id
            try:
                share_id = QuarkRequest.normalize_share_id(raw_share_id)
            except QuarkRequestError as exc:
                raise errors.ForbiddenError(msg=str(exc)) from exc
            source_ref = {'share_id': share_id, 'passcode': share.extract_code}
            return source_ref
        if share.provider == 'baidu':
            return {'url': share.share_url, 'passcode': share.extract_code}
        raise errors.ForbiddenError(msg=f'暂不支持解析 {share.provider} 分享链接')

    @staticmethod
    def _get_share_key(link: Any) -> str:
        """获取分享外链标识。"""
        if link.provider == 'quark':
            return QuarkRequest.normalize_share_id(link.url)
        return link.share_id

    @staticmethod
    def _file_to_dict(file: FileObject) -> dict[str, Any]:
        """转换文件快照。"""
        return {
            'file_id': file.file_id,
            'name': file.name,
            'path': file.path,
            'is_directory': file.is_directory,
            'size': file.size,
        }


mydrive_resource_service: MyDriveResourceService = MyDriveResourceService()
