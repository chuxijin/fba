#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

import sqlalchemy as sa

from sqlalchemy import cast, func, literal_column, select
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.admin.model.category import Category
from backend.app.question_bank.model.practice import PracticeRecord
from backend.app.question_bank.model.question import Question
from backend.app.question_bank.schema.knowledge_point import (
    GetKpDetailResponse,
    GetKpProgressResponse,
    KpChildNode,
    KpProgressNode,
)
from backend.common.exception import errors


class KnowledgePointService:
    """知识点详情服务"""

    @staticmethod
    async def resolve_codes_to_names(
        db: AsyncSession,
        codes: list[str],
    ) -> dict[str, str]:
        """
        批量解析知识点分类编码为名称

        :param db: 数据库会话
        :param codes: 分类编码列表
        :return: {code: name}
        """
        if not codes:
            return {}
        stmt = select(Category.code, Category.name).where(
            Category.code.in_(codes),
            Category.status.is_(True),
        )
        rows = (await db.execute(stmt)).all()
        return {row[0]: row[1] for row in rows if row[0]}

    @staticmethod
    async def _collect_leaf_names(
        db: AsyncSession,
        category_id: int,
    ) -> tuple[dict[str, Any], list[str], list[str]]:
        """
        获取分类节点及其所有叶子知识点的 code 和 name

        :param db: 数据库会话
        :param category_id: 分类 ID
        :return: (分类节点字典, 叶子编码列表, 叶子名称列表)
        """
        category = await category_dao.get(db, category_id)
        if not category:
            raise errors.NotFoundError(msg='知识点分类不存在')

        child_ids = await category_dao.get_all_children_ids(db, category_id)

        # 获取所有相关节点
        stmt = sa.select(category_dao.model).where(category_dao.model.id.in_(child_ids))
        result = await db.execute(stmt)
        all_nodes = list(result.scalars().all())

        leaf_codes: list[str] = []
        leaf_names: list[str] = []
        for c in all_nodes:
            has_child = any(cc.parent_id == c.id for cc in all_nodes)
            # 叶子节点且不能是当前分类本身
            if not has_child and c.id != category_id:
                if c.code:
                    leaf_codes.append(c.code)
                leaf_names.append(c.name)

        return {
            'id': category.id,
            'name': category.name,
            'children': all_nodes,
        }, leaf_codes, leaf_names

    @staticmethod
    async def _batch_count_by_kp_codes(
        db: AsyncSession,
        kp_codes: list[str],
    ) -> dict[str, int]:
        """
        一次性查询所有知识点编码对应的题目数量

        :param db: 数据库会话
        :param kp_codes: 知识点编码列表
        :return: {知识点编码: 题目数量}
        """
        if not kp_codes:
            return {}

        kp_json = cast(Question.knowledge_point, PGJSONB)
        kp_array = sa.case(
            (func.jsonb_typeof(kp_json) == 'array', kp_json),
            else_=func.jsonb_build_array(kp_json),
        )
        kp_elem = func.jsonb_array_elements(kp_array).table_valued('value')

        # 提取知识点值：兼容纯字符串 / dict 结构
        kp_value_expr = func.coalesce(
            kp_elem.c.value.op('->>')(literal_column("'code'")),
            kp_elem.c.value.op('->>')(literal_column("'name'")),
            kp_elem.c.value.op('->>')(literal_column("'label'")),
            kp_elem.c.value.op('->>')(literal_column("'title'")),
            kp_elem.c.value.op('#>>')(literal_column("'{}'")),
        ).label('kp_value')

        stmt = (
            select(kp_value_expr, func.count(func.distinct(Question.id)).label('cnt'))
            .select_from(Question)
            .join(kp_elem, literal_column('true'))
            .where(
                Question.knowledge_point.isnot(None),
                Question.content_status == 10,
            )
            .group_by(kp_value_expr)
            .having(kp_value_expr.in_(kp_codes))
        )
        rows = (await db.execute(stmt)).all()
        return {str(row[0]): int(row[1]) for row in rows if row[0]}

    @staticmethod
    async def _batch_progress_by_kp_codes(
        db: AsyncSession,
        user_id: int,
        kp_codes: list[str],
    ) -> dict[str, dict[str, int]]:
        """
        一次性查询用户在各知识点下的做题进度

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param kp_codes: 知识点编码列表
        :return: {知识点编码: {answer_count, correct_count}}
        """
        if not kp_codes:
            return {}

        kp_json = cast(Question.knowledge_point, PGJSONB)
        kp_array = sa.case(
            (func.jsonb_typeof(kp_json) == 'array', kp_json),
            else_=func.jsonb_build_array(kp_json),
        )
        kp_elem = func.jsonb_array_elements(kp_array).table_valued('value')

        kp_value_expr = func.coalesce(
            kp_elem.c.value.op('->>')(literal_column("'code'")),
            kp_elem.c.value.op('->>')(literal_column("'name'")),
            kp_elem.c.value.op('->>')(literal_column("'label'")),
            kp_elem.c.value.op('->>')(literal_column("'title'")),
            kp_elem.c.value.op('#>>')(literal_column("'{}'")),
        ).label('kp_value')

        stmt = (
            select(
                kp_value_expr,
                func.count(func.distinct(PracticeRecord.question_id)).label('answer_count'),
                func.sum(sa.case((PracticeRecord.is_correct.is_(True), 1), else_=0)).label('correct_count'),
            )
            .select_from(PracticeRecord)
            .join(Question, PracticeRecord.question_id == Question.id)
            .join(kp_elem, literal_column('true'))
            .where(
                PracticeRecord.user_id == user_id,
                PracticeRecord.user_answer.isnot(None),
                Question.knowledge_point.isnot(None),
            )
            .group_by(kp_value_expr)
            .having(kp_value_expr.in_(kp_codes))
        )
        rows = (await db.execute(stmt)).all()

        result: dict[str, dict[str, int]] = {}
        for row in rows:
            if row[0]:
                result[str(row[0])] = {
                    'answer_count': int(row[1] or 0),
                    'correct_count': int(row[2] or 0),
                }
        return result

    @staticmethod
    def _build_kp_tree(
        children: list,
        count_map: dict[str, int],
        parent_id: int,
    ) -> list[KpChildNode]:
        """
        将分类子节点构建为知识点树并回填题量

        :param children: 所有子分类列表
        :param count_map: 知识点编码→题量映射
        :param parent_id: 父分类 ID
        :return: 知识点子节点列表
        """
        nodes: list[KpChildNode] = []
        direct_children = [c for c in children if c.parent_id == parent_id]
        direct_children.sort(key=lambda c: getattr(c, 'sort_order', 0) or 0)

        for child in direct_children:
            sub_nodes = KnowledgePointService._build_kp_tree(children, count_map, child.id)
            if sub_nodes:
                child_count = sum(n.question_count for n in sub_nodes)
            else:
                # 叶子节点：优先用 code 匹配，兼容无 code 的旧数据
                child_code = getattr(child, 'code', None)
                child_count = count_map.get(child_code, 0) if child_code else count_map.get(child.name, 0)

            nodes.append(KpChildNode(
                id=child.id,
                name=child.name,
                question_count=child_count,
                children=sub_nodes,
            ))

        return nodes

    @staticmethod
    async def get_detail(*, db: AsyncSession, category_id: int) -> GetKpDetailResponse:
        """
        获取知识点详情（含子知识点树和题量统计）

        :param db: 数据库会话
        :param category_id: 分类 ID
        :return:
        """
        info, leaf_codes, _leaf_names = await KnowledgePointService._collect_leaf_names(db, category_id)
        count_map = await KnowledgePointService._batch_count_by_kp_codes(db, leaf_codes)

        kp_tree = KnowledgePointService._build_kp_tree(
            info['children'], count_map, category_id,
        )
        total = sum(n.question_count for n in kp_tree)

        return GetKpDetailResponse(
            id=info['id'],
            name=info['name'],
            total_question_count=total,
            children=kp_tree,
        )

    @staticmethod
    async def get_progress(
        *,
        db: AsyncSession,
        category_id: int,
        user_id: int,
    ) -> GetKpProgressResponse:
        """
        获取用户在各知识点下的做题进度

        :param db: 数据库会话
        :param category_id: 分类 ID
        :param user_id: 用户 ID
        :return:
        """
        info, leaf_codes, leaf_names = await KnowledgePointService._collect_leaf_names(db, category_id)
        count_map = await KnowledgePointService._batch_count_by_kp_codes(db, leaf_codes)
        progress_map = await KnowledgePointService._batch_progress_by_kp_codes(db, user_id, leaf_codes)

        items: list[KpProgressNode] = []
        total_q = 0
        total_a = 0
        total_c = 0

        for code, name in zip(leaf_codes, leaf_names):
            q_count = count_map.get(code, 0)
            prog = progress_map.get(code, {})
            a_count = prog.get('answer_count', 0)
            c_count = prog.get('correct_count', 0)

            total_q += q_count
            total_a += a_count
            total_c += c_count

            items.append(KpProgressNode(
                name=name,
                question_count=q_count,
                answer_count=a_count,
                correct_count=c_count,
                correct_ratio=round(c_count / a_count * 100, 1) if a_count > 0 else 0,
            ))

        return GetKpProgressResponse(
            id=info['id'],
            name=info['name'],
            total_question_count=total_q,
            total_answer_count=total_a,
            total_correct_count=total_c,
            items=items,
        )


knowledge_point_service: KnowledgePointService = KnowledgePointService()
