"""Formatter Service - 字段配置服务（带缓存）"""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.oc.crud.crud_formatter import (
    formatter_field_dao,
    formatter_embedding_dao,
    formatter_mapping_dao,
)


class FormatterCache:
    """Formatter 缓存"""

    def __init__(self):
        self._config: dict[str, Any] | None = None
        self._label_index: dict[str, tuple[str, str, int | None]] | None = None  # label -> (category, field, parent_id)
        self._mapping_index: dict[int, dict[str, list[str]]] | None = None  # field_id -> {source: targets}

    def clear(self):
        """清除缓存"""
        self._config = None
        self._label_index = None
        self._mapping_index = None

    @property
    def is_loaded(self) -> bool:
        return self._config is not None

    @property
    def config(self) -> dict[str, Any]:
        return self._config or {}

    @property
    def label_index(self) -> dict[str, tuple[str, str, int | None]]:
        return self._label_index or {}

    @property
    def mapping_index(self) -> dict[int, dict[str, list[str]]]:
        return self._mapping_index or {}

    def set_data(
        self,
        config: dict[str, Any],
        label_index: dict[str, tuple[str, str, int | None]],
        mapping_index: dict[int, dict[str, list[str]]]
    ):
        self._config = config
        self._label_index = label_index
        self._mapping_index = mapping_index


# 全局缓存实例
_cache = FormatterCache()


class FormatterService:
    """Formatter 服务"""

    @staticmethod
    async def load_cache(db: AsyncSession) -> None:
        """从数据库加载配置到缓存"""
        # 获取所有字段配置
        fields = await formatter_field_dao.get_all(db)
        embeddings = await formatter_embedding_dao.get_all(db)
        mappings = await formatter_mapping_dao.get_all(db)

        # 构建字段ID索引
        field_by_id: dict[int, Any] = {}
        for f in fields:
            field_by_id[f.id] = f

        # 构建 embedding 索引 (field_id -> list of embeddings)
        embedding_by_field: dict[int, list] = {}
        for e in embeddings:
            if e.field_id not in embedding_by_field:
                embedding_by_field[e.field_id] = []
            embedding_by_field[e.field_id].append(e)

        # 构建 mapping 索引 (field_id -> {source: targets})
        mapping_index: dict[int, dict[str, list[str]]] = {}
        for m in mappings:
            if m.field_id not in mapping_index:
                mapping_index[m.field_id] = {}
            mapping_index[m.field_id][m.source_value] = json.loads(m.target_values)

        # 构建配置字典和标签索引
        config: dict[str, Any] = {}
        label_index: dict[str, tuple[str, str, int | None]] = {}

        # 先处理顶级字段
        for f in fields:
            if f.parent_field_id is not None:
                continue  # 跳过子字段，后面处理

            if f.category not in config:
                config[f.category] = {
                    'chinese': f.category,  # 会被实际的中文名覆盖
                    'fields': {}
                }

            # 构建字段配置
            field_config: dict[str, Any] = {
                'chinese': f.chinese,
                'strategy': f.strategy,
                'embedding': [],
            }

            if f.default_value:
                field_config['default'] = f.default_value

            if f.tips:
                field_config['tips'] = f.tips

            # 添加 embedding
            if f.id in embedding_by_field:
                for e in embedding_by_field[f.id]:
                    field_config['embedding'].append({
                        'label': e.label,
                        'value_script': e.value_script or '',
                    })
                    # 添加到标签索引
                    label_index[e.label] = (f.category, f.field_name, None)

            # 添加 mapping
            if f.id in mapping_index:
                field_config['mapping'] = mapping_index[f.id]

            # 如果是复杂数组类型，添加子字段
            if f.is_array:
                field_config['keys'] = {}
                for sub_f in fields:
                    if sub_f.parent_field_id == f.id:
                        sub_config: dict[str, Any] = {
                            'chinese': sub_f.chinese,
                            'strategy': sub_f.strategy,
                            'embedding': [],
                        }

                        if sub_f.default_value:
                            sub_config['default'] = sub_f.default_value

                        # 添加子字段 embedding
                        if sub_f.id in embedding_by_field:
                            for e in embedding_by_field[sub_f.id]:
                                sub_config['embedding'].append({
                                    'label': e.label,
                                    'value_script': e.value_script or '',
                                })
                                # 添加到标签索引
                                label_index[e.label] = (f.category, sub_f.field_name, f.id)

                        # 添加子字段 mapping
                        if sub_f.id in mapping_index:
                            sub_config['mapping'] = mapping_index[sub_f.id]

                        field_config['keys'][sub_f.field_name] = sub_config

            config[f.category]['fields'][f.field_name] = field_config

        # 设置缓存
        _cache.set_data(config, label_index, mapping_index)
        print(f'[FormatterService] 缓存加载完成: {len(fields)} 字段, {len(embeddings)} 标签, {len(mappings)} 映射')

    @staticmethod
    def get_cache() -> FormatterCache:
        """获取缓存"""
        return _cache

    @staticmethod
    def get_formatter() -> dict[str, Any]:
        """获取 formatter 配置"""
        return _cache.config

    @staticmethod
    def find_field_by_label(label: str) -> tuple[str, str] | None:
        """根据标签查找字段

        Returns:
            (category, field_name) 或 None
        """
        if label in _cache.label_index:
            category, field_name, _ = _cache.label_index[label]
            return (category, field_name)
        return None

    @staticmethod
    def find_best_match(
        value: str,
        options: list[str],
        category: str | None,
        field: str | None
    ) -> str | None:
        """在下拉选项中查找最佳匹配值

        Args:
            value: 简历中的值
            options: 下拉选项列表
            category: 字段分类
            field: 字段名

        Returns:
            匹配到的选项值，或 None
        """
        if not options:
            return None

        # 1. 精确匹配
        if value in options:
            return value

        # 2. 使用 mapping 进行等价匹配
        if category and field:
            config = _cache.config
            if category in config and field in config[category].get('fields', {}):
                field_config = config[category]['fields'][field]
                mapping = field_config.get('mapping', {})
                if value in mapping:
                    target_values = mapping[value]
                    for target in target_values:
                        if target in options:
                            return target

            # 也检查子字段 (keys)
            if category in config:
                for parent_field, parent_config in config[category].get('fields', {}).items():
                    if 'keys' in parent_config and field in parent_config['keys']:
                        field_config = parent_config['keys'][field]
                        mapping = field_config.get('mapping', {})
                        if value in mapping:
                            target_values = mapping[value]
                            for target in target_values:
                                if target in options:
                                    return target

        # 3. 包含匹配
        value_lower = value.lower()
        for opt in options:
            if value_lower in opt.lower() or opt.lower() in value_lower:
                return opt

        return None

    @staticmethod
    def parse_resume_key(resume_key: str) -> tuple[str | None, str | None, str | None]:
        """解析 resume_key

        格式: ;category;index;field@label
        例如: ;basic_info;0;gender@性别

        Returns:
            (category, field, label)
        """
        try:
            if '@' in resume_key:
                key_part, label = resume_key.rsplit('@', 1)
            else:
                key_part = resume_key
                label = None

            parts = key_part.split(';')
            if len(parts) >= 4:
                category = parts[1] if parts[1] else None
                field = parts[3] if parts[3] else None
                return (category, field, label)

            return (None, None, label)
        except Exception:
            return (None, None, None)


formatter_service: FormatterService = FormatterService()
