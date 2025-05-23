"""
文件名: sync_task_crud.py
描述: 同步任务表的异步CRUD操作
作者: AI助手
创建日期: 2024-05-20
最后修改: 2024-05-22
版本: 1.1.0
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql.expression import or_, and_
from sqlalchemy.orm import joinedload

from app.db.crud.sync.sync_task_item_crud import get_task_items_summary
from app.models.sync.sync_task import SyncTask as SyncTaskModel
from app.models.sync.sync_config import SyncConfig
from app.models.sync.sync_task_item import SyncTaskItem
from app.schemas.sync.sync_task import SyncTask as SyncTaskSchema
from app.schemas.sync.sync_task import SyncTaskWithConfig as SyncTaskWithConfigSchema
from app.schemas.sync.sync_config import SyncConfig as SyncConfigSchema

# ==================== 基本查询函数 ====================

async def get_sync_task(session: AsyncSession, task_id: int) -> Optional[SyncTaskSchema]:
    """
    根据ID获取同步任务信息
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
    
    返回:
        Optional[SyncTaskSchema]: 任务Pydantic模型，未找到返回None
    """
    result = await session.execute(
        select(SyncTaskModel).where(SyncTaskModel.id == task_id)
    )
    task = result.scalars().first()
    if task:
        return SyncTaskSchema.from_orm(task)
    return None

async def get_sync_tasks(
    session: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    config_id: Optional[int] = None,
    status: Optional[str] = None
) -> List[SyncTaskSchema]:
    """
    获取同步任务列表
    
    参数:
        session (AsyncSession): 数据库会话
        skip (int): 跳过记录数
        limit (int): 返回记录数量限制，如果为0则返回所有记录
        config_id (Optional[int]): 按配置ID筛选
        status (Optional[str]): 按任务状态筛选
    
    返回:
        List[SyncTaskSchema]: 任务Pydantic模型列表
    """
    query = select(SyncTaskModel).order_by(SyncTaskModel.createTime.desc())
    
    if config_id is not None:
        query = query.where(SyncTaskModel.configId == config_id)
    
    if status:
        query = query.where(SyncTaskModel.status == status)
    
    # 仅当limit > 0时应用分页限制
    if limit > 0:
        query = query.offset(skip).limit(limit)
    
    result = await session.execute(query)
    tasks = result.scalars().all()
    
    return [SyncTaskSchema.from_orm(task) for task in tasks]

async def get_latest_task_by_config(
    session: AsyncSession,
    config_id: int
) -> Optional[SyncTaskSchema]:
    """
    获取指定配置的最新同步任务
    
    参数:
        session (AsyncSession): 数据库会话
        config_id (int): 配置ID
    
    返回:
        Optional[SyncTaskSchema]: 最新任务Pydantic模型，未找到返回None
    """
    query = select(SyncTaskModel).where(
        SyncTaskModel.configId == config_id
    ).order_by(SyncTaskModel.createTime.desc()).limit(1)
    
    result = await session.execute(query)
    task = result.scalars().first()
    
    if task:
        return SyncTaskSchema.from_orm(task)
    return None

# ==================== 新增操作函数 ====================

async def create_sync_task(
    session: AsyncSession,
    task_data: Dict[str, Any]
) -> SyncTaskSchema:
    """
    创建同步任务
    
    参数:
        session (AsyncSession): 数据库会话
        task_data (Dict[str, Any]): 任务数据
    
    返回:
        SyncTaskSchema: 创建的任务Pydantic模型
    """
    new_task = SyncTaskModel(**task_data)
    session.add(new_task)
    await session.commit()
    await session.refresh(new_task)
    
    return SyncTaskSchema.from_orm(new_task)

# ==================== 更新操作函数 ====================

async def update_sync_task_status(
    session: AsyncSession,
    task_id: int,
    status: str,
    err_msg: Optional[str] = None
) -> Optional[SyncTaskSchema]:
    """
    更新同步任务状态
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
        status (str): 新状态
        err_msg (Optional[str]): 错误消息
    
    返回:
        Optional[SyncTaskSchema]: 更新后的任务Pydantic模型，未找到返回None
    """
    result = await session.execute(
        select(SyncTaskModel).where(SyncTaskModel.id == task_id)
    )
    task = result.scalars().first()
    
    if not task:
        return None
    
    task.status = status
    if err_msg is not None:
        task.errMsg = err_msg
    
    # Populate summary fields for Pydantic model
    # These might not change just by status update, but for consistency if schema expects them
    task_items_summary = await get_task_items_summary(session, task_id)
    if task_items_summary:
        task.waitNum = task_items_summary.get('pending', 0)
        task.runningNum = task_items_summary.get('running', 0)
        task.successNum = task_items_summary.get('completed', 0)
        task.failNum = task_items_summary.get('failed', 0)
        task.taskNum = task_items_summary.get('total', task.taskNum) # task.taskNum should ideally be total
        task.otherNum = task.taskNum - (task.waitNum + task.runningNum + task.successNum + task.failNum)

    await session.commit()
    await session.refresh(task)
    
    return SyncTaskSchema.from_orm(task)

async def start_sync_task(
    session: AsyncSession,
    task_id: int,
    task_num: int
) -> Optional[SyncTaskSchema]:
    """
    开始执行同步任务
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
        task_num (int): 任务项数量
    
    返回:
        Optional[SyncTaskSchema]: 更新后的任务Pydantic模型，未找到返回None
    """
    result = await session.execute(
        select(SyncTaskModel).where(SyncTaskModel.id == task_id)
    )
    task = result.scalars().first()
    
    if not task:
        return None
    
    task.status = "running"
    task.startTime = datetime.now()
    task.taskNum = task_num  # total task items
    
    # Get summary and update task ORM object attributes
    # For a starting task, summary might mostly be 'pending' or 'total'
    task_items_summary = await get_task_items_summary(session, task_id)
    if task_items_summary:
        task.waitNum = task_items_summary.get('pending', task_num) # Initially, all are pending
        task.runningNum = task_items_summary.get('running', 0)
        task.successNum = task_items_summary.get('completed', 0)
        task.failNum = task_items_summary.get('failed', 0)
        # Ensure task.taskNum is consistent with summary['total'] if that's more accurate after items created
        task.taskNum = task_items_summary.get('total', task_num) 
        task.otherNum = task.taskNum - (task.waitNum + task.runningNum + task.successNum + task.failNum)
    else: # If no items yet, initialize counts based on task_num
        task.waitNum = task_num
        task.runningNum = 0
        task.successNum = 0
        task.failNum = 0
        task.otherNum = 0

    await session.commit()
    await session.refresh(task)
    
    return SyncTaskSchema.from_orm(task)

async def complete_sync_task(
    session: AsyncSession,
    task_id: int
) -> Optional[SyncTaskSchema]:
    """
    完成同步任务
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
    
    返回:
        Optional[SyncTaskSchema]: 更新后的任务Pydantic模型，未找到返回None
    """
    result = await session.execute(
        select(SyncTaskModel).where(SyncTaskModel.id == task_id)
    )
    task = result.scalars().first()
    
    if not task:
        return None
    
    # 计算持续时间
    if task.startTime:
        start_timestamp = int(task.startTime.timestamp())
        current_timestamp = int(time.time())
        task.duraTime = current_timestamp - start_timestamp
    
    task.status = "completed"
    
    # Get latest summary and update task ORM attributes
    task_items_summary = await get_task_items_summary(session, task_id)
    if task_items_summary:
        task.waitNum = task_items_summary.get('pending', 0)
        task.runningNum = task_items_summary.get('running', 0)
        task.successNum = task_items_summary.get('completed', 0)
        task.failNum = task_items_summary.get('failed', 0)
        task.taskNum = task_items_summary.get('total', task.taskNum)
        task.otherNum = task.taskNum - (task.waitNum + task.runningNum + task.successNum + task.failNum)
    
    await session.commit()
    await session.refresh(task)
    
    return SyncTaskSchema.from_orm(task)

async def fail_sync_task(
    session: AsyncSession,
    task_id: int,
    err_msg: str
) -> Optional[SyncTaskSchema]:
    """
    标记同步任务为失败
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
        err_msg (str): 错误信息
    
    返回:
        Optional[SyncTaskSchema]: 更新后的任务Pydantic模型，未找到返回None
    """
    result = await session.execute(
        select(SyncTaskModel).where(SyncTaskModel.id == task_id)
    )
    task = result.scalars().first()
    
    if not task:
        return None
    
    # 计算持续时间
    if task.startTime:
        start_timestamp = int(task.startTime.timestamp())
        current_timestamp = int(time.time())
        task.duraTime = current_timestamp - start_timestamp
    
    task.status = "failed"
    task.errMsg = err_msg
    
    # Get latest summary and update task ORM attributes
    task_items_summary = await get_task_items_summary(session, task_id)
    if task_items_summary:
        task.waitNum = task_items_summary.get('pending', 0)
        task.runningNum = task_items_summary.get('running', 0)
        task.successNum = task_items_summary.get('completed', 0)
        task.failNum = task_items_summary.get('failed', 0) # This might increase if items also failed
        task.taskNum = task_items_summary.get('total', task.taskNum)
        task.otherNum = task.taskNum - (task.waitNum + task.runningNum + task.successNum + task.failNum)

    await session.commit()
    await session.refresh(task)
    
    return SyncTaskSchema.from_orm(task)

# ==================== 删除操作函数 ====================

async def delete_sync_task(
    session: AsyncSession,
    task_id: int
) -> bool:
    """
    删除同步任务
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
    
    返回:
        bool: 删除成功返回True，未找到返回False
    """
    result = await session.execute(
        select(SyncTaskModel).where(SyncTaskModel.id == task_id)
    )
    task = result.scalars().first()
    
    if not task:
        return False
    
    await session.delete(task)
    await session.commit()
    
    return True

async def delete_sync_tasks_by_config(
    session: AsyncSession,
    config_id: int
) -> int:
    """
    删除指定配置的所有同步任务
    
    参数:
        session (AsyncSession): 数据库会话
        config_id (int): 配置ID
    
    返回:
        int: 删除的任务数量
    """
    result = await session.execute(
        select(SyncTaskModel).where(SyncTaskModel.configId == config_id)
    )
    tasks = result.scalars().all()
    
    count = len(tasks)
    for task in tasks:
        await session.delete(task)
    
    await session.commit()
    return count

# ==================== 扩展查询函数 ====================

async def count_sync_tasks(
    session: AsyncSession,
    config_id: Optional[int] = None,
    status: Optional[str] = None
) -> int:
    """
    统计同步任务数量
    
    参数:
        session (AsyncSession): 数据库会话
        config_id (Optional[int]): 按配置ID筛选
        status (Optional[str]): 按任务状态筛选
    
    返回:
        int: 任务总数
    """
    query = select(func.count(SyncTaskModel.id))
    
    if config_id is not None:
        query = query.where(SyncTaskModel.configId == config_id)
    
    if status:
        query = query.where(SyncTaskModel.status == status)
    
    result = await session.execute(query)
    count = result.scalar()
    return count or 0

async def get_running_tasks(session: AsyncSession) -> List[SyncTaskSchema]:
    """
    获取正在运行的同步任务列表
    
    参数:
        session (AsyncSession): 数据库会话
    
    返回:
        List[SyncTaskSchema]: 运行中的任务Pydantic模型列表
    """
    query = select(SyncTaskModel).where(SyncTaskModel.status == "running")
    result = await session.execute(query)
    tasks = result.scalars().all()
    
    return [SyncTaskSchema.from_orm(task) for task in tasks]

async def get_task_with_config(
    session: AsyncSession,
    task_id: int
) -> Optional[SyncTaskWithConfigSchema]:
    """
    获取同步任务及其关联的配置信息
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
    
    返回:
        Optional[SyncTaskWithConfigSchema]: 带配置信息的任务Pydantic模型，未找到返回None
    """
    query = select(SyncTaskModel).options(
        joinedload(SyncTaskModel.sync_config)
    ).where(SyncTaskModel.id == task_id)
    
    result = await session.execute(query)
    task = result.scalars().first()
    
    if not task:
        return None
    
    # Pydantic model SyncTaskWithConfig should handle the relationship
    return SyncTaskWithConfigSchema.from_orm(task) 