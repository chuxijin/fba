#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import re
from collections.abc import Sequence
from html import unescape
from html.parser import HTMLParser
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_interaction import (
    material_anchor_dao,
    question_interaction_annotation_dao,
)
from backend.app.question_bank.crud.crud_material import material_dao
from backend.app.question_bank.crud.crud_question import question_dao
from backend.app.question_bank.model.question import MaterialAnchor, QuestionInteractionAnnotation
from backend.app.question_bank.schema.interaction import (
    BatchCreateMaterialAnchorParam,
    CreateMaterialAnchorParam,
    CreateQuestionInteractionAnnotationParam,
    DeleteInteractionIdsParam,
    GetMaterialBlocksResult,
    GetMaterialAnchorDetail,
    GetMaterialQuestionPreview,
    GetQuestionInteractionAnnotationDetail,
    MaterialAnchorQueryParam,
    QuestionInteractionAnnotationQueryParam,
    UpdateMaterialAnchorParam,
    UpdateQuestionInteractionAnnotationParam,
)
from backend.common.exception import errors


class MaterialHtmlBlockParser(HTMLParser):
    """材料 HTML 分块解析器"""

    block_tags = {'article', 'div', 'li', 'p', 'section', 'table', 'tr'}

    def __init__(self, *, material_title: str) -> None:
        super().__init__(convert_charrefs=True)
        self.material_title = material_title
        self.blocks: list[dict[str, Any]] = []
        self.text_parts: list[str] = []
        self.text_count = 0
        self.image_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """
        处理开始标签

        :param tag: 标签名
        :param attrs: 标签属性
        :return:
        """
        tag_name = tag.lower()
        if tag_name == 'br':
            self.text_parts.append('\n')
            return
        if tag_name == 'img':
            self._flush_text()
            self._append_image(attrs)
            return
        if tag_name in self.block_tags:
            self._append_break()
            return
        if tag_name in {'td', 'th'}:
            self.text_parts.append(' ')

    def handle_endtag(self, tag: str) -> None:
        """
        处理结束标签

        :param tag: 标签名
        :return:
        """
        tag_name = tag.lower()
        if tag_name in self.block_tags:
            self._append_break()

    def handle_data(self, data: str) -> None:
        """
        处理文本数据

        :param data: 文本数据
        :return:
        """
        if data:
            self.text_parts.append(unescape(data))

    def close(self) -> None:
        """关闭解析器并写入剩余文本"""
        super().close()
        self._flush_text()

    def _append_break(self) -> None:
        """追加换行"""
        if self.text_parts and self.text_parts[-1] != '\n':
            self.text_parts.append('\n')

    def _append_image(self, attrs: list[tuple[str, str | None]]) -> None:
        """
        追加图片块

        :param attrs: 图片属性
        :return:
        """
        attr_map = {key.lower(): value or '' for key, value in attrs}
        asset_url = self._get_image_url(attr_map)
        if not asset_url:
            return

        self.image_count += 1
        natural_width = self._get_dimension(attr_map, 'width')
        natural_height = self._get_dimension(attr_map, 'height')
        block: dict[str, Any] = {
            'id': f'image-{self.image_count}',
            'type': 'image',
            'title': attr_map.get('alt') or '图表资料',
            'asset_url': asset_url,
            'sort_order': len(self.blocks) + 1,
        }
        if natural_width is not None:
            block['natural_width'] = natural_width
        if natural_height is not None:
            block['natural_height'] = natural_height
        self.blocks.append(block)

    def _flush_text(self) -> None:
        """写入文本块"""
        content = self._normalize_text(''.join(self.text_parts))
        self.text_parts = []
        if not content:
            return

        self.text_count += 1
        self.blocks.append(
            {
                'id': f'text-{self.text_count}',
                'type': 'text',
                'title': self.material_title if self.text_count == 1 else '材料',
                'content': content,
                'sort_order': len(self.blocks) + 1,
            }
        )

    @staticmethod
    def _get_image_url(attrs: dict[str, str]) -> str:
        """
        获取图片地址

        :param attrs: 图片属性
        :return:
        """
        for key in ('src', '_src', 'data-src', 'data-original', 'url'):
            value = attrs.get(key)
            if value:
                return value.strip()
        return ''

    @staticmethod
    def _get_dimension(attrs: dict[str, str], key: str) -> float | None:
        """
        获取图片尺寸

        :param attrs: 图片属性
        :param key: 尺寸字段
        :return:
        """
        direct_value = MaterialHtmlBlockParser._parse_number(attrs.get(key))
        if direct_value is not None:
            return direct_value

        style = attrs.get('style') or ''
        match = re.search(rf'{key}\s*:\s*([0-9.]+)', style, flags=re.IGNORECASE)
        if not match:
            return None
        return MaterialHtmlBlockParser._parse_number(match.group(1))

    @staticmethod
    def _parse_number(value: str | None) -> float | None:
        """
        解析数字

        :param value: 原始值
        :return:
        """
        if not value:
            return None
        match = re.search(r'[0-9.]+', value)
        if not match:
            return None
        return float(match.group(0))

    @staticmethod
    def _normalize_text(value: str) -> str:
        """
        规范化文本

        :param value: 原始文本
        :return:
        """
        normalized = value.replace('\xa0', ' ').replace('\r', '\n')
        lines = []
        for line in normalized.split('\n'):
            text = re.sub(r'[ \t\f\v]+', ' ', line).strip()
            if text:
                lines.append(text)
        return '\n'.join(lines)


