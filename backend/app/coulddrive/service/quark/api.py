#api.py
from typing import List, Optional, Dict, Any, Union
from enum import Enum

import requests

from .errors import QuarkApiError, assert_ok

# API 基础URL
PAN_QUARK_COM = "https://pan.quark.cn"
PC_QUARK_CN = "https://drive-pc.quark.cn"
H_QUARK_CN = "https://drive-h.quark.cn"

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
    """使用pan.quark.cn的网盘节点"""
    Account= "account/info"

    def url(self) -> str:
        return f"{PAN_QUARK_COM}/{self.value}"
    
class PCNode(Enum):
    """使用drive-pc.quark.cn的网盘节点"""
    Member = "/1/clouddrive/member"
    FileList = "/1/clouddrive/file/sort"
    FileCreate = "/1/clouddrive/file"
    FileRename = "/1/clouddrive/file/rename"
    FileMove = "/1/clouddrive/file/move"
    FileCopy = "/1/clouddrive/file/copy"
    FileDelete = "/1/clouddrive/file/delete"
    ShareList = "/1/clouddrive/share/mypage/detail"
    ShareCreate = "/1/clouddrive/share"
    ShareDelete = "/1/clouddrive/share/delete"
    ShareSave = "/1/clouddrive/share/sharepage/save"
    SharePasswd = "/1/clouddrive/share/password"
    ShareToken = "/1/clouddrive/share/sharepage/token"
    ShareDetail = "/1/clouddrive/share/sharepage/detail"
    TaskQuery = "/1/clouddrive/task"
    FileInfoPath = "/1/clouddrive/file/info/path_list"

    def url(self) -> str:
        return f"{PC_QUARK_CN}{self.value}"

