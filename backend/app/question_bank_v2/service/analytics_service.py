from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_bank import bank_revision_dao
from backend.app.question_bank_v2.crud.crud_catalog import collection_bank_dao, collection_dao
from backend.app.question_bank_v2.crud.crud_composition import bank_section_dao
from backend.app.question_bank_v2.crud.crud_statistics import (
    learning_analytics_dao,
    user_daily_statistics_dao,
    user_practice_statistics_dao,
)
from backend.app.question_bank_v2.model.bank import QbBankRevision
from backend.app.question_bank_v2.model.practice import QbPracticeSession
from backend.app.question_bank_v2.schema.analytics import (
    BankProgressSummary,
    BankSectionProgress,
    GetBankProgressBrief,
    GetBankProgressDetail,
    GetBankWrongSectionCounts,
    GetCollectionProgressSummary,
    GetPracticeRankList,
    GetUserPracticeReport,
    PracticeRankItem,
    QuestionTypeProgress,
    RankType,
    ResumableScope,
    UserDailyPracticeDetail,
    UserMonthlyPracticeDetail,
    WrongSectionCount,
    GetKnowledgePointTrends,
    KnowledgePointTrendModule,
    KnowledgePointTrendPoint,
)
from backend.app.question_bank_v2.service.access_service import bank_access_service
from backend.common.exception import errors
from backend.utils.timezone import timezone


