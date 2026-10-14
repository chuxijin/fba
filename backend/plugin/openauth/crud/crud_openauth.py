#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开放平台授权中心 CRUD"""

from uuid import uuid4

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.openauth.enums import OpenAuthAuthorizationStatus, OpenAuthClientStatus
from backend.plugin.openauth.model import OpenAuthClient, OpenAuthUserAuthorization
from backend.plugin.openauth.schema.authorization import CreateOpenAuthAuthorizationParam
from backend.utils.timezone import timezone


class CRUDOpenAuthClient(CRUDPlus[OpenAuthClient]):
    """客户端 CRUD"""

    async def get_by_client_id(self, db: AsyncSession, *, client_id: str) -> OpenAuthClient | None:
        stmt = sa.select(OpenAuthClient).where(OpenAuthClient.client_id == client_id, OpenAuthClient.deleted == 0)
        return (await db.execute(stmt)).scalars().first()


class CRUDOpenAuthUserAuthorization(CRUDPlus[OpenAuthUserAuthorization]):
    """用户授权关系 CRUD"""

    async def get_by_user_and_client(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        client_pk: int,
    ) -> OpenAuthUserAuthorization | None:
        stmt = sa.select(OpenAuthUserAuthorization).where(
            OpenAuthUserAuthorization.user_id == user_id,
            OpenAuthUserAuthorization.client_id == client_pk,
            OpenAuthUserAuthorization.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_active_by_user_and_client(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        client_pk: int,
    ) -> OpenAuthUserAuthorization | None:
        row = await self.get_by_user_and_client(db, user_id=user_id, client_pk=client_pk)
        if row and row.status == OpenAuthAuthorizationStatus.ACTIVE.value:
            return row
        return None

    async def upsert_authorization(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        client_pk: int,
        obj: CreateOpenAuthAuthorizationParam,
    ) -> OpenAuthUserAuthorization:
        """创建或激活授权关系（重新授权覆盖 scopes 并重新激活）"""
        now = timezone.now()
        stmt = insert(OpenAuthUserAuthorization).values(
            user_id=user_id,
            client_id=client_pk,
            scopes=obj.scopes,
            status=OpenAuthAuthorizationStatus.ACTIVE.value,
            authorized_time=now,
            grant_version=str(uuid4()),
            created_time=now,
            updated_time=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint='uk_openauth_user_auth_user_client',
            set_={
                'scopes': obj.scopes,
                'status': OpenAuthAuthorizationStatus.ACTIVE.value,
                'authorized_time': now,
                'updated_time': now,
                'grant_version': sa.case(
                    (
                        sa.and_(OpenAuthUserAuthorization.status == 'active', OpenAuthUserAuthorization.deleted == 0),
                        OpenAuthUserAuthorization.grant_version,
                    ),
                    else_=stmt.excluded.grant_version,
                ),
                'deleted': 0,
                'deleted_time': None,
            },
        ).returning(OpenAuthUserAuthorization)
        return (await db.execute(stmt.execution_options(populate_existing=True))).scalar_one()

    async def revoke(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        client_pk: int,
    ) -> bool:
        """吊销授权关系，返回是否存在生效授权"""
        row = await self.get_active_by_user_and_client(db, user_id=user_id, client_pk=client_pk)
        if not row:
            return False
        row.status = OpenAuthAuthorizationStatus.REVOKED.value
        row.grant_version = str(uuid4())
        row.updated_time = timezone.now()
        await db.flush()
        return True

    async def touch_last_used(
        self,
        db: AsyncSession,
        *,
        row: OpenAuthUserAuthorization,
    ) -> None:
        row.last_used_time = timezone.now()
        await db.flush()

    async def list_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> list[OpenAuthUserAuthorization]:
        stmt = (
            sa
            .select(OpenAuthUserAuthorization)
            .where(OpenAuthUserAuthorization.user_id == user_id, OpenAuthUserAuthorization.deleted == 0)
            .order_by(OpenAuthUserAuthorization.created_time.desc())
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    def is_active(row: OpenAuthUserAuthorization) -> bool:
        return row.status == OpenAuthAuthorizationStatus.ACTIVE.value

    async def list_with_clients(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> list[tuple[OpenAuthUserAuthorization, str, str]]:
        stmt = (
            sa
            .select(OpenAuthUserAuthorization, OpenAuthClient.client_id, OpenAuthClient.name)
            .join(OpenAuthClient, OpenAuthClient.id == OpenAuthUserAuthorization.client_id)
            .where(
                OpenAuthUserAuthorization.user_id == user_id,
                OpenAuthUserAuthorization.deleted == 0,
                OpenAuthClient.deleted == 0,
            )
            .order_by(OpenAuthUserAuthorization.created_time.desc())
        )
        return [(row[0], row[1], row[2]) for row in (await db.execute(stmt)).all()]


openauth_client_dao: CRUDOpenAuthClient = CRUDOpenAuthClient(OpenAuthClient)
openauth_user_authorization_dao: CRUDOpenAuthUserAuthorization = CRUDOpenAuthUserAuthorization(
    OpenAuthUserAuthorization
)


def client_enabled(client: OpenAuthClient) -> bool:
    return client.status == OpenAuthClientStatus.ENABLED.value
