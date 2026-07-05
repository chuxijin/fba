#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from math import ceil
import asyncio
from typing import Any

from fastapi_pagination.links.bases import create_links

from backend.app.halo.schema.halo import HaloCategoryItem, HaloPostDetail, HaloPostItem, HaloTagItem, DocTreeNode, DocDetail
from backend.app.halo.service.halo_client import halo_client
from backend.app.halo.service.halo_db import halo_db
from backend.core.conf import settings


class HaloService:
    """Halo 博客业务逻辑"""

    @staticmethod
    def _full_cover_url(cover: str) -> str:
        """
        将相对路径封面图拼接为完整 URL

        :param cover: 相对路径封面图
        :return:
        """
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
    def _parse_search_hit(hit: dict[str, Any]) -> HaloPostItem:
        """
        将搜索到的 HaloDocument 转换为 HaloPostItem schema

        :param hit: 搜索命中的 HaloDocument 原始数据
        :return:
        """
        return HaloPostItem(
            name=hit.get('metadataName', ''),
            title=hit.get('title', ''),
            slug=hit.get('permalink', '').split('/')[-1] if hit.get('permalink') else '',
            excerpt=hit.get('description') or hit.get('content', '')[:100],
            cover='',
            publish_time=hit.get('updateTimestamp') or hit.get('creationTimestamp', ''),
            categories=hit.get('categories', []),
            tags=hit.get('tags', []),
            view_count=0,
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
        获取文章列表，并适配统一的分页格式结构

        :param page: 页码
        :param size: 每页数量
        :param category: 分类名称
        :param tag: 标签名称
        :param keyword: 搜索关键词
        :return:
        """
        if keyword:
            # 采用统一搜索检索并限制最大拉取范围以供分页
            search_res = await halo_client.search_posts(keyword=keyword, limit=size * page)
            raw_hits = search_res.get('hits', [])
            
            # 手动过滤属于文章类型的对象进行本地截取
            post_hits = [h for h in raw_hits if 'post.content.halo.run' in h.get('type', '')]
            start_index = (page - 1) * size
            end_index = start_index + size
            
            items = [HaloService._parse_search_hit(hit) for hit in post_hits[start_index:end_index]]
            total = len(post_hits)
            total_pages = int(ceil(total / size)) if size > 0 else 1
        else:
            data = await halo_client.list_posts(page=page, size=size, category=category, tag=tag)
            raw_items = data.get('items', [])
            items = [HaloService._parse_post_item(item) for item in raw_items]
            total = data.get('total', 0)
            total_pages = data.get('totalPages') or int(ceil(total / size)) if size > 0 else 1

        # 组装符合 Pydantic PageData 实体的分页链接
        try:
            links = create_links(
                first={'page': 1, 'size': size},
                last={'page': total_pages, 'size': size} if total > 0 else {'page': 1, 'size': size},
                next={'page': page + 1, 'size': size} if (page + 1) <= total_pages else None,
                prev={'page': page - 1, 'size': size} if (page - 1) >= 1 else None,
            ).model_dump()
        except RuntimeError:
            links = {
                'first': f'/posts?page=1&size={size}',
                'last': f'/posts?page={total_pages}&size={size}' if total > 0 else f'/posts?page=1&size={size}',
                'self': f'/posts?page={page}&size={size}',
                'next': f'/posts?page={page + 1}&size={size}' if (page + 1) <= total_pages else None,
                'prev': f'/posts?page={page - 1}&size={size}' if (page - 1) >= 1 else None,
            }

        return {
            'page': page,
            'size': size,
            'total': total,
            'total_pages': total_pages,
            'links': links,
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
        """
        获取分类列表

        :return:
        """
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
        """
        获取标签列表

        :return:
        """
        items = await halo_client.list_tags()
        return [
            HaloTagItem(
                name=item.get('metadata', {}).get('name', ''),
                display_name=item.get('spec', {}).get('displayName', ''),
                slug=item.get('spec', {}).get('slug', ''),
            )
            for item in items
        ]

    @staticmethod
    async def create_post_with_content(
        *,
        title: str,
        slug: str,
        content: str,
        raw_content: str | None = None,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        owner: str = 'yzxj',
        publish: bool = True,
    ) -> dict[str, Any]:
        """
        创建文章并写入正文，完整流程：创建草稿 → 写入正文 → 修复 baseSnapshot → 可选发布

        :param title: 文章标题
        :param slug: 文章别名
        :param content: 渲染后的 HTML 格式正文内容
        :param raw_content: 原始格式正文内容，默认与 content 一致
        :param categories: 绑定的分类 metadata.name 列表
        :param tags: 绑定的标签 metadata.name 列表
        :param owner: 文章所有者
        :param publish: 是否直接发布
        :return:
        """
        # Step 1: 创建空草稿
        post_data = {
            'apiVersion': 'content.halo.run/v1alpha1',
            'kind': 'Post',
            'metadata': {
                'generateName': 'post-',
                'annotations': {
                    'content.halo.run/preferred-editor': 'default'
                }
            },
            'spec': {
                'title': title,
                'slug': slug,
                'allowComment': True,
                'deleted': False,
                'pinned': False,
                'priority': 0,
                'publish': False,
                'visible': 'PUBLIC',
                'excerpt': {
                    'autoGenerate': True
                },
                'categories': categories or [],
                'tags': tags or [],
                'owner': owner
            }
        }
        post = await halo_client.create_post(post_data)
        post_name = post['metadata']['name']

        # Step 2: 写入正文内容
        content_data = {
            'content': content,
            'raw': raw_content or content,
            'rawType': 'HTML'
        }
        post = await halo_client.update_post_content(post_name, content_data)

        # Step 3: 修复 baseSnapshot（Console API 不会自动设置，需重试避免版本冲突）
        head_snapshot = post.get('spec', {}).get('headSnapshot')
        if head_snapshot and not post.get('spec', {}).get('baseSnapshot'):
            for _ in range(3):
                await asyncio.sleep(0.5)
                post = await halo_client.get_post_extension(post_name)
                post['spec']['baseSnapshot'] = head_snapshot
                try:
                    post = await halo_client.update_post(post_name, post)
                    break
                except Exception:
                    continue

        # Step 4: 可选发布
        if publish:
            post = await halo_client.publish_post(post_name, head_snapshot)

        return post

    @staticmethod
    async def list_doc_tree() -> list[DocTreeNode]:
        """
        获取 Docsme 文档目录树

        :return: 树形结构节点列表
        """
        nodes = await asyncio.to_thread(halo_db.fetch_all_doctrees)
        tree = halo_db.build_tree(nodes)

        def convert(nodes_list: list[dict[str, Any]]) -> list[DocTreeNode]:
            return [
                DocTreeNode(
                    name=n['name'],
                    title=n['title'],
                    slug=n['slug'],
                    type=n['type'],
                    permalink=n['permalink'],
                    children=convert(n.get('children', [])),
                )
                for n in nodes_list
            ]

        return convert(tree)

    @staticmethod
    async def get_doc(*, name: str) -> DocDetail | None:
        """
        获取文档详情

        :param name: Doc UUID
        :return: 文档详情
        """
        detail = await asyncio.to_thread(halo_db.get_doc_detail, name)
        if not detail:
            return None
        return DocDetail(
            name=detail['name'],
            title=detail['title'],
            permalink=detail['permalink'],
            content=detail['content'],
            updated_at=detail['updated_at'],
        )

    @staticmethod
    async def unpublish_post(name: str) -> dict[str, Any]:
        """
        取消发布文章并回退到草稿状态

        :param name: 文章资源标识名称
        :return:
        """
        return await halo_client.unpublish_post(name)

    @staticmethod
    async def delete_post(name: str) -> dict[str, Any]:
        """
        物理删除文章资源实体

        :param name: 文章资源标识名称
        :return:
        """
        return await halo_client.delete_post_extension(name)

    @staticmethod
    async def get_post_draft_content(name: str) -> dict[str, Any]:
        """
        获取文章当前的最新草稿（headSnapshot）正文详情

        :param name: 文章资源标识名称
        :return: 包含 content 和 raw 的正文详情
        """
        post = await halo_client.get_post_extension(name)
        head_snapshot = post.get('spec', {}).get('headSnapshot')
        if not head_snapshot:
            return {'content': '', 'raw': '', 'rawType': 'HTML'}
        snapshot = await halo_client.get_snapshot(head_snapshot)
        spec = snapshot.get('spec', {})
        return {
            'content': spec.get('contentPatch', ''),
            'raw': spec.get('rawPatch', ''),
            'rawType': spec.get('rawType', 'HTML')
        }

    @staticmethod
    async def update_post_draft_content(
        name: str,
        content: str,
        raw_content: str | None = None
    ) -> dict[str, Any]:
        """
        更新文章的草稿正文内容

        :param name: 文章资源标识名称
        :param content: HTML 格式正文内容
        :param raw_content: 原始 Markdown 格式正文内容
        :return:
        """
        content_data = {
            'content': content,
            'raw': raw_content or content,
            'rawType': 'HTML'
        }
        return await halo_client.update_post_content(name, content_data)


halo_service = HaloService()
