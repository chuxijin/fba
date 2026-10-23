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

import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import anyio
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CycleType
from backend.app.access.crud.crud_rule import resource_rule_dao
from backend.app.access.engine.ledger import ledger_service
from backend.common.exception import errors
from backend.common.log import log
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.core.path_conf import STATIC_DIR
from backend.database.db import CurrentSession
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

    clean = re.sub(r'[\/:*?"<>|]', '_', (raw_title or '').strip())
    clean = re.sub(r'^(粉笔|华图|事考帮)[-_·\s]*', '', clean)
    clean = re.sub(r'[-_·\s]*(粉笔|华图|事考帮)[-_·\s]*', '', clean)
    clean = re.sub(r'(在线做题|错题练习|练习专项版|1比1考场版|做题记录|精选试题|行测模拟考卷)', '', clean).strip()

    if is_mistake:
        kp = keypoint_name or clean
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
    else:
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
    user_info = {
        'id': user.id,
        'username': user.username,
        'nickname': user.nickname,
        'avatar': str(user.avatar) if user.avatar else None,
    } if user else None
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
    else:
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

    # 1. 配额检查与预扣减（已登录用户全权由 access 模块决策与扣减；未登录游客按 IP 试看策略）
    if user_id is not None:
        quota_decision = await render_book_quota_service.consume_quota(
            db,
            user_id=user_id,
            source_ref=quota_source_ref,
        )
    else:
        guest_key = f'access:trial:guest_ip:{client_ip}:render_book:1:{today_str}'
        used_val = await redis_client.get(guest_key)
        used_count = int(used_val) if used_val else 0
        if used_count >= trial_limit:
            raise errors.RequestError(
                code=429,
                msg='您今日免登录试用额度已用完。可在浏览器右上角点击插件图标扫码登录，即可解锁更多排版特权与小程序同步！',
            )
        new_cnt = await redis_client.incr(guest_key)
        if new_cnt == 1:
            await redis_client.expire(guest_key, 86400 * 2)

    # 2. 校验试题内容
    total_in_req = sum(len(s.questions) for s in payload.paper.sections)
    if total_in_req == 0:
        raise errors.RequestError(code=400, msg='试卷中未包含任何试题，无法进行排版。')

    # 3. 转换为标准 RenderDocumentPayload 并智能识别排版模板
    doc_payload = convert_unified_paper_to_document_payload(payload)

    is_mistake = (
        '错题' in payload.paper.title
        or (payload.paper.metadata and payload.paper.metadata.get('scene') == 'mistake')
    )

    answer_placement = payload.options.answer_placement
    # 若显式声明不包含答案，归一化为 none
    if not payload.options.include_answer and answer_placement == 'merged':
        answer_placement = 'none'

    is_pdf = payload.options.output_format.lower() == 'pdf'
    output_ext = 'pdf' if is_pdf else 'docx'
    media_type = 'application/pdf' if is_pdf else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

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
    job_id = f'pub_{uuid.uuid4().hex[:12]}'
    job_output_dir = STATIC_DIR / 'upload' / 'public_reformat' / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

    practice_dir = TEMPLATES_ROOT / 'gongkao_practice' / '1.0.0'
    extra_files: list[dict[str, Any]] = []

    try:
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

                res_q = docx_render_engine.render_all(
                    template_file=tpl_q,
                    context=ctx_q,
                    output_dir=job_output_dir,
                    base_name=f'{file_base} - 试题册',
                    compile_pdf=is_pdf,
                    max_previews=2,
                )
                res_s = docx_render_engine.render_all(
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
                    await redis_client.set(f'{PUBLIC_DOWNLOAD_PREFIX}{tok_sol}', json.dumps(meta_sol, ensure_ascii=False), ex=86400)
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
                res_q = docx_render_engine.render_all(
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
                res_m = docx_render_engine.render_all(
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
            res_k = docx_render_engine.render_all(
                template_file=tpl_k,
                context=ctx_k,
                output_dir=job_output_dir,
                base_name=file_base,
                compile_pdf=is_pdf,
                max_previews=2,
            )
            primary_target = res_k['pdf'] if is_pdf else res_k['docx']

    except Exception as exc:
        log.exception(f'[PublicReformat] 试卷渲染生成异常: {exc}')
        if user_id is not None and quota_decision is not None:
            try:
                await render_book_quota_service.refund_quota(
                    db,
                    user_id=user_id,
                    decision=quota_decision,
                    source_ref=quota_source_ref,
                )
            except Exception as refund_err:
                log.warning(f'[PublicReformat] 权益回滚失败: {refund_err}')
        raise errors.ServerError(msg=f'排版生成引擎异常: {exc!s}')

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
    qr_code_url = f'/api/v1/render-books/public/minicode/{job_id}'

    return response_base.success(
        data=PublicReformatResponseData(
            job_id=job_id,
            file_name=file_name,
            download_url=download_url,
            output_format=output_ext,
            remaining_quota=remaining_quota,
            qr_code_url=qr_code_url,
            total_questions=doc_payload.paper.question_count,
            extra_files=extra_files if extra_files else None,
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

    if not download_meta:
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
                docx_render_engine.convert_to_pdf(docx_fallback, file_path)
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


@router.get('/minicode/{job_id}', summary='获取任务专属小程序码或引流卡片')
async def get_public_minicode(job_id: str):
    """
    返回微信小程序快速打印直通二维码 (支持 SVG 矢量生成或预置小程序码图)
    """
    # 返回考场双面打印引流与快速交付 SVG
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" viewBox="0 0 240 240">
      <rect width="240" height="240" fill="#f8fafc" rx="16"/>
      <rect x="20" y="20" width="200" height="200" fill="#ffffff" rx="12" stroke="#e2e8f0" stroke-width="2"/>
      <circle cx="120" cy="100" r="45" fill="#eff6ff"/>
      <path d="M120 75v50M95 100h50" stroke="#2563eb" stroke-width="6" stroke-linecap="round"/>
      <text x="120" y="165" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="bold" fill="#0f172a">我的题本 · 快速打印</text>
      <text x="120" y="188" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#64748b">微信扫码 5分钱/张 考场双面印</text>
    </svg>"""

    return Response(content=svg_content, media_type='image/svg+xml')
