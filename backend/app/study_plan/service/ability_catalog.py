#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.admin.model.category import Category
from backend.app.study_plan.crud import study_ability_catalog_dao, study_ability_category_binding_dao
from backend.app.study_plan.model.ability_profile import StudyAbilityCatalog, StudyAbilityCategoryBinding
from backend.app.study_plan.schema.ability import (
    CreateStudyAbilityCatalogParam,
    CreateStudyAbilityCategoryBindingParam,
    GetStudyAbilityCategoryBindingDetail,
    GetStudyPlanAbilityCatalogItem,
    UpdateStudyAbilityCatalogParam,
    UpdateStudyAbilityCategoryBindingParam,
)
from backend.common.exception import errors


_ABILITY_CATALOG = [
    {
        'key': 'basic_calculation',
        'title': '基础计算练习',
        'description': '训练加减乘除和常用基础运算，打好数量关系与资料分析基础',
        'domain': 'civil_service',
        'category': '数资基础',
        'url': '/pkg/ability/basic-calculation/session/index?typeIndex=0&count=20&order=asc',
        'default_minutes': 10,
        'default_question_count': 20,
        'default_accuracy': 0.8,
        'benchmark_seconds': 22,
        'supports_study_plan': True,
        'supports_result': True,
        'url_base': '/pkg/ability/basic-calculation/session/index',
        'param_schema': {
            'typeIndex': {'type': 'int', 'default': 0, 'min': 0, 'max': 17, 'label': '计算类型'},
            'count': {'type': 'int', 'default': 20, 'min': 1, 'max': 100, 'label': '题数', 'bind_to': 'question_count'},
            'order': {'type': 'enum', 'default': 'asc', 'options': ['asc', 'shuffle'], 'label': '顺序'},
        },
    },
    {
        'key': 'data_analysis_fill_blank',
        'title': '资料分析填空',
        'description': '专项训练资料分析常用公式和估算过程',
        'domain': 'civil_service',
        'category': '资料分析',
        'url': '/pkg/ability/data-analysis/fill-blank/session/index?key=base_value&count=10&order=asc',
        'default_minutes': 12,
        'default_question_count': 10,
        'default_accuracy': 0.75,
        'benchmark_seconds': 45,
        'supports_study_plan': True,
        'supports_result': True,
        'url_base': '/pkg/ability/data-analysis/fill-blank/session/index',
        'param_schema': {
            'key': {'type': 'string', 'default': 'base_value', 'label': '公式类型'},
            'count': {'type': 'int', 'default': 10, 'min': 1, 'max': 100, 'label': '题数', 'bind_to': 'question_count'},
            'order': {'type': 'enum', 'default': 'asc', 'options': ['asc', 'shuffle'], 'label': '顺序'},
        },
    },
    {
        'key': 'data_analysis_practice',
        'title': '资料分析实战',
        'description': '按资料分析题型进行小题组实战训练',
        'domain': 'civil_service',
        'category': '资料分析',
        'url': '/pkg/ability/data-analysis/practice/session/index?type=random&difficulty=normal&count=10&display=text_chart',
        'default_minutes': 15,
        'default_question_count': 10,
        'default_accuracy': 0.7,
        'benchmark_seconds': 50,
        'supports_study_plan': True,
        'supports_result': True,
        'url_base': '/pkg/ability/data-analysis/practice/session/index',
        'param_schema': {
            'type': {'type': 'string', 'default': 'random', 'label': '题型'},
            'difficulty': {'type': 'enum', 'default': 'normal', 'options': ['easy', 'normal', 'hard'], 'label': '难度'},
            'display': {'type': 'enum', 'default': 'text_chart', 'options': ['text_chart', 'formula'], 'label': '展示'},
            'count': {'type': 'int', 'default': 10, 'min': 1, 'max': 100, 'label': '题数', 'bind_to': 'question_count'},
        },
    },
    {
        'key': 'data_analysis_number_locate',
        'title': '资料分析找数训练',
        'description': '在材料图表中快速定位目标数据，支持读题时限抗重复读题训练',
        'domain': 'civil_service',
        'category': '资料分析',
        'url': '/pkg/ability/data-analysis/number-locate/session/index?count=10&readLimit=0',
        'default_minutes': 8,
        'default_question_count': 10,
        'default_accuracy': 0.8,
        'benchmark_seconds': 25,
        'supports_study_plan': True,
        'supports_result': True,
        'url_base': '/pkg/ability/data-analysis/number-locate/session/index',
        'param_schema': {
            'count': {'type': 'int', 'default': 10, 'min': 1, 'max': 50, 'label': '题数', 'bind_to': 'question_count'},
            'readLimit': {'type': 'enum', 'default': 0, 'options': [0, 5, 10, 15], 'label': '读题时限（秒）'},
        },
    },
    {
        'key': 'spatial_cube_box',
        'title': '六面体空间训练',
        'description': '训练六面体相对面、展开图和空间想象能力',
        'domain': 'civil_service',
        'category': '立体能力',
        'url': '/pkg/ability/spatial/cube-box/session/index?mode=opposite&kind=test&count=10',
        'default_minutes': 10,
        'default_question_count': 10,
        'default_accuracy': 0.7,
        'benchmark_seconds': 35,
        'supports_study_plan': True,
        'supports_result': True,
        'url_base': '/pkg/ability/spatial/cube-box/session/index',
        'param_schema': {
            'mode': {'type': 'enum', 'default': 'opposite', 'options': ['opposite', 'net'], 'label': '模式'},
            'kind': {'type': 'enum', 'default': 'test', 'options': ['training', 'test'], 'label': '类型'},
            'count': {'type': 'int', 'default': 10, 'min': 1, 'max': 50, 'label': '题数', 'bind_to': 'question_count'},
        },
    },
]


