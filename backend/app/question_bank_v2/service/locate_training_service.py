import json
import re
import time

from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_material import (
    material_anchor_dao,
    question_interaction_dao,
    question_material_dao,
)
from backend.app.question_bank_v2.crud.crud_question import question_answer_dao, question_dao
from backend.app.question_bank_v2.schema.locate_training import (
    LOCATE_INTERACTION_TYPES,
    CreateLocateTrainingParam,
    GetLocateAnchorDetail,
    GetLocateClickResult,
    GetLocateMaterialBlockDetail,
    GetLocateQuestionDetail,
    GetLocateRoleDetail,
    GetLocateTrainingResult,
    GetLocateTrainingSessionDetail,
    SubmitLocateClickParam,
)
from backend.app.question_bank_v2.service.material_service import material_service
from backend.common.exception import errors
from backend.database.redis import redis_client

if TYPE_CHECKING:
    from collections.abc import Sequence

LOCATE_TRAINING_TTL = 7200
LOCATE_TRAINING_REDIS_PREFIX = 'qbank_v2:locate_training'
_TAG_RE = re.compile(r'<[^>]+>')


class LocateTrainingService:
    """资料分析找数训练服务类"""

    @staticmethod
    def _redis_key(session_key: str) -> str:
        return f'{LOCATE_TRAINING_REDIS_PREFIX}:{session_key}'

    @staticmethod
    def _strip_html(value: str | None) -> str:
        """去除富文本标签，返回纯文本题干"""
        if not value:
            return ''
        text = _TAG_RE.sub(' ', value)
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _to_anchor_id(value: Any) -> int | None:
        """转换单个答案值为锚点 ID，无法转换时返回 None"""
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_answer_anchor_ids(answer_data: dict[str, Any]) -> list[int]:
        """从标准答案中提取目标锚点 ID，支持单值、列表和角色映射"""
        correct = answer_data.get('correct') if isinstance(answer_data, dict) else None
        if isinstance(correct, dict):
            values = list(correct.values())
        elif isinstance(correct, list):
            values = correct
        elif correct is not None:
            values = [correct]
        else:
            values = []
        anchor_ids = [anchor_id for value in values if (anchor_id := LocateTrainingService._to_anchor_id(value))]
        return anchor_ids

    ANCHOR_ROLE_LABELS = {
        'current_value': '现期值',
        'base_value': '基期值',
        'growth_rate': '增长率',
        'growth_amount': '增长量',
        'yoy': '同比',
        'mom': '环比',
        'change_amount': '变化量',
        'change_rate': '变化幅度',
    }

    @classmethod
    def _build_roles(cls, config: dict[str, Any]) -> list[GetLocateRoleDetail]:
        """优先读取显式 roles 列表，否则从 anchor_roles 映射派生"""
        raw_roles = config.get('roles') if isinstance(config, dict) else None
        if isinstance(raw_roles, list):
            roles: list[GetLocateRoleDetail] = []
            for item in raw_roles:
                if not isinstance(item, dict):
                    continue
                key = str(item.get('key') or '').strip()
                if not key:
                    continue
                roles.append(GetLocateRoleDetail(key=key, label=str(item.get('label') or key)))
            if roles:
                return roles

        anchor_roles = config.get('anchor_roles') if isinstance(config, dict) else None
        if not isinstance(anchor_roles, dict):
            return []
        seen: set[str] = set()
        roles = []
        for role in anchor_roles.values():
            key = str(role or '').strip()
            if not key or key in seen:
                continue
            seen.add(key)
            roles.append(GetLocateRoleDetail(key=key, label=cls.ANCHOR_ROLE_LABELS.get(key, key)))
        return roles

    @staticmethod
    async def _load_revision_candidates(
        db: AsyncSession,
        *,
        material_revision_id: int,
    ) -> list[dict[str, Any]]:
        """未显式配置候选时，取材料版本全部非退役锚点作为候选"""
        anchors = await material_anchor_dao.get_all(db, material_revision_id=material_revision_id)
        return [
            {
                'anchor_id': anchor.id,
                'candidate_role': '',
                'label': None,
                'sort_order': index,
                'material_revision_id': material_revision_id,
                'anchor': {
                    'id': anchor.id,
                    'material_id': anchor.material_id,
                    'material_revision_id': anchor.material_revision_id,
                    'anchor_key': anchor.anchor_key,
                    'anchor_type': anchor.anchor_type,
                    'text': anchor.text,
                    'semantic_role': anchor.semantic_role,
                    'block_id': anchor.block_id,
                    'start_offset': anchor.start_offset,
                    'end_offset': anchor.end_offset,
                    'asset_id': anchor.asset_id,
                    'bbox': anchor.bbox,
                    'polygon': anchor.polygon,
                    'table_cell': anchor.table_cell,
                    'source': anchor.source,
                    'confidence': anchor.confidence,
                    'content_hash': anchor.content_hash,
                    'status': anchor.status,
                    'extra_data': anchor.extra_data,
                },
            }
            for index, anchor in enumerate(anchors)
            if anchor.status != 'retired'
        ]

    async def _build_question_payload(
        self,
        *,
        db: AsyncSession,
        order: int,
        question_id: int,
    ) -> dict[str, Any] | None:
        """组装单道找数训练题，无可训练交互或无有效答案时返回 None"""
        rows = await question_interaction_dao.get_all(db, question_ids=[question_id], active_only=True)
        interaction = next(
            (row for row in rows if row.get('interaction_type') in LOCATE_INTERACTION_TYPES),
            None,
        )
        if interaction is None:
            return None
        config = interaction.get('config') if isinstance(interaction.get('config'), dict) else {}
        material_revision_id = interaction.get('material_revision_id')

        candidates = [item for item in interaction.get('candidates') or [] if item.get('anchor')]
        if not candidates and material_revision_id is not None:
            candidates = await self._load_revision_candidates(db, material_revision_id=material_revision_id)
        if not candidates:
            return None

        candidate_anchor_ids = [int(item['anchor_id']) for item in candidates]

        answer_data = config.get('answer_data')
        if not isinstance(answer_data, dict):
            answer = await question_answer_dao.get_by_question(db, question_id)
            answer_data = answer.answer_data if answer is not None else {}
        correct_anchor_ids = [
            anchor_id for anchor_id in self._extract_answer_anchor_ids(answer_data) if anchor_id in candidate_anchor_ids
        ]
        if not correct_anchor_ids:
            return None

        question = await question_dao.get(db, question_id)
        if question is None:
            return None

        material_title = None
        content_hash = None
        blocks: list[GetLocateMaterialBlockDetail] = []
        material_revision_id = interaction.get('material_revision_id')
        if material_revision_id is not None:
            relations = await question_material_dao.get_all(db, question_id)
            relation = next(
                (item for item in relations if item['material_revision_id'] == material_revision_id),
                None,
            )
            if relation is not None:
                blocks_data = await material_service.get_blocks(
                    db=db,
                    material_id=relation['material_id'],
                    revision_id=material_revision_id,
                )
                material_title = blocks_data.get('title')
                content_hash = blocks_data.get('content_hash')
                blocks = [
                    GetLocateMaterialBlockDetail(
                        id=str(block.get('id') or block.get('block_id') or index + 1),
                        type=str(block.get('type') or 'text'),
                        title=block.get('title'),
                        content=block.get('content'),
                        asset_url=block.get('asset_url'),
                        natural_width=block.get('natural_width'),
                        natural_height=block.get('natural_height'),
                    )
                    for index, block in enumerate(blocks_data.get('blocks') or [])
                ]

        anchors = [
            GetLocateAnchorDetail(
                id=int(item['anchor']['id']),
                anchor_key=str(item['anchor'].get('anchor_key') or ''),
                anchor_type=str(item['anchor'].get('anchor_type') or 'text_range'),
                text=item['anchor'].get('text'),
                semantic_role=item['anchor'].get('semantic_role'),
                block_id=item['anchor'].get('block_id'),
                start_offset=item['anchor'].get('start_offset'),
                end_offset=item['anchor'].get('end_offset'),
                bbox=item['anchor'].get('bbox'),
                polygon=item['anchor'].get('polygon'),
                table_cell=item['anchor'].get('table_cell'),
                candidate_role=str(item.get('candidate_role') or ''),
                candidate_label=item.get('label'),
            )
            for item in candidates
            if item.get('anchor')
        ]

        return {
            'order': order,
            'question_id': question_id,
            'stem': self._strip_html(question.stem) or interaction.get('instruction') or '请找出对应的数据',
            'instruction': interaction.get('instruction') or '请点击材料中对应的数据',
            'interaction_type': interaction['interaction_type'],
            'selection_mode': interaction.get('selection_mode') or 'single',
            'target_count': len(correct_anchor_ids),
            'material_title': material_title,
            'content_hash': content_hash,
            'blocks': [block.model_dump() for block in blocks],
            'anchors': [anchor.model_dump() for anchor in anchors],
            'roles': [role.model_dump() for role in self._build_roles(interaction.get('config') or {})],
            'correct_anchor_ids': correct_anchor_ids,
            'found_anchor_ids': [],
            'wrong_clicks': 0,
            'completed': False,
        }

    @staticmethod
    def _public_question(item: dict[str, Any]) -> GetLocateQuestionDetail:
        """剔除内部判分字段后构建公开题目"""
        return GetLocateQuestionDetail(
            order=item['order'],
            question_id=item['question_id'],
            stem=item['stem'],
            instruction=item['instruction'],
            interaction_type=item['interaction_type'],
            selection_mode=item['selection_mode'],
            target_count=item['target_count'],
            material_title=item.get('material_title'),
            content_hash=item.get('content_hash'),
            blocks=item.get('blocks') or [],
            anchors=item.get('anchors') or [],
            roles=item.get('roles') or [],
        )

    async def _load_runtime(self, *, session_key: str, user_id: int) -> tuple[dict[str, Any], int]:
        """加载并校验 Redis 临时训练会话"""
        redis_key = self._redis_key(session_key)
        raw = await redis_client.get(redis_key)
        if not raw:
            raise errors.NotFoundError(msg='找数训练会话不存在或已过期，请重新开始')
        try:
            runtime = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise errors.ServerError(msg='找数训练临时数据损坏') from exc
        if runtime.get('user_id') != user_id:
            raise errors.NotFoundError(msg='找数训练会话不存在')
        ttl = max(0, int(await redis_client.ttl(redis_key)))
        return runtime, ttl

    @staticmethod
    async def _save_runtime(runtime: dict[str, Any], session_key: str, ttl: int) -> None:
        """写回会话并保持原有效期"""
        await redis_client.set(
            LocateTrainingService._redis_key(session_key),
            json.dumps(runtime, ensure_ascii=False, default=str),
            ex=ttl if ttl > 0 else LOCATE_TRAINING_TTL,
        )

    async def create(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateLocateTrainingParam,
    ) -> GetLocateTrainingSessionDetail:
        """创建找数训练会话并投递不含答案的题目"""
        question_ids = await question_interaction_dao.get_locate_question_ids(
            db,
            interaction_types=LOCATE_INTERACTION_TYPES,
            limit=obj.count * 3,
        )
        questions: list[dict[str, Any]] = []
        for question_id in question_ids:
            payload = await self._build_question_payload(db=db, order=len(questions) + 1, question_id=question_id)
            if payload is not None:
                questions.append(payload)
            if len(questions) >= obj.count:
                break
        if not questions:
            raise errors.NotFoundError(msg='暂无可用的找数训练题目，请先配置找数题与材料锚点')

        session_key = uuid4().hex
        runtime = {
            'session_key': session_key,
            'user_id': user_id,
            'count': len(questions),
            'started_time': time.time(),
            'finished': False,
            'total_clicks': 0,
            'wrong_clicks': 0,
            'questions': questions,
        }
        await self._save_runtime(runtime, session_key, LOCATE_TRAINING_TTL)
        return GetLocateTrainingSessionDetail(
            session_key=session_key,
            count=len(questions),
            expires_in=LOCATE_TRAINING_TTL,
            questions=[self._public_question(item) for item in questions],
        )

    async def get(
        self,
        *,
        session_key: str,
        user_id: int,
    ) -> GetLocateTrainingSessionDetail:
        """恢复进行中的找数训练会话"""
        runtime, ttl = await self._load_runtime(session_key=session_key, user_id=user_id)
        if runtime.get('finished'):
            raise errors.RequestError(msg='找数训练已结束，请重新开始')
        return GetLocateTrainingSessionDetail(
            session_key=session_key,
            count=runtime.get('count') or len(runtime.get('questions') or []),
            expires_in=ttl,
            questions=[self._public_question(item) for item in runtime.get('questions') or []],
        )

    async def judge(
        self,
        *,
        session_key: str,
        user_id: int,
        obj: SubmitLocateClickParam,
    ) -> GetLocateClickResult:
        """判定单次找数点击，命中目标则累计进度"""
        runtime, ttl = await self._load_runtime(session_key=session_key, user_id=user_id)
        if runtime.get('finished'):
            raise errors.RequestError(msg='找数训练已结束，请重新开始')
        question = next(
            (item for item in runtime.get('questions') or [] if item['order'] == obj.question_order),
            None,
        )
        if question is None:
            raise errors.NotFoundError(msg='找数训练题目不存在')

        candidate_ids = {int(anchor['id']) for anchor in question.get('anchors') or []}
        if obj.anchor_id not in candidate_ids:
            raise errors.RequestError(msg='点击的位置不在本题候选范围内')

        correct_ids = set(question.get('correct_anchor_ids') or [])
        found_ids = set(question.get('found_anchor_ids') or [])
        runtime['total_clicks'] = int(runtime.get('total_clicks') or 0) + 1

        is_correct = obj.anchor_id in correct_ids
        already_found = is_correct and obj.anchor_id in found_ids
        if is_correct:
            found_ids.add(obj.anchor_id)
        else:
            question['wrong_clicks'] = int(question.get('wrong_clicks') or 0) + 1
            runtime['wrong_clicks'] = int(runtime.get('wrong_clicks') or 0) + 1

        question['found_anchor_ids'] = list(found_ids)
        target_count = int(question.get('target_count') or len(correct_ids))
        question_completed = len(found_ids) >= target_count and target_count > 0
        if question_completed:
            question['completed'] = True
        training_completed = question_completed and all(
            item.get('completed') for item in runtime.get('questions') or []
        )

        await self._save_runtime(runtime, session_key, ttl)
        return GetLocateClickResult(
            is_correct=is_correct,
            already_found=already_found,
            found_count=len(found_ids),
            target_count=target_count,
            question_completed=question_completed,
            training_completed=training_completed,
            question_wrong_clicks=int(question.get('wrong_clicks') or 0),
            total_clicks=int(runtime.get('total_clicks') or 0),
            wrong_clicks=int(runtime.get('wrong_clicks') or 0),
        )

    async def complete(
        self,
        *,
        session_key: str,
        user_id: int,
        question_meta: list[dict[str, Any]] | None = None,
    ) -> GetLocateTrainingResult:
        """结束找数训练并返回结算数据，会话随之销毁"""
        runtime, _ttl = await self._load_runtime(session_key=session_key, user_id=user_id)
        if runtime.get('finished'):
            raise errors.RequestError(msg='找数训练已结算，请重新开始')
        questions: Sequence[dict[str, Any]] = runtime.get('questions') or []
        total_clicks = int(runtime.get('total_clicks') or 0)
        wrong_clicks = int(runtime.get('wrong_clicks') or 0)
        completed_questions = sum(1 for item in questions if item.get('completed'))
        perfect_questions = sum(
            1 for item in questions if item.get('completed') and int(item.get('wrong_clicks') or 0) == 0
        )
        hit_clicks = max(0, total_clicks - wrong_clicks)
        click_accuracy = (Decimal(hit_clicks) / Decimal(total_clicks) if total_clicks else Decimal(1)).quantize(
            Decimal('0.0001')
        )
        duration_seconds = max(0, int(time.time() - float(runtime.get('started_time') or time.time())))

        given_up_questions = 0
        peeked_questions = 0
        total_peeks = 0
        if question_meta:
            known_orders = {int(item.get('order') or 0) for item in questions}
            for meta in question_meta:
                if not isinstance(meta, dict):
                    continue
                order = int(meta.get('question_order') or 0)
                if order not in known_orders:
                    continue
                if meta.get('given_up'):
                    given_up_questions += 1
                peek_count = int(meta.get('peek_count') or 0)
                if peek_count > 0:
                    peeked_questions += 1
                    total_peeks += peek_count

        result = GetLocateTrainingResult(
            session_key=session_key,
            question_count=len(questions),
            completed_questions=completed_questions,
            perfect_questions=perfect_questions,
            total_clicks=total_clicks,
            wrong_clicks=wrong_clicks,
            click_accuracy=click_accuracy,
            duration_seconds=duration_seconds,
            given_up_questions=given_up_questions,
            peeked_questions=peeked_questions,
            total_peeks=total_peeks,
        )
        await redis_client.delete(self._redis_key(session_key))
        return result


locate_training_service: LocateTrainingService = LocateTrainingService()
