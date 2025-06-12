from enum import Enum

class DriveType(Enum):
    """支持的网盘类型枚举"""
    BAIDU = "BaiduDrive"  # 别名
    BAIDU_DRIVE = "BaiduDrive"
    QUARK_DRIVE = "QuarkDrive"  # 新增夸克网盘
    ALIST_DRIVE = "AlistDrive"  # 新增Alist网盘
    # 在这里可以添加其他网盘类型，例如：
    # ALIYUN_DRIVE = "AliyunDrive"
    # LOCAL_STORAGE = "LocalStorage"

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
    SOFTWARE = "软件"
    EXAM_PAPER = "真题"

class ResourceDomain(Enum):
    """资源领域枚举"""
    EDUCATION = "教育"
    TECHNOLOGY = "科技"
    ENTERTAINMENT = "影视"

class EducationSubject(Enum):
    """教育领域科目枚举"""
    POSTGRADUATE_ENGLISH = "26考研英语"
    POSTGRADUATE_MATH = "26考研数学"
    POSTGRADUATE_POLITICS = "26考研政治"
    POSTGRADUATE_UNIFIED = "26考研统考"
    POSTGRADUATE_NON_UNIFIED = "26考研非统考"

class TechnologySubject(Enum):
    """科技领域科目枚举"""
    PROGRAMMING = "编程开发"
    ARTIFICIAL_INTELLIGENCE = "人工智能"
    DATA_SCIENCE = "数据科学"
    CYBERSECURITY = "网络安全"
    CLOUD_COMPUTING = "云计算"

class EntertainmentSubject(Enum):
    """影视领域科目枚举"""
    MOVIE = "电影"
    SHORT_DRAMA = "短剧"
    TV_SERIES = "电视剧"
    VARIETY_SHOW = "综艺"

# 领域和科目的映射关系
DOMAIN_SUBJECT_MAPPING = {
    ResourceDomain.EDUCATION.value: [subject.value for subject in EducationSubject],
    ResourceDomain.TECHNOLOGY.value: [subject.value for subject in TechnologySubject],
    ResourceDomain.ENTERTAINMENT.value: [subject.value for subject in EntertainmentSubject],
}