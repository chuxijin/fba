#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from typing import Sequence, Optional, List
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_rule_template import rule_template_dao
from backend.app.coulddrive.model.rule_template import RuleTemplate
from backend.app.coulddrive.schema.rule_template import (
    CreateRuleTemplateParam,
    UpdateRuleTemplateParam,
    GetRuleTemplateListParam,
    TemplateType,
    RuleTemplateStatsDetail
)
from backend.app.coulddrive.schema.file import ExclusionRuleDefinition, RenameRuleDefinition
from backend.common.exception.errors import NotFoundError, ForbiddenError


class MatchTarget(Enum):
    """匹配目标"""
    NAME = "name"           # 文件名
    PATH = "path"           # 完整路径
    EXTENSION = "extension" # 扩展名


class ItemType(Enum):
    """项目类型"""
    FILE = "file"     # 文件
    FOLDER = "folder" # 目录
    ANY = "any"       # 任意


class MatchMode(Enum):
    """匹配模式"""
    CONTAINS = "contains"   # 包含
    STARTS_WITH = "starts_with"  # 开头匹配
    ENDS_WITH = "ends_with"      # 结尾匹配
    REGEX = "regex"              # 正则表达式
    EXACT = "exact"              # 精确匹配


class RuleTemplateService:
    """规则模板服务类"""

    @staticmethod
    async def get_rule_template(db: AsyncSession, template_id: int) -> RuleTemplate:
        """
        获取规则模板详情

        :param db: 数据库会话
        :param template_id: 模板ID
        :return:
        """
        rule_template = await rule_template_dao.get(db, template_id)
        if not rule_template:
            raise NotFoundError(msg="规则模板不存在")
        return rule_template

    @staticmethod
    async def get_rule_template_list(db: AsyncSession, params: GetRuleTemplateListParam) -> Sequence[RuleTemplate]:
        """
        获取规则模板列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        return await rule_template_dao.get_list_with_pagination(db, params)

    @staticmethod
    async def create_rule_template(db: AsyncSession, obj: CreateRuleTemplateParam, created_by: int) -> None:
        """
        创建规则模板

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        # 检查模板名称是否已存在
        if await rule_template_dao.check_name_exists(db, obj.template_name):
            raise ForbiddenError(msg="模板名称已存在")
        
        await rule_template_dao.create(db, obj, created_by)

    @staticmethod
    async def update_rule_template(
        db: AsyncSession, 
        template_id: int, 
        obj: UpdateRuleTemplateParam, 
        updated_by: int
    ) -> None:
        """
        更新规则模板

        :param db: 数据库会话
        :param template_id: 模板ID
        :param obj: 更新参数
        :param updated_by: 更新者ID
        :return:
        """
        # 检查模板是否存在
        rule_template = await RuleTemplateService.get_rule_template(db, template_id)
        
        # 如果更新模板名称，检查是否重复
        if obj.template_name and obj.template_name != rule_template.template_name:
            if await rule_template_dao.check_name_exists(db, obj.template_name, template_id):
                raise ForbiddenError(msg="模板名称已存在")
        
        # 检查是否为系统模板
        if rule_template.is_system:
            raise ForbiddenError(msg="系统模板不允许修改")
        
        count = await rule_template_dao.update(db, template_id, obj, updated_by)
        if count == 0:
            raise NotFoundError(msg="更新失败，规则模板不存在")

    @staticmethod
    async def delete_rule_template(db: AsyncSession, template_id: int) -> None:
        """
        删除规则模板

        :param db: 数据库会话
        :param template_id: 模板ID
        :return:
        """
        rule_template = await RuleTemplateService.get_rule_template(db, template_id)
        
        # 检查是否为系统模板
        if rule_template.is_system:
            raise ForbiddenError(msg="系统模板不允许删除")
        
        count = await rule_template_dao.delete(db, [template_id])
        if count == 0:
            raise NotFoundError(msg="删除失败，规则模板不存在")

    @staticmethod
    async def delete_rule_templates(db: AsyncSession, template_ids: list[int]) -> None:
        """
        批量删除规则模板

        :param db: 数据库会话
        :param template_ids: 模板ID列表
        :return:
        """
        # 检查是否包含系统模板
        for template_id in template_ids:
            rule_template = await rule_template_dao.get(db, template_id)
            if rule_template and rule_template.is_system:
                raise ForbiddenError(msg=f"模板 '{rule_template.template_name}' 是系统模板，不允许删除")
        
        count = await rule_template_dao.delete(db, template_ids)
        if count == 0:
            raise NotFoundError(msg="删除失败，规则模板不存在")

    @staticmethod
    async def use_rule_template(db: AsyncSession, template_id: int) -> RuleTemplate:
        """
        使用规则模板（更新使用统计）

        :param db: 数据库会话
        :param template_id: 模板ID
        :return:
        """
        rule_template = await RuleTemplateService.get_rule_template(db, template_id)
        
        if not rule_template.is_active:
            raise ForbiddenError(msg="模板已禁用，无法使用")
        
        # 更新使用统计
        await rule_template_dao.update_usage(db, template_id)
        
        return rule_template

    @staticmethod
    async def toggle_rule_template_active(db: AsyncSession, template_id: int, is_active: bool) -> None:
        """
        切换规则模板启用状态

        :param db: 数据库会话
        :param template_id: 模板ID
        :param is_active: 是否启用
        :return:
        """
        rule_template = await RuleTemplateService.get_rule_template(db, template_id)
        
        # 检查是否为系统模板
        if rule_template.is_system:
            raise ForbiddenError(msg="系统模板不允许修改状态")
        
        count = await rule_template_dao.toggle_active(db, template_id, is_active)
        if count == 0:
            raise NotFoundError(msg="操作失败，规则模板不存在")

    @staticmethod
    async def get_rule_template_stats(db: AsyncSession) -> RuleTemplateStatsDetail:
        """
        获取规则模板统计信息

        :param db: 数据库会话
        :return:
        """
        stats = await rule_template_dao.get_stats(db)
        return RuleTemplateStatsDetail(**stats)

    @staticmethod
    async def get_templates_by_type(db: AsyncSession, template_type: TemplateType) -> Sequence[RuleTemplate]:
        """
        根据类型获取规则模板

        :param db: 数据库会话
        :param template_type: 模板类型
        :return:
        """
        return await rule_template_dao.get_by_type(db, template_type)

    @staticmethod
    async def get_templates_by_category(db: AsyncSession, category: str) -> Sequence[RuleTemplate]:
        """
        根据分类获取规则模板

        :param db: 数据库会话
        :param category: 分类
        :return:
        """
        return await rule_template_dao.get_by_category(db, category)


