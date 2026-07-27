import hashlib
import json

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_question import (
    question_answer_dao,
    question_dao,
    question_explanation_dao,
    question_revision_dao,
)
from backend.app.question_bank_v2.schema.question import (
    CreateQuestionParam,
    CreateQuestionRevisionParam,
    GetQuestionAnswerDetail,
    GetQuestionDetail,
    GetQuestionExplanationDetail,
    GetQuestionListItem,
    GetQuestionRevisionDetail,
    UpdateQuestionParam,
    UpdateQuestionRevisionParam,
)
from backend.common.exception import errors
from backend.utils.timezone import timezone


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
    async def _build_revision(*, db: AsyncSession, revision: Any) -> GetQuestionRevisionDetail:
        """组装题目版本、答案和解析详情"""
        answer = await question_answer_dao.get_by_revision(db, revision.id)
        explanations = await question_explanation_dao.get_all(db, revision.id)
        return GetQuestionRevisionDetail(
            id=revision.id,
            question_id=revision.question_id,
            revision_no=revision.revision_no,
            stem=revision.stem,
            content_format=revision.content_format,
            question_type=revision.question_type,
            options=revision.option_data,
            default_score=revision.default_score,
            difficulty=revision.difficulty,
            language=revision.language,
            content_hash=revision.content_hash,
            status=revision.status,
            answer=GetQuestionAnswerDetail.model_validate(answer) if answer is not None else None,
            explanations=[GetQuestionExplanationDetail.model_validate(item) for item in explanations],
            published_by=revision.published_by,
            published_time=revision.published_time,
            created_by=revision.created_by,
            updated_by=revision.updated_by,
            created_time=revision.created_time,
            updated_time=revision.updated_time,
        )

    @staticmethod
    async def _build_detail(*, db: AsyncSession, question: Any, revision_id: int | None = None) -> GetQuestionDetail:
        """组装题目稳定身份和指定版本详情"""
        if revision_id is not None:
            revision = await question_revision_dao.get(db, revision_id, question_id=question.id)
        else:
            revision = await question_revision_dao.get_latest(db, question.id)
        return GetQuestionDetail(
            id=question.id,
            code=question.code,
            owner_id=question.owner_id,
            current_revision_id=question.current_revision_id,
            visibility=question.visibility,
            origin_type=question.origin_type,
            status=question.status,
            revision=await QuestionService._build_revision(db=db, revision=revision) if revision is not None else None,
            created_by=question.created_by,
            updated_by=question.updated_by,
            created_time=question.created_time,
            updated_time=question.updated_time,
        )

    @staticmethod
    def _content_hash(revision: GetQuestionRevisionDetail) -> str:
        """计算题目版本完整权威内容哈希"""
        payload = {
            'stem': revision.stem,
            'content_format': revision.content_format,
            'question_type': revision.question_type,
            'options': [item.model_dump(mode='json') for item in revision.options],
            'default_score': str(revision.default_score),
            'difficulty': str(revision.difficulty) if revision.difficulty is not None else None,
            'language': revision.language,
            'answer': revision.answer.model_dump(mode='json', exclude={'id', 'question_revision_id'})
            if revision.answer
            else None,
            'explanations': [
                item.model_dump(
                    mode='json',
                    exclude={'id', 'question_revision_id', 'status'},
                )
                for item in revision.explanations
            ],
        }
        raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    async def get(*, db: AsyncSession, pk: int, revision_id: int | None = None) -> GetQuestionDetail:
        """获取题目管理详情"""
        question = await question_dao.get(db, pk)
        if question is None:
            raise errors.NotFoundError(msg='题目不存在')
        return await QuestionService._build_detail(db=db, question=question, revision_id=revision_id)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        question_type: str | None = None,
        revision_status: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[GetQuestionListItem]:
        """获取题目管理列表"""
        rows = await question_dao.get_list(
            db,
            question_type=question_type,
            revision_status=revision_status,
            keyword=keyword,
            offset=offset,
            limit=limit,
        )
        return [GetQuestionListItem(**row) for row in rows]

    @staticmethod
    async def _create_revision(
        *,
        db: AsyncSession,
        question_id: int,
        revision_no: int,
        obj: CreateQuestionRevisionParam,
        user_id: int,
    ) -> Any:
        """创建题目版本及其权威答案和解析"""
        QuestionService._validate_answer(
            question_type=obj.question_type,
            options=[item.model_dump() for item in obj.options],
            answer_data=obj.answer.answer_data,
        )
        revision = await question_revision_dao.create(
            db,
            question_id=question_id,
            revision_no=revision_no,
            obj=obj,
            created_by=user_id,
        )
        await question_answer_dao.upsert(db, revision_id=revision.id, obj=obj.answer, user_id=user_id)
        await question_explanation_dao.replace(
            db,
            revision_id=revision.id,
            items=obj.explanations,
            user_id=user_id,
        )
        return revision

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateQuestionParam, created_by: int) -> GetQuestionDetail:
        """创建题目及首个草稿版本"""
        if await question_dao.get_by_code(db, obj.code):
            raise errors.ConflictError(msg='题目编码已存在')
        owner_id = created_by if obj.visibility == 'private' or obj.origin_type == 'user_created' else None
        question = await question_dao.create(
            db,
            code=obj.code,
            owner_id=owner_id,
            visibility=obj.visibility,
            origin_type=obj.origin_type,
            status=obj.status,
            created_by=created_by,
        )
        revision = await QuestionService._create_revision(
            db=db,
            question_id=question.id,
            revision_no=1,
            obj=obj.revision,
            user_id=created_by,
        )
        return await QuestionService._build_detail(db=db, question=question, revision_id=revision.id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateQuestionParam, updated_by: int) -> GetQuestionDetail:
        """更新题目稳定身份"""
        question = await question_dao.get(db, pk)
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
        if data:
            data['updated_by'] = updated_by
            await question_dao.update(db, pk, data)
        question = await question_dao.get(db, pk)
        return await QuestionService._build_detail(db=db, question=question)

    @staticmethod
    async def get_revisions(*, db: AsyncSession, question_id: int) -> list[GetQuestionRevisionDetail]:
        """获取题目全部版本"""
        if await question_dao.get(db, question_id) is None:
            raise errors.NotFoundError(msg='题目不存在')
        revisions = await question_revision_dao.get_all(db, question_id)
        return [await QuestionService._build_revision(db=db, revision=item) for item in revisions]

    @staticmethod
    async def create_revision(
        *,
        db: AsyncSession,
        question_id: int,
        obj: CreateQuestionRevisionParam,
        created_by: int,
    ) -> GetQuestionRevisionDetail:
        """创建题目草稿版本"""
        question = await question_dao.get(db, question_id, for_update=True)
        if question is None:
            raise errors.NotFoundError(msg='题目不存在')
        revision_no = await question_revision_dao.get_next_revision_no(db, question_id)
        revision = await QuestionService._create_revision(
            db=db,
            question_id=question_id,
            revision_no=revision_no,
            obj=obj,
            user_id=created_by,
        )
        return await QuestionService._build_revision(db=db, revision=revision)

    @staticmethod
    async def update_revision(
        *,
        db: AsyncSession,
        question_id: int,
        revision_id: int,
        obj: UpdateQuestionRevisionParam,
        updated_by: int,
    ) -> GetQuestionRevisionDetail:
        """更新题目草稿版本及答案解析"""
        revision = await question_revision_dao.get(db, revision_id, question_id=question_id, for_update=True)
        if revision is None:
            raise errors.NotFoundError(msg='题目版本不存在')
        if revision.status != 'draft':
            raise errors.ConflictError(msg='已发布或已退役题目版本不可修改')
        data = obj.model_dump(exclude_unset=True, exclude={'answer', 'explanations', 'options'})
        if 'options' in obj.model_fields_set:
            data['option_data'] = [item.model_dump() for item in (obj.options or [])]
        if data:
            data['updated_by'] = updated_by
            await question_revision_dao.update(db, revision_id, data)
        if obj.answer is not None:
            await question_answer_dao.upsert(db, revision_id=revision_id, obj=obj.answer, user_id=updated_by)
        if obj.explanations is not None:
            await question_explanation_dao.replace(
                db,
                revision_id=revision_id,
                items=obj.explanations,
                user_id=updated_by,
            )
        revision = await question_revision_dao.get(db, revision_id, question_id=question_id)
        detail = await QuestionService._build_revision(db=db, revision=revision)
        if detail.answer is not None:
            QuestionService._validate_answer(
                question_type=detail.question_type,
                options=[item.model_dump() for item in detail.options],
                answer_data=detail.answer.answer_data,
            )
        return detail

    @staticmethod
    async def publish_revision(
        *,
        db: AsyncSession,
        question_id: int,
        revision_id: int,
        published_by: int,
    ) -> GetQuestionRevisionDetail:
        """发布题目版本并原子切换当前版本"""
        question = await question_dao.get(db, question_id, for_update=True)
        if question is None:
            raise errors.NotFoundError(msg='题目不存在')
        revision = await question_revision_dao.get(db, revision_id, question_id=question_id, for_update=True)
        if revision is None:
            raise errors.NotFoundError(msg='题目版本不存在')
        if revision.status != 'draft':
            raise errors.ConflictError(msg='仅草稿题目版本可以发布')
        detail = await QuestionService._build_revision(db=db, revision=revision)
        if detail.answer is None:
            raise errors.ConflictError(msg='题目缺少权威答案，不能发布')
        if sum(item.is_default for item in detail.explanations) != 1:
            raise errors.ConflictError(msg='题目必须且只能有一个默认解析')
        QuestionService._validate_answer(
            question_type=detail.question_type,
            options=[item.model_dump() for item in detail.options],
            answer_data=detail.answer.answer_data,
        )

        now = timezone.now()
        content_hash = QuestionService._content_hash(detail)
        if question.current_revision_id is not None and question.current_revision_id != revision_id:
            await question_revision_dao.update_model_by_column(
                db,
                {'status': 'retired', 'updated_by': published_by},
                id=question.current_revision_id,
                question_id=question_id,
                deleted=0,
                status='published',
            )
        await question_revision_dao.update_model_by_column(
            db,
            {
                'status': 'published',
                'content_hash': content_hash,
                'published_by': published_by,
                'published_time': now,
                'updated_by': published_by,
            },
            id=revision_id,
            question_id=question_id,
            deleted=0,
            status='draft',
        )
        for explanation in detail.explanations:
            await question_explanation_dao.update_model_by_column(
                db,
                {'status': 'published', 'updated_by': published_by},
                id=explanation.id,
                question_revision_id=revision_id,
                deleted=0,
                status='draft',
            )
        await question_dao.update(
            db,
            question_id,
            {'current_revision_id': revision_id, 'updated_by': published_by},
        )
        revision = await question_revision_dao.get(db, revision_id, question_id=question_id)
        return await QuestionService._build_revision(db=db, revision=revision)


question_service: QuestionService = QuestionService()
