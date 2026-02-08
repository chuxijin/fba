#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.model.dict_major import GkDictMajor
from backend.app.gongkao.model.user_profile import GkUserEducation, GkUserProfile
from backend.app.gongkao.schema.gangwei_match import CanApplyResult, ConditionCheckItem
from backend.common.exception import errors

# ========== 常量定义 ==========

# 表示"不限"的关键词
UNLIMITED_KEYWORDS: set[str] = {'不限', '无限制', '无要求', '', '不限制'}

# 学历等级（值越大学历越高）
EDUCATION_LEVELS: dict[str, int] = {
    '专科': 1, '大专': 1,
    '本科': 2,
    '硕士': 3, '硕士研究生': 3, '研究生': 3,
    '博士': 4, '博士研究生': 4,
}

# 学位等级
DEGREE_LEVELS: dict[str, int] = {
    '无学位': 0, '学士': 1, '硕士': 2, '博士': 3,
}

# 政治面貌层级（越高约束越严）
POLITICS_LEVELS: dict[str, int] = {
    '中共党员': 3, '中共预备党员': 2, '共青团员': 1,
    '群众': 0, '民主党派': 0, '无党派': 0,
}


# ========== 工具函数 ==========

def is_unlimited(value: str | None) -> bool:
    """判断是否为不限条件"""
    if not value:
        return True
    return value.strip() in UNLIMITED_KEYWORDS


def parse_education_requirement(text: str) -> tuple[int, bool]:
    """
    解析学历要求

    :param text: 如 "本科及以上"、"仅限本科"
    :return: (最低学历等级, 是否仅限该学历)
    """
    if is_unlimited(text):
        return 0, False

    text = text.strip()

    # 仅限
    only = re.search(r'仅限(\S+)', text)
    if only:
        return EDUCATION_LEVELS.get(only.group(1), 0), True

    # 及以上
    above = re.search(r'(\S+?)(?:及以上|以上)', text)
    if above:
        return EDUCATION_LEVELS.get(above.group(1), 0), False

    # 直接匹配
    for k, v in EDUCATION_LEVELS.items():
        if k in text:
            return v, False

    return 0, False


def parse_degree_requirement(text: str) -> tuple[int, bool]:
    """
    解析学位要求

    :param text: 学位要求文本
    :return: (最低学位等级, 是否仅限)
    """
    if is_unlimited(text):
        return 0, False

    text = text.strip()

    only = re.search(r'仅限(\S+)', text)
    if only:
        return DEGREE_LEVELS.get(only.group(1), 0), True

    above = re.search(r'(\S+?)(?:及以上|以上)', text)
    if above:
        return DEGREE_LEVELS.get(above.group(1), 0), False

    for k, v in DEGREE_LEVELS.items():
        if k in text:
            return v, False

    return 0, False


def parse_age_range(text: str) -> tuple[int | None, int | None]:
    """
    解析年龄要求

    :param text: 如 "18周岁以上、35周岁以下"
    :return: (最小年龄, 最大年龄)
    """
    if is_unlimited(text):
        return None, None

    text = text.strip()
    min_age = max_age = None

    above = re.search(r'(\d+)\s*(?:周岁|岁)\s*(?:以上|及以上)', text)
    below = re.search(r'(\d+)\s*(?:周岁|岁)\s*(?:以下|及以下)', text)

    if above:
        min_age = int(above.group(1))
    if below:
        max_age = int(below.group(1))

    # 18-35岁 格式
    if min_age is None and max_age is None:
        rng = re.search(r'(\d+)\s*[-~至到]\s*(\d+)\s*(?:周岁|岁)', text)
        if rng:
            min_age, max_age = int(rng.group(1)), int(rng.group(2))

    return min_age, max_age


def parse_grassroots_years(text: str) -> int:
    """
    解析基层工作年限

    :param text: 如 "2年及以上"
    :return: 要求年限（0 表示不限）
    """
    if is_unlimited(text):
        return 0
    m = re.search(r'(\d+)\s*年', text.strip())
    return int(m.group(1)) if m else 0


def calc_age(birth: date, ref: date | None = None) -> int:
    """计算年龄"""
    ref = ref or date.today()
    age = ref.year - birth.year
    if (ref.month, ref.day) < (birth.month, birth.day):
        age -= 1
    return age


