#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import asyncio
import json
import re

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_question import option_content_dao, question_option_dao
from backend.app.question_bank.model import (
    PracticeSession,
    QuestionAnalysis,
    QuestionBank,
    QuestionChapter,
    QuestionPlacement,
    SessionQuestion,
)
from backend.app.question_bank.model.question import Question
from backend.app.question_bank.schema.question import UpsertQuestionOptionItem
from backend.database.db import async_db_session

SOURCE = 'yunyxzx'
API_URL = 'https://www.yunyxzx.com/huikao_pc/queryoPaperSubjectList'
DEFAULT_CREATED_BY = 1
DEFAULT_CAT_ID = 0
TYPE_LABELS = {
    1: '单选题',
    2: '多选题',
    3: '判断题',
    4: '填空题',
    5: '简答题',
    6: '材料题',
}
TYPE_MAP = {
    1: 'single',
    2: 'multiple',
    3: 'judgement',
    4: 'fill',
    5: 'shortAnswer',
    6: 'shortAnswer',
}


@dataclass(slots=True)
class RemoteQuestion:
    """远端题目"""

    source_id: str
    group_key: str
    sub_type: int
    issue: str
    options: list[tuple[str, str]]
    answer: str
    analysis: str
    sort_order: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ImportStats:
    """导入统计"""

    fetched: int = 0
    questions_created: int = 0
    questions_updated: int = 0
    placements_upserted: int = 0
    analyses_upserted: int = 0
    skipped: int = 0


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='从云易学接口导入单套试卷题目')
    parser.add_argument('--paper-id', required=True, help='远端 paperId')
    parser.add_argument('--paper-name', default='', help='试卷名称，不传则使用 paperId 生成')
    parser.add_argument('--mode', type=int, default=2, help='远端接口 mode')
    parser.add_argument('--cat-id', type=int, default=DEFAULT_CAT_ID, help='题库分类 ID')
    parser.add_argument('--created-by', type=int, default=DEFAULT_CREATED_BY, help='创建者用户 ID')
    parser.add_argument('--bank-code', default='', help='题库编码，不传则自动生成')
    parser.add_argument('--target-bank-id', type=int, default=0, help='导入到已有题库 ID，传入后不会新建题库')
    parser.add_argument('--clear-existing', action='store_true', help='导入前清空目标题库现有题目和章节')
    parser.add_argument('--delete-history', action='store_true', help='清空时删除引用旧挂载的历史练习，再物理删除旧题')
    parser.add_argument('--cookie', default='', help='远端接口 Cookie')
    parser.add_argument('--authorization', default='', help='远端接口 Authorization 请求头')
    parser.add_argument('--input-json', default='', help='本地接口响应 JSON 文件，传入后不再请求网络')
    parser.add_argument('--dry-run', action='store_true', help='只预览不提交数据库')
    parser.add_argument('--timeout', type=float, default=30.0, help='接口超时时间')
    return parser.parse_args()


def normalize_text(value: Any) -> str:
    """
    规范化文本

    :param value: 原始文本
    :return:
    """
    return str(value or '').replace('\r\n', '\n').strip()


def normalize_html(value: Any) -> str:
    """
    规范化富文本

    :param value: 原始文本
    :return:
    """
    return normalize_text(value).replace('\n', '<br/>')


def build_bank_code(paper_id: str, bank_code: str) -> str:
    """
    构建题库编码

    :param paper_id: 远端试卷 ID
    :param bank_code: 指定编码
    :return:
    """
    if bank_code:
        return bank_code[:32]
    return f'YUNYXZX_{paper_id}'[:32]


def parse_year(paper_name: str) -> int | None:
    """
    从试卷名称提取年份

    :param paper_name: 试卷名称
    :return:
    """
    matched = re.search(r'(?<!\d)(20\d{2}|19\d{2})(?!\d)', paper_name)
    if not matched:
        return None
    return int(matched.group(1))


def parse_options(raw: Any) -> list[tuple[str, str]]:
    """
    解析选项

    :param raw: 远端选项字符串
    :return:
    """
    text = normalize_text(raw)
    if not text:
        return []

    options: list[tuple[str, str]] = []
    for index, part in enumerate(text.split('|'), start=1):
        item = part.strip()
        matched = re.match(r'^([A-Z])[\.\．、\s]*(.*)$', item, flags=re.IGNORECASE)
        if matched:
            code = matched.group(1).upper()
            content = matched.group(2).strip()
        else:
            code = chr(ord('A') + index - 1)
            content = item
        if content:
            options.append((code, content))
    return options


