#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import time

from typing import Any
from urllib.parse import quote

import requests


def print_section(title: str) -> None:
    """打印分段标题"""
    print(f'\n===== {title} =====', flush=True)


def print_json(value: Any) -> None:
    """
    打印 JSON

    :param value: 待打印对象
    :return:
    """
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str), flush=True)


def join_openlist_path(parent: str, name: str) -> str:
    """
    拼接 OpenList 路径

    :param parent: 父路径
    :param name: 子路径名称
    :return:
    """
    clean_parent = (parent or '/').rstrip('/') or '/'
    clean_name = name.strip('/')
    if clean_parent == '/':
        return f'/{clean_name}'
    return f'{clean_parent}/{clean_name}'


def import_with_trace(module_name: str) -> Any:
    """
    带耗时日志导入模块

    :param module_name: 模块名
    :return:
    """
    start_time = time.time()
    print(f'stage=import_start module={module_name}', flush=True)
    module = importlib.import_module(module_name)
    elapsed = time.time() - start_time
    print(f'stage=import_done module={module_name} elapsed={elapsed:.2f}s', flush=True)
    return module


def get_required_env(name: str) -> str:
    """
    获取必填环境变量

    :param name: 环境变量名称
    :return:
    """
    value = os.getenv(name, '').strip()
    if not value:
        raise RuntimeError(f'缺少环境变量: {name}')
    return value


