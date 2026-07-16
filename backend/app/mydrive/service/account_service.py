#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mydrive.service.drives.baidu.profile import get_baidu_profile
from backend.app.mydrive.service.drives.baidu.client import BaiduRequestError
from backend.app.mydrive.crud.crud_account import mydrive_account_dao
from backend.app.mydrive.model.account import MyDriveAccount
from backend.app.mydrive.service.drives.baidu.personal_space import BaiduPersonalSpace
from backend.app.mydrive.service.filesystem.models import FileObject
from backend.app.mydrive.schema.account import CreateMyDriveAccountParam, UpdateMyDriveAccountParam
from backend.app.mydrive.service.drives.quark.client import QuarkRequestError
from backend.app.mydrive.service.drives.quark.personal_space import QuarkPersonalSpace
from backend.app.mydrive.service.drives.quark.profile import get_quark_profile
from backend.app.mydrive.service.drives.thunder.personal_space import ThunderPersonalSpace
from backend.app.mydrive.service.drives.thunder.client import ThunderRequestError
from backend.app.mydrive.service.drives.thunder.profile import get_thunder_profile
from backend.common.exception import errors
from backend.utils.timezone import timezone


class MyDriveAccountService:
    """网盘账户服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int, owner_id: int) -> MyDriveAccount:
        """
        获取网盘账户。

        :param db: 数据库会话
        :param pk: 账户 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        account = await mydrive_account_dao.get(db, pk, owner_id)
        if account is None:
            raise errors.NotFoundError(msg='网盘账户不存在')
        return account

    @staticmethod
    async def get_select(*, owner_id: int, provider: str | None = None) -> Select:
        """
        获取网盘账户查询语句。

        :param owner_id: 所属用户 ID
        :param provider: 网盘驱动标识
        :return:
        """
        return await mydrive_account_dao.get_select(owner_id, provider)

    @staticmethod
    async def create(db: AsyncSession, *, owner_id: int, obj: CreateMyDriveAccountParam) -> MyDriveAccount:
        """
        创建网盘账户。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param obj: 创建参数
        :return:
        """
        profile = await MyDriveAccountService._fetch_profile(obj.provider, obj.credential)
        if not profile.external_account_id:
            raise errors.ForbiddenError(msg='未能获取网盘账户资料，请检查 Cookie 是否有效')

        credential = profile.credential if obj.provider == 'thunder' else obj.credential
        existing = await mydrive_account_dao.get_by_external_id(
            db,
            owner_id,
            obj.provider,
            profile.external_account_id,
        )
        if existing is not None:
            raise errors.ConflictError(msg='网盘账户已存在')
        account = MyDriveAccount(
            owner_id=owner_id,
            provider=obj.provider,
            external_account_id=profile.external_account_id,
            display_name=obj.display_name or profile.username or profile.external_account_id,
            credential=credential,
            credential_expires_at=obj.credential_expires_at,
            username=profile.username,
            avatar_url=profile.avatar_url,
            quota=profile.quota,
            used=profile.used,
            vip_level=profile.vip_level,
            status='active',
            last_verified_at=timezone.now(),
            last_profile_synced_at=timezone.now(),
        )
        db.add(account)
        await db.flush()
        return account

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        obj: UpdateMyDriveAccountParam,
    ) -> int:
        """
        更新网盘账户。

        :param db: 数据库会话
        :param pk: 账户 ID
        :param owner_id: 所属用户 ID
        :param obj: 更新参数
        :return:
        """
        account = await MyDriveAccountService.get(db, pk=pk, owner_id=owner_id)
        return await mydrive_account_dao.update_model(db, account.id, obj)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int, owner_id: int) -> int:
        """
        删除网盘账户。

        :param db: 数据库会话
        :param pk: 账户 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        account = await MyDriveAccountService.get(db, pk=pk, owner_id=owner_id)
        return await mydrive_account_dao.delete_model(db, account.id)

    @staticmethod
    async def list_personal_files(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        path: str,
        file_id: str | None,
        page: int,
        per_page: int,
    ) -> dict:
        """
        预览账户个人空间目录。

        :param db: 数据库会话
        :param pk: 账户 ID
        :param owner_id: 所属用户 ID
        :param path: 目录路径
        :param page: 页码
        :param per_page: 每页数量
        :return:
        """
        account = await MyDriveAccountService.get(db, pk=pk, owner_id=owner_id)
        file_space = MyDriveAccountService._create_personal_space(account)
        try:
            directory = MyDriveAccountService._resolve_preview_directory(path, file_id)
            files = await file_space.list(directory)
            return MyDriveAccountService._paginate_files(files, path, page, per_page)
        finally:
            await file_space.aclose()

    @staticmethod
    async def sync_profile(db: AsyncSession, *, pk: int, owner_id: int) -> MyDriveAccount:
        """
        同步网盘账户资料。

        :param db: 数据库会话
        :param pk: 账户 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        account = await MyDriveAccountService.get(db, pk=pk, owner_id=owner_id)
        profile = await MyDriveAccountService._fetch_profile(account.provider, account.credential)
        return await MyDriveAccountService._save_profile(db, account, profile)

    @staticmethod
    async def sync_active_profiles(db: AsyncSession) -> dict[str, object]:
        """
        同步所有活跃网盘账户资料。

        :param db: 数据库会话
        :return:
        """
        result: dict[str, object] = {
            'checked_accounts': 0,
            'refreshed_accounts': 0,
            'failed_accounts': 0,
            'details': [],
        }
        accounts = await mydrive_account_dao.list_active_accounts(db)
        result['checked_accounts'] = len(accounts)
        details: list[dict[str, object]] = []

        for account in accounts:
            try:
                profile = await MyDriveAccountService._fetch_profile(account.provider, account.credential)
                await MyDriveAccountService._save_profile(db, account, profile)
                result['refreshed_accounts'] = int(result['refreshed_accounts']) + 1
                details.append({'account_id': account.id, 'provider': account.provider, 'status': 'success'})
            except Exception as exc:
                result['failed_accounts'] = int(result['failed_accounts']) + 1
                details.append({
                    'account_id': account.id,
                    'provider': account.provider,
                    'status': 'failed',
                    'reason': str(exc),
                })
        result['details'] = details
        return result

    @staticmethod
    async def _fetch_profile(provider: str, credential: dict):
        """
        获取网盘账户资料。

        :param provider: 网盘驱动标识
        :param credential: 账户凭证
        :return:
        """
        if provider == 'thunder':
            try:
                return await get_thunder_profile(credential)
            except ThunderRequestError as exc:
                raise errors.ForbiddenError(msg=str(exc)) from exc

        cookie = str(credential.get('cookie') or '').strip()
        if not cookie:
            raise errors.ForbiddenError(msg='网盘账户缺少 Cookie 凭证')

        if provider == 'quark':
            try:
                profile = await get_quark_profile(cookie)
            except QuarkRequestError as exc:
                raise errors.ForbiddenError(msg=str(exc)) from exc
        elif provider == 'baidu':
            try:
                profile = await get_baidu_profile(cookie)
            except BaiduRequestError as exc:
                raise errors.ForbiddenError(msg=str(exc)) from exc
        else:
            raise errors.ForbiddenError(msg=f'暂不支持同步 {provider} 账户资料')
        return profile

    @staticmethod
    def _create_personal_space(account: MyDriveAccount):
        """创建个人空间预览实例。"""
        if account.provider == 'baidu':
            cookie = str(account.credential.get('cookie') or '').strip()
            if not cookie:
                raise errors.ForbiddenError(msg='网盘账户缺少 Cookie 凭证')
            return BaiduPersonalSpace(account_id=account.id, cookie=cookie, root_path='/')
        if account.provider == 'quark':
            cookie = str(account.credential.get('cookie') or '').strip()
            if not cookie:
                raise errors.ForbiddenError(msg='网盘账户缺少 Cookie 凭证')
            return QuarkPersonalSpace(account_id=account.id, cookie=cookie, root_id='0', root_path='/')
        if account.provider == 'thunder':
            return ThunderPersonalSpace(account_id=account.id, credential=account.credential, root_id='', root_path='/')
        raise errors.ForbiddenError(msg=f'暂不支持 {account.provider} 个人空间预览')

    @staticmethod
    def _resolve_preview_directory(path: str, file_id: str | None) -> FileObject | None:
        """构造预览目录对象。"""
        normalized_path = '/' + path.strip('/')
        if normalized_path == '/':
            return None
        return FileObject(
            space=None,
            file_id=file_id or normalized_path,
            name=normalized_path.rsplit('/', 1)[-1],
            path=normalized_path,
            is_directory=True,
        )

    @staticmethod
    def _paginate_files(files: list[FileObject], path: str, page: int, per_page: int) -> dict:
        """分页序列化文件列表。"""
        start = (page - 1) * per_page
        items = files[start:start + per_page]
        return {
            'items': items,
            'total': len(files),
            'page': page,
            'per_page': per_page,
            'path': '/' + path.strip('/'),
        }

    @staticmethod
    async def _save_profile(db: AsyncSession, account: MyDriveAccount, profile) -> MyDriveAccount:
        """
        保存网盘账户资料。

        :param db: 数据库会话
        :param account: 网盘账户
        :param profile: 网盘账户资料
        :return:
        """
        if not profile.external_account_id:
            raise errors.ServerError(msg='未能获取网盘账户标识')

        await mydrive_account_dao.update_model(
            db,
            account.id,
            {
                'external_account_id': profile.external_account_id,
                'username': profile.username,
                'avatar_url': profile.avatar_url,
                'quota': profile.quota,
                'used': profile.used,
                'vip_level': profile.vip_level,
                'credential': profile.credential if account.provider == 'thunder' else account.credential,
                'status': 'active',
                'last_verified_at': timezone.now(),
                'last_profile_synced_at': timezone.now(),
            },
        )
        return await MyDriveAccountService.get(db, pk=account.id, owner_id=account.owner_id)


mydrive_account_service: MyDriveAccountService = MyDriveAccountService()
