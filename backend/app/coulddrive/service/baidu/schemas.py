from typing import Optional, List, Dict, NamedTuple
from collections import namedtuple
from urllib.parse import unquote

from base64 import standard_b64encode

import os

class PcsFile(NamedTuple):
    """
    百度网盘文件

    path: str  # 远程绝对路径
    is_dir: Optional[bool] = None
    is_file: Optional[bool] = None
    fs_id: Optional[int] = None  # 文件ID
    size: Optional[int] = None
    md5: Optional[str] = None
    block_list: Optional[List[str]] = None  # 分块MD5列表
    category: Optional[int] = None
    user_id: Optional[int] = None
    ctime: Optional[int] = None  # 服务器创建时间
    mtime: Optional[int] = None  # 服务器修改时间
    local_ctime: Optional[int] = None  # 本地创建时间
    local_mtime: Optional[int] = None  # 本地修改时间
    server_ctime: Optional[int] = None  # 服务器创建时间
    server_mtime: Optional[int] = None  # 服务器修改时间
    shared: Optional[bool] = None  # 如果为True，表示此文件已共享
    """

    path: str  # remote absolute path
    is_dir: Optional[bool] = None
    is_file: Optional[bool] = None
    fs_id: Optional[int] = None  # file id
    size: Optional[int] = None
    md5: Optional[str] = None
    block_list: Optional[List[str]] = None  # block md5 list
    category: Optional[int] = None
    user_id: Optional[int] = None
    ctime: Optional[int] = None  # server created time
    mtime: Optional[int] = None  # server modifed time
    local_ctime: Optional[int] = None  # local created time
    local_mtime: Optional[int] = None  # local modifed time
    server_ctime: Optional[int] = None  # server created time
    server_mtime: Optional[int] = None  # server modifed time
    shared: Optional[bool] = None  # this file is shared if True
    dl_link: Optional[str] = None

    @staticmethod
    def from_(info) -> "PcsFile":
        return PcsFile(
            path=info.get("path"),
            is_dir=info.get("isdir") == 1,
            is_file=info.get("isdir") == 0,
            fs_id=info.get("fs_id"),
            size=info.get("size"),
            md5=info.get("md5"),
            block_list=info.get("block_list"),
            category=info.get("category"),
            user_id=info.get("user_id"),
            ctime=info.get("ctime"),
            mtime=info.get("mtime"),
            local_ctime=info.get("local_ctime"),
            local_mtime=info.get("local_mtime"),
            server_ctime=info.get("server_ctime"),
            server_mtime=info.get("server_mtime"),
            shared=info.get("shared"),
        )



class PcsSharedLink(NamedTuple):
    url: str
    paths: Optional[List[str]] = None
    fs_ids: Optional[List[int]] = None
    password: Optional[str] = None

    # The remained second before expiring.
    # -1 means being expired
    expired: Optional[int] = None

    # channel == 4, has password
    channel: Optional[bool] = None

    share_id: Optional[int] = None
    ctime: Optional[int] = None

    @staticmethod
    def from_(info) -> "PcsSharedLink":
        return PcsSharedLink(
            url=info.get("link") or info.get("shortlink"),
            paths=info.get("paths") or [info.get("typicalPath")],
            fs_ids=info.get("fsIds"),
            password=info.get("password"),
            expired=info.get("expiredTime") if info.get("expiredType") != -1 else -1,
            channel=info.get("channel"),
            share_id=info.get("share_id") or info.get("shareId") or info.get("shareid"),
            ctime=info.get("ctime"),
        )

    def has_password(self) -> bool:
        if self.password:
            return True
        if self.channel == 4:
            return True
        return False

    def available(self) -> bool:
        if not self.paths:
            return False
        if self.paths[0].startswith("/"):
            return True
        else:
            return False


class PcsSharedPath(NamedTuple):
    """
    用户共享路径

    `sharedpath`: 原始共享路径
    `remotepath`: 保存`sharedpath`的目录
    """

    fs_id: int
    path: str
    size: int
    is_dir: bool
    is_file: bool
    md5: Optional[str] = None
    local_ctime: Optional[int] = None  # local created time
    local_mtime: Optional[int] = None  # local modifed time
    server_ctime: Optional[int] = None  # server created time
    server_mtime: Optional[int] = None  # server modifed time

    uk: Optional[int] = None
    share_id: Optional[int] = None
    bdstoken: Optional[str] = None

    @staticmethod
    def from_(info) -> "PcsSharedPath":
        if "parent_path" in info:
            path = unquote(info["parent_path"] or "") + "/" + info["server_filename"]
        else:
            path = info["path"]
        return PcsSharedPath(
            fs_id=info.get("fs_id"),
            path=path,
            size=info.get("size"),
            is_dir=info.get("isdir") == 1,
            is_file=info.get("isdir") == 0,
            md5=info.get("md5"),
            local_ctime=info.get("local_ctime"),
            local_mtime=info.get("local_mtime"),
            server_ctime=info.get("server_ctime"),
            server_mtime=info.get("server_mtime"),
            uk=info.get("uk"),
            share_id=info.get("share_id") or info.get("shareid"),
            bdstoken=info.get("bdstoken"),
        )


FromTo = namedtuple("FromTo", ["from_", "to_"])


class PcsQuota(NamedTuple):
    quota: int
    used: int


class PcsAuth(NamedTuple):
    bduss: str
    cookies: Dict[str, Optional[str]]
    stoken: Optional[str] = None
    ptoken: Optional[str] = None


class PcsUserProduct(NamedTuple):
    name: str
    start_time: int  # second
    end_time: int  # second


class PcsUser(NamedTuple):
    user_id: int
    user_name: Optional[str] = None
    auth: Optional[PcsAuth] = None
    age: Optional[float] = None
    sex: Optional[str] = None
    quota: Optional[PcsQuota] = None
    products: Optional[List[PcsUserProduct]] = None
    level: Optional[int] = None


