#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response, StreamingResponse

from backend.app.coulddrive.schema.file import (
    BaseFileInfo,
    BaseShareInfo,
    BatchRenameParam,  # 导入批量重命名参数
    CancelShareParam,
    CopyParam,
    ListFilesParam,
    ListShareFilesParam,
    ListShareInfoParam,
    MkdirParam,
    MoveParam,
    RemoveParam,
    RenameParam,
    ShareParam,
    TransferParam,
)
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService, DriveAuthError
from backend.app.coulddrive.service.fileoprate_service import FileOperateService
from backend.common.pagination import DependsPagination, PageData, _CustomPageParams, paging_list_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()

# 全局服务实例，确保进度数据在同一个实例中
file_operate_service_instance = None


@router.get('/list', summary='获取文件列表', description='获取网盘文件列表，支持缓存加速', response_model=ResponseSchemaModel[PageData[BaseFileInfo]], dependencies=[DependsJwtAuth, DependsPagination])
async def get_file_list(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: Annotated[ListFilesParam, Depends()],
    page_params: Annotated[_CustomPageParams, DependsPagination],
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID（内部调用必传）")] = None
) -> ResponseSchemaModel[dict[str, Any]] | Response:
    """
    获取文件列表，支持智能缓存

    两种调用方式：
    1. 内部调用：传 drive_account_id，自动校验所有权
    2. 外部调试：不传 drive_account_id，直接用 x_token
    """
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        file_list = await service.get_disk_list(
            params=params,
            db=db,
            drive_account_id=drive_account_id
        )

        page_data = paging_list_data(file_list, page_params)
        return response_base.success(data=page_data)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))


@router.get(
    '/listshare',
    summary='获取分享文件列表',
    description='获取分享来源的文件列表，支持缓存加速',
    response_model=ResponseSchemaModel[PageData[BaseFileInfo]],
    dependencies=[DependsJwtAuth, DependsPagination]
)
async def get_share_file_list(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: Annotated[ListShareFilesParam, Depends()],
    page_params: Annotated[_CustomPageParams, DependsPagination],
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID（内部调用必传）")] = None
) -> ResponseSchemaModel[dict[str, Any]] | Response:
    """获取分享文件列表，支持智能缓存"""
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        file_list = await service.get_share_list(
            params=params,
            db=db,
            drive_account_id=drive_account_id
        )

        page_data = paging_list_data(file_list, page_params)
        return response_base.success(data=page_data)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))


@router.post(
    '/mkdir',
    summary='创建文件夹',
    description='在网盘中创建文件夹',
    response_model=ResponseSchemaModel[BaseFileInfo],
    dependencies=[DependsJwtAuth]
)
async def create_folder(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: MkdirParam,
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID")] = None
) -> ResponseSchemaModel[BaseFileInfo] | Response:
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        folder_info = await service.mkdir(params=params)
        return response_base.success(data=folder_info)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))


@router.post(
    '/rename',
    summary='重命名文件或文件夹',
    description='重命名网盘中的文件或文件夹',
    response_model=ResponseSchemaModel[bool],
    dependencies=[DependsJwtAuth]
)
async def rename_file(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: RenameParam,
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID")] = None
) -> ResponseSchemaModel[bool] | Response:
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        result = await service.rename(params=params)
        return response_base.success(data=result)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))


@router.post(
    '/move',
    summary='移动文件或文件夹',
    description='移动网盘中的文件或文件夹到指定目录',
    response_model=ResponseSchemaModel[bool],
    dependencies=[DependsJwtAuth]
)
async def move_files(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: MoveParam,
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID")] = None
) -> ResponseSchemaModel[bool] | Response:
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        result = await service.move(params=params)
        return response_base.success(data=result)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))


@router.post(
    '/copy',
    summary='复制文件或文件夹',
    description='复制网盘中的文件或文件夹到指定目录',
    response_model=ResponseSchemaModel[bool],
    dependencies=[DependsJwtAuth]
)
async def copy_files(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: CopyParam,
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID")] = None
) -> ResponseSchemaModel[bool] | Response:
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        result = await service.copy(params=params)
        return response_base.success(data=result)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))


@router.delete(
    '/remove',
    summary='删除文件或文件夹',
    description='删除网盘中的文件或文件夹',
    response_model=ResponseSchemaModel[bool],
    dependencies=[DependsJwtAuth]
)
async def remove_files(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: RemoveParam,
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID")] = None
) -> ResponseSchemaModel[bool] | Response:
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        result = await service.remove(params=params)
        return response_base.success(data=result)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))


@router.post(
    '/transfer',
    summary='转存文件',
    description='从分享来源转存文件到自己的网盘',
    response_model=ResponseSchemaModel[bool],
    dependencies=[DependsJwtAuth]
)
async def transfer_files(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: TransferParam,
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID")] = None
) -> ResponseSchemaModel[bool] | Response:
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        result = await service.transfer_files(params=params)
        return response_base.success(data=result)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))


