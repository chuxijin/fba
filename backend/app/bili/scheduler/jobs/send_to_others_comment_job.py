#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""场景C：监控指定作品评论并发送私信任务"""
import asyncio
import json
import random
from datetime import datetime, timedelta

from bilibili_api import Credential, comment, session, user, video
from bilibili_api.comment import CommentResourceType, OrderType
from bilibili_api.session import EventType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.model.account import BiliAccount
from backend.app.bili.model.duplicate_check import BiliDuplicateCheck
from backend.app.bili.model.task_config import BiliTaskConfig
from backend.app.bili.model.task_execution_log import BiliTaskExecutionLog
from backend.app.bili.model.template import BiliTemplate
from backend.app.bili.model.work import BiliWork
from backend.common.log import log
from backend.database.db import async_engine


class PrivateMessageError(Exception):
    """私信发送错误（需要立即停止任务）"""

    pass


async def send_to_others_comment_task(task_config: BiliTaskConfig) -> int:
    """
    场景C：监控指定作品的评论并给评论者发私信

    :param task_config: 任务配置
    :return: 发送成功数量
    """
    async with AsyncSession(async_engine) as db:
        # 创建任务执行记录
        task_start_time = datetime.now()
        execution_log = BiliTaskExecutionLog(
            task_config_id=task_config.id,
            task_name=task_config.task_name,
            task_type=task_config.task_type,
            start_time=task_start_time,
            work_id=task_config.work_id,
            account_id=task_config.account_id,
            execution_status='RUNNING',
        )
        db.add(execution_log)
        await db.commit()
        await db.refresh(execution_log)

        # 统计变量
        comments_fetched = 0
        users_processed = 0
        users_skipped = 0
        send_success = 0
        send_fail = 0

        try:
            # 1. 获取执行账号
            stmt = select(BiliAccount).where(BiliAccount.id == task_config.account_id, BiliAccount.status == 1)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()

            if not account:
                raise Exception(f'账号 ID {task_config.account_id} 不存在或未启用')

            # 2. 获取目标作品
            if not task_config.work_id:
                raise Exception('未配置目标作品 ID')

            stmt = select(BiliWork).where(BiliWork.id == task_config.work_id)
            result = await db.execute(stmt)
            work = result.scalar_one_or_none()

            if not work:
                raise Exception(f'作品 ID {task_config.work_id} 不存在')

            # 3. 获取私信模板
            template_ids = json.loads(task_config.template_ids) if task_config.template_ids else []
            templates = []
            if template_ids:
                stmt = select(BiliTemplate).where(
                    BiliTemplate.id.in_(template_ids), BiliTemplate.status == 1, BiliTemplate.template_type == 'message'
                )
                result = await db.execute(stmt)
                templates = result.scalars().all()

            if not templates:
                raise Exception('没有可用的私信模板')

            # 4. 解析筛选条件
            filter_config = json.loads(task_config.filter_config) if task_config.filter_config else {}
            exclude_levels = filter_config.get('exclude_levels', [])
            exclude_months = filter_config.get('exclude_months', 0)

            log.info(f'🎯 开始监控作品: {work.title} (BVID: {work.work_id})')

            # 5. 构建 Credential
            credential = _parse_credential(account.cookie)

            # 6. 获取评论列表（增量策略 + 时间排序）
            comments_to_process = await _fetch_comments_incremental(work, task_config, credential, db)
            comments_fetched = len(comments_to_process)

            if not comments_to_process:
                log.info('✅ 没有新评论需要处理')
                # 更新执行记录
                execution_log.end_time = datetime.now()
                execution_log.duration_seconds = int((execution_log.end_time - task_start_time).total_seconds())
                execution_log.comments_fetched = comments_fetched
                execution_log.execution_status = 'SUCCESS'
                await db.commit()
                return 0

            log.info(f'📋 获取到 {comments_fetched} 条新评论')

            # 7. 遍历评论并发送私信
            for comment_data in comments_to_process:
                users_processed += 1

                try:
                    commenter_mid = comment_data.get('mid')
                    commenter_name = comment_data.get('member', {}).get('uname', '未知用户')
                    comment_id = comment_data.get('rpid')
                    comment_text = comment_data.get('content', {}).get('message', '')
                    comment_time = comment_data.get('ctime', 0)

                    # 核心去重：检查该用户是否成功操作过（任何操作类型）
                    if await _is_user_in_records(db, commenter_mid):
                        log.debug(f'⏭️  用户 {commenter_name} (MID: {commenter_mid}) 已存在成功记录，跳过')
                        users_skipped += 1
                        continue

                    # 检查用户是否符合筛选条件
                    if not await _check_user_filter(commenter_mid, exclude_levels, exclude_months, credential):
                        log.debug(f'⏭️  用户 {commenter_name} 不符合筛选条件，跳过')
                        users_skipped += 1
                        continue

                    # 随机选择模板
                    template = random.choice(templates)
                    message_content = template.content

                    # 添加随机后缀（防检测）
                    message_content = _add_random_suffix(message_content)

                    # 发送私信（可能抛出 PrivateMessageError）
                    await _send_private_message(commenter_mid, message_content, credential)

                    log.success(f'✅ 成功发送私信给 {commenter_name} (MID: {commenter_mid})')
                    send_success += 1

                    # 记录操作到 duplicate_check
                    await _record_operation(
                        db=db,
                        mid=str(commenter_mid),
                        operation_type='message',
                        work_id=work.id,
                        send_content=message_content,
                        send_result='SUCCESS',
                        execution_log_id=execution_log.id,
                    )

                    # 更新任务状态（记录最后处理的评论）
                    await _update_task_progress(db, task_config.id, comment_id, comment_time)

                    # 随机延迟（防检测）
                    random_delay = random.randint(task_config.check_interval_min, task_config.check_interval_max)
                    log.debug(f'💤 延迟 {random_delay} 秒')
                    await asyncio.sleep(random_delay)

                except PrivateMessageError as e:
                    # 私信错误：立即停止任务
                    log.error(f'🛑 私信发送失败，任务终止: {str(e)}')
                    send_fail += 1

                    await _record_operation(
                        db=db,
                        mid=str(commenter_mid),
                        operation_type='message',
                        work_id=work.id,
                        send_content=message_content if 'message_content' in locals() else '',
                        send_result=f'FATAL: {str(e)}',
                        execution_log_id=execution_log.id,
                    )

                    # 更新执行记录为 FATAL
                    execution_log.end_time = datetime.now()
                    execution_log.duration_seconds = int(
                        (execution_log.end_time - task_start_time).total_seconds()
                    )
                    execution_log.comments_fetched = comments_fetched
                    execution_log.users_processed = users_processed
                    execution_log.users_skipped = users_skipped
                    execution_log.send_success = send_success
                    execution_log.send_fail = send_fail
                    execution_log.execution_status = 'FATAL'
                    execution_log.error_message = str(e)
                    await db.commit()

                    raise  # 抛出异常，停止任务

                except Exception as e:
                    log.error(f'❌ 处理评论失败: {str(e)}')
                    send_fail += 1

                    # 非致命错误，记录后继续
                    await _record_operation(
                        db=db,
                        mid=str(commenter_mid) if 'commenter_mid' in locals() else '',
                        operation_type='message',
                        work_id=work.id,
                        send_content=message_content if 'message_content' in locals() else '',
                        send_result=f'FAIL: {str(e)}',
                        execution_log_id=execution_log.id,
                    )

            # 8. 标记任务为非首次运行
            stmt = select(BiliTaskConfig).where(BiliTaskConfig.id == task_config.id)
            result = await db.execute(stmt)
            task = result.scalar_one_or_none()
            if task and task.is_first_run:
                task.is_first_run = False
                await db.commit()

            # 9. 更新执行记录为 SUCCESS
            execution_log.end_time = datetime.now()
            execution_log.duration_seconds = int((execution_log.end_time - task_start_time).total_seconds())
            execution_log.comments_fetched = comments_fetched
            execution_log.users_processed = users_processed
            execution_log.users_skipped = users_skipped
            execution_log.send_success = send_success
            execution_log.send_fail = send_fail
            execution_log.execution_status = 'SUCCESS'
            await db.commit()

        except PrivateMessageError:
            # FATAL 错误已在上面处理
            raise
        except Exception as e:
            log.error(f'❌ 任务执行异常: {str(e)}')

            # 更新执行记录为 FAIL
            execution_log.end_time = datetime.now()
            execution_log.duration_seconds = int((execution_log.end_time - task_start_time).total_seconds())
            execution_log.comments_fetched = comments_fetched
            execution_log.users_processed = users_processed
            execution_log.users_skipped = users_skipped
            execution_log.send_success = send_success
            execution_log.send_fail = send_fail
            execution_log.execution_status = 'FAIL'
            execution_log.error_message = str(e)
            await db.commit()

            raise

    return send_success


