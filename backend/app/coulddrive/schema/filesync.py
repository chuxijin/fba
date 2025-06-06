#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from backend.app.coulddrive.schema.enum import DriveType, RecursionSpeed, SyncMethod
from backend.common.schema import SchemaBase


class CreateSyncConfigParam(SchemaBase):
    """创建同步配置参数"""
    
    enable: bool = Field(True, description="是否启用")
    remark: str | None = Field(None, description="备注")
    type: DriveType = Field(..., description="网盘类型")
    src_path: str = Field(..., description="源路径")
    src_meta: str | None = Field(None, description="源路径元数据")
    dst_path: str = Field(..., description="目标路径")
    dst_meta: str | None = Field(None, description="目标路径元数据")
    user_id: int = Field(..., description="关联账号ID")
    cron: str | None = Field(None, description="定时任务表达式")
    speed: int = Field(0, description="同步速度")
    method: SyncMethod = Field(SyncMethod.INCREMENTAL, description="同步方法")
    end_time: datetime | None = Field(None, description="结束时间")
    exclude: str | None = Field(None, description="排除规则")
    rename: str | None = Field(None, description="重命名规则")

    @field_validator('src_path', 'dst_path')
    @classmethod
    def validate_paths(cls, v: str) -> str:
        """验证路径格式"""
        if not v:
            raise ValueError("路径不能为空")
        if not v.startswith('/'):
            v = '/' + v
        return v


class UpdateSyncConfigParam(SchemaBase):
    """更新同步配置参数"""
    
    enable: bool | None = Field(None, description="是否启用")
    remark: str | None = Field(None, description="备注")
    type: DriveType | None = Field(None, description="网盘类型")
    src_path: str | None = Field(None, description="源路径")
    src_meta: str | None = Field(None, description="源路径元数据")
    dst_path: str | None = Field(None, description="目标路径")
    dst_meta: str | None = Field(None, description="目标路径元数据")
    user_id: int | None = Field(None, description="关联账号ID")
    cron: str | None = Field(None, description="定时任务表达式")
    speed: int | None = Field(None, description="同步速度")
    method: SyncMethod | None = Field(None, description="同步方法")
    end_time: datetime | None = Field(None, description="结束时间")
    exclude: str | None = Field(None, description="排除规则")
    rename: str | None = Field(None, description="重命名规则")


class CreateSyncTaskParam(SchemaBase):
    """创建同步任务参数"""
    
    config_id: int = Field(..., description="配置ID")
    status: str = Field("pending", description="任务状态")
    err_msg: str | None = Field(None, description="错误信息")
    start_time: datetime | None = Field(None, description="开始时间")
    task_num: str | None = Field(None, description="任务统计信息")
    dura_time: int = Field(0, description="持续时间")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """验证任务状态"""
        allowed_status = ['pending', 'running', 'completed', 'failed', 'cancelled']
        if v not in allowed_status:
            raise ValueError(f"任务状态必须是 {allowed_status} 之一")
        return v


class UpdateSyncTaskParam(SchemaBase):
    """更新同步任务参数"""
    
    status: str | None = Field(None, description="任务状态")
    err_msg: str | None = Field(None, description="错误信息")
    start_time: datetime | None = Field(None, description="开始时间")
    task_num: str | None = Field(None, description="任务统计信息")
    dura_time: int | None = Field(None, description="持续时间")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """验证任务状态"""
        if v is not None:
            allowed_status = ['pending', 'running', 'completed', 'failed', 'cancelled']
            if v not in allowed_status:
                raise ValueError(f"任务状态必须是 {allowed_status} 之一")
        return v


class CreateSyncTaskItemParam(SchemaBase):
    """创建同步任务项参数"""
    
    task_id: int = Field(..., description="任务ID")
    type: str = Field(..., description="操作类型")
    src_path: str = Field(..., description="源文件路径")
    dst_path: str = Field(..., description="目标文件路径")
    file_name: str = Field(..., description="文件名")
    file_size: int = Field(0, description="文件大小")
    status: str = Field("pending", description="状态")
    err_msg: str | None = Field(None, description="错误信息")

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """验证操作类型"""
        allowed_types = ['delete', 'rename', 'copy', 'move', 'create']
        if v not in allowed_types:
            raise ValueError(f"操作类型必须是 {allowed_types} 之一")
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """验证状态"""
        allowed_status = ['pending', 'running', 'completed', 'failed']
        if v not in allowed_status:
            raise ValueError(f"状态必须是 {allowed_status} 之一")
        return v


