import hashlib
import json
import re

from collections.abc import Sequence
from html import unescape
from html.parser import HTMLParser
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.cache.material_cache import material_blocks_cache
from backend.app.question_bank_v2.crud.crud_material import (
    material_anchor_dao,
    material_dao,
    material_revision_dao,
)
from backend.app.question_bank_v2.crud.crud_question import question_dao
from backend.app.question_bank_v2.schema.material import (
    CreateMaterialAnchorParam,
    CreateMaterialParam,
    CreateMaterialRevisionParam,
    GetMaterialAnchorDetail,
    GetMaterialDetail,
    GetMaterialListItem,
    GetMaterialRevisionDetail,
    QuestionMaterialParam,
    UpdateMaterialAnchorParam,
    UpdateMaterialParam,
    UpdateMaterialRevisionParam,
)
from backend.common.exception import errors
from backend.utils.timezone import timezone


class MaterialService:
    """共享材料内容服务类"""

    @staticmethod
    def build_content_hash(content: str) -> str:
        raw = json.dumps({'content': content}, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def build_material_blocks(content: str, *, title: str) -> list[dict[str, Any]]:
        parser = MaterialHtmlBlockParser(material_title=title)
        parser.feed(content)
        parser.close()
        return parser.blocks

    @staticmethod
    async def build_mapping_page(rows: list[Any]) -> list[dict[str, Any]]:
        """将 SQLAlchemy 行转换为可序列化映射"""
        return [dict(row._mapping if hasattr(row, '_mapping') else row) for row in rows]

    @staticmethod
    async def get_question_previews(
        *,
        db: AsyncSession,
        material_id: int,
    ) -> list[dict[str, Any]]:
        """获取关联指定材料的所有题目预览"""
        return await question_dao.get_by_material(db, material_id=material_id)

    @staticmethod
    async def get_question_previews_select(*, db: AsyncSession, material_id: int) -> Select:
        if await material_dao.get(db, material_id) is None:
            raise errors.NotFoundError(msg='材料不存在')
        return question_dao.get_by_material_select(material_id=material_id)

    @staticmethod
    async def get_blocks(
        *,
        db: AsyncSession,
        material_id: int,
        revision_id: int,
    ) -> dict[str, Any]:
        async def factory() -> dict[str, Any]:
            revision = await material_revision_dao.get(db, revision_id, material_id=material_id)
            if revision is None:
                raise errors.NotFoundError(msg='材料版本不存在')
            content_hash = MaterialService.build_content_hash(revision.content)
            return {
                'material_id': material_id,
                'revision_id': revision_id,
                'title': revision.title,
                'content_hash': content_hash,
                'revision_status': revision.status,
                'blocks': MaterialService.build_material_blocks(revision.content, title=revision.title),
            }

        data = await material_blocks_cache.get_or_set(
            material_id,
            revision_id,
            factory=factory,
            should_cache=lambda item: item['revision_status'] in {'published', 'retired'},
        )
        data.pop('revision_status', None)
        return data

    @staticmethod
    async def invalidate_blocks_cache(*, material_id: int, revision_id: int) -> None:
        await material_blocks_cache.invalidate(material_id, revision_id)

    @staticmethod
    def _build_revision(revision: Any) -> GetMaterialRevisionDetail:
        """组装材料版本详情"""
        return GetMaterialRevisionDetail(
            id=revision.id,
            material_id=revision.material_id,
            revision_no=revision.revision_no,
            title=revision.title,
            content=revision.content,
            content_format=revision.content_format,
            structured_data=revision.structured_data,
            source_name=revision.source_name,
            source_url=revision.source_url,
            content_hash=revision.content_hash,
            status=revision.status,
            published_by=revision.published_by,
            published_time=revision.published_time,
            created_by=revision.created_by,
            updated_by=revision.updated_by,
            created_time=revision.created_time,
            updated_time=revision.updated_time,
        )

    @staticmethod
    async def _build_detail(
        *,
        db: AsyncSession,
        material: Any,
        revision_id: int | None = None,
    ) -> GetMaterialDetail:
        """组装材料稳定身份和指定版本详情"""
        if revision_id is not None:
            revision = await material_revision_dao.get(db, revision_id, material_id=material.id)
        else:
            revision = await material_revision_dao.get_latest(db, material.id)
        return GetMaterialDetail(
            id=material.id,
            code=material.code,
            current_revision_id=material.current_revision_id,
            status=material.status,
            revision=MaterialService._build_revision(revision) if revision is not None else None,
            created_by=material.created_by,
            updated_by=material.updated_by,
            created_time=material.created_time,
            updated_time=material.updated_time,
        )

    @staticmethod
    def _content_hash(revision: GetMaterialRevisionDetail) -> str:
        """计算材料版本完整权威内容哈希"""
        payload = revision.model_dump(
            mode='json',
            include={
                'title',
                'content',
                'content_format',
                'structured_data',
                'source_name',
                'source_url',
            },
        )
        raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    async def ensure_references(
        *,
        db: AsyncSession,
        items: Sequence[QuestionMaterialParam],
        publishable: bool = False,
    ) -> None:
        """校验题目引用的材料版本存在且在发布时可继续使用"""
        seen: set[tuple[int, str]] = set()
        for item in items:
            relation_key = (item.material_id, item.role)
            if relation_key in seen:
                raise errors.RequestError(msg='同一题目版本不能以相同用途重复关联同一材料')
            seen.add(relation_key)
        reference_keys = {(item.material_id, item.material_revision_id) for item in items}
        states = await material_revision_dao.get_reference_states(db, list(reference_keys))
        if len(states) != len(reference_keys):
            raise errors.NotFoundError(msg='关联材料或材料版本不存在')
        if publishable:
            for reference_key in reference_keys:
                state = states.get(reference_key)
                if state is None:
                    raise errors.NotFoundError(msg='关联材料或材料版本不存在')
                if state['material_status'] != 'active':
                    raise errors.ConflictError(msg='已禁用或归档材料不能用于发布新题目版本')
                if state['revision_status'] not in {'published', 'retired'} or state['content_hash'] is None:
                    raise errors.ConflictError(msg='题目关联的材料版本尚未发布')

    @staticmethod
    async def get(*, db: AsyncSession, pk: int, revision_id: int | None = None) -> GetMaterialDetail:
        """获取材料管理详情"""
        material = await material_dao.get(db, pk)
        if material is None:
            raise errors.NotFoundError(msg='材料不存在')
        detail = await MaterialService._build_detail(db=db, material=material, revision_id=revision_id)
        if revision_id is not None and detail.revision is None:
            raise errors.NotFoundError(msg='材料版本不存在')
        return detail

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        status: str | None = None,
        revision_status: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[GetMaterialListItem]:
        """获取材料管理列表"""
        rows = await material_dao.get_list(
            db,
            status=status,
            revision_status=revision_status,
            keyword=keyword,
            offset=offset,
            limit=limit,
        )
        return [GetMaterialListItem(**row) for row in rows]

    @staticmethod
    def get_list_select(
        *,
        status: str | None = None,
        revision_status: str | None = None,
        keyword: str | None = None,
    ) -> Select:
        """获取材料管理列表 Select 查询句"""
        return material_dao.get_list_select(
            status=status,
            revision_status=revision_status,
            keyword=keyword,
        )

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateMaterialParam, created_by: int) -> GetMaterialDetail:
        """创建材料及首个草稿版本"""
        if await material_dao.get_by_code(db, obj.code):
            raise errors.ConflictError(msg='材料编码已存在')
        material = await material_dao.create(
            db,
            code=obj.code,
            status=obj.status,
            created_by=created_by,
        )
        revision = await material_revision_dao.create(
            db,
            material_id=material.id,
            revision_no=1,
            obj=obj.revision,
            created_by=created_by,
        )
        return await MaterialService._build_detail(db=db, material=material, revision_id=revision.id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateMaterialParam, updated_by: int) -> GetMaterialDetail:
        """更新材料稳定身份"""
        material = await material_dao.get(db, pk)
        if material is None:
            raise errors.NotFoundError(msg='材料不存在')
        data = obj.model_dump(exclude_unset=True)
        if 'code' in data and data['code'] != material.code:
            existing = await material_dao.get_by_code(db, data['code'])
            if existing is not None and existing.id != pk:
                raise errors.ConflictError(msg='材料编码已存在')
        if data:
            data['updated_by'] = updated_by
            await material_dao.update(db, pk, data)
        material = await material_dao.get(db, pk)
        return await MaterialService._build_detail(db=db, material=material)

    @staticmethod
    async def get_revisions(*, db: AsyncSession, material_id: int) -> list[GetMaterialRevisionDetail]:
        """获取材料全部版本"""
        if await material_dao.get(db, material_id) is None:
            raise errors.NotFoundError(msg='材料不存在')
        revisions = await material_revision_dao.get_all(db, material_id)
        return [MaterialService._build_revision(item) for item in revisions]

    @staticmethod
    async def get_revisions_select(*, db: AsyncSession, material_id: int) -> Select:
        if await material_dao.get(db, material_id) is None:
            raise errors.NotFoundError(msg='材料不存在')
        return material_revision_dao.get_list_select(material_id=material_id)

    @staticmethod
    async def create_revision(
        *,
        db: AsyncSession,
        material_id: int,
        obj: CreateMaterialRevisionParam,
        created_by: int,
    ) -> GetMaterialRevisionDetail:
        """创建材料草稿版本"""
        material = await material_dao.get(db, material_id, for_update=True)
        if material is None:
            raise errors.NotFoundError(msg='材料不存在')
        revision_no = await material_revision_dao.get_next_revision_no(db, material_id)
        revision = await material_revision_dao.create(
            db,
            material_id=material_id,
            revision_no=revision_no,
            obj=obj,
            created_by=created_by,
        )
        # 如果存在旧版本，自动将旧版本的有效锚点继承复制到新草稿版本中
        prev_revision_id = material.current_revision_id
        if prev_revision_id is None:
            latest = await material_revision_dao.get_latest(db, material_id)
            if latest is not None and latest.id != revision.id:
                prev_revision_id = latest.id

        if prev_revision_id is not None:
            prev_anchors = await material_anchor_dao.get_all(db, material_revision_id=prev_revision_id)
            inherited = [
                CreateMaterialAnchorParam(
                    anchor_key=old.anchor_key,
                    anchor_type=old.anchor_type,
                    block_id=old.block_id,
                    text=old.text,
                    start_offset=old.start_offset,
                    end_offset=old.end_offset,
                    asset_id=old.asset_id,
                    bbox=old.bbox,
                    polygon=old.polygon,
                    table_cell=old.table_cell,
                    semantic_role=old.semantic_role,
                    source=old.source,
                    confidence=old.confidence,
                    status='active',
                    extra_data=dict(old.extra_data or {}),
                )
                for old in prev_anchors
                if old.status == 'active'
            ]
            await material_anchor_dao.create_all(
                db,
                material_id=material_id,
                material_revision_id=revision.id,
                content_hash=revision.content_hash,
                items=inherited,
                user_id=created_by,
            )
        return MaterialService._build_revision(revision)

    @staticmethod
    async def update_revision(
        *,
        db: AsyncSession,
        material_id: int,
        revision_id: int,
        obj: UpdateMaterialRevisionParam,
        updated_by: int,
    ) -> GetMaterialRevisionDetail:
        """更新材料草稿版本"""
        revision = await material_revision_dao.get(
            db,
            revision_id,
            material_id=material_id,
            for_update=True,
        )
        if revision is None:
            raise errors.NotFoundError(msg='材料版本不存在')
        if revision.status != 'draft':
            raise errors.ConflictError(msg='已发布或已退役材料版本不可修改')
        data = obj.model_dump(exclude_unset=True)
        if data:
            data['updated_by'] = updated_by
            await material_revision_dao.update(db, revision_id, data)
        revision = await material_revision_dao.get(db, revision_id, material_id=material_id)
        return MaterialService._build_revision(revision)

    @staticmethod
    async def publish_revision(
        *,
        db: AsyncSession,
        material_id: int,
        revision_id: int,
        published_by: int,
    ) -> GetMaterialRevisionDetail:
        """发布材料版本并原子切换当前版本"""
        material = await material_dao.get(db, material_id, for_update=True)
        if material is None:
            raise errors.NotFoundError(msg='材料不存在')
        if material.status != 'active':
            raise errors.ConflictError(msg='仅启用状态材料可以发布版本')
        revision = await material_revision_dao.get(
            db,
            revision_id,
            material_id=material_id,
            for_update=True,
        )
        if revision is None:
            raise errors.NotFoundError(msg='材料版本不存在')
        if revision.status != 'draft':
            raise errors.ConflictError(msg='仅草稿材料版本可以发布')

        detail = MaterialService._build_revision(revision)
        content_hash = MaterialService._content_hash(detail)
        anchors = await material_anchor_dao.get_all(db, material_revision_id=revision_id)
        if any(anchor.status == 'active' and anchor.content_hash != content_hash for anchor in anchors):
            raise errors.ConflictError(msg='材料内容已变化，请重新校准活动锚点后再发布')
        now = timezone.now()
        if material.current_revision_id is not None and material.current_revision_id != revision_id:
            await material_revision_dao.update_model_by_column(
                db,
                {'status': 'retired', 'updated_by': published_by},
                id=material.current_revision_id,
                material_id=material_id,
                deleted=0,
                status='published',
            )
        await material_revision_dao.update_model_by_column(
            db,
            {
                'status': 'published',
                'content_hash': content_hash,
                'published_by': published_by,
                'published_time': now,
                'updated_by': published_by,
            },
            id=revision_id,
            material_id=material_id,
            deleted=0,
            status='draft',
        )
        await material_dao.update(
            db,
            material_id,
            {'current_revision_id': revision_id, 'updated_by': published_by},
        )
        revision = await material_revision_dao.get(db, revision_id, material_id=material_id)
        return MaterialService._build_revision(revision)

    @staticmethod
    async def get_anchors(
        *,
        db: AsyncSession,
        material_id: int,
        revision_id: int,
    ) -> list[GetMaterialAnchorDetail]:
        """获取材料版本全部锚点"""
        revision = await material_revision_dao.get(db, revision_id, material_id=material_id)
        if revision is None:
            raise errors.NotFoundError(msg='材料版本不存在')
        anchors = await material_anchor_dao.get_all(db, material_revision_id=revision_id)
        return [GetMaterialAnchorDetail.model_validate(item, from_attributes=True) for item in anchors]

    @staticmethod
    async def get_anchors_select(*, db: AsyncSession, material_id: int, revision_id: int) -> Select:
        if await material_revision_dao.get(db, revision_id, material_id=material_id) is None:
            raise errors.NotFoundError(msg='材料版本不存在')
        return material_anchor_dao.get_list_select(material_revision_id=revision_id)

    @staticmethod
    async def create_anchor(
        *,
        db: AsyncSession,
        material_id: int,
        revision_id: int,
        obj: CreateMaterialAnchorParam,
        user_id: int,
    ) -> GetMaterialAnchorDetail:
        """在材料草稿版本上创建单个锚点"""
        anchors = await MaterialService.create_anchors(
            db=db,
            material_id=material_id,
            revision_id=revision_id,
            obj_list=[obj],
            user_id=user_id,
        )
        return anchors[0]

    @staticmethod
    async def create_anchors(
        *,
        db: AsyncSession,
        material_id: int,
        revision_id: int,
        obj_list: list[CreateMaterialAnchorParam],
        user_id: int,
    ) -> list[GetMaterialAnchorDetail]:
        """在材料草稿版本上批量创建锚点，整个过程。一个失败则整批失败。"""
        if not obj_list:
            return []
        revision = await material_revision_dao.get(db, revision_id, material_id=material_id)
        if revision is None:
            raise errors.NotFoundError(msg='材料版本不存在')
        if revision.status not in {'draft', 'published'}:
            raise errors.ConflictError(msg='当前材料版本状态不允许编辑锚点')
        content_hash = MaterialService._content_hash(MaterialService._build_revision(revision))
        anchor_keys = [obj.anchor_key for obj in obj_list]
        if len(anchor_keys) != len(set(anchor_keys)):
            raise errors.ConflictError(msg='批量创建中存在重复锚点键')
        existing = await material_anchor_dao.get_existing_keys(
            db,
            material_revision_id=revision_id,
            anchor_keys=anchor_keys,
        )
        if existing:
            raise errors.ConflictError(msg=f'材料版本内锚点键已存在：{min(existing)}')
        anchors = await material_anchor_dao.create_all(
            db,
            material_id=material_id,
            material_revision_id=revision_id,
            content_hash=content_hash,
            items=obj_list,
            user_id=user_id,
        )
        return [GetMaterialAnchorDetail.model_validate(item, from_attributes=True) for item in anchors]

    @staticmethod
    async def update_anchor(
        *,
        db: AsyncSession,
        material_id: int,
        revision_id: int,
        anchor_id: int,
        obj: UpdateMaterialAnchorParam,
        user_id: int,
    ) -> GetMaterialAnchorDetail:
        """更新材料草稿版本锚点并刷新内容校准哈希"""
        revision = await material_revision_dao.get(db, revision_id, material_id=material_id)
        if revision is None:
            raise errors.NotFoundError(msg='材料版本不存在')
        if revision.status not in {'draft', 'published'}:
            raise errors.ConflictError(msg='当前材料版本状态不允许更新锚点')
        anchor = await material_anchor_dao.get(
            db,
            anchor_id,
            material_id=material_id,
            material_revision_id=revision_id,
        )
        if anchor is None:
            raise errors.NotFoundError(msg='材料锚点不存在')
        data = obj.model_dump(exclude_unset=True)
        if 'anchor_key' in data and data['anchor_key'] != anchor.anchor_key:
            existing = await material_anchor_dao.get_by_key(
                db,
                material_revision_id=revision_id,
                anchor_key=data['anchor_key'],
            )
            if existing is not None and existing.id != anchor_id:
                raise errors.ConflictError(msg='材料版本内锚点键已存在')
        merged = {
            key: getattr(anchor, key)
            for key in (
                'anchor_key',
                'anchor_type',
                'text',
                'semantic_role',
                'block_id',
                'start_offset',
                'end_offset',
                'asset_id',
                'bbox',
                'polygon',
                'table_cell',
                'source',
                'confidence',
                'status',
                'extra_data',
            )
        }
        merged.update(data)
        validated = CreateMaterialAnchorParam(**merged)
        update_data = validated.model_dump()
        update_data.update({
            'content_hash': MaterialService._content_hash(MaterialService._build_revision(revision)),
            'updated_by': user_id,
        })
        await material_anchor_dao.update(db, anchor_id, data=update_data)
        anchor = await material_anchor_dao.get(
            db,
            anchor_id,
            material_id=material_id,
            material_revision_id=revision_id,
        )
        return GetMaterialAnchorDetail.model_validate(anchor, from_attributes=True)

    @staticmethod
    async def delete_anchor(
        *,
        db: AsyncSession,
        material_id: int,
        revision_id: int,
        anchor_id: int,
    ) -> None:
        """删除未被交互定义引用的材料草稿锚点"""
        revision = await material_revision_dao.get(db, revision_id, material_id=material_id)
        if revision is None:
            raise errors.NotFoundError(msg='材料版本不存在')
        if revision.status not in {'draft', 'published'}:
            raise errors.ConflictError(msg='当前材料版本状态不允许删除锚点')
        anchor = await material_anchor_dao.get(
            db,
            anchor_id,
            material_id=material_id,
            material_revision_id=revision_id,
        )
        if anchor is None:
            return
        if await material_anchor_dao.is_referenced(db, anchor_id=anchor_id):
            raise errors.ConflictError(msg='材料锚点仍被交互定义引用，不能删除')
        await material_anchor_dao.delete_model(db, anchor_id)


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
        tag_name = tag.lower()
        if tag_name in self.block_tags:
            self._append_break()

    def handle_data(self, data: str) -> None:
        if data:
            self.text_parts.append(unescape(data))

    def close(self) -> None:
        super().close()
        self._flush_text()

    def _append_break(self) -> None:
        if self.text_parts and self.text_parts[-1] != '\n':
            self.text_parts.append('\n')

    def _append_image(self, attrs: list[tuple[str, str | None]]) -> None:
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
        content = self._normalize_text(''.join(self.text_parts))
        self.text_parts = []
        if not content:
            return
        self.text_count += 1
        self.blocks.append({
            'id': f'text-{self.text_count}',
            'type': 'text',
            'title': self.material_title if self.text_count == 1 else '材料',
            'content': content,
            'sort_order': len(self.blocks) + 1,
        })

    @staticmethod
    def _get_image_url(attrs: dict[str, str]) -> str:
        for key in ('src', '_src', 'data-src', 'data-original', 'url'):
            value = attrs.get(key)
            if value:
                return value.strip()
        return ''

    @staticmethod
    def _get_dimension(attrs: dict[str, str], key: str) -> float | None:
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
        if not value:
            return None
        match = re.search(r'[0-9.]+', value)
        if not match:
            return None
        return float(match.group(0))

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = value.replace('\xa0', ' ').replace('\r', '\n')
        lines = []
        for line in normalized.split('\n'):
            text = re.sub(r'[ \t\f\v]+', ' ', line).strip()
            if text:
                lines.append(text)
        return '\n'.join(lines)


material_service: MaterialService = MaterialService()
