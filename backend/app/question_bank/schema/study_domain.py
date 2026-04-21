#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Literal

from pydantic import BaseModel, Field

StudyDomainCode = Literal['cet', 'kaoyan', 'gongkao', 'jiaozhi']


class StudyDomainCategoryTree(BaseModel):
    """领域分类树节点"""

    id: int = Field(description='分类 ID')
    parent_id: int | None = Field(None, description='父级分类 ID')
    name: str = Field(description='分类名称')
    code: str | None = Field(None, description='分类编码')
    type: str = Field(description='分类类型')
    children: list['StudyDomainCategoryTree'] = Field(default_factory=list, description='子分类')


class StudyDomainOptionResponse(BaseModel):
    """领域选项"""

    code: StudyDomainCode = Field(description='领域编码')
    label: str = Field(description='领域名称')
    app_code: str = Field(description='分类应用标识')


class StudyDomainScopeResponse(BaseModel):
    """领域分类范围"""

    code: StudyDomainCode = Field(description='领域编码')
    label: str = Field(description='领域名称')
    app_code: str = Field(description='分类应用标识')
    product_catalog_codes: list[str] = Field(default_factory=list, description='题库目录根编码')
    knowledge_point_codes: list[str] = Field(default_factory=list, description='知识点根编码')
    resource_exam_codes: list[str] = Field(default_factory=list, description='资料分类根编码')
    product_catalog_roots: list[StudyDomainCategoryTree] = Field(default_factory=list, description='题库目录根树')
    knowledge_point_roots: list[StudyDomainCategoryTree] = Field(default_factory=list, description='知识点根树')
    resource_exam_roots: list[StudyDomainCategoryTree] = Field(default_factory=list, description='资料分类根树')