class ExclusionRule:
    """排除规则类"""
    
    def __init__(self,
                 pattern: str,
                 target: MatchTarget = MatchTarget.NAME,
                 item_type: ItemType = ItemType.ANY,
                 mode: MatchMode = MatchMode.CONTAINS,
                 case_sensitive: bool = False):
        """
        初始化排除规则
        
        :param pattern: 匹配模式
        :param target: 匹配目标
        :param item_type: 项目类型
        :param mode: 匹配模式
        :param case_sensitive: 是否区分大小写
        """
        self.pattern = pattern
        self.target = target
        self.item_type = item_type
        self.mode = mode
        self.case_sensitive = case_sensitive
        
        # 预编译正则表达式
        if mode == MatchMode.REGEX:
            flags = 0 if case_sensitive else re.IGNORECASE
            self.regex = re.compile(pattern, flags)
        else:
            self.regex = None

    def _get_value_to_match(self, item) -> Optional[str]:
        """获取要匹配的值"""
        if self.target == MatchTarget.NAME:
            return item.file_name
        elif self.target == MatchTarget.PATH:
            return item.file_path
        elif self.target == MatchTarget.EXTENSION:
            if hasattr(item, 'file_name') and '.' in item.file_name:
                return item.file_name.split('.')[-1]
        return None

    def matches(self, item) -> bool:
        """检查项目是否匹配排除规则"""
        # 检查项目类型
        if self.item_type != ItemType.ANY:
            if self.item_type == ItemType.FILE and getattr(item, 'is_folder', False):
                return False
            elif self.item_type == ItemType.FOLDER and not getattr(item, 'is_folder', False):
                return False

        # 获取要匹配的值
        value = self._get_value_to_match(item)
        if value is None:
            return False

        # 根据是否区分大小写处理
        if not self.case_sensitive:
            value = value.lower()
            pattern = self.pattern.lower()
        else:
            pattern = self.pattern

        # 根据匹配模式进行匹配
        if self.mode == MatchMode.CONTAINS:
            return pattern in value
        elif self.mode == MatchMode.STARTS_WITH:
            return value.startswith(pattern)
        elif self.mode == MatchMode.ENDS_WITH:
            return value.endswith(pattern)
        elif self.mode == MatchMode.EXACT:
            return value == pattern
        elif self.mode == MatchMode.REGEX:
            return bool(self.regex and self.regex.search(value))
        
        return False


class ItemFilter:
    """项目过滤器"""
    
    def __init__(self, exclusion_rules: Optional[List[ExclusionRule]] = None):
        """初始化过滤器"""
        self.exclusion_rules = exclusion_rules or []

    def add_rule(self, rule: ExclusionRule):
        """添加排除规则"""
        self.exclusion_rules.append(rule)

    def should_exclude(self, item) -> bool:
        """检查项目是否应该被排除"""
        for rule in self.exclusion_rules:
            if rule.matches(item):
                return True
        return False