def infer_question_type(sub_type: int, answer: str, options: list[tuple[str, str]]) -> str:
    """
    推断题型

    :param sub_type: 远端题型
    :param answer: 答案
    :param options: 选项
    :return:
    """
    normalized_answer = normalize_answer(answer)
    if sub_type == 1 and len(normalized_answer) > 1:
        return 'multiple'
    if sub_type == 3:
        return 'judgement'
    if len(options) == 2:
        option_text = ''.join(content for _, content in options)
        if '正确' in option_text and '错误' in option_text:
            return 'judgement'
    return TYPE_MAP.get(sub_type, 'single')


def normalize_answer(answer: Any) -> str:
    """
    规范化答案

    :param answer: 原始答案
    :return:
    """
    return re.sub(r'[^A-Za-z0-9\u4e00-\u9fff]', '', normalize_text(answer)).upper()


def chapter_name(sub_type: int, group_key: str) -> str:
    """
    获取章节名称

    :param sub_type: 远端题型
    :param group_key: 远端分组
    :return:
    """
    return TYPE_LABELS.get(sub_type) or f'第 {group_key} 部分'


def iter_remote_questions(payload: Any) -> list[RemoteQuestion]:
    """
    展开远端题目

    :param payload: 接口 data
    :return:
    """
    questions: list[RemoteQuestion] = []
    if not isinstance(payload, list):
        return questions

    def collect(item: dict[str, Any], group_key: str) -> None:
        children = item.get('childre') or item.get('children') or []
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    collect(child, group_key)

        issue = normalize_html(item.get('issue') or item.get('stem'))
        source_id = normalize_text(item.get('id'))
        if not source_id or not issue:
            return

        sub_type = int(item.get('subType') or 1)
        questions.append(
            RemoteQuestion(
                source_id=source_id,
                group_key=group_key,
                sub_type=sub_type,
                issue=issue,
                options=parse_options(item.get('sOption')),
                answer=normalize_answer(item.get('answer')),
                analysis=normalize_html(item.get('analysis')),
                sort_order=int(item.get('order') or len(questions) + 1),
                raw=item,
            )
        )

    for group in payload:
        if not isinstance(group, dict):
            continue
        for group_key, items in group.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    collect(item, str(group_key))
    return questions


def parse_response_payload(payload: dict[str, Any]) -> list[RemoteQuestion]:
    """
    解析接口响应

    :param payload: 接口响应
    :return:
    """
    if payload.get('code') != 0:
        raise RuntimeError(f'远端接口返回失败: {payload.get("msg") or payload}')
    return iter_remote_questions(payload.get('data'))


def load_questions_from_json(path: str) -> list[RemoteQuestion]:
    """
    从本地 JSON 加载题目

    :param path: JSON 文件路径
    :return:
    """
    with open(path, encoding='utf-8') as file:
        payload = json.load(file)
    if isinstance(payload, list):
        return iter_remote_questions(payload)
    if isinstance(payload, dict):
        return parse_response_payload(payload)
    raise RuntimeError('JSON 文件格式不支持')


async def fetch_paper_questions(
    client: httpx.AsyncClient,
    paper_id: str,
    mode: int,
    cookie: str = '',
    authorization: str = '',
) -> list[RemoteQuestion]:
    """
    拉取远端试卷题目

    :param client: HTTP 客户端
    :param paper_id: 试卷 ID
    :param mode: 接口模式
    :param cookie: 登录 Cookie
    :param authorization: 登录令牌
    :return:
    """
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.yunyxzx.com/',
    }
    if cookie:
        headers['Cookie'] = cookie
    if authorization:
        headers['authorization'] = authorization
    response = await client.get(API_URL, params={'paperId': paper_id, 'mode': mode}, headers=headers)
    response.raise_for_status()
    return parse_response_payload(response.json())


