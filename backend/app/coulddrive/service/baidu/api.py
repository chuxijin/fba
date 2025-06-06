import json
import random
import re
import time
import urllib
from base64 import standard_b64encode
from enum import Enum
from pathlib import Path
from typing import IO, Any, Callable, Dict, List, Optional, Union
from urllib.error import HTTPError
from urllib.parse import quote_plus, urlparse

import requests  # type: ignore
from typing_extensions import Literal

# 添加日志模块导入
import logging

from ..utils_service import calu_md5, dump_json, now_timestamp
from .errors import BaiduApiError, assert_ok

# 为此模块创建一个 logger 实例
_api_logger = logging.getLogger(f"baidu_api.{__name__}")

PCS_BAIDU_COM = "https://pcs.baidu.com"
# PCS_BAIDU_COM = 'http://127.0.0.1:8888'
PAN_BAIDU_COM = "https://pan.baidu.com"
# PAN_BAIDU_COM = 'http://127.0.0.1:8888'

# PCS_UA = "netdisk;P2SP;2.2.90.43;WindowsBaiduYunGuanJia;netdisk;11.4.5;android-android;11.0;JSbridge4.4.0;LogStatistic"
# PCS_UA = "netdisk;P2SP;2.2.91.26;netdisk;11.6.3;GALAXY_S8;android-android;7.0;JSbridge4.4.0;jointBridge;1.1.0;"
# PCS_UA = "netdisk;P2SP;3.0.0.3;netdisk;11.5.3;PC;PC-Windows;android-android;11.0;JSbridge4.4.0"
# PCS_UA = "netdisk;P2SP;3.0.0.8;netdisk;11.12.3;GM1910;android-android;11.0;JSbridge4.4.0;jointBridge;1.1.0;"
PCS_UA = "softxm;netdisk"
PAN_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.75 Safari/537.36"

PCS_HEADERS = {"User-Agent": PCS_UA}
PAN_HEADERS = {"User-Agent": PAN_UA}

PCS_APP_ID = "778750"
PAN_APP_ID = "250528"

M3u8Type = Literal["M3U8_AUTO_720", "M3U8_AUTO_480"]


def _from_to(f: str, t: str) -> Dict[str, str]:
    return {"from": f, "to": t}


class Method(Enum):
    Head = "HEAD"
    Get = "GET"
    Post = "POST"


class PcsNode(Enum):
    """使用pcs.baidu.com的网盘节点"""

    Quota = "rest/2.0/pcs/quota"
    File = "rest/2.0/pcs/file"

    def url(self) -> str:
        return f"{PCS_BAIDU_COM}/{self.value}"


class PanNode(Enum):
    """使用pan.baidu.com的网盘节点"""

    TransferShared = "share/transfer"
    Share = "share/set"
    SharedPathList = "share/list"
    SharedRecord = "share/record"
    SharedCancel = "share/cancel"
    SharedPassword = "share/surlinfoinrecord"
    Getcaptcha = "api/getcaptcha"
    Cloud = "rest/2.0/services/cloud_dl"
    UserProducts = "rest/2.0/membership/user"
    FollowList = "mbox/relation/getfollowlist"
    GroupList = "mbox/group/list"
    FriendShareList = "mbox/msg/sessioninfo"
    GroupShareList = "mbox/group/listshare"
    ShareInfo = "mbox/msg/shareinfo"
    ShareTransfer = "mbox/msg/transfer"

    def url(self) -> str:
        return f"{PAN_BAIDU_COM}/{self.value}"


