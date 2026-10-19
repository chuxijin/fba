import asyncio

from unittest.mock import AsyncMock

from backend.app.question_bank_v2.service.content_group_service import ContentGroupService, _point_ids_from_path


class MappingResult:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def mappings(self) -> 'MappingResult':
        return self

    def all(self) -> list[dict]:
        return self.rows


def _point(
    point_id: int,
    name: str,
    *,
    parent_id: int | None = None,
    path: str | None = None,
    sort_order: int = 0,
) -> dict:
    return {
        'id': point_id,
        'name': name,
        'parent_id': parent_id,
        'path': path,
        'sort_order': sort_order,
    }


POINTS = {
    1: _point(1, '政治', path='1'),
    2: _point(2, '马原', parent_id=1, path='1.2'),
    3: _point(3, '唯物论', parent_id=2, path='1.2.3'),
    4: _point(4, '辩证法', parent_id=2, path='1.2.4', sort_order=1),
}


def test_knowledge_tree_restores_ancestors_and_dedupes_question_counts() -> None:
    groups = ContentGroupService._build_knowledge_nodes(
        points=POINTS,
        tagged={
            3: {'id': 3, 'name': '唯物论', 'count': 2, 'question_ids': [101, 102]},
            4: {'id': 4, 'name': '辩证法', 'count': 1, 'question_ids': [102, 103]},
        },
    )

    assert len(groups) == 1
    # 单一根「政治」被下钻一层，首屏直接是科目
    branch = groups[0]
    assert (branch.id, branch.name, branch.count) == (2, '马原', 3)
    assert branch.question_ids == []
    assert [child.name for child in branch.children] == ['唯物论', '辩证法']
    # 同一道题命中多个知识点时，父节点按去重并集计数
    assert branch.children[0].count == 2
    assert branch.children[0].question_ids == [101, 102]
    assert branch.children[1].question_ids == [102, 103]


def test_hit_parent_keeps_direct_questions_under_a_virtual_leaf() -> None:
    points = {
        1: _point(1, '政治', path='/1/'),
        2: _point(2, '马原', parent_id=1, path='/1/2/'),
        3: _point(3, '唯物论', parent_id=2, path='/1/2/3/'),
    }
    groups = ContentGroupService._build_knowledge_nodes(
        points=points,
        tagged={
            2: {'id': 2, 'name': '马原', 'count': 2, 'question_ids': [201, 202]},
            3: {'id': 3, 'name': '唯物论', 'count': 1, 'question_ids': [101]},
        },
    )

    branch = groups[0]
    assert branch.name == '马原'
    assert branch.count == 3
    assert [child.name for child in branch.children] == ['本级题目', '唯物论']
    virtual = branch.children[0]
    assert (virtual.id, virtual.count, virtual.question_ids) == (2, 2, [201, 202])
    # 有子节点的父节点本身不作为可练叶子
    assert branch.question_ids == []
    assert branch.children[1].question_ids == [101]


def test_knowledge_tree_loads_ancestor_chain_from_path_and_parent_id() -> None:
    db = AsyncMock()
    db.execute.side_effect = [
        MappingResult([_point(3, '唯物论', parent_id=2, path='1.2.3')]),
        MappingResult([
            _point(1, '政治', path='1'),
            _point(2, '马原', parent_id=1, path='1.2'),
        ]),
    ]

    groups = asyncio.run(
        ContentGroupService.build_knowledge_tree(
            db=db,
            rows=[{'id': 3, 'name': '唯物论', 'count': 1, 'question_ids': [101]}],
        )
    )

    assert [group.name for group in groups] == ['马原']
    assert groups[0].children[0].name == '唯物论'
    assert groups[0].children[0].question_ids == [101]


