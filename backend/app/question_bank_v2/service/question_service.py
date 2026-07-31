import hashlib
import json

from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_knowledge import question_knowledge_point_dao
from backend.app.question_bank_v2.crud.crud_material import question_interaction_dao, question_material_dao
from backend.app.question_bank_v2.crud.crud_question import (
    question_answer_dao,
    question_dao,
    question_explanation_dao,
)
from backend.app.question_bank_v2.schema.knowledge import GetKnowledgePointAssignmentDetail
from backend.app.question_bank_v2.schema.material import GetQuestionMaterialDetail
from backend.app.question_bank_v2.schema.question import (
    CreateQuestionParam,
    GetQuestionAnswerDetail,
    GetQuestionDetail,
    GetQuestionExplanationDetail,
    GetQuestionListItem,
    UpdateQuestionParam,
)
from backend.app.question_bank_v2.service.knowledge_service import knowledge_service
from backend.app.question_bank_v2.service.material_service import material_service
from backend.common.exception import errors


class QuestionService:
    """题目内容服务类"""

    @staticmethod
    def _validate_answer(*, question_type: str, options: list[dict[str, Any]], answer_data: dict[str, Any]) -> None:
        """校验题型、选项和结构化答案的一致性"""
        option_codes = [str(item.get('option_code', '')).strip() for item in options]
        if len(option_codes) != len(set(option_codes)) or any(not code for code in option_codes):
            raise errors.RequestError(msg='选项编码不能为空且不能重复')
        correct = answer_data.get('correct')
        if question_type in {'single_choice', 'multiple_choice'} and len(option_codes) < 2:
            raise errors.RequestError(msg='选择题至少需要两个选项')
        if question_type == 'single_choice':
            if not isinstance(correct, str) or correct not in option_codes:
                raise errors.RequestError(msg='单选题答案必须是有效选项编码')
        elif question_type == 'multiple_choice':
            if not isinstance(correct, list) or not correct or not set(correct) <= set(option_codes):
                raise errors.RequestError(msg='多选题答案必须是非空有效选项编码列表')
        elif question_type == 'true_false' and not isinstance(correct, bool):
            raise errors.RequestError(msg='判断题答案必须是布尔值')
        elif question_type != 'composite' and correct is None:
            raise errors.RequestError(msg='题目标准答案不能为空')
        if question_type not in {'single_choice', 'multiple_choice'} and options:
            raise errors.RequestError(msg='仅选择题允许配置选项')

    @staticmethod
    async def _build_detail(*, db: AsyncSession, question: Any) -> GetQuestionDetail:
        """组装题目聚合详情"""
        answer = await question_answer_dao.get_by_question(db, question.id)
        explanations = await question_explanation_dao.get_all(db, question.id)
        knowledge_points = await question_knowledge_point_dao.get_all(db, question.id)
        materials = await question_material_dao.get_all(db, question.id)
        interactions = await question_interaction_dao.get_all(db, question_ids=[question.id])
        return GetQuestionDetail(
            id=question.id,
            code=question.code,
            owner_id=question.owner_id,
            visibility=question.visibility,
            origin_type=question.origin_type,
            status=question.status,
            stem=question.stem,
            content_format=question.content_format,
            question_type=question.question_type,
            options=question.option_data,
            default_score=question.default_score,
            difficulty=question.difficulty,
            content_hash=question.content_hash,
            answer=GetQuestionAnswerDetail.model_validate(answer) if answer is not None else None,
            explanations=[GetQuestionExplanationDetail.model_validate(item) for item in explanations],
            knowledge_points=[GetKnowledgePointAssignmentDetail(**item) for item in knowledge_points],
            materials=[GetQuestionMaterialDetail(**item) for item in materials],
            interactions=interactions,
            created_by=question.created_by,
            updated_by=question.updated_by,
            created_time=question.created_time,
            updated_time=question.updated_time,
        )

    @staticmethod
    def _content_hash(
        *,
        stem: str,
        content_format: str,
        question_type: str,
        options: list[dict[str, Any]],
        default_score: Any,
        answer: Any,
        explanations: list[Any],
        knowledge_points: list[Any],
        materials: list[Any],
        interactions: list[Any],
    ) -> str:
        """计算题目完整权威内容哈希"""
        payload = {
            'stem': stem,
            'content_format': content_format,
            'question_type': question_type,
            'options': options,
            'default_score': str(default_score),
            'answer': answer.model_dump(mode='json', exclude={'id', 'question_id'})
            if answer
            else None,
            'explanations': [
                item.model_dump(
                    mode='json',
                    exclude={'id', 'question_id', 'status'},
                )
                for item in explanations
            ],
            'knowledge_points': [
                item.model_dump(mode='json', exclude={'id', 'question_id', 'knowledge_point_name'})
                for item in knowledge_points
            ],
            'materials': [
                item.model_dump(
                    mode='json',
                    include={
                        'material_id',
                        'material_revision_id',
                        'role',
                        'sort_order',
                        'display_config',
                        'content_hash',
                    },
                )
                for item in materials
            ],
            'interactions': [
                item.model_dump(
                    mode='json',
                    exclude={'id', 'question_id'},
                )
                for item in interactions
                if item.status == 'active'
            ],
        }
        raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GetQuestionDetail:
        """获取题目管理详情"""
        question = await question_dao.get(db, pk)
        if question is None:
            raise errors.NotFoundError(msg='题目不存在')
        return await QuestionService._build_detail(db=db, question=question)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        question_type: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[GetQuestionListItem]:
        """获取题目管理列表"""
        rows = await question_dao.get_list(
            db,
            question_type=question_type,
            keyword=keyword,
            offset=offset,
            limit=limit,
        )
        return [GetQuestionListItem(**row) for row in rows]

    @staticmethod
    def get_list_select(
        *,
        bank_id: int | None = None,
        question_type: str | None = None,
        keyword: str | None = None,
    ) -> Select:
        """构建题目管理列表分页查询，交给 API 层 paging_data 处理"""
        return question_dao.get_list_select(bank_id=bank_id, question_type=question_type, keyword=keyword)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateQuestionParam, created_by: int) -> GetQuestionDetail:
        """创建题目"""
        if await question_dao.get_by_code(db, obj.code):
            raise errors.ConflictError(msg='题目编码已存在')
        QuestionService._validate_answer(
            question_type=obj.question_type,
            options=[item.model_dump() for item in obj.options],
            answer_data=obj.answer.answer_data,
        )
        await knowledge_service.ensure_point_ids(
            db=db,
            point_ids=[item.knowledge_point_id for item in obj.knowledge_points],
        )
        await material_service.ensure_references(db=db, items=obj.materials)
        owner_id = created_by if obj.visibility == 'private' or obj.origin_type == 'user_created' else None
        question = await question_dao.create(
            db,
            code=obj.code,
            owner_id=owner_id,
            visibility=obj.visibility,
            origin_type=obj.origin_type,
            status=obj.status,
            stem=obj.stem,
            content_format=obj.content_format,
            question_type=obj.question_type,
            option_data=[item.model_dump() for item in obj.options],
            default_score=obj.default_score,
            difficulty=None,
            content_hash=None,
            created_by=created_by,
        )
        await question_answer_dao.upsert(db, question_id=question.id, obj=obj.answer, user_id=created_by)
        await question_explanation_dao.replace(
            db,
            question_id=question.id,
            items=obj.explanations,
            user_id=created_by,
        )
        await question_knowledge_point_dao.replace(
            db,
            question_id=question.id,
            items=obj.knowledge_points,
            user_id=created_by,
        )
        await question_material_dao.replace(
            db,
            question_id=question.id,
            items=obj.materials,
            user_id=created_by,
        )
        return await QuestionService._build_detail(db=db, question=question)

    @staticmethod
    async def update(  # noqa: C901
        *, db: AsyncSession, pk: int, obj: UpdateQuestionParam, updated_by: int
    ) -> GetQuestionDetail:
        """更新题目"""
        question = await question_dao.get(db, pk, for_update=True)
        if question is None:
            raise errors.NotFoundError(msg='题目不存在')
        data = obj.model_dump(exclude_unset=True)
        if 'code' in data and data['code'] != question.code:
            existing = await question_dao.get_by_code(db, data['code'])
            if existing is not None and existing.id != pk:
                raise errors.ConflictError(msg='题目编码已存在')
        if data.get('visibility') == 'private' and question.owner_id is None:
            data['owner_id'] = updated_by
        elif data.get('visibility') in {'public', 'internal'} and question.origin_type != 'user_created':
            data['owner_id'] = None
        option_data = data.pop('options', None)
        if option_data is not None:
            data['option_data'] = [item.model_dump() for item in option_data]
        answer = obj.answer or await question_answer_dao.get_by_question(db, pk)
        if answer is None:
            raise errors.ConflictError(msg='题目缺少权威答案')
        QuestionService._validate_answer(
            question_type=obj.question_type or question.question_type,
            options=data.get('option_data', question.option_data),
            answer_data=answer.answer_data,
        )
        data.pop('answer', None)
        data.pop('explanations', None)
        data.pop('knowledge_points', None)
        data.pop('materials', None)
        if data:
            data['updated_by'] = updated_by
            await question_dao.update(db, pk, data)
        if obj.answer is not None:
            await question_answer_dao.upsert(db, question_id=pk, obj=obj.answer, user_id=updated_by)
        if obj.explanations is not None:
            await question_explanation_dao.replace(
                db,
                question_id=pk,
                items=obj.explanations,
                user_id=updated_by,
            )
        if obj.knowledge_points is not None:
            await knowledge_service.ensure_point_ids(
                db=db,
                point_ids=[item.knowledge_point_id for item in obj.knowledge_points],
            )
            await question_knowledge_point_dao.replace(
                db,
                question_id=pk,
                items=obj.knowledge_points,
                user_id=updated_by,
            )
        if obj.materials is not None:
            await material_service.ensure_references(db=db, items=obj.materials)
            await question_material_dao.replace(
                db,
                question_id=pk,
                items=obj.materials,
                user_id=updated_by,
            )
        question = await question_dao.get(db, pk)
        return await QuestionService._build_detail(db=db, question=question)


question_service: QuestionService = QuestionService()
