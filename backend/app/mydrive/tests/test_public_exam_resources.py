#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公开资源列表公考筛选与详情提取码测试。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa

from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.admin.model.category import Category
from backend.app.mydrive.crud.crud_resource import mydrive_resource_dao
from backend.app.mydrive.model.account import MyDriveAccount
from backend.app.mydrive.model.resource import MyDriveResource, MyDriveResourceShare
from backend.app.mydrive.schema.resource import GetMyDriveResourceListParam
from backend.app.mydrive.service.resource_service import MyDriveResourceService, mydrive_resource_service


@dataclass
class SqliteFixture:
    """内存 SQLite 数据源。"""

    engine: sa.Engine
    ids: dict[str, int]


def _create_engine() -> sa.Engine:
    engine = sa.create_engine(
        'sqlite://',
        poolclass=StaticPool,
        connect_args={'check_same_thread': False},
    )
    # 仅调整独立 DDL 副本，不注册全局编译器，避免污染同一 pytest 进程的其他用例。
    metadata = sa.MetaData()
    for table in Category.__table__.metadata.tables.values():
        table.to_metadata(metadata)
    tables = [
        metadata.tables[model.__tablename__]
        for model in (
            Category,
            MyDriveAccount,
            MyDriveResource,
            MyDriveResourceShare,
        )
    ]
    for table in tables:
        for column in table.columns:
            if isinstance(column.type, sa.BigInteger):
                column.type = sa.Integer()
            elif isinstance(column.type, JSONB):
                column.type = sa.JSON()
    metadata.create_all(engine, tables=tables)
    return engine


def _build_database(*, include_gongkao: bool = True) -> SqliteFixture:
    """构造真实落库的分类、资源与分享数据。"""
    engine = _create_engine()
    ids: dict[str, int] = {}

    with Session(engine) as session:

        def create_category(
            key: str,
            name: str,
            *,
            parent: Category | None = None,
            category_type: str = 'resource_exam',
            code: str | None = None,
            status: bool = True,
        ) -> Category:
            category = Category(
                app_code='mydrive',
                name=name,
                type=category_type,
                code=code,
                parent_id=parent.id if parent else None,
                level=1 if parent is None else parent.level + 1,
                status=status,
                created_by=1,
            )
            session.add(category)
            session.flush()
            ids[key] = category.id
            return category

        def create_resource(
            key: str,
            category: Category,
            *,
            title: str | None = None,
            resource_type: str = '真题',
            resource_deleted: int = 0,
            created_time: datetime | None = None,
            share_url: str | None = None,
            share_status: str = 'active',
            share_title: str = '',
            share_deleted: int = 0,
            **overrides,
        ) -> MyDriveResource:
            values = {
                'owner_id': 1,
                'category_id': category.id,
                'title': title or f'{key}真题',
                'resource_type': resource_type,
                'description': '',
                'org_name': '',
                'content': '',
                'created_by': 1,
            }
            values.update(overrides)
            resource = MyDriveResource(**values)
            session.add(resource)
            session.flush()
            if resource_deleted:
                resource.deleted = resource_deleted
            if created_time is not None:
                resource.created_time = created_time
            share = MyDriveResourceShare(
                resource_id=resource.id,
                provider='quark',
                share_url=f'https://pan.example/{key}' if share_url is None else share_url,
                share_status=share_status,
                share_title=share_title,
                file_name='',
            )
            session.add(share)
            session.flush()
            if share_deleted:
                share.deleted = share_deleted
            ids[key] = resource.id
            return resource

        if include_gongkao:
            root = create_category('root', '公考', code='re_gongkao')
            guokao = create_category('guokao', '国考', parent=root)
            xingce = create_category('xingce', '行测', parent=guokao)
            shengkao = create_category('shengkao', '省考', parent=root)
            note_category = create_category('note_category', '公考笔记', parent=root, category_type='resource_note')
            disabled_category = create_category('disabled_category', '停用分类', parent=root, status=False)
            deleted_category = create_category('deleted_category', '删除分类', parent=root)
            deleted_category.deleted = 1
            kaoyan = create_category('kaoyan', '考研', code='re_kaoyan')

            create_resource('root_2024', root, title='2024年公考行测真题', content='行测专项')
            create_resource('guokao_2024', guokao, title='2024年国考行测真题', description='北京海淀')
            create_resource('xingce_2024', xingce, title='2024年国考真题')
            create_resource('shengkao_2024', shengkao, title='2024年省考申论真题', description='上海')
            create_resource('kaoyan_2024', kaoyan, title='2024考研政治真题', description='北京')
            create_resource('note_gongkao', note_category, title='2024国考笔记', resource_type='笔记')
            create_resource('guokao_keyword', guokao, title='2024年国考真题', content='通用资料')
            create_resource(
                'guokao_2023', guokao, title='2023年国考真题', created_time=datetime(2024, 6, 1, tzinfo=UTC)
            )
            create_resource('guokao_region_org', guokao, title='2024年国考真题', org_name='北京中公')
            create_resource(
                'shengkao_share_region',
                shengkao,
                title='2024年省考真题',
                share_title='上海真题包',
            )
            create_resource('wildcard', root, title='100%通过的公考真题', description='含%符号')
            create_resource('status_disabled', root, title='2024年公考真题', status='disabled')
            create_resource('resource_deleted', root, title='2024年公考真题', resource_deleted=1)
            create_resource('audit_pending', root, title='2024年公考真题', audit_status='pending')
            create_resource('share_deleted', root, title='2024年公考真题', share_deleted=1)
            create_resource('share_expired', root, title='2024年公考真题', share_status='expired')
            create_resource('share_empty_url', root, title='2024年公考真题', share_url='')
            create_resource('cat_disabled', disabled_category, title='2024年公考真题')
            create_resource('cat_deleted', deleted_category, title='2024年公考真题')
        else:
            kaoyan = create_category('kaoyan', '考研', code='re_kaoyan')
            regular = create_category('regular', '公开资料')
            create_resource('kaoyan', kaoyan, title='2024考研政治真题')
            create_resource('regular', regular, title='2024公开真题')

        session.commit()

    return SqliteFixture(engine=engine, ids=ids)