class InteractionAnnotationService:
    """交互标注服务类"""

    @staticmethod
    def build_content_hash(content: str) -> str:
        """
        构建内容哈希

        :param content: 内容
        :return:
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    @staticmethod
    def build_material_blocks(content: str, *, title: str) -> list[dict[str, Any]]:
        """
        构建材料顺序分块

        :param content: 材料 HTML 内容
        :param title: 材料标题
        :return:
        """
        parser = MaterialHtmlBlockParser(material_title=title)
        parser.feed(content)
        parser.close()
        return parser.blocks

    @staticmethod
    def _anchor_to_dict(anchor: MaterialAnchor) -> dict[str, Any]:
        """
        转换锚点公开数据

        :param anchor: 材料锚点
        :return:
        """
        return {
            'id': anchor.id,
            'material_id': anchor.material_id,
            'anchor_key': anchor.anchor_key,
            'anchor_type': anchor.anchor_type,
            'text': anchor.text,
            'role': anchor.role,
            'block_id': anchor.block_id,
            'start_offset': anchor.start_offset,
            'end_offset': anchor.end_offset,
            'asset_url': anchor.asset_url,
            'asset_hash': anchor.asset_hash,
            'natural_width': anchor.natural_width,
            'natural_height': anchor.natural_height,
            'bbox': anchor.bbox,
            'polygon': anchor.polygon,
            'table_cell': anchor.table_cell,
            'ocr_confidence': str(anchor.ocr_confidence) if anchor.ocr_confidence is not None else None,
            'source': anchor.source,
            'content_hash': anchor.content_hash,
            'extra_data': anchor.extra_data or {},
        }

    @staticmethod
    def _annotation_anchor_roles(annotation: QuestionInteractionAnnotation) -> dict[str, str]:
        """
        读取题目标注中的锚点角色映射

        :param annotation: 题目交互标注
        :return:
        """
        config = annotation.config if isinstance(annotation.config, dict) else {}
        raw_roles = config.get('anchor_roles')
        if not isinstance(raw_roles, dict):
            return {}
        return {
            str(anchor_id): str(role)
            for anchor_id, role in raw_roles.items()
            if str(anchor_id).isdigit() and str(role).strip()
        }

    @staticmethod
    def _extract_anchor_ids(value: Any) -> set[int]:
        """
        提取答案中的锚点 ID

        :param value: 答案值
        :return:
        """
        if value is None:
            return set()
        if isinstance(value, int):
            return {value}
        if isinstance(value, str) and value.isdigit():
            return {int(value)}
        if isinstance(value, list):
            anchor_ids: set[int] = set()
            for item in value:
                anchor_ids.update(InteractionAnnotationService._extract_anchor_ids(item))
            return anchor_ids
        if isinstance(value, dict):
            anchor_ids: set[int] = set()
            for item in value.values():
                anchor_ids.update(InteractionAnnotationService._extract_anchor_ids(item))
            return anchor_ids
        return set()

    @staticmethod
    async def _validate_material_exists(db: AsyncSession, material_id: int) -> None:
        """
        验证材料存在

        :param db: 数据库会话
        :param material_id: 材料 ID
        :return:
        """
        material = await material_dao.get(db, material_id)
        if not material:
            raise errors.NotFoundError(msg='材料不存在')

    @staticmethod
    async def _validate_question_exists(db: AsyncSession, question_id: int) -> None:
        """
        验证题目存在

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

    @staticmethod
    async def _validate_anchor_scope(
        *,
        db: AsyncSession,
        material_id: int | None,
        candidate_anchor_ids: list[int],
        answer_data: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> None:
        """
        验证锚点范围

        :param db: 数据库会话
        :param material_id: 材料 ID
        :param candidate_anchor_ids: 候选锚点 ID
        :param answer_data: 答案数据
        :return:
        """
        anchor_ids = set(candidate_anchor_ids)
        anchor_ids.update(InteractionAnnotationService._extract_anchor_ids(answer_data.get('correct')))
        anchor_roles = config.get('anchor_roles') if isinstance(config, dict) else None
        if isinstance(anchor_roles, dict):
            anchor_ids.update(
                int(anchor_id)
                for anchor_id in anchor_roles
                if str(anchor_id).isdigit()
            )
        if not anchor_ids:
            return

        anchors = await material_anchor_dao.get_by_ids(db, list(anchor_ids))
        existing_ids = {item.id for item in anchors}
        missing_ids = anchor_ids - existing_ids
        if missing_ids:
            raise errors.NotFoundError(msg=f'锚点不存在: {sorted(missing_ids)}')

        if material_id is None:
            return

        invalid_ids = [item.id for item in anchors if item.material_id != material_id]
        if invalid_ids:
            raise errors.RequestError(msg=f'锚点不属于当前材料: {invalid_ids}')

    async def get_anchor_list(
        self,
        *,
        db: AsyncSession,
        params: MaterialAnchorQueryParam,
    ) -> Sequence[MaterialAnchor]:
        """
        获取材料锚点列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        return await material_anchor_dao.get_list(db, params)

    async def create_anchor(
        self,
        *,
        db: AsyncSession,
        obj: CreateMaterialAnchorParam,
        created_by: int,
    ) -> MaterialAnchor:
        """
        创建材料锚点

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者用户 ID
        :return:
        """
        await self._validate_material_exists(db, obj.material_id)
        anchor = await material_anchor_dao.create(db, obj, created_by=created_by)
        await db.flush()
        return anchor

    async def create_anchors(
        self,
        *,
        db: AsyncSession,
        obj: BatchCreateMaterialAnchorParam,
        created_by: int,
    ) -> list[MaterialAnchor]:
        """
        批量创建材料锚点

        :param db: 数据库会话
        :param obj: 批量创建参数
        :param created_by: 创建者用户 ID
        :return:
        """
        material_ids = {item.material_id for item in obj.items}
        for material_id in material_ids:
            await self._validate_material_exists(db, material_id)

        anchors: list[MaterialAnchor] = []
        for item in obj.items:
            anchor = await material_anchor_dao.create(db, item, created_by=created_by)
            anchors.append(anchor)

        await db.flush()
        return anchors

    async def update_anchor(
        self,
        *,
        db: AsyncSession,
        pk: int,
        obj: UpdateMaterialAnchorParam,
        updated_by: int,
    ) -> int:
        """
        更新材料锚点

        :param db: 数据库会话
        :param pk: 锚点 ID
        :param obj: 更新参数
        :param updated_by: 更新者用户 ID
        :return:
        """
        anchor = await material_anchor_dao.get(db, pk)
        if not anchor:
            raise errors.NotFoundError(msg='锚点不存在')
        return await material_anchor_dao.update(db, pk, obj, updated_by=updated_by)

    async def delete_anchors(self, *, db: AsyncSession, obj: DeleteInteractionIdsParam) -> int:
        """
        删除材料锚点

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await material_anchor_dao.delete(db, obj.ids)

    async def get_annotation_list(
        self,
        *,
        db: AsyncSession,
        params: QuestionInteractionAnnotationQueryParam,
    ) -> Sequence[QuestionInteractionAnnotation]:
        """
        获取题目交互标注列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        return await question_interaction_annotation_dao.get_list(db, params)

    async def create_annotation(
        self,
        *,
        db: AsyncSession,
        obj: CreateQuestionInteractionAnnotationParam,
        created_by: int,
    ) -> QuestionInteractionAnnotation:
        """
        创建题目交互标注

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者用户 ID
        :return:
        """
        await self._validate_question_exists(db, obj.question_id)
        if obj.material_id is not None:
            await self._validate_material_exists(db, obj.material_id)
        await self._validate_anchor_scope(
            db=db,
            material_id=obj.material_id,
            candidate_anchor_ids=obj.candidate_anchor_ids,
            answer_data=obj.answer_data,
            config=obj.config,
        )
        if obj.is_default:
            await question_interaction_annotation_dao.unset_default(
                db,
                question_id=obj.question_id,
                interaction_type=obj.interaction_type,
            )
        annotation = await question_interaction_annotation_dao.create(db, obj, created_by=created_by)
        await db.flush()
        return annotation

    async def update_annotation(
        self,
        *,
        db: AsyncSession,
        pk: int,
        obj: UpdateQuestionInteractionAnnotationParam,
        updated_by: int,
    ) -> int:
        """
        更新题目交互标注

        :param db: 数据库会话
        :param pk: 标注 ID
        :param obj: 更新参数
        :param updated_by: 更新者用户 ID
        :return:
        """
        annotation = await question_interaction_annotation_dao.get(db, pk)
        if not annotation:
            raise errors.NotFoundError(msg='交互标注不存在')

        next_material_id = obj.material_id if obj.material_id is not None else annotation.material_id
        next_candidate_ids = (
            obj.candidate_anchor_ids if obj.candidate_anchor_ids is not None else annotation.candidate_anchor_ids
        )
        next_answer_data = obj.answer_data if obj.answer_data is not None else annotation.answer_data
        next_config = obj.config if obj.config is not None else annotation.config
        if next_material_id is not None:
            await self._validate_material_exists(db, next_material_id)
        await self._validate_anchor_scope(
            db=db,
            material_id=next_material_id,
            candidate_anchor_ids=next_candidate_ids,
            answer_data=next_answer_data,
            config=next_config,
        )

        next_interaction_type = obj.interaction_type or annotation.interaction_type
        if obj.is_default:
            await question_interaction_annotation_dao.unset_default(
                db,
                question_id=annotation.question_id,
                interaction_type=next_interaction_type,
                exclude_id=pk,
            )
        return await question_interaction_annotation_dao.update(db, pk, obj, updated_by=updated_by)

    async def delete_annotations(self, *, db: AsyncSession, obj: DeleteInteractionIdsParam) -> int:
        """
        删除题目交互标注

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await question_interaction_annotation_dao.delete(db, obj.ids)

    async def get_material_blocks(self, *, db: AsyncSession, material_id: int) -> GetMaterialBlocksResult:
        """
        获取材料顺序分块

        :param db: 数据库会话
        :param material_id: 材料 ID
        :return:
        """
        material = await material_dao.get(db, material_id)
        if not material:
            raise errors.NotFoundError(msg='材料不存在')

        return GetMaterialBlocksResult(
            material_id=material.id,
            title=material.title,
            content_hash=self.build_content_hash(material.content),
            blocks=self.build_material_blocks(material.content, title=material.title),
        )

    async def get_material_questions(
        self,
        *,
        db: AsyncSession,
        material_id: int,
    ) -> list[GetMaterialQuestionPreview]:
        """
        获取材料关联题目预览

        :param db: 数据库会话
        :param material_id: 材料 ID
        :return:
        """
        material = await material_dao.get(db, material_id)
        if not material:
            raise errors.NotFoundError(msg='材料不存在')

        questions = await question_dao.get_by_material_id(db, material_id)
        return [
            GetMaterialQuestionPreview(
                id=question.id,
                type=question.type,
                stem=question.stem,
                options=self._normalize_question_options(question.options),
                difficulty=question.difficulty,
                material_ids=[material_id],
            )
            for question in questions
        ]

    async def get_default_runtime_configs(
        self,
        *,
        db: AsyncSession,
        question_ids: list[int],
        interaction_type: str | None = None,
    ) -> dict[int, dict[str, Any]]:
        """
        获取题目默认运行时交互配置

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :param interaction_type: 交互类型
        :return:
        """
        annotations = await question_interaction_annotation_dao.get_default_by_question_ids(
            db,
            question_ids,
            interaction_type=interaction_type,
        )
        selected_annotations: dict[int, QuestionInteractionAnnotation] = {}
        for annotation in annotations:
            if annotation.question_id not in selected_annotations:
                selected_annotations[annotation.question_id] = annotation

        result: dict[int, dict[str, Any]] = {}
        for question_id, annotation in selected_annotations.items():
            public_config = await self._build_public_interaction_config(db=db, annotation=annotation)
            result[question_id] = {
                'annotation': annotation,
                'interaction_config': public_config,
                'answer_data': annotation.answer_data,
            }
        return result

    async def _build_public_interaction_config(
        self,
        *,
        db: AsyncSession,
        annotation: QuestionInteractionAnnotation,
    ) -> dict[str, Any]:
        """
        构建公开交互配置

        :param db: 数据库会话
        :param annotation: 交互标注
        :return:
        """
        anchors = await self._get_public_anchors(db=db, annotation=annotation)
        material_payload = None
        config = dict(annotation.config or {})
        if annotation.material_id is not None:
            material = await material_dao.get(db, annotation.material_id)
            if material:
                content_hash = annotation.content_hash or self.build_content_hash(material.content)
                blocks = self.build_material_blocks(material.content, title=material.title)
                config['blocks'] = blocks
                material_payload = {
                    'id': material.id,
                    'title': material.title,
                    'content': material.content,
                    'content_hash': content_hash,
                    'blocks': blocks,
                }

        anchor_roles = self._annotation_anchor_roles(annotation)
        anchors_payload = []
        for item in anchors:
            payload = self._anchor_to_dict(item)
            payload['role'] = anchor_roles.get(str(item.id))
            anchors_payload.append(payload)

        return {
            'annotation_id': annotation.id,
            'annotation_key': annotation.annotation_key,
            'interaction_type': annotation.interaction_type,
            'title': annotation.title,
            'instruction': annotation.instruction,
            'selection_mode': annotation.selection_mode,
            'material_id': annotation.material_id,
            'material': material_payload,
            'anchors': anchors_payload,
            'candidate_anchor_ids': [item.id for item in anchors],
            'config': config,
        }

    async def _get_public_anchors(
        self,
        *,
        db: AsyncSession,
        annotation: QuestionInteractionAnnotation,
    ) -> Sequence[MaterialAnchor]:
        """
        获取公开候选锚点

        :param db: 数据库会话
        :param annotation: 交互标注
        :return:
        """
        if annotation.candidate_anchor_ids:
            anchors = await material_anchor_dao.get_by_ids(db, annotation.candidate_anchor_ids)
            return [item for item in anchors if item.status == 10]

        if annotation.material_id is None:
            return []

        params = MaterialAnchorQueryParam(material_id=annotation.material_id, status=10)
        return await material_anchor_dao.get_list(db, params)

    @staticmethod
    def _normalize_question_options(options: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """
        规范化题目选项

        :param options: 选项列表
        :return:
        """
        normalized_options: list[dict[str, Any]] = []
        for index, item in enumerate(options or []):
            option_code = str(item.get('option_code') or item.get('code') or '').strip().upper()
            content = str(item.get('content') or '').strip()
            if not option_code or not content:
                continue

            sort_order = item.get('sort_order')
            if isinstance(sort_order, bool) or not isinstance(sort_order, int):
                sort_order = index

            normalized_options.append({
                'option_code': option_code,
                'content': content,
                'sort_order': sort_order,
                'is_active': bool(item.get('is_active', True)),
            })

        return sorted(normalized_options, key=lambda option: (option['sort_order'], option['option_code']))


interaction_annotation_service: InteractionAnnotationService = InteractionAnnotationService()

__all__ = [
    'GetMaterialAnchorDetail',
    'GetQuestionInteractionAnnotationDetail',
    'interaction_annotation_service',
]
