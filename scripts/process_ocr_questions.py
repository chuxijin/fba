#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR题目文本处理脚本
用于从OCR识别结果中提取题目并清洗噪声
"""
import re
from typing import Any


def clean_line(line: str) -> str:
    """
    清理单行文本的噪声

    :param line: 原始行文本
    :return: 清理后的文本
    """
    # 移除行号前缀 (数字→)
    line = re.sub(r'^\s*\d+→', '', line)
    # 移除多余空白
    line = line.strip()
    return line


def is_page_separator(line: str) -> bool:
    """判断是否为页码分隔符"""
    return '========' in line and '第' in line and '页' in line


def is_noise_line(line: str) -> bool:
    """
    判断是否为噪声行

    :param line: 待判断的文本行
    :return: 是否为噪声
    """
    noise_keywords = [
        '关注公众号',
        '有岸上',
        '免费考研资料',
        '无水印PDF',
        '========',
    ]
    return any(keyword in line for keyword in noise_keywords)


def extract_questions(ocr_text: str) -> list[dict[str, Any]]:
    """
    从OCR文本中提取题目信息

    :param ocr_text: OCR识别的原始文本
    :return: 题目列表
    """
    lines = ocr_text.split('\n')
    questions = []

    current_suite = ''  # 当前套卷名称
    current_type = ''   # 当前题型
    current_question = None

    i = 0
    while i < len(lines):
        line = clean_line(lines[i])

        # 跳过空行和噪声行
        if not line or is_page_separator(line) or is_noise_line(line):
            i += 1
            continue

        # 识别套卷标题
        if re.match(r'第[一二三四五六七八]套卷', line):
            current_suite = line
            i += 1
            continue

        # 识别题型
        if '单项选择题' in line or '多项选择题' in line:
            current_type = '单项选择题' if '单项选择题' in line else '多项选择题'
            i += 1
            continue

        # 识别题号（题目开始）
        question_match = re.match(r'^(\d+)[.、]', line)
        if question_match and current_suite and current_type:
            # 保存上一道题
            if current_question:
                questions.append(current_question)

            # 开始新题
            question_num = question_match.group(1)
            question_text = line[question_match.end():].strip()

            current_question = {
                '套卷名称': current_suite,
                '题型': current_type,
                '题号': question_num,
                '题干': question_text,
                '选项A': '',
                '选项B': '',
                '选项C': '',
                '选项D': '',
                '答案': ''
            }
            i += 1
            continue

        # 识别选项
        if current_question:
            option_match = re.match(r'^([A-D])[.、]', line)
            if option_match:
                option_label = f'选项{option_match.group(1)}'
                option_text = line[option_match.end():].strip()
                current_question[option_label] = option_text
            else:
                # 继续累加到题干或当前选项
                if not current_question['选项A']:
                    current_question['题干'] += line
                else:
                    # 找到最后一个非空选项，继续累加
                    for opt in ['选项D', '选项C', '选项B', '选项A']:
                        if current_question[opt]:
                            current_question[opt] += line
                            break

        i += 1

    # 保存最后一道题
    if current_question:
        questions.append(current_question)

    return questions


def main() -> None:
    """主函数"""
    # 读取OCR文件
    ocr_file = r'D:\100_Work\101_Program\Proj\QBT\26腿姐八套卷（试题册）_OCR结果.txt'
    with open(ocr_file, 'r', encoding='utf-8') as f:
        ocr_text = f.read()

    # 提取题目
    questions = extract_questions(ocr_text)

    print(f'共提取 {len(questions)} 道题目')

    # 显示前3道题作为示例
    for i, q in enumerate(questions[:3], 1):
        print(f'\n题目 {i}:')
        print(f"套卷: {q['套卷名称']}")
        print(f"题型: {q['题型']}")
        print(f"题号: {q['题号']}")
        print(f"题干: {q['题干'][:50]}...")
        print(f"选项A: {q['选项A'][:30]}...")


if __name__ == '__main__':
    main()
