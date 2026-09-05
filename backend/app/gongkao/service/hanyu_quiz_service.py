#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.model import GkHanyu
from backend.app.gongkao.model.hanyu_group import GkHanyuGroup, GkHanyuGroupItem
from backend.app.gongkao.schema.hanyu_quiz import (
    GetQuizSession,
    QuizOption,
    QuizQuestion,
    SubmitQuizParam,
    SubmitQuizResult,
)
from backend.app.gongkao.schema.hanyu_review import HanyuGroupItemOut, HanyuGroupOut


class HanyuQuizService:
    """全局选词检验服务类（以近义辨析组为驱动核心）"""

    @staticmethod
    def _clean_idiom_definition(word: str, raw_def: str) -> str:
        """
        清洗成语字典释义中的“字面逐字拆解”前缀与原词名泄露
        例如: ““功”，成功；“近”，眼前的。急于求成...” -> “急于求成...”
        """
        if not raw_def:
            return ''
        text = raw_def.strip()

        # 1. 替换完整词名泄露 (如: "如履薄冰的意思是..." -> "意思是...")
        text = text.replace(word, '该词')

        import re

        # 2. 尝试提取 "指/形容/比喻/意思/多指/表示/现指/泛指/极言" 开头的核心句
        m = re.search(r'(?:[。；;]|\A)\s*(指|形容|比喻|意思[是为]?|多指|表示|现指|泛指|原形容|极言)([^。；]+(?:[。；].*)?)', text)
        if m:
            core = m.group(1) + m.group(2)
            if len(core) >= 8:
                return core.strip()

        # 3. 若无显式标志词，切分并剔除过短的拆字分句 (如: “功”，成功 或 履：踩)
        parts = re.split(r'[。；;]', text)
        cleaned_parts = []
        for p in parts:
            p_str = p.strip()
            if not p_str:
                continue
            if re.match(r'^(?:[“”"]?[\u4e00-\u9fa5]{1,2}[“”"]?[：:，,]|[“”"][\u4e00-\u9fa5]{1,2}[“”"])', p_str) and len(p_str) <= 12:
                continue
            cleaned_parts.append(p_str)

        if cleaned_parts:
            res = '。'.join(cleaned_parts)
            return res + ('。' if not res.endswith('。') else '')

        return text

    @classmethod
    def _extract_gk_hanyu_meaning(cls, word: str, hanyu: GkHanyu | None, fallback_emphasis: str = '') -> str:
        """从 gk_hanyu 表提取标准权威释义并进行反泄题清洗"""
        raw_meaning = ''
        if hanyu:
            if hanyu.definition_info:
                if isinstance(hanyu.definition_info, dict):
                    d = hanyu.definition_info.get('definition') or hanyu.definition_info.get('mean')
                    if d and str(d).strip():
                        raw_meaning = str(d).strip()
                elif isinstance(hanyu.definition_info, str) and hanyu.definition_info.strip():
                    raw_meaning = hanyu.definition_info.strip()

            if not raw_meaning and hanyu.detail_means:
                if isinstance(hanyu.detail_means, list) and len(hanyu.detail_means) > 0:
                    first = hanyu.detail_means[0]
                    if isinstance(first, dict):
                        m = first.get('mean') or first.get('definition')
                        if m and str(m).strip():
                            raw_meaning = str(m).strip()
                    elif isinstance(first, str) and first.strip():
                        raw_meaning = first.strip()
                elif isinstance(hanyu.detail_means, dict):
                    first_val = next(iter(hanyu.detail_means.values()), '')
                    if isinstance(first_val, list) and len(first_val) > 0:
                        raw_meaning = str(first_val[0]).strip()
                    elif isinstance(first_val, str) and first_val.strip():
                        raw_meaning = first_val.strip()

        # 对提取出的原始释义进行防泄题清洗
        if raw_meaning:
            cleaned = cls._clean_idiom_definition(word, raw_meaning)
            if len(cleaned) >= 6:
                return cleaned

        if fallback_emphasis and fallback_emphasis.strip():
            return cls._clean_idiom_definition(word, fallback_emphasis.strip())

        return f'指{word}，多用于特定语境。'

    async def generate_quiz_session(
        self,
        db: AsyncSession,
        *,
        quiz_type: str = 'meaning_to_word',
        count: int = 10,
    ) -> GetQuizSession:
        """
        以辨析组为核心生成选词检验题目：
        1. 在 gk_hanyu_group 中随机抽取有效辨析组；
        2. 从 gk_hanyu_group_item 取出对应 2~4 个词项（有几个出几个选项，不硬凑 4 个）；
        3. 释义统一取自 gk_hanyu 权威底库。

        :param db: 数据库会话
        :param quiz_type: meaning_to_word (看释义选词) 或 word_to_meaning (看词选释义)
        :param count: 题量 (默认 10)
        :return:
        """
        count = max(5, min(30, count))

        # 1. 查找包含至少 2 个条目的辨析组 ID 集合
        stmt_valid_groups = (
            select(GkHanyuGroupItem.group_id)
            .group_by(GkHanyuGroupItem.group_id)
            .having(func.count(GkHanyuGroupItem.id) >= 2)
        )
        res_valid_groups = await db.execute(stmt_valid_groups)
        valid_group_ids = [gid for (gid,) in res_valid_groups.all()]

        if not valid_group_ids:
            return GetQuizSession(quiz_type=quiz_type, total_count=0, questions=[])

        # 2. 随机抽样 count 个组
        chosen_group_ids = random.sample(valid_group_ids, min(count, len(valid_group_ids)))

        stmt_groups = select(GkHanyuGroup).where(GkHanyuGroup.id.in_(chosen_group_ids))
        res_groups = await db.execute(stmt_groups)
        groups_map = {g.id: g for g in res_groups.scalars().all()}

        questions: list[QuizQuestion] = []
        option_letters = ['A', 'B', 'C', 'D', 'E', 'F']

        for idx, gid in enumerate(chosen_group_ids, 1):
            group = groups_map.get(gid)
            if not group:
                continue

            # 取出该组的所有 items
            stmt_items = (
                select(GkHanyuGroupItem)
                .where(GkHanyuGroupItem.group_id == gid)
                .order_by(GkHanyuGroupItem.sort_order)
            )
            res_items = await db.execute(stmt_items)
            group_items = res_items.scalars().all()

            if len(group_items) < 2:
                continue

            # 关联 gk_hanyu 提取权威释义与拼音
            item_data_list = []
            for it in group_items:
                stmt_h = (
                    select(GkHanyu)
                    .where((GkHanyu.id == it.hanyu_id) | (GkHanyu.name == it.word))
                    .limit(1)
                )
                res_h = await db.execute(stmt_h)
                h_obj = res_h.scalar_one_or_none()
                meaning = self._extract_gk_hanyu_meaning(it.word, h_obj, it.emphasis or '')

                item_data_list.append({
                    'item': it,
                    'hanyu': h_obj,
                    'hanyu_id': h_obj.id if h_obj else it.hanyu_id,
                    'word': it.word,
                    'pinyin': h_obj.pinyin if h_obj else None,
                    'meaning': meaning,
                    'emphasis': it.emphasis,
                    'collocation': it.collocation,
                })

            # 如果组内词数 > 4，随机截取 4 个
            if len(item_data_list) > 4:
                item_data_list = random.sample(item_data_list, 4)

            # 随机指定其中一个为考查目标（Target）
            target_data = random.choice(item_data_list)

            # 构建当前题的选项（组内所有词，打乱顺序）
            raw_options = []
            for d in item_data_list:
                is_correct = (d['word'] == target_data['word'])
                content = d['word'] if quiz_type == 'meaning_to_word' else d['meaning']
                raw_options.append({
                    'word': d['word'],
                    'content': content,
                    'hanyu_id': d['hanyu_id'],
                    'is_correct': is_correct,
                })

            random.shuffle(raw_options)

            # 分配选项标识 (A/B 或 A/B/C 或 A/B/C/D)
            final_options: list[QuizOption] = []
            correct_key = 'A'

            for o_idx, opt in enumerate(raw_options):
                key = option_letters[o_idx]
                if opt['is_correct']:
                    correct_key = key
                final_options.append(
                    QuizOption(
                        key=key,
                        content=opt['content'],
                        hanyu_id=opt['hanyu_id'],
                        is_correct=opt['is_correct'],
                    )
                )

            # 设置题干
            if quiz_type == 'meaning_to_word':
                stem = target_data['meaning']
            else:
                stem = target_data['word']

            # 组装辨析组详情供答错/复盘即时查看
            group_out = HanyuGroupOut(
                id=group.id,
                title=group.title,
                group_no=group.group_no,
                category=group.category,
                summary=group.summary,
                items=[
                    HanyuGroupItemOut(
                        hanyu_id=d['hanyu_id'],
                        word=d['word'],
                        emphasis=d['emphasis'],
                        collocation=d['collocation'],
                        is_current=(d['word'] == target_data['word']),
                    )
                    for d in item_data_list
                ],
            )

            questions.append(
                QuizQuestion(
                    question_id=idx,
                    quiz_type=quiz_type,
                    target_hanyu_id=target_data['hanyu_id'] or 0,
                    target_word=target_data['word'],
                    target_pinyin=target_data['pinyin'],
                    target_meaning=target_data['meaning'],
                    stem=stem,
                    options=final_options,
                    correct_key=correct_key,
                    commentary=target_data['emphasis'],
                    bianxi_groups=[group_out],
                )
            )

        return GetQuizSession(
            quiz_type=quiz_type,
            total_count=len(questions),
            questions=questions,
        )

    @staticmethod
    async def submit_quiz(
        db: AsyncSession,
        *,
        user_id: int,
        obj: SubmitQuizParam,
    ) -> SubmitQuizResult:
        """
        提交测验结果

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 提交数据
        :return:
        """
        percent = int(round((obj.correct_count / max(1, obj.total_count)) * 100))

        if percent == 100:
            eval_text = '🔥 满分登顶！公考言语词汇大师！'
        elif percent >= 80:
            eval_text = '✨ 拔尖水准！成语辨析火眼金睛！'
        elif percent >= 60:
            eval_text = '👍 表现扎实！个别近义成语需巩固。'
        else:
            eval_text = '📚 仍需磨砺！建议多刷词本强化辨析。'

        # 联动打卡学习时长与新词复习量
        from backend.app.gongkao.service.hanyu_checkin_service import hanyu_checkin_service

        await hanyu_checkin_service.update_daily_progress(
            db=db,
            user_id=user_id,
            is_new_word=False,
            duration_ms=obj.duration_ms,
        )
        await db.commit()

        return SubmitQuizResult(
            score_percent=percent,
            evaluation=eval_text,
            correct_count=obj.correct_count,
            total_count=obj.total_count,
        )


hanyu_quiz_service: HanyuQuizService = HanyuQuizService()
