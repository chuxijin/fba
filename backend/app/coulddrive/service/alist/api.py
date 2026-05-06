#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#api.py
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union

import requests

from backend.core.conf import settings

from .errors import AlistApiError, assert_ok

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
    Account = "/api/me"
    FileList = "/api/fs/list"
    FileRemove = "/api/fs/remove"
    FileCopy = "/api/fs/copy"
    FileMkdir = "/api/fs/mkdir"
    Login = "/api/auth/login"

    def url(self) -> str:
        return f"{ALIST_URL}{self.value}"  

class AlistApi:
    """alist网盘API实现"""

    def __init__(self, cookies: Optional[str] = None, username: str = "admin", password: str = "admin"):
        """
        初始化 AlistApi

        :param cookies: cookies
        :param username: 用户名，默认为 admin
        :param password: 密码，默认为 admin
        """
        self._username = username
        self._password = password
        self._cookies = cookies
        self._session = requests.Session()
        self._timeout = settings.HTTP_REQUEST_TIMEOUT
        self._headers = ALIST_HEADERS.copy()
        
        if cookies:
            self._headers["Authorization"] = cookies

    async def login(self, username: Optional[str] = None, password: Optional[str] = None) -> str:
        """
        登录获取 token
        
        :param username: 用户名，如果不提供则使用初始化时的用户名
        :param password: 密码，如果不提供则使用初始化时的密码
        :return: 新的 token
        """
        login_username = username or self._username
        login_password = password or self._password
        
        url = AlistNode.Login.url()
        data = {
            "username": login_username,
            "password": login_password
        }
        
        # 临时移除 Authorization 头进行登录
        temp_headers = self._headers.copy()
        if "Authorization" in temp_headers:
            del temp_headers["Authorization"]
        
        try:
            resp = await self._request_raw(Method.POST, url, data=data, headers=temp_headers)
            result = resp.json()
            
            if result.get("code") == 200 and "data" in result and "token" in result["data"]:
                new_token = result["data"]["token"]
                # 更新 cookies 和 headers
                self._cookies = new_token
                self._headers["Authorization"] = new_token
                return new_token
            else:
                raise AlistApiError(f"登录失败: {result.get('message', '未知错误')}")
                
        except Exception as e:
            raise AlistApiError(f"登录请求失败: {e}")

    async def _request_raw(
        self,
        method: Method,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Union[str, bytes, Dict[str, str], Any] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        **kwargs,
    ) -> requests.Response:
        """原始请求方法，不进行自动重试"""
        if params is None:
            params = {}

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
                timeout=timeout or self._timeout, # 使用传入的timeout，如果没有则使用实例的默认timeout
                **kwargs,
            )
            
            try:
                response_json = resp.json()
                print(f"   响应体: {response_json}")
            except Exception:
                print(f"   响应体 (文本): {resp.text}")
            
            return resp
        except Exception as err:
            print(f"❌ DEBUG - 请求异常: {err}")
            raise AlistApiError("AlistApi._request_raw", cause=err)

    async def _request(
        self,
        method: Method,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Union[str, bytes, Dict[str, str], Any] = None,
        files: Optional[Dict[str, Any]] = None,
        retry_login: bool = True,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        **kwargs,
    ) -> requests.Response:
        """带自动重新登录的请求方法"""
        if params is None:
            params = {}

        try:
            resp = await self._request_raw(method, url, params, headers, data, files, timeout=timeout, **kwargs)
            
            # 检查是否是认证失败
            if resp.status_code == 401 or (resp.status_code == 200 and resp.json().get("code") == 401):
                if retry_login and self._username and self._password:
                    print("🔄 检测到认证失败，尝试重新登录...")
                    await self.login()
                    # 重新发送请求，但不再重试登录
                    return await self._request(method, url, params, headers, data, files, retry_login=False, timeout=timeout, **kwargs)
                else:
                    raise AlistApiError("认证失败且无法自动重新登录")
            
            return resp
            
        except Exception as err:
            if "认证失败" in str(err):
                raise
            print(f"❌ DEBUG - 请求异常: {err}")
            raise AlistApiError("AlistApi._request", cause=err)

    async def _request_get(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        return await self._request(Method.GET, url, params=params, headers=headers)

    @property
    def cookies(self) -> str:
        """获取当前的 cookies"""
        return self._cookies

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

    @assert_ok
    async def get_account_info(self):
        """
        获取账户信息
        
        :return: 账户信息
        """
        url = AlistNode.Account.url()
        
        resp = await self._request(Method.GET, url)
        return resp.json()

    @assert_ok
    async def mkdir(self, path: str):
        """
        创建目录
        
        :param path: 目录路径
        :return: 创建结果
        """
        url = AlistNode.FileMkdir.url()
        
        data = {
            "path": path
        }
        
        resp = await self._request(Method.POST, url, data=data)
        return resp.json()
