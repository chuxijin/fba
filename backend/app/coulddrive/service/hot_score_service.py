#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_resource import resource_dao
from backend.app.coulddrive.schema.resource import ResourceListItem
from backend.common.log import log
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

# Redis key 前缀
CLICK_KEY_PREFIX = 'resource:hot:click:'
SEARCH_KEY_PREFIX = 'resource:hot:search:'
# 计数器过期时间（30 天）
COUNTER_TTL = 60 * 60 * 24 * 30

# 热度权重（基于用户行为价值金字塔）
# 点击 > 浏览 > 搜索曝光
WEIGHT_CLICK = 5.0
WEIGHT_VIEW = 1.0
WEIGHT_SEARCH = 0.3

# 时间衰减参数（HN 风格）
# half_life: 热度半衰期（天），资源在此天数后热度衰减一半
# gravity: 衰减曲线陡峭度，值越大老资源掉得越快
HALF_LIFE_DAYS = 7.0
GRAVITY = 1.5
HOT_SCORE_SCALE = 100


def calculate_hot_score(
    click_count: int,
    view_count: int,
    search_count: int,
    age_days: float,
) -> float:
    """
    计算资源热度评分

    公式：score = (click * W_click + view * W_view + search * W_search) / (1 + age / half_life) ^ gravity
    灵感来源：Hacker News 排名算法

    :param click_count: 前端点击次数
    :param view_count: 分享链接浏览量
    :param search_count: 搜索曝光次数
    :param age_days: 资源创建天数
    :return:
    """
    engagement = (
        click_count * WEIGHT_CLICK
        + view_count * WEIGHT_VIEW
        + search_count * WEIGHT_SEARCH
    )
    # 避免 age_days 为负
    age_days = max(age_days, 0.0)
    decay = math.pow(1 + age_days / HALF_LIFE_DAYS, GRAVITY)
    return engagement / decay


class HotScoreService:
    """资源热度评分服务"""

    @staticmethod
    async def record_click(resource_id: int) -> int:
        """
        记录前端点击事件

        :param resource_id: 资源 ID
        :return:
        """
        key = f'{CLICK_KEY_PREFIX}{resource_id}'
        count = await redis_client.incr(key)
        # 首次创建时设置过期时间
        if count == 1:
            await redis_client.expire(key, COUNTER_TTL)
        return count

    @staticmethod
    async def record_search_impressions(resource_ids: list[int]) -> None:
        """
        批量记录搜索曝光事件

        :param resource_ids: 命中搜索的资源 ID 列表
        :return:
        """
        if not resource_ids:
            return

        unique_resource_ids = list(dict.fromkeys(resource_ids))
        pipe = redis_client.pipeline()
        for rid in unique_resource_ids:
            key = f'{SEARCH_KEY_PREFIX}{rid}'
            pipe.incr(key)
        results = await pipe.execute()

        # 对首次创建的 key 设置过期时间
        pipe2 = redis_client.pipeline()
        for i, rid in enumerate(unique_resource_ids):
            if results[i] == 1:
                pipe2.expire(f'{SEARCH_KEY_PREFIX}{rid}', COUNTER_TTL)

        if pipe2.command_stack:
            await pipe2.execute()

    @staticmethod
    def _get_age_days(created_time) -> float:
        """
        计算资源已创建天数

        :param created_time: 资源创建时间
        :return:
        """
        now = timezone.now()
        normalized_created_time = created_time
        if normalized_created_time.tzinfo is None:
            normalized_created_time = normalized_created_time.replace(tzinfo=now.tzinfo)

        age_seconds = (now - normalized_created_time).total_seconds()
        if age_seconds <= 0:
            return 0.0

        return age_seconds / 86400

    @staticmethod
    async def get_counters(resource_ids: list[int]) -> dict[int, tuple[int, int]]:
        """
        批量获取 click_count 和 search_count

        :param resource_ids: 资源 ID 列表
        :return:
        """
        if not resource_ids:
            return {}

        pipe = redis_client.pipeline()
        for rid in resource_ids:
            pipe.get(f'{CLICK_KEY_PREFIX}{rid}')
            pipe.get(f'{SEARCH_KEY_PREFIX}{rid}')
        results = await pipe.execute()

        counters = {}
        for i, rid in enumerate(resource_ids):
            click_count = int(results[i * 2] or 0)
            search_count = int(results[i * 2 + 1] or 0)
            counters[rid] = (click_count, search_count)
        return counters

    @staticmethod
    async def get_hot_list(
        *,
        db: AsyncSession,
        category_ids: list[int] | None = None,
        resource_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[ResourceListItem]:
        """
        获取热门资源列表（实时计算）

        :param db: 数据库会话
        :param category_ids: 分类 ID 列表（包含子分类）
        :param resource_types: 资源类型列表
        :param limit: 获取数量
        :return:
        """
        resources = await resource_dao.get_hot_list(
            db,
            category_ids=category_ids,
            resource_types=resource_types,
            limit=limit,
        )
        return [ResourceListItem.model_validate(resource) for resource in resources]

    @staticmethod
    async def sync_hot_to_db(db: AsyncSession) -> int:
        """
        将实时热度评分同步到数据库 hot 字段（离线快照）

        :return:
        """
        resources = await resource_dao.get_active_resources(db)
        if not resources:
            return 0

        resource_ids = [r.id for r in resources]
        counters = await HotScoreService.get_counters(resource_ids)

        updated = 0
        for resource in resources:
            rid = resource.id
            click_count, search_count = counters.get(rid, (0, 0))
            age_days = HotScoreService._get_age_days(resource.created_time)
            score = calculate_hot_score(
                click_count=click_count,
                view_count=resource.view_count or 0,
                search_count=search_count,
                age_days=age_days,
            )
            hot_int = int(round(score * HOT_SCORE_SCALE))
            if resource.hot != hot_int:
                resource.hot = hot_int
                updated += 1

        if updated:
            await db.commit()
            log.info(f'热度快照同步完成，更新 {updated}/{len(resources)} 个资源')

        return updated


hot_score_service = HotScoreService()
