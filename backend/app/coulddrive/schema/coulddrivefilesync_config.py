"""
文件名: sync_config.py
描述: 同步配置的Pydantic模型
作者: AI助手
创建日期: 2024-05-20
最后修改: 2024-05-20
版本: 1.0.0
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import json

from ..coulddriveuser import CouldDriveUser

# ==================== 基础模型 ====================

class CouldDriveFileSyncConfigBase(BaseModel):
    """同步配置基础模型"""
    type: str = Field(..., description="同步类型（如：local2cloud, cloud2cloud等）")
    srcPath: str = Field(..., description="源路径")
    dstPath: str = Field(..., description="目标路径")
    accountId: int = Field(..., description="关联的网盘账号ID")

class CouldDriveFileSyncConfigCreate(CouldDriveFileSyncConfigBase):
    """创建同步配置模型"""
    enable: Optional[int] = Field(1, description="是否启用（0否1是）")
    remark: Optional[str] = Field(None, description="备注说明")
    srcMeta: Optional[str] = Field(None, description="源路径元数据")
    dstMeta: Optional[str] = Field(None, description="目标路径元数据")
    corn: Optional[str] = Field(None, description="定时任务表达式")
    speed: Optional[int] = Field(0, description="同步速度限制（单位：KB/s，0表示不限速）")
    method: Optional[str] = Field("copy", description="同步方法（copy/move）")
    endTime: Optional[datetime] = Field(None, description="同步结束时间")
    exclude: Optional[str] = Field(None, description="排除规则（JSON格式）")
    rename: Optional[str] = Field(None, description="重命名规则（JSON格式）")
    
    @validator('exclude', 'rename', pre=True)
    def validate_json(cls, v):
        """验证JSON格式字段"""
        if v is None:
            return v
        if isinstance(v, str):
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                raise ValueError("必须是有效的JSON字符串")
        elif isinstance(v, (dict, list)):
            return json.dumps(v)
        return v

class CouldDriveFileSyncConfigUpdate(CouldDriveFileSyncConfigBase):
    """更新同步配置模型"""
    enable: Optional[int] = Field(None, description="是否启用（0否1是）")
    remark: Optional[str] = Field(None, description="备注说明")
    type: Optional[str] = Field(None, description="同步类型")
    srcPath: Optional[str] = Field(None, description="源路径")
    srcMeta: Optional[str] = Field(None, description="源路径元数据")
    dstPath: Optional[str] = Field(None, description="目标路径")
    dstMeta: Optional[str] = Field(None, description="目标路径元数据")
    accountId: Optional[int] = Field(None, description="关联的网盘账号ID")
    corn: Optional[str] = Field(None, description="定时任务表达式")
    speed: Optional[int] = Field(None, description="同步速度限制")
    method: Optional[str] = Field(None, description="同步方法")
    endTime: Optional[datetime] = Field(None, description="同步结束时间")
    exclude: Optional[str] = Field(None, description="排除规则")
    rename: Optional[str] = Field(None, description="重命名规则")
    
    @validator('exclude', 'rename', pre=True)
    def validate_json(cls, v):
        """验证JSON格式字段"""
        if v is None:
            return v
        if isinstance(v, str):
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                raise ValueError("必须是有效的JSON字符串")
        elif isinstance(v, (dict, list)):
            return json.dumps(v)
        return v

# ==================== 响应模型 ====================

class CouldDriveFileSyncConfigInDB(CouldDriveFileSyncConfigBase):
    """数据库中的同步配置模型"""
    id: int
    enable: int
    remark: Optional[str]
    srcMeta: Optional[str]
    dstMeta: Optional[str]
    corn: Optional[str]
    speed: int
    method: str
    endTime: Optional[datetime]
    exclude: Optional[str]
    rename: Optional[str]
    lastSync: Optional[datetime]
    createTime: datetime
    updateTime: datetime
    
    class Config:
        from_attributes = True

class CouldDriveFileSyncConfig(CouldDriveFileSyncConfigInDB):
    """API响应的同步配置模型"""
    # 解析后的JSON字段
    excludeRules: Optional[List[Dict[str, Any]]] = Field(None, description="解析后的排除规则")
    renameRules: Optional[List[Dict[str, Any]]] = Field(None, description="解析后的重命名规则")
    
    # 计算字段
    lastSyncFormatted: Optional[str] = Field(None, description="格式化的最后同步时间")
    createTimeFormatted: str = Field(..., description="格式化的创建时间")
    
    @staticmethod
    def from_orm(obj):
        """从ORM模型创建Pydantic模型并处理额外字段"""
        config = SyncConfigInDB.from_orm(obj)
        config_dict = config.dict()
        
        # 解析JSON字段
        if config.exclude:
            try:
                config_dict["excludeRules"] = json.loads(config.exclude)
            except json.JSONDecodeError:
                config_dict["excludeRules"] = None
                
        if config.rename:
            try:
                config_dict["renameRules"] = json.loads(config.rename)
            except json.JSONDecodeError:
                config_dict["renameRules"] = None
        
        # 格式化时间字段
        if config.lastSync:
            config_dict["lastSyncFormatted"] = config.lastSync.strftime("%Y-%m-%d %H:%M:%S")
            
        config_dict["createTimeFormatted"] = config.createTime.strftime("%Y-%m-%d %H:%M:%S")
        
        return SyncConfig(**config_dict)
    
    class Config:
        from_attributes = True

# ==================== 列表响应模型 ====================

class CouldDriveFileSyncConfigList(BaseModel):
    """同步配置列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[CouldDriveFileSyncConfig] = Field(..., description="配置列表")
    
    class Config:
        from_attributes = True

# ==================== 扩展响应模型 ====================

class CouldDriveFileSyncConfigWithAccount(CouldDriveFileSyncConfig):
    """带账号信息的同步配置模型"""
    account: Optional[DriveAccount] = Field(None, description="关联的网盘账号")
    
    class Config:
        from_attributes = True 