@pytest.fixture()
def db() -> SqliteFixture:
    fixture = _build_database()
    yield fixture
    fixture.engine.dispose()


@pytest.fixture()
def no_gongkao_db() -> SqliteFixture:
    fixture = _build_database(include_gongkao=False)
    yield fixture
    fixture.engine.dispose()


async def _query_ids(fixture: SqliteFixture, **params) -> set[int]:
    stmt = await mydrive_resource_dao.get_public_select(GetMyDriveResourceListParam(**params))
    query = stmt.with_only_columns(MyDriveResource.id)
    with Session(fixture.engine) as session:
        return {int(row[0]) for row in session.execute(query).all()}


async def _ordered_ids(fixture: SqliteFixture, *, limit: int | None = None, offset: int = 0, **params) -> list[int]:
    stmt = await mydrive_resource_dao.get_public_select(GetMyDriveResourceListParam(**params))
    query = stmt.with_only_columns(MyDriveResource.id).order_by(MyDriveResource.id)
    if limit is not None:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    with Session(fixture.engine) as session:
        return [int(row[0]) for row in session.execute(query).all()]


async def test_exam_domain_covers_root_and_descendants(db: SqliteFixture) -> None:
    """公考根分类、国考/省考及孙级分类下的真题都应命中。"""
    result = await _query_ids(db, exam_domain='gongkao')

    assert result == {
        db.ids[key]
        for key in (
            'root_2024',
            'guokao_2024',
            'xingce_2024',
            'shengkao_2024',
            'guokao_keyword',
            'guokao_2023',
            'guokao_region_org',
            'shengkao_share_region',
            'wildcard',
        )
    }


async def test_exam_domain_does_not_leak_other_domains_or_notes(db: SqliteFixture) -> None:
    """考研资料和笔记类型即使公开也不应进入公考真题列表。"""
    result = await _query_ids(db, exam_domain='gongkao')

    assert result.isdisjoint({db.ids['kaoyan_2024'], db.ids['note_gongkao']})