def list_ability_catalog(domain: str | None = None) -> list[GetStudyPlanAbilityCatalogItem]:
    """
    获取静态能力目录

    :param domain: 业务领域
    :return:
    """
    items = _ABILITY_CATALOG
    if domain:
        items = [item for item in items if item['domain'] == domain]

    return [GetStudyPlanAbilityCatalogItem(**item) for item in items]


def get_ability_catalog_item(key: str) -> GetStudyPlanAbilityCatalogItem | None:
    """
    按 key 获取静态能力目录项

    :param key: 能力标识
    :return:
    """
    for item in _ABILITY_CATALOG:
        if item['key'] == key:
            return GetStudyPlanAbilityCatalogItem(**item)
    return None


async def list_ability_catalog_with_db(
    db: AsyncSession,
    domain: str | None = None,
    keyword: str | None = None,
    include_inactive: bool = False,
    include_static_fallback: bool = True,
) -> list[GetStudyPlanAbilityCatalogItem]:
    """
    获取数据库能力目录

    :param db: 数据库会话
    :param domain: 业务领域
    :param keyword: 搜索关键词
    :param include_inactive: 是否包含停用项
    :param include_static_fallback: 是否包含静态兜底项
    :return:
    """
    db_items = await study_ability_catalog_dao.list_catalog(
        db,
        domain=domain,
        keyword=keyword,
        include_inactive=include_inactive,
    )
    result = [_build_catalog_item(item) for item in db_items]
    if not include_static_fallback:
        return result

    suppress_items = db_items
    if not include_inactive:
        suppress_items = await study_ability_catalog_dao.list_catalog(
            db,
            domain=domain,
            include_inactive=True,
        )
    existing_keys = {(item.domain, item.ability_key) for item in suppress_items}
    for item in list_ability_catalog(domain):
        if keyword and keyword not in item.key and keyword not in item.title and keyword not in item.category:
            continue
        if (item.domain, item.key) in existing_keys:
            continue
        item.is_persisted = False
        result.append(item)

    return result


async def create_ability_catalog(
    db: AsyncSession,
    param: CreateStudyAbilityCatalogParam,
    created_by: int,
) -> GetStudyPlanAbilityCatalogItem:
    """
    创建能力目录

    :param db: 数据库会话
    :param param: 创建参数
    :param created_by: 创建者 ID
    :return:
    """
    existing = await study_ability_catalog_dao.get_by_key(db, param.ability_key, param.domain)
    if existing is not None:
        raise errors.ConflictError(msg='能力目录已存在')

    catalog = StudyAbilityCatalog(
        ability_key=param.ability_key,
        title=param.title,
        category=param.category,
        url=param.url,
        domain=param.domain,
        description=param.description,
        default_minutes=param.default_minutes,
        default_question_count=param.default_question_count,
        default_accuracy=_to_decimal(param.default_accuracy, '0.0001'),
        benchmark_seconds=_to_decimal(param.benchmark_seconds, '0.01'),
        supports_study_plan=param.supports_study_plan,
        supports_result=param.supports_result,
        is_active=param.is_active,
        extra=param.extra,
        url_base=param.url_base,
        param_schema=param.param_schema,
        created_by=created_by,
    )
    db.add(catalog)
    await db.flush()
    return _build_catalog_item(catalog)


