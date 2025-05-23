#api.py
from typing import List, Optional, Dict, Any, Union
from enum import Enum

import requests

from errors import AlistApiError, assert_ok

# API 基础URL
ALIST_URL = "https://alist.yzxj.vip"


# User-Agent

ALIST_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Headers
ALIST_HEADERS = {
    "User-Agent": ALIST_UA,
    "Content-Type": "application/json"
}

class Method(Enum):
    """HTTP方法枚举"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"

class AlistNode(Enum):
    """使用alist.nuaa.top的网盘节点"""
    FileList = "/api/fs/list"
    FileRemove = "/api/fs/remove"
    FileCopy = "/api/fs/copy"

    def url(self) -> str:
        return f"{ALIST_URL}{self.value}"  

class AlistApi:
    """alist网盘API实现"""

    def __init__(self, token: Optional[str] = None):
        """
        初始化 AlistApi

        :param token: Authorization token
        """
        if not token:
            assert False, "token is required"

        self._token = token
        self._session = requests.Session()
        self._headers = ALIST_HEADERS.copy()
        self._headers["Authorization"] = token

    async def _request(
        self,
        method: Method,
        url: str,
        params: Optional[Dict[str, str]] = {},
        headers: Optional[Dict[str, str]] = None,
        data: Union[str, bytes, Dict[str, str], Any] = None,
        files: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> requests.Response:
        if not headers:
            headers = self._headers

        try:
            resp = self._session.request(
                method.value,
                url,
                params=params,
                headers=headers,
                json=data,  # 使用json参数，因为Alist API使用JSON格式
                files=files,
                **kwargs,
            )
            return resp
        except Exception as err:
            raise AlistApiError("AlistApi._request", cause=err)

    async def _request_get(
        self,
        url: str,
        params: Optional[Dict[str, str]] = {},
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        return await self._request(Method.GET, url, params=params, headers=headers)

    @assert_ok
    async def list(
        self,
        file_path: str,
        page: Optional[int] = 1,
        num: Optional[int] = 0,
        refresh: Optional[bool] = False,
    ):
        """
        获取文件列表

        :param path: 文件路径
        :param page: 页码，从1开始
        :param per_page: 每页数量
        :param refresh: 是否刷新缓存
        """
        url = AlistNode.FileList.url()
        
        data = {
            "path": file_path,  
            "page": page,
            "per_page": num,
            "refresh": refresh
        }
        
        resp = await self._request(Method.POST, url, data=data)
        return resp.json()
    
    @assert_ok
    async def remove(
        self,
        names: list,
        dir: str,
    ):
        """
        删除文件

        :param names: 文件名列表
        :param dir: 父级ID
        """
        url = AlistNode.FileRemove.url()    

        data = {
            "names": names,
            "dir": dir
        }
        
        resp = await self._request(Method.POST, url, data=data)
        return resp.json()

    @assert_ok
    async def copy(
        self,
        src_dir: str,
        dst_dir: str,
        names: list,
    ):
        """
        复制文件

        :param src_dir: 源文件路径
        :param dst_dir: 目标文件路径
        :param names: 文件名列表
        """
        url = AlistNode.FileCopy.url()
        
        data = {
            "src_dir": src_dir,
            "dst_dir": dst_dir,
            "names": names
        }
        
        resp = await self._request(Method.POST, url, data=data)
        return resp.json()
