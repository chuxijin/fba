"""
文件名: sync_task.py
描述: 同步任务的Pydantic模型
作者: AI助手
创建日期: 2024-05-20
最后修改: 2024-07-25
版本: 1.1.0
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from .coulddrivefilesync_config import SyncConfig

# ==================== 基础模型 ====================

class CouldDriveFileSyncTaskBase(BaseModel):
    """同步任务基础模型"""
    configId: int = Field(..., description="关联的同步配置ID")

class CouldDriveFileSyncTaskCreate(CouldDriveFileSyncTaskBase):
    """创建同步任务模型"""
    status: Optional[str] = Field("pending", description="任务状态（pending/running/completed/failed）")

# ==================== 响应模型 ====================

class CouldDriveFileSyncTaskInDB(CouldDriveFileSyncTaskBase):
    """数据库中的同步任务模型"""
    id: int
    status: str
    errMsg: Optional[str]
    startTime: Optional[datetime]
    taskNum: int = Field(0, description="总任务数量")
    
    # 任务项状态计数
    waitNum: int = Field(0, description="等待中的任务项数量")
    runningNum: int = Field(0, description="运行中的任务项数量")
    successNum: int = Field(0, description="成功的任务项数量")
    failNum: int = Field(0, description="失败的任务项数量")
    otherNum: int = Field(0, description="其他状态的任务项数量")
    
    duraTime: int
    createTime: datetime
    
    class Config:
        from_attributes = True

class CouldDriveFileSyncTask(CouldDriveFileSyncTaskInDB):
    """API响应的同步任务模型"""
    # 计算字段
    startTimeFormatted: Optional[str] = Field(None, description="格式化的开始时间")
    createTimeFormatted: str = Field(..., description="格式化的创建时间")
    duraTimeFormatted: str = Field("00:00:00", description="格式化的持续时间")
    
    # 任务项状态统计
    itemStats: Dict[str, int] = Field(
        None, 
        description="任务项状态统计"
    )
    
    @staticmethod
    def from_orm(obj):
        """从ORM模型创建Pydantic模型并处理额外字段"""
        task = CouldDriveFileSyncTaskInDB.from_orm(obj)
        task_dict = task.dict()
        
        # 格式化时间字段
        if task.startTime:
            task_dict["startTimeFormatted"] = task.startTime.strftime("%Y-%m-%d %H:%M:%S")
            
        task_dict["createTimeFormatted"] = task.createTime.strftime("%Y-%m-%d %H:%M:%S")
        
        # 格式化持续时间
        if task.duraTime > 0:
            duration = timedelta(seconds=task.duraTime)
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            task_dict["duraTimeFormatted"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # 构建任务项状态统计
        task_dict["itemStats"] = {
            "waitNum": task.waitNum,
            "runningNum": task.runningNum,
            "successNum": task.successNum,
            "failNum": task.failNum,
            "otherNum": task.otherNum,
            "allNum": task.taskNum
        }
        
        return CouldDriveFileSyncTask(**task_dict)
    
    class Config:
        from_attributes = True

# ==================== 列表响应模型 ====================

class CouldDriveFileSyncTaskList(BaseModel):
    """同步任务列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[CouldDriveFileSyncTask] = Field(..., description="任务列表")
    
    class Config:
        from_attributes = True

# ==================== 扩展响应模型 ====================

class CouldDriveFileSyncTaskWithConfig(CouldDriveFileSyncTask):
    """带配置信息的同步任务模型"""
    config: Optional[CouldDriveFileSyncConfig] = Field(None, description="关联的同步配置")
    
    class Config:
        from_attributes = True

class CouldDriveFileSyncTaskWithItems(CouldDriveFileSyncTask):
    """带任务项信息的同步任务模型"""
    
    class Config:
        from_attributes = True

class CouldDriveFileSyncTaskWithConfigAndItems(CouldDriveFileSyncTaskWithConfig, CouldDriveFileSyncTaskWithItems):
    """带配置和任务项信息的同步任务模型"""
    
    class Config:
        from_attributes = True 