class AnalyticsService:
    """题库 V2 学习进度、报告与排行榜服务类"""

    @staticmethod
    def _rate(numerator: int, denominator: int) -> Decimal:
        """计算四位小数的安全比例"""
        if denominator <= 0:
            return Decimal('0.0000')
        return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal('0.0001'))

    @staticmethod
    def _type_progress(type_row: dict[str, int]) -> QuestionTypeProgress:
        """将单行题型聚合转换为题型进度"""
        graded = type_row['correct_count'] + type_row['wrong_count']
        return QuestionTypeProgress(
            question_count=type_row['total_count'],
            answered_count=type_row['answered_count'],
            correct_count=type_row['correct_count'],
            wrong_count=type_row['wrong_count'],
            progress_rate=AnalyticsService._rate(type_row['answered_count'], type_row['total_count']),
            accuracy_rate=AnalyticsService._rate(type_row['correct_count'], graded),
        )

    @staticmethod
    def _build_type_data(
        *,
        type_rows: list[dict[str, Any]],
        section_id: int | None = None,
    ) -> tuple[dict[str, int], dict[str, QuestionTypeProgress]]:
        """从题型聚合行中构建 question_type_counts 和 question_type_progress"""
        qtype_counts: dict[str, int] = {}
        qtype_progress: dict[str, QuestionTypeProgress] = {}
        for tr in type_rows:
            if tr.get('section_id') != section_id:
                continue
            qt = tr['question_type']
            qtype_counts[qt] = int(tr['total_count'])
            qtype_progress[qt] = AnalyticsService._type_progress(tr)
        return qtype_counts, qtype_progress

    @staticmethod
    def _merge_type_progress(
        base_counts: dict[str, int],
        base_progress: dict[str, QuestionTypeProgress],
        child_counts: dict[str, int],
        child_progress: dict[str, QuestionTypeProgress],
    ) -> tuple[dict[str, int], dict[str, QuestionTypeProgress]]:
        """将子节点的题型进度合并到父节点"""
        merged_counts = {**base_counts}
        merged_progress = {k: v.model_copy() for k, v in base_progress.items()}
        for qt, cnt in child_counts.items():
            merged_counts[qt] = merged_counts.get(qt, 0) + cnt
        for qt, cp in child_progress.items():
            if qt in merged_progress:
                mp = merged_progress[qt]
                mp.question_count += cp.question_count
                mp.answered_count += cp.answered_count
                mp.correct_count += cp.correct_count
                mp.wrong_count += cp.wrong_count
                graded = mp.correct_count + mp.wrong_count
                mp.progress_rate = AnalyticsService._rate(mp.answered_count, mp.question_count)
                mp.accuracy_rate = AnalyticsService._rate(mp.correct_count, graded)
            else:
                merged_progress[qt] = cp.model_copy()
        return merged_counts, merged_progress

    @staticmethod
    def _progress_summary(
        data: dict[str, int],
        qtype_counts: dict[str, int] | None = None,
        qtype_progress: dict[str, QuestionTypeProgress] | None = None,
    ) -> BankProgressSummary:
        """将计数转换为进度汇总"""
        graded_count = data['correct_count'] + data['wrong_count']
        return BankProgressSummary(
            total_count=data['total_count'],
            answered_count=data['answered_count'],
            correct_count=data['correct_count'],
            wrong_count=data['wrong_count'],
            progress_rate=AnalyticsService._rate(data['answered_count'], data['total_count']),
            accuracy_rate=AnalyticsService._rate(data['correct_count'], graded_count),
            question_type_counts=qtype_counts or {},
            question_type_progress=qtype_progress or {},
        )

    @staticmethod
    def _build_progress_tree(
        *,
        sections: list[Any],
        rows: list[dict[str, Any]],
        type_rows: list[dict[str, Any]],
    ) -> list[BankSectionProgress]:
        """构建篇章进度树并向父节点汇总后代题目及题型进度"""
        row_map = {row['section_id']: row for row in rows}
        type_map: dict[int | None, list[dict[str, Any]]] = {}
        for tr in type_rows:
            sid = tr.get('section_id')
            type_map.setdefault(sid, []).append(tr)

        nodes: dict[int, dict[str, Any]] = {}
        children: dict[int | None, list[int]] = {}
        for section in sections:
            row = row_map.get(section.id, {})
            qt_counts, qt_progress = AnalyticsService._build_type_data(type_rows=type_rows, section_id=section.id)
            nodes[section.id] = {
                'id': section.id,
                'name': section.name,
                'parent_id': section.parent_id,
                'depth': section.depth,
                'sort_order': section.sort_order,
                'total_count': int(row.get('total_count') or 0),
                'answered_count': int(row.get('answered_count') or 0),
                'correct_count': int(row.get('correct_count') or 0),
                'wrong_count': int(row.get('wrong_count') or 0),
                'question_type_counts': qt_counts,
                'question_type_progress': qt_progress,
            }
            children.setdefault(section.parent_id, []).append(section.id)

        def build(section_id: int) -> BankSectionProgress:
            node = nodes[section_id]
            child_nodes = [build(child_id) for child_id in children.get(section_id, [])]
            for child in child_nodes:
                node['total_count'] += child.total_count
                node['answered_count'] += child.answered_count
                node['correct_count'] += child.correct_count
                node['wrong_count'] += child.wrong_count
                merged_counts, merged_progress = AnalyticsService._merge_type_progress(
                    node['question_type_counts'],
                    node['question_type_progress'],
                    child.question_type_counts,
                    child.question_type_progress,
                )
                node['question_type_counts'] = merged_counts
                node['question_type_progress'] = merged_progress
            return BankSectionProgress(
                **node,
                progress_rate=AnalyticsService._rate(node['answered_count'], node['total_count']),
                accuracy_rate=AnalyticsService._rate(
                    node['correct_count'],
                    node['correct_count'] + node['wrong_count'],
                ),
                children=child_nodes,
            )

        root_ids = [section.id for section in sections if section.parent_id not in nodes]
        return [build(section_id) for section_id in root_ids]

    @staticmethod
    async def _get_bank_context(*, db: AsyncSession, user_id: int, bank_id: int) -> tuple[Any, Any]:
        """校验题库刷题权限并获取当前发布版本"""
        bank, _ = await bank_access_service.ensure_bank_access(db=db, user_id=user_id, bank_id=bank_id)
        revision = await bank_revision_dao.get(db, bank.current_revision_id, bank_id=bank.id)
        if revision is None or revision.status != 'published':
            raise errors.NotFoundError(msg='题库当前发布版本不存在')
        return bank, revision

    @staticmethod
    async def _get_resumable_scopes(
        *,
        db: AsyncSession,
        user_id: int,
        bank_id: int,
    ) -> list[ResumableScope]:
        """聚合当前用户在题库维度下可续接的进行中会话维度

        仅收录“按题库/篇章/题型”来源的会话（排除知识点与收藏维度），
        每个维度聚合存在进行中会话的练习模式，供前端判断入口显示“继续”还是“开始”。
        """
        rows = (
            await db.execute(
                select(
                    QbPracticeSession.mode,
                    QbPracticeSession.source_snapshot,
                    QbPracticeSession.delivery_config,
                )
                .join(
                    QbBankRevision,
                    and_(
                        QbBankRevision.id == QbPracticeSession.bank_revision_id,
                        QbBankRevision.deleted == 0,
                    ),
                )
                .where(
                    QbPracticeSession.user_id == user_id,
                    QbPracticeSession.deleted == 0,
                    QbPracticeSession.status.in_(('created', 'in_progress')),
                    QbBankRevision.bank_id == bank_id,
                )
            )
        ).mappings().all()
        scopes: dict[tuple[Any, Any], set[str]] = defaultdict(set)
        for row in rows:
            source = dict(row['source_snapshot'] or {})
            delivery = dict(row['delivery_config'] or {})
            if source.get('knowledge_point_ids') or source.get('favorite_folder_id') is not None:
                continue
            question_types = list(delivery.get('question_types') or [])
            question_type = question_types[0] if len(question_types) == 1 else None
            scopes[source.get('section_id'), question_type].add(str(row['mode']))
        return [
            ResumableScope(section_id=section_id, question_type=question_type, modes=sorted(modes))
            for (section_id, question_type), modes in scopes.items()
        ]

    @staticmethod
    async def get_bank_progress(
        *,
        db: AsyncSession,
        user_id: int,
        bank_id: int,
    ) -> GetBankProgressDetail:
        """获取题库当前版本总进度和篇章进度树"""
        _, revision = await AnalyticsService._get_bank_context(db=db, user_id=user_id, bank_id=bank_id)
        sections, rows, type_rows = await learning_analytics_dao.get_bank_progress_rows(
            db,
            user_id=user_id,
            bank_revision_id=revision.id,
        )
        unsectioned_row = next((row for row in rows if row['section_id'] is None), {})
        unsectioned_data = {
            key: int(unsectioned_row.get(key) or 0)
            for key in ('total_count', 'answered_count', 'correct_count', 'wrong_count')
        }
        totals = {
            key: sum(int(row.get(key) or 0) for row in rows)
            for key in ('total_count', 'answered_count', 'correct_count', 'wrong_count')
        }
        # 未归入篇章的题型进度
        unsectioned_qt_counts, unsectioned_qt_progress = AnalyticsService._build_type_data(
            type_rows=type_rows, section_id=None,
        )
        # 全库级别题型进度 = 所有 type_rows 汇总
        all_qt_counts: dict[str, int] = {}
        all_qt_progress: dict[str, QuestionTypeProgress] = {}
        for tr in type_rows:
            qt = tr['question_type']
            all_qt_counts[qt] = all_qt_counts.get(qt, 0) + int(tr['total_count'])
            if qt in all_qt_progress:
                cp = all_qt_progress[qt]
                cp.question_count += int(tr['total_count'])
                cp.answered_count += int(tr['answered_count'])
                cp.correct_count += int(tr['correct_count'])
                cp.wrong_count += int(tr['wrong_count'])
            else:
                all_qt_progress[qt] = AnalyticsService._type_progress(tr)
        for qtp in all_qt_progress.values():
            graded = qtp.correct_count + qtp.wrong_count
            qtp.progress_rate = AnalyticsService._rate(qtp.answered_count, qtp.question_count)
            qtp.accuracy_rate = AnalyticsService._rate(qtp.correct_count, graded)

        return GetBankProgressDetail(
            bank_id=bank_id,
            bank_revision_id=revision.id,
            bank_name=revision.name,
            **AnalyticsService._progress_summary(totals, all_qt_counts, all_qt_progress).model_dump(),
            unsectioned=AnalyticsService._progress_summary(
                unsectioned_data,
                unsectioned_qt_counts,
                unsectioned_qt_progress,
            ),
            sections=AnalyticsService._build_progress_tree(sections=sections, rows=rows, type_rows=type_rows),
            resumable_scopes=await AnalyticsService._get_resumable_scopes(
                db=db,
                user_id=user_id,
                bank_id=bank_id,
            ),
        )

    @staticmethod
    async def get_collection_progress_summary(
        *,
        db: AsyncSession,
        user_id: int,
        collection_id: int,
        include_descendants: bool = True,
    ) -> GetCollectionProgressSummary:
        """
        获取合集作用域内各题库的进度摘要

        只返回调用者自己的作答计数，不做逐库准入判定：题量本身已通过公开目录暴露，
        逐库跑权限引擎会让列表页退化成 N 次查询。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param collection_id: 合集 ID
        :param include_descendants: 是否包含子合集
        :return:
        """
        collection = await collection_dao.get(db, collection_id)
        if collection is None or collection.status != 'active':
            raise errors.NotFoundError(msg='题库合集不存在')

        collection_ids = (
            await collection_dao.get_subtree_ids(db, collection_id)
            if include_descendants
            else [collection_id]
        )
        mounts = await collection_bank_dao.get_effective_bank_revisions(db, collection_ids)

        # 同一题库可挂多处：follow_latest 优先，其次 revision_no 最大
        best: dict[int, dict[str, Any]] = {}
        for mount in mounts:
            bank_id = int(mount['bank_id'])
            current = best.get(bank_id)
            if current is None:
                best[bank_id] = mount
                continue
            better = (
                (bool(mount['follow_latest']), int(mount['revision_no']))
                > (bool(current['follow_latest']), int(current['revision_no']))
            )
            if better:
                best[bank_id] = mount

        revision_pairs = [(bank_id, int(m['bank_revision_id'])) for bank_id, m in best.items()]
        rows = await learning_analytics_dao.get_bank_progress_summary_rows(
            db, user_id=user_id, revision_pairs=revision_pairs,
        )
        row_map = {int(row['bank_revision_id']): row for row in rows}

        banks: list[GetBankProgressBrief] = []
        totals = {'total_count': 0, 'answered_count': 0, 'correct_count': 0, 'wrong_count': 0}
        for bank_id, revision_id in revision_pairs:
            row = row_map.get(revision_id)
            if row is None:
                continue  # 版本下无启用题目，跳过，客户端按缺失兜底
            counts = {k: int(row.get(k) or 0) for k in totals}
            for key, value in counts.items():
                totals[key] += value
            banks.append(
                GetBankProgressBrief(
                    bank_id=bank_id,
                    bank_revision_id=revision_id,
                    **counts,
                    progress_rate=AnalyticsService._rate(counts['answered_count'], counts['total_count']),
                    accuracy_rate=AnalyticsService._rate(
                        counts['correct_count'], counts['correct_count'] + counts['wrong_count'],
                    ),
                )
            )

        return GetCollectionProgressSummary(
            collection_id=collection_id,
            **totals,
            progress_rate=AnalyticsService._rate(totals['answered_count'], totals['total_count']),
            accuracy_rate=AnalyticsService._rate(
                totals['correct_count'], totals['correct_count'] + totals['wrong_count'],
            ),
            banks=banks,
        )

    @staticmethod
    async def get_bank_wrong_sections(
        *,
        db: AsyncSession,
        user_id: int,
        bank_id: int,
    ) -> GetBankWrongSectionCounts:
        """获取题库当前版本的活跃错题篇章树"""
        _, revision = await AnalyticsService._get_bank_context(db=db, user_id=user_id, bank_id=bank_id)
        # 只需要章节树本身，不必跑 get_bank_progress_rows 的两条聚合查询
        sections = list(await bank_section_dao.get_all(db, revision_id=revision.id))
        rows = await learning_analytics_dao.get_wrong_section_counts(
            db,
            user_id=user_id,
            bank_revision_id=revision.id,
        )
        count_map = {row['section_id']: int(row['wrong_count']) for row in rows}
        nodes: dict[int, WrongSectionCount] = {}
        children: dict[int | None, list[int]] = {}
        for section in reversed(sections):
            child_nodes = [nodes[child_id] for child_id in children.get(section.id, [])]
            nodes[section.id] = WrongSectionCount(
                id=section.id,
                name=section.name,
                parent_id=section.parent_id,
                depth=section.depth,
                sort_order=section.sort_order,
                wrong_count=count_map.get(section.id, 0) + sum(child.wrong_count for child in child_nodes),
                children=list(reversed(child_nodes)),
            )
            children.setdefault(section.parent_id, []).append(section.id)
        root_ids = [section.id for section in sections if section.parent_id not in nodes]
        unsectioned_count = count_map.get(None, 0)
        return GetBankWrongSectionCounts(
            bank_id=bank_id,
            bank_revision_id=revision.id,
            total_wrong_count=sum(int(row['wrong_count']) for row in rows),
            unsectioned_wrong_count=unsectioned_count,
            sections=[nodes[section_id] for section_id in root_ids],
        )

    @staticmethod
    def _rank_item(row: dict[str, Any] | None) -> PracticeRankItem | None:
        """构建排行榜项"""
        if row is None:
            return None
        return PracticeRankItem(
            rank=int(row['rank']),
            user_id=int(row['user_id']),
            nickname=row['nickname'],
            avatar=row['avatar'],
            value=Decimal(str(row['value'] or 0)),
        )

    @staticmethod
    async def get_rank_list(
        *,
        db: AsyncSession,
        user_id: int,
        rank_type: RankType,
        offset: int,
        limit: int,
    ) -> GetPracticeRankList:
        """获取刷题量、正确率或连续练习排行榜"""
        total, rows, current = await user_practice_statistics_dao.get_rank_rows(
            db,
            rank_type=rank_type,
            current_user_id=user_id,
            offset=offset,
            limit=limit,
        )
        return GetPracticeRankList(
            rank_type=rank_type,
            total_users=total,
            current_user_rank=AnalyticsService._rank_item(current),
            items=[AnalyticsService._rank_item(row) for row in rows if row is not None],
        )

    @staticmethod
    async def get_user_report(
        *,
        db: AsyncSession,
        user_id: int,
        days: int,
    ) -> GetUserPracticeReport:
        """获取用户累计刷题报告、每日趋势和月度趋势"""
        today = timezone.now().date()
        start_date = today - timedelta(days=days - 1)
        statistics = await user_practice_statistics_dao.get(db, user_id=user_id)
        daily_rows = await user_daily_statistics_dao.get_range(
            db,
            user_id=user_id,
            start_date=start_date,
            end_date=today,
        )
        daily_map = {row.activity_date: row for row in daily_rows}
        daily_trend: list[UserDailyPracticeDetail] = []
        monthly_agg = defaultdict(lambda: {'attempt_count': 0, 'graded_count': 0, 'correct_count': 0, 'duration_ms': 0})
        for day_offset in range(days):
            activity_date = start_date + timedelta(days=day_offset)
            row = daily_map.get(activity_date)
            attempt_count = row.attempt_count if row else 0
            graded_count = row.graded_count if row else 0
            correct_count = row.correct_count if row else 0
            duration_ms = row.duration_ms if row else 0
            daily_trend.append(
                UserDailyPracticeDetail(
                    activity_date=activity_date,
                    attempt_count=attempt_count,
                    graded_count=graded_count,
                    correct_count=correct_count,
                    duration_ms=duration_ms,
                )
            )
            if row:
                month_key = activity_date.strftime('%Y-%m')
                agg = monthly_agg[month_key]
                agg['attempt_count'] += attempt_count
                agg['graded_count'] += graded_count
                agg['correct_count'] += correct_count
                agg['duration_ms'] += duration_ms

        # 补全月度趋势中缺失的月份（包含空月份）
        monthly_trend: list[UserMonthlyPracticeDetail] = []
        cursor = start_date.replace(day=1)
        today_first = today.replace(day=1)
        while cursor <= today_first:
            month_key = cursor.strftime('%Y-%m')
            data = monthly_agg.get(
                month_key,
                {'attempt_count': 0, 'graded_count': 0, 'correct_count': 0, 'duration_ms': 0},
            )
            monthly_trend.append(UserMonthlyPracticeDetail(month=month_key, **data))
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)

        site_summary = await user_practice_statistics_dao.get_site_summary(db)
        _, _, current_rank = await user_practice_statistics_dao.get_rank_rows(
            db,
            rank_type='practice_count',
            current_user_id=user_id,
            offset=0,
            limit=1,
        )
        graded_count = statistics.graded_count if statistics else 0
        correct_count = statistics.correct_count if statistics else 0
        today_row = daily_map.get(today)
        today_attempt_count = today_row.attempt_count if today_row else 0
        return GetUserPracticeReport(
            session_count=statistics.session_count if statistics else 0,
            attempt_count=statistics.attempt_count if statistics else 0,
            graded_count=graded_count,
            correct_count=correct_count,
            accuracy_rate=AnalyticsService._rate(correct_count, graded_count),
            total_duration_ms=statistics.total_duration_ms if statistics else 0,
            practice_days=statistics.practice_days if statistics else 0,
            streak_days=statistics.streak_days if statistics else 0,
            last_practice_date=statistics.last_practice_date if statistics else None,
            site_total_attempt_count=site_summary['total_attempt_count'],
            site_max_attempt_count=site_summary['max_attempt_count'],
            attempt_rank=int(current_rank['rank']) if current_rank else None,
            today_attempt_count=today_attempt_count,
            daily_trend=daily_trend,
            monthly_trend=monthly_trend,
        )

    @staticmethod
    async def get_knowledge_point_trends(
        *,
        db: AsyncSession,
        user_id: int,
        days: int = 90,
    ) -> GetKnowledgePointTrends:
        """基于作答事实表，按顶层知识点 × 日期聚合刷题趋势

        通过 QbQuestionAttempt JOIN QbQuestionKnowledgePoint JOIN QbKnowledgePoint 实时计算，
        仅取 version='default' 知识体系中 parent_id IS NULL 的顶层知识点。
        """
        from backend.app.question_bank_v2.model.knowledge import (
            QbKnowledgePoint,
            QbKnowledgeSystem,
            QbQuestionKnowledgePoint,
        )
        from backend.app.question_bank_v2.model.practice import QbQuestionAttempt

        now = timezone.now()
        start_datetime = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

        practiced_at = sa.cast(QbQuestionAttempt.submitted_time, sa.Date).label('practiced_at')
        attempt_count_col = sa.func.count(QbQuestionAttempt.id).label('attempt_count')
        correct_count_col = sa.func.sum(
            sa.case((QbQuestionAttempt.is_correct.is_(True), 1), else_=0)
        ).label('correct_count')
        avg_duration_col = sa.func.avg(QbQuestionAttempt.duration_ms).label('avg_duration_ms')

        stmt = (
            select(
                practiced_at,
                QbKnowledgePoint.id.label('knowledge_point_id'),
                QbKnowledgePoint.name.label('module_name'),
                QbKnowledgePoint.sort_order,
                attempt_count_col,
                correct_count_col,
                avg_duration_col,
            )
            .select_from(QbQuestionAttempt)
            .join(
                QbQuestionKnowledgePoint,
                and_(
                    QbQuestionAttempt.question_id == QbQuestionKnowledgePoint.question_id,
                    QbQuestionKnowledgePoint.deleted == 0,
                ),
            )
            .join(
                QbKnowledgePoint,
                and_(
                    QbQuestionKnowledgePoint.knowledge_point_id == QbKnowledgePoint.id,
                    QbKnowledgePoint.deleted == 0,
                    QbKnowledgePoint.parent_id.is_(None),
                ),
            )
            .join(
                QbKnowledgeSystem,
                and_(
                    QbKnowledgePoint.system_id == QbKnowledgeSystem.id,
                    QbKnowledgeSystem.deleted == 0,
                    QbKnowledgeSystem.version == 'default',
                ),
            )
            .where(
                QbQuestionAttempt.user_id == user_id,
                QbQuestionAttempt.deleted == 0,
                QbQuestionAttempt.grading_status == 'graded',
                QbQuestionAttempt.submitted_time >= start_datetime,
            )
            .group_by(
                practiced_at,
                QbKnowledgePoint.id,
                QbKnowledgePoint.name,
                QbKnowledgePoint.sort_order,
            )
            .order_by(sa.text('practiced_at'), QbKnowledgePoint.sort_order)
        )

        rows = (await db.execute(stmt)).mappings().all()

        modules: dict[int, KnowledgePointTrendModule] = {}
        for row in rows:
            kp_id = int(row['knowledge_point_id'])
            if kp_id not in modules:
                modules[kp_id] = KnowledgePointTrendModule(
                    module_name=row['module_name'],
                    knowledge_point_id=kp_id,
                    points=[],
                )

            att_count = int(row['attempt_count'])
            cor_count = int(row['correct_count'] or 0)
            accuracy = round(cor_count * 100.0 / att_count, 1) if att_count > 0 else 0.0
            avg_ms = float(row['avg_duration_ms'] or 0)
            avg_seconds = round(avg_ms / 1000.0, 1) if avg_ms > 0 else None

            modules[kp_id].points.append(
                KnowledgePointTrendPoint(
                    practiced_at=str(row['practiced_at']),
                    attempt_count=att_count,
                    correct_count=cor_count,
                    accuracy=accuracy,
                    avg_seconds=avg_seconds,
                )
            )

        return GetKnowledgePointTrends(module_trends=list(modules.values()))


analytics_service: AnalyticsService = AnalyticsService()
