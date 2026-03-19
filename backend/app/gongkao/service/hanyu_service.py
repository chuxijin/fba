#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_hanyu import hanyu_dao
from backend.app.gongkao.model import GkHanyu
from backend.app.gongkao.schema.hanyu import (
    CreateHanyuParam,
    DeleteHanyuParam,
    HanyuParam,
    UpdateHanyuParam,
)
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data


class HanyuService:
    """汉语词汇服务类"""

    @staticmethod
    async def _fetch_from_baidu(name: str) -> dict[str, Any] | None:
        """
        从百度汉语 API 获取词汇详情

        :param name: 词语名称
        :return:
        """
        url = 'https://hanyuapp.baidu.com/dictapp/swan/termdetail'
        params = {
            'wd': name,
            'client': 'pc',
            'source_tag': '2',
            'lesson_from': 'xiaodu',
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return data
        except Exception as e:
            log.error(f'从百度汉语获取词汇 "{name}" 失败: {e}')
            return None

    @staticmethod
    async def _parse_baidu_response(data: dict[str, Any]) -> dict[str, Any]:
        """
        解析百度汉语 API 响应

        :param data: API 响应数据
        :return:
        """
        result = {}

        if not data or data.get('errno') != 0:
            return result

        term_data = data.get('data', {})

        result['pinyin'] = term_data.get('pinyin')
        result['baobian'] = term_data.get('baobian')
        result['structure'] = term_data.get('structure')
        result['voice'] = term_data.get('voice')

        definition_info = term_data.get('definitionInfo', {})
        if definition_info:
            result['definition_info'] = {
                'definition': definition_info.get('definition'),
                'wordFormation': definition_info.get('wordFormation'),
            }

            detail_means = definition_info.get('detailMeans', [])
            if detail_means:
                result['detail_means'] = detail_means

        liju_list = term_data.get('liju', [])
        if liju_list:
            result['liju'] = [item.get('name') for item in liju_list if item.get('name')]

        antonym_list = term_data.get('antonym', [])
        if antonym_list:
            result['antonym'] = [item.get('name') for item in antonym_list if item.get('name')]

        synonyms_list = term_data.get('synonyms', [])
        if synonyms_list:
            result['synonyms'] = [item.get('name') for item in synonyms_list if item.get('name')]

        chu_chu_list = term_data.get('chuChu', [])
        if chu_chu_list:
            result['chu_chu'] = [
                {
                    'source': item.get('source'),
                    'dynasty': item.get('dynasty'),
                    'author': item.get('author'),
                    'sourceChapter': item.get('sourceChapter'),
                    'citeOriginalText': item.get('citeOriginalText'),
                }
                for item in chu_chu_list
            ]

        yin_zheng_list = term_data.get('yinZheng', [])
        if yin_zheng_list:
            result['yin_zheng'] = [
                {
                    'source': item.get('source'),
                    'dynasty': item.get('dynasty'),
                    'author': item.get('author'),
                    'sourceChapter': item.get('sourceChapter'),
                    'citeOriginalText': item.get('citeOriginalText'),
                }
                for item in yin_zheng_list
            ]

        return {k: v for k, v in result.items() if v}

    @staticmethod
    async def _is_data_complete(hanyu: GkHanyu) -> bool:
        """
        检查数据是否完整

        :param hanyu: 汉语词汇对象
        :return:
        """
        return hanyu.pinyin is not None or hanyu.definition_info is not None

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkHanyu:
        """
        获取详情

        :param db: 数据库会话
        :param pk: ID
        :return:
        """
        hanyu = await hanyu_dao.get(db, pk)
        if not hanyu:
            raise errors.NotFoundError(msg='汉语词汇不存在')

        if not await HanyuService._is_data_complete(hanyu):
            log.info(f'词汇 "{hanyu.name}" 数据不完整，尝试从百度汉语获取')

            baidu_data = await HanyuService._fetch_from_baidu(hanyu.name)
            if baidu_data:
                parsed_data = await HanyuService._parse_baidu_response(baidu_data)
                if parsed_data:
                    update_obj = UpdateHanyuParam(**parsed_data)
                    await hanyu_dao.update(db, pk, update_obj, updated_by=1)
                    await db.commit()
                    await db.refresh(hanyu)
                    log.info(f'成功更新词汇 "{hanyu.name}" 的详细信息')
                else:
                    log.warning(f'百度汉语返回数据无法解析: {hanyu.name}')
            else:
                log.warning(f'无法从百度汉语获取词汇 "{hanyu.name}" 的详细信息')

        return hanyu

    @staticmethod
    async def get_by_name(*, db: AsyncSession, name: str, type_: str | None = None) -> GkHanyu:
        """
        根据名称获取详情

        :param db: 数据库会话
        :param name: 词语名称
        :param type_: 类型
        :return:
        """
        hanyu = await hanyu_dao.get_by_name(db, name, type_)
        if not hanyu:
            raise errors.NotFoundError(msg='汉语词汇不存在')
        return hanyu

    @staticmethod
    async def get_list(*, db: AsyncSession, params: HanyuParam) -> dict[str, Any]:
        """
        获取列表（分页）

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        hanyu_select = await hanyu_dao.get_select(params)
        return await paging_data(db, hanyu_select)

    @staticmethod
    async def get_types(*, db: AsyncSession) -> list[str]:
        """
        获取所有类型

        :param db: 数据库会话
        :return:
        """
        return await hanyu_dao.get_types(db)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateHanyuParam, created_by: int) -> GkHanyu:
        """
        创建

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        existing = await hanyu_dao.get_by_name(db, obj.name, obj.type)
        if existing:
            raise errors.ForbiddenError(msg=f'词语 "{obj.name}" 在类型 "{obj.type}" 下已存在')
        return await hanyu_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateHanyuParam, updated_by: int) -> int:
        """
        更新

        :param db: 数据库会话
        :param pk: ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        hanyu = await hanyu_dao.get(db, pk)
        if not hanyu:
            raise errors.NotFoundError(msg='汉语词汇不存在')
        if obj.name and obj.type and (obj.name != hanyu.name or obj.type != hanyu.type):
            existing = await hanyu_dao.get_by_name(db, obj.name, obj.type)
            if existing:
                raise errors.ForbiddenError(msg=f'词语 "{obj.name}" 在类型 "{obj.type}" 下已存在')
        return await hanyu_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteHanyuParam) -> int:
        """
        删除

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await hanyu_dao.delete(db, obj.ids)

    @staticmethod
    async def increment_frequency(*, db: AsyncSession, pk: int) -> int:
        """
        增加使用频次

        :param db: 数据库会话
        :param pk: ID
        :return:
        """
        hanyu = await hanyu_dao.get(db, pk)
        if not hanyu:
            raise errors.NotFoundError(msg='汉语词汇不存在')
        return await hanyu_dao.increment_frequency(db, pk)


hanyu_service: HanyuService = HanyuService()