async def ensure_bank(
    db: AsyncSession,
    *,
    paper_id: str,
    paper_name: str,
    bank_code: str,
    cat_id: int,
    created_by: int,
) -> QuestionBank:
    """
    获取或创建试卷题库

    :param db: 数据库会话
    :param paper_id: 试卷 ID
    :param paper_name: 试卷名称
    :param bank_code: 题库编码
    :param cat_id: 分类 ID
    :param created_by: 创建者
    :return:
    """
    code = build_bank_code(paper_id, bank_code)
    name = paper_name or f'云易学试卷 {paper_id}'
    bank = await db.scalar(select(QuestionBank).where(QuestionBank.code == code))
    if bank is None:
        fallback_source_bank_id = await db.scalar(select(QuestionBank.id).order_by(QuestionBank.id).limit(1))
        if fallback_source_bank_id is None:
            raise RuntimeError('当前库中没有可用题库，无法满足 chapter_source_bank_id 外键')
        bank = QuestionBank(
            cat_id=cat_id,
            name=name,
            code=code,
            desc=f'{SOURCE} paperId={paper_id}',
            year=parse_year(name),
            cover_url=None,
            difficulty=None,
            bank_type=2,
            scene_mask=1,
            parent_id=None,
            sort_order=0,
            chapter_source_bank_id=fallback_source_bank_id,
            status=1,
            q_count_cache=0,
            total_score_cache=Decimal('0'),
            buy_count=0,
            access_entitlement_code=None,
            created_by=created_by,
        )
        db.add(bank)
        await db.flush()
        bank.chapter_source_bank_id = bank.id
        await db.flush()
        return bank

    bank.name = name
    bank.desc = f'{SOURCE} paperId={paper_id}'
    bank.year = parse_year(name)
    bank.bank_type = 2
    bank.chapter_source_bank_id = bank.id
    bank.status = 1
    bank.updated_by = created_by
    await db.flush()
    return bank


async def get_target_bank(
    db: AsyncSession,
    *,
    bank_id: int,
    created_by: int,
) -> QuestionBank:
    """
    获取已有目标题库

    :param db: 数据库会话
    :param bank_id: 题库 ID
    :param created_by: 操作人
    :return:
    """
    bank = await db.scalar(select(QuestionBank).where(QuestionBank.id == bank_id))
    if bank is None:
        raise RuntimeError(f'目标题库不存在: {bank_id}')
    bank.status = 1
    bank.updated_by = created_by
    return bank


async def clear_bank_content(db: AsyncSession, *, bank: QuestionBank, delete_history: bool = False) -> dict[str, int]:
    """
    清空题库已有题目与章节

    :param db: 数据库会话
    :param bank: 题库
    :param delete_history: 是否删除历史练习
    :return:
    """
    placement_rows = (
        await db.execute(
            select(QuestionPlacement.id, QuestionPlacement.question_id)
            .where(QuestionPlacement.bank_id == bank.id)
        )
    ).all()
    placement_ids = [int(row.id) for row in placement_rows]
    question_ids = {int(row.question_id) for row in placement_rows}

    deleted_sessions = 0
    deleted_placements = 0
    deleted_questions = 0
    inactive_placements = 0

    if delete_history and placement_ids:
        session_ids = list(
            (
                await db.execute(
                    select(SessionQuestion.session_id)
                    .where(SessionQuestion.placement_id.in_(placement_ids))
                    .distinct()
                )
            ).scalars().all()
        )
        if session_ids:
            result = await db.execute(sa_delete(PracticeSession).where(PracticeSession.id.in_(session_ids)))
            deleted_sessions = int(result.rowcount or 0)
            await db.flush()

        result = await db.execute(sa_delete(QuestionPlacement).where(QuestionPlacement.id.in_(placement_ids)))
        deleted_placements = int(result.rowcount or 0)
        await db.flush()

        if question_ids:
            referenced_question_ids = set(
                (
                    await db.execute(
                        select(QuestionPlacement.question_id)
                        .where(QuestionPlacement.question_id.in_(question_ids))
                        .distinct()
                    )
                ).scalars().all()
            )
            orphan_question_ids = sorted(question_ids - referenced_question_ids)
            if orphan_question_ids:
                result = await db.execute(sa_delete(Question).where(Question.id.in_(orphan_question_ids)))
                deleted_questions = int(result.rowcount or 0)
    else:
        result = await db.execute(
            sa_update(QuestionPlacement)
            .where(QuestionPlacement.bank_id == bank.id)
            .values(
                chapter_id=None,
                is_active=False,
                review_status=20,
            )
        )
        inactive_placements = int(result.rowcount or 0)

    await db.execute(sa_delete(QuestionChapter).where(QuestionChapter.bank_id == bank.id))
    bank.q_count_cache = 0
    bank.total_score_cache = Decimal('0')
    await db.flush()
    return {
        'deleted_sessions': deleted_sessions,
        'deleted_placements': deleted_placements,
        'deleted_questions': deleted_questions,
        'inactive_placements': inactive_placements,
    }


