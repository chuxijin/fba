from __future__ import annotations
from datetime import datetime
import os # Good to have for Pydantic models too
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union

from app.coulddrive.schema.enum import RecursionSpeed, MatchTarget, ItemType, MatchMode, DriveType

class BaseFileInfo(BaseModel):
    """
    网盘文件/目录信息类
    
    作为文件/目录属性的容器，支持类型检查和自动 schema 生成。
    """
    # --- 显式定义字段 ---
    file_id: str = Field(..., description="文件/目录的唯一ID (例如 fs_id)")
    file_name: str = Field(..., description="文件/目录的名称")
    file_path: str = Field(..., description="文件/目录的完整路径")
    is_folder: bool = Field(False, description="是否为文件夹")
    file_size: Optional[int] = Field(None, description="文件大小(字节)，文件夹通常为None或0")
    parent_id: Optional[str] = Field("", description="父目录ID")
    created_at: Optional[str] = Field("", description="创建时间戳 (字符串形式)") # 或使用 datetime
    updated_at: Optional[str] = Field("", description="更新时间戳 (字符串形式)") # 或使用 datetime
    # 用于存储来自API的、未显式映射到上述字段的其他所有信息
    file_ext: Dict[str, Any] = Field(default_factory=dict, description="扩展信息字典，包含API返回的其他未映射字段")

    model_config = {
        "from_attributes": True, 
        "arbitrary_types_allowed": True 
    }
    
    @property
    def filename(self) -> str:
        """
        获取文件名（不含路径部分，仅文件名本身）
        
        注意: BaseFileInfo.file_name 通常已经是纯文件名。
        如果 BaseFileInfo.file_name *可能* 包含路径，则 os.path.basename 是正确的。
        如果 BaseFileInfo.file_name *保证* 是纯文件名，则可以直接返回 self.file_name。
        为安全起见，保留 os.path.basename，以防 file_name 构造方式不一致。
        """
        # 假设 self.file_name 可能包含路径，尽管通常它应该是纯文件名。
        # 如果确定 self.file_name 总是纯文件名，可以直接 return self.file_name
        return os.path.basename(self.file_name) 

    def __repr__(self) -> str:
        """
        字符串表示
        """
        if self.is_folder:
            return f"BaseFileInfo(file_id='{self.file_id}', file_name='{self.file_name}', folder=True)"
        else:
            return f"BaseFileInfo(file_id='{self.file_id}', file_name='{self.file_name}', file_size={self.file_size})"

class BaseShareInfo:
    """
    网盘分享信息基类
    
    提供网盘分享信息的基础属性和方法
    """
    
    def __init__(
        self,
        share_id: str = "",
        title: str = "",
        share_url: str = "",
        created_at: Optional[datetime] = None,
        **kwargs
    ):
        """
        初始化分享信息
        
        参数:
            share_id: 分享ID
            title: 分享标题
            share_url: 分享链接
            created_at: 创建时间
            kwargs: 其他扩展属性
        """
        self.share_id = share_id
        self.title = title
        self.share_url = share_url
        self.created_at = created_at
        self.__dict__.update(kwargs)
        
    def __str__(self) -> str:
        """字符串表示"""
        return f"BaseShareInfo(share_id='{self.share_id}', title='{self.title}')"


def get_filepath(
    filedir: str = None,
    filename: str = None,
    filepath: str = None,
) -> str:
    """
    获取文件完整路径
    
    根据提供的目录路径和文件名，或直接提供的完整路径，构建文件的完整路径
    
    参数:
        filedir: 文件目录路径
        filename: 文件名
        filepath: 完整的文件路径

    返回:
        str: 文件的完整路径
        
    示例:
        >>> get_filepath(filedir="/downloads", filename="file.txt")
        "/downloads/file.txt"
        >>> get_filepath(filepath="/downloads/file.txt")
        "/downloads/file.txt"
    """
    if filepath is not None:
        return filepath
    elif filedir is not None and filename is not None:
        return os.path.join(filedir, filename)
        
    return None

class ExclusionRuleDefinition(BaseModel):
    pattern: str
    target: MatchTarget = MatchTarget.NAME 
    item_type: ItemType = ItemType.ANY     
    mode: MatchMode = MatchMode.CONTAINS     
    case_sensitive: bool = False

class RenameRuleDefinition(BaseModel):
    match_regex: str
    replace_string: str
    target_scope: MatchTarget = MatchTarget.NAME 
    case_sensitive: bool = False

