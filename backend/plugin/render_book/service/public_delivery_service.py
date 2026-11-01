"""把插件已生成的文件登记为题本；扫码领取不重新渲染、不扣额度。"""

import hashlib
import re
import secrets
import time

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.plugin.render_book.crud import render_book_job_dao, render_book_job_file_dao
from backend.plugin.render_book.model import RenderBookJob
from backend.utils.wechat_code import create_miniapp_code

DELIVERY_TTL = 86400
DELIVERY_PAGE = 'pkg/mine/render-books/index'


def delivery_digest(token: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]{24}', token):
        raise errors.NotFoundError(msg='题本领取码无效或已过期，请回到插件重新导出')
    return hashlib.sha256(token.encode()).hexdigest()


async def register_public_book(
    *,
    db: AsyncSession,
    job_id: str,
    user_id: int | None,
    title: str,
    question_count: int,
    is_mistake: bool,
    answer_placement: str,
    files: list[tuple[Path, str]],
) -> str:
    token = secrets.token_urlsafe(18)
    separated = len(files) > 1
    job = await render_book_job_dao.create_job(
        db,
        data={
            'job_id': job_id,
            'user_id': user_id,
            'title': title[:200],
            'template_key': 'gongkao_practice' if is_mistake else 'gongkao_xingce',
            'status': 'succeeded',
            'mode': 'final',
            'book_kind': 'wrong' if is_mistake else 'exam',
            'solution_mode': 'separate' if separated else 'none' if answer_placement == 'none' else 'appendix',
            'question_count': question_count,
            'metadata_json': {
                'user_id': user_id,
                'cat_id': 1400,
                'kp_cat_id': 1401,
                'source_type': 'extension',
                'delivery_hash': delivery_digest(token),
                'delivery_expires_at': int(time.time()) + DELIVERY_TTL,
            },
        },
    )
    for index, (path, filename) in enumerate(files):
        if not path.is_file():
            raise errors.ServerError(msg='排版产物未生成，请重试')
        variant = (
            'solutions_only'
            if index
            else 'questions_only'
            if separated or answer_placement == 'none'
            else 'combined_appendix'
        )
        kind = (
            'solution_pdf' if index else 'question_pdf' if separated or answer_placement == 'none' else 'combined_pdf'
        )
        await render_book_job_file_dao.create_file(
            db,
            data={
                'render_job_id': job.id,
                'file_kind': kind,
                'render_variant': variant,
                'filename': filename,
                'local_path': str(path.resolve()),
                'size_bytes': path.stat().st_size,
                'content_type': 'application/pdf'
                if path.suffix.lower() == '.pdf'
                else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            },
        )
    return token


async def get_delivery_job(*, db: AsyncSession, token: str, for_update: bool = False) -> RenderBookJob:
    stmt = select(RenderBookJob).where(
        RenderBookJob.del_flag.is_(False),
        RenderBookJob.metadata_json['delivery_hash'].as_string() == delivery_digest(token),
    )
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    job = (await db.execute(stmt)).scalars().first()
    if job is None or int((job.metadata_json or {}).get('delivery_expires_at', 0)) <= time.time():
        raise errors.NotFoundError(msg='题本领取码已过期或题本已删除，请回到插件重新导出')
    return job


async def delivery_minicode(*, db: AsyncSession, token: str) -> str:
    job = await get_delivery_job(db=db, token=token)
    ttl = int(job.metadata_json['delivery_expires_at'] - time.time())
    return await create_miniapp_code(page=DELIVERY_PAGE, scene=f'rb_{token}', ttl=ttl)


async def receive_public_book(*, db: AsyncSession, token: str, user_id: int) -> dict:
    # 行锁覆盖检查与归属写入；同一用户重复扫码幂等，其他用户不能领取已归属题本。
    job = await get_delivery_job(db=db, token=token, for_update=True)
    if job.user_id is not None and job.user_id != user_id:
        raise errors.AuthorizationError(msg='这份题本已属于其他账号，请使用导出时的账号登录')
    job.user_id = user_id
    job.metadata_json = {**(job.metadata_json or {}), 'user_id': user_id}
    await db.flush()
    return {'job_id': job.job_id, 'title': job.title, 'cat_id': 1400}
