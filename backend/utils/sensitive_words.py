#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.core.conf import settings


def contains_sensitive_words(text: str | None) -> bool:
    """
    检测文本是否包含敏感词

    :param text: 待检测的文本
    :return: 是否包含敏感词
    """
    if not text:
        return False

    # 将文本转换为小写，提高匹配准确率
    text_lower = text.lower()

    # 检查是否包含任何敏感词
    for sensitive_word in settings.SENSITIVE_WORDS:
        if sensitive_word.lower() in text_lower:
            return True

    return False


def get_matched_sensitive_words(text: str | None) -> list[str]:
    """
    获取文本中匹配到的所有敏感词

    :param text: 待检测的文本
    :return: 匹配到的敏感词列表
    """
    if not text:
        return []

    # 将文本转换为小写，提高匹配准确率
    text_lower = text.lower()
    matched_words = []

    # 收集所有匹配的敏感词
    for sensitive_word in settings.SENSITIVE_WORDS:
        if sensitive_word.lower() in text_lower:
            matched_words.append(sensitive_word)

    return matched_words
