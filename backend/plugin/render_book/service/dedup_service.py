# -*- coding: utf-8 -*-
"""
试卷排版试题自动去重与来源标签智能合并服务
核心职责：
1. 规范化题干与选项特征，生成稳定的内容指纹 (SHA-256)，精准判重；
2. 智能解析来源信息并提取公因式合并（例如：【26国考·地市 & 行政执法】）；
3. 对 RenderDocumentPayload 中的试题流水进行去重合并，并平滑顺延题号。
"""

import hashlib
import re
from typing import Any

from backend.plugin.render_book.schema.payload import (
    RenderQuestionOptionPayload,
    RenderQuestionPayload,
    RenderSectionPayload,
)

PROVINCE_SHORT_MAP = {
    '北京': '北京', '天津': '天津', '上海': '上海', '重庆': '重庆',
    '河北': '河北', '山西': '山西', '辽宁': '辽宁', '吉林': '吉林',
    '黑龙江': '黑龙江', '江苏': '江苏', '浙江': '浙江', '安徽': '安徽',
    '福建': '福建', '江西': '江西', '山东': '山东', '河南': '河南',
    '湖北': '湖北', '湖南': '湖南', '广东': '广东', '海南': '海南',
    '四川': '四川', '贵州': '贵州', '云南': '云南', '陕西': '陕西',
    '甘肃': '甘肃', '青海': '青海', '台湾': '台湾',
    '内蒙古': '内蒙', '广西': '广西', '西藏': '西藏',
    '宁夏': '宁夏', '新疆': '新疆',
}


def clean_text_for_fingerprint(text: str | None) -> str:
    """提取纯净正文用于比对指纹（去除 HTML、题号前缀、空白字符与标点噪音）"""
    if not text:
        return ''
    # 1. 过滤 HTML 标签与转义符
    s = re.sub(r'<[^>]+>', '', text)
    s = s.replace('&nbsp;', '').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    # 2. 去除首部常见序号（如 "1. "、"1、"、"第1题 "）
    s = re.sub(r'^(?:第?\s*\d+\s*[题\.\、\:\s]\s*)+', '', s)
    # 3. 去除所有空白字符（空格、换行、制表符、全角空格）
    s = re.sub(r'[\s\u3000\xa0]+', '', s)
    # 4. 去除标点符号差异（避免中英文标点或空格影响哈希）
    s = re.sub(r'[，。！？；：、“”‘’\"\'\(\)（）\-\_\—\.\,\;\:\?\!]', '', s)
    return s.strip()


def build_question_fingerprint(
    stem: str | None,
    options: list[Any] | None = None,
) -> str:
    """
    联合题干纯文本与核心选项特征计算 SHA-256 内容指纹：
    - 绝不因“根据以下资料回答下列各题”等公共设问发生误判；
    - 只要题干与选项一致，不论题号或排版差异，均能精准命中。
    """
    clean_stem = clean_text_for_fingerprint(stem)

    clean_opts_list = []
    if options:
        for opt in options:
            if isinstance(opt, RenderQuestionOptionPayload):
                raw_opt = opt.content_text
            elif isinstance(opt, dict):
                raw_opt = str(opt.get('content') or opt.get('value') or opt.get('text') or '')
            else:
                raw_opt = str(opt)
            # 剥离选项序号前缀（如 A.、A、B:、1.、(A)）
            raw_opt_no_prefix = re.sub(r'^[（\(]?[A-Za-z0-9][）\)\.\、\:\s]+', '', raw_opt.strip())
            cleaned_opt = clean_text_for_fingerprint(raw_opt_no_prefix or raw_opt)
            if cleaned_opt:
                clean_opts_list.append(cleaned_opt)

    # 选项按字母或内容稳定排序后再拼合
    clean_opts_list.sort()
    combined = f'{clean_stem}||{"|".join(clean_opts_list)}'
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


