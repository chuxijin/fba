"""近年政治客观卷的默认模块配额，不代表官方逐年不变的命题规定。"""

from collections.abc import Sequence
from dataclasses import dataclass

from backend.common.exception import errors

POLITICS_BLUEPRINT_VERSION = 'real_2025_2026_v1'


@dataclass(frozen=True, slots=True)
class PoliticsModule:
    code: str
    name: str
    single_count: int
    multiple_count: int


POLITICS_MODULES = (
    PoliticsModule('kaoyan_politics_mayuan', '马原', 4, 5),
    PoliticsModule('kaoyan_politics_maozhongte', '毛中特', 2, 1),
    PoliticsModule('kaoyan_politics_xinshixiang', '新思想', 3, 4),
    PoliticsModule('kaoyan_politics_shigang', '史纲', 4, 3),
    PoliticsModule('kaoyan_politics_sixiu', '思修／道法', 1, 2),
    PoliticsModule('kaoyan_politics_shizheng', '时政', 2, 2),
)


@dataclass(frozen=True, slots=True)
class PoliticsModuleQuota:
    module: PoliticsModule
    point_ids: frozenset[int]
    single_count: int
    multiple_count: int

    def as_snapshot(self) -> dict:
        return {
            'module_code': self.module.code,
            'module_name': self.module.name,
            'knowledge_point_ids': sorted(self.point_ids),
            'single_count': self.single_count,
            'multiple_count': self.multiple_count,
        }


def _allocate(total: int, weights: Sequence[int]) -> list[int]:
    """整数最大余数法；同余数按固定模块顺序，不受勾选顺序或题池容量影响。"""
    denominator = sum(weights)
    counts = [total * weight // denominator for weight in weights]
    ranked = sorted(range(len(weights)), key=lambda index: -(total * weights[index] % denominator))
    for index in ranked[:total - sum(counts)]:
        counts[index] += 1
    return counts


def build_politics_quotas(
    scopes: Sequence[tuple[PoliticsModule, frozenset[int]]],
) -> list[PoliticsModuleQuota]:
    """先合并同模块范围，再独立分配16单选和17多选；不以题量不足为由挪配额。"""
    points_by_code: dict[str, set[int]] = {}
    known_codes = {module.code for module in POLITICS_MODULES}
    for module, point_ids in scopes:
        if module.code not in known_codes:
            raise errors.RequestError(msg='当前政治模块未配置组卷配额')
        if point_ids:
            points_by_code.setdefault(module.code, set()).update(point_ids)
    modules = [module for module in POLITICS_MODULES if module.code in points_by_code]
    if not modules:
        raise errors.RequestError(msg='所选抽题范围不可用，请返回重新选择')
    singles = _allocate(16, [module.single_count for module in modules])
    multiples = _allocate(17, [module.multiple_count for module in modules])
    return [
        PoliticsModuleQuota(module, frozenset(points_by_code[module.code]), singles[index], multiples[index])
        for index, module in enumerate(modules)
    ]
