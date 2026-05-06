from enum import Enum


class DriveType(Enum):
    """支持的网盘类型枚举"""
    BAIDU_DRIVE = "BaiduDrive"
    QUARK_DRIVE = "QuarkDrive"
    ALIST_DRIVE = "AlistDrive"
    LOCAL_FILE = "LocalFile"

class RecursionSpeed(Enum):
    """递归获取列表时的速度控制"""
    NORMAL = "normal" # 正常速度，无暂停
    SLOW = "slow"     # 慢速，在每次请求子目录前暂停
    FAST = "fast"     # 快速，优先使用数据库缓存，提升响应速度

class MatchTarget(Enum):
    NAME = "name"  # Match against BaseFileInfo.file_name
    PATH = "path"  # Match against BaseFileInfo.file_path
    EXTENSION = "extension" # Match against the file extension from BaseFileInfo.file_name

class ItemType(Enum):
    FILE = "file"
    FOLDER = "folder"
    ANY = "any"

class MatchMode(Enum):
    REGEX = "regex"
    EXACT = "exact"
    WILDCARD = "wildcard" # e.g., "*.txt", "folder/*"
    CONTAINS = "contains"

class SyncMethod(Enum):
    """同步方式枚举"""
    INCREMENTAL = "incremental"  # 增量同步：只添加新文件，不删除目标中已有的文件
    FULL = "full"                # 完全同步：添加新文件，删除目标中多余的文件
    OVERWRITE = "overwrite"      # 覆盖同步：删除目标中所有文件，然后添加源中的所有文件

class ResourceType(Enum):
    """资源类型枚举"""
    COURSE = "课程"
    EBOOK = "电子书"
    NOTE = "笔记"
    SOFTWARE = "软件"
    EXAM_PAPER = "真题"