#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.study_plan.crud import study_plan_record_dao
from backend.app.study_plan.model.item import StudyPlanItem
from backend.app.study_plan.schema.item import GetStudyPlanItemDetail
from backend.app.study_plan.schema.record import GetStudyPlanRecordDetail


async def build_item_detail(db: AsyncSession, item: StudyPlanItem) -> GetStudyPlanItemDetail:
    """
    构造计划项详情

    :param db: 数据库会话
    :param item: 计划项
    :return:
    """
    detail = GetStudyPlanItemDetail.model_validate(item)
    record = await study_plan_record_dao.get_latest_by_item(db, item.id)
    if record is not None:
        detail.latest_record = GetStudyPlanRecordDetail.model_validate(record)
    return detail


async def build_item_details(db: AsyncSession, items: Sequence[StudyPlanItem]) -> list[GetStudyPlanItemDetail]:
    """
    批量构造计划项详情

    :param db: 数据库会话
    :param items: 计划项列表
    :return:
    """
    item_list = list(items)
    item_ids = [item.id for item in item_list]
    records = await study_plan_record_dao.list_latest_by_items(db, item_ids)
    record_map = {record.item_id: record for record in records}

    details: list[GetStudyPlanItemDetail] = []
    for item in item_list:
        detail = GetStudyPlanItemDetail.model_validate(item)
        record = record_map.get(item.id)
        if record is not None:
            detail.latest_record = GetStudyPlanRecordDetail.model_validate(record)
        details.append(detail)

    return details
