#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mydrive.crud.crud_space import mydrive_space_dao
from backend.app.mydrive.crud.crud_sync import (
    mydrive_sync_config_dao,
    mydrive_sync_rule_dao,
    mydrive_sync_rule_set_dao,
    mydrive_sync_task_dao,
    mydrive_sync_task_item_dao,
)
from backend.app.mydrive.model.sync import MyDriveSyncConfig, MyDriveSyncRuleSet, MyDriveSyncTask
from backend.app.mydrive.schema.sync import (
    CreateMyDriveSyncConfigParam,
    CreateMyDriveSyncRuleSetParam,
    UpdateMyDriveSyncConfigParam,
    UpdateMyDriveSyncRuleSetParam,
)
from backend.app.mydrive.service.sync.policy import validate_sync_spaces
from backend.app.mydrive.service.sync.rules import SyncRule, validate_rules
from backend.common.exception import errors


class MyDriveSyncService:
    """文件同步配置服务"""

    @staticmethod
    async def get_rule_set(db: AsyncSession, *, pk: int, owner_id: int) -> dict[str, Any]:
        """
        获取同步规则集详情。

        :param db: 数据库会话
        :param pk: 规则集 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        rule_set = await mydrive_sync_rule_set_dao.get(db, pk, owner_id)
        if rule_set is None:
            raise errors.NotFoundError(msg='同步规则集不存在')
        return await MyDriveSyncService._serialize_rule_set(db, rule_set)

    @staticmethod
    async def get_rule_set_select(owner_id: int):
        """获取同步规则集查询语句。"""
        return await mydrive_sync_rule_set_dao.get_select(owner_id)

    @staticmethod
    async def create_rule_set(
        db: AsyncSession,
        *,
        owner_id: int,
        obj: CreateMyDriveSyncRuleSetParam,
    ) -> dict[str, Any]:
        """
        创建同步规则集。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param obj: 创建参数
        :return:
        """
        await MyDriveSyncService._validate_rule_set_name(db, owner_id, obj.name)
        rule_values = MyDriveSyncService._get_rule_values(obj.rules)
        rule_set = MyDriveSyncRuleSet(owner_id=owner_id, name=obj.name, description=obj.description)
        db.add(rule_set)
        await db.flush()
        if rule_values:
            await mydrive_sync_rule_dao.replace(db, rule_set.id, rule_values)
        return await MyDriveSyncService._serialize_rule_set(db, rule_set)

    @staticmethod
    async def update_rule_set(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        obj: UpdateMyDriveSyncRuleSetParam,
    ) -> None:
        """
        更新同步规则集。

        :param db: 数据库会话
        :param pk: 规则集 ID
        :param owner_id: 所属用户 ID
        :param obj: 更新参数
        :return:
        """
        rule_set = await mydrive_sync_rule_set_dao.get(db, pk, owner_id)
        if rule_set is None:
            raise errors.NotFoundError(msg='同步规则集不存在')
        if obj.name is not None and obj.name != rule_set.name:
            await MyDriveSyncService._validate_rule_set_name(db, owner_id, obj.name)
        values = obj.model_dump(exclude_unset=True, exclude={'rules'})
        if values:
            await mydrive_sync_rule_set_dao.update_model(db, rule_set.id, values)
        if obj.rules is not None:
            await mydrive_sync_rule_dao.replace(db, rule_set.id, MyDriveSyncService._get_rule_values(obj.rules))

    @staticmethod
    async def delete_rule_set(db: AsyncSession, *, pk: int, owner_id: int) -> None:
        """
        删除同步规则集。

        :param db: 数据库会话
        :param pk: 规则集 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        rule_set = await mydrive_sync_rule_set_dao.get(db, pk, owner_id)
        if rule_set is None:
            raise errors.NotFoundError(msg='同步规则集不存在')
        await mydrive_sync_rule_set_dao.delete_model(db, rule_set.id)

    @staticmethod
    async def get_config(db: AsyncSession, *, pk: int, owner_id: int) -> MyDriveSyncConfig:
        """
        获取同步配置。

        :param db: 数据库会话
        :param pk: 同步配置 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        config = await mydrive_sync_config_dao.get(db, pk, owner_id)
        if config is None:
            raise errors.NotFoundError(msg='同步配置不存在')
        return config

    @staticmethod
    async def get_config_select(owner_id: int):
        """获取同步配置查询语句。"""
        return await mydrive_sync_config_dao.get_select(owner_id)

    @staticmethod
    async def create_config(
        db: AsyncSession,
        *,
        owner_id: int,
        obj: CreateMyDriveSyncConfigParam,
    ) -> MyDriveSyncConfig:
        """
        创建同步配置。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param obj: 创建参数
        :return:
        """
        await MyDriveSyncService._validate_config_references(
            db,
            owner_id,
            obj.source_space_id,
            obj.target_space_id,
            obj.rule_set_id,
            obj.sync_method,
            obj.source_path,
        )
        config = MyDriveSyncConfig(owner_id=owner_id, **obj.model_dump())
        db.add(config)
        await db.flush()
        return config

    @staticmethod
    async def update_config(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        obj: UpdateMyDriveSyncConfigParam,
    ) -> None:
        """
        更新同步配置。

        :param db: 数据库会话
        :param pk: 同步配置 ID
        :param owner_id: 所属用户 ID
        :param obj: 更新参数
        :return:
        """
        config = await MyDriveSyncService.get_config(db, pk=pk, owner_id=owner_id)
        values = obj.model_dump(exclude_unset=True)
        source_space_id = values.get('source_space_id', config.source_space_id)
        target_space_id = values.get('target_space_id', config.target_space_id)
        rule_set_id = values.get('rule_set_id', config.rule_set_id)
        sync_method = values.get('sync_method', config.sync_method)
        source_path = values.get('source_path', config.source_path)
        await MyDriveSyncService._validate_config_references(
            db,
            owner_id,
            source_space_id,
            target_space_id,
            rule_set_id,
            sync_method,
            source_path,
        )
        if values:
            await mydrive_sync_config_dao.update_model(db, config.id, values)

    @staticmethod
    async def delete_config(db: AsyncSession, *, pk: int, owner_id: int) -> None:
        """
        删除同步配置。

        :param db: 数据库会话
        :param pk: 同步配置 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        config = await MyDriveSyncService.get_config(db, pk=pk, owner_id=owner_id)
        await mydrive_sync_config_dao.delete_model(db, config.id)

    @staticmethod
    async def create_task(db: AsyncSession, *, config_id: int, owner_id: int) -> MyDriveSyncTask:
        """
        创建待执行的同步任务。

        :param db: 数据库会话
        :param config_id: 同步配置 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        config = await MyDriveSyncService.get_config(db, pk=config_id, owner_id=owner_id)
        if not config.is_enabled:
            raise errors.ForbiddenError(msg='同步配置已停用')
        if config.end_time is not None and config.end_time <= datetime.now(config.end_time.tzinfo):
            raise errors.ForbiddenError(msg='同步配置已超过结束时间')
        if await mydrive_sync_task_dao.has_active_task(db, config.id):
            raise errors.ConflictError(msg='同步配置已有待执行或执行中的任务')
        task = MyDriveSyncTask(
            config_id=config.id,
            statistics={'planned': 0, 'completed': 0, 'failed': 0, 'skipped': 0},
        )
        db.add(task)
        await db.flush()
        return task

    @staticmethod
    async def get_task(db: AsyncSession, *, pk: int, owner_id: int) -> MyDriveSyncTask:
        """
        获取同步任务。

        :param db: 数据库会话
        :param pk: 同步任务 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        task = await mydrive_sync_task_dao.get(db, pk, owner_id)
        if task is None:
            raise errors.NotFoundError(msg='同步任务不存在')
        return task

    @staticmethod
    async def get_task_select(owner_id: int, config_id: int | None = None):
        """
        获取同步任务查询语句。

        :param owner_id: 所属用户 ID
        :param config_id: 同步配置 ID
        :return:
        """
        return await mydrive_sync_task_dao.get_select(owner_id, config_id)

    @staticmethod
    async def request_task_cancel(db: AsyncSession, *, pk: int, owner_id: int) -> None:
        """
        请求取消同步任务。

        :param db: 数据库会话
        :param pk: 同步任务 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        task = await MyDriveSyncService.get_task(db, pk=pk, owner_id=owner_id)
        if task.status not in {'pending', 'running'}:
            raise errors.ForbiddenError(msg='当前同步任务无法取消')
        await mydrive_sync_task_dao.update_model(db, task.id, {'cancel_requested': True})

    @staticmethod
    async def get_task_item_select(db: AsyncSession, *, task_id: int, owner_id: int):
        """
        获取同步任务项查询语句。

        :param db: 数据库会话
        :param task_id: 同步任务 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        await MyDriveSyncService.get_task(db, pk=task_id, owner_id=owner_id)
        return await mydrive_sync_task_item_dao.get_select(task_id)

    @staticmethod
    async def _serialize_rule_set(db: AsyncSession, rule_set: MyDriveSyncRuleSet) -> dict[str, Any]:
        """序列化同步规则集详情。"""
        return {
            'id': rule_set.id,
            'owner_id': rule_set.owner_id,
            'name': rule_set.name,
            'description': rule_set.description,
            'is_enabled': rule_set.is_enabled,
            'rules': await mydrive_sync_rule_dao.list_by_rule_set(db, rule_set.id),
            'created_time': rule_set.created_time,
            'updated_time': rule_set.updated_time,
        }

    @staticmethod
    def _get_rule_values(rules: list) -> list[dict[str, Any]]:
        """验证并转换规则列表。"""
        rule_values = [rule.model_dump() for rule in rules]
        if len({value['sort_order'] for value in rule_values}) != len(rule_values):
            raise errors.ForbiddenError(msg='同步规则执行顺序不能重复')
        try:
            validate_rules([MyDriveSyncService._get_sync_rule(value) for value in rule_values])
        except (ValueError, TypeError) as exc:
            raise errors.ForbiddenError(msg=f'同步规则无效: {exc}') from exc
        return rule_values

    @staticmethod
    def _get_sync_rule(value: dict[str, Any]) -> SyncRule:
        """转换为规则引擎对象。"""
        return SyncRule(
            rule_type=value['rule_type'],
            pattern=value['pattern'],
            replacement=value.get('replacement', ''),
            is_enabled=value.get('is_enabled', True),
        )

    @staticmethod
    async def _validate_rule_set_name(db: AsyncSession, owner_id: int, name: str) -> None:
        """验证同步规则集名称唯一。"""
        if await mydrive_sync_rule_set_dao.get_by_name(db, owner_id, name):
            raise errors.ConflictError(msg='同步规则集名称已存在')

    @staticmethod
    async def _validate_config_references(
        db: AsyncSession,
        owner_id: int,
        source_space_id: int,
        target_space_id: int,
        rule_set_id: int | None,
        sync_method: str,
        source_path: str,
    ) -> None:
        """验证同步配置关联的空间和规则集。"""
        if sync_method not in {'incremental', 'full', 'overwrite'}:
            raise errors.ForbiddenError(msg='同步模式仅支持 incremental、full、overwrite')
        source = await mydrive_space_dao.get(db, source_space_id, owner_id)
        target = await mydrive_space_dao.get(db, target_space_id, owner_id)
        if source is None or target is None:
            raise errors.NotFoundError(msg='同步来源或目标文件空间不存在')
        validate_sync_spaces(source, target)
        if source.space_type == 'share_link' and source_path.startswith('/sharelink'):
            raise errors.ForbiddenError(msg='独立分享链接空间请从 / 或挂载内子目录选择来源路径')
        if rule_set_id is not None and await mydrive_sync_rule_set_dao.get(db, rule_set_id, owner_id) is None:
            raise errors.NotFoundError(msg='同步规则集不存在')


mydrive_sync_service: MyDriveSyncService = MyDriveSyncService()
