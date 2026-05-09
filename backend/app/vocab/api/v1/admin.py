#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, File, Form, Path, Query, Request, UploadFile
from starlette.responses import Response

from backend.app.vocab.schema.book import (
    BatchAddWordsParam,
    BatchRemoveWordsParam,
    CreateBookParam,
    GetBookDetail,
    UpdateBookParam,
)
from backend.app.vocab.schema.vocab_import import VocabExcelImportResult
from backend.app.vocab.schema.word import CreateWordParam, GetWordDetail, UpdateWordParam
from backend.app.vocab.service.book_service import book_service
from backend.app.vocab.service.vocab_import_service import vocab_import_service
from backend.app.vocab.service.word_service import word_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/vocab/admin', tags=['单词本管理'], dependencies=[DependsJwtAuth])


# ============ 词书管理 ============
@router.post('/books', summary='创建词书')
async def create_book(request: Request, db: CurrentSession, obj: CreateBookParam) -> ResponseSchemaModel[GetBookDetail]:
    """创建词书"""
    data = await book_service.create_book(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put('/books/{pk}', summary='更新词书')
async def update_book(
    db: CurrentSession,
    pk: Annotated[int, Path(description='词书 ID')],
    obj: UpdateBookParam,
) -> ResponseModel:
    """更新词书"""
    count = await book_service.update_book(db=db, pk=pk, obj=obj)
    return response_base.success(data={'updated': count})


@router.delete('/books/{pk}', summary='删除词书')
async def delete_book(db: CurrentSession, pk: Annotated[int, Path(description='词书 ID')]) -> ResponseModel:
    """删除词书"""
    count = await book_service.delete_book(db=db, pk=pk)
    return response_base.success(data={'deleted': count})


@router.get('/books', summary='词书列表', dependencies=[DependsPagination])
async def get_book_list(
    db: CurrentSession,
    category: Annotated[str | None, Query(description='分类过滤')] = None,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
    is_official: Annotated[bool | None, Query(description='是否官方')] = None,
    status: Annotated[int | None, Query(description='状态过滤')] = None,
) -> ResponseModel:
    """获取词书列表"""
    data = await book_service.get_book_list(db=db, category=category, keyword=keyword, is_official=is_official, status=status)
    return response_base.success(data=data)


@router.get('/books/{pk}', summary='词书详情')
async def get_book_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='词书 ID')],
) -> ResponseSchemaModel[GetBookDetail]:
    """获取词书详情"""
    data = await book_service.get_book_detail(db=db, pk=pk)
    return response_base.success(data=data)


@router.post('/books/{pk}/words', summary='批量添加单词到词书')
async def add_words_to_book(
    db: CurrentSession,
    pk: Annotated[int, Path(description='词书 ID')],
    obj: BatchAddWordsParam,
) -> ResponseModel:
    """批量添加单词到词书"""
    count = await book_service.add_words_to_book(db=db, pk=pk, obj=obj)
    return response_base.success(data={'added': count})


@router.delete('/books/{pk}/words', summary='批量从词书移除单词')
async def remove_words_from_book(
    db: CurrentSession,
    pk: Annotated[int, Path(description='词书 ID')],
    obj: BatchRemoveWordsParam,
) -> ResponseModel:
    """批量从词书移除单词"""
    count = await book_service.remove_words_from_book(db=db, pk=pk, obj=obj)
    return response_base.success(data={'removed': count})


# ============ 单词管理 ============
@router.post('/words', summary='创建单词')
async def create_word(request: Request, db: CurrentSession, obj: CreateWordParam) -> ResponseSchemaModel[GetWordDetail]:
    """创建单词"""
    data = await word_service.create_word(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put('/words/{pk}', summary='更新单词')
async def update_word(
    db: CurrentSession,
    pk: Annotated[int, Path(description='单词 ID')],
    obj: UpdateWordParam,
) -> ResponseModel:
    """更新单词"""
    count = await word_service.update_word(db=db, pk=pk, obj=obj)
    return response_base.success(data={'updated': count})


@router.delete('/words/{pk}', summary='删除单词')
async def delete_word(db: CurrentSession, pk: Annotated[int, Path(description='单词 ID')]) -> ResponseModel:
    """删除单词"""
    count = await word_service.delete_word(db=db, pk=pk)
    return response_base.success(data={'deleted': count})


@router.get('/words', summary='单词列表', dependencies=[DependsPagination])
async def get_word_list(
    db: CurrentSession,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
) -> ResponseModel:
    """获取单词列表"""
    data = await word_service.get_word_list(db=db, keyword=keyword)
    return response_base.success(data=data)


@router.get('/words/{pk}', summary='单词详情')
async def get_word_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='单词 ID')],
) -> ResponseSchemaModel[GetWordDetail]:
    """获取单词详情"""
    data = await word_service.get_word_detail(db=db, pk=pk)
    return response_base.success(data=data)


# ============ Excel 导入 ============
@router.get('/import/template', summary='下载单词导入模板')
async def download_import_template() -> Response:
    """下载 Excel 导入模板"""
    content = await vocab_import_service.build_import_template()
    return Response(
        content=content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=vocab_import_template.xlsx'},
    )


@router.post('/import-excel', summary='从 Excel 导入单词')
async def import_from_excel(
    request: Request,
    db: CurrentSessionTransaction,
    file: Annotated[UploadFile, File(description='Excel 文件（.xlsx）')],
    book_id: Annotated[int | None, Form(description='目标词书 ID，为空则仅创建单词')] = None,
) -> ResponseSchemaModel[VocabExcelImportResult]:
    """
    从 Excel 导入单词

    - 按模板格式填写单词、释义、例句等
    - 支持同时关联到指定词书
    - 已存在的单词自动跳过或仅做词书关联
    """
    content = await file.read()
    rows = await vocab_import_service.parse_excel_file(content=content, filename=file.filename)
    data = await vocab_import_service.import_from_excel(
        db=db,
        book_id=book_id,
        rows=rows,
        user_id=request.user.id,
    )
    return response_base.success(data=data)