@pytest.mark.parametrize(
    'key',
    [
        'status_disabled',
        'resource_deleted',
        'audit_pending',
        'share_deleted',
        'share_expired',
        'share_empty_url',
        'cat_disabled',
        'cat_deleted',
    ],
)
async def test_exam_domain_excludes_unavailable_resources(db: SqliteFixture, key: str) -> None:
    """禁用分类、下架资源、审核中及失效分享都应被排除。"""
    result = await _query_ids(db, exam_domain='gongkao')

    assert db.ids[key] not in result


async def test_exam_domain_without_category_root_returns_empty(no_gongkao_db: SqliteFixture) -> None:
    """缺少公考根分类时返回空集，绝不能退化为全库查询。"""
    assert await _query_ids(no_gongkao_db)
    assert await _query_ids(no_gongkao_db, exam_domain='gongkao') == set()


async def test_subject_matches_category_tree_or_text(db: SqliteFixture) -> None:
    """科目既匹配同名分类树，也匹配资源文本。"""
    tree_and_text = await _query_ids(db, exam_domain='gongkao', subject='国考')
    text_only = await _query_ids(db, exam_domain='gongkao', subject='行测')

    assert tree_and_text == {
        db.ids[key] for key in ('guokao_2024', 'xingce_2024', 'guokao_keyword', 'guokao_2023', 'guokao_region_org')
    }
    assert text_only == {db.ids[key] for key in ('root_2024', 'guokao_2024', 'xingce_2024')}


async def test_year_matches_text_not_upload_time(db: SqliteFixture) -> None:
    """年份按资源文本匹配，2023 真题即使创建于 2024 年也不属于 2024。"""
    year_2024 = await _query_ids(db, exam_domain='gongkao', year=2024)
    year_2023 = await _query_ids(db, exam_domain='gongkao', year=2023)

    assert year_2024 == {
        db.ids[key]
        for key in (
            'root_2024',
            'guokao_2024',
            'xingce_2024',
            'shengkao_2024',
            'guokao_keyword',
            'guokao_region_org',
            'shengkao_share_region',
        )
    }
    assert year_2023 == {db.ids['guokao_2023']}


async def test_region_matches_each_text_field(db: SqliteFixture) -> None:
    """地区分别匹配描述、机构名与分享标题。"""
    beijing = await _query_ids(db, exam_domain='gongkao', region='北京')
    shanghai = await _query_ids(db, exam_domain='gongkao', region='上海')

    assert beijing == {db.ids['guokao_2024'], db.ids['guokao_region_org']}
    assert shanghai == {db.ids['shengkao_2024'], db.ids['shengkao_share_region']}


async def test_three_filters_and_keyword_are_combined_with_and(db: SqliteFixture) -> None:
    """科目、年份、地区与关键词逐项 AND，不能互相放宽。"""
    full = await _query_ids(
        db,
        exam_domain='gongkao',
        subject='行测',
        year=2024,
        region='北京',
        keyword='国考',
    )
    without_region = await _query_ids(db, exam_domain='gongkao', subject='行测', year=2024, keyword='国考')
    without_keyword = await _query_ids(db, exam_domain='gongkao', subject='行测', year=2024)

    assert full == {db.ids['guokao_2024']}
    assert without_region == {db.ids['guokao_2024'], db.ids['xingce_2024']}
    assert without_keyword == {db.ids['root_2024'], db.ids['guokao_2024'], db.ids['xingce_2024']}


async def test_like_wildcards_are_escaped(db: SqliteFixture) -> None:
    """含 % 的筛选值按字面匹配，不会匹配整个列表。"""
    region_percent = await _query_ids(db, exam_domain='gongkao', region='%')
    region_literal = await _query_ids(db, exam_domain='gongkao', region='100%')
    subject_percent = await _query_ids(db, exam_domain='gongkao', subject='%')

    assert region_percent == {db.ids['wildcard']}
    assert region_literal == {db.ids['wildcard']}
    assert subject_percent == {db.ids['wildcard']}


