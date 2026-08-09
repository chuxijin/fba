#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

import httpx
import re


from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_hanyu import hanyu_dao
from backend.app.gongkao.model import GkHanyu
from backend.app.gongkao.schema.hanyu import (
    CreateHanyuParam,
    DeleteHanyuParam,
    HanyuParam,
    UpdateHanyuParam,
)
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data


class HanyuService:
    """汉语词汇服务类"""

    @staticmethod
    def _extract_words_from_html(html_snippet: str) -> list[str]:
        """
        从 HTML 片段中提取词汇列表

        :param html_snippet: HTML 片段
        :return: 不添加返回说明
        """
        if not html_snippet:
            return []
        words = re.findall(r'<a[^>]*>(.*?)</a>', html_snippet)
        if not words:
            plain_txt = re.sub(r'<[^>]+>', '', html_snippet).strip()
            if plain_txt:
                plain_txt = (
                    plain_txt
                    .replace('、', ' ')
                    .replace('，', ' ')
                    .replace(',', ' ')
                    .replace('；', ' ')
                    .replace(';', ' ')
                )
                words = [w.strip() for w in plain_txt.split() if w.strip()]
        return words

    @staticmethod
    async def _fetch_from_guoxue(name: str) -> dict[str, Any] | None:
        """
        从汉语国学网获取词汇详情

        :param name: 词语名称
        :return: 不添加返回说明
        """
        import urllib.parse

        quoted_name = urllib.parse.quote(name)
        url = f'https://www.hanyuguoxue.com/chengyu/search?words={quoted_name}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                if response.status_code != 200:
                    return None

                html = response.text
                if name not in html:
                    return None

                result = {}

                # 1. 提取拼音
                py_match = re.search(r'<span>拼音<i>：</i></span>\s*([^<]+)', html)
                if py_match:
                    result['pinyin'] = py_match.group(1).replace('怎么读', '').strip()
                else:
                    py_match2 = re.search(r'<div class="pinyin"><span>(.*?)</span>', html)
                    if py_match2:
                        result['pinyin'] = py_match2.group(1).strip()

                # 2. 提取释义
                def_match = re.search(r'<p class="explain primary">(.*?)</p>', html, re.S)
                if def_match:
                    def_text = def_match.group(1)
                    def_text = re.sub(r'<button[^>]*>.*?</button>', '', def_text, flags=re.S)
                    def_text = re.sub(r'<br\s*/?>', '\n', def_text)
                    definition = re.sub(r'<[^>]+>', '', def_text).strip()
                    result['definition_info'] = {'definition': definition}

                # 3. 提取出处
                cc_match = re.search(r'<span class="name">出处<i>：</i></span>(.*?)</p>', html, re.S)
                if cc_match:
                    cc_text = re.sub(r'<[^>]+>', '', cc_match.group(1)).strip()
                    result['chu_chu'] = [{'source': cc_text}]

                # 4. 提取例句
                liju = []
                example_match = re.search(r'<span class="name">例子<i>：</i></span>(.*?)</p>', html, re.S)
                if example_match:
                    lj_text = re.sub(r'<[^>]+>', '', example_match.group(1)).strip()
                    if lj_text:
                        liju.append(lj_text)

                liju_block_match = re.search(r'<summary>例句</summary>(.*?)</details>', html, re.S)
                if liju_block_match:
                    liju_html = liju_block_match.group(1)
                    notes = re.findall(r'<p class="note"><span class="no">.*?</span>(.*?)</p>', liju_html, re.S)
                    for note in notes:
                        cleaned_note = re.sub(r'<[^>]+>', '', note).strip()
                        if cleaned_note and cleaned_note not in liju:
                            liju.append(cleaned_note)
                if liju:
                    result['liju'] = liju

                # 5. 提取近义词和反义词
                synonyms = []
                antonyms = []
                syn_match = re.search(r'<span>近义词<i>：</i></span>\s*(.*?)</p>', html, re.S)
                if syn_match:
                    synonyms = HanyuService._extract_words_from_html(syn_match.group(1))

                ant_match = re.search(r'<span>反义词<i>：</i></span>\s*(.*?)</p>', html, re.S)
                if ant_match:
                    antonyms = HanyuService._extract_words_from_html(ant_match.group(1))

                result['synonyms'] = [s.strip() for s in synonyms if s.strip()]
                result['antonym'] = [a.strip() for a in antonyms if a.strip()]

                # 6. 提取感情色彩
                bb_match = re.search(r'<span>感情</span>\s*<a[^>]*>([^<]+?)</a>', html)
                if bb_match:
                    baobian = bb_match.group(1).replace('成语', '').strip()
                    result['baobian'] = baobian

                # 7. 提取结构
                str_match = re.search(r'<span>结构</span>\s*<a[^>]*>([^<]+?)</a>', html)
                if str_match:
                    result['structure'] = str_match.group(1).strip()

                return result
        except Exception as e:
            log.error(f'从汉语国学网获取词汇 "{name}" 失败: {e}')
            return None

    @staticmethod
    async def _fetch_from_zdic(name: str) -> dict[str, Any] | None:
        """
        从汉典网获取词汇详情

        :param name: 词语名称
        :return: 不添加返回说明
        """
        import urllib.parse

        quoted_name = urllib.parse.quote(name)
        url = f'https://zdic.net/hans/{quoted_name}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                if response.status_code != 200:
                    return None

                html = response.text
                result = {}

                # 检测是否含有国语辞典区块
                guoyu_match = re.search(r'<section class="dict-section guoyu-section".*?</section>', html, re.S)
                if guoyu_match:
                    gy_html = guoyu_match.group(0)

                    # 1. 提取拼音
                    py_match = re.search(r'<span class="gy-reading__py">(.*?)</span>', gy_html)
                    if py_match:
                        result['pinyin'] = py_match.group(1).strip()

                    # 2. 提取释义（优先从国语辞典释义，更具深度和准确度）
                    def_match = re.search(r'<p class="gy-sense__def">(.*?)</p>', gy_html, re.S)
                    if def_match:
                        definition = def_match.group(1).strip()
                        definition = re.sub(r'<[^>]+>', '', definition).strip()
                        result['definition_info'] = {'definition': definition}

                    # 3. 提取书证/出处
                    cit_items = re.findall(r'<li class="gy-sense__cit-item">(.*?)</li>', gy_html, re.S)
                    if cit_items:
                        cc_list = []
                        for item in cit_items:
                            cleaned = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', item)).strip()
                            cc_list.append(cleaned)
                        if cc_list:
                            result['chu_chu'] = [{'source': '; '.join(cc_list)}]
                else:
                    # 退化到使用默认成语/词语解释解析
                    # 1. 提取拼音
                    py_match = re.search(r'<span class="xxjs-reading__py">(.*?)</span>', html)
                    if py_match:
                        result['pinyin'] = py_match.group(1).strip()
                    else:
                        py_match2 = re.search(r'<span class="meta-pinyin">\s*([^\s<]+)', html)
                        if py_match2:
                            result['pinyin'] = py_match2.group(1).strip()

                    # 2. 提取释义
                    definition = None
                    def_match = re.search(
                        r'<span class="idiom-entry__label">解释</span>\s*<span class="idiom-entry__text">(.*?)</span>',
                        html,
                        re.S,
                    )
                    if def_match:
                        definition = def_match.group(1).strip()
                    else:
                        def_match2 = re.search(r'<div class="xxjs-item__def">\s*(.*?)\s*</div>', html, re.S)
                        if def_match2:
                            definition = def_match2.group(1).strip()

                    if definition:
                        definition = re.sub(r'<[^>]+>', '', definition).strip()
                        result['definition_info'] = {'definition': definition}

                    # 3. 提取出处
                    cc_text = None
                    cc_match = re.search(
                        r'<span class="idiom-entry__label">出处</span>\s*<span class="idiom-entry__text">\s*(.*?)\s*</span>',
                        html,
                        re.S,
                    )
                    if cc_match:
                        cc_text = re.sub(r'<[^>]+>', '', cc_match.group(1)).strip()
                    else:
                        cc_list = re.findall(r'<li class="xxjs-citation__item">(.*?)</li>', html, re.S)
                        if cc_list:
                            cc_text = '; '.join([
                                re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).strip() for c in cc_list
                            ])

                    if cc_text:
                        result['chu_chu'] = [{'source': cc_text}]

                    # 提取例句
                    liju = []
                    lj_match = re.search(
                        r'<span class="idiom-entry__label">示例</span>\s*<span class="idiom-entry__text">\s*(.*?)\s*</span>',
                        html,
                        re.S,
                    )
                    if lj_match:
                        lj_text = re.sub(r'<[^>]+>', '', lj_match.group(1)).strip()
                        if lj_text and lj_text != '无':
                            liju.append(lj_text)
                    if liju:
                        result['liju'] = liju

                # 4. 提取近反义词 (合并专门区块与国语辞典区块的近反义词，保证最全面)
                synonyms = []
                antonyms = []

                # 方式 A：近反义词专属板块
                syn_match = re.search(
                    r'<span class="synonym-label synonym-label--syn">近义词</span>\s*<span class="synonym-tags">(.*?)</span>',
                    html,
                    re.S,
                )
                if syn_match:
                    synonyms.extend(HanyuService._extract_words_from_html(syn_match.group(1)))
                ant_match = re.search(
                    r'<span class="synonym-label synonym-label--ant">反义词</span>\s*<span class="synonym-tags">(.*?)</span>',
                    html,
                    re.S,
                )
                if ant_match:
                    antonyms.extend(HanyuService._extract_words_from_html(ant_match.group(1)))

                # 方式 B：国语辞典中的近反义词板块
                gy_syn_match = re.search(
                    r'xxjs-block-label--syn">近义词</span>\s*<span class="xxjs-also__text">(.*?)</span>', html, re.S
                )
                if gy_syn_match:
                    synonyms.extend(HanyuService._extract_words_from_html(gy_syn_match.group(1)))
                gy_ant_match = re.search(
                    r'xxjs-block-label--ant">反义词</span>\s*<span class="xxjs-also__text">(.*?)</span>', html, re.S
                )
                if gy_ant_match:
                    antonyms.extend(HanyuService._extract_words_from_html(gy_ant_match.group(1)))

                seen_syn = set()
                result['synonyms'] = [
                    s.strip() for s in synonyms if s.strip() and not (s.strip() in seen_syn or seen_syn.add(s.strip()))
                ]
                seen_ant = set()
                result['antonym'] = [
                    a.strip() for a in antonyms if a.strip() and not (a.strip() in seen_ant or seen_ant.add(a.strip()))
                ]

                # 5. 提取褒贬与语法
                baobian = None
                grammar_match = re.search(
                    r'<span class="idiom-entry__label">语法</span>\s*<span class="idiom-entry__text">(.*?)</span>',
                    html,
                    re.S,
                )
                if grammar_match:
                    grammar_text = grammar_match.group(1)
                    if '贬义' in grammar_text or '贬' in grammar_text:
                        baobian = '贬义'
                    elif '褒义' in grammar_text or '褒' in grammar_text:
                        baobian = '褒义'
                    elif '中性' in grammar_text:
                        baobian = '中性'
                result['baobian'] = baobian

                return result
        except Exception as e:
            log.error(f'从汉典网获取词汇 "{name}" 失败: {e}')
            return None

    @staticmethod
    async def _is_data_complete(hanyu: GkHanyu) -> bool:
        """
        检查数据是否完整

        :param hanyu: 汉语词汇对象
        :return: 不添加返回说明
        """
        has_pinyin = bool(hanyu.pinyin and hanyu.pinyin.strip())
        has_definition = False
        if hanyu.definition_info and isinstance(hanyu.definition_info, dict):
            has_definition = bool(hanyu.definition_info.get('definition'))

        # 对于成语类型，如果出处列表为空，我们也认为数据不完整，应当重新拉取补全
        has_chu_chu = True
        if hanyu.type == '成语':
            has_chu_chu = bool(hanyu.chu_chu and len(hanyu.chu_chu) > 0)

        # 对于成语类型，若 synonyms 和 antonym 同时为 None（SQL NULL），说明从未被爬虫抓取过近反义词
        is_syn_never_scraped = hanyu.type == '成语' and hanyu.synonyms is None and hanyu.antonym is None

        return has_pinyin and has_definition and has_chu_chu and not is_syn_never_scraped

    @staticmethod
    async def ensure_related_words_exist(db: AsyncSession, hanyu: GkHanyu) -> None:
        """
        确保关联近反义词存在

        :param db: 数据库会话
        :param hanyu: 汉语词汇对象
        :return: 不添加返回说明
        """
        related_names = set()
        if hanyu.synonyms and isinstance(hanyu.synonyms, list):
            for name in hanyu.synonyms:
                if isinstance(name, str) and name.strip():
                    related_names.add(name.strip())
        if hanyu.antonym and isinstance(hanyu.antonym, list):
            for name in hanyu.antonym:
                if isinstance(name, str) and name.strip():
                    related_names.add(name.strip())

        if not related_names:
            return

        from sqlalchemy import select
        from backend.app.gongkao.model import GkHanyu
        from backend.app.gongkao.schema.hanyu import CreateHanyuParam

        stmt = select(GkHanyu.name).where(GkHanyu.name.in_(list(related_names)))
        res = await db.execute(stmt)
        existing_names = set(res.scalars().all())

        missing_names = related_names - existing_names
        if missing_names:
            for name in missing_names:
                try:
                    create_obj = CreateHanyuParam(name=name, type='成语' if len(name) == 4 else '词语')
                    await hanyu_dao.create(db, create_obj, created_by=1)
                except Exception as e:
                    log.warning(f"自动创建关联词汇 '{name}' 失败: {e}")
            await db.flush()

    @staticmethod
    async def ensure_data_complete(db: AsyncSession, hanyu: GkHanyu) -> GkHanyu:
        """
        确保数据完整，若不完整则静默抓取并补全

        :param db: 数据库会话
        :param hanyu: 汉语词汇对象
        :return: 不添加返回说明
        """
        if not await HanyuService._is_data_complete(hanyu):
            log.info(f'词汇 "{hanyu.name}" 数据不完整，尝试从国学网/汉典网获取并更新...')

            # 1. 优先从汉语国学网获取 (成语核心源)
            parsed_data = await HanyuService._fetch_from_guoxue(hanyu.name)

            # 2. 获取失败或非成语词汇，降级从汉典网获取
            if not parsed_data and hanyu.type != '成语':
                log.info(f'国学网未获取到数据，降级使用汉典网: {hanyu.name}')
                parsed_data = await HanyuService._fetch_from_zdic(hanyu.name)

            if parsed_data:
                from backend.app.gongkao.schema.hanyu import UpdateHanyuParam

                update_obj = UpdateHanyuParam(**parsed_data)
                await hanyu_dao.update(db, hanyu.id, update_obj, updated_by=1)
                await db.flush()
                await db.refresh(hanyu)
                log.info(f'成功补充词汇 "{hanyu.name}" 的详细信息')

                # 自动为不存在的关联词汇在数据库中创建占位记录
                await HanyuService.ensure_related_words_exist(db, hanyu)
            else:
                log.warning(f'国学网及汉典网均无法获取或解析词汇详情: {hanyu.name}')
        return hanyu

    @staticmethod
    async def get(*, db: AsyncSession, pk: int, user_id: int | None = None) -> GkHanyu:
        """
        获取详情

        :param db: 数据库会话
        :param pk: ID
        :param user_id: 用户 ID
        :return: 不添加返回说明
        """
        hanyu = await hanyu_dao.get(db, pk)
        if not hanyu:
            raise errors.NotFoundError(msg='汉语词汇不存在')

        await HanyuService.ensure_data_complete(db, hanyu)

        hanyu.in_notebook = False
        if user_id:
            hanyu.in_notebook = await HanyuService.check_in_notebook(db=db, user_id=user_id, hanyu_id=pk)

        hanyu.question_count = len(hanyu.frequency) if hanyu.frequency else 0

        return hanyu

    @staticmethod
    async def add_to_notebook(*, db: AsyncSession, user_id: int, hanyu_id: int) -> None:
        """
        添加词汇到生词本

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param hanyu_id: 汉语词汇 ID
        :return: 不添加返回说明
        """
        from backend.app.gongkao.model.hanyu_notebook import GkHanyuNotebook
        from sqlalchemy import select

        # 先确认词汇是否存在
        hanyu = await hanyu_dao.get(db, hanyu_id)
        if not hanyu:
            raise errors.NotFoundError(msg='汉语词汇不存在')

        # 检查是否已添加过
        stmt = select(GkHanyuNotebook).where(
            GkHanyuNotebook.user_id == user_id,
            GkHanyuNotebook.hanyu_id == hanyu_id,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return

        notebook_entry = GkHanyuNotebook(user_id=user_id, hanyu_id=hanyu_id)
        db.add(notebook_entry)
        await db.flush()

    @staticmethod
    async def remove_from_notebook(*, db: AsyncSession, user_id: int, hanyu_id: int) -> None:
        """
        从生词本移出词汇

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param hanyu_id: 汉语词汇 ID
        :return: 不添加返回说明
        """
        from backend.app.gongkao.model.hanyu_notebook import GkHanyuNotebook
        from sqlalchemy import delete

        stmt = delete(GkHanyuNotebook).where(
            GkHanyuNotebook.user_id == user_id,
            GkHanyuNotebook.hanyu_id == hanyu_id,
        )
        await db.execute(stmt)
        await db.flush()

    @staticmethod
    async def check_in_notebook(*, db: AsyncSession, user_id: int, hanyu_id: int) -> bool:
        """
        检查词汇是否在生词本中

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param hanyu_id: 汉语词汇 ID
        :return: 不添加返回说明
        """
        from backend.app.gongkao.model.hanyu_notebook import GkHanyuNotebook
        from sqlalchemy import select

        stmt = select(GkHanyuNotebook).where(
            GkHanyuNotebook.user_id == user_id,
            GkHanyuNotebook.hanyu_id == hanyu_id,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        return existing is not None

    @staticmethod
    async def get_by_name(*, db: AsyncSession, name: str, type_: str | None = None) -> GkHanyu:
        """
        根据名称获取详情

        :param db: 数据库会话
        :param name: 词语名称
        :param type_: 类型
        :return:
        """
        hanyu = await hanyu_dao.get_by_name(db, name, type_)
        if not hanyu:
            raise errors.NotFoundError(msg='汉语词汇不存在')
        return hanyu

    @staticmethod
    async def get_list(*, db: AsyncSession, params: HanyuParam) -> dict[str, Any]:
        """
        获取列表（分页）

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        hanyu_select = await hanyu_dao.get_select(params)
        page_data = await paging_data(db, hanyu_select)

        user_id = getattr(params, 'user_id', None)
        if user_id and page_data.get('items'):
            from backend.app.gongkao.model.hanyu_notebook import GkHanyuNotebook
            from sqlalchemy import select

            item_ids = [item['id'] for item in page_data['items']]
            stmt = select(GkHanyuNotebook.hanyu_id).where(
                GkHanyuNotebook.user_id == user_id,
                GkHanyuNotebook.hanyu_id.in_(item_ids),
            )
            result = await db.execute(stmt)
            notebook_ids = set(result.scalars().all())
            for item in page_data['items']:
                item['in_notebook'] = item['id'] in notebook_ids

        if page_data.get('items'):
            for item in page_data['items']:
                freq = item.get('frequency')
                item['question_count'] = len(freq) if isinstance(freq, list) else 0

        return page_data

    @staticmethod
    async def get_types(*, db: AsyncSession) -> list[str]:
        """
        获取所有类型

        :param db: 数据库会话
        :return:
        """
        return await hanyu_dao.get_types(db)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateHanyuParam, created_by: int) -> GkHanyu:
        """
        创建

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        existing = await hanyu_dao.get_by_name(db, obj.name, obj.type)
        if existing:
            raise errors.ForbiddenError(msg=f'词语 "{obj.name}" 在类型 "{obj.type}" 下已存在')
        return await hanyu_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateHanyuParam, updated_by: int) -> int:
        """
        更新

        :param db: 数据库会话
        :param pk: ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        hanyu = await hanyu_dao.get(db, pk)
        if not hanyu:
            raise errors.NotFoundError(msg='汉语词汇不存在')
        if obj.name and obj.type and (obj.name != hanyu.name or obj.type != hanyu.type):
            existing = await hanyu_dao.get_by_name(db, obj.name, obj.type)
            if existing:
                raise errors.ForbiddenError(msg=f'词语 "{obj.name}" 在类型 "{obj.type}" 下已存在')
        return await hanyu_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteHanyuParam) -> int:
        """
        删除

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await hanyu_dao.delete(db, obj.ids)

    @staticmethod
    async def increment_frequency(*, db: AsyncSession, pk: int, question_id: int) -> int:
        """
        追加题目 ID 到相关题目列表

        :param db: 数据库会话
        :param pk: ID
        :param question_id: 题目 ID
        :return:
        """
        hanyu = await hanyu_dao.get(db, pk)
        if not hanyu:
            raise errors.NotFoundError(msg='汉语词汇不存在')
        return await hanyu_dao.increment_frequency(db, pk, question_id)

    @staticmethod
    async def create_practice_session(*, db: AsyncSession, user_id: int, pk: int) -> str:
        """
        根据词汇相关题目创建练习会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param pk: 汉语词汇 ID
        :return: session_key
        """
        from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam
        from backend.app.question_bank_v2.service.practice_service import practice_service

        hanyu = await hanyu_dao.get(db, pk)
        if not hanyu:
            raise errors.NotFoundError(msg='汉语词汇不存在')

        question_ids = hanyu.frequency or []
        if not question_ids:
            raise errors.ForbiddenError(msg=f'词语 "{hanyu.name}" 暂无相关题目')

        obj = CreatePracticeSessionParam(
            source_type='custom',
            question_ids=question_ids,
            mode='practice',
            title=f'词语练习 - {hanyu.name}',
            shuffle=True,
        )
        session = await practice_service.create(db=db, user_id=user_id, obj=obj)
        return session.session_key


hanyu_service: HanyuService = HanyuService()
