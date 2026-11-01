#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公开免登录试卷排版与极速交付接口
为浏览器插件【公考内容排版】提供对外服务：
1. 游客免登录每日 5 次限流保护 (Redis 原子计数)；
2. UnifiedPaper -> RenderDocumentPayload -> gongkao_adapter 考场规范适配；
3. docx_render_engine 极速本地生成 Word / PDF 交付文件；
4. 临时下载通道与小程序引流码响应。
"""

import base64
import json
import re
import secrets
import time
import uuid

from pathlib import Path
from typing import Any
from urllib.parse import quote

import anyio

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.access.constants import CycleType
from backend.app.access.crud.crud_rule import resource_rule_dao
from backend.app.access.engine.ledger import ledger_service
from backend.common.exception import errors
from backend.common.log import log
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.core.conf import settings
from backend.database.db import CurrentSession, CurrentSessionTransaction, async_db_session
from backend.database.redis import redis_client
from backend.plugin.render_book.schema.public_reformat import (
    PublicReformatRequest,
    PublicReformatResponseData,
    convert_unified_paper_to_document_payload,
)
from backend.plugin.render_book.service.adapters import adapt_gongkao_payload
from backend.plugin.render_book.service.adapters.practice_adapter import adapt_practice_payload
from backend.plugin.render_book.service.docx_engine import docx_render_engine
from backend.plugin.render_book.service.public_auth_service import get_public_user
from backend.plugin.render_book.service.public_delivery_service import (
    DELIVERY_TTL,
    delivery_minicode,
    receive_public_book,
    register_public_book,
)
from backend.plugin.render_book.service.quota_service import render_book_quota_service
from backend.plugin.render_book.utils.template_catalog import TEMPLATES_ROOT
from backend.utils.request_parse import get_request_ip
from backend.utils.timezone import timezone

router = APIRouter()

PUBLIC_DOWNLOAD_PREFIX = 'fba:render_book:public_download:'
_IN_MEMORY_DOWNLOAD_CACHE: dict[str, dict] = {}


def build_clean_paper_and_filenames(
    raw_title: str,
    platform: str,
    is_mistake: bool,
    total_q: int,
    ext: str = 'pdf',
    keypoint_name: str = '',
) -> dict[str, str]:
    """
    智能清洗试卷大标题，并生成规范的四段式文件名：
    【平台标签】知识点/试卷真名 (共N题) - 分册属性.pdf
    """
    plat_map = {'fenbi': '粉笔', 'huatu': '华图', 'shikaobang': '事考帮'}
    plat = plat_map.get((platform or '').lower(), '粉笔')

    clean = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', (raw_title or '').strip())
    clean = re.sub(r'^(粉笔|华图|事考帮)[-_·\s]*', '', clean)
    clean = re.sub(r'[-_·\s]*(粉笔|华图|事考帮)[-_·\s]*', '', clean)
    clean = re.sub(r'(在线做题|错题练习|练习专项版|1比1考场版|做题记录|精选试题|行测模拟考卷)', '', clean).strip()

    if is_mistake:
        kp = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', (keypoint_name or clean).strip())
        kp = re.sub(r'(错题本|错题集|错题|专项集训|突破集|前\d+道)', '', kp).strip()
        if not kp or kp in ['题库', '专项', '练习']:
            kp = '数学运算'

        display_title = f'{plat}{kp}错题'
        base_name = f'【{plat}错题】{kp} (共{total_q}题)'

        return {
            'display_title': display_title,
            'base_name': base_name,
            'merged': f'{base_name}.{ext}',
            'sep_q': f'{base_name} - 试题册.{ext}',
            'sep_s': f'{base_name} - 答案解析册.{ext}',
            'q_only': f'{base_name} - 纯试卷.{ext}',
        }
    subject = clean or '全真模拟试卷'
    display_title = f'{plat}{subject}'
    base_name = f'【{plat}真题】{subject} (共{total_q}题)'
    return {
        'display_title': display_title,
        'base_name': base_name,
        'exam': f'{base_name}.{ext}',
    }


async def _get_trial_policy_limit(db: AsyncSession) -> int:
    """从 resource_rule 动态获取未付费/试看的每日限制"""
    try:
        rules = await resource_rule_dao.resolve_for_resource(
            db,
            resource_type='render_book',
            resource_id=1,
            ts=timezone.now(),
        )
        for r in rules:
            if r.trial_policy and r.trial_policy.get('limit'):
                return int(r.trial_policy['limit'])
    except Exception as e:
        log.warning(f'读取试看规则失败: {e}')
    return 5


@router.get('/quota', summary='查询当前用户/IP今日可用额度')
async def get_public_quota(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[dict]:
    client_ip = get_request_ip(request)
    user = await get_public_user(request=request)
    user_id = user.id if user else None
    user_info = (
        {
            'id': user.id,
            'username': user.username,
            'nickname': user.nickname,
            'avatar': str(user.avatar) if user.avatar else None,
        }
        if user
        else None
    )
    trial_limit = await _get_trial_policy_limit(db)
    now = timezone.now()
    today_str = now.strftime('%Y-%m-%d')

    if user_id is not None:
        # 已登录用户：优先通过 access 模块读取当前周期额度包余额
        try:
            # 1. 检查订阅并解析当天额度上限
            limit = await ledger_service._resolve_subscription_quota_limit(
                db,
                user_id=user_id,
                entitlement_code='render_book.export.quota',
                cycle_type=CycleType.DAILY,
                ts=now,
            )
            balance = await ledger_service.get_balance(
                db,
                user_id=user_id,
                entitlement_code='render_book.export.quota',
                scope_key='render_book',
                cycle_type=CycleType.DAILY,
                cycle_key=today_str,
                ts=now,
            )
            if limit > 0:
                # 若今天尚未扣减过，balance 可能为 0 (惰性未补账)，有效可用额度为 limit
                remaining = balance if balance > 0 else limit
                used = max(0, limit - remaining)
                return response_base.success(
                    data={
                        'client_ip': client_ip,
                        'is_logged_in': True,
                        'user': user_info,
                        'daily_limit': limit,
                        'used_count': used,
                        'remaining_quota': remaining,
                    }
                )
        except Exception as e:
            log.warning(f'[PublicQuota] 读取 access 额度失败: {e}')

        # 若用户无订阅额度包，走 access trial 试看计数器
        trial_key = f'access:trial:{user_id}:render_book:1:render_book.export.quota:{today_str}'
        used_count = 0
        try:
            val = await redis_client.get(trial_key)
            if val is not None:
                used_count = int(val)
        except Exception:
            pass
        remaining = max(0, trial_limit - used_count)
        return response_base.success(
            data={
                'client_ip': client_ip,
                'is_logged_in': True,
                'user': user_info,
                'daily_limit': trial_limit,
                'used_count': used_count,
                'remaining_quota': remaining,
            }
        )
    # 未登录游客：走客户端 IP 维度的试看限流
    guest_key = f'access:trial:guest_ip:{client_ip}:render_book:1:{today_str}'
    used_count = 0
    try:
        val = await redis_client.get(guest_key)
        if val is not None:
            used_count = int(val)
    except Exception:
        pass
    remaining = max(0, trial_limit - used_count)
    return response_base.success(
        data={
            'client_ip': client_ip,
            'is_logged_in': False,
            'daily_limit': trial_limit,
            'used_count': used_count,
            'remaining_quota': remaining,
        }
    )


@router.post('/reformat', summary='公开免登录试卷排版生成')
async def public_reformat_paper(
    request: Request,
    payload: PublicReformatRequest,
    db: CurrentSession,
) -> ResponseSchemaModel[PublicReformatResponseData]:
    user = await get_public_user(request=request)
    user_id = user.id if user else None
    client_ip = get_request_ip(request)
    now = timezone.now()
    today_str = now.strftime('%Y-%m-%d')
    trial_limit = await _get_trial_policy_limit(db)

    job_id = f'pub_{uuid.uuid4().hex[:12]}'
    quota_source_ref = f'public_reformat:{job_id}'
    quota_decision = None
    guest_key = None

    # 2. 校验试题内容
    total_in_req = sum(len(s.questions) for s in payload.paper.sections)
    if total_in_req == 0:
        raise errors.RequestError(code=400, msg='试卷中未包含任何试题，无法进行排版。')

    # 3. 转换为标准 RenderDocumentPayload 并智能识别排版模板
    doc_payload = convert_unified_paper_to_document_payload(payload)

    is_mistake = '错题' in payload.paper.title or (
        payload.paper.metadata and payload.paper.metadata.get('scene') == 'mistake'
    )

    answer_placement = payload.options.answer_placement
    # 若显式声明不包含答案，归一化为 none
    if not payload.options.include_answer and answer_placement == 'merged':
        answer_placement = 'none'

    is_pdf = payload.options.output_format.lower() == 'pdf'
    output_ext = 'pdf' if is_pdf else 'docx'
    media_type = (
        'application/pdf' if is_pdf else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )

    # 智能提纯试卷大标题与规范化文件名（遵循【平台标签】知识点 (共N题) - 分册四段式标准）
    kp_name = (payload.paper.metadata or {}).get('keypointName') or ''
    naming_meta = build_clean_paper_and_filenames(
        raw_title=payload.paper.title,
        platform=payload.paper.source_platform,
        is_mistake=is_mistake,
        total_q=doc_payload.paper.question_count,
        ext=output_ext,
        keypoint_name=kp_name,
    )
    doc_payload.book.title = naming_meta['display_title']

    log.info(
        f'[PublicReformat] 收到排版请求 IP={client_ip}, 试卷={naming_meta["display_title"]} (类型={"练习专项本" if is_mistake else "考场卷"}, 答案模式={answer_placement}), 题量={doc_payload.paper.question_count}, 格式={payload.options.output_format}'
    )

    # 4. 执行渲染输出
    job_output_dir = Path(settings.RENDER_BOOK_STORAGE_ROOT) / 'public_reformat' / job_id

    practice_dir = TEMPLATES_ROOT / 'gongkao_practice' / '1.0.0'
    extra_files: list[dict[str, Any]] = []

    # 完成内容校验后才预扣；游客检查与计数在 Redis 中原子执行。
    if user_id is not None:
        quota_decision = await render_book_quota_service.consume_quota(
            db,
            user_id=user_id,
            source_ref=quota_source_ref,
        )
    else:
        guest_key = f'access:trial:guest_ip:{client_ip}:render_book:1:{today_str}'
        new_cnt = int(
            await redis_client.eval(
                "local n = tonumber(redis.call('GET', KEYS[1]) or '0'); "
                'if n >= tonumber(ARGV[1]) then return -1 end; '
                "n = redis.call('INCR', KEYS[1]); "
                "if n == 1 then redis.call('EXPIRE', KEYS[1], 172800) end; return n",
                1,
                guest_key,
                trial_limit,
            )
        )
        if new_cnt < 0:
            raise errors.RequestError(code=429, msg='您今日免登录试用额度已用完，请登录后再试。')

    try:
        job_output_dir.mkdir(parents=True, exist_ok=True)
        if is_mistake and practice_dir.exists():
            if answer_placement == 'separate':
                # 分立两本：同时渲染试卷分册与答案解析分册
                tpl_q = practice_dir / 'template_questions_only.docx'
                if not tpl_q.exists():
                    tpl_q = practice_dir / 'template.docx'
                tpl_s = practice_dir / 'template_solutions_only.docx'
                if not tpl_s.exists():
                    tpl_s = practice_dir / 'template.docx'

                ctx_q = adapt_practice_payload(doc_payload, template_file=tpl_q)
                ctx_s = adapt_practice_payload(doc_payload, template_file=tpl_s)

                file_base = naming_meta['base_name']
                file_name = naming_meta['sep_q']
                sol_file_name = naming_meta['sep_s']

                res_q = await run_in_threadpool(
                    docx_render_engine.render_all,
                    template_file=tpl_q,
                    context=ctx_q,
                    output_dir=job_output_dir,
                    base_name=f'{file_base} - 试题册',
                    compile_pdf=is_pdf,
                    max_previews=2,
                )
                res_s = await run_in_threadpool(
                    docx_render_engine.render_all,
                    template_file=tpl_s,
                    context=ctx_s,
                    output_dir=job_output_dir,
                    base_name=f'{file_base} - 答案解析册',
                    compile_pdf=is_pdf,
                    max_previews=2,
                )

                primary_target = res_q['pdf'] if is_pdf else res_q['docx']
                sol_target = res_s['pdf'] if is_pdf else res_s['docx']

                # 签发答案解析分册的下载凭证
                tok_sol = f'tok_{uuid.uuid4().hex}'
                meta_sol = {
                    'file_path': str(sol_target),
                    'file_name': sol_file_name,
                    'media_type': media_type,
                    'created_at': time.time(),
                }
                _IN_MEMORY_DOWNLOAD_CACHE[tok_sol] = meta_sol
                try:
                    await redis_client.set(
                        f'{PUBLIC_DOWNLOAD_PREFIX}{tok_sol}', json.dumps(meta_sol, ensure_ascii=False), ex=86400
                    )
                except Exception:
                    pass

                extra_files.append({
                    'file_name': sol_file_name,
                    'download_url': f'/api/v1/render-books/public/download/{tok_sol}',
                })

            elif answer_placement == 'none':
                # 纯试题卷（不含答案）
                tpl_q = practice_dir / 'template_questions_only.docx'
                if not tpl_q.exists():
                    tpl_q = practice_dir / 'template.docx'
                ctx_q = adapt_practice_payload(doc_payload, template_file=tpl_q)
                file_base = naming_meta['base_name']
                file_name = naming_meta['q_only']
                res_q = await run_in_threadpool(
                    docx_render_engine.render_all,
                    template_file=tpl_q,
                    context=ctx_q,
                    output_dir=job_output_dir,
                    base_name=f'{file_base} - 纯试卷',
                    compile_pdf=is_pdf,
                    max_previews=2,
                )
                primary_target = res_q['pdf'] if is_pdf else res_q['docx']

            else:
                # 默认 merged：合订版（题目 + 卷末答案解析）
                tpl_m = practice_dir / 'template.docx'
                ctx_m = adapt_practice_payload(doc_payload, template_file=tpl_m)
                file_base = naming_meta['base_name']
                file_name = naming_meta['merged']
                res_m = await run_in_threadpool(
                    docx_render_engine.render_all,
                    template_file=tpl_m,
                    context=ctx_m,
                    output_dir=job_output_dir,
                    base_name=file_base,
                    compile_pdf=is_pdf,
                    max_previews=2,
                )
                primary_target = res_m['pdf'] if is_pdf else res_m['docx']
        else:
            # 考场卷
            tpl_k = TEMPLATES_ROOT / 'gongkao_xingce' / '1.0.0' / 'template.docx'
            if not tpl_k.exists():
                raise errors.ServerError(msg='公考行测标准排版模板丢失，请联系管理员。')
            ctx_k = adapt_gongkao_payload(doc_payload)
            file_base = naming_meta['base_name']
            file_name = naming_meta['exam']
            res_k = await run_in_threadpool(
                docx_render_engine.render_all,
                template_file=tpl_k,
                context=ctx_k,
                output_dir=job_output_dir,
                base_name=file_base,
                compile_pdf=is_pdf,
                max_previews=2,
            )
            primary_target = res_k['pdf'] if is_pdf else res_k['docx']

        # 文件登记与数据库额度使用同一事务；失败一并回滚。
        book_files = [(Path(primary_target), file_name)]
        if extra_files:
            book_files.append((Path(sol_target), sol_file_name))
        delivery_token = await register_public_book(
            db=db,
            job_id=job_id,
            user_id=user_id,
            title=doc_payload.book.title,
            question_count=doc_payload.paper.question_count,
            is_mistake=is_mistake,
            answer_placement=answer_placement,
            files=book_files,
        )
        await db.commit()
    except Exception as exc:
        log.exception('[PublicReformat] 渲染或题本登记失败')
        await db.rollback()
        if user_id is not None and quota_decision is not None:
            try:
                await render_book_quota_service.refund_quota(
                    db,
                    user_id=user_id,
                    decision=quota_decision,
                    source_ref=quota_source_ref,
                )
                await db.commit()
            except Exception as refund_err:
                log.warning(f'[PublicReformat] 权益回滚失败: {refund_err}')
        elif guest_key:
            try:
                await redis_client.eval(
                    "local n = tonumber(redis.call('GET', KEYS[1]) or '0'); "
                    "if n > 0 then return redis.call('DECR', KEYS[1]) end; return 0",
                    1,
                    guest_key,
                )
            except Exception:
                log.exception('[PublicReformat] 游客额度退回失败')
        raise errors.ServerError(msg='排版生成或题本保存失败，请稍后重试') from exc

    # 5. 生成主文件临时安全下载凭证并缓存
    download_token = f'tok_{uuid.uuid4().hex}'
    download_meta = {
        'file_path': str(primary_target),
        'file_name': file_name,
        'media_type': media_type,
        'created_at': time.time(),
    }
    _IN_MEMORY_DOWNLOAD_CACHE[download_token] = download_meta
    try:
        await redis_client.set(
            f'{PUBLIC_DOWNLOAD_PREFIX}{download_token}',
            json.dumps(download_meta, ensure_ascii=False),
            ex=86400,
        )
    except Exception as e:
        log.warning(f'[PublicReformat] 缓存下载元数据至 Redis 失败，使用内存缓存: {e}')

    # 6. 动态查询 access 模块获取当前剩余额度
    remaining_quota = 0
    if user_id is not None:
        try:
            balance = await ledger_service.get_balance(
                db,
                user_id=user_id,
                entitlement_code='render_book.export.quota',
                scope_key='render_book',
                cycle_type=CycleType.DAILY,
                cycle_key=today_str,
                ts=now,
            )
            remaining_quota = max(0, balance)
        except Exception:
            remaining_quota = 0
    else:
        remaining_quota = max(0, trial_limit - new_cnt)

    download_url = f'/api/v1/render-books/public/download/{download_token}'
    qr_code_url = f'/api/v1/render-books/public/minicode/{delivery_token}'

    return response_base.success(
        data=PublicReformatResponseData(
            job_id=job_id,
            file_name=file_name,
            download_url=download_url,
            output_format=output_ext,
            remaining_quota=remaining_quota,
            qr_code_url=qr_code_url,
            total_questions=doc_payload.paper.question_count,
            extra_files=extra_files or None,
        )
    )


@router.get('/download/{download_token}', summary='下载已排版就绪的试卷文件')
async def download_public_reformat_file(download_token: str):
    """
    通过临时安全 Token 下载排版好的 Word 或 PDF 文件
    """
    download_meta = None
    try:
        raw_val = await redis_client.get(f'{PUBLIC_DOWNLOAD_PREFIX}{download_token}')
        if raw_val:
            download_meta = json.loads(raw_val)
    except Exception as e:
        log.warning(f'[PublicDownload] 读取下载 Token 失败: {e}')

    if not download_meta:
        download_meta = _IN_MEMORY_DOWNLOAD_CACHE.get(download_token)

    if not download_meta or time.time() - float(download_meta.get('created_at', 0)) >= DELIVERY_TTL:
        _IN_MEMORY_DOWNLOAD_CACHE.pop(download_token, None)
        raise errors.NotFoundError(msg='下载链接已失效或不存在，请重新在插件中排版。')

    file_path = Path(download_meta['file_path'])
    file_name = download_meta['file_name']
    media_type = download_meta.get('media_type', 'application/octet-stream')

    async_path = anyio.Path(file_path)
    if not await async_path.exists() or not await async_path.is_file():
        # 自愈机制：若目标 PDF 缺失，但同名 Word 题本存在，尝试即时补转
        docx_fallback = file_path.with_suffix('.docx')
        if await anyio.Path(docx_fallback).exists():
            try:
                log.info(f'[PublicDownload] 侦测到 PDF 缺失但 Word 题本完好，正在即时自愈补转: {docx_fallback}')
                await run_in_threadpool(docx_render_engine.convert_to_pdf, docx_fallback, file_path)
            except Exception as e:
                log.warning(f'[PublicDownload] 即时自愈补转 PDF 失败: {e}')

        if not await async_path.exists() or not await async_path.is_file():
            # 优雅降级：若补转失败但 Word 文件存在，降级交付 Word 题本
            if await anyio.Path(docx_fallback).exists():
                file_path = docx_fallback
                file_name = file_name.replace('.pdf', '.docx')
                media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                log.info(f'[PublicDownload] 自动降级交付已排版好的 Word 题本: {file_path}')
            else:
                raise errors.NotFoundError(msg='排版产物文件已过期清理，请重新排版。')

    encoded_filename = quote(file_name)
    headers = {
        'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}",
        'Access-Control-Expose-Headers': 'Content-Disposition',
    }

    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers=headers,
    )


@router.get('/minicode/{token}', summary='获取本次题本的真实小程序码')
async def get_public_minicode(token: str, db: CurrentSession) -> Response:
    data_url = await delivery_minicode(db=db, token=token)
    header, encoded = data_url.split(',', 1)
    return Response(
        content=base64.b64decode(encoded),
        media_type=header[5:].split(';')[0],
        headers={'Cache-Control': 'no-store'},
    )


@router.post('/receive/{token}', summary='登录后保存扫码题本', dependencies=[DependsJwtAuth])
async def receive_render_book(token: str, request: Request, db: CurrentSessionTransaction) -> ResponseSchemaModel[dict]:
    result = await receive_public_book(db=db, token=token, user_id=request.user.id)
    return response_base.success(data=result)


EXPORT_PREFIX = 'fba:render_book:export:'
_IN_MEMORY_EXPORT_CACHE: dict[str, tuple[float, dict]] = {}


async def _run_public_export(ticket: str, request: Request, payload: PublicReformatRequest) -> None:
    try:
        async with async_db_session() as db:
            result = await public_reformat_paper(request=request, payload=payload, db=db)
        state = {'status': 'succeeded', 'result': result.data.model_dump(mode='json')}
    except Exception as exc:
        log.exception('[PublicExport] 插件排版任务失败')
        message = '排版失败，请检查试题内容或稍后重试'
        if isinstance(exc, errors.BaseExceptionError) and exc.code < 500:
            message = exc.msg or message
        state = {'status': 'failed', 'message': message}
    # 最终状态短暂写入失败时保留本进程结果，不把已扣额度的成功任务报成排版失败。
    _IN_MEMORY_EXPORT_CACHE[ticket] = (time.time(), state)
    for attempt in range(3):
        try:
            await redis_client.set(f'{EXPORT_PREFIX}{ticket}', json.dumps(state, ensure_ascii=False), ex=DELIVERY_TTL)
            _IN_MEMORY_EXPORT_CACHE.pop(ticket, None)
            break
        except Exception:
            log.exception('[PublicExport] 保存排版最终状态失败')
            if attempt < 2:
                await anyio.sleep(1)


@router.post('/exports', summary='提交插件排版，短请求避免浏览器后台长连接中断')
async def start_public_export(
    request: Request, payload: PublicReformatRequest, tasks: BackgroundTasks
) -> ResponseSchemaModel[dict]:
    await get_public_user(request=request)
    ticket = secrets.token_urlsafe(24)
    await redis_client.set(
        f'{EXPORT_PREFIX}{ticket}', json.dumps({'status': 'running', 'started_at': time.time()}), ex=DELIVERY_TTL
    )
    tasks.add_task(_run_public_export, ticket, request, payload)
    return response_base.success(data={'ticket': ticket})


@router.get('/exports/{ticket}', summary='查询本次插件排版状态')
async def get_public_export(ticket: str) -> ResponseSchemaModel[dict]:
    if not re.fullmatch(r'[A-Za-z0-9_-]{32}', ticket):
        raise errors.NotFoundError(msg='排版任务不存在')
    cached = _IN_MEMORY_EXPORT_CACHE.get(ticket)
    if cached:
        if time.time() - cached[0] < DELIVERY_TTL:
            return response_base.success(data=cached[1])
        _IN_MEMORY_EXPORT_CACHE.pop(ticket, None)
    raw = await redis_client.get(f'{EXPORT_PREFIX}{ticket}')
    if not raw:
        raise errors.NotFoundError(msg='排版任务已过期，请重新导出')
    state = json.loads(raw)
    if state['status'] == 'running' and time.time() - state['started_at'] > 1200:
        state = {'status': 'failed', 'message': '排版处理时间较长或服务已重启；请先检查我的题本，避免重复导出。'}
    return response_base.success(data=state)
