#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.study_plan.model.spatial_cube import StudySpatialCubePattern
from backend.app.study_plan.schema.spatial_cube import CreateSpatialCubePatternParam


class CRUDStudySpatialCubePattern(CRUDPlus[StudySpatialCubePattern]):
    """六面体面素材数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> StudySpatialCubePattern | None:
        """
        获取面素材

        :param db: 数据库会话
        :param pk: 素材 ID
        :return:
        """
        return await self.select_model(db, pk, deleted=0)

    async def get_by_code(self, db: AsyncSession, code: str) -> StudySpatialCubePattern | None:
        """
        按编码获取面素材

        :param db: 数据库会话
        :param code: 素材编码
        :return:
        """
        return await self.select_model_by_column(db, code=code, deleted=0)

    async def get_all(
        self,
        db: AsyncSession,
        *,
        include_inactive: bool = False,
    ) -> Sequence[StudySpatialCubePattern]:
        """
        获取面素材列表

        :param db: 数据库会话
        :param include_inactive: 是否包含停用素材
        :return:
        """
        stmt = self.get_select(include_inactive=include_inactive)
        result = await db.execute(stmt)
        return result.scalars().all()

    def get_select(
        self,
        *,
        include_inactive: bool = False,
        keyword: str | None = None,
        render_type: str | None = None,
        is_active: bool | None = None,
    ) -> Select[tuple[StudySpatialCubePattern]]:
        """
        构建面素材查询语句

        :param include_inactive: 是否包含停用素材
        :param keyword: 名称、编码或素材地址关键词
        :param render_type: 渲染类型
        :param is_active: 启用状态
        :return:
        """
        filters = [StudySpatialCubePattern.deleted == 0]
        if is_active is not None:
            filters.append(StudySpatialCubePattern.is_active.is_(is_active))
        elif not include_inactive:
            filters.append(StudySpatialCubePattern.is_active.is_(True))
        if render_type:
            filters.append(StudySpatialCubePattern.render_type == render_type)
        normalized_keyword = keyword.strip() if keyword else ''
        if normalized_keyword:
            search_pattern = f'%{normalized_keyword}%'
            filters.append(
                or_(
                    StudySpatialCubePattern.code.ilike(search_pattern),
                    StudySpatialCubePattern.name.ilike(search_pattern),
                    StudySpatialCubePattern.asset_url.ilike(search_pattern),
                )
            )
        return (
            select(StudySpatialCubePattern)
            .where(*filters)
            .order_by(StudySpatialCubePattern.sort.asc(), StudySpatialCubePattern.id.asc())
        )

    async def create(
        self,
        db: AsyncSession,
        obj: CreateSpatialCubePatternParam,
        created_by: int,
    ) -> StudySpatialCubePattern:
        """
        创建面素材

        :param db: 数据库会话
        :param obj: 素材数据
        :param created_by: 创建者 ID
        :return:
        """
        return await self.create_model(db, obj, flush=True, created_by=created_by, commit=False)

    async def update(
        self,
        db: AsyncSession,
        pk: int,
        data: dict[str, object],
        updated_by: int,
    ) -> int:
        """
        更新面素材

        :param db: 数据库会话
        :param pk: 素材 ID
        :param data: 更新数据
        :param updated_by: 修改者 ID
        :return:
        """
        return await self.update_model(db, pk, data, updated_by=updated_by, commit=False)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除面素材

        :param db: 数据库会话
        :param pk: 素材 ID
        :return:
        """
        return await self.delete_model(db, pk, commit=False)


study_spatial_cube_pattern_dao = CRUDStudySpatialCubePattern(StudySpatialCubePattern)