async def _fetch_comments_incremental(
    work: BiliWork, task_config: BiliTaskConfig, credential: Credential, db: AsyncSession
) -> list:
    """
    增量获取评论（首次全量，后续只获取新评论）- 按时间排序

    :param work: 作品对象
    :param task_config: 任务配置
    :param credential: 凭证
    :param db: 数据库会话
    :return: 需要处理的评论列表
    """
    if task_config.is_first_run:
        # 首次运行：全量扫描（多页）
        log.info('🔄 首次运行，开始全量扫描评论（按时间排序）...')
        return await _fetch_all_comments_by_time(work, credential)
    else:
        # 非首次：只获取比上次处理时间更新的评论
        log.info('🔄 增量扫描，只获取新评论')
        return await _fetch_new_comments_since_last(work, task_config, credential)


async def _fetch_all_comments_by_time(work: BiliWork, credential: Credential, max_pages: int = 5) -> list:
    """
    全量获取评论（按时间排序，最多前N页）

    :param work: 作品对象
    :param credential: 凭证
    :param max_pages: 最多获取页数
    :return: 评论列表（按时间倒序）
    """
    all_comments = []

    for page in range(1, max_pages + 1):
        try:
            comments_data = await comment.get_comments(
                oid=work.aid,
                type_=CommentResourceType.VIDEO,
                page_index=page,
                order=OrderType.TIME,  # 关键：按时间排序
                credential=credential,
            )

            replies = comments_data.get('replies', [])
            if not replies:
                break

            all_comments.extend(replies)
            total_count = comments_data.get('page', {}).get('count', 0)
            log.info(f'📄 获取第 {page} 页评论: {len(replies)} 条，总评论数: {total_count}')

            # 防止请求过快
            await asyncio.sleep(random.uniform(1, 2))

        except Exception as e:
            log.error(f'❌ 获取第 {page} 页评论失败: {str(e)}')
            break

    return all_comments


