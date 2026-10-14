"""AI 自动标注：把脚本的编排逻辑搬到这里，供管理端页面调用。

原脚本：`backend/scripts/qbank/label/qbank_autolabel_knowledge_points.py`（保留作为对照工具）。

## 与脚本的行为差异

1. **同步执行**，不建任务表。所以单次题量必须受限（`max_questions`），
   一次几万题会 HTTP 超时 —— 要跑大批量请分批。
2. **低置信度直接丢弃**，不返回明细。脚本是打到日志里给你导 Markdown 清单。
3. **描述优先读知识点表自己的 `description` 字段**（页面上可维护），
   脚本是硬编码的 `JEV_CRITERIA_HINTS`。
4. **带退避重试**（脚本是裸 httpx）。
"""

import asyncio
import json
import re
import time

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any, Literal

import httpx

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_knowledge import question_knowledge_point_dao
from backend.app.question_bank_v2.schema.knowledge import KnowledgePointAssignmentParam
from backend.app.question_bank_v2.service.ai_label_prompt import (
    CLASSIFY_RULES,
    DB_PRECISION,
    JEV_INSTRUCTION,
    JEV_MAX_OPTIONS,
    JEV_OTHER_DESC,
    JEV_OTHER_KEY,
    SYSTEM_PROMPT,
    build_point_option,
)
from backend.app.question_bank_v2.service.jev_client import (
    JevError,
    call_decision_model,
    parse_answer,
    resolve_decision_model,
)
from backend.common.log import log
from backend.plugin.ai.enums import AIProviderType
from backend.plugin.ai.model.model import AIModel
from backend.plugin.ai.model.provider import AIProvider
from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
from backend.plugin.ai.service.chat_service import ai_chat_service

# 单次请求体上限（官方规格），超了服务端会拒
MAX_STEM_CHARS = 2000
DEFAULT_LIMIT = 200
#: 同步执行的硬上限：再大就 HTTP 超时了，要跑更多请分批
MAX_QUESTIONS_PER_RUN = 2000

Engine = Literal['jev', 'chat']


# ============ 文本处理 ============


def strip_html(content: str | None) -> str:
    """富文本题干 → 纯文本。"""
    if not content:
        return ''
    value = re.sub(r'<br\s*/?>', '\n', str(content), flags=re.IGNORECASE)
    value = re.sub(r'</(p|div|li)>', '\n', value, flags=re.IGNORECASE)
    value = re.sub(r'<[^>]+>', '', value)
    return re.sub(r'\n{2,}', '\n', unescape(value)).strip()


def normalize_options(raw: Any) -> list[tuple[str, str]]:
    """`option_data` 规整成 [(选项号, 文本)]，兼容 JSONB 直出与字符串。"""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    options: list[tuple[str, str]] = []
    for index, item in enumerate(raw):
        if isinstance(item, dict):
            code = item.get('option_code') or item.get('code') or chr(65 + index)
            options.append((str(code), strip_html(item.get('content'))))
        else:
            options.append((chr(65 + index), strip_html(str(item))))
    return options


def to_decimal(value: Any) -> Decimal | None:
    """置信度 → 能存库的 Decimal。"""
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal(DB_PRECISION))
    except (InvalidOperation, TypeError, ValueError):
        return None


def build_stem_block(*, stem: str, options: list[tuple[str, str]], question_type: str | None) -> str:
    """题干 + 选项（两个引擎共用的「题目部分」文本）。"""
    parts = [f'【题目类型】{question_type or "未知"}', f'【题干】\n{stem}']
    if options:
        parts.append('【本题选项】\n' + '\n'.join(f'{c}. {t}' for c, t in options))
    return '\n\n'.join(parts)


# ============ 取候选知识点 ============


