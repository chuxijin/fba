from typing import Any

from backend.app.halo.schema.halo import HaloCategoryItem, HaloPostDetail, HaloPostItem, HaloTagItem
from backend.app.halo.service.halo_client import halo_client
from backend.core.conf import settings


class HaloService:
    """Halo 博客业务逻辑"""

    @staticmethod
    def _full_cover_url(cover: str) -> str:
        """将相对路径封面图拼接为完整 URL"""
        if not cover:
            return ''
        if cover.startswith('http'):
            return cover
        return f'{settings.HALO_BASE_URL.rstrip("/")}{cover}'

    @staticmethod
    def _parse_post_item(item: dict[str, Any]) -> HaloPostItem:
        """
        将 Halo Public API 文章数据转换为 schema

        :param item: Halo 原始文章数据
        :return:
        """
        spec = item.get('spec', {})
        status = item.get('status', {})
        stats = item.get('stats', {})
        categories = [c['spec']['displayName'] for c in item.get('categories', []) if 'spec' in c]
        tags = [t['spec']['displayName'] for t in item.get('tags', []) if 'spec' in t]

        return HaloPostItem(
            name=item.get('metadata', {}).get('name', ''),
            title=spec.get('title', ''),
            slug=spec.get('slug', ''),
            excerpt=status.get('excerpt', ''),
            cover=HaloService._full_cover_url(spec.get('cover', '')),
            publish_time=status.get('lastModifyTime') or item.get('metadata', {}).get('creationTimestamp', ''),
            categories=categories,
            tags=tags,
            view_count=stats.get('visit', 0),
        )

    @staticmethod
    def _parse_post_detail(item: dict[str, Any]) -> HaloPostDetail:
        """
        将 Halo Public API 文章详情转换为 schema

        :param item: Halo 原始文章数据（含 content）
        :return:
        """
        spec = item.get('spec', {})
        status = item.get('status', {})
        stats = item.get('stats', {})
        content = item.get('content', {})
        categories = [c['spec']['displayName'] for c in item.get('categories', []) if 'spec' in c]
        tags = [t['spec']['displayName'] for t in item.get('tags', []) if 'spec' in t]

        return HaloPostDetail(
            name=item.get('metadata', {}).get('name', ''),
            title=spec.get('title', ''),
            slug=spec.get('slug', ''),
            excerpt=status.get('excerpt', ''),
            cover=HaloService._full_cover_url(spec.get('cover', '')),
            publish_time=status.get('lastModifyTime') or item.get('metadata', {}).get('creationTimestamp', ''),
            categories=categories,
            tags=tags,
            view_count=stats.get('visit', 0),
            content=content.get('content', ''),
        )

    @staticmethod
    async def list_posts(
        *,
        page: int = 1,
        size: int = 10,
        category: str | None = None,
        tag: str | None = None,
        keyword: str | None = None,
    ) -> dict[str, Any]:
        """
        获取文章列表

        :param page: 页码
        :param size: 每页数量
        :param category: 分类名称
        :param tag: 标签名称
        :param keyword: 搜索关键词
        :return:
        """
        data = await halo_client.list_posts(page=page, size=size, category=category, tag=tag, keyword=keyword)
        items = [HaloService._parse_post_item(item) for item in data.get('items', [])]
        return {
            'page': data.get('page', page),
            'size': data.get('size', size),
            'total': data.get('total', 0),
            'items': items,
        }

    @staticmethod
    async def get_post(*, name: str) -> HaloPostDetail:
        """
        获取文章详情

        :param name: 文章的 metadata.name
        :return:
        """
        data = await halo_client.get_post(name)
        return HaloService._parse_post_detail(data)

    @staticmethod
    async def list_categories() -> list[HaloCategoryItem]:
        """获取分类列表"""
        items = await halo_client.list_categories()
        return [
            HaloCategoryItem(
                name=item.get('metadata', {}).get('name', ''),
                display_name=item.get('spec', {}).get('displayName', ''),
                slug=item.get('spec', {}).get('slug', ''),
                post_count=item.get('status', {}).get('visiblePostCount', 0),
            )
            for item in items
        ]

    @staticmethod
    async def list_tags() -> list[HaloTagItem]:
        """获取标签列表"""
        items = await halo_client.list_tags()
        return [
            HaloTagItem(
                name=item.get('metadata', {}).get('name', ''),
                display_name=item.get('spec', {}).get('displayName', ''),
                slug=item.get('spec', {}).get('slug', ''),
            )
            for item in items
        ]


halo_service = HaloService()
