#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from croniter import croniter
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.admin.model import Category
from backend.app.mydrive.crud.crud_feishu import feishu_sheet_config_dao, feishu_sheet_task_dao
from backend.app.mydrive.model.feishu import FeishuSheetConfig, FeishuSheetTask
from backend.app.mydrive.model.resource import MyDriveResource
from backend.app.mydrive.schema.feishu import CreateFeishuSheetConfigParam, UpdateFeishuSheetConfigParam
from backend.common.exception import errors
from backend.common.log import log
from backend.database.db import async_db_session
from backend.plugin.feishu.service.sheet_service import feishu_sheet_service
from backend.utils.timezone import timezone

# 表格列顺序：标题 / 分享链接 / 分类 / 更新时间 / 状态 / 来源 / ID
HEADERS: list[str] = ['标题', '分享链接', '分类', '更新时间', '状态', '来源', 'ID']
LAST_COLUMN: str = 'G'
ID_COLUMN_INDEX: int = len(HEADERS) - 1
SOURCE_COLUMN_INDEX: int = 5
HEADER_ROWS: int = 1

# 状态中文映射与下拉选项
STATUS_LABELS: dict[str, str] = {'enabled': '有效', 'disabled': '失效'}
STATUS_OPTIONS: list[str] = ['有效', '失效']
STATUS_COLORS: list[str] = ['#c9e7c0', '#f5c9b6']

# 来源取值（配置里的 source_weights 若全部失效，用这套兜底，保证来源列下拉不为空）
DEFAULT_SOURCE_OPTIONS: list[str] = ['网络获取', '用户推荐', '店铺购买']

# 时间格式
DATETIME_FORMAT: str = '%Y-%m-%d %H:%M:%S'

# 数据区字体：加粗 + 12 号（飞书默认字号约 10~11，12 号更易读）
BODY_FONT_SIZE: int = 12

# 读取表格时的兜底上限
#
# 正常情况下读取范围由子表元信息的 `grid_properties.row_count` 动态决定（见 `_scan_bound()`），
# 它天然是「数据行数的上界」——向网格之外的行写入会失败，所以数据不会超出网格。
# 只有取不到元信息时才回退到这个常量，避免退回「每轮固定读 5000 行」的旧行为。
MAX_SCAN_ROWS: int = 5000
# 动态读取上界的最小值：网格刚建时行数较少，留一点余量避免贴着边界读
MIN_SCAN_ROWS: int = 100
# 更新已有行时单次请求的最大区域数
UPDATE_CHUNK_SIZE: int = 50
# 数据区样式与下拉额外预留的行数、最少装饰行数
BODY_BUFFER_ROWS: int = 20
MIN_DECORATE_ROWS: int = 50

# 列宽（像素）
COLUMN_WIDTHS: list[int] = [300, 320, 110, 160, 80, 100, 70]

# 定时检查窗口（分钟），与 mydrive 同步保持一致
CRON_WINDOW_MINUTES: int = 5

# 任务超时阈值（分钟）：超过该时长仍处于 pending / running 的任务视为僵死，创建新任务时回收
TASK_STALE_MINUTES: int = 60

# 分类来源候选里，附带多少个分类名示例（供管理端确认来源选对了）
CATEGORY_SAMPLE_SIZE: int = 3