async def _fetch_new_comments_since_last(
    work: BiliWork, task_config: BiliTaskConfig, credential: Credential, max_pages: int = 3
) -> list:
    """
    只获取比上次处理时间更新的评论

    :param work: 作品对象
    :param task_config: 任务配置
    :param credential: 凭证
    :param max_pages: 最多检查页数
    :return: 新评论列表
    """
    new_comments = []
    last_processed_time = task_config.last_processed_time

    if not last_processed_time:
        # 如果没有记录，获取第一页
        return await _fetch_first_page_comments_by_time(work, credential)

    for page in range(1, max_pages + 1):
        try:
            comments_data = await comment.get_comments(
                oid=work.aid,
                type_=CommentResourceType.VIDEO,
                page_index=page,
                order=OrderType.TIME,
                credential=credential,
            )

            replies = comments_data.get('replies', [])
            if not replies:
                break

            # 筛选出比上次处理时间更新的评论
            for reply in replies:
                comment_time = datetime.fromtimestamp(reply.get('ctime', 0))
                if comment_time > last_processed_time:
                    new_comments.append(reply)
                else:
                    # 时间排序，遇到旧评论就停止
                    log.debug(f'🛑 遇到已处理的评论，停止扫描')
                    return new_comments

            await asyncio.sleep(random.uniform(0.5, 1))

        except Exception as e:
            log.error(f'❌ 获取第 {page} 页评论失败: {str(e)}')
            break

    return new_comments


async def _fetch_first_page_comments_by_time(work: BiliWork, credential: Credential) -> list:
    """
    只获取第一页评论（按时间排序）

    :param work: 作品对象
    :param credential: 凭证
    :return: 第一页评论列表
    """
    try:
        comments_data = await comment.get_comments(
            oid=work.aid, type_=CommentResourceType.VIDEO, page_index=1, order=OrderType.TIME, credential=credential
        )

        replies = comments_data.get('replies', [])
        log.info(f'📄 获取第一页评论: {len(replies)} 条')
        return replies

    except Exception as e:
        log.error(f'❌ 获取第一页评论失败: {str(e)}')
        return []