# ========== 条件检查函数 ==========

def check_education(req: str, educations: list[GkUserEducation]) -> ConditionCheckItem:
    """检查学历"""
    if is_unlimited(req):
        return ConditionCheckItem(name='学历', requirement=req, passed=True, reason='不限')

    min_level, only = parse_education_requirement(req)
    if min_level == 0:
        return ConditionCheckItem(name='学历', requirement=req, passed=True, reason='无法解析，视为通过')

    user_level = 0
    user_name = ''
    for edu in educations:
        lv = EDUCATION_LEVELS.get(edu.edu_level, 0)
        if lv > user_level:
            user_level, user_name = lv, edu.edu_level

    if user_level == 0:
        return ConditionCheckItem(name='学历', requirement=req, user_value=None, passed=False, reason='未填写学历')

    if only:
        ok = user_level == min_level
        return ConditionCheckItem(
            name='学历', requirement=req, user_value=user_name,
            passed=ok, reason='匹配' if ok else f'要求仅限，用户为{user_name}'
        )

    ok = user_level >= min_level
    return ConditionCheckItem(
        name='学历', requirement=req, user_value=user_name,
        passed=ok, reason='满足' if ok else f'学历不足'
    )


def check_degree(req: str, educations: list[GkUserEducation]) -> ConditionCheckItem:
    """检查学位"""
    if is_unlimited(req):
        return ConditionCheckItem(name='学位', requirement=req, passed=True, reason='不限')

    min_level, only = parse_degree_requirement(req)
    if min_level == 0:
        return ConditionCheckItem(name='学位', requirement=req, passed=True, reason='无法解析，视为通过')

    user_level = 0
    user_name = ''
    for edu in educations:
        if edu.degree:
            lv = DEGREE_LEVELS.get(edu.degree, 0)
            if lv > user_level:
                user_level, user_name = lv, edu.degree

    if user_level == 0:
        return ConditionCheckItem(name='学位', requirement=req, user_value=None, passed=False, reason='未填写学位')

    if only:
        ok = user_level == min_level
        return ConditionCheckItem(
            name='学位', requirement=req, user_value=user_name,
            passed=ok, reason='匹配' if ok else f'要求仅限，用户为{user_name}'
        )

    ok = user_level >= min_level
    return ConditionCheckItem(
        name='学位', requirement=req, user_value=user_name,
        passed=ok, reason='满足' if ok else '学位不足'
    )


async def build_major_index(db: AsyncSession) -> dict[str, dict[str, Any]]:
    """
    构建专业索引

    :param db: 数据库会话
    :return: {专业名: {code, level, category_name, discipline_name, ...}}
    """
    stmt = select(GkDictMajor).where(GkDictMajor.is_active.is_(True))
    result = await db.execute(stmt)
    majors = result.scalars().all()

    code_map = {m.code: m for m in majors}
    index: dict[str, dict[str, Any]] = {}

    for m in majors:
        info: dict[str, Any] = {'code': m.code, 'name': m.name, 'level': m.level}

        if m.level == 3 and m.parent_code:
            parent = code_map.get(m.parent_code)
            if parent:
                info['category_name'] = parent.name
                info['category_code'] = parent.code
                if parent.parent_code:
                    disc = code_map.get(parent.parent_code)
                    if disc:
                        info['discipline_name'] = disc.name

        elif m.level == 2 and m.parent_code:
            disc = code_map.get(m.parent_code)
            if disc:
                info['discipline_name'] = disc.name

        index[m.name] = info
        if m.aliases:
            for alias in m.aliases:
                index[alias] = info

    return index


def check_major(
    req: str,
    educations: list[GkUserEducation],
    major_index: dict[str, dict[str, Any]],
) -> ConditionCheckItem:
    """检查专业"""
    if is_unlimited(req):
        return ConditionCheckItem(name='专业', requirement=req, passed=True, reason='不限')

    user_majors = [e.major_name for e in educations if e.major_name]
    user_categories = [e.major_category for e in educations if e.major_category]
    user_disciplines = [e.major_discipline for e in educations if e.major_discipline]
    user_value = ', '.join(user_majors) or None

    if not user_majors:
        return ConditionCheckItem(name='专业', requirement=req, user_value=None, passed=False, reason='未填写专业')

    # 1. 精确匹配
    for name in user_majors:
        if name in req:
            return ConditionCheckItem(name='专业', requirement=req, user_value=user_value, passed=True, reason=f'精确匹配: {name}')

    # 2. 专业类匹配
    for name in user_majors:
        info = major_index.get(name)
        if info and info.get('category_name') and info['category_name'] in req:
            return ConditionCheckItem(
                name='专业', requirement=req, user_value=user_value,
                passed=True, reason=f'专业类匹配: {name} 属于 {info["category_name"]}'
            )

    # 3. 学科门类匹配
    for name in user_majors:
        info = major_index.get(name)
        if info and info.get('discipline_name') and info['discipline_name'] in req:
            return ConditionCheckItem(
                name='专业', requirement=req, user_value=user_value,
                passed=True, reason=f'学科门类匹配: {name} 属于 {info["discipline_name"]}'
            )

    # 4. 用户填的专业类/门类直接匹配
    for cat in user_categories:
        if cat and cat in req:
            return ConditionCheckItem(name='专业', requirement=req, user_value=user_value, passed=True, reason=f'专业类匹配: {cat}')

    for disc in user_disciplines:
        if disc and disc in req:
            return ConditionCheckItem(name='专业', requirement=req, user_value=user_value, passed=True, reason=f'学科门类匹配: {disc}')

    # 5. 反向：检查要求列表中的专业与用户是否同类
    req_items = re.split(r'[、，,/；;（）()\s]+', req)
    for ri in req_items:
        ri = ri.strip()
        if not ri:
            continue
        ri_info = major_index.get(ri)
        if not ri_info:
            continue
        for um in user_majors:
            um_info = major_index.get(um)
            if not um_info:
                continue
            if ri_info.get('category_code') and um_info.get('category_code') == ri_info['category_code']:
                return ConditionCheckItem(
                    name='专业', requirement=req, user_value=user_value,
                    passed=True, reason=f'同专业类: {um} 与 {ri}'
                )

    return ConditionCheckItem(name='专业', requirement=req, user_value=user_value, passed=False, reason='专业不符')


def check_politics(req: str, user_politics: str | None) -> ConditionCheckItem:
    """检查政治面貌"""
    if is_unlimited(req):
        return ConditionCheckItem(name='政治面貌', requirement=req, passed=True, reason='不限')

    if not user_politics:
        return ConditionCheckItem(name='政治面貌', requirement=req, user_value=None, passed=False, reason='未填写')

    if user_politics in req:
        return ConditionCheckItem(name='政治面貌', requirement=req, user_value=user_politics, passed=True, reason='匹配')

    # 层级判断
    req_lv = POLITICS_LEVELS.get(req.strip(), -1)
    user_lv = POLITICS_LEVELS.get(user_politics, -1)
    if req_lv >= 0 and user_lv >= 0 and user_lv >= req_lv:
        return ConditionCheckItem(name='政治面貌', requirement=req, user_value=user_politics, passed=True, reason='满足')

    return ConditionCheckItem(name='政治面貌', requirement=req, user_value=user_politics, passed=False, reason='不符')


def check_age(req: str, birth_date: date | None) -> ConditionCheckItem:
    """检查年龄"""
    if is_unlimited(req):
        return ConditionCheckItem(name='年龄', requirement=req, passed=True, reason='不限')

    if not birth_date:
        return ConditionCheckItem(name='年龄', requirement=req, user_value=None, passed=False, reason='未填写出生日期')

    min_age, max_age = parse_age_range(req)
    if min_age is None and max_age is None:
        return ConditionCheckItem(name='年龄', requirement=req, passed=True, reason='无法解析，视为通过')

    age = calc_age(birth_date)
    user_value = f'{age}岁'

    if min_age and age < min_age:
        return ConditionCheckItem(name='年龄', requirement=req, user_value=user_value, passed=False, reason=f'年龄不足 {min_age} 岁')

    if max_age and age > max_age:
        return ConditionCheckItem(name='年龄', requirement=req, user_value=user_value, passed=False, reason=f'超过 {max_age} 岁')

    return ConditionCheckItem(name='年龄', requirement=req, user_value=user_value, passed=True, reason='满足')


def check_gender(req: str, user_gender: str | None) -> ConditionCheckItem:
    """检查性别"""
    if is_unlimited(req):
        return ConditionCheckItem(name='性别', requirement=req, passed=True, reason='不限')

    if not user_gender:
        return ConditionCheckItem(name='性别', requirement=req, user_value=None, passed=False, reason='未填写')

    if user_gender in req or (req == '男性' and user_gender == '男') or (req == '女性' and user_gender == '女'):
        return ConditionCheckItem(name='性别', requirement=req, user_value=user_gender, passed=True, reason='匹配')

    return ConditionCheckItem(name='性别', requirement=req, user_value=user_gender, passed=False, reason='不符')


def check_grassroots(req: str, work_months: int) -> ConditionCheckItem:
    """检查基层工作年限"""
    if is_unlimited(req):
        return ConditionCheckItem(name='基层年限', requirement=req, passed=True, reason='不限')

    required = parse_grassroots_years(req)
    if required == 0:
        return ConditionCheckItem(name='基层年限', requirement=req, passed=True, reason='不限')

    user_years = work_months // 12
    user_value = f'{user_years}年'

    if user_years >= required:
        return ConditionCheckItem(name='基层年限', requirement=req, user_value=user_value, passed=True, reason='满足')

    return ConditionCheckItem(name='基层年限', requirement=req, user_value=user_value, passed=False, reason=f'不足 {required} 年')


# ========== 服务类 ==========

class GangweiMatchService:
    """岗位匹配服务"""

    @staticmethod
    async def get_profile(db: AsyncSession, user_id: int) -> GkUserProfile:
        """
        获取用户画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(GkUserProfile).where(GkUserProfile.user_id == user_id)
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        if not profile:
            raise errors.NotFoundError(msg='用户画像不存在，请先完善个人信息')
        return profile

    @staticmethod
    async def check_can_apply(
        *,
        db: AsyncSession,
        gangwei_id: int,
        user_id: int,
    ) -> CanApplyResult:
        """
        检查用户能否报考指定岗位

        :param db: 数据库会话
        :param gangwei_id: 岗位 ID
        :param user_id: 用户 ID
        :return:
        """
        from backend.app.gongkao.crud.crud_gangwei import gangwei_dao

        gangwei = await gangwei_dao.get(db, gangwei_id)
        if not gangwei:
            raise errors.NotFoundError(msg='岗位不存在')

        profile = await GangweiMatchService.get_profile(db, user_id)
        major_index = await build_major_index(db)

        checks: list[ConditionCheckItem] = []
        reasons: list[str] = []

        # 逐项检查
        c1 = check_education(gangwei.education or '', profile.educations)
        checks.append(c1)
        if not c1.passed:
            reasons.append(f'学历: {c1.reason}')

        c2 = check_degree(gangwei.degree or '', profile.educations)
        checks.append(c2)
        if not c2.passed:
            reasons.append(f'学位: {c2.reason}')

        c3 = check_major(gangwei.major or '', profile.educations, major_index)
        checks.append(c3)
        if not c3.passed:
            reasons.append(f'专业: {c3.reason}')

        c4 = check_politics(gangwei.politics or '', profile.politics)
        checks.append(c4)
        if not c4.passed:
            reasons.append(f'政治面貌: {c4.reason}')

        c5 = check_age(gangwei.age_requirement or '', profile.birth_date)
        checks.append(c5)
        if not c5.passed:
            reasons.append(f'年龄: {c5.reason}')

        c6 = check_gender(gangwei.gender_requirement or '', profile.gender)
        checks.append(c6)
        if not c6.passed:
            reasons.append(f'性别: {c6.reason}')

        c7 = check_grassroots(gangwei.grassroots_years or '', profile.total_work_years)
        checks.append(c7)
        if not c7.passed:
            reasons.append(f'基层年限: {c7.reason}')

        return CanApplyResult(
            can_apply=len(reasons) == 0,
            reasons=reasons,
            checks=checks,
        )


gangwei_match_service: GangweiMatchService = GangweiMatchService()
