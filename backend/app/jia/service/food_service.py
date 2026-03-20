#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_food import food_dao
from backend.app.jia.model.food import HealthyFood
from backend.app.jia.schema.food import CreateFoodParam, GetFoodDetail, UpdateFoodParam
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.utils.embedding import embed


def generate_nutrition_tags(food: HealthyFood | CreateFoodParam | UpdateFoodParam) -> list[str]:
    """
    根据营养素数值生成语义标签

    :param food: 食物对象或参数
    :return: 标签列表
    """
    tags = []

    # 获取属性值的辅助函数
    def get_float(attr: str) -> float | None:
        val = getattr(food, attr, None)
        return float(val) if val is not None else None

    # 蛋白质标签
    protein = get_float('protein')
    if protein is not None:
        if protein >= 20:
            tags.append('高蛋白')
        elif protein >= 10:
            tags.append('中等蛋白')

    # 脂肪标签
    fat = get_float('fat')
    if fat is not None:
        if fat < 3:
            tags.append('低脂')
        elif fat >= 20:
            tags.append('高脂')

    # 碳水标签
    carb = get_float('carbohydrate')
    if carb is not None:
        if carb < 10:
            tags.append('低碳水')
        elif carb >= 50:
            tags.append('高碳水')

    # 膳食纤维标签
    fiber = get_float('fiber')
    if fiber is not None and fiber >= 5:
        tags.append('高纤维')

    # 能量标签
    energy = get_float('energy')
    if energy is not None:
        if energy < 50:
            tags.append('低卡')
        elif energy >= 300:
            tags.append('高热量')

    # 维生素标签
    if get_float('vitamin_c') is not None and get_float('vitamin_c') >= 30:
        tags.append('富含维生素C')
    if get_float('calcium') is not None and get_float('calcium') >= 100:
        tags.append('高钙')
    if get_float('iron') is not None and get_float('iron') >= 3:
        tags.append('富含铁')

    return tags


def build_embed_text(
    name: str,
    alias: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    energy: float | None = None,
    protein: float | None = None,
    fat: float | None = None,
    carbohydrate: float | None = None,
) -> str:
    """
    构建用于向量化的文本

    :param name: 食物名称
    :param alias: 别名
    :param description: 描述
    :param tags: 营养特征标签
    :param energy: 热量
    :param protein: 蛋白质
    :param fat: 脂肪
    :param carbohydrate: 碳水化合物
    :return: 向量化文本
    """
    parts = [f'名称: {name}']

    if alias:
        parts.append(f'别名: {alias}')
    if description:
        parts.append(f'描述: {description}')
    if tags:
        parts.append(f'特征: {", ".join(tags)}')

    # 主要营养素摘要
    nutrients = []
    if energy is not None:
        nutrients.append(f'热量{energy:.0f}kcal')
    if protein is not None:
        nutrients.append(f'蛋白质{protein:.1f}g')
    if fat is not None:
        nutrients.append(f'脂肪{fat:.1f}g')
    if carbohydrate is not None:
        nutrients.append(f'碳水{carbohydrate:.1f}g')
    if nutrients:
        parts.append(f'营养: {", ".join(nutrients)}')

    return ', '.join(parts)