async def update_ability_catalog(
    db: AsyncSession,
    catalog_id: int,
    param: UpdateStudyAbilityCatalogParam,
    updated_by: int,
) -> GetStudyPlanAbilityCatalogItem:
    """
    更新能力目录

    :param db: 数据库会话
    :param catalog_id: 目录 ID
    :param param: 更新参数
    :param updated_by: 修改者 ID
    :return:
    """
    catalog = await study_ability_catalog_dao.get(db, catalog_id)
    if catalog is None:
        raise errors.NotFoundError(msg='能力目录不存在')

    fields = param.model_dump(exclude_unset=True)
    if 'default_accuracy' in fields:
        fields['default_accuracy'] = _to_decimal(fields['default_accuracy'], '0.0001')
    if 'benchmark_seconds' in fields:
        fields['benchmark_seconds'] = _to_decimal(fields['benchmark_seconds'], '0.01')
    if fields:
        fields['updated_by'] = updated_by
        await study_ability_catalog_dao.update_model(db, catalog_id, fields)

    refreshed = await study_ability_catalog_dao.get(db, catalog_id)
    return _build_catalog_item(refreshed)


async def delete_ability_catalog(db: AsyncSession, catalog_id: int) -> None:
    """
    删除能力目录

    :param db: 数据库会话
    :param catalog_id: 目录 ID
    :return:
    """
    catalog = await study_ability_catalog_dao.get(db, catalog_id)
    if catalog is None:
        raise errors.NotFoundError(msg='能力目录不存在')
    await study_ability_catalog_dao.delete_model(db, catalog_id)


async def list_ability_bindings(
    db: AsyncSession,
    ability_key: str | None = None,
    category_id: int | None = None,
    role: str | None = None,
) -> list[GetStudyAbilityCategoryBindingDetail]:
    """
    获取能力分类绑定

    :param db: 数据库会话
    :param ability_key: 能力标识
    :param category_id: 分类 ID
    :param role: 绑定角色
    :return:
    """
    bindings = await study_ability_category_binding_dao.list_bindings(
        db,
        ability_key=ability_key,
        category_id=category_id,
        role=role,
    )
    categories = await _list_binding_categories(db, [binding.category_id for binding in bindings])
    return [_build_binding_detail(binding, categories.get(binding.category_id)) for binding in bindings]


async def create_ability_binding(
    db: AsyncSession,
    param: CreateStudyAbilityCategoryBindingParam,
    created_by: int,
) -> GetStudyAbilityCategoryBindingDetail:
    """
    创建能力分类绑定

    :param db: 数据库会话
    :param param: 创建参数
    :param created_by: 创建者 ID
    :return:
    """
    await _ensure_catalog_key_exists(db, param.ability_key)
    category = await _get_valid_category(db, param.category_id)
    await _ensure_binding_unique(
        db,
        ability_key=param.ability_key,
        mode=param.mode,
        category_id=param.category_id,
        role=param.role,
    )

    binding = StudyAbilityCategoryBinding(
        ability_key=param.ability_key,
        mode=param.mode,
        category_id=param.category_id,
        role=param.role,
        weight=_to_decimal(param.weight, '0.0001') or Decimal('1'),
        is_primary=param.is_primary,
        source=param.source,
        confidence=_to_decimal(param.confidence, '0.0001') or Decimal('1'),
        created_by=created_by,
    )
    db.add(binding)
    await db.flush()
    return _build_binding_detail(binding, category)


async def update_ability_binding(
    db: AsyncSession,
    binding_id: int,
    param: UpdateStudyAbilityCategoryBindingParam,
    updated_by: int,
) -> GetStudyAbilityCategoryBindingDetail:
    """
    更新能力分类绑定

    :param db: 数据库会话
    :param binding_id: 绑定 ID
    :param param: 更新参数
    :param updated_by: 修改者 ID
    :return:
    """
    binding = await study_ability_category_binding_dao.get(db, binding_id)
    if binding is None:
        raise errors.NotFoundError(msg='能力分类绑定不存在')

    fields = param.model_dump(exclude_unset=True)
    category_id = fields.get('category_id', binding.category_id)
    role = fields.get('role', binding.role)
    mode = fields.get('mode', binding.mode)
    if 'category_id' in fields:
        await _get_valid_category(db, category_id)

    await _ensure_binding_unique(
        db,
        ability_key=binding.ability_key,
        mode=mode,
        category_id=category_id,
        role=role,
        exclude_id=binding_id,
    )

    if 'weight' in fields:
        fields['weight'] = _to_decimal(fields['weight'], '0.0001')
    if 'confidence' in fields:
        fields['confidence'] = _to_decimal(fields['confidence'], '0.0001')
    if fields:
        fields['updated_by'] = updated_by
        await study_ability_category_binding_dao.update_model(db, binding_id, fields)

    refreshed = await study_ability_category_binding_dao.get(db, binding_id)
    category = await _get_category(db, refreshed.category_id)
    return _build_binding_detail(refreshed, category)


async def delete_ability_binding(db: AsyncSession, binding_id: int) -> None:
    """
    删除能力分类绑定

    :param db: 数据库会话
    :param binding_id: 绑定 ID
    :return:
    """
    binding = await study_ability_category_binding_dao.get(db, binding_id)
    if binding is None:
        raise errors.NotFoundError(msg='能力分类绑定不存在')
    await study_ability_category_binding_dao.delete_model(db, binding_id)


