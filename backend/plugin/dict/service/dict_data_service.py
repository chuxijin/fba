import re

from collections.abc import Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.plugin.dict.crud.crud_dict_data import dict_data_dao
from backend.plugin.dict.crud.crud_dict_type import dict_type_dao
from backend.plugin.dict.model import DictData
from backend.plugin.dict.schema.dict_data import CreateDictDataParam, DeleteDictDataParam, UpdateDictDataParam


class DictDataService:
    """字典数据服务类"""

    @staticmethod
    async def _validate_exam_target(
        db: AsyncSession, obj: CreateDictDataParam | UpdateDictDataParam, code: str, existing: DictData | None = None,
    ) -> None:
        from pydantic import ValidationError

        from backend.app.question_bank_v2.schema.study_goal import EXAM_TARGET_DICT_CODE, ExamTargetConfig
        from backend.app.question_bank_v2.service.study_goal_service import study_goal_service

        if (
            existing is not None
            and getattr(existing, 'type_code', None) == EXAM_TARGET_DICT_CODE
            and code != EXAM_TARGET_DICT_CODE
        ):
            raise errors.RequestError(msg='备考目标不可改为其他字典类型；请停用或新增字典数据')
        if code != EXAM_TARGET_DICT_CODE:
            return
        if re.fullmatch(r'[a-z0-9_]{1,32}', obj.value) is None:
            raise errors.RequestError(msg='备考目标编码只允许小写字母、数字和下划线，最多32字符')
        if db is not None and db.get_bind().dialect.name == 'postgresql':
            # 同类目录写入很少；事务锁避免两次并发录入绕过编码查重，无需新增索引/字段。
            await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('dict:study_exam_target'))"))
        duplicates = await dict_data_dao.get_by_value_and_type_code(db, obj.value, code)
        if any(item.id != getattr(existing, 'id', None) for item in duplicates):
            raise errors.ConflictError(msg='备考目标编码已存在')
        if existing is not None and existing.value != obj.value:
            raise errors.RequestError(msg='备考目标编码为稳定引用，不可修改；请新增另一目标')
        extra = obj.extra if 'extra' in obj.model_fields_set or existing is None else existing.extra
        if not extra and obj.status == 0:
            return
        try:
            config = ExamTargetConfig.model_validate(extra)
        except ValidationError as exc:
            raise errors.RequestError(msg='备考目标扩展配置不合法，请检查科目、年度与模块配额') from exc
        # 资源已下线时仍可停用目标，但非空配置的结构必须有效。
        if obj.status != 0:
            await study_goal_service.validate_config(db=db, config=config)

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> DictData:
        """
        获取字典数据详情

        :param db: 数据库会话
        :param pk: 字典数据 ID
        :return:
        """
        dict_data = await dict_data_dao.get(db, pk)
        if not dict_data:
            raise errors.NotFoundError(msg='字典数据不存在')
        return dict_data

    @staticmethod
    async def get_by_type_code(*, db: AsyncSession, code: str) -> Sequence[DictData]:
        """
        获取字典数据详情

        :param db: 数据库会话
        :param code: 字典类型编码
        :return:
        """
        dict_datas = await dict_data_dao.get_by_type_code(db, code)
        if not dict_datas:
            raise errors.NotFoundError(msg='字典数据不存在')
        return dict_datas

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[DictData]:
        """
        获取所有字典数据

        :param db: 数据库会话
        :return:
        """
        dict_datas = await dict_data_dao.get_all(db)
        return dict_datas

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        type_code: str | None,
        label: str | None,
        value: str | None,
        status: int | None,
        type_id: int | None,
    ) -> dict[str, Any]:
        """
        获取字典数据列表

        :param db: 数据库会话
        :param type_code: 字典类型编码
        :param label: 字典数据标签
        :param value: 字典数据键值
        :param status: 状态
        :param type_id: 字典类型 ID
        :return:
        """
        dict_data_select = await dict_data_dao.get_select(
            type_code=type_code,
            label=label,
            value=value,
            status=status,
            type_id=type_id,
        )
        return await paging_data(db, dict_data_select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateDictDataParam) -> None:
        """
        创建字典数据

        :param db: 数据库会话
        :param obj: 字典数据创建参数
        :return:
        """
        dict_type = await dict_type_dao.get(db, obj.type_id)
        if not dict_type:
            raise errors.NotFoundError(msg='字典类型不存在')
        await DictDataService._validate_exam_target(db, obj, dict_type.code)
        dict_data = await dict_data_dao.get_by_label_and_type_code(db, obj.label, dict_type.code)
        if dict_data:
            raise errors.ConflictError(msg='字典数据已存在')
        await dict_data_dao.create(db, obj, dict_type.code)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateDictDataParam) -> int:
        """
        更新字典数据

        :param db: 数据库会话
        :param pk: 字典数据 ID
        :param obj: 字典数据更新参数
        :return:
        """
        dict_data = await dict_data_dao.get(db, pk)
        if not dict_data:
            raise errors.NotFoundError(msg='字典数据不存在')
        dict_type = await dict_type_dao.get(db, obj.type_id)
        if not dict_type:
            raise errors.NotFoundError(msg='字典类型不存在')
        await DictDataService._validate_exam_target(db, obj, dict_type.code, dict_data)
        if dict_data.label != obj.label or dict_data.type_code != dict_type.code:
            new_dict_data = await dict_data_dao.get_by_label_and_type_code(db, obj.label, dict_type.code)
            if new_dict_data and new_dict_data.id != pk:
                raise errors.ConflictError(msg='字典数据已存在')
        count = await dict_data_dao.update(db, pk, obj, dict_type.code)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteDictDataParam) -> int:
        """
        批量删除字典数据

        :param db: 数据库会话
        :param obj: 字典数据 ID 列表
        :return:
        """
        count = await dict_data_dao.delete(db, obj.pks)
        return count


dict_data_service: DictDataService = DictDataService()