class HNode(Enum):
    """使用drive-h.quark.cn的网盘节点"""
    ShareToken = "/1/clouddrive/share/sharepage/token"
    ShareDetail = "/1/clouddrive/share/sharepage/detail"

    def url(self) -> str:
        return f"{H_QUARK_CN}{self.value}"

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
            headers = PAN_HEADERS.copy()

        # 如果是POST请求且data是字典，转换为JSON
        if method == Method.POST and isinstance(data, dict):
            import json
            headers["Content-Type"] = "application/json"
            data = json.dumps(data)

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
            from backend.common.log import log
            log.error(f"🌐 [请求失败] {method.value} {url} - {err}")
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
    async def get_member_info(self, **kwargs):
        """获取用户会员信息
        
        Args:
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
                - fetch_subscribe: 是否获取订阅信息，默认true
                - _ch: 渠道，默认home
                - fetch_identity: 是否获取身份信息，默认true
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.Member.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", ""),
            "fetch_subscribe": kwargs.pop("fetch_subscribe", "true"),
            "_ch": kwargs.pop("_ch", "home"),
            "fetch_identity": kwargs.pop("fetch_identity", "true")
        }
        
        resp = await self._request(Method.GET, url, params=params)
        return resp.json()

    @assert_ok
    async def get_account_info(self, **kwargs):
        """获取账户信息
        
        Args:
            **kwargs: 可选参数
                - fr: 来源标识，默认pc
                - platform: 平台标识，默认pc
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PanNode.Account.url()
        params = {
            "fr": kwargs.pop("fr", "pc"),
            "platform": kwargs.pop("platform", "pc")
        }
        
        resp = await self._request(Method.GET, url, params=params)
        return resp.json()

    @assert_ok
    async def list_files(
        self,
        pdir_fid: str = "0",
        page: int = 1,
        size: int = 50,
        sort: str = "file_type:asc,file_name:asc",
        **kwargs
    ):
        """获取文件列表
        
        Args:
            pdir_fid: 父目录ID，默认为"0"（根目录）
            page: 页码，默认为1
            size: 每页数量，默认为50
            sort: 排序方式，默认为"file_type:asc,file_name:asc"
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
                - _fetch_total: 是否获取总数，默认1
                - _fetch_sub_dirs: 是否获取子目录，默认0
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.FileList.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", ""),
            "pdir_fid": str(pdir_fid),
            "_page": str(page),
            "_size": str(size),
            "_fetch_total": str(kwargs.pop("_fetch_total", 1)),
            "_fetch_sub_dirs": str(kwargs.pop("_fetch_sub_dirs", 0)),
            "_sort": sort
        }
        
        resp = await self._request(Method.GET, url, params=params)
        return resp.json()

    @assert_ok
    async def delete_files(
        self,
        file_ids: List[str],
        action_type: int = 2,
        exclude_fids: Optional[List[str]] = None,
        **kwargs
    ):
        """删除文件
        
        Args:
            file_ids: 要删除的文件ID列表
            action_type: 操作类型，默认为2
            exclude_fids: 排除的文件ID列表，默认为空列表
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.FileDelete.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", "")
        }
        
        data = {
            "action_type": action_type,
            "filelist": file_ids,
            "exclude_fids": exclude_fids or []
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def query_task(
        self,
        task_id: str,
        retry_index: int = 0,
        **kwargs
    ):
        """查询任务状态
        
        Args:
            task_id: 任务ID
            retry_index: 重试索引，默认为0
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.TaskQuery.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", ""),
            "task_id": task_id,
            "retry_index": str(retry_index)
        }
        
        resp = await self._request(Method.GET, url, params=params)
        return resp.json()

    @assert_ok
    async def create_folder(
        self,
        pdir_fid: str,
        file_name: str,
        dir_path: str = "",
        dir_init_lock: bool = False,
        **kwargs
    ):
        """创建文件夹
        
        Args:
            pdir_fid: 父目录ID
            file_name: 文件夹名称
            dir_path: 目录路径，默认为空
            dir_init_lock: 目录初始化锁，默认为False
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.FileCreate.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", "")
        }
        
        data = {
            "pdir_fid": pdir_fid,
            "file_name": file_name,
            "dir_path": dir_path,
            "dir_init_lock": dir_init_lock
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def rename_file(
        self,
        fid: str,
        file_name: str,
        **kwargs
    ):
        """重命名文件
        
        Args:
            fid: 文件ID
            file_name: 新文件名
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.FileRename.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", "")
        }
        
        data = {
            "fid": fid,
            "file_name": file_name
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def move_files(
        self,
        file_ids: List[str],
        to_pdir_fid: str,
        action_type: int = 1,
        exclude_fids: Optional[List[str]] = None,
        **kwargs
    ):
        """移动文件
        
        Args:
            file_ids: 要移动的文件ID列表
            to_pdir_fid: 目标父目录ID
            action_type: 操作类型，默认为1
            exclude_fids: 排除的文件ID列表，默认为空列表
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.FileMove.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", "")
        }
        
        data = {
            "action_type": action_type,
            "to_pdir_fid": to_pdir_fid,
            "filelist": file_ids,
            "exclude_fids": exclude_fids or []
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def copy_files(
        self,
        file_ids: List[str],
        to_pdir_fid: str,
        action_type: int = 1,
        exclude_fids: Optional[List[str]] = None,
        **kwargs
    ):
        """复制文件
        
        Args:
            file_ids: 要复制的文件ID列表
            to_pdir_fid: 目标父目录ID
            action_type: 操作类型，默认为1
            exclude_fids: 排除的文件ID列表，默认为空列表
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.FileCopy.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", "")
        }
        
        data = {
            "action_type": action_type,
            "to_pdir_fid": to_pdir_fid,
            "filelist": file_ids,
            "exclude_fids": exclude_fids or []
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def get_share_page(
        self,
        page: int = 1,
        size: int = 50,
        order_field: str = "created_at",
        order_type: str = "desc",
        **kwargs
    ):
        """获取分享列表
        
        Args:
            page: 页码，默认为1
            size: 每页数量，默认为50
            order_field: 排序字段，默认为"created_at"
            order_type: 排序类型，默认为"desc"
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
                - _fetch_total: 是否获取总数，默认1
                - _fetch_notify_follow: 是否获取通知关注，默认1
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.ShareList.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", ""),
            "_page": str(page),
            "_size": str(size),
            "_order_field": order_field,
            "_order_type": order_type,
            "_fetch_total": str(kwargs.pop("_fetch_total", 1)),
            "_fetch_notify_follow": str(kwargs.pop("_fetch_notify_follow", 1))
        }
        
        resp = await self._request(Method.GET, url, params=params)
        return resp.json()

    @assert_ok
    async def cancel_shared(
        self,
        share_ids: List[str],
        **kwargs
    ):
        """删除分享
        
        Args:
            share_ids: 要删除的分享ID列表
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.ShareDelete.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", "")
        }
        
        data = {
            "share_ids": share_ids
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def create_share(
        self,
        fid_list: List[str],
        title: str,
        url_type: int = 1,
        expired_type: int = 1,
        **kwargs
    ):
        """创建分享
        
        Args:
            fid_list: 要分享的文件ID列表
            title: 分享标题
            url_type: URL类型，默认为1
            expired_type: 过期类型，默认为1
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.ShareCreate.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", "")
        }
        
        data = {
            "fid_list": fid_list,
            "title": title,
            "url_type": url_type,
            "expired_type": expired_type
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def get_share_password(
        self,
        share_id: str,
        **kwargs
    ):
        """获取分享密码
        
        Args:
            share_id: 分享ID
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        url = PCNode.SharePasswd.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", "")
        }
        
        data = {
            "share_id": share_id
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def get_share_token(
        self,
        pwd_id: str,
        passcode: str = "",
        support_visit_limit_private_share: bool = True,
        **kwargs
    ):
        """获取分享token
        
        Args:
            pwd_id: 密码ID
            passcode: 访问密码，默认为空
            support_visit_limit_private_share: 是否支持访问限制私有分享，默认True
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
                - __dt: 时间戳差值
                - __t: 时间戳
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        import time
        current_time = int(time.time() * 1000)
        
        url = HNode.ShareToken.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", ""),
            "__dt": str(kwargs.pop("__dt", 653)),
            "__t": str(kwargs.pop("__t", current_time))
        }
        
        data = {
            "pwd_id": pwd_id,
            "passcode": passcode,
            "support_visit_limit_private_share": support_visit_limit_private_share
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def get_share_detail(
        self,
        pwd_id: str,
        stoken: str,
        pdir_fid: str = "0",
        page: int = 1,
        size: int = 50,
        sort: str = "file_type:asc,file_name:asc",
        **kwargs
    ):
        """获取分享详情
        
        Args:
            pwd_id: 密码ID
            stoken: 分享token
            pdir_fid: 父目录ID，默认为"0"
            page: 页码，默认为1
            size: 每页数量，默认为50
            sort: 排序方式，默认为"file_type:asc,file_name:asc"
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
                - force: 强制刷新，默认0
                - _fetch_banner: 是否获取横幅，默认1
                - _fetch_share: 是否获取分享信息，默认1
                - _fetch_total: 是否获取总数，默认1
                - __dt: 时间戳差值
                - __t: 时间戳
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        import time
        current_time = int(time.time() * 1000)
        
        url = HNode.ShareDetail.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", ""),
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": str(pdir_fid),
            "force": str(kwargs.pop("force", 0)),
            "_page": str(page),
            "_size": str(size),
            "_fetch_banner": str(kwargs.pop("_fetch_banner", 1)),
            "_fetch_share": str(kwargs.pop("_fetch_share", 1)),
            "_fetch_total": str(kwargs.pop("_fetch_total", 1)),
            "_sort": sort,
            "__dt": str(kwargs.pop("__dt", 887)),
            "__t": str(kwargs.pop("__t", current_time))
        }
        
        resp = await self._request(Method.GET, url, params=params)
        return resp.json()

    @assert_ok
    async def get_file_info_by_path(
        self,
        file_paths: List[str],
        **kwargs
    ):
        """根据路径获取文件信息
        
        Args:
            file_paths: 文件路径列表
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
                - __dt: 时间戳差值
                - __t: 时间戳
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        import time
        current_time = int(time.time() * 1000)
        
        url = PCNode.FileInfoPath.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", ""),
            "__dt": str(kwargs.pop("__dt", 1215)),
            "__t": str(kwargs.pop("__t", current_time))
        }
        
        data = {
            "file_path": file_paths
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

    @assert_ok
    async def save_shared_files(
        self,
        pwd_id: str,
        stoken: str,
        to_pdir_fid: str,
        pdir_fid: str = "",
        pack_dir_name: str = "",
        pdir_save_all: bool = True,
        scene: str = "link",
        fid_list: Optional[List[str]] = None,
        fid_token_list: Optional[List[str]] = None,
        exclude_fids: Optional[List[str]] = None,
        **kwargs
    ):
        """保存分享文件
        
        Args:
            pwd_id: 密码ID
            stoken: 分享token
            to_pdir_fid: 目标父目录ID
            pdir_fid: 源父目录ID，默认为空
            pack_dir_name: 打包目录名，默认为空
            pdir_save_all: 是否保存全部，默认True
            scene: 场景，默认为"link"
            fid_list: 文件ID列表，默认为空列表
            fid_token_list: 文件token列表，默认为空列表
            exclude_fids: 排除的文件ID列表，默认为空列表
            **kwargs: 可选参数
                - pr: 产品标识，默认ucpro
                - fr: 来源标识，默认pc
                - uc_param_str: UC参数字符串，默认空
                - __dt: 时间戳差值
                - __t: 时间戳
        
        Returns:
            Dict: 返回原始 JSON 响应
        """
        import time
        current_time = int(time.time() * 1000)
        
        url = PCNode.ShareSave.url()
        params = {
            "pr": kwargs.pop("pr", "ucpro"),
            "fr": kwargs.pop("fr", "pc"),
            "uc_param_str": kwargs.pop("uc_param_str", ""),
            "__dt": str(kwargs.pop("__dt", 346163)),
            "__t": str(kwargs.pop("__t", current_time))
        }
        
        data = {
            "fid_list": fid_list or [],
            "fid_token_list": fid_token_list or [],
            "to_pdir_fid": to_pdir_fid,
            "pack_dir_name": pack_dir_name,
            "pdir_fid": pdir_fid,
            "pdir_save_all": pdir_save_all,
            "pwd_id": pwd_id,
            "scene": scene,
            "stoken": stoken,
            "exclude_fids": exclude_fids or []
        }
        
        resp = await self._request(Method.POST, url, params=params, data=data)
        return resp.json()

