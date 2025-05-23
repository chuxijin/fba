from __future__ import annotations
import os
from collections import deque
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import IO, Callable, Dict, List, Optional, Set, Tuple, Union, Any
import re
from datetime import datetime
import time
import logging # Import standard logging
import asyncio

from PIL import Image

from app.client.coulddrive.server import ItemFilter
from app.schemas.enum import RecursionSpeed
from app.schemas.coulddrive.file import BaseFileInfo
# from fastapi import logger # Remove fastapi.logger import

from ..drivebase_service import BaseDrive
from app.schemas.coulddrive.user import BaseUserInfo, UserFriend, UserGroup
from .schemas import (
    FromTo,
    PcsFile,
    PcsQuota,
    PcsSharedLink,
    PcsSharedPath,
)
from .api import BaiduApi, BaiduApiError

SHARED_URL_PREFIX = "https://pan.baidu.com/s/"


def _unify_shared_url(url: str) -> str:
    """统一输入的分享链接格式"""

    # For Standard url
    temp = r"pan\.baidu\.com/s/(.+?)(\?|$)"
    m = re.search(temp, url)
    if m:
        return SHARED_URL_PREFIX + m.group(1)

    # For surl url
    temp = r"baidu\.com.+?\?surl=(.+?)(\?|$)"
    m = re.search(temp, url)
    if m:
        return SHARED_URL_PREFIX + "1" + m.group(1)

    raise ValueError(f"The shared url is not a valid url. {url}")