class ParsedSource:
    """解析后的试卷来源元数据"""

    def __init__(self, raw: str) -> None:
        self.raw = raw.strip()
        self.year = ''
        self.exam_type = ''
        self.categories: list[str] = []
        self.question_no = ''

        self._parse()

    def _parse(self) -> None:
        text = self.raw
        # 1. 严格提取年份 (必须为4位20xx、显式带'年'字、或两位数紧跟考型/省份简称，绝不能将原题号误判为年份)
        m_year_4 = re.search(r'20(\d{2})', text)
        if m_year_4:
            self.year = m_year_4.group(1)
        else:
            m_year_2 = re.search(r'(?<!\d)(\d{2})\s*年', text)
            if m_year_2:
                self.year = m_year_2.group(1)
            else:
                prov_pattern = '|'.join(set(PROVINCE_SHORT_MAP.values()))
                m_year_abbr = re.search(rf'(?<!\d)(\d{{2}})\s*[·\s]*(?:国考|省考|联考|事考|粉笔|华图|模考|{prov_pattern})', text)
                if m_year_abbr:
                    self.year = m_year_abbr.group(1)

        # 2. 提取原题号 (如 模考原第47题, 第47题, No.47)
        m_no = re.search(r'(?:模考原第|原第|第)\s*(\d+)\s*题', text)
        if m_no:
            self.question_no = f"No.{m_no.group(1)}"
        else:
            m_no2 = re.search(r'No\.(\d+)', text, re.IGNORECASE)
            if m_no2:
                self.question_no = f"No.{m_no2.group(1)}"

        # 3. 提取考型/主体与类别
        is_mock = '模考' in text or '大赛' in text
        is_joint_exam = ('联考' in text or '多省' in text or bool(re.search(r'(?:0225|0326|0822|0316|0421|0422)', text)))

        if is_mock:
            plat = '华图' if '华图' in text else ('事考帮' if '事考帮' in text else '粉笔')
            self.exam_type = f'{plat}模考'
        elif '国考' in text or '国家公务员' in text or '中央机关' in text:
            self.exam_type = '国考'
        elif is_joint_exam:
            self.exam_type = '联考'
            for prov_full, prov_short in PROVINCE_SHORT_MAP.items():
                if prov_full in text and prov_short not in self.categories:
                    self.categories.append(prov_short)
        else:
            for prov_full, prov_short in PROVINCE_SHORT_MAP.items():
                if prov_full in text:
                    self.exam_type = prov_short
                    break
            if not self.exam_type:
                if '省考' in text:
                    self.exam_type = '省考'
                elif '事考' in text or '事业单位' in text or '事考帮' in text:
                    self.exam_type = '事考'
                else:
                    self.exam_type = '真题'

        # 4. 提取卷种/类别类别（支持多类别并联识别）
        if '副省' in text or '省级' in text or '综合管理' in text:
            if '副省' not in self.categories:
                self.categories.append('副省')
        if '市地' in text or '地市' in text or '市级' in text:
            if '地市' not in self.categories:
                self.categories.append('地市')
        if '行政执法' in text or '执法' in text:
            if '行政执法' not in self.categories:
                self.categories.append('行政执法')
        if '县乡' in text or '乡镇' in text:
            if '县乡' not in self.categories:
                self.categories.append('县乡')

        m_abcs = re.findall(r'([ABCabc])\s*[类卷]?', text)
        for letter in m_abcs:
            abc_tag = f'{letter.upper()}类'
            if abc_tag not in self.categories:
                self.categories.append(abc_tag)


