"""
文件名: sync_task_item.py
描述: 同步任务项的Pydantic模型
作者: AI助手
创建日期: 2024-05-20
最后修改: 2024-05-20
版本: 1.0.0
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

# ==================== 基础模型 ====================

class CouldDriveFileSyncTaskItemBase(BaseModel):
    """同步任务项基础模型"""
    taskId: int = Field(..., description="关联的同步任务ID")
    type: str = Field(..., description="操作类型（delete/rename/copy）")
    srcPath: str = Field(..., description="源文件路径")
    dstPath: str = Field(..., description="目标文件路径")
    fileName: str = Field(..., description="文件名")

class CouldDriveFileSyncTaskItemCreate(CouldDriveFileSyncTaskItemBase):
    """创建同步任务项模型"""
    fileSize: Optional[int] = Field(0, description="文件大小（单位：字节）")
    status: Optional[str] = Field("pending", description="状态（pending/running/completed/failed）")
    errMsg: Optional[str] = Field(None, description="错误信息")

class CouldDriveFileSyncTaskItemBatchCreate(BaseModel):
    """批量创建同步任务项模型"""
    taskId: int = Field(..., description="关联的同步任务ID")
    items: List[CouldDriveFileSyncTaskItemCreate] = Field(..., description="任务项列表")

class CouldDriveFileSyncTaskItemUpdate(BaseModel):
    """更新同步任务项模型"""
    status: Optional[str] = Field(None, description="状态")
    errMsg: Optional[str] = Field(None, description="错误信息")

# ==================== 响应模型 ====================

class CouldDriveFileSyncTaskItemInDB(CouldDriveFileSyncTaskItemBase):
    """数据库中的同步任务项模型"""
    id: int
    fileSize: int
    status: str
    errMsg: Optional[str]
    createTime: datetime
    
    class Config:
        from_attributes = True

class CouldDriveFileSyncTaskItem(CouldDriveFileSyncTaskItemInDB):
    """API响应的同步任务项模型"""
    # 计算字段
    fileSizeFormatted: str = Field("0 B", description="格式化的文件大小")
    createTimeFormatted: str = Field(..., description="格式化的创建时间")
    
    @staticmethod
    def from_orm(obj):
        """从ORM模型创建Pydantic模型并处理额外字段"""
        item = CouldDriveFileSyncTaskItemInDB.from_orm(obj)
        item_dict = item.dict()
        
        # 格式化文件大小
        size = item.fileSize
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0 or unit == 'TB':
                item_dict["fileSizeFormatted"] = f"{size:.2f} {unit}"
                break
            size /= 1024.0
        
        # 格式化时间字段
        item_dict["createTimeFormatted"] = item.createTime.strftime("%Y-%m-%d %H:%M:%S")
        
        return CouldDriveFileSyncTaskItem(**item_dict)
    
    class Config:
        from_attributes = True

# ==================== 列表响应模型 ====================

class CouldDriveFileSyncTaskItemList(BaseModel):
    """同步任务项列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[CouldDriveFileSyncTaskItem] = Field(..., description="任务项列表")
    
    class Config:
        from_attributes = True

# ==================== 聚合统计模型 ====================

class CouldDriveFileSyncTaskItemStats(BaseModel):
    """同步任务项状态统计模型"""
    pending: int = Field(0, description="待处理数量")
    running: int = Field(0, description="运行中数量")
    completed: int = Field(0, description="已完成数量")
    failed: int = Field(0, description="失败数量")
    total: int = Field(0, description="总数量")
    
    class Config:
        from_attributes = True 