class BaiduClient(BaseDrive):
    """百度网盘 PCS API

    这是对`BaiduPCS`的封装。它将原始BaiduPCS请求的响应内容解析为一些内部数据结构。
    """

    def __init__(
        self,
        bduss: Optional[str] = None,
        stoken: Optional[str] = None,
        ptoken: Optional[str] = None,
        cookies: Dict[str, Optional[str]] = {},
        user_id: Optional[int] = None,
    ):
        super().__init__()
        self._baidupcs = BaiduApi(
            bduss, stoken=stoken, ptoken=ptoken, cookies=cookies, user_id=user_id
        )
        # self.logger = logger # Remove assignment of fastapi.logger
        self.logger = logging.getLogger(f"BaiduClient.{self.__class__.__name__}") # Use standard Python logger
        # Configure logger if needed (e.g., set level, add handler), 
        # or assume it's configured globally by the application using the client.
        # For basic output during testing if no global config:
        if not self.logger.handlers:
            # If no handlers are configured, add a basic one to see output.
            # This is often good for library code that might be used outside a pre-configured app.
            # However, generally, libraries should not configure logging handlers themselves.
            # For now, let's assume the calling environment (like test script or app) might set it up.
            # If logs don't appear in tests, uncomment and refine the above handler setup.
            pass # Let's assume for now the calling environment (like test script or app) might set it up.
                 # If logs don't appear in tests, uncomment and refine the above handler setup.

        self._is_authorized = bool(bduss)

    @property
    def drive_type(self) -> str:
        return "BaiduDrive"

    def login(self, bduss: Optional[str] = None, stoken: Optional[str] = None, ptoken: Optional[str] = None, cookies: Dict[str, Optional[str]] = {}, user_id: Optional[int] = None) -> bool:
        """
        登录百度网盘
        如果提供了参数，则使用新参数重新初始化 BaiduPCS 实例。
        否则，检查现有实例是否认为已授权。
        """
        if bduss:
            try:
                self._baidupcs = BaiduApi(
                    bduss, stoken=stoken, ptoken=ptoken, cookies=cookies, user_id=user_id
                )
                if self._baidupcs._bduss:
                    self._is_authorized = True
                    return True
                self._is_authorized = False
                return False
            except Exception as e:
                self.logger.error(f"百度网盘登录失败: {e}")
                self._is_authorized = False
                return False
        return self._is_authorized

    @property
    def bduss(self) -> str:
        return self._baidupcs._bduss

    @property
    def bdstoken(self) -> str:
        return self._baidupcs.bdstoken

    @property
    def stoken(self) -> Optional[str]:
        return self._baidupcs._stoken

    @property
    def ptoken(self) -> Optional[str]:
        return self._baidupcs._ptoken

    @property
    def baiduid(self) -> Optional[str]:
        return self._baidupcs._baiduid

    @property
    def logid(self) -> Optional[str]:
        return self._baidupcs._logid

    @property
    def user_id(self) -> Optional[int]:
        return self._baidupcs._user_id

    @property
    def cookies(self) -> Dict[str, Optional[str]]:
        return self._baidupcs.cookies

    async def quota(self) -> PcsQuota:
        """获取配额信息"""

        info = await self._baidupcs.quota()
        return PcsQuota(quota=info["quota"], used=info["used"])

    async def get_user_info(self) -> BaseUserInfo:
        """获取用户信息，包括配额信息"""
        try:
            # 并行获取用户信息和配额信息
            user_info_task = self._baidupcs.get_user_info()
            quota_task = self._baidupcs.get_quota()
            
            # 使用 await 等待 gather 完成
            results = await asyncio.gather(
                user_info_task, quota_task, 
                return_exceptions=True
            )
            user_info_response, quota_response = results
  
            # 检查是否有任何任务抛出异常
            if isinstance(user_info_response, Exception):
                raise user_info_response
            if isinstance(quota_response, Exception):
                self.logger.warning(f"获取配额信息失败: {quota_response}")
                quota_response = {}

            # 解析用户信息 - 百度API响应格式固定，用户信息在user_info字段中
            if not isinstance(user_info_response, dict):
                raise ValueError("Invalid user info response format")
                
            user_info = user_info_response.get("user_info", {})
            if not isinstance(user_info, dict):
                raise ValueError("Invalid user info data structure")

            # 获取用户ID并更新客户端实例
            try:
                user_id = int(user_info.get("uk")) if user_info.get("uk") is not None else None
                if user_id and not self._baidupcs._user_id:
                    self._baidupcs._user_id = user_id
            except (TypeError, ValueError) as e:
                self.logger.error(f"解析用户ID时出错: {e}")
                user_id = None

            return BaseUserInfo(
                user_id=str(user_id) if user_id is not None else None,
                username=user_info.get("username"),
                avatar_url=user_info.get("photo"),
                quota=quota_response.get("total"),
                used=quota_response.get("used"),
                is_vip=bool(user_info.get("is_vip") == 1),
                is_supervip=bool(user_info.get("is_svip") == 1),
            )
        except BaiduApiError as e:
            self.logger.error(f"获取用户信息失败: {e.message}")
            return BaseUserInfo(
                username="获取失败", 
                **{"error": f"Failed to get user info: {e.message}", "errno": e.error_code}
            )
        except Exception as e:
            self.logger.error(f"获取用户信息时发生未知错误: {str(e)}")
            return BaseUserInfo(
                username="获取失败", 
                **{"error": f"Unknown error while getting user info: {str(e)}"}
            )
    
    async def meta(self, *file_paths: str) -> List[PcsFile]:
        """获取`file_paths`的元数据"""

        info = await self._baidupcs.meta(*file_paths)
        return [PcsFile.from_(v) for v in info.get("list", [])]

    async def exists(self, file_path: str) -> bool:
        """检查`file_path`是否存在"""

        return await self._baidupcs.exists(file_path)

    async def is_file(self, file_path: str) -> bool:
        """检查`file_path`是否是文件"""

        return await self._baidupcs.is_file(file_path)

    async def is_dir(self, file_path: str) -> bool:
        """检查`file_path`是否是目录"""

        return await self._baidupcs.is_dir(file_path)

    async def get_disk_list(
        self,
        file_path: str,
        file_id: str,
        recursive: bool = False,
        desc: bool = False,
        name: bool = False,
        time: bool = False,
        size: bool = False,
        recursion_speed: RecursionSpeed = RecursionSpeed.NORMAL,
        item_filter: Optional[ItemFilter] = None, # Added item_filter
        *args: Any,
        **kwargs: Any
    ) -> List[BaseFileInfo]:
        """列出目录内容，并构建 parent_id.
        
        Args:
            file_path (str): 要列出内容的目录路径。
            file_id (str): 必须是 file_path 对应的目录的 fs_id。用于设置子项的 parent_id。
                           对于根目录 '/', 通常传递 "" 或特定的根ID（如果知道）。
            recursive (bool): 是否递归获取所有子项。
            desc (bool): 按降序排序。
            name (bool): 按名称排序。
            time (bool): 按时间排序。
            size (bool): 按大小排序。
            recursion_speed (RecursionSpeed): 递归获取时的速度控制（默认 NORMAL）。SLOW 模式会在请求子目录前暂停3秒。
                                            FAST 模式预留用于数据库缓存（未实现）。
            item_filter (Optional[ItemFilter]): 过滤器，用于过滤目录项
            *args: 其他位置参数。
            **kwargs: 其他关键字参数。
            
        Returns:
            List[BaseFileInfo]: 包含文件/目录信息的列表，已填充 parent_id。
        """

        drive_files_list: List[BaseFileInfo] = []
        initial_parent_id = file_id

        try:
            info = await self._baidupcs.list(
                file_path, desc=desc, name=name, time=time, size=size
            )
            initial_items_raw = info.get("list", [])
        except Exception as e:
            self.logger.error(f"Error listing path '{file_path}': {e}") # Added more context to log
            return []

        items_to_process = deque()
        # Convert initial items to BaseFileInfo for potential early filtering of initial target folders
        for item_dict_initial in initial_items_raw:
            # Create a preliminary BaseFileInfo for filtering checks, parent_id for these top items is initial_parent_id
            # We need to be careful here if file_path is a file itself. get_disk_list usually lists a dir.
            # Assuming for now that if file_path points to a file, initial_items_raw will contain that one file.
            temp_df_for_filter = BaseFileInfo(
                file_id=str(item_dict_initial.get('fs_id', '')),
                file_path=item_dict_initial.get('path', ''),
                file_name=item_dict_initial.get('server_filename', ''),
                is_folder=bool(item_dict_initial.get('isdir', 0)),
                # Other fields can be dummy or minimal for filtering purposes if not used by filter rules
                file_size=item_dict_initial.get('size'),
                created_at=str(item_dict_initial.get('server_ctime', '')),
                updated_at=str(item_dict_initial.get('server_mtime', '')),
                parent_id=str(initial_parent_id) if initial_parent_id is not None else ""
            )
            if item_filter and item_filter.should_exclude(temp_df_for_filter):
                self.logger.debug(f"[Filter] Excluding initial item: {temp_df_for_filter.file_path}")
                continue
            items_to_process.append((item_dict_initial, initial_parent_id))
        
        # items_to_process = deque([(item_dict, initial_parent_id) for item_dict in initial_items_raw])
        all_processed_data = []
        processed_fs_ids = set()

        while items_to_process:
            item_dict, current_parent_id = items_to_process.popleft()
            all_processed_data.append((item_dict, current_parent_id))

            current_fs_id = item_dict.get('fs_id')
            is_dir = bool(item_dict.get('isdir'))
            current_item_path = item_dict.get('path')

            if is_dir and recursive and current_fs_id and current_fs_id not in processed_fs_ids:
                # Before fetching sub-directory content, check if this directory itself should be filtered out
                # We need a BaseFileInfo representation of this directory to pass to the filter
                current_dir_drive_file = BaseFileInfo(
                    file_id=str(current_fs_id),
                    file_path=str(current_item_path),
                    file_name=PurePosixPath(str(current_item_path)).name, # Approximate name
                    is_folder=True,
                    parent_id=str(current_parent_id) if current_parent_id is not None else "",
                    # Minimal other fields, assuming filter primarily uses path/name/is_folder
                    file_size=0, created_at="0", updated_at="0" 
                )
                if item_filter and item_filter.should_exclude(current_dir_drive_file):
                    self.logger.debug(f"[Filter] Excluding directory from recursion: {current_item_path}")
                else:
                    if current_item_path:
                        processed_fs_ids.add(current_fs_id)
                        if recursion_speed == RecursionSpeed.FAST:
                            self.logger.debug(f"Fast mode (disk): Skipping recursion for sub-directory: {current_item_path}")
                        elif recursion_speed == RecursionSpeed.SLOW:
                            self.logger.debug(f"Slow mode (disk): Pausing for 3s before listing {current_item_path}...")
                            time.sleep(3)
                    
                        try:
                            sub_info = await self._baidupcs.list(
                                current_item_path, desc=desc, name=name, time=time, size=size
                            )
                            sub_list = sub_info.get("list", [])
                            for sub_item_dict in sub_list:
                                temp_sub_df = BaseFileInfo(
                                    file_id=str(sub_item_dict.get('fs_id', '')),
                                    file_path=sub_item_dict.get('path', ''),
                                    file_name=sub_item_dict.get('server_filename', ''),
                                    is_folder=bool(sub_item_dict.get('isdir', 0)),
                                    file_size=sub_item_dict.get('size'),
                                    created_at=str(sub_item_dict.get('server_ctime', '')),
                                    updated_at=str(sub_item_dict.get('server_mtime', '')),
                                    parent_id=str(current_fs_id) # Parent is the current directory being processed
                                )
                                if item_filter and item_filter.should_exclude(temp_sub_df):
                                    self.logger.debug(f"[Filter] Excluding sub-item: {temp_sub_df.file_path}")
                                    continue
                                items_to_process.append((sub_item_dict, current_fs_id))
                        except Exception as e:
                            self.logger.error(f"Error listing subdirectory '{current_item_path}': {e}")
                            # pass # Changed from pass to allow flow to continue if a subdir fails

        explicit_raw_keys = {
            "fs_id", "path", "server_filename", "size", "isdir", 
            "server_ctime", "server_mtime"
        }
        
        for item_dict, parent_id_for_item in all_processed_data:
            file_ext_val = {
                k: v for k, v in item_dict.items() if k not in explicit_raw_keys
            }

            file_instance = BaseFileInfo(
                file_id=str(item_dict.get('fs_id', '')),
                file_path=item_dict.get('path', ''),
                file_name=item_dict.get('server_filename', ''),
                file_size=item_dict.get('size'),
                is_folder=bool(item_dict.get('isdir', 0)),
                created_at=str(item_dict.get('server_ctime', '')), 
                updated_at=str(item_dict.get('server_mtime', '')), 
                parent_id=str(parent_id_for_item) if parent_id_for_item is not None else "",
                #file_ext=file_ext_val,
            )
            drive_files_list.append(file_instance)
        return drive_files_list

    def search(
        self, keyword: str, file_path: str, recursive: bool = False
    ) -> List[PcsFile]:
        """在`file_path`中搜索`keyword`"""

        info = self._baidupcs.search(keyword, file_path, recursive=recursive)
        pcs_files = []
        for file_info in info["list"]:
            pcs_files.append(PcsFile.from_(file_info))
        return pcs_files

    async def mkdir(
        self,
        file_path: str,
        parent_id: str = "",
        file_name: str = "",
        return_if_exist: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> BaseFileInfo:
        """创建目录
        
        Args:
            file_path: 完整的目录路径
            parent_id: 父目录ID (百度网盘不使用此参数，但为保持接口兼容性保留)
            file_name: 目录名称 (百度网盘不使用此参数，但为保持接口兼容性保留)
            return_if_exist: 如果目录已存在，是否返回已存在目录的信息
            *args: 其他位置参数
            **kwargs: 其他关键字参数
            
        Returns:
            BaseFileInfo: 创建的目录信息
            
        Raises:
            BaiduApiError: 创建目录失败时抛出
        """
        # 规范化路径
        if not file_path.startswith("/"):
            file_path = "/" + file_path

        # 如果提供了 file_name，则将其附加到 file_path
        if file_name:
            file_path = os.path.join(file_path, file_name).replace("\\", "/")

        try:
            # 检查目录是否已存在
            if return_if_exist and await self.exists(file_path):
                # 获取已存在目录的信息
                meta_info = self.meta(file_path)
                if meta_info and len(meta_info) > 0:
                    pcs_file = meta_info[0]
                    return BaseFileInfo(
                        file_id=str(pcs_file.fs_id),
                        file_path=pcs_file.path,
                        file_name=os.path.basename(pcs_file.path),
                        is_folder=True,
                        file_size=0,
                        created_at=str(pcs_file.server_ctime) if pcs_file.server_ctime else "",
                        updated_at=str(pcs_file.server_mtime) if pcs_file.server_mtime else "",
                        parent_id=parent_id if parent_id else str(os.path.dirname(pcs_file.path))
                    )

            # 创建新目录
            info = await self._baidupcs.makedir(file_path)
            pcs_file = PcsFile.from_(info)

            return BaseFileInfo(
                file_id=str(pcs_file.fs_id),
                file_path=pcs_file.path,
                file_name=os.path.basename(pcs_file.path),
                is_folder=True,
                file_size=0,
                created_at=str(pcs_file.server_ctime) if pcs_file.server_ctime else "",
                updated_at=str(pcs_file.server_mtime) if pcs_file.server_mtime else "",
                parent_id=parent_id if parent_id else str(os.path.dirname(pcs_file.path))
            )

        except BaiduApiError as e:
            self.logger.error(f"创建目录失败: {e}")
            raise

    async def move(self, *file_paths: str) -> List[FromTo]:
        """将`file_paths[:-1]`移动到`file_paths[-1]`"""

        info = self._baidupcs.move(*file_paths)
        r = info["extra"].get("list")
        if not r:
            raise BaiduApiError("File operator [move] fails")
        return [FromTo(from_=v["from"], to_=v["to"]) for v in r]

    async def rename(self, source: str, dest: str) -> FromTo:
        """重命名文件"""
        
        info = self._baidupcs.rename(source, dest)
        r = info["extra"].get("list")
        if not r:
            raise BaiduApiError("File operator [rename] fails")
        v = r[0]
        return FromTo(from_=v["from"], to_=v["to"])

    async def copy(self, *file_paths: str):
        """将`file_paths[:-1]`复制到`file_paths[-1]`"""

        info = self._baidupcs.copy(*file_paths)
        r = info["extra"].get("list")
        if not r:
            raise BaiduApiError("File operator [copy] fails")
        return [FromTo(from_=v["from"], to_=v["to"]) for v in r]

    async def remove(
        self,
        file_paths: Union[str, List[str]],
        file_ids: Optional[Union[str, List[str]]] = None,
        parent_id: Optional[str] = None,  # 百度网盘不使用此参数，但为保持接口兼容性保留
        file_name: Optional[str] = None,  # 百度网盘不使用此参数，如果 file_paths 是完整路径则不应使用
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """删除文件或目录"""
        try:
            paths_for_api_call = []
            
            input_paths_list = []
            if isinstance(file_paths, str):
                input_paths_list = [file_paths] if file_paths else []
            elif isinstance(file_paths, list):
                input_paths_list = file_paths

            # 如果提供了 file_paths，优先使用它们，并确保它们是绝对路径
            if input_paths_list:
                for path in input_paths_list:
                    if not path: continue # 跳过空路径
                    
                    # 假设 input_paths_list 包含的是完整的目标路径
                    # file_name 参数在此处的逻辑比较模糊，如果path已经是完整路径，则不应再拼接file_name
                    # 为了安全起见，当前版本忽略 file_name，依赖 file_paths 是完整的。
                    current_path_to_delete = path
                    if not current_path_to_delete.startswith("/"):
                        current_path_to_delete = "/" + current_path_to_delete
                    
                    # 可以在此处添加存在性检查，但底层API也会处理不存在的情况
                    # if not await self.exists(current_path_to_delete):
                    #     self.logger.warning(f"要删除的路径不存在: {current_path_to_delete}")
                    #     continue
                    paths_for_api_call.append(current_path_to_delete)
            
            # 如果仅提供了 file_ids 而没有 file_paths，当前实现无法处理，
            # 因为底层的 _baidupcs.remove 需要路径。
            # 之前尝试通过 self.meta(id) 获取路径的逻辑是错误的。
            elif file_ids and not input_paths_list:
                 self.logger.error(
                     "BaiduClient.remove 不支持单独使用 file_ids 删除，除非实现可靠的ID到路径转换或百度提供基于ID的删除API。"
                     "请同时提供对应的 file_paths。"
                 )
                 return False
            elif not input_paths_list and not file_ids:
                self.logger.warning("没有提供 file_paths 或 file_ids 进行删除操作。")
                return False # 或者 True，因为没有操作也算成功？

            if not paths_for_api_call:
                self.logger.info("处理输入后，没有可供删除的有效路径。")
                # 如果初始输入非空但最终没有可操作路径（例如，所有路径都不存在并被跳过），
                # 返回True表示操作完成且无错误，或False表示未达到预期删除效果。
                # 此处返回True表示"尝试删除，但没有符合条件的目标"。
                return True

            # 使用收集到的所有有效路径，一次性调用底层API
            await self._baidupcs.remove(*paths_for_api_call) 
            self.logger.info(f"已成功请求删除以下路径: {paths_for_api_call}")
            if file_ids: # 如果也提供了ID，可以一起记录，方便追踪
                 self.logger.debug(f"对应的 file_ids (如果提供): {file_ids}")

            return True
        
        except BaiduApiError as e:
            # 此处捕获由 _baidupcs.remove 或其他百度API调用（如 self.exists）抛出的 BaiduApiError
            msg = e.message if hasattr(e, 'message') and e.message else str(e)
            self.logger.error(f"删除文件/目录时发生百度API错误: {msg}")
            raise # 将 BaiduApiError 重新抛出，由上层 (server.py) 处理
        except Exception as e_generic:
            # 捕获其他未预料的错误
            self.logger.error(f"删除文件/目录时发生未知错误: {str(e_generic)}")
            # 将未知错误包装成 BaiduApiError 再抛出
            raise BaiduApiError(f"删除文件/目录失败 (未知错误): {str(e_generic)}")

    def share(self, *file_paths: str, password: str, period: int = 0) -> PcsSharedLink:
        """将`file_paths`公开分享，可选择使用密码

        要使用此API，`cookies`中必须包含`STOKEN`

        period (int): 过期天数。`0`表示永不过期
        """

        info = self._baidupcs.share(*file_paths, password=password, period=period)
        link = PcsSharedLink.from_(info)._replace(
            paths=list(file_paths), password=password
        )
        return link

    def list_shared(self, page: int = 1) -> List[PcsSharedLink]:
        """列出某页的分享链接

        要使用此API，`cookies`中必须包含`STOKEN`
        """

        info = self._baidupcs.list_shared(page)
        return [PcsSharedLink.from_(v) for v in info["list"]]

    def shared_password(self, share_id: int) -> Optional[str]:
        """显示分享链接密码

        要使用此API，`cookies`中必须包含`STOKEN`
        """

        info = self._baidupcs.shared_password(share_id)
        p = info.get("pwd", "0")
        if p == "0":
            return None
        return p

    def cancel_shared(self, *share_ids: int):
        """取消具有`share_ids`的分享链接

        要使用此API，`cookies`中必须包含`STOKEN`
        """

        self._baidupcs.cancel_shared(*share_ids)

    def access_shared(
        self,
        shared_url: str,
        password: str,
        vcode_str: Optional[str] = None,
        vcode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """验证需要`password`的`shared_url`
        如果需要验证码，将返回包含验证码信息的字典。
        否则，返回成功或失败的信息。
        """
        try:
            self._baidupcs.access_shared(shared_url, password, vcode_str or "", vcode or "") 
            return {"vcode_required": False, "success": True, "message": "访问共享链接成功"}
        except BaiduApiError as err:
            if err.error_code in (-9, -62):
                self.logger.warning(f"验证码相关错误: {err.error_code} - {err.message}")
                try:
                    vcode_challenge_str, vcode_img_url = self.getcaptcha(shared_url)
                    return {
                        "vcode_required": True,
                        "vcode_str": vcode_challenge_str,
                        "vcode_image_url": vcode_img_url,
                        "message": err.message or ("验证码错误或需要输入验证码" if err.error_code == -9 else "需要输入验证码"),
                        "original_error_code": err.error_code
                    }
                except BaiduApiError as captcha_err:
                    self.logger.error(f"获取验证码失败: {captcha_err}")
                    raise BaiduApiError(
                        message=f"访问共享链接时需要验证码，但获取新验证码失败: {captcha_err.message}", 
                        error_code=err.error_code,
                        cause=captcha_err
                    ) 
            else:
                self.logger.error(f"访问共享时发生其他错误: {err}")
                raise err

    def getcaptcha(self, shared_url: str) -> Tuple[str, str]:
        """获取一个验证码信息
        返回 `vcode_str`, `vcode_img_url`"""

        info = self._baidupcs.getcaptcha(shared_url)
        return info["vcode_str"], info["vcode_img"]

    def get_vcode_img(self, vcode_img_url: str, shared_url: str) -> bytes:
        """获取验证码图像内容"""

        return self._baidupcs.get_vcode_img(vcode_img_url, shared_url)

    def shared_paths(self, shared_url: str) -> List[PcsSharedPath]:
        """获取`shared_url`的共享路径"""

        info = self._baidupcs.shared_paths(shared_url)
        uk = info.get("share_uk") or info.get("uk")
        uk = int(uk)

        assert uk, "`BaiduPCSApi.shared_paths`: Don't get `uk`"

        share_id = info["shareid"]
        bdstoken = info["bdstoken"]

        if not info.get("file_list"):
            return []

        if isinstance(info["file_list"], list):
            file_list = info["file_list"]
        elif isinstance(info["file_list"].get("list"), list):
            file_list = info["file_list"]["list"]
        else:
            raise ValueError("`shared_paths`: Parsing shared info fails")

        return [
            PcsSharedPath.from_(v)._replace(uk=uk, share_id=share_id, bdstoken=bdstoken)
            for v in file_list
        ]

    async def list_shared_paths(
        self,
        sharedpath: str,
        uk: int,
        share_id: int,
        bdstoken: str,
        page: int = 1,
        size: int = 100,
    ) -> List[PcsSharedPath]:
        """共享目录`sharedpath`的子共享路径"""

        info = self._baidupcs.list_shared_paths(
            sharedpath, uk, share_id, page=page, size=size
        )
        return [
            PcsSharedPath.from_(v)._replace(uk=uk, share_id=share_id, bdstoken=bdstoken)
            for v in info["list"]
        ]

    async def transfer_shared_paths(
        self,
        remotedir: str,
        fs_ids: List[int],
        uk: int,
        share_id: int,
        bdstoken: str,
        shared_url: str,
    ):
        """保存这些共享路径的`fs_ids`到`remotedir`"""

        self._baidupcs.transfer_shared_paths(
            remotedir, fs_ids, uk, share_id, bdstoken, shared_url
        )

    async def save_shared(
        self, shared_url: str, remote_dir: str, password: Optional[str] = None
    ):
        """保存共享链接到指定目录"""
        
        shared_url = _unify_shared_url(shared_url)

        access_result = self.access_shared(shared_url, password or "") 
        if password:
            access_result = self.access_shared(shared_url, password, vcode_str=None, vcode=None)
            if access_result.get("vcode_required"):
                self.logger.error(f"保存共享失败: 需要验证码才能继续. {access_result}")
                raise BaiduApiError(message=f"需要验证码才能保存共享: {access_result.get('message')}", error_code=access_result.get('original_error_code', -62))
        
        shared_paths_list = self.shared_paths(shared_url)
        if not shared_paths_list:
            self.logger.info("共享链接中没有文件或访问失败后未能正确设置会话。")
            return

        shared_paths_deque = deque(shared_paths_list)
        _remote_dirs: Dict[PcsSharedPath, str] = dict(
            [(sp, remote_dir) for sp in shared_paths_deque]
        )
        _dir_exists: Set[str] = set()

        while shared_paths_deque:
            shared_path = shared_paths_deque.popleft()
            rd = _remote_dirs[shared_path]

            if rd not in _dir_exists:
                if not await self.exists(rd):
                    await self.mkdir(rd)
                _dir_exists.add(rd)

            if shared_path.is_file and await self.remote_path_exists(
                PurePosixPath(shared_path.path).name, rd
            ):
                self.logger.warning(f"{shared_path.path} has be in {rd}")
                continue

            uk, share_id_val, bdstoken_val = (
                shared_path.uk,
                shared_path.share_id,
                shared_path.bdstoken,
            )

            try:
                await self.transfer_shared_paths(
                    rd, [shared_path.fs_id], uk, share_id_val, bdstoken_val, shared_url
                )
                self.logger.info(f"save: {shared_path.path} to {rd}")
                continue
            except BaiduApiError as err:
                if err.error_code == 12:
                    self.logger.warning(
                        f"error_code: {err.error_code}, 文件已经存在, {shared_path.path} has be in {rd}"
                    )
                elif err.error_code == -32:
                    self.logger.error(f"error_code:{err.error_code} 剩余空间不足，无法转存")
                elif err.error_code == -33:
                    self.logger.error(
                        f"error_code:{err.error_code} 一次支持操作999个，减点试试吧"
                    )
                elif err.error_code == 4:
                    self.logger.error(
                        f"error_code:{err.error_code} share transfer pcs error"
                    )
                elif err.error_code == 130:
                    self.logger.error(f"error_code:{err.error_code} 转存文件数超限")
                elif err.error_code == 120:
                    self.logger.error(f"error_code:{err.error_code} 转存文件数超限")
                else:
                    self.logger.error(f"转存 {shared_path.path} 失败: error_code:{err.error_code}:{err}")
                    continue

            if shared_path.is_dir:
                sub_paths = await self.list_all_sub_paths(
                    shared_path.path, uk, share_id_val, bdstoken_val
                )
                current_dir_name = PurePosixPath(shared_path.path).name
                sub_remote_dir = (Path(rd) / current_dir_name).as_posix()
                
                for sp in sub_paths:
                    _remote_dirs[sp] = sub_remote_dir
                shared_paths_deque.extendleft(sub_paths[::-1])

    async def remote_path_exists(
        self, name: str, rd: str, _cache: Dict[str, Set[str]] = {}
    ) -> bool:
        """检查远程路径是否存在"""
        
        names = _cache.get(rd)
        if not names:
            listed_items = self.list(rd)
            names = set([PurePosixPath(item.get('path', '')).name for item in listed_items if item.get('path')])
            _cache[rd] = names
        return name in names

    async def list_all_sub_paths(
        self, shared_path: str, uk: int, share_id: int, bdstoken: str, size=100
    ) -> List[PcsSharedPath]:
        """列出所有子路径"""
        
        sub_paths = []
        for page in range(1, 1000):
            sps = await self.list_shared_paths(
                shared_path, uk, share_id, bdstoken, page=page, size=size
            )
            sub_paths.extend(sps)
            if len(sps) < size:
                break
        return sub_paths
        
    async def get_relationship_list(self, relationship_type: str) -> Union[List[UserFriend], List[UserGroup], List[Any]]:
        """
        获取所有关注的用户列表或群组列表

        Args:
            relationship_type (str): "friend" 或 "group"
        
        返回:
            Union[List[UserFriend], List[UserGroup]]: 用户/群组列表
        """
        all_items = []
        start = 0
        limit = 20 # 百度API通常限制为20

        if relationship_type not in ["friend", "group"]:
            self.logger.error(f"无效的 relationship_type: {relationship_type}. 必须是 'friend' 或 'group'.")
            return []
        
        while True:
            response = None # Initialize response
            try:
                if relationship_type == "friend":
                    response = await self._baidupcs.get_follow_list(start=start, limit=limit)
                elif relationship_type == "group":
                    response = await self._baidupcs.get_group_list(start=start, limit=limit)
                else: # Should not happen due to the check above
                    return []
            except BaiduApiError as e:
                self.logger.error(f"获取 {relationship_type} 列表时API出错: {e}")
                break
            except Exception as e:
                self.logger.error(f"获取 {relationship_type} 列表时发生未知错误: {e}")
                break
            
            if response is None:
                self.logger.error(f"获取 {relationship_type} 列表后响应为空，可能在API调用后出现意外情况。")
                break
            
            if response.get("errno") != 0:
                self.logger.error(f"获取 {relationship_type} 列表失败: {response}")
                break
            
            records = response.get("records", [])
            if not records:
                break
            
            for record in records:
                if relationship_type == "friend":
                    try:
                        # 映射API返回的好友数据到UserFriend模型
                        friend_data = {
                            "uk": int(record.get("uk", 0)),
                            "uname": record.get("uname", ""),
                            "nick_name": record.get("nick_name", record.get("uname", "")),  # 如果没有昵称就用用户名
                            "avatar_url": record.get("avatar_url", ""),
                            "is_friend": record.get("is_friend", 2)  # 默认设为2表示互相关注
                        }
                        item = UserFriend(**friend_data)
                    except Exception as e:
                        self.logger.error(f"解析好友数据失败: {record}, 错误: {e}")
                        continue
                elif relationship_type == "group":
                    try:
                        # 映射API返回的群组数据到UserGroup模型
                        group_data = {
                            "gid": str(record.get("gid", "")),
                            "gnum": str(record.get("gnum", "")),
                            "name": record.get("name", ""),
                            "type": str(record.get("type", "")),
                            "status": str(record.get("status", "1"))  # 默认状态为1（正常）
                        }
                        item = UserGroup(**group_data)
                    except Exception as e:
                        self.logger.error(f"解析群组数据失败: {record}, 错误: {e}")
                        continue
                else:
                    self.logger.warning(f"未知的关系类型: {relationship_type}")
                    return []
                all_items.append(item)
            
            if relationship_type == "friend":
                if not response.get("has_more"):
                    break
            elif relationship_type == "group":
                total_count = response.get("count", 0)
                current_fetched = start + len(records)
                if current_fetched >= total_count or not response.get("has_more", True):
                    break
            
            start += limit
        
        return all_items

    async def get_relationship_share_list(
        self,
        relationship_type: str,
        identifier: str,  # 好友时为 to_uk, 群组时为 gid
        type: int = 2,    # API 默认为 2
        **kwargs
    ) -> Dict:
        """获取好友或群组的分享列表
        
        Args:
            relationship_type (str): "friend" 或 "group"
            identifier (str): 当 relationship_type 为 "friend" 时, 此为好友的 UK (to_uk);
                              当 relationship_type 为 "group" 时, 此为群组的 ID (gid).
            type (int): 分享类型，API 默认为 2.
            **kwargs: 其他可选参数.
                对于群组类型 (relationship_type="group"):
                    limit (int): 每页数量，默认为 50.
                    desc (int): 是否降序 (1降序, 0升序)，默认为 1.
                其他参数 (如 clienttype, app_id, web) 会透传给底层 API.
                
        Returns:
            Dict: 返回分享列表信息
        """
        if relationship_type == "friend":
            # 对于好友分享，limit 和 desc 不是 get_friend_share_list 的直接参数
            # 如果它们在 kwargs 中，会传递给底层 API，但可能被忽略
            return await self._baidupcs.get_friend_share_list(to_uk=identifier, type=type, **kwargs)
        elif relationship_type == "group":
            # 从 kwargs 中提取群组特定的参数，如果未提供则使用默认值
            group_limit = kwargs.pop('limit', 50)
            group_desc = kwargs.pop('desc', 1)
            return await self._baidupcs.get_group_share_list(
                gid=identifier, type=type, limit=group_limit, desc=group_desc, **kwargs
            )
        else:
            self.logger.error(f"无效的 relationship_type: {relationship_type}. 必须是 'friend' 或 'group'.")
            return {"errno": -1, "error_msg": f"无效的 relationship_type: {relationship_type}", "records": []} 
        
    async def get_relationship_share_detail(
        self,
        relationship_type: str,
        identifier: str,  # 好友时为 to_uk, 群组时为 gid
        from_uk: str,
        msg_id: str,
        fs_id: str,
        page: int = 1,
        num: int = 50,
        **kwargs
    ) -> Dict:
        """获取好友或群组的分享详情
        
        Args:
            relationship_type (str): "friend" 或 "group"
            identifier (str): 当 relationship_type 为 "friend" 时, 此为好友的 UK (to_uk);
                              当 relationship_type 为 "group" 时, 此为群组的 ID (gid).
            from_uk (str): 分享者UK
            msg_id (str): 消息ID
            fs_id (str): 文件ID
            page (int): 页码，默认为1
            num (int): 每页数量，默认为50
            **kwargs: 其他可选参数.
                type (int): 分享类型. 如果未提供, 好友默认为1, 群组默认为2.
                对于群组类型 (relationship_type="group"):
                    limit (int): 列表限制，默认为 50.
                    desc (int): 是否降序 (1降序, 0升序)，默认为 1.
                其他参数 (如 clienttype, app_id, web) 会透传给底层 API.
                
        Returns:
            Dict: 返回分享详情信息
        """
        if relationship_type == "friend":
            # 如果 'type' 在 kwargs 中，则使用它，否则默认为 1
            final_type = kwargs.pop('type', 1)
            return await self._baidupcs.get_friend_share_detail(
                from_uk=from_uk,
                msg_id=msg_id,
                to_uk=str(self.user_id),  # 使用当前登录用户的UK
                fs_id=fs_id,
                type=final_type,
                page=page,
                num=num,
                **kwargs  # 传递剩余的 kwargs
            )
        elif relationship_type == "group":
            # 如果 'type' 在 kwargs 中，则使用它，否则默认为 2
            final_type = kwargs.pop('type', 2)
            # 从 kwargs 中提取群组特定的参数，如果未提供则使用 API 定义的默认值
            group_limit = kwargs.pop('limit', 50)
            group_desc = kwargs.pop('desc', 1)
            return await self._baidupcs.get_group_share_detail(
                from_uk=from_uk,
                msg_id=msg_id,
                gid=identifier,  # identifier 是 gid
                fs_id=fs_id,
                type=final_type,
                page=page,
                num=num,
                limit=group_limit,
                desc=group_desc,
                **kwargs  # 传递剩余的 kwargs
            )
        else:
            self.logger.error(f"无效的 relationship_type: {relationship_type}. 必须是 'friend' 或 'group'.")
            return {"errno": -1, "error_msg": f"无效的 relationship_type: {relationship_type}"}        

    async def get_share_list(
        self,
        source_type: str,
        source_id: str,  # friend_uk (context to_uk) or group_gid
        file_path: str,  # path within a share, e.g., "/SharedFolderAlpha/SubDir"
        recursive: bool = False,
        recursion_speed: RecursionSpeed = RecursionSpeed.NORMAL,
        item_filter: Optional[ItemFilter] = None, # Added item_filter
    ) -> List[BaseFileInfo]:
        """
        获取指定好友或群组分享中特定路径下的文件/目录列表.
         file_path 的第一部分必须匹配某个分享事件的根共享名.
        """
        self.logger.info(f"get_share_list: type='{source_type}', id='{source_id}', path='{file_path}', recursive={recursive}")
        drive_files_list: List[BaseFileInfo] = []

        normalized_file_path = file_path.strip('/')
        if not normalized_file_path:
            self.logger.error("file_path cannot be empty or root '/'. It must specify the shared item's name e.g., '/MyShare/subfolder'.")
            return []
        path_components = normalized_file_path.split('/')

        # 1. Get all share events/messages
        share_events_response = await self.get_relationship_share_list(
            relationship_type=source_type,
            identifier=source_id
        )

        if share_events_response.get("errno", 0) != 0:
            self.logger.error(f"Failed to get share events for {source_type} {source_id}: {share_events_response}")
            return []

        share_messages = []
        # Based on provided JSON:
        # Friend: response.records.list
        # Group: response.records.msg_list
        records_obj = share_events_response.get("records", {})
        if source_type == "friend":
            share_messages = records_obj.get("list", [])
        elif source_type == "group":
            share_messages = records_obj.get("msg_list", [])
        
        if not share_messages:
            self.logger.info(f"No share messages found for {source_type} {source_id}.")
            return []

        # 2. Find the target share event and its root item
        target_share_info = None # Store {'msg_id', 'sharer_uk', 'root_fs_id', 'root_name'}

        for share_event in share_messages:
            msg_id = share_event.get("msg_id")
            sharer_uk = None
            share_root_items_list = [] 

            if source_type == "friend":
                sharer_uk = share_event.get("from_uk")
                share_root_items_list = share_event.get("filelist", {}).get("list", [])
            elif source_type == "group":
                sharer_uk = share_event.get("uk") 
                share_root_items_list = share_event.get("file_list", []) # Directly a list for groups
            
            if not msg_id or sharer_uk is None or not share_root_items_list:
                self.logger.debug(f"Skipping share_event due to missing essential info (msg_id, sharer_uk, or root items): {share_event}")
                continue

            share_event_root_item = share_root_items_list[0] # Assuming first item is the main shared root
            root_item_name = share_event_root_item.get("server_filename")
            # server_filename from group shares might be URL encoded if taken from 'path' field, but API examples show it decoded.
            # Example group share path: "%2F%E8%AF%BE%E7%A8%8B%E7%9B%AE%E5%BD%95..." -> /课程目录...
            # server_filename seems to be correctly decoded in the provided JSONs.
            
            root_item_fs_id = share_event_root_item.get("fs_id")

            if not root_item_name or root_item_fs_id is None:
                self.logger.debug(f"Skipping share_event's root item due to missing name/fs_id: {share_event_root_item}")
                continue
            
            if path_components[0] == root_item_name:
                target_share_info = {
                    "msg_id": str(msg_id),
                    "sharer_uk": str(sharer_uk),
                    "root_fs_id": str(root_item_fs_id),
                    "root_name": str(root_item_name) 
                }
                self.logger.info(f"Matched share event by root name '{root_item_name}': {target_share_info}")
                break # Found the target share event
        
        if not target_share_info:
            self.logger.warning(f"No share event found with root item named '{path_components[0]}' for {source_type} {source_id}.")
            return []

        # 3. Navigate the path within the selected share
        current_nav_fs_id = target_share_info["root_fs_id"]
        current_constructed_drive_path = PurePosixPath("/") / target_share_info["root_name"]

        for component_idx in range(1, len(path_components)):
            component_name = path_components[component_idx]
            self.logger.debug(f"Navigating: current_fs_id={current_nav_fs_id}, seeking component='{component_name}'")

            detail_response = await self.get_relationship_share_detail(
                relationship_type=source_type,
                identifier=source_id, 
                from_uk=target_share_info["sharer_uk"],
                msg_id=target_share_info["msg_id"],
                fs_id=current_nav_fs_id
            )

            if detail_response.get("errno") != 0:
                self.logger.error(f"Navigation failed at component '{component_name}' (under fs_id: {current_nav_fs_id}). Response: {detail_response}")
                return []

            items_in_current_dir = detail_response.get("records", [])
            found_next_component = False
            for item_dict in items_in_current_dir:
                item_name_api = item_dict.get("server_filename")
                if item_name_api == component_name:
                    if not item_dict.get("isdir") and component_idx < len(path_components) - 1:
                        self.logger.error(f"Path component '{component_name}' is a file, but further path components exist in query.")
                        return []
                    current_nav_fs_id = str(item_dict.get("fs_id"))
                    current_constructed_drive_path = current_constructed_drive_path / component_name
                    found_next_component = True
                    self.logger.debug(f"Found path component '{component_name}', new current_nav_fs_id={current_nav_fs_id}, new_path_base={current_constructed_drive_path}")
                    break
            
            if not found_next_component:
                self.logger.error(f"Path component '{component_name}' not found in directory (fs_id of parent: { (path_components[component_idx-1] if component_idx > 0 else target_share_info['root_name']) }).")
                return []
        
        # 4. List target content (current_nav_fs_id is the target fs_id to list)
        queue = deque([(str(current_nav_fs_id), current_constructed_drive_path, str(current_nav_fs_id))])
        # Queue stores: (fs_id_to_list_its_content, path_base_for_its_content, parent_id_for_items_listed_from_it)
        
        processed_fs_ids_for_recursion = set()
        is_first_pass_in_queue = True # To identify the initial listing of the target path

        while queue:
            fs_id_to_process, path_base_for_items, parent_id_for_items = queue.popleft()

            if fs_id_to_process in processed_fs_ids_for_recursion and recursive:
                 continue
            if recursive: # Only add to processed if we are in recursive mode
                processed_fs_ids_for_recursion.add(fs_id_to_process)

            # Apply recursion speed logic only if recursion is enabled
            if recursive and not is_first_pass_in_queue: # Speed logic applies to sub-directory processing, not the initial target path
                if recursion_speed == RecursionSpeed.SLOW:
                    self.logger.debug(f"Slow mode (share): Pausing for 3s before listing fs_id: {fs_id_to_process}")
                    time.sleep(3)
                elif recursion_speed == RecursionSpeed.FAST:
                    # TODO: Implement fast mode logic
                    # - Try to get sublist of current_item_path from DB cache
                    # - If cache hit, add children (item_dict, current_fs_id) to all_processed_data (or return cached BaseFileInfo list directly? Needs design)
                    # - If cache miss, can either:
                    #   - Fallback to NORMAL mode behavior (make API request)
                    #   - Or skip, assuming cache is complete
                    # - Note handling cache update logic
                    self.logger.debug(f"Fast mode (share) selected for fs_id: {fs_id_to_process}, but no specific fast-path implemented yet. Proceeding as NORMAL for this level.")
                    pass # Explicitly do nothing different for FAST for now, beyond logging.
            
            if is_first_pass_in_queue:
                is_first_pass_in_queue = False # Mark that the first item from queue has been processed

            self.logger.debug(f"Listing content for fs_id: {fs_id_to_process}, path_base: {path_base_for_items}, items_parent_id: {parent_id_for_items}")
            detail_response = await self.get_relationship_share_detail(
                relationship_type=source_type,
                identifier=source_id, 
                from_uk=target_share_info["sharer_uk"],
                msg_id=target_share_info["msg_id"],
                fs_id=fs_id_to_process
            )

            if detail_response.get("errno") != 0:
                self.logger.warning(f"Failed to get details for fs_id {fs_id_to_process} during final listing: {detail_response}")
                continue
            
            items_from_api = detail_response.get("records", [])
            
            # Check if the fs_id_to_process itself was a file.
            # If fs_id_to_process is a file, items_from_api will contain only that file.
            is_listing_a_single_target_file = False
            if len(items_from_api) == 1 and str(items_from_api[0].get("fs_id")) == fs_id_to_process and not items_from_api[0].get("isdir"):
                is_listing_a_single_target_file = True
                self.logger.debug(f"Target fs_id {fs_id_to_process} for listing is a single file.")

            for item_dict in items_from_api:
                item_fs_id_str = str(item_dict.get("fs_id"))
                item_name = item_dict.get("server_filename", "Unknown")
                is_folder_item = bool(item_dict.get("isdir"))
                
                # Construct BaseFileInfo path:
                # If listing a single target file, its path is path_base_for_items.
                # If listing a directory's content, item's path is path_base_for_items / item_name.
                drive_file_item_path_str = str(path_base_for_items if is_listing_a_single_target_file else path_base_for_items / item_name)

                df = BaseFileInfo(
                    file_id=item_fs_id_str,
                    file_name=item_name,
                    file_path=drive_file_item_path_str,
                    file_size=item_dict.get("size", 0),
                    is_folder=is_folder_item,
                    created_at=str(item_dict.get("server_ctime")), # API uses server_ctime
                    updated_at=str(item_dict.get("server_mtime")), # API uses server_mtime
                    parent_id=str(parent_id_for_items),
                    file_ext={
                        "from_uk": target_share_info["sharer_uk"],
                        "msg_id": target_share_info["msg_id"],
                        # 如果需要，也可以保留原始API项目的部分或全部信息
                        # "baidu_api_item": dict(item_dict),
                        #"sharer_original_path": item_dict.get("path")
                    }
                )

                if item_filter and item_filter.should_exclude(df):
                    self.logger.debug(f"[Filter] Excluding shared item: {df.file_path}")
                    if df.is_folder and recursive: # If a folder is excluded, don't add its children to queue
                        # We need to ensure this df.file_id isn't added to queue later
                        # The current logic adds to queue based on df.is_folder *after* this check
                        # So, if it's excluded, it won't be added to queue below. This is fine.
                        pass 
                    continue # Skip adding to drive_files_list and further processing for queue
                
                drive_files_list.append(df)

                if recursive and is_folder_item and not is_listing_a_single_target_file:
                    # Filter already applied to df. If it wasn't excluded, it can be added to queue.
                    queue.append((df.file_id, PurePosixPath(drive_file_item_path_str), df.file_id))
            
            if is_listing_a_single_target_file: # If the initial target was a file, we've listed it, so stop.
                break
        
        return drive_files_list
        
    async def transfer(
        self,
        source_type: str, # "link", "group", "friend"
        source_id: str,   # share_url for "link", group_id for "group", friend_uk for "friend"
        source_path: str, # ignored for baidu, but kept for interface compatibility
        target_path: str, # target directory in user's own drive
        file_ids: Optional[List[Union[int, str]]] = None, # fs_ids to transfer
        **kwargs: Any,
    ) -> bool:
        """
        从各种来源传输文件到自己的网盘。

        参数:
            source_type (str): 来源类型，可选值："link" (链接分享), "group" (群组分享), "friend" (好友分享)。
            source_id (str): 来源的唯一标识符。
                             - 当 source_type 为 "link" 时, 此为分享链接的URL (当前未实现)。
                             - 当 source_type 为 "group" 时, 此为群组的ID (gid)。
                             - 当 source_type 为 "friend" 时, 此为好友的用户ID (UK)，即分享者。
            source_path (str): 源文件/目录在分享中的路径 (百度网盘在此转存场景下通常不直接使用此参数进行API调用，
                               而是依赖 file_ids, msg_id 以及分享者信息，但为保持接口兼容性而保留)。
            target_path (str): 文件/目录在用户自己网盘中保存的目标路径。
            file_ids (Optional[List[Union[int, str]]]): 要传输的文件/目录的 fs_id 列表。
                                                      对于 "friend" 和 "group" 类型的转存是必需的。
            **kwargs (Any): 其他可选参数。
                           - msg_id (str): 消息ID。对于 "friend" 和 "group" 类型的转存是必需的。
                           - from_uk (str): 分享者的用户ID (UK)。当 source_type 为 "group" 时是必需的 (因为此时 source_id 是群组ID)。
                           - ondup (str): 文件名冲突时的处理方式，可选值为 "newcopy" (新建副本，默认), "skip" (跳过)。
                           - async (int): 是否异步执行，可传递给底层API (例如 0 或 1，默认为1，表示异步)。
        
        返回:
            bool: 如果转存操作被API接受并报告成功，则返回 True；否则返回 False。
        """
        # 确保target_path使用正斜杠
        target_path = target_path.replace("\\", "/")
        
        self.logger.info(
            f"转存请求: source_type='{source_type}', source_id='{source_id}', "
            f"source_path='{source_path}', target_path='{target_path}', file_ids='{file_ids}'"
        )

        if not self.user_id: # 此检查对于 to_uk 参数仍然是必要的
            self.logger.error("转存失败: 用户ID (to_uk) 缺失.")
            return False

        if source_type == "link":
            self.logger.warning("来自 'link' 类型的转存尚未为百度网盘实现.")
            # TODO: 如果接口适用，在此处实现 save_shared 或类似逻辑
            # 目前根据用户请求，这是一个占位符。
            # self.save_shared(shared_url=source_id, remote_dir=target_path, password=kwargs.get("password"))
            # save_shared 方法本身需要调整以返回简单的布尔值。
            raise NotImplementedError("百度客户端尚不支持从 'link' 类型转存.")

        elif source_type in ["friend", "group"]:
            if not file_ids:
                self.logger.error(f"转存失败: source_type '{source_type}' 需要 'file_ids'.")
                return False
            
            msg_id = kwargs.get("msg_id")
            if not msg_id:
                self.logger.error(f"转存失败: source_type '{source_type}' 的 kwargs 中需要 'msg_id'.")
                return False

            transfer_type = 1 if source_type == "friend" else 2
            
            # 构建API参数
            api_kwargs = {
                "path": target_path,
                "ondup": kwargs.get("ondup", "newcopy"),
            }
            
            # 处理异步参数 - 简化逻辑
            async_value = kwargs.get("async_", kwargs.get("async", 1))
            api_kwargs["async_"] = int(async_value) if async_value is not None else 1


            from_uk_param = None

            if source_type == "friend":
                from_uk_param = source_id # source_id 是好友的 UK (分享者 UK)
            elif source_type == "group":
                # source_id 是群组的 ID (gid)
                # api.py 中的 `transfer_files` 方法需要 `from_uk` (分享者) 和 `gid` (群组).
                from_uk_param = kwargs.get("from_uk") # kwargs 中必须提供分享者的 UK
                if not from_uk_param:
                    self.logger.error("群组分享转存失败: kwargs 中需要 'from_uk' (分享者 UK).")
                    return False
                api_kwargs["gid"] = source_id # 将 gid 传递给 transfer_files 的 api_kwargs


            try:
                result = await self._baidupcs.transfer_files(
                    from_uk=str(from_uk_param) if from_uk_param else "",
                    to_uk=str(self.user_id),
                    msg_id=str(msg_id),
                    fs_ids=file_ids,
                    type=transfer_type,
                    **api_kwargs
                )
                if result.get("errno") == 0:
                    self.logger.info(f"source_type '{source_type}' 转存成功. API 响应: {result}")
                    return True
                else:
                    self.logger.error(f"source_type '{source_type}' 转存失败. API 响应: {result}")
                    return False
            except BaiduApiError as e:
                self.logger.error(f"'{source_type}' 转存期间发生百度 API 错误: {e}")
                return False
            except Exception as e:
                self.logger.error(f"'{source_type}' 转存期间发生意外错误: {e}")
                return False
        else:
            self.logger.error(f"不支持的转存 source_type: {source_type}")
            return False
        
    