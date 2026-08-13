import asyncio

from unittest.mock import AsyncMock

from backend.app.question_bank_v2.service.content_group_service import ContentGroupService


class MappingResult:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def mappings(self) -> 'MappingResult':
        return self

    def all(self) -> list[dict]:
        return self.rows


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
    assert len(bank.children) == 2
    # 子章节「仔细阅读」的错题归并到根章节「阅读」，不再往下展开
    assert bank.children[0].name == '阅读'
    assert bank.children[0].children == []
    assert bank.children[0].count == 3
    assert bank.children[0].question_ids == [101, 102, 103]
    assert bank.children[1].name == '数量'
    assert bank.children[1].children == []
    assert bank.children[1].count == 2
    assert bank.children[1].question_ids == [201, 202]
    assert groups[1].name == '未归属题库'
    assert groups[1].id == 0
    assert groups[1].question_ids == [301]
