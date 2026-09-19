from typing import Annotated, Any

from fastapi import APIRouter, Query

from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.plugin.feishu.schema.sheet import (
    SheetAppendParam,
    SheetAppendResult,
    SheetBatchAppendParam,
    SheetBatchAppendResult,
    SheetDropdownInfo,
    SheetDropdownParam,
    SheetInfo,
    SheetInsertRowsParam,
    SheetResizeParam,
    SheetStyleParam,
    SheetUpdateResult,
    SheetWriteParam,
)
from backend.plugin.feishu.service.sheet_service import feishu_sheet_service

router = APIRouter()


@router.get('/sheets', summary='获取电子表格子表列表', dependencies=[DependsJwtAuth])
async def get_feishu_sheets(
    workbook: Annotated[str, Query(description='表格链接或 token，留空使用默认配置')] = '',
) -> ResponseSchemaModel[list[SheetInfo]]:
    """
    获取电子表格的子表列表

    :param workbook: 表格链接或 token
    :return:
    """
    sheets = await feishu_sheet_service.list_sheets(workbook)
    data = [
        SheetInfo(
            sheet_id=str(item.get('sheet_id') or ''),
            title=str(item.get('title') or ''),
            index=int(item.get('index') or 0),
            row_count=int((item.get('grid_properties') or {}).get('row_count') or 0),
            column_count=int((item.get('grid_properties') or {}).get('column_count') or 0),
            hidden=bool(item.get('hidden')),
        )
        for item in sheets
    ]
    return response_base.success(data=data)


@router.get('/read', summary='读取单元格数据', dependencies=[DependsJwtAuth])
async def read_feishu_cells(
    workbook: Annotated[str, Query(description='表格链接或 token，留空使用默认配置')] = '',
    sheet: Annotated[str | None, Query(description='子表名称或 sheet_id，留空使用默认子表')] = None,
    cell_range: Annotated[str, Query(description='A1 范围，如 A1:F10')] = 'A1:Z1000',
) -> ResponseSchemaModel[list[list[Any]]]:
    """
    读取单元格数据

    :param workbook: 表格链接或 token
    :param sheet: 子表名称或 sheet_id
    :param cell_range: A1 范围
    :return:
    """
    values = await feishu_sheet_service.read(workbook=workbook, sheet=sheet, cell_range=cell_range)
    return response_base.success(data=values)


@router.post('/write', summary='写入指定范围', dependencies=[DependsJwtAuth])
async def write_feishu_cells(param: SheetWriteParam) -> ResponseSchemaModel[SheetUpdateResult]:
    """
    写入指定范围（会覆盖目标区域原有内容）

    :param param: 写入参数
    :return:
    """
    updates = await feishu_sheet_service.write(
        workbook=param.workbook,
        sheet=param.sheet,
        cell_range=param.cell_range,
        values=param.values,
    )
    return response_base.success(data=SheetUpdateResult.from_updates(updates))


@router.post('/append', summary='追加数据到数据区末尾', dependencies=[DependsJwtAuth])
async def append_feishu_rows(param: SheetAppendParam) -> ResponseSchemaModel[SheetAppendResult]:
    """
    追加数据到数据区末尾，表头行不受影响

    :param param: 追加参数
    :return:
    """
    raw = await feishu_sheet_service.append(
        workbook=param.workbook,
        sheet=param.sheet,
        rows=param.rows,
        header_rows=param.header_rows,
    )
    return response_base.success(data=SheetAppendResult.from_raw(raw))


@router.post('/batch-append', summary='批量追加（同一工作簿合并为一次请求）', dependencies=[DependsJwtAuth])
async def batch_append_feishu_rows(
    param: SheetBatchAppendParam,
) -> ResponseSchemaModel[list[SheetBatchAppendResult]]:
    """
    批量追加，同一工作簿内的多个子表会合并为一次 HTTP 请求

    :param param: 批量追加参数
    :return:
    """
    raw = await feishu_sheet_service.batch_append(
        jobs=[
            {
                'workbook': job.workbook,
                'sheet': job.sheet,
                'rows': job.rows,
                'header_rows': job.header_rows,
            }
            for job in param.jobs
        ]
    )
    data = [
        SheetBatchAppendResult(
            workbook_token=str(item.get('workbook_token') or ''),
            ranges=[str(item) for item in item.get('ranges') or []],
            revision=int(item.get('revision') or 0),
        )
        for item in raw
    ]
    return response_base.success(data=data)