class RenameRule:
    """重命名规则类"""
    
    def __init__(self,
                 match_regex: str,
                 replace_string: str,
                 target_scope: MatchTarget = MatchTarget.NAME,
                 case_sensitive: bool = False):
        """
        初始化重命名规则
        
        :param match_regex: 匹配的正则表达式
        :param replace_string: 替换字符串
        :param target_scope: 目标范围
        :param case_sensitive: 是否区分大小写
        """
        self.match_regex = match_regex
        self.replace_string = replace_string
        self.target_scope = target_scope
        self.case_sensitive = case_sensitive
        
        # 预编译正则表达式
        flags = 0 if case_sensitive else re.IGNORECASE
        self.regex = re.compile(match_regex, flags)

    def generate_new_path(self, item) -> Optional[str]:
        """生成新的路径"""
        if self.target_scope == MatchTarget.NAME:
            original_value = getattr(item, 'file_name', '')
        elif self.target_scope == MatchTarget.PATH:
            original_value = getattr(item, 'file_path', '')
        else:
            return None

        if not original_value:
            return None

        # 应用重命名规则
        new_value = self.regex.sub(self.replace_string, original_value)
        
        # 如果没有变化，返回None
        if new_value == original_value:
            return None
            
        return new_value


def parse_exclusion_rules(rules_def: Optional[List[ExclusionRuleDefinition]]) -> Optional[ItemFilter]:
    """解析排除规则定义"""
    if not rules_def:
        return None
    
    rules = []
    for rule_def in rules_def:
        try:
            rule = ExclusionRule(
                pattern=rule_def.pattern,
                target=MatchTarget(rule_def.target),
                item_type=ItemType(rule_def.item_type),
                mode=MatchMode(rule_def.mode),
                case_sensitive=rule_def.case_sensitive
            )
            rules.append(rule)
        except (ValueError, AttributeError) as e:
            # 跳过无效的规则定义
            continue
    
    return ItemFilter(rules) if rules else None


def parse_rename_rules(rules_def: Optional[List[RenameRuleDefinition]]) -> Optional[List[RenameRule]]:
    """解析重命名规则定义"""
    if not rules_def:
        return None
    
    rules = []
    for rule_def in rules_def:
        try:
            rule = RenameRule(
                match_regex=rule_def.match_regex,
                replace_string=rule_def.replace_string,
                target_scope=MatchTarget(rule_def.target_scope),
                case_sensitive=rule_def.case_sensitive
            )
            rules.append(rule)
        except (ValueError, AttributeError) as e:
            # 跳过无效的规则定义
            continue
    
    return rules if rules else None


async def parse_rule_templates(
    exclude_template_id: Optional[int], 
    rename_template_id: Optional[int],
    db: AsyncSession
) -> tuple[Optional[List[ExclusionRuleDefinition]], Optional[List[RenameRuleDefinition]]]:
    """
    解析规则模板
    
    Args:
        exclude_template_id: 排除规则模板ID
        rename_template_id: 重命名规则模板ID
        db: 数据库会话
        
    Returns:
        tuple[Optional[List[ExclusionRuleDefinition]], Optional[List[RenameRuleDefinition]]]: 排除规则和重命名规则
    """
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    exclude_rules = None
    rename_rules = None
    
    # 解析排除规则模板
    if exclude_template_id:
        try:
            exclude_template = await rule_template_dao.get(db, exclude_template_id)
            if exclude_template and exclude_template.rule_config:
                rules_data = exclude_template.rule_config
                # 如果rule_config是字符串，需要解析JSON
                if isinstance(rules_data, str):
                    rules_data = json.loads(rules_data)
                
                # 根据实际数据格式解析规则
                rules_list = rules_data.get('rules', [])
                if rules_list:
                    exclude_rules = [
                        ExclusionRuleDefinition(**rule) for rule in rules_list
                    ]
        except Exception as e:
            logger.error(f"解析排除规则模板失败: {e}")
    
    # 解析重命名规则模板
    if rename_template_id:
        try:
            rename_template = await rule_template_dao.get(db, rename_template_id)
            if rename_template and rename_template.rule_config:
                rules_data = rename_template.rule_config
                # 如果rule_config是字符串，需要解析JSON
                if isinstance(rules_data, str):
                    rules_data = json.loads(rules_data)
                
                # 根据实际数据格式解析规则
                rules_list = rules_data.get('rules', [])
                if rules_list:
                    rename_rules = [
                        RenameRuleDefinition(**rule) for rule in rules_list
                    ]
        except Exception as e:
            logger.error(f"解析重命名规则模板失败: {e}")
    
    return exclude_rules, rename_rules


rule_template_service = RuleTemplateService() 