from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.question_bank_v2.schema.question import GetQuestionSearchItem
from backend.app.question_bank_v2.service.question_service import question_service
from backend.common.exception import errors
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

# 公开检索接口：小程序未登录也能搜题，因此不能挂在题目管理路由上
router = APIRouter()


@router.get(
    '/search',
    summary='公开题目检索',
    name='qbank_v2_search_questions',
    dependencies=[DependsPagination],
)
async def search_questions(
    db: CurrentSession,
    *,
    keyword: Annotated[str, Query(min_length=1, max_length=100, description='题干、选项或解析关键词')],
    domain_category_id: Annotated[int | None, Query(gt=0, description='领域根分类 ID；不传则不限领域')] = None,
) -> ResponseSchemaModel[PageData[GetQuestionSearchItem]]:
    """按关键词检索公开题库中的题目（题干 / 选项 / 解析任一命中）

    返回题干、选项与默认解析，不含标准答案。
    """
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise errors.RequestError(msg='搜索关键词不能为空')

    stmt = await question_service.get_public_search_select(
        db=db,
        keyword=normalized_keyword,
        domain_category_id=domain_category_id,
    )
    # 结果集含 JSONB 选项列，SQLAlchemy 行不可哈希；查询本身已按题目去重，无需再 unique
    page_data = await paging_data(db, stmt, GetQuestionSearchItem, unique=False)
    return response_base.success(data=page_data)