class BaiduApi:
    """`BaiduPCS`提供返回原始JSON的PCS API"""

    def __init__(
        self,
        cookies: str,
        user_id: Optional[int] = None,
    ):
        """
        
        :param cookies: cookies 字符串，格式如 "BDUSS=xxx; STOKEN=xxx; PTOKEN=xxx"
        :param user_id: 用户ID
        """
        # 解析 cookies 字符串
        parsed_cookies = self._parse_cookies(cookies)
        
        # 验证必需的认证信息
        self._bduss = parsed_cookies.get("BDUSS")
        assert self._bduss, "cookies 中必须包含 BDUSS"
        
        # 提取其他认证信息
        self._stoken = parsed_cookies.get("STOKEN")
        self._ptoken = parsed_cookies.get("PTOKEN")
        self._bdstoken = ""
        
        # 处理 BAIDUID 和 logid
        self._baiduid = parsed_cookies.get("BAIDUID")
        self._logid = None
        if self._baiduid:
            self._logid = standard_b64encode(self._baiduid.encode("ascii")).decode("utf-8")

        # 设置 cookies 和 session
        self._cookies = parsed_cookies
        self._session = requests.Session()
        self._session.cookies.update(parsed_cookies)
        self._user_id = user_id
        self._user_info = None  # 用户信息将在需要时通过异步方法获取

    def _parse_cookies(self, cookies_str: str) -> Dict[str, str]:
        """将字符串形式的 cookies 转换为字典
        
        :param cookies_str: cookies 字符串，格式如 "key1=value1; key2=value2"
        :return: cookies 字典
        """
        if not cookies_str:
            return {}
            
        cookie_dict = {}
        for cookie in cookies_str.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                key, value = cookie.split('=', 1)  # 只分割第一个 '='
                cookie_dict[key.strip()] = value.strip()
        return cookie_dict

    @property
    def cookies(self) -> Dict[str, str]:
        return self._session.cookies.get_dict()

    @staticmethod
    def _app_id(url: str):
        """根据`url`选择app_id"""

        if PCS_BAIDU_COM in url:
            return PCS_APP_ID
        else:
            return PAN_APP_ID

    @property
    async def bdstoken(self) -> str:
        assert self._stoken or self._cookies.get("STOKEN")

        if self._bdstoken:
            return self._bdstoken

        url = "http://pan.baidu.com/disk/home"
        resp = await self._request(Method.Get, url, params=None)
        cn = resp.text
        mod = re.search(r'bdstoken[\'":]+([0-9a-f]{32})', cn)
        if mod:
            s = mod.group(1)
            self._bdstoken = str(s)
            return s
        return ""

    @staticmethod
    def _headers(url: str):
        """根据`url`选择请求头"""

        if PCS_BAIDU_COM in url:
            return dict(PCS_HEADERS)
        else:
            return dict(PAN_HEADERS)

    def _cookies_update(self, cookies: Dict[str, str]):
        self._session.cookies.update(cookies)

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
        if params and isinstance(params, dict):
            app_id = self._app_id(url)
            params["app_id"] = app_id

        if not headers:
            headers = self._headers(url)

        # if isinstance(data, (MultipartEncoder, MultipartEncoderMonitor)):
        #     assert headers
        #     headers["Content-Type"] = data.content_type

        # 网络请求调试信息
        from backend.common.log import log
        log.info(f"🌐 [网络请求] {method.value} {url}")
        if params:
            log.info(f"🌐 [请求参数] {params}")
        if data and not files:  # 不打印文件上传的data
            if isinstance(data, str) and len(data) > 500:
                log.info(f"🌐 [请求数据] {data[:500]}... (截断)")
            else:
                log.info(f"🌐 [请求数据] {data}")
        if files:
            log.info(f"🌐 [上传文件] {list(files.keys())}")

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
            
            # 网络响应调试信息
            log.info(f"🌐 [响应状态] {resp.status_code}")
            try:
                resp_json = resp.json()
                if isinstance(resp_json, dict):
                    # 只显示关键字段，避免日志过长
                    key_fields = ["errno", "error_code", "error_msg", "message", "list", "info"]
                    summary = {k: v for k, v in resp_json.items() if k in key_fields}
                    if "list" in summary and isinstance(summary["list"], list):
                        summary["list"] = f"列表包含 {len(summary['list'])} 个项目"
                    log.info(f"🌐 [响应摘要] {summary}")
                else:
                    log.info(f"🌐 [响应内容] {resp_json}")
            except:
                # 如果不是JSON响应，显示文本内容的前200字符
                text_content = resp.text[:200]
                log.info(f"🌐 [响应文本] {text_content}{'...' if len(resp.text) > 200 else ''}")
            
            return resp
        except Exception as err:
            log.error(f"🌐 [请求失败] {method.value} {url} - {err}")
            raise BaiduApiError("BaiduApi._request", cause=err)

    async def _request_get(
        self,
        url: str,
        params: Optional[Dict[str, str]] = {},
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        return await self._request(Method.Get, url, params=params, headers=headers)

    @assert_ok
    async def quota(self):
        """配额空间信息"""

        url = PcsNode.Quota.url()
        params = {"method": "info"}
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    async def meta(self, *file_paths: str):
        if not all([p.startswith("/") for p in file_paths]):
            raise BaiduApiError(error_code=-1, message="`file_paths`必须是绝对路径")

        param = [{"path": p} for p in file_paths]
        return await self.file_operate("meta", param)

    async def exists(self, file_path: str) -> bool:
        r = await self.meta(file_path)
        if r.get("error_code"):
            return False
        else:
            return True

    async def is_file(self, file_path: str) -> bool:
        r = await self.meta(file_path)
        if r.get("error_code"):
            return False
        if r["list"][0]["isdir"] == 0:
            return True
        else:
            return False

    async def is_dir(self, file_path: str) -> bool:
        r = await self.meta(file_path)
        if r.get("error_code"):
            return False
        if r["list"][0]["isdir"] == 1:
            return True
        else:
            return False

    @assert_ok
    async def list(
        self,
        file_path: str,
        desc: bool = False,
        name: bool = False,
        time: bool = False,
        size: bool = False,
    ):
        url = PcsNode.File.url()
        orderby = None
        if name:
            orderby = "name"
        elif time:
            orderby = "time"  # 服务器最后修改时间
        elif size:
            orderby = "size"
        else:
            orderby = "name"

        params = {
            "method": "list",
            "by": orderby,
            "limit": "0-2147483647",
            "order": ["asc", "desc"][desc],
            "path": str(file_path),
        }
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    @assert_ok
    async def search(self, keyword: str, file_path: str, recursive: bool = False):
        url = PcsNode.File.url()
        params = {
            "method": "search",
            "path": file_path,
            "wd": keyword,
            "re": "1" if recursive else "0",
        }
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    @assert_ok
    async def makedir(self, directory: str):
        url = PcsNode.File.url()
        params = {
            "method": "mkdir",
            "path": directory,
        }
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    async def file_operate(self, operate: str, param: List[Dict[str, str]]):
        url = PcsNode.File.url()
        params = {"method": operate}
        data = {"param": dump_json({"list": param})}
        resp = await self._request(Method.Post, url, params=params, data=data)
        return resp.json()

    @assert_ok
    def move(self, *file_paths: str):
        """
        将源文件移动到目标文件夹

        sources, dest = file_paths[:-1], file_paths[-1]

        `dest`必须是一个目录
        """

        assert len(file_paths) > 1 and all(
            [p.startswith("/") for p in file_paths]
        ), "`sources`, `dest`必须是绝对路径"

        sources, dest = file_paths[:-1], file_paths[-1]

        if self.is_file(dest):
            raise BaiduApiError("远程`dest`是一个文件。它必须是一个目录。")

        if not self.is_dir(dest):
            self.makedir(dest)

        _sources = (Path(s) for s in sources)
        _dest = Path(dest)

        param = [_from_to(s.as_posix(), (_dest / s.name).as_posix()) for s in _sources]
        return self.file_operate("move", param)

    @assert_ok
    def rename(self, source: str, dest: str):
        """将`source`重命名为`dest`"""

        assert all(
            [p.startswith("/") for p in [source, dest]]
        ), "`source`, `dest`必须是绝对路径"

        param = [_from_to(source, dest)]
        return self.file_operate("move", param)

    @assert_ok
    def copy(self, *file_paths: str):
        """
        将源文件复制到目标文件夹

        sources, dest = file_paths[:-1], file_paths[-1]

        `dest`必须是一个目录
        """

        assert len(file_paths) > 1 and all(
            [p.startswith("/") for p in file_paths]
        ), "`sources`, `dest`必须是绝对路径"

        sources, dest = file_paths[:-1], file_paths[-1]

        if self.is_file(dest):
            raise BaiduApiError("远程`dest`是一个文件。它必须是一个目录。")

        if not self.is_dir(dest):
            self.makedir(dest)

        _sources = (Path(s) for s in sources)
        _dest = Path(dest)

        param = [_from_to(s.as_posix(), (_dest / s.name).as_posix()) for s in _sources]
        return self.file_operate("copy", param)

    @assert_ok
    async def remove(self, *file_paths: str):
        assert all(
            [p.startswith("/") for p in file_paths]
        ), "`sources`, `dest`必须是绝对路径"

        param = [{"path": p} for p in file_paths]
        return await self.file_operate("delete", param)

    @assert_ok
    async def share(self, *file_paths: str, password: str, period: int = 0):
        """将`file_paths`公开分享

        period (int): 过期天数。`0`表示永不过期
        """

        assert self._stoken, "`STOKEN`不在`cookies`中"
        assert len(password) == 4, "`password`必须设置"

        meta = await self.meta(*file_paths)
        fs_ids = [i["fs_id"] for i in meta["list"]]

        url = PanNode.Share.url()
        params = {
            "channel": "chunlei",
            "clienttype": "0",
            "web": "1",
            "bdstoken": await self.bdstoken,
        }
        data = {
            "fid_list": dump_json(fs_ids),
            "schannel": "0",
            "channel_list": "[]",
            "period": str(int(period)),
        }
        if password:
            data["pwd"] = password
            data["schannel"] = "4"

        resp = await self._request(Method.Post, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def list_shared(self, page: int = 1):
        """
        list.0.channel:
            - 0, no password
            - 4, with password
        """

        url = PanNode.SharedRecord.url()
        params = {
            "page": str(page),
            "desc": "1",
            "order": "time",
        }
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    @assert_ok
    async def shared_password(self, share_id: int):
        """
        Only return password
        """

        url = PanNode.SharedPassword.url()
        params = {
            "shareid": str(share_id),
            "sign": calu_md5(f"{share_id}_sharesurlinfo!@#"),
        }
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    @assert_ok
    async def cancel_shared(self, *share_ids: int):
        url = PanNode.SharedCancel.url()
        data = {
            "shareid_list": dump_json(share_ids),
        }
        hdrs = dict(PCS_HEADERS)
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
        resp = await self._request(Method.Post, url, headers=hdrs, params=None, data=data)
        return resp.json()

    def shared_init_url(self, shared_url: str) -> str:
        u = urlparse(shared_url)
        surl = u.path.split("/s/1")[-1]
        return f"https://pan.baidu.com/share/init?surl={surl}"

    @assert_ok
    async def access_shared(self, shared_url: str, password: str, vcode_str: str, vcode: str):
        """向会话传递密码

        警告：此方法不是线程安全的。
        """

        url = "https://pan.baidu.com/share/verify"
        init_url = self.shared_init_url(shared_url)
        params = {
            "surl": init_url.split("surl=")[-1],
            "t": str(now_timestamp() * 1000),
            "channel": "chunlei",
            "web": "1",
            "bdstoken": "null",
            "clienttype": "0",
        }
        data = {
            "pwd": password,
            "vcode": vcode,
            "vcode_str": vcode_str,
        }
        hdrs = dict(PAN_HEADERS)
        hdrs["Referer"] = init_url
        resp = await self._request(Method.Post, url, headers=hdrs, params=params, data=data)

        # 这些cookie必须包含在所有子进程中
        self._cookies_update(resp.cookies.get_dict())

        return resp.json()

    @assert_ok
    async def getcaptcha(self, shared_url: str) -> str:
        url = PanNode.Getcaptcha.url()
        params = {
            "prod": "shareverify",
            "channel": "chunlei",
            "web": "1",
            "bdstoken": "null",
            "clienttype": "0",
        }

        hdrs = dict(PAN_HEADERS)
        hdrs["Referer"] = self.shared_init_url(shared_url)
        hdrs["X-Requested-With"] = "XMLHttpRequest"
        hdrs["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        resp = await self._request(Method.Get, url, headers=hdrs, params=params)
        return resp.json()

    async def get_vcode_img(self, vcode_img_url: str, shared_url: str) -> bytes:
        hdrs = dict(PAN_HEADERS)
        hdrs["Referer"] = self.shared_init_url(shared_url)
        resp = await self._request_get(vcode_img_url, headers=hdrs)
        return resp.content

    @assert_ok
    async def shared_paths(self, shared_url: str):
        """获取共享路径

        调用此函数前先调用`BaiduPCS.access_share`

        警告：此方法不是线程安全的。
        """

        assert self._stoken, "`STOKEN`不在`cookies`中"

        resp = await self._request(Method.Get, shared_url, params=None)
        html = resp.text

        # 这些cookie必须包含在所有子进程中
        self._cookies_update(resp.cookies.get_dict())

        m = re.search(r"(?:yunData.setData|locals.mset)\((.+?)\);", html)
        assert m, "`BaiduPCS.shared_paths`: 无法获取共享信息"

        shared_data = m.group(1)
        return json.loads(shared_data)

    @assert_ok
    async def list_shared_paths(
        self, sharedpath: str, uk: int, share_id: int, page: int = 1, size: int = 100
    ):
        assert self._stoken, "`STOKEN`不在`cookies`中"

        url = PanNode.SharedPathList.url()
        params = {
            "channel": "chunlei",
            "clienttype": "0",
            "web": "1",
            "page": str(page),  # from 1
            "num": str(size),  # max is 100
            "dir": sharedpath,
            "t": str(random.random()),
            "uk": str(uk),
            "shareid": str(share_id),
            "desc": "1",  # reversely
            "order": "other",  # sort by name, or size, time
            "bdstoken": "null",
            "showempty": "0",
        }
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    @assert_ok
    async def transfer_shared_paths(
        self,
        remotedir: str,
        fs_ids: List[int],
        uk: int,
        share_id: int,
        bdstoken: str,
        shared_url: str,
    ):
        """`remotedir`必须存在"""

        url = PanNode.TransferShared.url()
        params = {
            "shareid": str(share_id),
            "from": str(uk),
            "bdstoken": bdstoken,
            "channel": "chunlei",
            "clienttype": "0",
            "web": "1",
        }
        data = {
            "fsidlist": dump_json(fs_ids),
            "path": remotedir,
        }
        hdrs = dict(PAN_HEADERS)
        hdrs["X-Requested-With"] = "XMLHttpRequest"
        hdrs["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        hdrs["Origin"] = "https://pan.baidu.com"
        hdrs["Referer"] = shared_url  # WARNING: Referer must be set to shared_url

        resp = await self._request(Method.Post, url, headers=hdrs, params=params, data=data)
        info = resp.json()
        if info.get("info") and info["info"][0]["errno"]:
            info["errno"] = info["info"][0]["errno"]
        return info

    @assert_ok
    async def user_products(self):
        url = PanNode.UserProducts.url()
        params = {
            "method": "query",
        }
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    @assert_ok
    async def get_user_info(self, **kwargs):
        """获取用户信息
        
        Args:
            **kwargs: 可选参数
                - clienttype: 客户端类型，默认0
                - app_id: 应用ID，默认250528
                - web: 是否web端，默认1
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = f"{PAN_BAIDU_COM}/rest/2.0/membership/user/info"
        params = {
            "method": "query",
            "clienttype": kwargs.pop("clienttype", 0),
            "app_id": kwargs.pop("app_id", 250528),
            "web": kwargs.pop("web", 1)
        }
        
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    @assert_ok
    async def get_quota(self, **kwargs):
        """获取空间配额信息
        
        Args:
            **kwargs: 可选参数
                - clienttype: 客户端类型，默认0
                - app_id: 应用ID，默认250528
                - web: 是否web端，默认1
        
        Returns:
            Dict: 返回空间配额信息
        """
        url = f"{PAN_BAIDU_COM}/api/quota"
        params = {
            "clienttype": kwargs.pop("clienttype", 0),
            "app_id": kwargs.pop("app_id", 250528),
            "web": kwargs.pop("web", 1)
        }
        
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    @assert_ok
    async def get_login_status(self, **kwargs):
        """获取登录状态信息
        
        Args:
            **kwargs: 可选参数
                - clienttype: 客户端类型，默认1
                - app_id: 应用ID，默认250528
                - web: 是否web端，默认1
                - channel: 渠道，默认web
                - version: 版本号，默认0
        
        Returns:
            Dict: 返回登录状态信息
        """
        url = f"{PAN_BAIDU_COM}/api/loginStatus"
        params = {
            "clienttype": kwargs.pop("clienttype", 1),
            "app_id": kwargs.pop("app_id", 250528),
            "web": kwargs.pop("web", 1),
            "channel": kwargs.pop("channel", "web"),
            "version": kwargs.pop("version", 0)
        }
        
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()

    @assert_ok
    async def get_follow_list(self, start: int = 0, limit: int = 20, **kwargs):
        """获取关注列表
        
        Args:
            start: 起始位置，默认0
            limit: 每页数量，默认20
            **kwargs: 可选参数
                - clienttype: 客户端类型，默认0
                - app_id: 应用ID，默认250528
                - web: 是否web端，默认1
        """
        url = PanNode.FollowList.url()
        params = {
            "start": str(start),
            "limit": str(limit),
            "clienttype": kwargs.pop("clienttype", 0),
            "web": kwargs.pop("web", 1)
        }
        
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()
        
    @assert_ok
    async def get_group_list(self, start: int = 0, limit: int = 20, type: int = 0, **kwargs):
        """获取群组列表
        
        Args:
            start: 起始位置，默认0
            limit: 每页数量，默认20
            type: 群组类型，默认0
            **kwargs: 可选参数
                - clienttype: 客户端类型，默认0
                - app_id: 应用ID，默认250528
                - web: 是否web端，默认1
        """
        url = PanNode.GroupList.url()
        params = {
            "start": str(start),
            "limit": str(limit),
            "type": str(type),
            "clienttype": kwargs.pop("clienttype", 0),
            "web": kwargs.pop("web", 1)
        }
        
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()
        
    @assert_ok
    async def get_friend_share_list(self, to_uk: str, type: int = 2, **kwargs):
        """获取好友分享列表
        
        Args:
            to_uk: 好友UK
            type: 分享类型，默认2
            **kwargs: 可选参数
                - clienttype: 客户端类型，默认0
                - app_id: 应用ID，默认250528
                - web: 是否web端，默认1
        """
        url = PanNode.FriendShareList.url()
        params = {
            "clienttype": kwargs.pop("clienttype", 0),
            "web": kwargs.pop("web", 1)
        }
        
        data = {
            "type": str(type),
            "to_uk": to_uk
        }
        
        resp = await self._request(Method.Post, url, params=params, data=data)
        return resp.json()
        
    @assert_ok
    async def get_group_share_list(self, gid: str, type: int = 2, limit: int = 50, desc: int = 1, **kwargs):
        """获取群组分享列表
        
        Args:
            gid: 群组ID
            type: 分享类型，默认2
            limit: 每页数量，默认50
            desc: 是否降序，1降序，0升序，默认1
            **kwargs: 可选参数
                - clienttype: 客户端类型，默认0
                - app_id: 应用ID，默认250528
                - web: 是否web端，默认1
        """
        url = PanNode.GroupShareList.url()
        params = {
            "clienttype": kwargs.pop("clienttype", 0),
            "web": kwargs.pop("web", 1),
            "type": str(type),
            "gid": gid,
            "limit": str(limit),
            "desc": str(desc)
        }
        
        resp = await self._request(Method.Get, url, params=params)
        return resp.json()
        
    @assert_ok
    async def get_friend_share_detail(self, from_uk: str, msg_id: str, to_uk: str, fs_id: str, 
                               type: int = 1, page: int = 1, num: int = 50, **kwargs):
        """获取好友分享详情
        
        Args:
            from_uk: 分享者UK
            msg_id: 消息ID
            to_uk: 接收者UK
            fs_id: 文件ID
            type: 分享类型，默认1
            page: 页码，默认1
            num: 每页数量，默认50
            **kwargs: 可选参数
                - clienttype: 客户端类型，默认0
                - app_id: 应用ID，默认250528
                - web: 是否web端，默认1
        """
        url = PanNode.ShareInfo.url()
        params = {
            "from_uk": from_uk,
            "msg_id": msg_id,
            "to_uk": to_uk,
            "type": str(type),
            "num": str(num),
            "page": str(page),
            "fs_id": fs_id,
            "clienttype": kwargs.pop("clienttype", 0),
            "web": kwargs.pop("web", 1)
        }
        
        resp = await self._request(Method.Post, url, params=params)
        return resp.json()
        
    @assert_ok
    async def get_group_share_detail(self, from_uk: str, msg_id: str, gid: str, fs_id: str,
                              type: int = 2, page: int = 1, num: int = 50, 
                              limit: int = 50, desc: int = 1, **kwargs):
        """获取群组分享详情
        
        Args:
            from_uk: 分享者UK
            msg_id: 消息ID
            gid: 群组ID
            fs_id: 文件ID
            type: 分享类型，默认2
            page: 页码，默认1
            num: 每页数量，默认50
            limit: 列表限制，默认50
            desc: 是否降序，1降序，0升序，默认1
            **kwargs: 可选参数
                - clienttype: 客户端类型，默认0
                - app_id: 应用ID，默认250528
                - web: 是否web端，默认1
        """
        url = PanNode.ShareInfo.url()
        params = {
            "from_uk": from_uk,
            "msg_id": msg_id,
            "type": str(type),
            "num": str(num),
            "page": str(page),
            "fs_id": fs_id,
            "gid": gid,
            "limit": str(limit),
            "desc": str(desc),
            "clienttype": kwargs.pop("clienttype", 0),
            "web": kwargs.pop("web", 1)
        }
        
        resp = await self._request(Method.Post, url, params=params)
        return resp.json()

    @assert_ok
    async def transfer_files(
        self,
        from_uk: str,
        to_uk: str,
        msg_id: str,
        fs_ids: List[Union[int, str]],
        path: str = "/我的资源",
        type: int = 1,
        ondup: str = "newcopy",
        **kwargs
    ):
        """转存文件
        
        Args:
            from_uk: 分享者UK
            to_uk: 接收者UK
            msg_id: 消息ID
            fs_ids: 文件ID列表
            path: 保存路径，默认为"/我的资源"
            type: 分享类型，默认1（好友分享）, 2为群组分享
            ondup: 重名处理方式，默认"newcopy"，可选"skip"跳过
            **kwargs: 可选参数
                - channel: 渠道，默认chunlei
                - clienttype: 客户端类型，默认0
                - app_id: 应用ID，默认250528
                - web: 是否web端，默认1
                - async: 是否异步，默认1
                - gid: 当type=2(群组分享)时的群组ID
        """
        url = PanNode.ShareTransfer.url()
        
        # 确保所有参数都是字符串类型
        params = {
            "channel": str(kwargs.pop("channel", "chunlei")),
            "clienttype": str(kwargs.pop("clienttype", 0)),
            "web": str(kwargs.pop("web", 1)),
            "logId": str(self._logid) if self._logid else "",
            "bdstoken": str(await self.bdstoken)
        }
        
        # 确保 fs_ids 中的每个元素都是字符串
        fs_ids_str = [str(fs_id) for fs_id in fs_ids]
        
        data = {
            "from_uk": str(from_uk),
            "to_uk": str(to_uk),
            "msg_id": str(msg_id),
            "path": str(path),
            "ondup": str(ondup),
            "async": str(kwargs.pop("async", 1)),
            "fs_ids": dump_json(fs_ids_str),
            "type": str(type)
        }
        
        # 如果是群组分享类型且提供了gid，则添加到请求体中
        gid = kwargs.pop("gid", None)
        if type == 2 and gid:
            data["gid"] = str(gid)
        
        try:
            resp = await self._request(Method.Post, url, params=params, data=data)
            return resp.json()
        except Exception as e:
            raise