async def test_pagination_pages_keep_filters(db: SqliteFixture) -> None:
    """分页各页都保持筛选条件，拼接后与全量结果一致且不重复。"""
    all_ids = await _ordered_ids(db, exam_domain='gongkao')
    first_page = await _ordered_ids(db, limit=4, exam_domain='gongkao')
    second_page = await _ordered_ids(db, limit=4, offset=4, exam_domain='gongkao')
    third_page = await _ordered_ids(db, limit=4, offset=8, exam_domain='gongkao')

    assert len(all_ids) == 9
    assert first_page + second_page + third_page == all_ids
    assert len(set(first_page + second_page + third_page)) == 9


async def test_repeated_queries_with_different_conditions_are_independent(db: SqliteFixture) -> None:
    """连续不同条件的查询互不影响，递归分类范围不会串用。"""
    by_subject = await _query_ids(db, exam_domain='gongkao', subject='国考')
    by_year = await _query_ids(db, exam_domain='gongkao', year=2023)
    by_region = await _query_ids(db, exam_domain='gongkao', region='上海')

    assert by_subject == {
        db.ids[key] for key in ('guokao_2024', 'xingce_2024', 'guokao_keyword', 'guokao_2023', 'guokao_region_org')
    }
    assert by_year == {db.ids['guokao_2023']}
    assert by_region == {db.ids['shengkao_2024'], db.ids['shengkao_share_region']}


async def test_legacy_list_without_exam_domain_is_unchanged(db: SqliteFixture) -> None:
    """不传 exam_domain 时保持原有公开列表语义，不强制真题也不限制分类。"""
    legacy = await _query_ids(db)
    exam_only = await _query_ids(db, exam_domain='gongkao')

    assert legacy == {
        db.ids[key]
        for key in (
            'root_2024',
            'guokao_2024',
            'xingce_2024',
            'shengkao_2024',
            'kaoyan_2024',
            'note_gongkao',
            'guokao_keyword',
            'guokao_2023',
            'guokao_region_org',
            'shengkao_share_region',
            'wildcard',
            'cat_disabled',
            'cat_deleted',
        )
    }
    assert exam_only < legacy


@pytest.mark.parametrize('year', [1900, 2100])
def test_year_schema_accepts_boundaries(year: int) -> None:
    """年份边界 1900 与 2100 应通过校验。"""
    assert GetMyDriveResourceListParam(year=year).year == year


@pytest.mark.parametrize('year', [1899, 2101])
def test_year_schema_rejects_out_of_range(year: int) -> None:
    """超出 1900-2100 的年份应被拒绝。"""
    with pytest.raises(ValidationError):
        GetMyDriveResourceListParam(year=year)


@pytest.mark.parametrize(
    ['extract_code', 'expected'],
    [
        ['a1b2', 'a1b2'],
        ['', ''],
        [None, ''],
    ],
)
async def test_public_detail_extracts_code_from_share(
    monkeypatch: pytest.MonkeyPatch,
    extract_code: str | None,
    expected: str,
) -> None:
    """公开详情应从分享记录读取提取码。"""
    share = SimpleNamespace(
        provider='quark',
        share_url='https://pan.example/detail',
        extract_code=extract_code,
        file_size=1024,
    )
    resource = SimpleNamespace(
        id=7,
        category_id=11,
        title='真题详情',
        description='描述',
        org_name='机构',
        resource_type='真题',
        hot=3,
        created_time=datetime(2024, 1, 1, tzinfo=UTC),
        images=[],
        updated_time=None,
        share=share,
    )
    monkeypatch.setattr(mydrive_resource_dao, 'get_public', AsyncMock(return_value=resource))
    monkeypatch.setattr(MyDriveResourceService, '_get_category_name_map', AsyncMock(return_value={}))

    detail = await mydrive_resource_service.get_public_detail(None, pk=resource.id)

    assert detail.extract_code == expected
    assert detail.share_url == 'https://pan.example/detail'
