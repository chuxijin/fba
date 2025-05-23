"""
文件名: base.py
描述: 网盘基础类定义，提供网盘操作的抽象接口和通用实现
作者: PanMaster团队
创建日期: 2023-04-01
最后修改: 2024-04-24
版本: 1.3.0
"""


from typing import Any, List, Optional, Union
from app.coulddrive.schema.enum import RecursionSpeed, DriveType
from app.coulddrive.schema.file import BaseFileInfo
from app.coulddrive.schema.user import BaseUserInfo
class BaseDrive:
    """
    网盘操作基础类
    
    提供网盘操作的抽象接口定义，子类须实现具体方法
    主要功能包括：
    - 身份验证与基础属性
    - 文件和目录管理
    - 下载与上传
    - 分享与传输
    - 搜索与回收站管理
    - 路径与ID转换
    """

    def __init__(self, *args, **kwargs):
        """
        初始化网盘基类
        :param args: 位置参数
        :param kwargs: 关键字参数
        """
        self._is_authorized = False

    @property
    def drive_type(self) -> str:
        """网盘类型"""
        raise NotImplementedError()

    def login(self, *args: Any, **kwargs: Any) -> bool:
        """
        登录网盘
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 登录是否成功
        """
        raise NotImplementedError()
    
    def get_user_info(self, *args: Any, **kwargs: Any) -> dict:
        """
        获取用户信息
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 用户信息字典
        """
        raise NotImplementedError()

    def get_quota(self, *args: Any, **kwargs: Any) -> dict:
        """
        获取网盘空间使用情况

        Args:
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            dict: 包含总空间、已用空间等信息的字典
        """
        raise NotImplementedError()
    
    def get_relationship_list(self, *args: Any, **kwargs: Any) -> List[BaseFileInfo]:
        """
        获取网盘关系列表
        """
        raise NotImplementedError()
        
    #--------------------------------------------------
    # 文件和目录管理
    #--------------------------------------------------

    def mkdir(
        self,
        file_path: str,
        parent_id: str,
        file_name: str,
        return_if_exist: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> BaseFileInfo:
        """
        创建目录
        :param fid: 父目录ID
        :param name: 目录名称
        :param return_if_exist: 如果目录已存在，是否返回已存在目录的ID
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 创建的目录信息
        """
        raise NotImplementedError()

    def exist(self, fid: str, *args: Any, **kwargs: Any) -> bool:
        """
        检查文件或目录是否存在
        :param fid: 文件或目录ID
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 是否存在
        """
        raise NotImplementedError()

    def remove(
        self,
        file_paths: Union[str, List[str]],  # 支持单个路径或路径数组
        file_ids: Optional[Union[str, List[str]]] = None,  # 支持单个ID或ID数组
        parent_id: Optional[str] = None,
        file_name: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """
        删除文件或目录
        
        Args:
            file_paths: 要删除的文件或目录的路径，可以是单个路径字符串或路径列表
            file_ids: 要删除的文件或目录的ID，可以是单个ID字符串或ID列表。如果提供，将优先使用ID进行删除
            parent_id: 父目录ID（可选）
            file_name: 文件/目录名称（可选）
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            bool: 删除是否成功
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError()

    def move(
        self,
        source_fid: str,
        target_fid: str,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """
        移动文件或目录
        
        将源文件或目录移动到目标目录
        
        参数:
            source_fid (str): 源文件或目录ID
            target_fid (str): 目标目录ID
            args (Any): 位置参数
            kwargs (Any): 关键字参数
            
        返回:
            bool: 移动是否成功
            
        示例:
            >>> drive.move("/源文件.txt", "/目标目录")
            True
        """
        raise NotImplementedError()

    def copy(
        self,
        source_fid: str,
        target_fid: str,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """
        复制文件或目录
        
        将源文件或目录复制到目标目录
        
        参数:
            source_fid (str): 源文件或目录ID
            target_fid (str): 目标目录ID
            args (Any): 位置参数
            kwargs (Any): 关键字参数
            
        返回:
            bool: 复制是否成功
            
        示例:
            >>> drive.copy("/源文件.txt", "/目标目录")
            True
        """
        raise NotImplementedError()

    async def get_disk_list(
        self, 
        file_path: str,
        file_id: str, 
        recursive: bool = False,
        desc: bool = False,      # 新增：是否按降序排序
        name: bool = False,      # 新增：是否按名称排序
        time: bool = False,      # 新增：是否按时间排序
        size: bool = False,      # 新增：是否按大小排序
        recursion_speed: RecursionSpeed = RecursionSpeed.NORMAL, # 新增：递归速度控制
        item_filter = None,      # 新增：项目过滤器
        *args: Any, 
        **kwargs: Any
    ) -> List[BaseFileInfo]:
        """
        获取目录下的文件和目录列表，并构建 parent_id.
        
        Args:
            file_path (str): 要列出内容的目录路径。
            file_id (str): 必须是 file_path 对应的目录的 fs_id。用于设置子项的 parent_id。
                           对于根目录 '/', 通常传递 "" 或特定的根ID（如果知道）。
            recursive (bool): 是否递归获取所有子项。
            desc (bool): 按降序排序。
            name (bool): 按名称排序。
            time (bool): 按时间排序。
            size (bool): 按大小排序。
            recursion_speed (RecursionSpeed): 递归获取时的速度控制（默认 NORMAL）。
            item_filter: 用于过滤项目的过滤器实例。
            *args: 其他位置参数。
            **kwargs: 其他关键字参数。
            
        Returns:
            List[BaseFileInfo]: 包含文件/目录信息的列表，已填充 parent_id。
        """
        raise NotImplementedError()
    
    async def get_share_list(
        self,
        source_type: str,
        source_id: str,
        file_path: str,
        recursive: bool = False,
        recursion_speed: RecursionSpeed = RecursionSpeed.NORMAL,
        item_filter = None,
        *args: Any,
        **kwargs: Any
    ) -> List[BaseFileInfo]:
        """
        获取分享来源的文件列表
        
        从不同来源（链接分享、好友分享、群组分享）获取文件列表
        
        参数:
            source_type (str): 来源类型，可选值："link"(链接)、"group"(群组)、"friend"(好友)
            source_id (str): 来源ID，根据source_type不同而不同:
                             - 当source_type为"link"时，为分享链接
                             - 当source_type为"group"时，为群组ID
                             - 当source_type为"friend"时，为好友用户ID
            file_path (str): 分享内的文件路径
            recursive (bool): 是否递归获取所有子项
            recursion_speed (RecursionSpeed): 递归获取时的速度控制
            item_filter: 用于过滤项目的过滤器实例
            args (Any): 位置参数
            kwargs (Any): 关键字参数，可能包括:
                         - share_password: 分享密码（针对加密分享）
                         - from_uk: 分享者ID
                         - msg_id: 消息ID（针对群组和好友分享）
                         
        返回:
            List[BaseFileInfo]: 分享来源的文件列表
            
        示例:
            # 获取链接分享的文件列表
            >>> drive.get_share_list("link", "https://pan.example.com/s/1abcdef", share_password="1234")
            [BaseFileInfo(...), BaseFileInfo(...)]
            
            # 获取群组分享的文件列表
            >>> drive.get_share_list("group", "12345", from_uk="67890", msg_id="msg123")
            [BaseFileInfo(...), BaseFileInfo(...)]
        """
        raise NotImplementedError()

    def get_item_info(self, fid: str, *args: Any, **kwargs: Any) -> Optional[BaseFileInfo]:
        """
        获取文件或目录的详细信息
        
        :param fid: 文件或目录ID
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 文件或目录信息对象
        """
        raise NotImplementedError()
        
    def rename(
        self,
        fid: str,
        new_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """
        重命名文件或目录

        Args:
            fid: 文件/目录ID
            new_name: 新名称
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            bool: 重命名是否成功
        """
        raise NotImplementedError()
        
    #--------------------------------------------------
    # 分享与传输
    #--------------------------------------------------
        
    def share(
        self,
        *fids: str,
        password: str = None,
        expire_days: int = 0,
        description: str = "",
    ) -> Any:
        """
        分享文件或目录

        Args:
            fids: 要分享的文件或目录ID列表
            password: 分享密码
            expire_days: 分享链接有效期(天),0表示永久有效
            description: 分享描述

        Returns:
            Any: 分享链接信息
        """
        raise NotImplementedError()


    def transfer(
        self,
        source_type: str,
        source_id: str,
        source_path: str,
        target_path: str,
        file_ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> bool:
        """
        从各种来源传输文件到自己的网盘
        
        支持从链接分享、群组分享、好友分享等多种来源传输文件
        
        参数:
            source_type (str): 来源类型，可选值："link"(链接)、"group"(群组)、"friend"(好友)
            source_id (str): 来源ID，根据source_type不同而不同:
                             - 当source_type为"link"时，为分享链接
                             - 当source_type为"group"时，为群组ID
                             - 当source_type为"friend"时，为好友用户ID
            target_path (str): 目标保存路径
            source_path (str): 源文件路径
            file_ids (List[str], 可选): 要传输的文件ID列表，默认传输所有文件
            **kwargs (Any): 其他参数，可能包括:
                           - from_uk: 分享者ID
                           - msg_id: 消息ID
                           - to_uk: 接收者ID (自己的ID)
                           - session_id: 会话ID
                           - ondup: 文件名冲突处理方式，可选值"overwrite"(覆盖)、"newcopy"(使用新副本)、"skip"(跳过)
        
        返回:
            bool: 传输是否成功
            
        示例:
            # 从分享链接传输
            >>> drive.transfer_files("link", "https://pan.example.com/s/1abcdef", "/我的资源", share_password="1234")
            True
            
            # 从群组分享传输
            >>> drive.transfer_files("group", "12345", "/我的资源", file_ids=["file1", "file2"], from_uk="67890", msg_id="msg123")
            True
            
            # 从好友分享传输
            >>> drive.transfer_files("friend", "12345", "/我的资源", file_ids=["file1"], from_uk="67890", msg_id="msg123")
            True
        """
        raise NotImplementedError()
    
    #--------------------------------------------------
    # 搜索与回收站管理
    #--------------------------------------------------

    def search(
        self,
        keyword: str,
        fid: Optional[str] = None,
        file_type: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> List[BaseFileInfo]:
        """
        搜索文件或目录

        Args:
            keyword: 搜索关键词
            fid: 搜索的起始目录ID,默认从根目录开始
            file_type: 文件类型筛选,如'doc','video','image'等
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            List[BaseFileInfo]: 符合条件的文件列表
        """
        raise NotImplementedError()
        
    def get_recycle_list(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> List[BaseFileInfo]:
        """
        获取回收站文件列表

        Args:
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            List[BaseFileInfo]: 回收站中的文件列表
        """
        raise NotImplementedError()

    def restore(self, fid: str, *args: Any, **kwargs: Any) -> bool:
        """
        从回收站恢复文件

        Args:
            fid: 文件ID
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            bool: 恢复是否成功
        """
        raise NotImplementedError()

    def clear_recycle(self, *args: Any, **kwargs: Any) -> bool:
        """
        清空回收站

        Args:
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            bool: 清空是否成功
        """
        raise NotImplementedError()
        
    #--------------------------------------------------
    # 路径与ID转换
    #--------------------------------------------------
        
    def path_to_fid(self, path: str) -> str:
        """将路径转换为文件ID
        
        该方法通过路径来获取文件ID。
        默认实现是通过逐层遍历查找，子类可以重写此方法提供更高效的实现。
        
        Args:
            path: 文件路径
            
        Returns:
            str: 文件ID
        """
        self.logger.debug(f"将路径转换为文件ID: {path}")
        
        if not path or path == "/" or path == "root":
            return "root"
            
        # 规范化路径
        path = path.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
            
        # 按路径分段
        segments = path.split("/")
        segments = [seg for seg in segments if seg]  # 过滤空段
        
        # 从根目录开始遍历
        current_id = "root"
        current_path = ""
        
        for segment in segments:
            current_path += "/" + segment
            self.logger.debug(f"查找路径: {current_path}")
            
            # 获取当前目录下的文件列表
            items = self.get_disk_list(current_id)
            
            # 查找匹配的子项
            found = False
            for item in items:
                if item.name == segment:
                    current_id = item.fid
                    found = True
                    break
            
            if not found:
                self.logger.warning(f"路径不存在: {current_path}")
                return ""
                
        return current_id
        
    def fid_to_path(self, fid: str) -> str:
        """将文件ID转换为路径
        
        该方法需要从文件ID反向构建路径。
        默认实现假设文件记录中有path属性，如果没有则返回空。
        子类应当根据具体实现重写此方法。
        
        Args:
            fid: 文件ID
            
        Returns:
            str: 文件路径
        """
        file_info = self.get_item_info(fid)
        if file_info and file_info.path:
            return file_info.path
        return ""


def get_drive_client(drive_type: DriveType, **config_kwargs: Any) -> Optional[BaseDrive]:
    """
    网盘客户端工厂函数

    根据指定的网盘类型和配置参数，返回相应的网盘客户端实例。

    参数:
        drive_type (DriveType): 网盘类型枚举值。
        **config_kwargs: 传递给特定网盘客户端构造函数的配置参数。
                         例如，对于百度网盘，可能是 bduss, stoken 等。

    返回:
        Optional[BaseDrive]: 成功则返回对应网盘的 BaseDrive 实例，否则返回 None。
    """
    if drive_type == DriveType.BAIDU_DRIVE:
        # 延迟导入以避免循环依赖
        from .baidu.client import BaiduClient
        try:
            # 假设 BaiduClient 的构造函数接受这些参数
            # 我们需要确保 config_kwargs 包含 BaiduClient 初始化所需的参数
            # 例如: bduss, stoken, ptoken, cookies, user_id
            # 如果 BaiduClient 的 __init__ 参数与 BaseDrive 不同，这里需要适配
            # 目前 BaiduClient 的 __init__ 接受 bduss, stoken 等
            return BaiduClient(**config_kwargs)
        except ImportError:
            # Log error or handle missing client implementation
            print(f"错误: 无法导入 {drive_type.value} 客户端。")
            return None
        except TypeError as e:
            print(f"错误: 初始化 {drive_type.value} 客户端失败，参数可能不正确: {e}")
            # 打印出期望的参数和收到的参数会更有帮助
            # import inspect
            # sig = inspect.signature(BaiduClient.__init__)
            # print(f"BaiduClient 需要参数: {sig}")
            # print(f"收到的参数: {config_kwargs}")
            return None
        except Exception as e:
            print(f"错误: 初始化 {drive_type.value} 客户端时发生未知错误: {e}")
            return None
            
    # elif drive_type == DriveType.ALIYUN_DRIVE:
    #     from .aliyun.client import AliyunClient # 假设有阿里云客户端
    #     try:
    #         return AliyunClient(**config_kwargs)
    #     except ImportError:
    #         print(f"错误: 无法导入 {drive_type.value} 客户端。")
    #         return None
    #     except Exception as e:
    #         print(f"错误: 初始化 {drive_type.value} 客户端时发生未知错误: {e}")
    #         return None
            
    else:
        print(f"错误: 不支持的网盘类型: {drive_type}")
        return None
