#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from bilibili_api import video
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.crud import bili_work_dao
from backend.app.bili.model import BiliWork
from backend.app.bili.schema.work import CreateBiliWorkParam, UpdateBiliWorkParam
from backend.common.exception import errors
from backend.common.log import log


class BiliWorkService:
    """B 站作品服务类"""

    @staticmethod
    async def get(db: AsyncSession, pk: int) -> BiliWork:
        """
        获取作品详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        work = await bili_work_dao.get(db, pk)
        if not work:
            raise errors.NotFoundError(msg='作品不存在')
        return work

    @staticmethod
    async def create(db: AsyncSession, obj: CreateBiliWorkParam) -> None:
        """
        创建作品

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        work = await bili_work_dao.get_by_work_id(db, obj.work_id)
        if work:
            raise errors.ForbiddenError(msg='作品 ID 已存在')
        await bili_work_dao.create(db, obj)

    @staticmethod
    async def update(db: AsyncSession, pk: int, obj: UpdateBiliWorkParam) -> int:
        """
        更新作品

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        work = await bili_work_dao.get(db, pk)
        if not work:
            raise errors.NotFoundError(msg='作品不存在')
        count = await bili_work_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(db: AsyncSession, pk: int) -> int:
        """
        删除作品

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        work = await bili_work_dao.get(db, pk)
        if not work:
            raise errors.NotFoundError(msg='作品不存在')
        count = await bili_work_dao.delete(db, pk)
        return count

    @staticmethod
    async def get_or_create_by_bvid(db: AsyncSession, bvid: str) -> BiliWork:
        """
        根据 BVID 获取或创建作品

        :param db: 数据库会话
        :param bvid: BVID
        :return: 作品对象
        """
        # 先查询数据库
        work = await bili_work_dao.get_by_work_id(db, bvid)
        if work:
            log.info(f'作品已存在: {bvid}')
            return work

        # 从 B 站 API 获取作品信息
        try:
            v = video.Video(bvid=bvid)
            info = await v.get_info()

            # 创建作品记录
            create_param = CreateBiliWorkParam(
                work_id=bvid,
                aid=info.get('aid'),  # 保存 AID，用于评论 API
                title=info.get('title', ''),
                work_type='video',
                url=f'https://www.bilibili.com/video/{bvid}',
                view_count=info.get('stat', {}).get('view', 0),
                like_count=info.get('stat', {}).get('like', 0),
                comment_count=info.get('stat', {}).get('reply', 0),
                coin_count=info.get('stat', {}).get('coin', 0),
                share_count=info.get('stat', {}).get('share', 0),
                favorite_count=info.get('stat', {}).get('favorite', 0),
                mid=str(info.get('owner', {}).get('mid', '')),
            )

            work = await bili_work_dao.create(db, create_param)
            log.success(f'作品创建成功: {bvid} - {info.get("title", "")}')
            return work

        except Exception as e:
            log.error(f'获取作品信息失败: {bvid}, {str(e)}')
            raise errors.ServerError(msg=f'无法获取作品信息: {str(e)}')


bili_work_service = BiliWorkService()
