#api.py
from typing import List, Optional, Dict, Any, Union
from enum import Enum

import requests

from errors import QuarkApiError, assert_ok

# API 基础URL
PAN_QUARK_COM = "https://pan.quark.com"
PC_QUARK_CN = "https://drive-pc.quark.cn"

# User-Agent

PAN_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Headers
PAN_HEADERS = {"User-Agent": PAN_UA}

class Method(Enum):
    """HTTP方法枚举"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"

class PanNode(Enum):
    """使用pan.quark.com的网盘节点"""
    Account= "/account/info"

    def url(self) -> str:
        return f"{PAN_QUARK_COM}/{self.value}"
    
class PCNode(Enum):
    """使用drive-pc.quark.cn的网盘节点"""
    Member = "/clouddrive/member"
    FileList = "/1/clouddrive/file/sort"
    FileCreate = "/1/clouddrive/file"
    FileRename = "/1/clouddrive/file/rename"
    FileMove = "/1/clouddrive/file/move"
    FileCopy = "/1/clouddrive/file/copy"
    FileDelete = "/1/clouddrive/file/delete"
    ShareList = "/1/clouddrive/share/mypage/detail"
    ShareCreate = "/1/clouddrive/share"
    ShareSave = "/1/clouddrive/share/sharepage/save"
    SharePasswd = "/1/clouddrive/share/password"
    ShareToken = "/1/clouddrive/share/sharepage/token"
    ShareDetail = "/1/clouddrive/share/sharepage/detail"
    TaskQuery = "/1/clouddrive/task"

    def url(self) -> str:
        return f"{PC_QUARK_CN}{self.value}"

class QuarkApi:
    """夸克网盘API实现"""

    def __init__(self, cookies: Optional[str] = None):
        if not cookies:
            assert False, "cookies is required"

        self._cookies = self._parse_cookies(cookies)
        self._session = requests.Session()
        self._session.cookies.update(self._cookies)
        self._user_id = None
        self._user_info = None

    def _parse_cookies(self, cookies: str) -> Dict[str, Optional[str]]:
        """将字符串形式的 cookies 转换为字典"""
        cookie_dict = {}
        for cookie in cookies.split(';'):
            key, value = cookie.strip().split('=', 1)  # 只分割第一个 '='
            cookie_dict[key] = value
        return cookie_dict

    @property
    def cookies(self) -> Dict[str, Optional[str]]:
        return self._session.cookies.get_dict()

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
            headers = PAN_HEADERS

        try:
            resp = self._session.request(
                method.value,
                url,
                params=params,
                headers=headers,
                data=data,
                files=files,
                **kwargs,
            )
            return resp
        except Exception as err:
            raise QuarkApiError("QuarkApi._request", cause=err)

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
        file_id: str,
        page: Optional[int] = 1,
        num: Optional[int] = 50,
        desc: bool = False,
        name: bool = False,
        time: bool = False,
        size: bool = False,
    ):
        url = PCNode.FileList.url()
        orderby = None
        if name:
            orderby = "file_name"
        elif time:
            orderby = "time"
        elif size:
            orderby = "size"
        else:
            orderby = "file_type"

        params = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "pdir_fid": file_id,
            "_page": page,
            "_size": num,
            "_fetch_total": 1,
            "_fetch_sub_dirs": 0,
            "_sort": f"{orderby}:asc" if not desc else f"{orderby}:desc"
        }
        resp = await self._request(Method.GET, url, params=params)
        return resp.json()