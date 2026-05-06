#!/usr/bin/env python3
import re


def extract_option_codes(text: str | list[str]) -> list[str]:
    """
    从答案文本中提取选项编码（如 A、B、C）

    :param text: 答案文本或选项列表
    :return:
    """
    raw = ','.join([str(item) for item in text if str(item).strip()]) if isinstance(text, list) else str(text or '')

    raw = raw.strip().upper()
    if not raw:
        return []

    parts = re.split(r'[\s,，、|]+', raw)
    codes: list[str] = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if token.isalpha():
            if len(token) > 1:
                codes.extend(list(token))
            else:
                codes.append(token)
            continue
        letters = [ch for ch in token if ch.isalpha()]
        if not letters:
            continue
        if len(letters) == 1:
            codes.append(letters[0])
        else:
            codes.extend(letters)

    return codes


def split_answer_text(answer_str: str) -> list[str]:
    """
    按常见分隔符拆分答案文本

    :param answer_str: 答案字符串
    :return:
    """
    if not answer_str:
        return []
    text = str(answer_str)
    for sep in ['\r\n', '\n', '\r', '，', ';', '；', '|', '/', '\\', '、']:
        text = text.replace(sep, ',')
    return [item.strip() for item in text.split(',') if item.strip()]