def test_knowledge_tree_falls_back_to_parent_links_when_path_missing() -> None:
    db = AsyncMock()
    db.execute.side_effect = [
        MappingResult([_point(4, '辩证法', parent_id=2, path=None)]),
        MappingResult([_point(2, '马原', parent_id=1, path=None)]),
        MappingResult([_point(1, '政治', path=None)]),
    ]

    groups = asyncio.run(
        ContentGroupService.build_knowledge_tree(
            db=db,
            rows=[{'id': 4, 'name': '辩证法', 'count': 1, 'question_ids': [301]}],
        )
    )

    assert [group.name for group in groups] == ['马原']
    assert groups[0].children[0].name == '辩证法'


def test_point_path_supports_dot_and_slash_formats() -> None:
    """线上 path 是点分隔 ID 链，也要兼容斜杠写法"""
    assert _point_ids_from_path('588.589.590') == {588, 589, 590}
    assert _point_ids_from_path('/588/589/590/') == {588, 589, 590}
    assert _point_ids_from_path('588') == {588}
    assert _point_ids_from_path(None) == set()


def test_knowledge_tree_skips_empty_rows_without_querying() -> None:
    db = AsyncMock()

    assert asyncio.run(ContentGroupService.build_knowledge_tree(db=db, rows=[])) == []
    assert asyncio.run(
        ContentGroupService.build_knowledge_tree(
            db=db,
            rows=[{'id': 3, 'name': '空知识点', 'count': 0, 'question_ids': []}],
        )
    ) == []
    db.execute.assert_not_called()


def test_bank_tree_restores_collection_and_section_ancestors() -> None:
    db = AsyncMock()
    db.execute.side_effect = [
        MappingResult([
            {'id': 100, 'bank_revision_id': 20, 'parent_id': None, 'name': '阅读', 'depth': 0, 'sort_order': 0},
            {'id': 101, 'bank_revision_id': 20, 'parent_id': 100, 'name': '仔细阅读', 'depth': 1, 'sort_order': 0},
            {'id': 200, 'bank_revision_id': 21, 'parent_id': None, 'name': '数量', 'depth': 0, 'sort_order': 1},
        ]),
    ]

    groups = asyncio.run(
        ContentGroupService.build_bank_tree(
            db=db,
            rows=[
                {
                    'bank_id': 10,
                    'bank_revision_id': 20,
                    'bank_name': '2026 国考行测',
                    'section_id': 101,
                    'section_name': '仔细阅读',
                    'count': 3,
                    'question_ids': [101, 102, 103],
                },
                {
                    'bank_id': 10,
                    'bank_revision_id': 21,
                    'bank_name': '2026 国考行测',
                    'section_id': 200,
                    'section_name': '数量',
                    'count': 2,
                    'question_ids': [201, 202],
                },
                {
                    'bank_id': None,
                    'bank_revision_id': None,
                    'bank_name': None,
                    'section_id': None,
                    'section_name': None,
                    'count': 1,
                    'question_ids': [301],
                },
            ],
            ungrouped_name='未归属题库',
        )
    )

    assert len(groups) == 2
    # 层级收敛为两级：题库直接作顶层，不再有专区分组
    bank = groups[0]
    assert bank.type is None
    assert bank.name == '2026 国考行测'
    assert bank.count == 5
    # 题库章节节点只做统计展示，不下发题目 ID
    assert bank.question_ids == []
    assert len(bank.children) == 2
    # 子章节「仔细阅读」的错题归并到根章节「阅读」，不再往下展开
    assert bank.children[0].name == '阅读'
    assert bank.children[0].children == []
    assert bank.children[0].count == 3
    assert bank.children[0].question_ids == []
    assert bank.children[1].name == '数量'
    assert bank.children[1].children == []
    assert bank.children[1].count == 2
    assert bank.children[1].question_ids == []
    # 未归属（外部录入）节点仍下发题目 ID，供 custom 投递使用
    assert groups[1].name == '未归属题库'
    assert groups[1].id == 0
    assert groups[1].question_ids == [301]
