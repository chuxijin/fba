from typing import Any

import httpx

from backend.core.conf import settings

HALO_PUBLIC_API = '/apis/api.content.halo.run/v1alpha1'
HALO_EXTENSION_API = '/apis/content.halo.run/v1alpha1'
HALO_TIMEOUT = 15


class HaloClient:
    """Halo 2.x API 客户端"""

    def __init__(self) -> None:
        self._base_url = settings.HALO_BASE_URL.rstrip('/')
        self._pat = settings.HALO_PAT

    def _auth_headers(self) -> dict[str, str]:
        """构建 PAT 认证请求头"""
        return {'Authorization': f'Bearer {self._pat}'}

    async def _get(self, path: str, *, auth: bool = False, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        发送 GET 请求

        :param path: API 路径
        :param auth: 是否需要 PAT 认证
        :param params: 查询参数
        :return:
        """
        headers = self._auth_headers() if auth else {}
        async with httpx.AsyncClient(timeout=HALO_TIMEOUT) as client:
            response = await client.get(f'{self._base_url}{path}', headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    async def _post(self, path: str, *, json_data: dict[str, Any]) -> dict[str, Any]:
        """
        发送 POST 请求（需要 PAT 认证）

        :param path: API 路径
        :param json_data: 请求体
        :return:
        """
        async with httpx.AsyncClient(timeout=HALO_TIMEOUT) as client:
            response = await client.post(
                f'{self._base_url}{path}',
                headers={**self._auth_headers(), 'Content-Type': 'application/json'},
                json=json_data,
            )
            response.raise_for_status()
            return response.json()

    async def _put(self, path: str, *, json_data: dict[str, Any]) -> dict[str, Any]:
        """
        发送 PUT 请求（需要 PAT 认证）

        :param path: API 路径
        :param json_data: 请求体
        :return:
        """
        async with httpx.AsyncClient(timeout=HALO_TIMEOUT) as client:
            response = await client.put(
                f'{self._base_url}{path}',
                headers={**self._auth_headers(), 'Content-Type': 'application/json'},
                json=json_data,
            )
            response.raise_for_status()
            return response.json()

    async def list_posts(
        self,
        *,
        page: int = 1,
        size: int = 10,
        category: str | None = None,
        tag: str | None = None,
        keyword: str | None = None,
    ) -> dict[str, Any]:
        """
        获取已发布文章列表（Public API）

        :param page: 页码
        :param size: 每页数量
        :param category: 分类名称（Halo metadata.name）
        :param tag: 标签名称（Halo metadata.name）
        :param keyword: 搜索关键词
        :return:
        """
        params: dict[str, Any] = {'page': page, 'size': size}
        if category:
            params['categoryName'] = category
        if tag:
            params['tagName'] = tag
        if keyword:
            params['keyword'] = keyword
        return await self._get(f'{HALO_PUBLIC_API}/posts', params=params)

    async def get_post(self, name: str) -> dict[str, Any]:
        """
        获取文章详情（Public API）

        :param name: 文章的 metadata.name
        :return:
        """
        return await self._get(f'{HALO_PUBLIC_API}/posts/{name}')

    async def list_categories(self) -> list[dict[str, Any]]:
        """获取所有分类（Extension API）"""
        data = await self._get(f'{HALO_EXTENSION_API}/categories', auth=True, params={'page': 0, 'size': 100})
        return data.get('items', [])

    async def list_tags(self) -> list[dict[str, Any]]:
        """获取所有标签（Extension API）"""
        data = await self._get(f'{HALO_EXTENSION_API}/tags', auth=True, params={'page': 0, 'size': 100})
        return data.get('items', [])

    async def create_post(self, post_data: dict[str, Any]) -> dict[str, Any]:
        """
        创建文章（Extension API）

        :param post_data: Halo Post 对象
        :return:
        """
        return await self._post(f'{HALO_EXTENSION_API}/posts', json_data=post_data)

    async def update_post(self, name: str, post_data: dict[str, Any]) -> dict[str, Any]:
        """
        更新文章（Extension API）

        :param name: 文章的 metadata.name
        :param post_data: Halo Post 对象
        :return:
        """
        return await self._put(f'{HALO_EXTENSION_API}/posts/{name}', json_data=post_data)


halo_client = HaloClient()
