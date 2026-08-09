#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Integer, Select, and_, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import CommonStatus, GrantMode, ResourceType
from backend.app.access.model.rule import ResourceRule

# 层级展开跳数上限, 防御脏数据成环
_HIERARCHY_MAX_DEPTH = 10


@dataclass(frozen=True)
class RuleScope:
    """规则归属范围: 一组同类型资源, 以及命中它们是否要求规则可继承"""

    resource_type: str
    resource_ids: tuple[int, ...]
    require_inherit: bool


class CRUDResourceRule(CRUDPlus[ResourceRule]):
    """资源规则 CRUD"""

    @staticmethod
    async def _get_v1_bank_distances(db: AsyncSession, *, resource_id: int) -> dict[int, int]:
        """
        获取 V1 题库自身及父级题库的层级距离

        :param db: 数据库会话
        :param resource_id: 题库 ID
        :return: 题库 ID -> 距离(自身为 0, 逐级父级递增)
        """
        from backend.app.question_bank.model import QuestionBank

        chain = (
            select(
                QuestionBank.id.label('node_id'),
                QuestionBank.parent_id.label('parent_id'),
                cast(literal(0), Integer).label('depth'),
            )
            .where(QuestionBank.id == resource_id)
            .cte('v1_bank_chain', recursive=True)
        )
        parent = aliased(QuestionBank)
        chain = chain.union_all(
            select(
                parent.id.label('node_id'),
                parent.parent_id.label('parent_id'),
                (chain.c.depth + 1).label('depth'),
            ).where(
                parent.id == chain.c.parent_id,
                chain.c.depth < _HIERARCHY_MAX_DEPTH,
            )
        )

        rows = (await db.execute(select(chain.c.node_id, chain.c.depth))).all()
        return CRUDResourceRule._collapse_distances(rows)

    @staticmethod
    async def _get_collection_distances_for_bank(db: AsyncSession, *, bank_id: int) -> dict[int, int]:
        """
        获取 V2 题库所属合集及其祖先合集的层级距离

        题库可同时挂载到多个合集, 同一合集经不同路径可达时取最短距离。

        :param db: 数据库会话
        :param bank_id: 题库稳定身份 ID
        :return: 合集 ID -> 距离(直接挂载合集为 1, 逐级父合集递增)
        """
        from backend.app.question_bank_v2.model.catalog import QbCollection, QbCollectionBank

        # 合集被归档不应让付费题库失去门槛, 因此只过滤软删除
        mounted = (
            select(
                QbCollection.id.label('node_id'),
                QbCollection.parent_id.label('parent_id'),
                cast(literal(1), Integer).label('depth'),
            )
            .join(QbCollectionBank, QbCollectionBank.collection_id == QbCollection.id)
            .where(
                QbCollectionBank.bank_id == bank_id,
                QbCollectionBank.deleted == 0,
                QbCollectionBank.is_active.is_(True),
                QbCollection.deleted == 0,
            )
            .cte('v2_collection_chain', recursive=True)
        )
        parent = aliased(QbCollection)
        mounted = mounted.union_all(
            select(
                parent.id.label('node_id'),
                parent.parent_id.label('parent_id'),
                (mounted.c.depth + 1).label('depth'),
            ).where(
                parent.id == mounted.c.parent_id,
                parent.deleted == 0,
                mounted.c.depth < _HIERARCHY_MAX_DEPTH,
            )
        )

        rows = (
            await db.execute(select(mounted.c.node_id, func.min(mounted.c.depth)).group_by(mounted.c.node_id))
        ).all()
        return CRUDResourceRule._collapse_distances(rows)

    @staticmethod
    async def _get_collection_ancestor_distances(db: AsyncSession, *, collection_id: int) -> dict[int, int]:
        """
        获取 V2 合集自身及其祖先合集的层级距离

        :param db: 数据库会话
        :param collection_id: 合集 ID
        :return: 合集 ID -> 距离(自身为 0, 逐级父合集递增)
        """
        from backend.app.question_bank_v2.model.catalog import QbCollection

        chain = (
            select(
                QbCollection.id.label('node_id'),
                QbCollection.parent_id.label('parent_id'),
                cast(literal(0), Integer).label('depth'),
            )
            .where(QbCollection.id == collection_id, QbCollection.deleted == 0)
            .cte('v2_collection_ancestors', recursive=True)
        )
        parent = aliased(QbCollection)
        chain = chain.union_all(
            select(
                parent.id.label('node_id'),
                parent.parent_id.label('parent_id'),
                (chain.c.depth + 1).label('depth'),
            ).where(
                parent.id == chain.c.parent_id,
                parent.deleted == 0,
                chain.c.depth < _HIERARCHY_MAX_DEPTH,
            )
        )

        rows = (await db.execute(select(chain.c.node_id, chain.c.depth))).all()
        return CRUDResourceRule._collapse_distances(rows)

    @staticmethod
    def _collapse_distances(rows: Sequence[tuple[int, int]]) -> dict[int, int]:
        """
        将层级展开结果收敛为最短距离映射

        :param rows: (节点 ID, 距离) 序列
        :return:
        """
        distances: dict[int, int] = {}
        for node_id, depth in rows:
            node_id = int(node_id)
            depth = int(depth)
            if node_id not in distances or depth < distances[node_id]:
                distances[node_id] = depth
        return distances

    @staticmethod
    def build_qbank_scopes(
        *,
        resource_id: int,
        v1_distances: dict[int, int],
        collection_distances: dict[int, int],
    ) -> list[RuleScope]:
        """
        计算题库应当纳入哪些资源的规则

        :param resource_id: 题库 ID
        :param v1_distances: V1 父题库链距离
        :param collection_distances: V2 所属合集链距离
        :return:
        """
        # 自身规则无条件生效, 即便题库只存在于某一个版本的表中
        scopes = [
            RuleScope(
                resource_type=ResourceType.QBANK,
                resource_ids=(resource_id,),
                require_inherit=False,
            )
        ]

        inherited_bank_ids = tuple(sorted(bid for bid, depth in v1_distances.items() if depth > 0))
        if inherited_bank_ids:
            scopes.append(
                RuleScope(
                    resource_type=ResourceType.QBANK,
                    resource_ids=inherited_bank_ids,
                    require_inherit=True,
                )
            )

        collection_ids = tuple(sorted(collection_distances))
        if collection_ids:
            scopes.append(
                RuleScope(
                    resource_type=ResourceType.QBANK_COLLECTION,
                    resource_ids=collection_ids,
                    require_inherit=True,
                )
            )
        return scopes

    @staticmethod
    def build_collection_scopes(*, resource_id: int, distances: dict[int, int]) -> list[RuleScope]:
        """
        计算合集应当纳入哪些资源的规则

        :param resource_id: 合集 ID
        :param distances: 合集祖先链距离
        :return:
        """
        scopes = [
            RuleScope(
                resource_type=ResourceType.QBANK_COLLECTION,
                resource_ids=(resource_id,),
                require_inherit=False,
            )
        ]

        ancestor_ids = tuple(sorted(cid for cid, depth in distances.items() if depth > 0))
        if ancestor_ids:
            scopes.append(
                RuleScope(
                    resource_type=ResourceType.QBANK_COLLECTION,
                    resource_ids=ancestor_ids,
                    require_inherit=True,
                )
            )
        return scopes

    async def resolve_for_resource(
        self,
        db: AsyncSession,
        *,
        resource_type: str,
        resource_id: int,
        ts: datetime,
    ) -> Sequence[ResourceRule]:
        """
        解析资源在指定时刻的所有生效规则

        :param db: 数据库会话
        :param resource_type: 资源类型
        :param resource_id: 资源 ID
        :param ts: 时间点
        :return:
        """
        if resource_type == ResourceType.QBANK:
            return await self._resolve_qbank_resource(db, resource_id=resource_id, ts=ts)

        if resource_type == ResourceType.QBANK_COLLECTION:
            return await self._resolve_qbank_collection_resource(db, resource_id=resource_id, ts=ts)

        stmt = (
            select(self.model)
            .where(
                self.model.resource_type == resource_type,
                self.model.resource_id == resource_id,
                self.model.status == CommonStatus.ACTIVE,
                or_(
                    self.model.valid_period.is_(None),
                    self.model.valid_period.contains(ts),
                ),
            )
            .order_by(self.model.priority.desc(), self.model.id.asc())
        )
        return (await db.execute(stmt)).scalars().all()

    async def _resolve_qbank_resource(
        self,
        db: AsyncSession,
        *,
        resource_id: int,
        ts: datetime,
    ) -> Sequence[ResourceRule]:
        """
        解析题库自身规则, 以及 V1 父题库 / V2 所属合集的可继承规则

        题库自身的规则始终生效; 上层(V1 父题库、V2 合集及其祖先)的规则只在
        inherit_to_children=True 时向下穿透。两者合并后统一交给决策引擎,
        由责任链决定放行与否 —— 因此题库自身的限免规则可以覆盖合集的付费规则。

        :param db: 数据库会话
        :param resource_id: 题库 ID
        :param ts: 时间点
        :return:
        """
        # AsyncSession 不支持并发操作, 两次层级展开必须顺序执行
        v1_distances = await self._get_v1_bank_distances(db, resource_id=resource_id)
        collection_distances = await self._get_collection_distances_for_bank(db, bank_id=resource_id)
        scopes = self.build_qbank_scopes(
            resource_id=resource_id,
            v1_distances=v1_distances,
            collection_distances=collection_distances,
        )
        return await self._fetch_rules(db, scopes=scopes, ts=ts)

    async def _resolve_qbank_collection_resource(
        self,
        db: AsyncSession,
        *,
        resource_id: int,
        ts: datetime,
    ) -> Sequence[ResourceRule]:
        """
        解析合集自身及其祖先合集的可继承规则

        :param db: 数据库会话
        :param resource_id: 合集 ID
        :param ts: 时间点
        :return:
        """
        distances = await self._get_collection_ancestor_distances(db, collection_id=resource_id)
        scopes = self.build_collection_scopes(resource_id=resource_id, distances=distances)
        return await self._fetch_rules(db, scopes=scopes, ts=ts)

    async def _fetch_rules(
        self,
        db: AsyncSession,
        *,
        scopes: Sequence[RuleScope],
        ts: datetime,
    ) -> Sequence[ResourceRule]:
        """
        按给定归属范围拉取当前生效的规则

        :param db: 数据库会话
        :param scopes: 规则归属范围
        :param ts: 时间点
        :return:
        """
        clauses = []
        for scope in scopes:
            conditions = [
                self.model.resource_type == scope.resource_type,
                self.model.resource_id.in_(scope.resource_ids),
            ]
            if scope.require_inherit:
                conditions.append(self.model.inherit_to_children.is_(True))
            clauses.append(and_(*conditions))

        stmt = (
            select(self.model)
            .where(
                or_(*clauses),
                self.model.status == CommonStatus.ACTIVE,
                or_(
                    self.model.valid_period.is_(None),
                    self.model.valid_period.contains(ts),
                ),
            )
            .order_by(self.model.priority.desc(), self.model.id.asc())
        )
        return (await db.execute(stmt)).scalars().all()

    async def get_select(
        self,
        *,
        resource_type: str | None = None,
        resource_id: int | None = None,
        entitlement_code: str | None = None,
        grant_mode: GrantMode | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        分页查询语句

        :param resource_type: 资源类型
        :param resource_id: 资源 ID
        :param entitlement_code: 权益编码
        :param grant_mode: 授权模式
        :param status: 状态
        :return:
        """
        filters: dict[str, object] = {}
        if resource_type is not None:
            filters['resource_type__eq'] = resource_type
        if resource_id is not None:
            filters['resource_id__eq'] = resource_id
        if entitlement_code is not None:
            filters['entitlement_code__eq'] = entitlement_code
        if grant_mode is not None:
            filters['grant_mode__eq'] = grant_mode
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('priority', 'desc', **filters)


resource_rule_dao: CRUDResourceRule = CRUDResourceRule(ResourceRule)