class FoodService:

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> HealthyFood:
        """获取食物详情"""
        food = await food_dao.get(db, pk)
        if not food:
            raise errors.NotFoundError(msg='食物不存在')
        return food

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        name: str | None = None,
        category_id: int | None = None,
        status: bool | None = None,
        semantic: bool = False,
        limit: int = 20,
    ) -> dict[str, Any] | list[HealthyFood]:
        """
        获取食物列表（支持普通搜索和语义搜索）

        :param db: 数据库会话
        :param name: 名称/搜索关键词
        :param category_id: 分类 ID
        :param status: 状态
        :param semantic: 是否启用语义搜索
        :param limit: 语义搜索返回数量
        :return:
        """
        if semantic and name:
            # 语义搜索模式
            try:
                vector = await embed(name)
                return await food_dao.search_by_vector(db, vector, limit=limit)
            except Exception as e:
                log.error(f'语义搜索向量化失败: {e}')
                # 降级为普通搜索

        # 普通分页搜索
        select_stmt = await food_dao.get_list(name=name, category_id=category_id, status=status)
        return await paging_data(db, select_stmt, schema_cls=GetFoodDetail)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateFoodParam) -> None:
        """创建食物"""
        if await food_dao.get_by_name(db, obj.name):
            raise errors.ConflictError(msg='该食物名称已存在')
        if obj.barcode and await food_dao.get_by_barcode(db, obj.barcode):
            raise errors.ConflictError(msg='该条形码已存在')

        # 生成营养标签和向量化文本
        tags = generate_nutrition_tags(obj)
        text_to_embed = build_embed_text(
            name=obj.name,
            alias=obj.alias,
            description=obj.description,
            tags=tags,
            energy=obj.energy,
            protein=obj.protein,
            fat=obj.fat,
            carbohydrate=obj.carbohydrate,
        )

        try:
            vector = await embed(text_to_embed)
        except Exception as e:
            raise errors.ServerError(msg=f'食物创建失败: 向量化服务异常 - {str(e)}')

        await food_dao.create(db, obj, vector=vector)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateFoodParam) -> int:
        """更新食物"""
        food = await food_dao.get(db, pk)
        if not food:
            raise errors.NotFoundError(msg='食物不存在')

        if obj.name and obj.name != food.name:
            if await food_dao.get_by_name(db, obj.name):
                raise errors.ConflictError(msg='该食物名称已存在')

        if obj.barcode and obj.barcode != food.barcode:
            if await food_dao.get_by_barcode(db, obj.barcode):
                raise errors.ConflictError(msg='该条形码已存在')

        # 检查是否需要更新向量
        vector = None
        update_data = obj.model_dump(exclude_unset=True)
        vector_fields = ['name', 'alias', 'description', 'energy', 'protein', 'fat', 'carbohydrate', 'fiber']
        if any(k in update_data for k in vector_fields):
            # 合并新旧值
            new_name = obj.name if obj.name is not None else food.name
            new_alias = obj.alias if obj.alias is not None else (food.alias or '')
            new_desc = obj.description if obj.description is not None else (food.description or '')
            new_energy = obj.energy if obj.energy is not None else food.energy
            new_protein = obj.protein if obj.protein is not None else food.protein
            new_fat = obj.fat if obj.fat is not None else food.fat
            new_carb = obj.carbohydrate if obj.carbohydrate is not None else food.carbohydrate

            # 创建临时对象用于生成标签
            class MergedFood:
                pass

            merged = MergedFood()
            merged.protein = new_protein
            merged.fat = new_fat
            merged.carbohydrate = new_carb
            merged.fiber = obj.fiber if obj.fiber is not None else food.fiber
            merged.energy = new_energy
            merged.vitamin_c = obj.vitamin_c if obj.vitamin_c is not None else food.vitamin_c
            merged.calcium = obj.calcium if obj.calcium is not None else food.calcium
            merged.iron = obj.iron if obj.iron is not None else food.iron

            tags = generate_nutrition_tags(merged)
            text_to_embed = build_embed_text(
                name=new_name,
                alias=new_alias,
                description=new_desc,
                tags=tags,
                energy=float(new_energy) if new_energy else None,
                protein=float(new_protein) if new_protein else None,
                fat=float(new_fat) if new_fat else None,
                carbohydrate=float(new_carb) if new_carb else None,
            )

            try:
                vector = await embed(text_to_embed)
            except Exception as e:
                log.error(f'更新食物向量化失败: {e}')

        return await food_dao.update(db, pk, obj, vector=vector)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: list[int]) -> int:
        """删除食物"""
        return await food_dao.delete(db, pk)


food_service: FoodService = FoodService()