@router.post('/insert-rows', summary='在指定位置插入空行', dependencies=[DependsJwtAuth])
async def insert_feishu_rows(param: SheetInsertRowsParam) -> ResponseModel:
    """
    在指定位置插入空行，新行插入到 position 行之前

    :param param: 插入行参数
    :return:
    """
    await feishu_sheet_service.insert_rows(
        workbook=param.workbook,
        sheet=param.sheet,
        position=param.position,
        count=param.count,
        inherit_style=param.inherit_style,
    )
    return response_base.success()


@router.put('/style', summary='设置单元格样式', dependencies=[DependsJwtAuth])
async def set_feishu_style(param: SheetStyleParam) -> ResponseSchemaModel[SheetUpdateResult]:
    """
    设置单元格样式（不改变单元格的值与公式）

    :param param: 样式参数
    :return:
    """
    style = feishu_sheet_service.build_style(
        bold=param.style.bold,
        italic=param.style.italic,
        font_size=param.style.font_size,
        font_color=param.style.font_color,
        background_color=param.style.background_color,
        horizontal_alignment=param.style.horizontal_alignment,
        vertical_alignment=param.style.vertical_alignment,
        border_type=param.style.border_type,
        border_color=param.style.border_color,
    )
    updates = await feishu_sheet_service.set_style(
        workbook=param.workbook,
        sheet=param.sheet,
        cell_range=param.cell_range,
        style=style,
    )
    return response_base.success(data=SheetUpdateResult.from_updates(updates))


@router.post('/dropdown', summary='设置下拉列表', dependencies=[DependsJwtAuth])
async def set_feishu_dropdown(param: SheetDropdownParam) -> ResponseModel:
    """
    为单元格范围设置下拉列表

    :param param: 下拉列表参数
    :return:
    """
    await feishu_sheet_service.set_dropdown(
        workbook=param.workbook,
        sheet=param.sheet,
        cell_range=param.cell_range,
        options=param.options,
        multiple=param.multiple,
        highlight=param.highlight,
        colors=param.colors,
    )
    return response_base.success()


@router.get('/dropdown', summary='查询下拉列表', dependencies=[DependsJwtAuth])
async def get_feishu_dropdown(
    workbook: Annotated[str, Query(description='表格链接或 token，留空使用默认配置')] = '',
    sheet: Annotated[str | None, Query(description='子表名称或 sheet_id，留空使用默认子表')] = None,
    cell_range: Annotated[str, Query(description='A1 范围，如 E1:E100')] = 'A1:Z1000',
) -> ResponseSchemaModel[list[SheetDropdownInfo]]:
    """
    查询下拉列表配置

    :param workbook: 表格链接或 token
    :param sheet: 子表名称或 sheet_id
    :param cell_range: A1 范围
    :return:
    """
    raw = await feishu_sheet_service.get_dropdown(workbook=workbook, sheet=sheet, cell_range=cell_range)
    return response_base.success(data=[SheetDropdownInfo.from_raw(item) for item in raw])


@router.delete('/dropdown', summary='删除下拉列表', dependencies=[DependsJwtAuth])
async def delete_feishu_dropdown(
    workbook: Annotated[str, Query(description='表格链接或 token，留空使用默认配置')] = '',
    sheet: Annotated[str | None, Query(description='子表名称或 sheet_id，留空使用默认子表')] = None,
    cell_range: Annotated[str, Query(description='A1 范围，如 E1:E100')] = 'A1:Z1000',
) -> ResponseModel:
    """
    删除下拉列表配置

    :param workbook: 表格链接或 token
    :param sheet: 子表名称或 sheet_id
    :param cell_range: A1 范围
    :return:
    """
    await feishu_sheet_service.delete_dropdown(workbook=workbook, sheet=sheet, cell_range=cell_range)
    return response_base.success()


@router.put('/resize', summary='调整行高列宽', dependencies=[DependsJwtAuth])
async def resize_feishu_dimension(param: SheetResizeParam) -> ResponseModel:
    """
    调整行高或列宽

    :param param: 行列尺寸参数
    :return:
    """
    await feishu_sheet_service.resize(
        workbook=param.workbook,
        sheet=param.sheet,
        dimension=param.dimension,
        start=param.start,
        end=param.end,
        size=param.size,
    )
    return response_base.success()