class ShareSourceDefinition(BaseModel):
    file_path: str = Field(..., description="分享内部的相对路径，必须以分享事件的根项目名开始。例如：'/MySharedFolder/SubDir'")
    source_type: str = Field(..., description="分享来源: 'friend' 或 'group'")
    source_id: str = Field(..., description="分享来源ID (好友UK或群组GID)")
    ext_params: Dict[str, Any] = Field(default_factory=dict, description="扩展参数，用于存储额外需要的参数，如msg_id等")

    @validator('file_path')
    def check_share_file_path(cls, v):
        if not v or v == "/":
             raise ValueError("分享内部路径 'file_path' 必须指定分享内的具体项目路径，不能是空或根路径 '/'。例如：'/MySharedFolder/SubDir'")
        if not v.startswith("/"):
            raise ValueError("分享内部路径 'file_path' 必须以 '/' 开头。")
        return v

    @validator('source_type')
    def check_share_source_type(cls, v):
        if v not in ['friend', 'group']:
            raise ValueError("分享来源类型 'source_type' 必须是 'friend' 或 'group'")
        return v

class DiskTargetDefinition(BaseModel):
    file_path: str = Field(..., description="用户云盘中的绝对路径。例如：'/My Pictures/Holidays'")
    file_id: str = Field(..., description="'file_path' 参数对应目录的 fs_id。根目录通常是 '0' 或特定ID。") # Adjusted description

    @validator('file_path')
    def check_disk_file_path(cls, v):
        if not v :
            raise ValueError("用户云盘路径 'file_path' 不能为空。")
        if not v.startswith("/"):
            # Allow non-slashed for root if file_id indicates root, but generally enforce for clarity
            # For now, let's be strict, user can provide "/" for root.
            raise ValueError("用户云盘路径 'file_path' 必须以 '/' 开头。")
        return v
        
# SourceListParams is removed as its functionality is split and incorporated into new models and CompareRequest

class CompareRequest(BaseModel):
    drive_type: str = Field("baidu", description="网盘类型 (例如 'baidu')")
    recursive: bool = Field(False, description="是否递归获取源和目标列表的所有子项")
    recursion_speed: RecursionSpeed = Field(RecursionSpeed.NORMAL, description="递归获取时的速度控制 (统一应用于源和目标)")
    
    source_definition: ShareSourceDefinition = Field(..., description="源定义 (分享内容)")
    target_definition: DiskTargetDefinition = Field(..., description="目标定义 (用户云盘位置)")
    
    comparison_mode: str = Field("incremental", description="对比模式: 'incremental' 或 'full_sync'")
    exclude_rules: Optional[List[ExclusionRuleDefinition]] = Field(None, description="排除规则列表 (应用于源和目标列表的获取)")
    rename_rules: Optional[List[RenameRuleDefinition]] = Field(None, description="重命名规则列表 (应用于源列表的项，在比较前进行转换)")


class CompareResultData(BaseModel):
    """比较结果数据模型"""
    drive_type: str = Field(..., description="网盘类型 (例如 'baidu')")
    source_list_time: float = Field(..., description="获取源列表耗时（秒）")
    target_list_time: float = Field(..., description="获取目标列表耗时（秒）")
    source_list_num: int = Field(..., description="源列表文件总数")
    target_list_num: int = Field(..., description="目标列表文件总数")
    to_add: List[BaseFileInfo] = Field(..., description="需要添加的文件列表")
    to_update_in_target: List[Dict[str, BaseFileInfo]] = Field(..., description="需要更新到目标的文件列表")
    to_delete_from_target: List[BaseFileInfo] = Field(..., description="需要从目标删除的文件列表")
    to_rename_in_target: List[Dict[str, Any]] = Field(..., description="需要重命名的文件列表")
    source_definition: ShareSourceDefinition = Field(..., description="源定义")
    target_definition: DiskTargetDefinition = Field(..., description="目标定义")

class MkdirRequest(BaseModel):
    """创建文件夹的请求模型"""
    drive_type: str = Field("baidu", description="网盘类型 (当前仅支持 'baidu')")
    file_path: str = Field(..., description="要创建的文件夹完整路径")
    parent_id: Optional[str] = Field(None, description="父文件夹ID (可选，百度网盘不使用此参数)")
    file_name: Optional[str] = Field(None, description="文件夹名称 (可选，百度网盘不使用此参数)")
    return_if_exist: bool = Field(True, description="如果文件夹已存在是否返回已存在文件夹信息")