async def fetch_candidate_points(
    db: AsyncSession,
    *,
    system_id: int,
    point_ids: list[int] | None = None,
    root_point_id: int | None = None,
    leaves_only: bool = True,
) -> list[dict[str, Any]]:
    """取候选知识点（含完整路径 + description）。

    - `point_ids` 显式指定时只取这几个（页面上勾选的）。
    - `root_point_id` 把候选限制在某个子树内。
    - `leaves_only` 去掉父节点 —— 「数量关系」这种太笼统，模型选它没意义。

    候选越少越准，尤其决策模型是直觉模型，混进一堆无关选项会明显掉点。
    """
    rows = (
        (
            await db.execute(
                text(
                    'SELECT id, name, description, path, depth, parent_id '
                    'FROM qbank_v2_knowledge_point '
                    'WHERE system_id = :sid AND deleted = 0 ORDER BY depth, sort_order, id'
                ),
                {'sid': system_id},
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        msg = f'知识体系 {system_id} 下没有知识点'
        raise ValueError(msg)

    if point_ids:
        wanted = set(point_ids)
        rows = [row for row in rows if row['id'] in wanted]
        if not rows:
            msg = '选中的知识点不属于该知识体系'
            raise ValueError(msg)
    elif root_point_id is not None:
        # path 是祖先 id 的点连接，所以「path 含 root」即该子树内
        rows = [row for row in rows if str(root_point_id) in str(row['path'] or '').split('.')]
        if not rows:
            msg = f'知识点 {root_point_id} 子树下没有任何知识点'
            raise ValueError(msg)

    name_by_id = {row['id']: row['name'] for row in rows}
    parent_ids = {row['parent_id'] for row in rows if row['parent_id'] is not None}
    selected = [row for row in rows if not leaves_only or row['id'] not in parent_ids]
    if not selected:
        msg = '过滤叶子后没有候选知识点（取消勾选「只取叶子」试试）'
        raise ValueError(msg)

    points: list[dict[str, Any]] = []
    for row in selected:
        chain = [
            name_by_id[int(part)]
            for part in str(row['path'] or '').split('.')
            if part.isdigit() and int(part) in name_by_id
        ]
        points.append({
            'id': row['id'],
            'name': row['name'],
            'description': row['description'] or '',
            'depth': row['depth'],
            'path_text': ' > '.join(chain) or row['name'],
        })
    return points


# ============ 取题 ============


def _build_where(
    *,
    system_id: int,
    section_ids: list[int],
    bank_ids: list[int],
    question_ids: list[int],
    include_labeled: bool,
    overwrite_manual: bool,
) -> tuple[str, dict[str, Any]]:
    clauses = ['q.deleted = 0']
    params: dict[str, Any] = {'sid': system_id}

    if section_ids:
        clauses.append('bi.section_id = ANY(:section_ids)')
        params['section_ids'] = section_ids
    if bank_ids:
        clauses.append(
            'bi.bank_revision_id IN '
            '(SELECT r.id FROM qbank_v2_bank_revision r WHERE r.bank_id = ANY(:bank_ids))'
        )
        params['bank_ids'] = bank_ids
    if question_ids:
        clauses.append('q.id = ANY(:question_ids)')
        params['question_ids'] = question_ids

    # 默认只跑还没挂过本体系标注的题
    if not include_labeled:
        clauses.append(
            'NOT EXISTS (SELECT 1 FROM qbank_v2_question_knowledge_point x '
            'JOIN qbank_v2_knowledge_point kp ON kp.id = x.knowledge_point_id '
            'WHERE x.question_id = q.id AND x.deleted = 0 '
            'AND kp.system_id = :sid AND kp.deleted = 0)'
        )
    # 人工标注默认受保护 —— replace() 是物理删除，别让 AI 顺手抹掉人工成果
    if not overwrite_manual:
        clauses.append(
            'NOT EXISTS (SELECT 1 FROM qbank_v2_question_knowledge_point x '
            'JOIN qbank_v2_knowledge_point kp ON kp.id = x.knowledge_point_id '
            'WHERE x.question_id = q.id AND x.deleted = 0 AND kp.system_id = :sid '
            "AND kp.deleted = 0 AND x.source = 'manual')"
        )
    return ' AND '.join(clauses), params


async def fetch_questions(
    db: AsyncSession, *, where: str, params: dict[str, Any], limit: int
) -> list[dict[str, Any]]:
    """取待标注的题目。`limit` 会被 `MAX_QUESTIONS_PER_RUN` 截断。"""
    capped = min(limit, MAX_QUESTIONS_PER_RUN)
    sql = f"""
        SELECT DISTINCT q.id, q.stem, q.question_type, q.option_data
        FROM qbank_v2_question q
        JOIN qbank_v2_bank_item bi ON bi.question_id = q.id AND bi.deleted = 0
        WHERE {where}
        ORDER BY q.id
        LIMIT :limit
    """
    rows = (await db.execute(text(sql), {**params, 'limit': capped})).mappings().all()
    return [dict(row) for row in rows]


async def count_questions(db: AsyncSession, *, where: str, params: dict[str, Any]) -> int:
    """符合条件的总题数（用于告诉用户「这一批有多少题要跑」）。"""
    sql = f"""
        SELECT count(DISTINCT q.id)
        FROM qbank_v2_question q
        JOIN qbank_v2_bank_item bi ON bi.question_id = q.id AND bi.deleted = 0
        WHERE {where}
    """
    return int((await db.execute(text(sql), params)).scalar() or 0)


async def fetch_bank_summary(
    db: AsyncSession, *, where: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """按题库汇总待处理题量 —— 落库前先让人看清这批题到底是什么域的东西。"""
    sql = f"""
        SELECT r.bank_id,
               r.name AS bank_name,
               COALESCE(string_agg(DISTINCT c.name, ' / '), '(无分类)') AS categories,
               count(DISTINCT q.id) AS questions
        FROM qbank_v2_question q
        JOIN qbank_v2_bank_item bi ON bi.question_id = q.id AND bi.deleted = 0
        JOIN qbank_v2_bank_revision r ON r.id = bi.bank_revision_id
        LEFT JOIN qbank_v2_bank_category bc ON bc.bank_id = r.bank_id AND bc.deleted = 0
        LEFT JOIN sys_category c ON c.id = bc.category_id
        WHERE {where}
        GROUP BY r.bank_id, r.name
        ORDER BY questions DESC
    """
    return [dict(row) for row in (await db.execute(text(sql), params)).mappings().all()]


async def fetch_chapter_tree(db: AsyncSession, *, bank_ids: list[int] | None = None) -> list[dict[str, Any]]:
    """章节树（带题量），供页面上勾选范围。

    ⚠️ **不是所有题库都有章节记录** —— 考研政治那 12 个题库在章节表里一行都没有，
    所以页面上要用「按题库勾选」兜住那部分，只靠章节会漏。
    """
    params: dict[str, Any] = {}
    bank_filter = ''
    if bank_ids:
        bank_filter = 'AND r.bank_id = ANY(:bank_ids)'
        params['bank_ids'] = bank_ids

    sql = f"""
        WITH RECURSIVE sec AS (
            SELECT s.id, s.name, s.parent_id, s.bank_revision_id, s.depth, 0 AS qty
            FROM qbank_v2_bank_section s
            JOIN qbank_v2_bank_revision r ON r.id = s.bank_revision_id
            WHERE s.deleted = 0 AND r.deleted = 0 {bank_filter}
            UNION ALL
            SELECT c.id, c.name, c.parent_id, c.bank_revision_id, c.depth, 0 AS qty
            FROM qbank_v2_bank_section c
            JOIN sec ON c.parent_id = sec.id
            WHERE c.deleted = 0
        )
        SELECT s.id, s.name, s.parent_id, s.bank_revision_id,
               r.bank_id,
               (SELECT count(*) FROM qbank_v2_bank_item bi
                 WHERE bi.section_id = s.id AND bi.deleted = 0) AS question_count
        FROM sec s
        JOIN qbank_v2_bank_revision r ON r.id = s.bank_revision_id
        ORDER BY r.bank_id, s.depth, s.id
    """
    rows = [dict(row) for row in (await db.execute(text(sql), params)).mappings().all()]

    # 在内存里拼树：同一 revision 内按 parent_id 挂
    by_parent: dict[tuple[int, int | None], list[dict[str, Any]]] = {}
    for row in rows:
        by_parent.setdefault((row['bank_revision_id'], row['parent_id']), []).append(row)
    for group in by_parent.values():
        for item in group:
            item['children'] = by_parent.get((item['bank_revision_id'], item['id']), [])

    # 只取没有父节点的作为根，按 bank_id 归组
    revision_bank = {row['bank_revision_id']: row['bank_id'] for row in rows}
    result: dict[int, list[dict[str, Any]]] = {}
    for (revision_id, parent_id), group in by_parent.items():
        if parent_id is None:
            result.setdefault(revision_bank.get(revision_id, 0), []).extend(group)
    return [
        {'bank_id': bank_id, 'sections': sections}
        for bank_id, sections in sorted(result.items())
        if sections
    ]


# ============ 引擎调用 ============


async def _resolve_chat_model(
    db: AsyncSession, *, model_id: str | None, provider_id: int | None
) -> tuple[AIModel, AIProvider]:
    """取 chat 模式的模型（排除决策模型通道）。"""
    from sqlalchemy import select

    stmt = (
        select(AIModel, AIProvider)
        .join(AIProvider, AIProvider.id == AIModel.provider_id)
        .where(
            AIModel.status == 1,
            AIProvider.status == 1,
            AIProvider.deleted == 0,
            AIModel.deleted == 0,
            AIProvider.type != AIProviderType.decision_model,
        )
    )
    if model_id:
        stmt = stmt.where(AIModel.model_id == model_id)
    if provider_id:
        stmt = stmt.where(AIProvider.id == provider_id)
    row = (await db.execute(stmt.order_by(AIModel.id.desc()).limit(1))).first()
    if row is None:
        msg = '没有可用的对话模型，请先在「AI 供应商」里配置'
        raise ValueError(msg)
    return row[0], row[1]


def build_jev_criteria(
    points: list[dict[str, Any]], *, with_other: bool = False, use_description: bool = True
) -> dict[str, str]:
    """Jev 的 criteria：key 是选项名（模型看得到），描述写完整路径 + 特征词。

    `with_other` 默认**关掉** —— 实测（2026-09-25，455 题）挂着 other 会让模型把
    15%~25% 的题推给它；关掉后这些题都回到正确类别。低置信度题在 `label_one`
    里按阈值挡掉，不写库。
    """
    if len(points) + (1 if with_other else 0) > JEV_MAX_OPTIONS:
        msg = f'决策模型最多 {JEV_MAX_OPTIONS} 个选项，当前候选 {len(points)} 个；请缩小范围'
        raise ValueError(msg)
    criteria = {str(p['id']): build_point_option(p, use_description=use_description) for p in points}
    if with_other:
        criteria[JEV_OTHER_KEY] = JEV_OTHER_DESC
    return criteria


def build_chat_messages(
    *,
    stem: str,
    options: list[tuple[str, str]],
    question_type: str | None,
    point_lines: list[str],
) -> list[AIChatMessage]:
    body = [
        build_stem_block(stem=stem, options=options, question_type=question_type),
        '【候选知识点】（只能从中选一个）\n' + '\n'.join(point_lines),
        CLASSIFY_RULES,
        '请返回 JSON：{"point_id": <候选里的 id，都不合适则为 null>, '
        '"confidence": <0 到 1 之间的数字>, "reason": "<20 字以内的理由>"}',
    ]
    return [
        AIChatMessage(role='system', content=SYSTEM_PROMPT),
        AIChatMessage(role='user', content='\n\n'.join(body)),
    ]


# ============ 单题处理 ============


async def _label_one(
    *,
    db: AsyncSession,
    http: httpx.AsyncClient,
    question: dict[str, Any],
    point_by_id: dict[int, dict[str, Any]],
    engine: Engine,
    threshold: Decimal,
    system_id: int,
    user_id: int,
    write: bool,
    jev_settings: dict[str, Any] | None,
    point_lines: list[str],
    model: AIModel | None,
    provider: AIProvider | None,
) -> dict[str, Any]:
    """处理一题，返回一条结果记录。**单题异常在这里被吞掉，不中断整批。**"""
    question_id = question['id']
    record: dict[str, Any] = {
        'question_id': question_id,
        'point_id': None,
        'point_name': None,
        'confidence': None,
        'status': 'failed',
        'note': '',
    }

    try:
        stem = strip_html(question['stem'])[:MAX_STEM_CHARS]
        options = normalize_options(question['option_data'])
        state = build_stem_block(
            stem=stem, options=options, question_type=question['question_type']
        )

        if engine == 'jev':
            if jev_settings is None:
                msg = '决策模型未初始化'
                raise JevError(msg)
            payload = await call_decision_model(http=http, state=state, **jev_settings)
            point_id, confidence, note = parse_answer(payload, point_by_id=point_by_id)
        else:
            from backend.app.question_bank_v2.service.evaluation_service import EvaluationService

            if model is None or provider is None:
                msg = '对话模型未初始化'
                raise JevError(msg)
            messages = build_chat_messages(
                stem=stem,
                options=options,
                question_type=question['question_type'],
                point_lines=point_lines,
            )
            response = await ai_chat_service.raw_chat(
                db=db,
                chat=AIChat(
                    provider_id=provider.id,
                    model_id=model.model_id,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=512,
                ),
            )
            data = EvaluationService._extract_json_payload(
                EvaluationService._extract_text_content(response)
            )
            raw_id = data.get('point_id')
            point_id = int(raw_id) if isinstance(raw_id, (int, float)) else None
            confidence = to_decimal(data.get('confidence'))
            note = str(data.get('reason') or '').strip()
    except Exception as exc:
        log.exception('id=%s 标注失败', question_id)
        record['note'] = f'调用失败：{exc}'
        return record

    record['confidence'] = float(confidence) if confidence is not None else None
    record['note'] = note

    if point_id is None:
        record['status'] = 'abstain'
        return record

    point = point_by_id.get(point_id)
    if point is None:
        record['status'] = 'invalid'
        record['note'] = f'模型返回了不存在的知识点 {point_id}'
        return record

    record['point_id'] = point_id
    record['point_name'] = point['path_text'] or point['name']

    # 低于阈值直接丢弃 —— 页面不展示、也不落库，留给人工
    if confidence is None or confidence < threshold:
        record['status'] = 'skipped'
        return record

    if not write:
        record['status'] = 'dry_run'
        return record

    # ⚠️ replace() 是物理删除。务必传 system_id，否则会把这题其它体系的标注一起删光
    await question_knowledge_point_dao.replace(
        db,
        question_id=question_id,
        items=[
            KnowledgePointAssignmentParam(
                knowledge_point_id=point_id,
                source='ai',
                confidence=confidence,
            )
        ],
        user_id=user_id,
        system_id=system_id,
    )
    record['status'] = 'written'
    return record


# ============ 主入口 ============


@dataclass
class _Engine:
    """一次标注要用的引擎资源。jev 走 httpx 直连，chat 走项目自带网关。"""

    http: httpx.AsyncClient
    jev_settings: dict[str, Any] | None
    point_lines: list[str]
    model: AIModel | None = None
    provider: AIProvider | None = None

    async def aclose(self) -> None:
        await self.http.aclose()


async def _init_engine(
    db: AsyncSession,
    *,
    engine: Engine,
    points: list[dict[str, Any]],
    with_other: bool,
    use_description: bool,
    provider_id: int | None,
    model_id: str | None,
) -> _Engine:
    point_lines = [p['path_text'] or p['name'] for p in points]
    http = httpx.AsyncClient(timeout=60.0)

    if engine == 'jev':
        dm, dp = await resolve_decision_model(db, provider_id=provider_id, model_id=model_id)
        return _Engine(
            http=http,
            point_lines=point_lines,
            jev_settings={
                'api_host': dp.api_host,
                'api_key': dp.api_key,
                'model': dm.model_id,
                'criteria': build_jev_criteria(
                    points, with_other=with_other, use_description=use_description
                ),
                # ⚠️ 不带 CLASSIFY_RULES：实测决策模型是 System 1 直觉模型，
                # 塞长规则反而把它推向 other（弃权 25%），去掉后同一批题零弃权且 21142 仍判对
                'instructions': JEV_INSTRUCTION,
            },
        )

    model, provider = await _resolve_chat_model(db, model_id=model_id, provider_id=provider_id)
    return _Engine(http=http, point_lines=point_lines, jev_settings=None, model=model, provider=provider)


async def run_autolabel(
    db: AsyncSession,
    *,
    system_id: int,
    user_id: int,
    engine: Engine = 'jev',
    section_ids: list[int] | None = None,
    bank_ids: list[int] | None = None,
    question_ids: list[int] | None = None,
    point_ids: list[int] | None = None,
    root_point_id: int | None = None,
    leaves_only: bool = True,
    include_labeled: bool = True,
    overwrite_manual: bool = False,
    use_description: bool = True,
    with_other: bool = False,
    threshold: float = 0.6,
    limit: int = DEFAULT_LIMIT,
    write: bool = False,
    provider_id: int | None = None,
    model_id: str | None = None,
    sleep: float = 0.05,
) -> dict[str, Any]:
    """跑一批 AI 标注，同步返回结果。

    `write=False` 是干跑（只统计不落库），**先干跑看一眼再落库**。
    """
    if not any([section_ids, bank_ids, question_ids]):
        msg = '必须至少指定章节、题库或题目之一，避免误伤全库'
        raise ValueError(msg)

    threshold_dec = Decimal(str(threshold)).quantize(Decimal(DB_PRECISION))

    # 1) 候选知识点
    points = await fetch_candidate_points(
        db,
        system_id=system_id,
        point_ids=point_ids,
        root_point_id=root_point_id,
        leaves_only=leaves_only,
    )
    point_by_id = {p['id']: p for p in points}

    # 2) 待标注题目
    where, params = _build_where(
        system_id=system_id,
        section_ids=section_ids or [],
        bank_ids=bank_ids or [],
        question_ids=question_ids or [],
        include_labeled=include_labeled,
        overwrite_manual=overwrite_manual,
    )
    total_matched = await count_questions(db, where=where, params=params)
    summary = await fetch_bank_summary(db, where=where, params=params)
    questions = await fetch_questions(db, where=where, params=params, limit=limit)

    result: dict[str, Any] = {
        'total_matched': total_matched,
        'processed': len(questions),
        'candidates': [p['path_text'] or p['name'] for p in points],
        'bank_summary': summary,
        'write': write,
        'threshold': float(threshold_dec),
        'engine': engine,
        'items': [],
        'statistics': {},
        'elapsed_seconds': 0.0,
    }
    if not questions:
        return result

    # 3) 逐题跑
    started = time.monotonic()
    items: list[dict[str, Any]] = []
    counters: dict[str, int] = dict.fromkeys(
        ('written', 'dry_run', 'skipped', 'abstain', 'invalid', 'failed'), 0
    )
    runner = await _init_engine(
        db,
        engine=engine,
        points=points,
        with_other=with_other,
        use_description=use_description,
        provider_id=provider_id,
        model_id=model_id,
    )
    try:
        for index, question in enumerate(questions, start=1):
            record = await _label_one(
                db=db,
                http=runner.http,
                question=question,
                point_by_id=point_by_id,
                engine=engine,
                threshold=threshold_dec,
                system_id=system_id,
                user_id=user_id,
                write=write,
                jev_settings=runner.jev_settings,
                point_lines=runner.point_lines,
                model=runner.model,
                provider=runner.provider,
            )
            counters[record['status']] += 1
            # 干跑返回全部明细；落库时成功项只回显前 200 条，避免响应体过大
            if not write or index <= 200 or record['status'] != 'written':
                items.append(record)
            # 每 20 题提交一次，别攒到最后
            if write and index % 20 == 0:
                await db.commit()
            if sleep:
                await asyncio.sleep(sleep)
    finally:
        if write:
            await db.commit()
        await runner.aclose()

    result['items'] = items
    result['statistics'] = counters
    result['elapsed_seconds'] = round(time.monotonic() - started, 2)
    log.info(
        'AI 标注完成：引擎 %s，处理 %s 题，写入 %s，跳过 %s，耗时 %s 秒',
        engine,
        result['processed'],
        counters['written'] or counters['dry_run'],
        counters['skipped'],
        result['elapsed_seconds'],
    )
    return result


async def list_decision_models(db: AsyncSession) -> list[dict[str, Any]]:
    """给页面的模型下拉用：所有已启用的决策模型通道。"""
    sql = """
        SELECT p.id AS provider_id, p.name AS provider_name, p.api_host,
               m.model_id, m.id AS model_id_pk
        FROM ai_model m
        JOIN ai_provider p ON p.id = m.provider_id
        WHERE p.type = :ptype AND p.status = 1 AND p.deleted = 0
          AND m.status = 1 AND m.deleted = 0
        ORDER BY p.id, m.id
    """
    rows = (
        (await db.execute(text(sql), {'ptype': int(AIProviderType.decision_model)}))
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