def _build_catalog_item(catalog: StudyAbilityCatalog) -> GetStudyPlanAbilityCatalogItem:
    """
    构建能力目录响应

    :param catalog: 能力目录
    :return:
    """
    return GetStudyPlanAbilityCatalogItem(
        id=catalog.id,
        key=catalog.ability_key,
        title=catalog.title,
        description=catalog.description or '',
        domain=catalog.domain,
        category=catalog.category,
        url=catalog.url,
        default_minutes=catalog.default_minutes,
        default_question_count=catalog.default_question_count,
        default_accuracy=float(catalog.default_accuracy) if catalog.default_accuracy is not None else None,
        benchmark_seconds=float(catalog.benchmark_seconds) if catalog.benchmark_seconds is not None else None,
        supports_study_plan=catalog.supports_study_plan,
        supports_result=catalog.supports_result,
        is_active=catalog.is_active,
        is_persisted=True,
        extra=catalog.extra,
        url_base=catalog.url_base,
        param_schema=catalog.param_schema,
    )


def _build_binding_detail(
    binding: StudyAbilityCategoryBinding,
    category: Category | None,
) -> GetStudyAbilityCategoryBindingDetail:
    """
    构建绑定详情

    :param binding: 分类绑定
    :param category: 系统分类
    :return:
    """
    return GetStudyAbilityCategoryBindingDetail(
        id=binding.id,
        ability_key=binding.ability_key,
        mode=binding.mode,
        category_id=binding.category_id,
        category_name=category.name if category is not None else None,
        category_code=category.code if category is not None else None,
        category_type=category.type if category is not None else None,
        role=binding.role,
        weight=float(binding.weight),
        is_primary=binding.is_primary,
        source=binding.source,
        confidence=float(binding.confidence),
        created_time=binding.created_time,
        updated_time=binding.updated_time,
    )


async def _ensure_catalog_key_exists(db: AsyncSession, ability_key: str) -> None:
    """
    校验能力标识存在

    :param db: 数据库会话
    :param ability_key: 能力标识
    :return:
    """
    stmt = (
        select(StudyAbilityCatalog.id)
        .where(
            StudyAbilityCatalog.ability_key == ability_key,
            StudyAbilityCatalog.deleted == 0,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        return
    if get_ability_catalog_item(ability_key) is not None:
        return
    raise errors.NotFoundError(msg='能力目录不存在，请先维护能力目录')


async def _get_valid_category(db: AsyncSession, category_id: int) -> Category:
    """
    获取有效分类

    :param db: 数据库会话
    :param category_id: 分类 ID
    :return:
    """
    category = await _get_category(db, category_id)
    if category is None:
        raise errors.NotFoundError(msg='分类不存在')
    if not category.status:
        raise errors.RequestError(msg='分类已停用')
    return category


async def _get_category(db: AsyncSession, category_id: int) -> Category | None:
    """
    获取分类

    :param db: 数据库会话
    :param category_id: 分类 ID
    :return:
    """
    category = await category_dao.get(db, category_id)
    if category is None or category.deleted != 0:
        return None
    return category


async def _ensure_binding_unique(
    db: AsyncSession,
    *,
    ability_key: str,
    mode: str | None,
    category_id: int,
    role: str,
    exclude_id: int | None = None,
) -> None:
    """
    校验绑定唯一

    :param db: 数据库会话
    :param ability_key: 能力标识
    :param mode: 练习模式
    :param category_id: 分类 ID
    :param role: 绑定角色
    :param exclude_id: 排除绑定 ID
    :return:
    """
    duplicate = await study_ability_category_binding_dao.get_duplicate(
        db,
        ability_key=ability_key,
        mode=mode,
        category_id=category_id,
        role=role,
        exclude_id=exclude_id,
    )
    if duplicate is not None:
        raise errors.ConflictError(msg='能力分类绑定已存在')


async def _list_binding_categories(db: AsyncSession, category_ids: list[int]) -> dict[int, Category]:
    """
    获取绑定分类映射

    :param db: 数据库会话
    :param category_ids: 分类 ID 列表
    :return:
    """
    ids = sorted(set(category_ids))
    if not ids:
        return {}

    stmt = select(Category).where(Category.id.in_(ids), Category.deleted == 0)
    result = await db.execute(stmt)
    return {category.id: category for category in result.scalars().all()}


def _to_decimal(value: object, quant: str) -> Decimal | None:
    """
    转换 Decimal

    :param value: 原始值
    :param quant: 量化精度
    :return:
    """
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal(quant), rounding=ROUND_HALF_UP)