class MyDriveFeishuExportService:
    """飞书表格导出服务

    配置来源为 feishu_sheet_config 表（每行一份配置，可并存多张表），
    导入逻辑本身与配置解耦：任何一个以 FeishuSheetConfig 为入参的方法，
    都可以服务任意一张表 / 任意一个业务场景（公考、考研……）。
    """

    def __init__(self) -> None:
        # 装饰签名缓存：{配置 ID:子表名称: (装饰签名, 已装饰到的末行号)}
        #
        # 表头样式、数据区样式、三个下拉列表都是「一次性结构」，不应该每轮重写。
        # 用签名判断是否需要重建：签名 = 表头 + 各下拉选项 + 表格地址。任一变化
        # （改了配置里的分类选项 / 来源权重，或换了表格）都会触发一次重建。
        # 缓存只存在进程内存里，重启后每个子表会重建一次，属于可接受的一次性开销。
        self._decorated: dict[str, tuple[tuple[Any, ...], int]] = {}

    # ---------- 配置：解析 ----------

    @staticmethod
    def sheet_type_map(config: FeishuSheetConfig) -> dict[str, list[str]]:
        """
        子表 -> 资源类型列表（多个资源类型可映射到同一子表）

        :param config: 导出配置
        :return:
        """
        grouped: dict[str, list[str]] = defaultdict(list)
        for resource_type, sheet in (config.sheet_map or {}).items():
            if str(resource_type).strip() and str(sheet).strip():
                grouped[str(sheet)].append(str(resource_type))
        if not grouped:
            log.warning(f'[飞书导出] 配置「{config.name}」的 sheet_map 为空，本次不同步任何子表')
        return dict(grouped)

    @staticmethod
    def source_options(config: FeishuSheetConfig) -> list[str]:
        """
        来源列的可选值：直接取 source_weights 的键（权重决定抽取概率，键决定下拉选项）

        :param config: 导出配置
        :return:
        """
        options = [str(key).strip() for key in (config.source_weights or {}) if str(key).strip()]
        return options or list(DEFAULT_SOURCE_OPTIONS)

    @staticmethod
    def _random_source(*, config: FeishuSheetConfig, sheet: str) -> str:
        """
        按权重随机生成来源，店铺购买仅在指定子表出现

        :param config: 导出配置
        :param sheet: 子表名称
        :return:
        """
        weights = {str(key): int(value) for key, value in (config.source_weights or {}).items()}
        if sheet not in (config.paid_sheets or []):
            weights.pop('店铺购买', None)

        pool = [key for key, value in weights.items() if value > 0]
        if not pool:
            return ''
        return random.choices(pool, weights=[weights[key] for key in pool], k=1)[0]

    # ---------- 配置：管理 ----------

    @staticmethod
    async def get_config(db: AsyncSession, *, pk: int) -> FeishuSheetConfig:
        """
        获取导出配置

        :param db: 数据库会话
        :param pk: 导出配置 ID
        :return:
        """
        config = await feishu_sheet_config_dao.get(db, pk)
        if config is None:
            raise errors.NotFoundError(msg='飞书表导出配置不存在')
        return config

    @staticmethod
    async def get_config_select(name: str | None = None, *, is_enabled: bool | None = None) -> Select:
        """获取导出配置查询语句。"""
        return await feishu_sheet_config_dao.get_select(name, is_enabled)

    @staticmethod
    async def create_config(db: AsyncSession, *, obj: CreateFeishuSheetConfigParam) -> FeishuSheetConfig:
        """
        创建导出配置

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await MyDriveFeishuExportService._validate_config(db, obj, pk=None)
        config = FeishuSheetConfig(**obj.model_dump())
        db.add(config)
        await db.flush()
        return config

    @staticmethod
    async def update_config(db: AsyncSession, *, pk: int, obj: UpdateFeishuSheetConfigParam) -> None:
        """
        更新导出配置

        :param db: 数据库会话
        :param pk: 导出配置 ID
        :param obj: 更新参数
        :return:
        """
        config = await MyDriveFeishuExportService.get_config(db, pk=pk)
        values = obj.model_dump(exclude_unset=True)
        merged = {**{key: getattr(config, key) for key in values}, **values}
        await MyDriveFeishuExportService._validate_config(db, obj, pk=pk, merged=merged)
        if values:
            await feishu_sheet_config_dao.update_model(db, config.id, values)

    @staticmethod
    async def delete_config(db: AsyncSession, *, pk: int) -> None:
        """
        删除导出配置

        :param db: 数据库会话
        :param pk: 导出配置 ID
        :return:
        """
        config = await MyDriveFeishuExportService.get_config(db, pk=pk)
        if await feishu_sheet_task_dao.has_active_task(db, config.id):
            raise errors.ConflictError(msg='该配置存在待执行或执行中的任务，无法删除')
        await feishu_sheet_config_dao.delete_model(db, config.id)

    @staticmethod
    async def _validate_config(
        db: AsyncSession,
        obj: CreateFeishuSheetConfigParam | UpdateFeishuSheetConfigParam,
        *,
        pk: int | None,
        merged: dict[str, Any] | None = None,
    ) -> None:
        """
        校验导出配置的取值

        :param db: 数据库会话
        :param obj: 创建或更新参数
        :param pk: 导出配置 ID（更新时传入，用于排除自身）
        :param merged: 更新后的完整取值（更新时传入）
        :return:
        """
        name = merged['name'] if merged else obj.name
        if name:
            existing = await feishu_sheet_config_dao.get_by_name(db, name)
            if existing is not None and existing.id != pk:
                raise errors.ConflictError(msg='配置名称已存在')

        values = merged or obj.model_dump()
        if not values.get('sheet_map'):
            raise errors.ForbiddenError(msg='资源类型映射不能为空，否则不会有任何资源被导出')
        if not values.get('sheet_url'):
            raise errors.ForbiddenError(msg='飞书表格地址不能为空')

        cron = values.get('cron')
        if cron and not croniter.is_valid(cron):
            raise errors.ForbiddenError(msg=f'定时表达式无效: {cron}（需为标准 5 段式，如 0 3 * * *）')

        weights = values.get('source_weights') or {}
        for key, value in weights.items():
            if not str(key).strip():
                raise errors.ForbiddenError(msg='来源名称不能为空')
            if not isinstance(value, int) or isinstance(value, bool):
                raise errors.ForbiddenError(msg=f'来源权重必须是整数: {key}={value!r}')
            if value < 0:
                raise errors.ForbiddenError(msg=f'来源权重不能为负数: {key}={value}')

    @staticmethod
    async def list_category_sources(db: AsyncSession) -> list[dict[str, Any]]:
        """
        列出可选的「分类来源」候选（app_code + category_type 组合）

        直接从 sys_category 聚合，不写死任何业务值：将来新增业务（如考研）后，
        只要分类表里有数据，管理端下拉就会自动出现，无需改代码。
        附带的 `sample_names` 供管理端展示，便于确认「来源选对了」。

        :param db: 数据库会话
        :return:
        """
        stmt = (
            select(Category.app_code, Category.type, Category.name)
            .where(Category.deleted == 0)
            .order_by(Category.app_code, Category.type, Category.sort_order, Category.id)
        )
        rows = (await db.execute(stmt)).all()

        # 分类总量（数百条量级）一次拉回后在内存分组，比逐组查询更省往返
        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for row in rows:
            grouped[str(row.app_code), str(row.type)].append(str(row.name))

        return [
            {
                'app_code': app_code,
                'category_type': category_type,
                'category_count': len(names),
                'sample_names': names[:CATEGORY_SAMPLE_SIZE],
            }
            for (app_code, category_type), names in grouped.items()
        ]

    # ---------- 任务：管理 ----------

    @staticmethod
    async def get_task(db: AsyncSession, *, pk: int) -> FeishuSheetTask:
        """
        获取导出任务

        :param db: 数据库会话
        :param pk: 导出任务 ID
        :return:
        """
        task = await feishu_sheet_task_dao.get(db, pk)
        if task is None:
            raise errors.NotFoundError(msg='飞书表导出任务不存在')
        return task

    @staticmethod
    async def get_task_select(config_id: int | None = None, status: str | None = None) -> Select:
        """获取导出任务查询语句。"""
        return await feishu_sheet_task_dao.get_select(config_id, status)

    @staticmethod
    async def create_task(db: AsyncSession, *, config_id: int, manual: bool = False) -> FeishuSheetTask:
        """
        创建待执行的导出任务

        :param db: 数据库会话
        :param config_id: 导出配置 ID
        :param manual: 是否人工触发（人工触发忽略启用状态与结束时间）
        :return:
        """
        config = await MyDriveFeishuExportService.get_config(db, pk=config_id)
        if not manual:
            if not config.is_enabled:
                raise errors.ForbiddenError(msg='导出配置已停用')
            if config.end_time is not None and config.end_time <= timezone.now():
                raise errors.ForbiddenError(msg='导出配置已超过结束时间')

        # 先回收僵死任务：worker 进程被强杀 / 容器重启时，running 状态会永久留在库里，
        # 若不回收，该配置将再也无法触发导出（has_active_task 永远为真）。
        await MyDriveFeishuExportService.reclaim_stale_tasks(db, config_id=config.id)

        if await feishu_sheet_task_dao.has_active_task(db, config.id):
            raise errors.ConflictError(msg='导出配置已有待执行或执行中的任务')

        task = FeishuSheetTask(
            config_id=config.id,
            statistics={'total_inserted': 0, 'total_updated': 0, 'sheets': []},
        )
        db.add(task)
        await db.flush()
        return task

    @staticmethod
    async def reclaim_stale_tasks(db: AsyncSession, *, config_id: int) -> int:
        """
        把超时未结束的任务标记为失败，避免僵死任务永久阻塞该配置

        判定口径：状态仍为 pending / running，且开始时间（无开始时间则取创建时间）
        早于 now - TASK_STALE_MINUTES。

        :param db: 数据库会话
        :param config_id: 导出配置 ID
        :return: 被回收的任务数
        """
        deadline = timezone.now() - timedelta(minutes=TASK_STALE_MINUTES)
        stmt = select(FeishuSheetTask).where(
            FeishuSheetTask.config_id == config_id,
            FeishuSheetTask.status.in_(('pending', 'running')),
            func.coalesce(FeishuSheetTask.started_at, FeishuSheetTask.created_time) < deadline,
        )
        stale_tasks = list((await db.execute(stmt)).scalars().all())
        for stale in stale_tasks:
            stale.status = 'failed'
            stale.error_message = (
                f'任务超过 {TASK_STALE_MINUTES} 分钟未结束（开始于 '
                f'{timezone.from_datetime(stale.started_at or stale.created_time)}），已判定为超时中断'
            )
            stale.finished_at = timezone.now()
            log.warning(f'[飞书导出] 回收僵死任务 {stale.id}（配置 {config_id}）')
        return len(stale_tasks)

    @staticmethod
    async def execute_task(db: AsyncSession, task_id: int, *, commit: bool = True) -> dict[str, Any]:
        """
        执行导出任务，并把结果写回任务记录

        事务约定：本方法**不主动结束**调用方的事务。若自行 mid-flight commit，
        会把调用方 `async with async_db_session.begin()` 的事务提前关闭，
        之后任何写入（statistics / status / finished_at）都会抛
        `InvalidRequestError: Can't operate on closed transaction inside context manager`。
        因此这里统一用 flush() 把中间状态推给数据库，由调用方在退出时提交。

        :param db: 数据库会话
        :param task_id: 导出任务 ID
        :param commit: 是否在结束时提交（调用方已用 begin() 时传 False）
        :return:
        """
        task = await MyDriveFeishuExportService.get_task(db, pk=task_id)
        if task.status not in {'pending', 'running'}:
            raise errors.ForbiddenError(msg='当前导出任务无法执行')

        config = await MyDriveFeishuExportService.get_config(db, pk=task.config_id)

        task.status = 'running'
        task.started_at = timezone.now()
        task.error_message = None
        # 先落库 running 状态，便于前端在任务执行期间就能看到「执行中」
        await db.flush()
        if commit:
            await db.commit()

        try:
            # sync_all 是实例方法（内部要用 self.sheet_type_map），必须经实例调用
            result = await MyDriveFeishuExportService().sync_all(config)
        except Exception as exc:
            task.status = 'failed'
            task.error_message = str(exc)
            task.finished_at = timezone.now()
            await feishu_sheet_config_dao.update_model(db, config.id, {'last_synced_at': timezone.now()})
            await db.flush()
            if commit:
                await db.commit()
            log.error(f'[飞书导出] 任务 {task_id}（配置「{config.name}」）执行失败: {exc!s}')
            return {'task_id': task_id, 'success': False, 'config_name': config.name, 'error': str(exc)}

        failed = [item for item in result.get('sheets', []) if item.get('status') == 'failed']
        task.statistics = result
        task.status = 'failed' if failed else 'completed'
        task.error_message = '；'.join(f'{item.get("sheet")}: {item.get("error")}' for item in failed) or None
        task.finished_at = timezone.now()
        # 记录本轮执行时间，供定时判重（避免同一窗口重复派发）
        await feishu_sheet_config_dao.update_model(db, config.id, {'last_synced_at': timezone.now()})
        await db.flush()
        if commit:
            await db.commit()
        log.info(f'[飞书导出] 任务 {task_id}（配置「{config.name}」）完成: {result}')
        return {'task_id': task_id, 'success': not failed, 'config_name': config.name, **result}

    @staticmethod
    def should_execute_now(cron_expr: str, last_synced_at: datetime | None, current_time: datetime) -> bool:
        """
        判断当前检查窗口是否应执行

        :param cron_expr: Cron 表达式
        :param last_synced_at: 最近同步时间
        :param current_time: 当前时间
        :return:
        """
        if not cron_expr or not cron_expr.strip():
            return False
        if not croniter.is_valid(cron_expr):
            log.error(f'[飞书导出] 定时表达式无效，已跳过: {cron_expr}')
            return False

        cron = croniter(cron_expr, current_time)
        previous_time = cron.get_prev(datetime)
        diff_minutes = (current_time - previous_time).total_seconds() / 60
        if diff_minutes < 0 or diff_minutes > CRON_WINDOW_MINUTES:
            return False
        if last_synced_at is None:
            return True
        return last_synced_at < previous_time

    # ---------- 取数 ----------

    @staticmethod
    def is_public_visible(resource: MyDriveResource) -> bool:
        """
        判断资源当前是否对公众可见

        口径与 app/mydrive/crud/crud_resource.py 中 get_public_select / get_public_hot_list /
        get_public 保持一致：资源未删除、状态有效、审核通过，且存在一条可用的分享记录。
        这张表格是对外公开的，任何一条不满足都不应该以「有效」的姿态出现。

        :param resource: 资源对象
        :return:
        """
        if resource.deleted != 0:
            return False
        if resource.status != 'enabled':
            return False
        if resource.audit_status != 'approved':
            return False

        share = resource.share
        if share is None or share.deleted != 0:
            return False
        if share.share_status != 'active':
            return False
        return bool(str(share.share_url or '').strip())

    @staticmethod
    async def _load_app_category_ids(*, config: FeishuSheetConfig, db: AsyncSession) -> set[int]:
        """
        加载本配置分类体系下的全部分类 ID

        多张表并存时，仅凭 resource_type 无法区分资源归属：公考的「笔记」与考研的「笔记」
        是同一个类型值。必须用 category_id 落在本配置 app_code + category_type 的分类集合内
        做隔离，否则每张表都会把别的业务的资源一起拉进去。

        :param config: 导出配置
        :param db: 数据库会话
        :return:
        """
        stmt = select(Category.id).where(
            Category.app_code == config.app_code,
            Category.type == config.category_type,
        )
        return {int(row[0]) for row in (await db.execute(stmt)).all()}

    @staticmethod
    async def _count_app_categories(*, app_code: str, category_type: str, db: AsyncSession) -> int:
        """
        统计指定 app_code + category_type 下的分类数量（用于校验取数隔离是否生效）

        :param app_code: 分类来源
        :param category_type: 分类类型
        :param db: 数据库会话
        :return:
        """
        stmt = (
            select(func.count())
            .select_from(Category)
            .where(
                Category.app_code == app_code,
                Category.type == category_type,
            )
        )
        return int((await db.execute(stmt)).scalar() or 0)

    @staticmethod
    async def _load_resources(
        *,
        db: AsyncSession,
        resource_types: list[str],
        category_ids: set[int],
        known_ids: set[int] | None = None,
    ) -> list[MyDriveResource]:
        """
        查询指定类型、且归属本配置分类体系的资源（含分享信息）

        取数口径分两类：
        - 正常候选：属于本子表资源类型、归属本配置分类、且未删除的资源，只有它们才可能新增行
        - 复核对象：表格里已经存在的资源 ID，一律取出（不限类型、含已软删除），
          用于把对应行按当前状态改写成「有效 / 失效」；类型被改走的资源也能在此改判，不会留下僵尸行

        :param db: 数据库会话
        :param resource_types: 资源类型列表
        :param category_ids: 本配置分类体系下的分类 ID 集合
        :param known_ids: 表格中已存在的资源 ID 集合
        :return:
        """
        if not category_ids:
            log.warning('[飞书导出] 本配置分类体系下没有任何分类，本次不会匹配到任何资源')

        candidates = and_(
            MyDriveResource.resource_type.in_(resource_types),
            MyDriveResource.category_id.in_(category_ids),
            MyDriveResource.deleted == 0,
        )
        where_clause = or_(candidates, MyDriveResource.id.in_(known_ids)) if known_ids else candidates

        stmt = (
            select(MyDriveResource)
            .where(where_clause)
            .options(selectinload(MyDriveResource.share))
            .order_by(MyDriveResource.updated_time.desc(), MyDriveResource.id.desc())
            # MyDriveResource.share 声明为 lazy='noload'：若同一会话中已访问过该属性，
            # identity map 会把对象标记为「关系已加载（空值）」，此时 selectinload 不会覆盖它，
            # is_public_visible 将把有效资源误判为失效。populate_existing 强制以数据库当前值刷新，避免该陷阱。
            .execution_options(populate_existing=True)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def _load_category_names(*, config: FeishuSheetConfig, db: AsyncSession) -> dict[int, str]:
        """
        加载分类 id -> 分类名映射

        :param config: 导出配置
        :param db: 数据库会话
        :return:
        """
        stmt = select(Category.id, Category.name).where(
            Category.app_code == config.app_code,
            Category.type == config.category_type,
        )
        rows = (await db.execute(stmt)).all()
        return {int(row[0]): str(row[1]) for row in rows}

    # ---------- 行组装 ----------

    @staticmethod
    def _build_row(resource: MyDriveResource, category_name: str, source: str, status_label: str) -> list[Any]:
        """
        组装一行表格数据

        :param resource: 资源对象
        :param category_name: 分类名称
        :param source: 来源
        :param status_label: 状态列文案（有效 / 失效）
        :return:
        """
        share_url = resource.share.share_url if resource.share else ''
        updated = resource.updated_time or resource.created_time
        # ORM 取出的时间为 UTC，需先转为项目配置的本地时区再格式化，否则表格里会比北京时间早 8 小时
        return [
            resource.title,
            share_url or '',
            category_name,
            timezone.from_datetime(updated).strftime(DATETIME_FORMAT) if updated else '',
            status_label,
            source,
            resource.id,
        ]

    @staticmethod
    def _normalize_cell(value: Any) -> str:
        """
        把单元格值归一化成可比较的字符串

        飞书回读结果与写入值存在三类已知差异，归一化后即可直接做值对比：

        1. 空单元格：行长度不足或值为 None，统一视为空字符串；
        2. 数字列（ID）：可能回读为 int / float / str，统一按整数文本比较，
           否则 `123` 与 `123.0` 会被判成不同，导致该行每轮都被重写；
        3. 富文本 / 超链接列：回读为 `[{'text': ..., 'link': ...}]` 结构（也可能是单个对象），
           取其中的文本拼接，与写入的 URL 字符串等价。

        归一化只在「确定相等」时才认为相等：任何无法识别的结构都会退化成
        `str(value)`，从而产生「不等」的判断并触发一次写入 —— 宁可多写一次，
        也不能因为判等过宽而漏掉一次真实更新。

        :param value: 单元格原始值
        :return:
        """
        if value is None:
            return ''
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (int, float)):
            return str(int(value)) if float(value).is_integer() else str(value)
        if isinstance(value, (list, dict)):
            segments = value if isinstance(value, list) else [value]
            parts = []
            for segment in segments:
                # 只有带 text / link 标记的才是可识别的富文本片段，其余原样保留文本
                if isinstance(segment, dict) and ('text' in segment or 'link' in segment):
                    parts.append(str(segment.get('text') or segment.get('link') or ''))
                else:
                    parts.append(str(segment))
            return ''.join(parts)
        return str(value)

    @classmethod
    def _row_changed(cls, old_values: list[Any], new_row: list[Any]) -> bool:
        """
        判断表格中的旧行与即将写入的新行是否存在差异

        逐列归一化后比较；旧行长度不足时缺失的列视为空。任一处不同即视为「变过」。

        :param old_values: 从表格回读的该行原始值
        :param new_row: 由当前数据库状态组装出的新行
        :return: 是否需要写入
        """
        for index, new_value in enumerate(new_row):
            old_value = old_values[index] if index < len(old_values) else None
            if cls._normalize_cell(old_value) != cls._normalize_cell(new_value):
                return True
        return False

    # ---------- 表格状态 ----------

    async def _scan_bound(self, *, config: FeishuSheetConfig, sheet: str) -> int:
        """
        计算读取数据区的行上界

        优先取子表已分配的网格行数（`grid_properties.row_count`）：它是「数据行数的天然上界」，
        因为向网格之外的行写入会失败，所以数据不可能超出网格。该值来自子表元信息，
        命中插件侧的子表列表缓存时零额外请求。

        取代原先写死的 `MAX_SCAN_ROWS=5000`，好处有二：
        1. 读取量跟实际网格大小走，表还小时不必每轮读 5000 行范围；
        2. 不会因表变大超过 5000 行而读到一半 —— 旧实现超过 5000 行后，后面的行读不到
           会被误判为新资源并重复插入，是颗定时炸弹。

        :param config: 导出配置
        :param sheet: 子表名称
        :return:
        """
        try:
            grid_rows = await feishu_sheet_service.get_grid_row_count(workbook=config.sheet_url, sheet=sheet)
        except Exception as exc:
            log.warning(f'[飞书导出] 子表 {sheet} 取网格行数失败，回退到 {MAX_SCAN_ROWS} 行: {exc!s}')
            return MAX_SCAN_ROWS

        if grid_rows <= 0:
            log.warning(f'[飞书导出] 子表 {sheet} 未取到网格行数，回退到 {MAX_SCAN_ROWS} 行')
            return MAX_SCAN_ROWS
        return max(grid_rows, MIN_SCAN_ROWS)

    async def _scan_sheet(self, *, config: FeishuSheetConfig, sheet: str) -> tuple[dict[int, dict[str, Any]], int]:
        """
        一次读取数据区，同时得到行号索引与数据末行

        之所以把两件事合并成一次读取：原先 `_read_sheet_state()` 与 `decorate_sheet()`
        各自读一遍同一个范围，同一轮里纯重复读两次表。

        :param config: 导出配置
        :param sheet: 子表名称
        :return: (state, last_row)
            - state: {资源 ID: {'row': 行号, 'values': 该行原始值, 'source': 来源}}
            - last_row: 最后一个非空行号（含表头行），无数据时为 HEADER_ROWS
        """
        bound = await self._scan_bound(config=config, sheet=sheet)
        values = await feishu_sheet_service.read(
            workbook=config.sheet_url,
            sheet=sheet,
            cell_range=f'A2:{LAST_COLUMN}{bound}',
        )

        state: dict[int, dict[str, Any]] = {}
        last_row = HEADER_ROWS
        for index, row in enumerate(values):
            if row and any(cell not in (None, '') for cell in row):
                last_row = index + HEADER_ROWS + 1
            if not row or len(row) <= ID_COLUMN_INDEX:
                continue
            resource_id = self._to_int(row[ID_COLUMN_INDEX])
            if resource_id is None:
                continue
            source = row[SOURCE_COLUMN_INDEX] if len(row) > SOURCE_COLUMN_INDEX else ''
            state[resource_id] = {
                'row': index + HEADER_ROWS + 1,
                'values': list(row),
                'source': source,
            }

        if values and values[-1] and any(cell not in (None, '') for cell in values[-1]):
            log.warning(
                f'[飞书导出] 子表 {sheet} 数据已铺满读取上界 A2:{LAST_COLUMN}{bound}'
                f'（上界 = 网格已分配行数），下一轮请确认网格是否已扩容'
            )
        return state, last_row

    async def _read_sheet_state(self, *, config: FeishuSheetConfig, sheet: str) -> dict[int, dict[str, Any]]:
        """
        读取表格现有数据，返回 {资源 ID: {'row': 行号, 'source': 来源}}

        :param config: 导出配置
        :param sheet: 子表名称
        :return:
        """
        state, _ = await self._scan_sheet(config=config, sheet=sheet)
        return state

    async def _last_data_row(self, *, config: FeishuSheetConfig, sheet: str) -> int:
        """
        读取数据区，返回最后一个非空行号（含表头行）

        :param config: 导出配置
        :param sheet: 子表名称
        :return:
        """
        _, last_row = await self._scan_sheet(config=config, sheet=sheet)
        return last_row

    @staticmethod
    def _to_int(value: Any) -> int | None:
        """
        尽力把单元格值转成整数

        :param value: 单元格值
        :return:
        """
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else None
        if isinstance(value, str):
            text = value.strip()
            return int(text) if text.isdigit() else None
        return None

    async def _ensure_grid_rows(self, *, config: FeishuSheetConfig, sheet: str, min_rows: int) -> None:
        """
        确保子表网格行数不少于指定值

        :param config: 导出配置
        :param sheet: 子表名称
        :param min_rows: 需要的最小行数
        :return:
        """
        current = await feishu_sheet_service.get_grid_row_count(workbook=config.sheet_url, sheet=sheet)
        if current >= min_rows:
            return
        workbook_token, sheet_id = await feishu_sheet_service.resolve_target(config.sheet_url, sheet)
        if current <= 0:
            # 取不到网格行数时不擅自扩容：insert_rows 的 position 依赖准确的当前行数，
            # 猜错位置会把数据区结构顶乱。宁可少扩容（下一轮 get_grid_row_count 就正常了）。
            log.warning(f'[飞书导出] 子表 {sheet} 未取到网格行数，跳过扩容')
            return
        log.info(f'[飞书导出] 扩容子表 {sheet}: {current} -> {min_rows}')
        await feishu_sheet_service.insert_rows(
            workbook=workbook_token,
            sheet=sheet_id,
            position=current + 1,
            count=min_rows - current,
            inherit_style='none',
        )

    # ---------- 装饰 ----------

    def _decoration_signature(self, *, config: FeishuSheetConfig, sheet: str) -> tuple[Any, ...]:
        """
        计算装饰签名：签名一致即代表表头与下拉无需重建

        包含三样会直接影响装饰结果的东西：表格地址、表头文案、三个下拉的选项。
        只要它们没变，重建出来的结果就与现状完全相同，没有重写的必要。

        :param config: 导出配置
        :param sheet: 子表名称
        :return:
        """
        return (
            sheet,
            str(config.sheet_url or ''),
            tuple(HEADERS),
            tuple(str(item) for item in (config.category_options or [])),
            tuple(self.source_options(config)),
            tuple(STATUS_OPTIONS),
        )

    async def decorate_sheet(self, *, config: FeishuSheetConfig, sheet: str, data_rows: int | None = None) -> int:
        """
        重建子表的表头样式、数据区样式与下拉列表

        :param config: 导出配置
        :param sheet: 子表名称
        :param data_rows: 已知的数据行数；为空时自行读取。传入它可避免与调用方重复读表
        :return: 本次装饰覆盖到的末行号
        """
        if data_rows is None:
            _, last_row = await self._scan_sheet(config=config, sheet=sheet)
            data_rows = max(last_row - HEADER_ROWS, 0)
        end_row = max(data_rows + BODY_BUFFER_ROWS, MIN_DECORATE_ROWS)

        await self._ensure_grid_rows(config=config, sheet=sheet, min_rows=end_row)

        header_style = feishu_sheet_service.build_style(
            bold=True,
            font_color='#FFFFFF',
            background_color='#4472C4',
            horizontal_alignment='center',
            vertical_alignment='middle',
            border_type='FULL_BORDER',
            border_color='#B7C9D9',
        )
        await feishu_sheet_service.set_style(
            workbook=config.sheet_url, sheet=sheet, cell_range=f'A1:{LAST_COLUMN}1', style=header_style
        )

        body_style = feishu_sheet_service.build_style(
            bold=True,
            font_size=BODY_FONT_SIZE,
            vertical_alignment='middle',
            border_type='FULL_BORDER',
            border_color='#DFE5EC',
        )
        await feishu_sheet_service.set_style(
            workbook=config.sheet_url, sheet=sheet, cell_range=f'A2:{LAST_COLUMN}{end_row}', style=body_style
        )

        await feishu_sheet_service.set_dropdown(
            workbook=config.sheet_url,
            sheet=sheet,
            cell_range=f'C2:C{end_row}',
            options=list(config.category_options or []),
        )
        await feishu_sheet_service.set_dropdown(
            workbook=config.sheet_url,
            sheet=sheet,
            cell_range=f'E2:E{end_row}',
            options=STATUS_OPTIONS,
            colors=STATUS_COLORS,
        )
        await feishu_sheet_service.set_dropdown(
            workbook=config.sheet_url,
            sheet=sheet,
            cell_range=f'F2:F{end_row}',
            options=self.source_options(config),
        )
        log.info(f'[飞书导出] 子表装饰完成 {sheet} 数据区=A2:{LAST_COLUMN}{end_row}')
        return end_row

    async def _apply_decoration(self, *, config: FeishuSheetConfig, sheet: str, data_rows: int | None = None) -> int:
        """
        执行一次装饰，并把「签名 + 覆盖范围」记入缓存

        :param config: 导出配置
        :param sheet: 子表名称
        :param data_rows: 已知的数据行数
        :return: 本次装饰覆盖到的末行号
        """
        end_row = await self.decorate_sheet(config=config, sheet=sheet, data_rows=data_rows)
        self._decorated[f'{config.id}:{sheet}'] = (
            self._decoration_signature(config=config, sheet=sheet),
            end_row,
        )
        return end_row

    async def ensure_decorated(self, *, config: FeishuSheetConfig, sheet: str, data_rows: int) -> bool:
        """
        按需装饰：只在「首次」「选项变化」或「数据区超出已装饰范围」时才重建

        表头样式与下拉是结构性的东西，每轮重写纯属浪费（一轮 6 次请求，且结果完全相同）。
        因此这里先比对签名与覆盖范围，命中缓存则直接返回，一次请求都不发。

        触发重建的三种情形：
        1. 本进程首次处理该子表（缓存为空，进程重启后最多各触发一次）；
        2. 签名变化（改了分类下拉选项 / 来源权重 / 表格地址）；
        3. 数据行数增长到超出上次装饰的覆盖范围（需要为新增行补下拉与样式）。

        :param config: 导出配置
        :param sheet: 子表名称
        :param data_rows: 本轮数据区的实际行数（不含表头）
        :return: 本次是否真的执行了装饰
        """
        end_row = max(data_rows + BODY_BUFFER_ROWS, MIN_DECORATE_ROWS)
        cached = self._decorated.get(f'{config.id}:{sheet}')
        if (
            cached is not None
            and cached[0] == self._decoration_signature(config=config, sheet=sheet)
            and cached[1] >= end_row
        ):
            return False
        await self._apply_decoration(config=config, sheet=sheet, data_rows=data_rows)
        return True

    # ---------- 初始化 ----------

    async def init_sheet(
        self,
        *,
        config: FeishuSheetConfig,
        sheet: str,
        rename_from: str | None = None,
        clear_data: bool = False,
    ) -> None:
        """
        初始化单个子表：重命名 / 表头 / 样式 / 下拉 / 列宽 / 隐藏 ID 列

        :param config: 导出配置
        :param sheet: 目标子表名称
        :param rename_from: 若目标不存在，则把该名称的子表重命名过来
        :param clear_data: 是否清空既有数据区内容（会丢失来源列的人工痕迹）
        :return:
        """
        sheet_id = await feishu_sheet_service.find_sheet_by_title(workbook=config.sheet_url, title=sheet)
        if not sheet_id and rename_from:
            sheet_id = await feishu_sheet_service.find_sheet_by_title(workbook=config.sheet_url, title=rename_from)
            if sheet_id:
                await feishu_sheet_service.rename_sheet(workbook=config.sheet_url, sheet=rename_from, title=sheet)
                log.info(f'[飞书导出] 子表重命名 {rename_from} -> {sheet}')
        if not sheet_id:
            await feishu_sheet_service.create_sheet(workbook=config.sheet_url, title=sheet)
            log.info(f'[飞书导出] 新建子表 {sheet}')

        if clear_data:
            last_row = await self._last_data_row(config=config, sheet=sheet)
            if last_row > HEADER_ROWS:
                await feishu_sheet_service.clear_values(
                    workbook=config.sheet_url,
                    sheet=sheet,
                    cell_range=f'A{HEADER_ROWS + 1}:{LAST_COLUMN}{last_row}',
                )
                log.info(f'[飞书导出] 清空历史数据 {sheet} A2:{LAST_COLUMN}{last_row}')

        await feishu_sheet_service.write(
            workbook=config.sheet_url,
            sheet=sheet,
            cell_range=f'A1:{LAST_COLUMN}1',
            values=[HEADERS],
        )
        for index, width in enumerate(COLUMN_WIDTHS, start=1):
            await feishu_sheet_service.resize(
                workbook=config.sheet_url,
                sheet=sheet,
                dimension='columns',
                start=index,
                end=index,
                size=width,
            )
        await self._apply_decoration(config=config, sheet=sheet)
        await feishu_sheet_service.set_dimension_visible(
            workbook=config.sheet_url,
            sheet=sheet,
            dimension='columns',
            start=len(HEADERS),
            end=len(HEADERS),
            visible=False,
        )
        log.info(f'[飞书导出] 子表初始化完成 {sheet}')

    async def _init_one(
        self, *, config: FeishuSheetConfig, sheet: str, rename_from: str | None, clear_data: bool
    ) -> dict[str, Any]:
        """
        初始化单个子表并捕获异常

        :param config: 导出配置
        :param sheet: 目标子表名称
        :param rename_from: 重命名来源子表名称
        :param clear_data: 是否清空既有数据区内容
        :return:
        """
        try:
            await self.init_sheet(config=config, sheet=sheet, rename_from=rename_from, clear_data=clear_data)
        except Exception as exc:
            log.error(f'[飞书导出] 子表初始化失败 {sheet}: {exc!s}')
            return {'sheet': sheet, 'status': 'failed', 'error': str(exc)}
        return {'sheet': sheet, 'status': 'ok'}

    async def init_all(self, config: FeishuSheetConfig, *, clear_data: bool = False) -> dict[str, Any]:
        """
        初始化全部目标子表

        :param config: 导出配置
        :param clear_data: 是否清空既有数据区内容
        :return:
        """
        rename_map = {'笔记部分': '笔记专栏', '刷题部分': '真题获取', '干货部分': '干货汇总'}
        results = [
            await self._init_one(config=config, sheet=sheet, rename_from=rename_map.get(sheet), clear_data=clear_data)
            for sheet in self.sheet_type_map(config)
        ]
        return {'config_id': config.id, 'sheets': results}

    # ---------- 同步 ----------

    async def sync_sheet(
        self, *, db: AsyncSession, config: FeishuSheetConfig, sheet: str, resource_types: list[str]
    ) -> dict[str, Any]:
        """
        同步单个子表

        规则（表格为对外公开，只呈现当前有效的资源）：
        - 表格中已有该资源：与表格现状逐列比对，**只有真正变化**时才更新那一行；
          状态列按当前是否可见改写为「有效 / 失效」
        - 表格中没有、且当前可见：插入新行
        - 表格中没有、且当前不可见：跳过，不插入

        即资源失效时保留原行、只把状态列改为失效，不删除行，以免丢失来源列的人工痕迹。
        表格现状始终是唯一真值来源：每轮仍会完整读一次数据区（一次请求），
        因此表格被人工改动过的地方也会在下一轮按数据库状态修正回来。

        :param db: 数据库会话
        :param config: 导出配置
        :param sheet: 子表名称
        :param resource_types: 归属该子表的资源类型
        :return:
        """
        # 一次读取同时拿到「行号索引」与「数据末行」，供后面的装饰复用，避免同一轮读两遍表
        state, last_row = await self._scan_sheet(config=config, sheet=sheet)
        category_ids = await self._load_app_category_ids(config=config, db=db)
        resources = await self._load_resources(
            db=db,
            resource_types=resource_types,
            category_ids=category_ids,
            known_ids=set(state),
        )
        category_names = await self._load_category_names(config=config, db=db)

        valid_options = set(config.category_options or [])
        inserts: list[list[Any]] = []
        updates: list[dict[str, Any]] = []
        visible_total = 0
        offline = 0

        for resource in resources:
            category_name = category_names.get(resource.category_id, '')
            if category_name and category_name not in valid_options:
                log.warning(f'[飞书导出] 分类不在下拉选项中，将按原值写入: {category_name}')

            visible = self.is_public_visible(resource)
            status_label = STATUS_LABELS['enabled'] if visible else STATUS_LABELS['disabled']
            if visible:
                visible_total += 1

            existing = state.get(resource.id)
            if existing:
                # 来源只在首次插入时确定，后续同步沿用表格中的旧值
                source = str(existing['source'] or '').strip() or self._random_source(config=config, sheet=sheet)
                row = self._build_row(resource, category_name, source, status_label)
                if not visible:
                    offline += 1
                # 只写真正变化的行：与表格现状一致的行直接跳过，不再每轮整表重写。
                # 判等偏保守（见 _normalize_cell），拿不准时按「变了」处理，宁可多写一次。
                if self._row_changed(existing['values'], row):
                    row_ref = f'A{existing["row"]}:{LAST_COLUMN}{existing["row"]}'
                    updates.append({'cell_range': row_ref, 'values': [row]})
                continue

            if visible:
                inserts.append(
                    self._build_row(
                        resource, category_name, self._random_source(config=config, sheet=sheet), status_label
                    )
                )

        # 1) 先更新已有行，此时行号尚未被插入扰动
        for start in range(0, len(updates), UPDATE_CHUNK_SIZE):
            await feishu_sheet_service.batch_write(
                workbook=config.sheet_url,
                sheet=sheet,
                ranges=updates[start : start + UPDATE_CHUNK_SIZE],
            )

        # 2) 再把新增行插入到标题行下方（最新在最上）
        if inserts:
            await feishu_sheet_service.insert_rows(
                workbook=config.sheet_url,
                sheet=sheet,
                position=HEADER_ROWS + 1,
                count=len(inserts),
                inherit_style='after',
            )
            await feishu_sheet_service.write(
                workbook=config.sheet_url,
                sheet=sheet,
                cell_range=f'A{HEADER_ROWS + 1}:{LAST_COLUMN}{HEADER_ROWS + len(inserts)}',
                values=inserts,
            )

        # 表头 / 样式 / 下拉按需重建（`ensure_decorated` 内部先比签名与覆盖范围，
        # 命中缓存则一次请求都不发）。放在这里而不是 `if inserts or updates` 里，
        # 是为了让「数据被清空后」也能自动补回表头与下拉。
        # 插入会让数据区整体下移，总行数增加 len(inserts)，故复用本轮的末行即可。
        await self.ensure_decorated(
            config=config,
            sheet=sheet,
            data_rows=max(last_row - HEADER_ROWS, 0) + len(inserts),
        )

        result = {
            'sheet': sheet,
            'resource_types': resource_types,
            'total': len(resources),
            'visible': visible_total,
            'inserted': len(inserts),
            'updated': len(updates),
            'offline': offline,
        }
        log.info(f'[飞书导出] 子表同步完成 {result}')
        return result

    async def _sync_one(
        self,
        *,
        db: AsyncSession,
        config: FeishuSheetConfig,
        sheet: str,
        resource_types: list[str],
    ) -> dict[str, Any]:
        """
        同步单个子表并捕获异常

        :param db: 数据库会话
        :param config: 导出配置
        :param sheet: 子表名称
        :param resource_types: 归属该子表的资源类型
        :return:
        """
        try:
            return await self.sync_sheet(db=db, config=config, sheet=sheet, resource_types=resource_types)
        except Exception as exc:
            log.error(f'[飞书导出] 子表同步失败 {sheet}: {exc!s}')
            return {'sheet': sheet, 'status': 'failed', 'error': str(exc)}

    async def sync_all(self, config: FeishuSheetConfig) -> dict[str, Any]:
        """
        同步一份配置下的全部子表

        :param config: 导出配置
        :return:
        """
        results = []
        async with async_db_session() as db:
            for sheet, resource_types in self.sheet_type_map(config).items():
                results.append(await self._sync_one(db=db, config=config, sheet=sheet, resource_types=resource_types))

        total_inserted = sum(int(item.get('inserted') or 0) for item in results)
        total_updated = sum(int(item.get('updated') or 0) for item in results)
        return {
            'config_id': config.id,
            'config_name': config.name,
            'sheets': results,
            'total_inserted': total_inserted,
            'total_updated': total_updated,
        }

    async def sync_enabled_configs(self) -> dict[str, Any]:
        """
        同步全部启用的配置（供 Celery 定时任务调用）

        :return:
        """
        async with async_db_session() as db:
            stmt = await feishu_sheet_config_dao.get_select(is_enabled=True)
            config_ids = [config.id for config in (await db.execute(stmt)).scalars().all()]

        results: list[dict[str, Any]] = []
        for config_id in config_ids:
            async with async_db_session() as db:
                config = await self.get_config(db, pk=config_id)
                try:
                    results.append(await self.sync_all(config))
                except Exception as exc:
                    log.error(f'[飞书导出] 配置「{config.name}」同步失败: {exc!s}')
                    results.append({'config_id': config.id, 'config_name': config.name, 'error': str(exc)})

        return {
            'configs': results,
            'total_inserted': sum(int(item.get('total_inserted') or 0) for item in results),
            'total_updated': sum(int(item.get('total_updated') or 0) for item in results),
        }


mydrive_feishu_export_service = MyDriveFeishuExportService()
