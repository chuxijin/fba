#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_user_bank_progress import user_bank_progress_dao
from backend.app.question_bank.crud.crud_question import question_dao
from backend.app.question_bank.model import Question, QuestionAnalysis
from backend.app.question_bank.schema.practice import (
    GetPracticeHomeNode,
    GetPracticeHomeResponse,
    PracticeHomeFilter,
)
from backend.app.question_bank.service.bank_mount_service import bank_mount_service
from backend.app.question_bank.service.category_filter_service import category_filter_service
from backend.app.question_bank.service.knowledge_point_service import knowledge_point_service
from backend.app.question_bank.service.question_service import question_service
from backend.common.exception import errors


class PracticeService:
    """刷题服务类（只读）"""

    @staticmethod
    def _collect_home_node_ids(nodes: list[dict[str, Any]]) -> list[int]:
        """
        收集刷题首页节点 ID

        :param nodes: 内容树节点
        :return:
        """
        node_ids: list[int] = []
        for node in nodes:
            node_id = int(node['id'])
            node_ids.append(node_id)
            node_ids.extend(PracticeService._collect_home_node_ids(node.get('children') or []))

        return node_ids

    @staticmethod
    def _build_home_bank_nodes(
        nodes: list[dict[str, Any]],
        answer_count_map: dict[int, int],
    ) -> list[GetPracticeHomeNode]:
        """
        构造刷题首页题库节点

        :param nodes: 内容树节点
        :param answer_count_map: 作答数量映射
        :return:
        """
        result: list[GetPracticeHomeNode] = []
        for node in nodes:
            children = PracticeService._build_home_bank_nodes(node.get('children') or [], answer_count_map)
            count = sum(child.count for child in children)
            answer_count = sum(child.answerCount for child in children)
            if not children:
                node_id = int(node['id'])
                count = int(node.get('q_count_cache') or 0)
                answer_count = int(answer_count_map.get(node_id, 0))

            if count <= 0:
                continue

            result.append(GetPracticeHomeNode(
                id=int(node['id']),
                name=str(node.get('name') or ''),
                count=count,
                answerCount=answer_count,
                children=children or None,
            ))

        return result

    @staticmethod
    async def _build_bank_home_by_collection(
        *,
        db: AsyncSession,
        cat_id: int,
        tab_id: int,
        user_id: int | None,
    ) -> list[GetPracticeHomeNode]:
        """
        按题库合集构造首页内容

        :param db: 数据库会话
        :param cat_id: 题库目录分类 ID
        :param tab_id: 合集题库 ID
        :param user_id: 用户 ID
        :return:
        """
        bank = await bank_dao.get(db, tab_id)
        if bank is None or bank.status != 1:
            raise errors.NotFoundError(msg='题库合集不存在')
        if bank.bank_type != 3:
            raise errors.RequestError(msg='当前 Tab 不是题库合集')

        category_ids = await category_filter_service.get_product_catalog_category_ids(
            db=db,
            cat_id=cat_id,
        )
        if int(bank.cat_id) not in category_ids:
            raise errors.RequestError(msg='题库合集不属于当前题库目录')

        bank_rows = await bank_dao.get_home_mappings(db, cat_ids=[int(bank.cat_id)], status=1)
        tree_data = await bank_mount_service.get_mount_tree(
            db=db,
            bank_select=bank_rows,
            status=1,
            parent_id=tab_id,
        )
        if tree_data is None:
            tree_data = []

        answer_count_map: dict[int, int] = {}
        if user_id is not None:
            node_ids = PracticeService._collect_home_node_ids(tree_data)
            answer_count_map, _ = await user_bank_progress_dao.get_answer_correct_maps(
                db=db,
                user_id=user_id,
                bank_ids=node_ids,
            )

        return PracticeService._build_home_bank_nodes(tree_data, answer_count_map)

    @staticmethod
    def _keypoint_match_term(category: Any) -> str:
        """
        获取知识点匹配值

        :param category: 分类对象
        :return:
        """
        code = str(getattr(category, 'code', '') or '').strip()
        if code:
            return code
        return str(getattr(category, 'name', '') or '').strip()

    @staticmethod
    def _build_keypoint_home_node(
        *,
        category: Any,
        categories: list[Any],
        count_map: dict[str, int],
        progress_map: dict[str, dict[str, int]],
    ) -> GetPracticeHomeNode | None:
        """
        构造知识点首页节点

        :param category: 当前分类
        :param categories: 分类列表
        :param count_map: 题量映射
        :param progress_map: 进度映射
        :return:
        """
        children: list[GetPracticeHomeNode] = []
        direct_children = [item for item in categories if item.parent_id == category.id]
        direct_children.sort(key=lambda item: (int(getattr(item, 'sort_order', 0) or 0), int(item.id)))

        for child in direct_children:
            child_node = PracticeService._build_keypoint_home_node(
                category=child,
                categories=categories,
                count_map=count_map,
                progress_map=progress_map,
            )
            if child_node is not None:
                children.append(child_node)

        count = sum(child.count for child in children)
        answer_count = sum(child.answerCount for child in children)
        if not children:
            term = PracticeService._keypoint_match_term(category)
            count = int(count_map.get(term, 0))
            answer_count = int(progress_map.get(term, {}).get('answer_count', 0))

        if count <= 0:
            return None

        return GetPracticeHomeNode(
            id=int(category.id),
            name=str(category.name or ''),
            count=count,
            answerCount=answer_count,
            children=children or None,
        )

    @staticmethod
    async def _build_keypoint_home(
        *,
        db: AsyncSession,
        kp_cat_id: int,
        tab_id: int | None,
        user_id: int | None,
    ) -> list[GetPracticeHomeNode]:
        """
        按知识点分类构造首页内容

        :param db: 数据库会话
        :param kp_cat_id: 知识点分类 ID
        :param tab_id: 知识点分类 ID
        :param user_id: 用户 ID
        :return:
        """
        if tab_id is None:
            raise errors.RequestError(msg='请选择知识点 Tab')

        category = await category_dao.get(db, tab_id)
        if category is None or not category.status:
            raise errors.NotFoundError(msg='知识点分类不存在')
        if category.type != 'knowledge_point':
            raise errors.RequestError(msg='当前 Tab 不是知识点分类')

        category_ids = await category_filter_service.get_knowledge_point_category_ids(
            db=db,
            kp_cat_id=kp_cat_id,
        )
        if int(category.id) not in category_ids:
            raise errors.RequestError(msg='知识点分类不属于当前知识点目录')

        child_ids = await category_dao.get_all_children_ids(db, tab_id)
        stmt = (
            select(category_dao.model)
            .where(
                category_dao.model.id.in_(child_ids),
                category_dao.model.status.is_(True),
            )
        )
        categories = list((await db.execute(stmt)).scalars().all())
        leaf_terms: list[str] = []
        for item in categories:
            has_child = any(child.parent_id == item.id for child in categories)
            if has_child:
                continue
            term = PracticeService._keypoint_match_term(item)
            if term:
                leaf_terms.append(term)

        count_map = await knowledge_point_service._batch_count_by_kp_codes(db, leaf_terms)
        progress_map: dict[str, dict[str, int]] = {}
        if user_id is not None:
            progress_map = await knowledge_point_service._batch_progress_by_kp_codes(
                db,
                user_id,
                leaf_terms,
            )

        direct_children = [item for item in categories if item.parent_id == tab_id]
        if not direct_children:
            node = PracticeService._build_keypoint_home_node(
                category=category,
                categories=categories,
                count_map=count_map,
                progress_map=progress_map,
            )
            return [node] if node is not None else []

        result: list[GetPracticeHomeNode] = []
        direct_children.sort(key=lambda item: (int(getattr(item, 'sort_order', 0) or 0), int(item.id)))
        for child in direct_children:
            node = PracticeService._build_keypoint_home_node(
                category=child,
                categories=categories,
                count_map=count_map,
                progress_map=progress_map,
            )
            if node is not None:
                result.append(node)

        return result

    @staticmethod
    async def get_home(
        *,
        db: AsyncSession,
        cat_id: int,
        kp_cat_id: int | None,
        tab_id: int,
        filter_type: PracticeHomeFilter = 'bank',
        user_id: int | None = None,
    ) -> GetPracticeHomeResponse:
        """
        获取刷题首页内容

        :param db: 数据库会话
        :param cat_id: 题库目录分类 ID
        :param kp_cat_id: 知识点分类 ID
        :param tab_id: Tab ID
        :param filter_type: 首页过滤类型
        :param user_id: 用户 ID
        :return:
        """
        if filter_type == 'keypoint':
            items = await PracticeService._build_keypoint_home(
                db=db,
                kp_cat_id=kp_cat_id or cat_id,
                tab_id=tab_id,
                user_id=user_id,
            )
        elif filter_type == 'bank':
            items = await PracticeService._build_bank_home_by_collection(
                db=db,
                cat_id=cat_id,
                tab_id=tab_id,
                user_id=user_id,
            )
        else:
            raise errors.RequestError(msg='暂不支持的首页过滤类型')

        return GetPracticeHomeResponse(
            cat_id=cat_id,
            kp_cat_id=kp_cat_id,
            tab_id=tab_id,
            filter=filter_type,
            items=items,
        )

    @staticmethod
    async def get_practice_questions(
        *,
        db: AsyncSession,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
    ) -> Sequence[Question]:
        """
        获取可练习的题目列表（不含答案）

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param type: 题型
        :param difficulty: 难度
        :return:
        """
        return await question_dao.get_all(
            db=db,
            bank_id=bank_id,
            chapter_id=chapter_id,
            type=type,
            difficulty=difficulty,
            is_active=True,
            review_status=10,
        )

    @staticmethod
    async def get_question_for_practice(*, db: AsyncSession, question_id: int) -> dict[str, Any]:
        """
        获取题目详情用于练习（返回标准化 DTO，不含答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        question = await question_dao.get_with_relations(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')
        if question.content_status != 10:
            raise errors.NotFoundError(msg='题目内容未通过审核')

        data = question_service.serialize_question(
            question=question,
            include_analysis=False,
            include_materials=False,
        )
        await question_service._fill_kp_display_batch(db, [data])
        return data

    @staticmethod
    async def get_practice_analysis(*, db: AsyncSession, question_id: int) -> QuestionAnalysis:
        """
        查看题目解析（刷题后查看答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        return await question_service.get_analysis(db=db, question_id=question_id, increment_view=True)


practice_service: PracticeService = PracticeService()