@router.post(
    '/batch_rename',
    summary='批量重命名文件或文件夹',
    description='对选定的网盘文件或文件夹进行批量重命名，支持递归和规则模板',
    response_model=ResponseSchemaModel[dict[str, Any]],
    dependencies=[DependsJwtAuth]
)
async def batch_rename_files(
    db: CurrentSession,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: BatchRenameParam,
) -> ResponseSchemaModel[dict[str, Any]] | Response:
    """批量重命名文件或文件夹"""
    global file_operate_service_instance
    if not file_operate_service_instance:
        file_operate_service_instance = FileOperateService()
    
    # 使用前端传递的task_id，如果没有则生成一个
    import uuid
    temp_task_id = params.task_id or str(int(str(uuid.uuid4().int)[:8]))
    
    # 在开始长时间处理前，先获取账户信息和模板信息，然后释放数据库连接
    try:
        # 快速获取账户ID，避免长时间持有数据库连接
        from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
        account_id = await drive_account_dao.get_id_by_cookies(db, x_token)
        if not account_id:
            return response_base.fast_success(res=CustomResponse(400, "无法获取网盘账户信息"))
        account_key = str(account_id)
        
        # 如果有模板ID，预先获取模板信息
        template_data = None
        if params.template_id:
            try:
                from backend.app.coulddrive.crud.crud_rule_template import rule_template_dao
                template = await rule_template_dao.get(db, params.template_id)
                if template and template.rule_config:
                    template_data = template.rule_config
            except Exception as e:
                return response_base.fast_success(res=CustomResponse(400, f"获取重命名模板失败: {str(e)}"))
        
        # 初始化进度信息
        file_operate_service_instance.update_progress(temp_task_id, {
            'type': 'start',
            'message': '开始批量重命名...',
            'current_folder': '',
            'current_file': '',
            'completed': 0,
            'total': 0
        })
        
        # 定义进度回调函数
        async def progress_callback(progress_data):
            file_operate_service_instance.update_progress(temp_task_id, progress_data)
        
        # 调用服务层，传递进度回调（不传递数据库连接，避免长时间持有）
        result = await file_operate_service_instance.batch_rename_files_with_progress(
            x_token, params, task_id=temp_task_id, db=None, account_key=account_key,
            progress_callback=progress_callback, template_data=template_data
        )
        
        # 标记任务完成
        file_operate_service_instance.update_progress(temp_task_id, {
            'type': 'complete',
            'message': '批量重命名完成',
            'stats': result
        })
        return response_base.success(data=result)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except Exception as e:
        return response_base.fast_success(res=CustomResponse(500, f"批量重命名失败: {str(e)}"))


@router.get(
    '/batch-rename-progress/{task_id}',
    summary='获取批量重命名进度',
    description='通过SSE获取批量重命名实时进度',
)
async def get_batch_rename_progress(task_id: str):
    """获取批量重命名进度 - SSE"""
    global file_operate_service_instance
    if not file_operate_service_instance:
        file_operate_service_instance = FileOperateService()
    
    return StreamingResponse(
        file_operate_service_instance.progress_stream_generator(task_id),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        }
    )


@router.get(
    '/shareinfo',
    summary='获取分享详情信息',
    description='获取分享详情信息，支持外部分享链接信息获取和本地分享列表获取',
    response_model=ResponseSchemaModel[list[BaseShareInfo]],
    dependencies=[DependsJwtAuth]
)
async def get_share_info(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: Annotated[ListShareInfoParam, Depends()],
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID")] = None
) -> ResponseSchemaModel[list[BaseShareInfo]] | Response:
    """
    获取分享详情信息

    :param db: 数据库会话
    :param request: 请求对象
    :param x_token: 认证令牌
    :param params: 分享详情查询参数
    :param drive_account_id: 网盘账户ID
    :return: 分享详情信息列表
    """
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        share_info_result = await service.get_share_info(params=params)

        # 如果返回的是包含分页信息的字典，提取列表部分
        if isinstance(share_info_result, dict) and 'list' in share_info_result:
            share_info_list: list[BaseShareInfo] = share_info_result['list']
        else:
            share_info_list = share_info_result

        return response_base.success(data=share_info_list)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))


@router.post(
    '/share',
    summary='创建分享链接',
    description='创建文件或文件夹的分享链接',
    response_model=ResponseSchemaModel[BaseShareInfo],
    dependencies=[DependsJwtAuth]
)
async def create_share(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: ShareParam,
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID")] = None
) -> ResponseSchemaModel[BaseShareInfo] | Response:
    """
    创建分享链接

    :param db: 数据库会话
    :param request: 请求对象
    :param x_token: 认证令牌
    :param params: 分享参数
    :param drive_account_id: 网盘账户ID
    :return: 分享信息
    """
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        share_info = await service.create_share(params=params)
        return response_base.success(data=share_info)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))


@router.delete(
    '/share/cancel',
    summary='取消分享链接',
    description='取消已创建的分享链接',
    response_model=ResponseSchemaModel[bool],
    dependencies=[DependsJwtAuth]
)
async def cancel_share(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: CancelShareParam,
    drive_account_id: Annotated[int | None, Query(description="网盘账户ID")] = None
) -> ResponseSchemaModel[bool] | Response:
    """
    取消分享链接

    :param db: 数据库会话
    :param request: 请求对象
    :param x_token: 认证令牌
    :param params: 取消分享参数
    :param drive_account_id: 网盘账户ID
    :return: 是否成功取消
    """
    try:
        service = CouldDriveService.create_from_request(
            db=db,
            request=request,
            x_token=x_token,
            drive_type=params.drive_type,
            drive_account_id=drive_account_id
        )

        result = await service.cancel_share(params=params)
        return response_base.success(data=result)

    except DriveAuthError as e:
        return response_base.fast_success(res=CustomResponse(401, f'网盘认证已失效，请更新 Cookie: {e}'))
    except PermissionError as e:
        return response_base.fast_success(res=CustomResponse(403, str(e)))
    except ValueError as e:
        return response_base.fast_success(res=CustomResponse(404, str(e)))
