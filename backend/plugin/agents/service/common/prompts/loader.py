#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Any

import yaml

from jinja2 import Environment, StrictUndefined

from backend.common.exception import errors
from backend.plugin.agents.service.common.prompts.template import PromptTemplate


class PromptLoader:
    """Prompt 加载器"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self._cache: dict[str, PromptTemplate] = {}
        self._env = Environment(
            autoescape=False,
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=False,
            lstrip_blocks=False,
        )

    def load(self, name: str) -> PromptTemplate:
        """
        加载 <base_dir>/<name>.yaml 模板

        :param name: 模板名 (不带扩展名)
        :return:
        """
        cached = self._cache.get(name)
        if cached is not None:
            return cached

        path = self.base_dir / f'{name}.yaml'
        if not path.exists():
            raise errors.ServerError(msg=f'Prompt 模板未找到: {path}')

        try:
            data = yaml.safe_load(path.read_text(encoding='utf-8'))
        except yaml.YAMLError as e:
            raise errors.ServerError(msg=f'Prompt 模板 YAML 解析失败 {path}: {e!s}') from e

        if not isinstance(data, dict):
            raise errors.ServerError(msg=f'Prompt 模板根节点必须是 mapping: {path}')

        template = PromptTemplate.model_validate(data)
        self._cache[name] = template
        return template

    def render(
        self,
        template: PromptTemplate,
        variables: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """
        渲染 system 与 user prompt

        :param template: 模板对象
        :param variables: 变量字典
        :return:
        """
        variables = variables or {}
        try:
            system = self._env.from_string(template.system).render(**variables)
            user = self._env.from_string(template.user).render(**variables)
        except Exception as e:
            raise errors.ServerError(msg=f'Prompt 渲染失败: {e!s}') from e
        return system, user

    def load_and_render(
        self,
        name: str,
        variables: dict[str, Any] | None = None,
    ) -> tuple[str, str, PromptTemplate]:
        """
        加载并渲染模板, 同时返回模板对象供上层取版本号等元信息

        :param name: 模板名
        :param variables: 变量字典
        :return:
        """
        template = self.load(name)
        system, user = self.render(template, variables)
        return system, user, template

    def clear_cache(self) -> None:
        """清空模板缓存"""
        self._cache.clear()