class RemoveRequest(BaseModel):
    """删除文件/目录的请求模型"""
    drive_type: str = Field(default="baidu", description="网盘类型 (当前仅支持 'baidu')")
    file_paths: Optional[Union[str, List[str]]] = Field(None, description="要删除的文件/目录路径，可以是单个路径字符串或路径数组")
    file_ids: Optional[Union[str, List[str]]] = Field(None, description="要删除的文件/目录ID，可以是单个ID字符串或ID数组。如果提供，将优先使用ID进行删除")
    parent_id: Optional[str] = Field(None, description="父目录ID (百度网盘不使用此参数)")
    file_name: Optional[str] = Field(None, description="文件/目录名称 (百度网盘不使用此参数)") 

class TransferRequest(BaseModel):
    drive_type: str = Field("baidu", description="网盘类型 (当前仅支持 'baidu')")
    source_type: str = Field(..., description="来源类型 ('link', 'friend', 'group')")
    source_id: str = Field(..., description="来源ID (分享链接URL, 好友UK, 或群组GID)")
    source_path: str = Field(..., description="源文件/目录在分享中的路径 (百度网盘通常忽略此参数，但为接口兼容保留)")
    target_path: str = Field(..., description="文件/目录在用户自己网盘中保存的目标路径")
    file_ids: Optional[List[Union[int, str]]] = Field(None, description="要传输的文件/目录的 fs_id 列表")
    ext: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="百度网盘转存所需的额外参数，包括：\n"
                   "- msg_id (str): 消息ID，对于 'friend' 和 'group' 类型转存必需\n"
                   "- from_uk (str): 分享者的用户ID (UK)，当 source_type 为 'group' 时必需\n"
                   "- ondup (str): 文件名冲突时的处理方式，可选值: 'newcopy'(默认), 'skip'\n"
                   "- async (int): 是否异步执行，可选值: 1(默认，异步), 0(同步)"
    )

    @validator('source_type')
    def validate_source_type(cls, v):
        if v not in ['link', 'friend', 'group']:
            raise ValueError("source_type 必须是 'link', 'friend' 或 'group' 之一")
        return v

    @validator('target_path')
    def validate_target_path(cls, v):
        if not v.startswith('/'):
            return '/' + v
        return v

    class Config:
        # 允许额外的字段被放入 ext
        extra = "allow"

class ListFilesParams(BaseModel):
    """
    文件列表获取参数模型
    """
    drive_type: str = Field("baidu", description="网盘类型 (当前仅支持 'baidu')")
    file_id: Optional[str] = Field(None, description="要列出内容的文件夹ID (fs_id)。如果提供，则必须是目标文件夹的有效ID。优先于 file_path。")
    file_path: Optional[str] = Field(None, description="要列出内容的文件夹路径。仅在未提供 file_id 时使用以查找 file_id。")
    recursive: bool = Field(False, description="是否递归获取所有子项")
    recursion_speed: RecursionSpeed = Field(RecursionSpeed.NORMAL, description="递归获取速度")
    desc: bool = Field(False, description="是否按降序排序")
    name: bool = Field(False, description="是否按名称排序")
    time: bool = Field(False, description="是否按时间排序")
    size_sort: bool = Field(False, alias="size", description="是否按大小排序")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, alias="size", description="每页数量")
    exclude_rules: Optional[str] = Field(None, alias="exclude_rules", description="排除规则的JSON字符串")
    
    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }

class ListShareFilesParams(BaseModel):
    """
    分享文件列表获取参数模型
    """
    drive_type: str = Field("baidu", description="网盘类型 (当前仅支持 'baidu')")
    source_type: str = Field(..., description="分享来源类型 ('friend' 或 'group')")
    source_id: str = Field(..., description="分享来源ID (好友的UK或群组的GID)")
    file_path: str = Field(..., description="分享内部的路径。必须以分享事件的根项目名开始，例如：'/我的分享根文件夹/内部子路径'。")
    recursive: bool = Field(False, description="是否递归获取所有子项")
    recursion_speed: RecursionSpeed = Field(RecursionSpeed.NORMAL, description="递归获取速度")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, alias="size", description="每页数量")
    exclude_rules: Optional[str] = Field(None, alias="exclude_rules", description="排除规则的JSON字符串")
    
    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }