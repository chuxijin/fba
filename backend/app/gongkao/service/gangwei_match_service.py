#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.model.dict_major import GkDictMajor
from backend.app.gongkao.model.user_profile import GkUserProfile
from backend.app.gongkao.schema.gangwei_match import CanApplyResult, ConditionCheckItem
from backend.common.exception import errors

# ========== 常量定义 ==========

UNLIMITED_KEYWORDS: set[str] = {'不限', '无限制', '无要求', ''}

EDUCATION_LEVELS: dict[str, int] = {
    '专科': 1,
    '大专': 1,
    '本科': 2,
    '硕士': 3,
    '硕士研究生': 3,
    '研究生': 3,
    '博士': 4,
    '博士研究生': 4,
}

DEGREE_LEVELS: dict[str, int] = {
    '无学位': 0,
    '学士': 1,
    '硕士': 2,
    '博士': 3,
}

POLITICS_LEVELS: dict[str, int] = {
    '中共党员': 3,
    '中共预备党员': 2,
    '共青团员': 1,
    '群众': 0,
    '民主党派': 0,
    '无党派': 0,
}


def is_unlimited(value: str | None) -> bool:
    """判断是否为不限条件"""
    if not value:
        return True
    return value.strip() in UNLIMITED_KEYWORDS


def get_education_field(education: dict[str, Any], field: str) -> str | None:
    """
    获取教育经历字段

    :param education: 教育经历 JSON
    :param field: 字段名
    :return:
    """
    value = education.get(field)
    if value is None:
        return None
    return str(value)


def parse_education_requirement(text: str) -> tuple[int, bool]:
    """
    解析学历要求

    :param text: 学历要求文本
    :return:
    """
    if is_unlimited(text):
        return 0, False

    cleaned_text = text.strip()

    only = re.search(r'仅限(\S+)', cleaned_text)
    if only:
        return EDUCATION_LEVELS.get(only.group(1), 0), True

    above = re.search(r'(\S+?)(?:及以上|以上)', cleaned_text)
    if above:
        return EDUCATION_LEVELS.get(above.group(1), 0), False

    for key, level in EDUCATION_LEVELS.items():
        if key in cleaned_text:
            return level, False

    return 0, False


def parse_degree_requirement(text: str) -> tuple[int, bool]:
    """
    解析学位要求

    :param text: 学位要求文本
    :return:
    """
    if is_unlimited(text):
        return 0, False

    cleaned_text = text.strip()

    only = re.search(r'仅限(\S+)', cleaned_text)
    if only:
        return DEGREE_LEVELS.get(only.group(1), 0), True

    above = re.search(r'(\S+?)(?:及以上|以上)', cleaned_text)
    if above:
        return DEGREE_LEVELS.get(above.group(1), 0), False

    for key, level in DEGREE_LEVELS.items():
        if key in cleaned_text:
            return level, False

    return 0, False


def parse_age_range(text: str) -> tuple[int | None, int | None]:
    """
    解析年龄要求

    :param text: 年龄要求文本
    :return:
    """
    if is_unlimited(text):
        return None, None

    cleaned_text = text.strip()
    min_age = None
    max_age = None

    above = re.search(r'(\d+)\s*(?:周岁|岁)?\s*(?:以上|及以上)', cleaned_text)
    below = re.search(r'(\d+)\s*(?:周岁|岁)?\s*(?:以下|及以下)', cleaned_text)

    if above:
        min_age = int(above.group(1))
    if below:
        max_age = int(below.group(1))

    if min_age is None and max_age is None:
        between = re.search(r'(\d+)\s*[-~至到]\s*(\d+)\s*(?:周岁|岁)?', cleaned_text)
        if between:
            min_age = int(between.group(1))
            max_age = int(between.group(2))

    return min_age, max_age


def parse_grassroots_years(text: str) -> int:
    """
    解析基层年限要求

    :param text: 基层年限要求文本
    :return:
    """
    if is_unlimited(text):
        return 0

    match = re.search(r'(\d+)\s*年', text.strip())
    if not match:
        return 0
    return int(match.group(1))


def calc_age(birth: date, ref: date | None = None) -> int:
    """
    计算年龄

    :param birth: 出生日期
    :param ref: 参考日期
    :return:
    """
    ref_date = ref or date.today()
    age = ref_date.year - birth.year
    if (ref_date.month, ref_date.day) < (birth.month, birth.day):
        age -= 1
    return age


def check_education(req: str, educations: list[dict[str, Any]] | None) -> ConditionCheckItem:
    """
    检查学历

    :param req: 岗位学历要求
    :param educations: 用户教育经历 JSON
    :return:
    """
    if is_unlimited(req):
        return ConditionCheckItem(name='学历', requirement=req, passed=True, reason='不限')

    min_level, only = parse_education_requirement(req)
    if min_level == 0:
        return ConditionCheckItem(name='学历', requirement=req, passed=True, reason='要求无法解析，默认通过')

    user_level = 0
    user_name = ''
    for education in educations or []:
        edu_level = get_education_field(education, 'edu_level')
        level = EDUCATION_LEVELS.get(edu_level, 0)
        if level > user_level:
            user_level = level
            user_name = edu_level or ''

    if user_level == 0:
        return ConditionCheckItem(name='学历', requirement=req, user_value=None, passed=False, reason='未填写学历')

    if only:
        passed = user_level == min_level
        return ConditionCheckItem(
            name='学历',
            requirement=req,
            user_value=user_name,
            passed=passed,
            reason='匹配' if passed else f'要求仅限，当前为 {user_name}',
        )

    passed = user_level >= min_level
    return ConditionCheckItem(
        name='学历',
        requirement=req,
        user_value=user_name,
        passed=passed,
        reason='满足' if passed else '学历不满足要求',
    )


def check_degree(req: str, educations: list[dict[str, Any]] | None) -> ConditionCheckItem:
    """
    检查学位

    :param req: 岗位学位要求
    :param educations: 用户教育经历 JSON
    :return:
    """
    if is_unlimited(req):
        return ConditionCheckItem(name='学位', requirement=req, passed=True, reason='不限')

    min_level, only = parse_degree_requirement(req)
    if min_level == 0:
        return ConditionCheckItem(name='学位', requirement=req, passed=True, reason='要求无法解析，默认通过')

    user_level = 0
    user_name = ''
    for education in educations or []:
        degree = get_education_field(education, 'degree')
        if not degree:
            continue
        level = DEGREE_LEVELS.get(degree, 0)
        if level > user_level:
            user_level = level
            user_name = degree

    if user_level == 0:
        return ConditionCheckItem(name='学位', requirement=req, user_value=None, passed=False, reason='未填写学位')

    if only:
        passed = user_level == min_level
        return ConditionCheckItem(
            name='学位',
            requirement=req,
            user_value=user_name,
            passed=passed,
            reason='匹配' if passed else f'要求仅限，当前为 {user_name}',
        )

    passed = user_level >= min_level
    return ConditionCheckItem(
        name='学位',
        requirement=req,
        user_value=user_name,
        passed=passed,
        reason='满足' if passed else '学位不满足要求',
    )


async def build_major_index(db: AsyncSession) -> dict[str, dict[str, Any]]:
    """
    构建专业索引

    :param db: 数据库会话
    :return:
    """
    stmt = select(GkDictMajor).where(GkDictMajor.is_active.is_(True))
    result = await db.execute(stmt)
    majors = result.scalars().all()

    code_map = {major.code: major for major in majors}
    index: dict[str, dict[str, Any]] = {}

    for major in majors:
        info: dict[str, Any] = {'code': major.code, 'name': major.name, 'level': major.level}

        if major.level == 3 and major.parent_code:
            category = code_map.get(major.parent_code)
            if category:
                info['category_name'] = category.name
                info['category_code'] = category.code
                if category.parent_code:
                    discipline = code_map.get(category.parent_code)
                    if discipline:
                        info['discipline_name'] = discipline.name

        if major.level == 2 and major.parent_code:
            discipline = code_map.get(major.parent_code)
            if discipline:
                info['discipline_name'] = discipline.name

        index[major.name] = info
        if major.aliases:
            for alias in major.aliases:
                index[alias] = info

    return index


def check_major(
    req: str,
    educations: list[dict[str, Any]] | None,
    major_index: dict[str, dict[str, Any]],
) -> ConditionCheckItem:
    """
    检查专业

    :param req: 岗位专业要求
    :param educations: 用户教育经历 JSON
    :param major_index: 专业索引
    :return:
    """
    if is_unlimited(req):
        return ConditionCheckItem(name='专业', requirement=req, passed=True, reason='不限')

    user_educations = educations or []
    user_majors = [major for item in user_educations if (major := get_education_field(item, 'major_name'))]
    user_categories = [category for item in user_educations if (category := get_education_field(item, 'major_category'))]
    user_disciplines = [
        discipline for item in user_educations if (discipline := get_education_field(item, 'major_discipline'))
    ]
    user_value = ', '.join(user_majors) or None

    if not user_majors:
        return ConditionCheckItem(name='专业', requirement=req, user_value=None, passed=False, reason='未填写专业')

    for major in user_majors:
        if major in req:
            return ConditionCheckItem(name='专业', requirement=req, user_value=user_value, passed=True, reason=f'精确匹配: {major}')

    for major in user_majors:
        major_info = major_index.get(major)
        category_name = major_info.get('category_name') if major_info else None
        if category_name and category_name in req:
            return ConditionCheckItem(
                name='专业',
                requirement=req,
                user_value=user_value,
                passed=True,
                reason=f'专业类匹配: {major} 属于 {category_name}',
            )

    for major in user_majors:
        major_info = major_index.get(major)
        discipline_name = major_info.get('discipline_name') if major_info else None
        if discipline_name and discipline_name in req:
            return ConditionCheckItem(
                name='专业',
                requirement=req,
                user_value=user_value,
                passed=True,
                reason=f'学科门类匹配: {major} 属于 {discipline_name}',
            )

    for category in user_categories:
        if category and category in req:
            return ConditionCheckItem(name='专业', requirement=req, user_value=user_value, passed=True, reason=f'专业类匹配: {category}')

    for discipline in user_disciplines:
        if discipline and discipline in req:
            return ConditionCheckItem(
                name='专业',
                requirement=req,
                user_value=user_value,
                passed=True,
                reason=f'学科门类匹配: {discipline}',
            )

    req_items = re.split(r'[、，,/；;（）()\s]+', req)
    for req_item in req_items:
        candidate = req_item.strip()
        if not candidate:
            continue

        req_info = major_index.get(candidate)
        if not req_info:
            continue

        for user_major in user_majors:
            user_info = major_index.get(user_major)
            if not user_info:
                continue

            req_category_code = req_info.get('category_code')
            user_category_code = user_info.get('category_code')
            if req_category_code and req_category_code == user_category_code:
                return ConditionCheckItem(
                    name='专业',
                    requirement=req,
                    user_value=user_value,
                    passed=True,
                    reason=f'同专业类: {user_major} 与 {candidate}',
                )

    return ConditionCheckItem(name='专业', requirement=req, user_value=user_value, passed=False, reason='专业不满足要求')


def check_politics(req: str, user_politics: str | None) -> ConditionCheckItem:
    """
    检查政治面貌

    :param req: 岗位政治面貌要求
    :param user_politics: 用户政治面貌
    :return:
    """
    if is_unlimited(req):
        return ConditionCheckItem(name='政治面貌', requirement=req, passed=True, reason='不限')

    if not user_politics:
        return ConditionCheckItem(name='政治面貌', requirement=req, user_value=None, passed=False, reason='未填写')

    if user_politics in req:
        return ConditionCheckItem(name='政治面貌', requirement=req, user_value=user_politics, passed=True, reason='匹配')

    req_level = POLITICS_LEVELS.get(req.strip(), -1)
    user_level = POLITICS_LEVELS.get(user_politics, -1)
    if req_level >= 0 and user_level >= 0 and user_level >= req_level:
        return ConditionCheckItem(name='政治面貌', requirement=req, user_value=user_politics, passed=True, reason='满足')

    return ConditionCheckItem(name='政治面貌', requirement=req, user_value=user_politics, passed=False, reason='不满足要求')


def check_age(req: str, birth_date: date | None) -> ConditionCheckItem:
    """
    检查年龄

    :param req: 岗位年龄要求
    :param birth_date: 出生日期
    :return:
    """
    if is_unlimited(req):
        return ConditionCheckItem(name='年龄', requirement=req, passed=True, reason='不限')

    if not birth_date:
        return ConditionCheckItem(name='年龄', requirement=req, user_value=None, passed=False, reason='未填写出生日期')

    min_age, max_age = parse_age_range(req)
    if min_age is None and max_age is None:
        return ConditionCheckItem(name='年龄', requirement=req, passed=True, reason='要求无法解析，默认通过')

    age = calc_age(birth_date)
    user_value = f'{age} 岁'

    if min_age is not None and age < min_age:
        return ConditionCheckItem(name='年龄', requirement=req, user_value=user_value, passed=False, reason=f'低于 {min_age} 岁')

    if max_age is not None and age > max_age:
        return ConditionCheckItem(name='年龄', requirement=req, user_value=user_value, passed=False, reason=f'高于 {max_age} 岁')

    return ConditionCheckItem(name='年龄', requirement=req, user_value=user_value, passed=True, reason='满足')


def check_gender(req: str, user_gender: str | None) -> ConditionCheckItem:
    """
    检查性别

    :param req: 岗位性别要求
    :param user_gender: 用户性别
    :return:
    """
    if is_unlimited(req):
        return ConditionCheckItem(name='性别', requirement=req, passed=True, reason='不限')

    if not user_gender:
        return ConditionCheckItem(name='性别', requirement=req, user_value=None, passed=False, reason='未填写')

    if user_gender in req:
        return ConditionCheckItem(name='性别', requirement=req, user_value=user_gender, passed=True, reason='匹配')

    male_keywords = {'男', '男性'}
    female_keywords = {'女', '女性'}
    if req.strip() in male_keywords and user_gender in male_keywords:
        return ConditionCheckItem(name='性别', requirement=req, user_value=user_gender, passed=True, reason='匹配')
    if req.strip() in female_keywords and user_gender in female_keywords:
        return ConditionCheckItem(name='性别', requirement=req, user_value=user_gender, passed=True, reason='匹配')

    return ConditionCheckItem(name='性别', requirement=req, user_value=user_gender, passed=False, reason='不满足要求')


def check_grassroots(req: str, work_months: int) -> ConditionCheckItem:
    """
    检查基层工作年限

    :param req: 岗位基层年限要求
    :param work_months: 用户总工作月数
    :return:
    """
    if is_unlimited(req):
        return ConditionCheckItem(name='基层年限', requirement=req, passed=True, reason='不限')

    required_years = parse_grassroots_years(req)
    if required_years == 0:
        return ConditionCheckItem(name='基层年限', requirement=req, passed=True, reason='不限')

    user_years = max(work_months, 0) // 12
    user_value = f'{user_years} 年'

    if user_years >= required_years:
        return ConditionCheckItem(name='基层年限', requirement=req, user_value=user_value, passed=True, reason='满足')

    return ConditionCheckItem(
        name='基层年限',
        requirement=req,
        user_value=user_value,
        passed=False,
        reason=f'不足 {required_years} 年',
    )


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
        educations = profile.educations or []

        checks: list[ConditionCheckItem] = []
        reasons: list[str] = []

        education_check = check_education(gangwei.education or '', educations)
        checks.append(education_check)
        if not education_check.passed:
            reasons.append(f'学历: {education_check.reason}')

        degree_check = check_degree(gangwei.degree or '', educations)
        checks.append(degree_check)
        if not degree_check.passed:
            reasons.append(f'学位: {degree_check.reason}')

        major_check = check_major(gangwei.major or '', educations, major_index)
        checks.append(major_check)
        if not major_check.passed:
            reasons.append(f'专业: {major_check.reason}')

        politics_check = check_politics(gangwei.politics or '', profile.politics)
        checks.append(politics_check)
        if not politics_check.passed:
            reasons.append(f'政治面貌: {politics_check.reason}')

        age_check = check_age(gangwei.age_requirement or '', profile.birth_date)
        checks.append(age_check)
        if not age_check.passed:
            reasons.append(f'年龄: {age_check.reason}')

        gender_check = check_gender(gangwei.gender_requirement or '', profile.gender)
        checks.append(gender_check)
        if not gender_check.passed:
            reasons.append(f'性别: {gender_check.reason}')

        grassroots_check = check_grassroots(gangwei.grassroots_years or '', profile.total_work_years)
        checks.append(grassroots_check)
        if not grassroots_check.passed:
            reasons.append(f'基层年限: {grassroots_check.reason}')

        return CanApplyResult(
            can_apply=len(reasons) == 0,
            reasons=reasons,
            checks=checks,
        )


gangwei_match_service: GangweiMatchService = GangweiMatchService()
