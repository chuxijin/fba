#!/usr/bin/env python3


def safe_path_segment(value: str | None, default: str = 'file', max_length: int = 80) -> str:
    """
    清理 Windows 和 URL 存储路径片段

    :param value: 原始路径片段
    :param default: 默认名称
    :param max_length: 最大长度
    :return:
    """
    invalid_chars = '<>:"/\\|?*'
    raw_value = str(value or '').strip()
    cleaned_chars: list[str] = []
    for char in raw_value:
        if ord(char) < 32 or char in invalid_chars:
            cleaned_chars.append('_')
            continue
        if char.isspace():
            cleaned_chars.append('_')
            continue
        cleaned_chars.append(char)

    segment = ''.join(cleaned_chars).strip(' .')
    while '__' in segment:
        segment = segment.replace('__', '_')

    if not segment:
        segment = default

    reserved_names = {
        'CON',
        'PRN',
        'AUX',
        'NUL',
        'COM1',
        'COM2',
        'COM3',
        'COM4',
        'COM5',
        'COM6',
        'COM7',
        'COM8',
        'COM9',
        'LPT1',
        'LPT2',
        'LPT3',
        'LPT4',
        'LPT5',
        'LPT6',
        'LPT7',
        'LPT8',
        'LPT9',
    }
    if segment.upper() in reserved_names:
        segment = f'{segment}_file'

    segment = segment[:max_length].rstrip(' .')
    if not segment:
        return default
    return segment