async def ensure_chapter(
    db: AsyncSession,
    *,
    bank_id: int,
    group_key: str,
    name: str,
    sort_order: int,
) -> QuestionChapter:
    """
    获取或创建题型章节

    :param db: 数据库会话
    :param bank_id: 题库 ID
    :param group_key: 分组编码
    :param name: 章节名称
    :param sort_order: 排序
    :return:
    """
    code = f'{SOURCE}_{group_key}'[:64]
    chapter = await db.scalar(
        select(QuestionChapter).where(
            QuestionChapter.bank_id == bank_id,
            QuestionChapter.code == code,
        )
    )
    if chapter is None:
        chapter = QuestionChapter(
            bank_id=bank_id,
            name=name,
            parent_id=None,
            code=code,
            level=1,
            sort_order=sort_order,
            q_count_cache=0,
            status=1,
        )
        db.add(chapter)
        await db.flush()
        return chapter

    chapter.name = name
    chapter.sort_order = sort_order
    chapter.status = 1
    await db.flush()
    return chapter


async def get_question_by_source_id(db: AsyncSession, source_id: str) -> Question | None:
    """
    根据远端题目 ID 查找本地题目

    :param db: 数据库会话
    :param source_id: 远端题目 ID
    :return:
    """
    stmt = (
        select(Question)
        .join(QuestionAnalysis, QuestionAnalysis.question_id == Question.id)
        .where(
            QuestionAnalysis.answer_data.cast(PGJSONB).contains(
                {'source': SOURCE, 'source_question_id': source_id}
            )
        )
        .limit(1)
    )
    return await db.scalar(stmt)


async def replace_analysis(
    db: AsyncSession,
    *,
    question_id: int,
    remote: RemoteQuestion,
    created_by: int,
) -> None:
    """
    替换官方解析

    :param db: 数据库会话
    :param question_id: 题目 ID
    :param remote: 远端题目
    :param created_by: 创建者
    :return:
    """
    await db.execute(
        sa_delete(QuestionAnalysis).where(
            QuestionAnalysis.question_id == question_id,
            QuestionAnalysis.type == 'official',
            QuestionAnalysis.version_no == 1,
        )
    )
    db.add(
        QuestionAnalysis(
            question_id=question_id,
            answer_data={
                'source': SOURCE,
                'source_question_id': remote.source_id,
                'correct': remote.answer,
                'answer': remote.answer,
                'paper_id': remote.raw.get('paperId'),
                'structure_id': remote.raw.get('structureId'),
                'remote_order': remote.raw.get('order'),
            },
            content=remote.analysis or '暂无解析',
            type='official',
            version_no=1,
            is_default=True,
            view_count=0,
            helpful_count=0,
            unhelpful_count=0,
            status=10,
            created_by=created_by,
        )
    )


async def upsert_placement(
    db: AsyncSession,
    *,
    question_id: int,
    bank_id: int,
    chapter_id: int,
    sort_order: int,
    created_by: int,
) -> None:
    """
    写入题目挂载

    :param db: 数据库会话
    :param question_id: 题目 ID
    :param bank_id: 题库 ID
    :param chapter_id: 章节 ID
    :param sort_order: 排序
    :param created_by: 创建者
    :return:
    """
    placement = await db.scalar(
        select(QuestionPlacement).where(
            QuestionPlacement.bank_id == bank_id,
            QuestionPlacement.question_id == question_id,
        )
    )
    if placement is None:
        db.add(
            QuestionPlacement(
                question_id=question_id,
                bank_id=bank_id,
                chapter_id=chapter_id,
                sort_order=sort_order,
                is_active=True,
                score=Decimal('1'),
                review_status=10,
                scene_mask=None,
                created_by=created_by,
            )
        )
        return

    placement.chapter_id = chapter_id
    placement.sort_order = sort_order
    placement.is_active = True
    placement.score = Decimal('1')
    placement.review_status = 10
    placement.updated_by = created_by


async def recalc_cache(db: AsyncSession, bank: QuestionBank) -> None:
    """
    重算题库和章节缓存

    :param db: 数据库会话
    :param bank: 题库
    :return:
    """
    q_count = await db.scalar(
        select(func.count(QuestionPlacement.id)).where(
            QuestionPlacement.bank_id == bank.id,
            QuestionPlacement.is_active.is_(True),
        )
    )
    total_score = await db.scalar(
        select(func.coalesce(func.sum(QuestionPlacement.score), 0)).where(
            QuestionPlacement.bank_id == bank.id,
            QuestionPlacement.is_active.is_(True),
        )
    )
    bank.q_count_cache = int(q_count or 0)
    bank.total_score_cache = Decimal(str(total_score or 0))

    chapters = (await db.execute(select(QuestionChapter).where(QuestionChapter.bank_id == bank.id))).scalars().all()
    for chapter in chapters:
        chapter_count = await db.scalar(
            select(func.count(QuestionPlacement.id)).where(
                QuestionPlacement.bank_id == bank.id,
                QuestionPlacement.chapter_id == chapter.id,
                QuestionPlacement.is_active.is_(True),
            )
        )
        chapter.q_count_cache = int(chapter_count or 0)