async def _is_user_in_records(db: AsyncSession, mid: int) -> bool:
    """
    检查用户是否在操作记录中存在（任何操作类型，仅成功的记录）

    :param db: 数据库会话
    :param mid: 用户 MID
    :return: 是否存在
    """
    stmt = select(BiliDuplicateCheck).where(
        BiliDuplicateCheck.mid == str(mid),
        BiliDuplicateCheck.is_active == True,
        BiliDuplicateCheck.send_result == 'SUCCESS',  # 只检查成功的记录
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _check_user_filter(mid: int, exclude_levels: list, exclude_months: int, credential: Credential) -> bool:
    """
    检查用户是否符合筛选条件

    :param mid: 用户 MID
    :param exclude_levels: 排除等级列表
    :param exclude_months: 排除注册月份
    :param credential: 凭证
    :return: 是否符合条件
    """
    try:
        u = user.User(uid=mid, credential=credential)
        user_info = await u.get_user_info()

        # 检查等级
        level = user_info.get('level', 0)
        if level in exclude_levels:
            log.debug(f'⏭️  用户等级 Lv.{level} 在排除列表中')
            return False

        # 检查注册时间
        if exclude_months > 0:
            # TODO: bilibili-api 可能没有直接提供注册时间
            # 可以通过 get_relation_info() 获取关注时间作为参考
            pass

        return True

    except Exception as e:
        log.warning(f'⚠️ 获取用户信息失败 (MID: {mid}): {str(e)}')
        return False


async def _send_private_message(mid: int, content: str, credential: Credential):
    """
    发送私信（遇到错误抛出 PrivateMessageError）

    :param mid: 用户 MID
    :param content: 消息内容
    :param credential: 凭证
    """
    try:
        await session.send_msg(
            credential=credential,
            receiver_id=mid,
            msg_type=EventType.TEXT,
            content=content,
        )

    except Exception as e:
        error_msg = str(e).lower()

        # 检查是否是致命错误（需要停止任务）
        if any(
            keyword in error_msg
            for keyword in ['banned', 'forbidden', 'restricted', 'rate limit', '风控', '封禁', '限制']
        ):
            raise PrivateMessageError(f'账号被限制或风控: {str(e)}')

        # 其他错误也抛出，但标记为普通错误
        raise Exception(f'发送失败: {str(e)}')


async def _record_operation(
    db: AsyncSession,
    mid: str,
    operation_type: str,
    work_id: int,
    send_content: str,
    send_result: str,
    execution_log_id: int | None = None,
):
    """
    记录操作到 bili_duplicate_check

    :param db: 数据库会话
    :param mid: 用户 MID
    :param operation_type: 操作类型
    :param work_id: 作品 ID
    :param send_content: 发送内容
    :param send_result: 发送结果
    :param execution_log_id: 任务执行记录 ID
    """
    record = BiliDuplicateCheck(
        mid=mid,
        operation_type=operation_type,
        is_active=True,
        send_content=send_content,
        send_result=send_result,
        work_id=work_id,
        execution_log_id=execution_log_id,
    )
    db.add(record)
    await db.commit()


async def _update_task_progress(db: AsyncSession, task_id: int, comment_id: int, comment_time: int):
    """
    更新任务进度（记录最后处理的评论）

    :param db: 数据库会话
    :param task_id: 任务 ID
    :param comment_id: 评论 ID
    :param comment_time: 评论时间戳
    """
    stmt = select(BiliTaskConfig).where(BiliTaskConfig.id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if task:
        task.last_processed_id = str(comment_id)
        task.last_processed_time = datetime.fromtimestamp(comment_time)
        await db.commit()


def _parse_credential(cookie_str: str) -> Credential:
    """
    解析 Cookie 为 Credential

    :param cookie_str: Cookie 字符串
    :return: Credential 对象
    """
    cookie_dict = {}
    if cookie_str:
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                cookie_dict[key.strip()] = value.strip()

    return Credential(
        sessdata=cookie_dict.get('SESSDATA', ''),
        bili_jct=cookie_dict.get('bili_jct', ''),
        buvid3=cookie_dict.get('buvid3', ''),
    )


def _add_random_suffix(content: str) -> str:
    """
    添加随机后缀（防检测）

    :param content: 原始内容
    :return: 添加后缀的内容
    """
    suffix_types = ['emoji', 'number', 'dots', 'space', 'rare_char']
    suffix_type = random.choice(suffix_types)

    if suffix_type == 'emoji':
        emojis = ['😊', '👍', '✨', '🌟', '💫', '🎉', '🔥', '💪']
        return f'{content}{random.choice(emojis)}'
    elif suffix_type == 'number':
        return f'{content}{random.randint(1, 99)}'
    elif suffix_type == 'dots':
        dots = random.randint(1, 3)
        return f'{content}{"." * dots}'
    elif suffix_type == 'space':
        return f'{content} '
    elif suffix_type == 'rare_char':
        rare_chars = ['⁣', '⁤', '⁢', '\u200b', '\u200c']
        return f'{content}{random.choice(rare_chars)}'
    else:
        return content