def openlist_request(
    *,
    method: str,
    base_url: str,
    token: str,
    path: str,
    data: dict[str, Any] | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """
    请求 OpenList API

    :param method: HTTP 方法
    :param base_url: OpenList 地址
    :param token: OpenList Token
    :param path: API 路径
    :param data: 请求体
    :param timeout: 超时时间
    :return:
    """
    headers = {'Authorization': token, 'Content-Type': 'application/json'}
    url = f'{base_url.rstrip("/")}{path}'
    if method == 'GET':
        response = requests.get(url, headers=headers, timeout=timeout)
    else:
        response = requests.post(url, headers=headers, json=data or {}, timeout=timeout)

    try:
        payload = response.json()
    except ValueError:
        payload = {'raw': response.text[:500]}

    return {'status_code': response.status_code, 'payload': payload}


def upload_text_file(base_url: str, token: str, directory: str, file_name: str, content: str) -> dict[str, Any]:
    """
    上传文本文件到 OpenList

    :param base_url: OpenList 地址
    :param token: OpenList Token
    :param directory: 目标目录
    :param file_name: 文件名
    :param content: 文件内容
    :return:
    """
    file_path = join_openlist_path(directory, file_name)
    url = f'{base_url.rstrip("/")}/api/fs/put'
    common_headers = {
        'Authorization': token,
        'Content-Type': 'application/octet-stream',
        'As-Task': 'false',
    }
    payload_bytes = content.encode('utf-8')
    last_result: dict[str, Any] | None = None

    for header_path in [quote(file_path, safe=''), file_path]:
        headers = dict(common_headers)
        headers['File-Path'] = header_path
        response = requests.put(url, headers=headers, data=payload_bytes, timeout=30)
        try:
            payload = response.json()
        except ValueError:
            payload = {'raw': response.text[:500]}

        last_result = {'status_code': response.status_code, 'payload': payload}
        if response.status_code == 200 and isinstance(payload, dict) and payload.get('code') in (200, 0):
            return last_result

    raise RuntimeError(f'OpenList 上传失败: {file_path}, result={last_result}')


def assert_openlist_ok(result: dict[str, Any]) -> dict[str, Any]:
    """
    校验 OpenList 响应

    :param result: 请求结果
    :return:
    """
    payload = result['payload']
    if result['status_code'] != 200:
        raise RuntimeError(f'HTTP {result["status_code"]}: {payload}')
    if isinstance(payload, dict) and payload.get('code') not in (200, 0):
        raise RuntimeError(f'OpenList code={payload.get("code")}: {payload.get("message")}')
    return payload.get('data') if isinstance(payload, dict) else payload


def run_raw_readonly(base_url: str, token: str) -> None:
    """
    执行 OpenList 原生 API 只读测试

    :param base_url: OpenList 地址
    :param token: OpenList Token
    :return:
    """
    print_section('RAW_OPENLIST_ACCOUNT')
    account_result = openlist_request(method='GET', base_url=base_url, token=token, path='/api/me')
    account_data = assert_openlist_ok(account_result)
    print_json({
        'username': account_data.get('username'),
        'id': account_data.get('id'),
        'role': account_data.get('role'),
        'disabled': account_data.get('disabled'),
    })

    print_section('RAW_OPENLIST_ROOT_LIST')
    list_result = openlist_request(
        method='POST',
        base_url=base_url,
        token=token,
        path='/api/fs/list',
        data={'path': '/', 'page': 1, 'per_page': 50, 'refresh': False},
    )
    list_data = assert_openlist_ok(list_result)
    content = list_data.get('content') or []
    print_json({
        'total': list_data.get('total'),
        'write': list_data.get('write'),
        'names': [item.get('name') for item in content[:20]],
    })


async def run_project_readonly(base_url: str, token: str) -> None:
    """
    执行项目封装只读测试

    :param base_url: OpenList 地址
    :param token: OpenList Token
    :return:
    """
    print_section('PROJECT_OPENLIST_CLIENT')
    print('stage=import_project_modules', flush=True)
    enum_module = import_with_trace('backend.app.coulddrive.schema.enum')
    file_schema_module = import_with_trace('backend.app.coulddrive.schema.file')
    service_module = import_with_trace('backend.app.coulddrive.service.coulddrive_service')

    DriveType = enum_module.DriveType
    ListFilesParam = file_schema_module.ListFilesParam
    UserInfoParam = file_schema_module.UserInfoParam
    CouldDriveService = service_module.CouldDriveService

    print('stage=create_service', flush=True)
    service = CouldDriveService(auth_data={'token': token}, drive_type=DriveType.OPENLIST_DRIVE)
    print('stage=get_user_info_start', flush=True)
    user_info = await asyncio.wait_for(
        service.get_user_info(UserInfoParam(drive_type=DriveType.OPENLIST_DRIVE)),
        timeout=30,
    )
    print('stage=get_user_info_done', flush=True)
    print('stage=get_disk_list_start', flush=True)
    file_list = await asyncio.wait_for(
        service.get_disk_list(ListFilesParam(drive_type=DriveType.OPENLIST_DRIVE, file_path='/')),
        timeout=30,
    )
    print('stage=get_disk_list_done', flush=True)
    print_json({
        'user': user_info.model_dump(
            include={'username', 'user_id', 'quota', 'used', 'is_vip', 'is_supervip'},
            mode='json',
        ),
        'files': [item.file_name for item in file_list[:20]],
    })


async def run_db_readonly() -> None:
    """执行数据库只读诊断"""
    print_section('DB_READONLY')
    from sqlalchemy import text

    from backend.database.db import async_db_session

    legacy_openlist_type = 'A' + 'listDrive'
    async with async_db_session() as db:
        tables_result = await db.execute(
            text(
                """
                select table_name
                from information_schema.tables
                where table_schema = current_schema()
                  and table_name in ('yp_user', 'filesync_config', 'filesync_task', 'filesync_task_item')
                order by table_name
                """
            )
        )
        tables = [row[0] for row in tables_result.all()]

        account_result = await db.execute(
            text(
                """
                select id, type, username, is_valid
                from yp_user
                where type in ('OpenListDrive', :legacy_openlist_type)
                order by id desc
                limit 10
                """
            ),
            {'legacy_openlist_type': legacy_openlist_type},
        )
        accounts = [
            {'id': row[0], 'type': row[1], 'username': row[2], 'is_valid': row[3]}
            for row in account_result.all()
        ]

        config_result = await db.execute(
            text(
                """
                select id, type, src_path, dst_path, method, enable
                from filesync_config
                where type in ('OpenListDrive', :legacy_openlist_type)
                order by id desc
                limit 10
                """
            ),
            {'legacy_openlist_type': legacy_openlist_type},
        )
        configs = [
            {
                'id': row[0],
                'type': row[1],
                'src_path': row[2],
                'dst_path': row[3],
                'method': row[4],
                'enable': row[5],
            }
            for row in config_result.all()
        ]

    print_json({'tables': tables, 'openlist_accounts': accounts, 'openlist_sync_configs': configs})


def mkdir(base_url: str, token: str, path: str) -> None:
    """
    创建 OpenList 目录

    :param base_url: OpenList 地址
    :param token: OpenList Token
    :param path: 目录路径
    :return:
    """
    assert_openlist_ok(
        openlist_request(
            method='POST',
            base_url=base_url,
            token=token,
            path='/api/fs/mkdir',
            data={'path': path},
        )
    )


def remove(base_url: str, token: str, directory: str, names: list[str]) -> None:
    """
    删除 OpenList 文件

    :param base_url: OpenList 地址
    :param token: OpenList Token
    :param directory: 父目录
    :param names: 名称列表
    :return:
    """
    assert_openlist_ok(
        openlist_request(
            method='POST',
            base_url=base_url,
            token=token,
            path='/api/fs/remove',
            data={'dir': directory, 'names': names},
        )
    )


def run_write_openlist_smoke(base_url: str, token: str, parent: str, keep: bool) -> None:
    """
    执行 OpenList 写入 smoke 测试

    :param base_url: OpenList 地址
    :param token: OpenList Token
    :param parent: 测试父目录
    :param keep: 是否保留测试目录
    :return:
    """
    print_section('WRITE_OPENLIST_SMOKE')
    test_name = f'__fba_openlist_diag_{int(time.time())}'
    test_root = f'{parent.rstrip("/")}/{test_name}'
    renamed_name = 'renamed_folder'
    copied_parent = f'{test_root}/copy_target'

    mkdir(base_url, token, test_root)
    mkdir(base_url, token, f'{test_root}/old_folder')
    mkdir(base_url, token, copied_parent)

    rename_result = openlist_request(
        method='POST',
        base_url=base_url,
        token=token,
        path='/api/fs/rename',
        data={'path': f'{test_root}/old_folder', 'name': renamed_name},
    )
    assert_openlist_ok(rename_result)

    copy_result = openlist_request(
        method='POST',
        base_url=base_url,
        token=token,
        path='/api/fs/copy',
        data={'src_dir': test_root, 'dst_dir': copied_parent, 'names': [renamed_name]},
    )
    copy_payload = copy_result['payload']

    list_result = openlist_request(
        method='POST',
        base_url=base_url,
        token=token,
        path='/api/fs/list',
        data={'path': test_root, 'page': 1, 'per_page': 20, 'refresh': True},
    )
    list_data = assert_openlist_ok(list_result)

    print_json({
        'test_root': test_root,
        'rename_ok': True,
        'copy_response': copy_payload,
        'root_names_after': [item.get('name') for item in (list_data.get('content') or [])],
        'cleanup': not keep,
    })

    if not keep:
        remove(base_url, token, parent.rstrip('/') or '/', [test_name])
        print_json({'cleanup_done': test_root})


async def run_project_write_smoke(token: str, parent: str, keep: bool) -> None:
    """
    执行项目 OpenList 封装写入 smoke 测试

    :param token: OpenList Token
    :param parent: 测试父目录
    :param keep: 是否保留测试目录
    :return:
    """
    print_section('PROJECT_WRITE_SMOKE')
    enum_module = import_with_trace('backend.app.coulddrive.schema.enum')
    file_schema_module = import_with_trace('backend.app.coulddrive.schema.file')
    service_module = import_with_trace('backend.app.coulddrive.service.coulddrive_service')

    DriveType = enum_module.DriveType
    CopyParam = file_schema_module.CopyParam
    ListFilesParam = file_schema_module.ListFilesParam
    MkdirParam = file_schema_module.MkdirParam
    RemoveParam = file_schema_module.RemoveParam
    RenameParam = file_schema_module.RenameParam
    CouldDriveService = service_module.CouldDriveService

    drive_type = DriveType.OPENLIST_DRIVE
    service = CouldDriveService(auth_data={'token': token}, drive_type=drive_type)
    test_name = f'__fba_project_openlist_diag_{int(time.time())}'
    test_root = f'{parent.rstrip("/")}/{test_name}'
    old_folder = f'{test_root}/old_folder'
    renamed_name = 'renamed_folder'
    renamed_folder = f'{test_root}/{renamed_name}'
    copied_parent = f'{test_root}/copy_target'
    copy_ok = False
    rename_ok = False
    cleanup_done = False

    try:
        await service.mkdir(MkdirParam(drive_type=drive_type, file_path=test_root))
        await service.mkdir(MkdirParam(drive_type=drive_type, file_path=old_folder))
        await service.mkdir(MkdirParam(drive_type=drive_type, file_path=copied_parent))

        rename_ok = await service.rename(
            RenameParam(
                drive_type=drive_type,
                file_path=old_folder,
                new_name=renamed_name,
            )
        )
        copy_ok = await service.copy(
            CopyParam(
                drive_type=drive_type,
                file_paths=[renamed_folder],
                target_path=copied_parent,
            )
        )

        root_items = await service.get_disk_list(ListFilesParam(drive_type=drive_type, file_path=test_root))
        copied_items = await service.get_disk_list(ListFilesParam(drive_type=drive_type, file_path=copied_parent))
        print_json({
            'test_root': test_root,
            'rename_ok': rename_ok,
            'copy_ok': copy_ok,
            'root_names_after': [item.file_name for item in root_items],
            'copy_target_names_after': [item.file_name for item in copied_items],
            'cleanup': not keep,
        })
    finally:
        if not keep:
            try:
                cleanup_done = await service.remove(
                    RemoveParam(
                        drive_type=drive_type,
                        file_paths=[test_root],
                    )
                )
            finally:
                print_json({'cleanup_done': cleanup_done, 'test_root': test_root})


async def run_project_sync_smoke(base_url: str, token: str, parent: str, keep: bool) -> None:
    """
    执行项目同步服务 smoke 测试

    :param base_url: OpenList 地址
    :param token: OpenList Token
    :param parent: 测试父目录
    :param keep: 是否保留测试目录
    :return:
    """
    print_section('PROJECT_SYNC_SMOKE')
    enum_module = import_with_trace('backend.app.coulddrive.schema.enum')
    file_schema_module = import_with_trace('backend.app.coulddrive.schema.file')
    service_module = import_with_trace('backend.app.coulddrive.service.coulddrive_service')
    filesync_module = import_with_trace('backend.app.coulddrive.service.filesync_service')

    DriveType = enum_module.DriveType
    RecursionSpeed = enum_module.RecursionSpeed
    SyncMethod = enum_module.SyncMethod
    DiskTargetDefinition = file_schema_module.DiskTargetDefinition
    ListFilesParam = file_schema_module.ListFilesParam
    ShareSourceDefinition = file_schema_module.ShareSourceDefinition
    CouldDriveService = service_module.CouldDriveService
    FileSyncService = filesync_module.FileSyncService

    drive_type = DriveType.OPENLIST_DRIVE
    coulddrive_service = CouldDriveService(auth_data={'token': token}, drive_type=drive_type)
    filesync_service = FileSyncService()
    test_name = f'__fba_project_sync_diag_{int(time.time())}'
    test_root = join_openlist_path(parent, test_name)

    def sync_source(path: str) -> Any:
        return ShareSourceDefinition(file_path=path, source_type='local', source_id='')

    def sync_target(path: str) -> Any:
        return DiskTargetDefinition(file_path=path, file_id=path)

    async def list_names(path: str) -> list[str]:
        files = await coulddrive_service.get_disk_list(ListFilesParam(drive_type=drive_type, file_path=path))
        return [item.file_name for item in files]

    async def run_sync(source_path: str, target_path: str, method: str) -> dict[str, Any]:
        return await filesync_service.perform_sync(
            token,
            drive_type,
            sync_source(source_path),
            sync_target(target_path),
            method,
            recursion_speed=RecursionSpeed.FAST,
            max_depth=10,
        )

    cleanup_done = False
    try:
        copy_source = join_openlist_path(test_root, 'copy_source')
        copy_target = join_openlist_path(test_root, 'copy_target')
        rename_source = join_openlist_path(test_root, 'rename_source')
        rename_target = join_openlist_path(test_root, 'rename_target')
        rename_source_dir = join_openlist_path(rename_source, 'new_folder')
        rename_target_dir = join_openlist_path(rename_target, 'old_folder')
        protect_source = join_openlist_path(test_root, 'protect_source')
        protect_target = join_openlist_path(test_root, 'protect_target')

        for directory in [
            test_root,
            copy_source,
            copy_target,
            rename_source,
            rename_target,
            rename_source_dir,
            rename_target_dir,
            protect_source,
            protect_target,
        ]:
            mkdir(base_url, token, directory)

        upload_text_file(base_url, token, copy_source, 'seed.txt', 'copy smoke\n')
        upload_text_file(base_url, token, rename_source_dir, 'same.txt', 'same folder fingerprint\n')
        upload_text_file(base_url, token, rename_target_dir, 'same.txt', 'same folder fingerprint\n')
        upload_text_file(base_url, token, protect_source, 'source_only.txt', 'source only\n')
        upload_text_file(base_url, token, protect_target, 'target_only.txt', 'target only\n')

        copy_result = await run_sync(copy_source, copy_target, SyncMethod.INCREMENTAL.value)
        rename_result = await run_sync(rename_source, rename_target, SyncMethod.INCREMENTAL.value)
        protect_result = await run_sync(protect_source, protect_target, SyncMethod.INCREMENTAL.value)

        print_json({
            'test_root': test_root,
            'copy_new_file': {
                'success': copy_result.get('success'),
                'files_transferred': copy_result.get('stats', {}).get('files_transferred'),
                'target_names_after': await list_names(copy_target),
            },
            'same_parent_folder_rename': {
                'success': rename_result.get('success'),
                'folders_renamed': rename_result.get('stats', {}).get('folders_renamed'),
                'target_names_after': await list_names(rename_target),
            },
            'structure_change_protection': {
                'success': protect_result.get('success'),
                'local_protection_skipped': protect_result.get('stats', {}).get('local_protection_skipped'),
                'warnings': protect_result.get('stats', {}).get('warnings', []),
                'target_names_after': await list_names(protect_target),
            },
            'cleanup': not keep,
        })
    finally:
        if not keep:
            try:
                remove(base_url, token, parent.rstrip('/') or '/', [test_name])
                cleanup_done = True
            finally:
                print_json({'cleanup_done': cleanup_done, 'test_root': test_root})


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='OpenList / coulddrive 同步诊断脚本')
    parser.add_argument('--project', action='store_true', help='验证项目 OpenListClient / CouldDriveService 只读链路')
    parser.add_argument('--db', action='store_true', help='验证数据库表和 OpenList 记录，只读')
    parser.add_argument('--write-openlist-smoke', action='store_true', help='执行 OpenList 写入 smoke 测试')
    parser.add_argument('--project-write-smoke', action='store_true', help='执行项目 OpenList 封装写入 smoke 测试')
    parser.add_argument('--project-sync-smoke', action='store_true', help='执行项目同步服务 smoke 测试')
    parser.add_argument('--smoke-parent', default='/同步目录', help='写入 smoke 测试父目录')
    parser.add_argument('--keep-smoke-dir', action='store_true', help='保留写入 smoke 测试目录')
    return parser.parse_args()


async def async_main() -> None:
    """脚本入口"""
    args = parse_args()
    base_url = get_required_env('OPENLIST_BASE_URL')
    token = get_required_env('OPENLIST_TOKEN')
    os.environ['OPENLIST_BASE_URL'] = base_url

    run_raw_readonly(base_url, token)

    if args.project:
        await run_project_readonly(base_url, token)

    if args.db:
        await run_db_readonly()

    if args.write_openlist_smoke:
        run_write_openlist_smoke(base_url, token, args.smoke_parent, args.keep_smoke_dir)

    if args.project_write_smoke:
        await run_project_write_smoke(token, args.smoke_parent, args.keep_smoke_dir)

    if args.project_sync_smoke:
        await run_project_sync_smoke(base_url, token, args.smoke_parent, args.keep_smoke_dir)


if __name__ == '__main__':
    asyncio.run(async_main())