async def import_questions(
    db: AsyncSession,
    *,
    bank: QuestionBank,
    questions: list[RemoteQuestion],
    created_by: int,
) -> ImportStats:
    """
    导入题目

    :param db: 数据库会话
    :param bank: 题库
    :param questions: 远端题目
    :param created_by: 创建者
    :return:
    """
    stats = ImportStats(fetched=len(questions))
    chapter_cache: dict[str, QuestionChapter] = {}
    for index, remote in enumerate(questions, start=1):
        if not remote.issue:
            stats.skipped += 1
            continue

        chapter_key = str(remote.sub_type or remote.group_key)
        chapter = chapter_cache.get(chapter_key)
        if chapter is None:
            chapter = await ensure_chapter(
                db=db,
                bank_id=bank.id,
                group_key=chapter_key,
                name=chapter_name(remote.sub_type, remote.group_key),
                sort_order=len(chapter_cache) + 1,
            )
            chapter_cache[chapter_key] = chapter

        question_type = infer_question_type(remote.sub_type, remote.answer, remote.options)
        question = await get_question_by_source_id(db, remote.source_id)
        if question is None:
            question = Question(
                type=question_type,
                stem=remote.issue,
                difficulty='medium',
                default_score=Decimal('1'),
                knowledge_point=[chapter.name],
                content_status=10,
                created_by=created_by,
            )
            db.add(question)
            await db.flush()
            stats.questions_created += 1
        else:
            question.type = question_type
            question.stem = remote.issue
            question.default_score = Decimal('1')
            question.knowledge_point = [chapter.name]
            question.content_status = 10
            question.updated_by = created_by
            stats.questions_updated += 1

        option_items = [
            UpsertQuestionOptionItem(option_code=code, content=content, sort_order=option_index)
            for option_index, (code, content) in enumerate(remote.options, start=1)
        ]
        await question_option_dao.replace_by_items(
            db,
            question_id=question.id,
            items=option_items,
            option_content_crud=option_content_dao,
        )
        await replace_analysis(db, question_id=question.id, remote=remote, created_by=created_by)
        await upsert_placement(
            db=db,
            question_id=question.id,
            bank_id=bank.id,
            chapter_id=chapter.id,
            sort_order=index,
            created_by=created_by,
        )
        stats.analyses_upserted += 1
        stats.placements_upserted += 1

    await db.flush()
    await recalc_cache(db, bank)
    return stats


async def main() -> None:
    """运行导入脚本"""
    args = parse_args()
    if args.input_json:
        remote_questions = load_questions_from_json(args.input_json)
    else:
        async with httpx.AsyncClient(timeout=httpx.Timeout(args.timeout)) as client:
            remote_questions = await fetch_paper_questions(
                client,
                args.paper_id,
                args.mode,
                args.cookie,
                args.authorization,
            )

    async with async_db_session.begin() as db:
        if args.target_bank_id > 0:
            bank = await get_target_bank(db, bank_id=args.target_bank_id, created_by=args.created_by)
        else:
            bank = await ensure_bank(
                db,
                paper_id=args.paper_id,
                paper_name=args.paper_name,
                bank_code=args.bank_code,
                cat_id=args.cat_id,
                created_by=args.created_by,
            )
        clear_stats = {
            'deleted_sessions': 0,
            'deleted_placements': 0,
            'deleted_questions': 0,
            'inactive_placements': 0,
        }
        if args.clear_existing:
            clear_stats = await clear_bank_content(db, bank=bank, delete_history=args.delete_history)
        stats = await import_questions(
            db,
            bank=bank,
            questions=remote_questions,
            created_by=args.created_by,
        )
        bank_id = bank.id
        bank_code = bank.code
        if args.dry_run:
            await db.rollback()
            action = 'rollback'
        else:
            action = 'commit'

        print(
            f'[YUNYXZX] {action} bank_id={bank_id} bank_code={bank_code} '
            f'fetched={stats.fetched} created={stats.questions_created} '
            f'updated={stats.questions_updated} placements={stats.placements_upserted} '
            f'analyses={stats.analyses_upserted} skipped={stats.skipped} '
            f'deleted_sessions={clear_stats["deleted_sessions"]} '
            f'deleted_old_placements={clear_stats["deleted_placements"]} '
            f'deleted_old_questions={clear_stats["deleted_questions"]} '
            f'inactivated_old_placements={clear_stats["inactive_placements"]}'
        )


if __name__ == '__main__':
    asyncio.run(main())