class UpdateSyncTaskItemParam(SchemaBase):
    """更新同步任务项参数"""
    
    type: str | None = Field(None, description="操作类型")
    src_path: str | None = Field(None, description="源文件路径")
    dst_path: str | None = Field(None, description="目标文件路径")
    file_name: str | None = Field(None, description="文件名")
    file_size: int | None = Field(None, description="文件大小")
    status: str | None = Field(None, description="状态")
    err_msg: str | None = Field(None, description="错误信息")

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        """验证操作类型"""
        if v is not None:
            allowed_types = ['delete', 'rename', 'copy', 'move', 'create']
            if v not in allowed_types:
                raise ValueError(f"操作类型必须是 {allowed_types} 之一")
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """验证状态"""
        if v is not None:
            allowed_status = ['pending', 'running', 'completed', 'failed']
            if v not in allowed_status:
                raise ValueError(f"状态必须是 {allowed_status} 之一")
        return v


class ExecuteSyncParam(SchemaBase):
    """执行同步参数"""
    
    config_id: int = Field(..., description="配置ID")
    force: bool = Field(False, description="是否强制执行")
    dry_run: bool = Field(False, description="是否试运行")
    recursion_speed: RecursionSpeed = Field(RecursionSpeed.NORMAL, description="递归速度")
    exclude_rules: str | None = Field(None, description="排除规则JSON")
    rename_rules: str | None = Field(None, description="重命名规则JSON")


class GetSyncConfigDetail(SchemaBase):
    """同步配置详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="配置ID")
    enable: bool = Field(..., description="是否启用")
    remark: str | None = Field(None, description="备注")
    type: DriveType = Field(..., description="网盘类型")
    src_path: str = Field(..., description="源路径")
    src_meta: str | None = Field(None, description="源路径元数据")
    dst_path: str = Field(..., description="目标路径")
    dst_meta: str | None = Field(None, description="目标路径元数据")
    user_id: int = Field(..., description="关联账号ID")
    cron: str | None = Field(None, description="定时任务表达式")
    speed: int = Field(..., description="同步速度")
    method: SyncMethod = Field(..., description="同步方法")
    end_time: datetime | None = Field(None, description="结束时间")
    exclude: str | None = Field(None, description="排除规则")
    rename: str | None = Field(None, description="重命名规则")
    last_sync: datetime | None = Field(None, description="最后同步时间")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: datetime | None = Field(None, description="更新时间")
    created_by: int = Field(..., description="创建人")
    
    @field_validator('type', mode='before')
    @classmethod
    def validate_type(cls, v):
        """将数据库中的字符串值转换为枚举"""
        if isinstance(v, str):
            # 优先通过枚举值匹配（数据库中存储的是枚举值）
            for drive_type in DriveType:
                if drive_type.value == v:
                    return drive_type
            
            # 兼容旧格式的名称匹配
            legacy_mapping = {
                "BAIDU_DRIVE": DriveType.BAIDU_DRIVE,
                "QUARK_DRIVE": DriveType.QUARK_DRIVE,
            }
            if v in legacy_mapping:
                return legacy_mapping[v]
            
            # 如果都找不到，直接抛出验证错误
            raise ValueError(f"无效的网盘类型: {v}，支持的类型: {[dt.value for dt in DriveType]}")
        return v
    
    @field_validator('method', mode='before')
    @classmethod
    def validate_method(cls, v):
        """将数据库中的字符串值转换为枚举"""
        if isinstance(v, str):
            # 处理数据库中可能存在的不同格式
            if v == "1":
                return SyncMethod.INCREMENTAL
            elif v == "copy":
                return SyncMethod.INCREMENTAL
            elif v == "incremental":
                return SyncMethod.INCREMENTAL
            elif v == "full":
                return SyncMethod.FULL
            elif v == "overwrite":
                return SyncMethod.OVERWRITE
            # 尝试直接匹配枚举值
            for sync_method in SyncMethod:
                if sync_method.value == v:
                    return sync_method
        return v


class GetSyncTaskDetail(SchemaBase):
    """同步任务详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="任务ID")
    config_id: int = Field(..., description="配置ID")
    status: str = Field(..., description="任务状态")
    err_msg: str | None = Field(None, description="错误信息")
    start_time: datetime | None = Field(None, description="开始时间")
    task_num: str | None = Field(None, description="任务统计信息")
    dura_time: int = Field(..., description="持续时间")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: datetime = Field(..., description="更新时间")
    created_by: int = Field(..., description="创建人")
    updated_by: int = Field(..., description="更新人")