def merge_source_labels(raw_sources: list[str]) -> str | None:
    """
    智能提取公因式合并来源标签：
    - 输入：['2026年国考行测（市地级）', '2026年国考行测（行政执法）']
    - 输出：'26国考·地市 & 行政执法'
    - 输入：['2025年江苏行测A类', '2025年江苏行测B类']
    - 输出：'25江苏·A类 & B类'
    - 输入：['2023年湖北行测', '2023年重庆行测']
    - 输出：'23联考·湖北 & 重庆'
    - 输入：['2027年国考第三十六季行测模考大赛 (模考原第47题)']
    - 输出：'27·粉笔模考 No.47'
    """
    valid_sources = [s.strip() for s in raw_sources if s and s.strip()]
    if not valid_sources:
        return None

    # 去重原始来源
    unique_raw = []
    seen = set()
    for s in valid_sources:
        if s not in seen:
            seen.add(s)
            unique_raw.append(s)

    parsed_list = [ParsedSource(s) for s in unique_raw]

    # 若仅有一条来源且带原题号，优雅保留原题号信息
    if len(parsed_list) == 1 and parsed_list[0].question_no:
        p = parsed_list[0]
        prefix = f'{p.year}·{p.exam_type}' if p.year else p.exam_type
        if p.categories:
            cat_joined = ' & '.join(p.categories)
            return f'{prefix}·{cat_joined} {p.question_no}'
        return f'{prefix} {p.question_no}'

    # 按 (year, exam_type) 分组提取公因式
    groups: dict[tuple[str, str], list[str]] = {}
    for p in parsed_list:
        key = (p.year, p.exam_type)
        cats = p.categories or ['通用']
        for cat in cats:
            if cat not in groups.setdefault(key, []):
                groups[key].append(cat)

    cat_order = {'副省': 1, '地市': 2, '行政执法': 3, '县乡': 4, 'A类': 5, 'B类': 6, 'C类': 7}
    merged_parts = []
    for (year, exam_type), cats in groups.items():
        prefix = f'{year}{exam_type}' if year else exam_type
        cats.sort(key=lambda c: cat_order.get(c, 99))
        if len(cats) == 1 and cats[0] == '通用':
            merged_parts.append(prefix)
        else:
            real_cats = [c for c in cats if c != '通用']
            if real_cats:
                cat_joined = ' & '.join(real_cats)
                merged_parts.append(f'{prefix}·{cat_joined}')
            else:
                merged_parts.append(prefix)

    return ' / '.join(merged_parts)


def deduplicate_and_merge_sections(
    sections: list[RenderSectionPayload],
) -> tuple[list[RenderSectionPayload], int]:
    """
    对多章节试题流水执行去重与来源公因式合并：
    1. 计算每题指纹，若重复则将来源追加到首题，并不再重复输出该题；
    2. 合并后的首题获得精炼的 source_label（如【26国考·地市 & 行政执法】）；
    3. 全卷题号自动顺延重新连续编号（1, 2, 3...）；
    4. 返回 (new_sections, dedup_removed_count)。
    """
    seen_fingerprints: dict[str, RenderQuestionPayload] = {}
    question_sources_map: dict[str, list[str]] = {}

    dedup_count = 0
    new_sections: list[RenderSectionPayload] = []
    global_num = 1

    for sec in sections:
        retained_questions: list[RenderQuestionPayload] = []
        for q in (sec.questions or []):
            fp = build_question_fingerprint(q.stem_text, q.options)

            # 提取本题自身携带的可能来源文本
            q_source = q.source_label or q.source_text or q.bank_name or sec.title
            if not q_source or q_source == sec.title:
                # 尝试从 tags 获取
                for t in (q.tags or []):
                    if '国考' in t or '省考' in t or '联考' in t:
                        q_source = t
                        break

            if fp in seen_fingerprints:
                # 发现重复题：累加来源
                dedup_count += 1
                if q_source:
                    question_sources_map[fp].append(q_source)
            else:
                # 首见题目：登记并保留
                seen_fingerprints[fp] = q
                question_sources_map[fp] = [q_source] if q_source else []
                # 重编连续题号
                q.number = global_num
                global_num += 1
                retained_questions.append(q)

        new_sections.append(
            RenderSectionPayload(
                key=sec.key,
                title=sec.title,
                questions=retained_questions,
                words=sec.words,
            )
        )

    # 第二轮：将合并后的紧凑公因式来源标签回写至保留试题中
    for fp, first_q in seen_fingerprints.items():
        sources = question_sources_map.get(fp, [])
        merged_label = merge_source_labels(sources)
        if merged_label:
            first_q.source_label = merged_label
            if f'【{merged_label}】' not in first_q.tags:
                first_q.tags.append(f'【{merged_label}】')

    return new_sections, dedup_count
