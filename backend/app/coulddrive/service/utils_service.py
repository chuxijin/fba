"""
文件名: utils.py
描述: 提供网盘应用通用工具函数，包括JSON处理、时间格式化、大小转换、二进制处理和随机功能
作者: PanMaster团队
创建日期: 2023-04-03
最后修改: 2024-04-23
版本: 1.2.0
"""

# 标准库
from hashlib import md5
import json
import math
import string
import time
import struct
import random
import os
import re
from functools import partial
from datetime import datetime
from typing import Union, Optional, Any, Dict

# ==================== JSON处理函数 ====================

def dump_json(obj: Any) -> str:
    """
    将对象转换为紧凑的JSON字符串
    
    将对象序列化为没有多余空格的JSON字符串，支持中文等非ASCII字符
    
    参数:
        obj (Any): 要序列化的Python对象
    
    返回:
        str: 序列化后的JSON字符串
    """
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

# ==================== 文件大小处理函数 ====================

def human_size(size: int) -> str:
    """
    将字节大小转换为人类可读的格式
    
    根据大小自动选择合适的单位（B, KB, MB, GB, TB）
    
    参数:
        size (int): 字节大小
    
    返回:
        str: 格式化后的大小字符串，如"1.5 MB"
    
    示例:
        >>> human_size(1536)
        '1.5 KB'
    """
    s = float(size)
    v = ""
    t = ""
    for t in ["B", "KB", "MB", "GB", "TB"]:
        if s < 1024.0:
            v = f"{s:3.1f}"
            break
        s /= 1024.0
    if v.endswith(".0"):
        v = v[:-2]
    return f"{v} {t}"


_nums_set = set(string.digits + ".")


def human_size_to_int(size_str: str) -> int:
    """
    将人类可读的大小格式转换回字节整数
    
    支持各种单位（KB, MB, GB, TB）转换为字节大小
    
    参数:
        size_str (str): 大小字符串，如"1.5 GB"
    
    返回:
        int: 字节大小
    
    示例:
        >>> human_size_to_int("1.5 MB")
        1572864
    """
    size_str = size_str.strip()
    if not size_str:
        return 0

    i = 0
    while i < len(size_str):
        if size_str[i] in _nums_set:
            i += 1
            continue
        else:
            break

    if i == 0:
        return 0

    s = float(size_str[:i])
    _s = s

    unit = size_str[i:].upper().replace(" ", "")
    if not unit:
        return math.floor(_s)

    for t in ["KB", "MB", "GB", "TB"]:
        _s *= 1024
        if unit == t or unit[0] == t[0]:
            return math.floor(_s)

    return math.floor(s)

# ==================== 时间格式处理函数 ====================
def now_timestamp() -> int:
    """
    获取当前的Unix时间戳（秒）
    
    返回当前系统时间的秒级时间戳
    
    返回:
        int: 当前时间的Unix时间戳（秒）
    
    示例:
        >>> now_timestamp()
        1617456789
    """
    return int(time.time())

def format_time(time_input: Union[int, float, str]) -> str:
    """
    将时间输入转换为标准格式的日期时间字符串
    
    支持毫秒级时间戳、Unix时间戳和ISO 8601格式字符串
    
    参数:
        time_input (Union[int, float, str]): 时间输入，可以是：
            - 毫秒级时间戳(>9999999999)
            - Unix时间戳(秒)
            - ISO 8601格式字符串
    
    返回:
        str: 格式化的日期时间字符串"YYYY-MM-DD HH:MM:SS"，无效输入返回空字符串
    
    示例:
        >>> format_time(1617456000000)  # 毫秒级时间戳
        '2021-04-03 18:00:00'
        >>> format_time(1617456000)  # Unix时间戳
        '2021-04-03 18:00:00'
        >>> format_time("2021-04-03T18:00:00")  # ISO 8601
        '2021-04-03 18:00:00'
    """
    from datetime import datetime
    
    try:
        if isinstance(time_input, (int, float)):
            # 处理时间戳（秒级或毫秒级）
            if time_input > 9999999999:  # 毫秒级时间戳
                time_input = time_input / 1000
            return datetime.fromtimestamp(time_input).strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(time_input, str):
            # 处理日期时间字符串
            # 尝试解析ISO 8601格式
            if "T" in time_input:
                try:
                    dt = datetime.strptime(time_input, "%Y-%m-%dT%H:%M:%S")
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            else:
                try:
                    dt = datetime.strptime(time_input, "%Y-%m-%d %H:%M:%S")
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            return ""
        return ""
    except (ValueError, TypeError, OverflowError, OSError):
        return ""

# ==================== 随机功能函数 ====================

# 64位无符号整数的最大值
MAX_U64 = 1 << 64

# 安全的随机洗牌函数，使用操作系统提供的高质量随机源
shuffle = partial(
    random.shuffle, random=lambda: struct.unpack("Q", os.urandom(8))[0] / MAX_U64
)

# ==================== MD5处理函数 ====================

def calu_md5(buf: Union[str, bytes], encoding="utf-8") -> str:
    assert isinstance(buf, (str, bytes))

    if isinstance(buf, str):
        buf = buf.encode(encoding)
    return md5(buf).hexdigest()
        
def normalize_path(path: str) -> str:
    """
    规范化文件路径
    
    处理重复的斜杠，确保路径格式一致
    
    参数:
        path (str): 原始路径
        
    返回:
        str: 规范化后的路径
        
    示例:
        >>> normalize_path("//folder//subfolder/file.txt")
        '/folder/subfolder/file.txt'
        >>> normalize_path("/")
        '/'
    """
    # 替换连续的斜杠为单个斜杠
    normalized = re.sub(r'/{2,}', '/', path)
    
    # 确保以/开头
    if not normalized.startswith('/'):
        normalized = '/' + normalized
        
    # 去除结尾的/（除非是根目录）
    if normalized.endswith('/') and len(normalized) > 1:
        normalized = normalized[:-1]
        
    return normalized