class GetSyncTaskItemDetail(SchemaBase):
    """同步任务项详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="任务项ID")
    task_id: int = Field(..., description="任务ID")
    type: str = Field(..., description="操作类型")
    src_path: str = Field(..., description="源文件路径")
    dst_path: str = Field(..., description="目标文件路径")
    file_name: str = Field(..., description="文件名")
    file_size: int = Field(..., description="文件大小")
    status: str = Field(..., description="状态")
    err_msg: str | None = Field(None, description="错误信息")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: datetime = Field(..., description="更新时间")
    created_by: int = Field(..., description="创建人")
    updated_by: int = Field(..., description="更新人")


class GetSyncConfigWithRelationDetail(SchemaBase):
    """同步配置详情含关系"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="配置ID")
    enable: bool = Field(..., description="是否启用")
    remark: str | None = Field(None, description="备注")
    type: DriveType = Field(..., description="网盘类型")
    src_path: str = Field(..., description="源路径")
    src_meta: str | None = Field(None, description="源路径元数据")
    dst_path: str = Field(..., description="目标路径")
    dst_meta: str | None = Field(None, description="目标路径元数据")
    user_id: int = Field(..., description="关联账号ID")
    cron: str | None = Field(None, description="定时任务表达式")
    speed: int = Field(..., description="同步速度")
    method: SyncMethod = Field(..., description="同步方法")
    end_time: datetime | None = Field(None, description="结束时间")
    exclude: str | None = Field(None, description="排除规则")
    rename: str | None = Field(None, description="重命名规则")
    last_sync: datetime | None = Field(None, description="最后同步时间")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: datetime = Field(..., description="更新时间")
    created_by: int = Field(..., description="创建人")
    updated_by: int = Field(..., description="更新人")
    sync_tasks: list[GetSyncTaskDetail] = Field(default_factory=list, description="同步任务列表")


class GetSyncTaskWithRelationDetail(SchemaBase):
    """同步任务详情含关系"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="任务ID")
    config_id: int = Field(..., description="配置ID")
    status: str = Field(..., description="任务状态")
    err_msg: str | None = Field(None, description="错误信息")
    start_time: datetime | None = Field(None, description="开始时间")
    task_num: str | None = Field(None, description="任务统计信息")
    dura_time: int = Field(..., description="持续时间")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: datetime = Field(..., description="更新时间")
    created_by: int = Field(..., description="创建人")
    updated_by: int = Field(..., description="更新人")
    task_items: list[GetSyncTaskItemDetail] = Field(default_factory=list, description="任务项列表")


class SyncExecutionResult(SchemaBase):
    """同步执行结果"""
    
    task_id: int = Field(..., description="任务ID")
    status: str = Field(..., description="执行状态")
    message: str = Field(..., description="执行消息")
    total_items: int = Field(0, description="总项目数")
    completed_items: int = Field(0, description="已完成项目数")
    failed_items: int = Field(0, description="失败项目数")
    start_time: datetime | None = Field(None, description="开始时间")
    end_time: datetime | None = Field(None, description="结束时间")
    duration: int = Field(0, description="执行时长")
    errors: list[str] = Field(default_factory=list, description="错误列表")


class SyncProgressInfo(SchemaBase):
    """同步进度信息"""
    
    task_id: int = Field(..., description="任务ID")
    config_id: int = Field(..., description="配置ID")
    status: str = Field(..., description="当前状态")
    progress: float = Field(0.0, ge=0.0, le=100.0, description="进度百分比")
    current_file: str | None = Field(None, description="当前处理文件")
    total_files: int = Field(0, description="总文件数")
    processed_files: int = Field(0, description="已处理文件数")
    failed_files: int = Field(0, description="失败文件数")
    speed: str | None = Field(None, description="传输速度")
    eta: str | None = Field(None, description="预计剩余时间")
    last_update: datetime = Field(..., description="最后更新时间")


class GetSyncConfigListParam(SchemaBase):
    """获取同步配置列表参数"""
    
    enable: bool | None = Field(None, description="是否启用")
    type: DriveType | None = Field(None, description="网盘类型")
    remark: str | None = Field(None, description="备注关键词")
    created_by: int | None = Field(None, description="创建人ID")



