"""
文件名: sync_task_item_crud.py
描述: 同步任务项表的异步CRUD操作
作者: AI助手
创建日期: 2024-05-20
最后修改: 2024-05-22
版本: 1.1.0
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql.expression import or_, and_

from app.coulddrive.model.coulddrivefilesync_task_item import CouldDriveFileSyncTaskItem
from app.coulddrive.schemas.coulddrivefilesync_task_item import CouldDriveFileSyncTaskItem as CouldDriveFileSyncTaskItemSchema

# ==================== 基本查询函数 ====================

async def get_sync_task_item(session: AsyncSession, item_id: int) -> Optional[SyncTaskItemSchema]:
    """
    根据ID获取同步任务项信息
    
    参数:
        session (AsyncSession): 数据库会话
        item_id (int): 任务项ID
    
    返回:
        Optional[SyncTaskItemSchema]: 任务项Pydantic模型，未找到返回None
    """
    result = await session.execute(
        select(SyncTaskItem).where(SyncTaskItem.id == item_id)
    )
    item = result.scalars().first()
    if item:
        return SyncTaskItemSchema.from_orm(item)
    return None

async def get_sync_task_items(
    session: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    task_id: Optional[int] = None,
    status: Optional[str] = None,
    type: Optional[str] = None
) -> List[SyncTaskItemSchema]:
    """
    获取同步任务项列表
    
    参数:
        session (AsyncSession): 数据库会话
        skip (int): 跳过记录数
        limit (int): 返回记录数量限制，如果为0则返回所有记录
        task_id (Optional[int]): 按任务ID筛选
        status (Optional[str]): 按状态筛选
        type (Optional[str]): 按操作类型筛选
    
    返回:
        List[SyncTaskItemSchema]: 任务项Pydantic模型列表
    """
    query = select(SyncTaskItem).order_by(SyncTaskItem.createTime.desc())
    
    if task_id is not None:
        query = query.where(SyncTaskItem.taskId == task_id)
    
    if status:
        query = query.where(SyncTaskItem.status == status)
    
    if type:
        query = query.where(SyncTaskItem.type == type)
    
    # 仅当limit > 0时应用分页限制
    if limit > 0:
        query = query.offset(skip).limit(limit)
    
    result = await session.execute(query)
    items = result.scalars().all()
    
    return [SyncTaskItemSchema.from_orm(item) for item in items]

# ==================== 新增操作函数 ====================

async def create_sync_task_item(
    session: AsyncSession,
    item_data: Dict[str, Any]
) -> SyncTaskItemSchema:
    """
    创建同步任务项
    
    参数:
        session (AsyncSession): 数据库会话
        item_data (Dict[str, Any]): 任务项数据
    
    返回:
        SyncTaskItemSchema: 创建的任务项Pydantic模型
    """
    new_item = SyncTaskItem(**item_data)
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)
    
    return SyncTaskItemSchema.from_orm(new_item)

async def batch_create_sync_task_items(
    session: AsyncSession,
    items_data: List[Dict[str, Any]]
) -> List[SyncTaskItemSchema]:
    """
    批量创建同步任务项
    
    参数:
        session (AsyncSession): 数据库会话
        items_data (List[Dict[str, Any]]): 任务项数据列表
    
    返回:
        List[SyncTaskItemSchema]: 创建的任务项Pydantic模型列表
    """
    new_items = []
    
    for item_data in items_data:
        new_item = SyncTaskItem(**item_data)
        session.add(new_item)
        new_items.append(new_item)
    
    await session.commit()
    
    # 刷新所有新创建的项
    for item in new_items:
        await session.refresh(item)
    
    return [SyncTaskItemSchema.from_orm(item) for item in new_items]

# ==================== 更新操作函数 ====================

async def update_sync_task_item_status(
    session: AsyncSession,
    item_id: int,
    status: str,
    err_msg: Optional[str] = None
) -> Optional[SyncTaskItemSchema]:
    """
    更新同步任务项状态
    
    参数:
        session (AsyncSession): 数据库会话
        item_id (int): 任务项ID
        status (str): 新状态
        err_msg (Optional[str]): 错误消息
    
    返回:
        Optional[SyncTaskItemSchema]: 更新后的任务项Pydantic模型，未找到返回None
    """
    result = await session.execute(
        select(SyncTaskItem).where(SyncTaskItem.id == item_id)
    )
    item = result.scalars().first()
    
    if not item:
        return None
    
    item.status = status
    if err_msg is not None:
        item.errMsg = err_msg
    
    await session.commit()
    await session.refresh(item)
    
    return SyncTaskItemSchema.from_orm(item)

async def update_task_items_status_by_task(
    session: AsyncSession,
    task_id: int,
    status: str
) -> int:
    """
    更新指定任务的所有任务项状态
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
        status (str): 新状态
    
    返回:
        int: 更新的记录数
    """
    result = await session.execute(
        select(SyncTaskItem).where(SyncTaskItem.taskId == task_id)
    )
    items = result.scalars().all()
    
    for item in items:
        item.status = status
    
    await session.commit()
    return len(items)

# ==================== 删除操作函数 ====================

async def delete_sync_task_item(
    session: AsyncSession,
    item_id: int
) -> bool:
    """
    删除同步任务项
    
    参数:
        session (AsyncSession): 数据库会话
        item_id (int): 任务项ID
    
    返回:
        bool: 删除成功返回True，未找到返回False
    """
    result = await session.execute(
        select(SyncTaskItem).where(SyncTaskItem.id == item_id)
    )
    item = result.scalars().first()
    
    if not item:
        return False
    
    await session.delete(item)
    await session.commit()
    
    return True

async def delete_sync_task_items_by_task(
    session: AsyncSession,
    task_id: int
) -> int:
    """
    删除指定任务的所有任务项
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
    
    返回:
        int: 删除的记录数
    """
    result = await session.execute(
        select(SyncTaskItem).where(SyncTaskItem.taskId == task_id)
    )
    items = result.scalars().all()
    
    count = len(items)
    for item in items:
        await session.delete(item)
    
    await session.commit()
    return count

# ==================== 扩展查询函数 ====================

async def count_sync_task_items(
    session: AsyncSession,
    task_id: Optional[int] = None,
    status: Optional[str] = None,
    type: Optional[str] = None
) -> int:
    """
    统计同步任务项数量
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (Optional[int]): 按任务ID筛选
        status (Optional[str]): 按状态筛选
        type (Optional[str]): 按操作类型筛选
    
    返回:
        int: 任务项总数
    """
    query = select(func.count(SyncTaskItem.id))
    
    if task_id is not None:
        query = query.where(SyncTaskItem.taskId == task_id)
    
    if status:
        query = query.where(SyncTaskItem.status == status)
    
    if type:
        query = query.where(SyncTaskItem.type == type)
    
    result = await session.execute(query)
    count = result.scalar()
    return count or 0

async def get_task_items_summary(
    session: AsyncSession,
    task_id: int
) -> Dict[str, Any]:
    """
    获取任务项状态摘要统计
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
    
    返回:
        Dict[str, Any]: 包含各种状态的统计数据
    """
    # 获取总数
    total_query = select(func.count(SyncTaskItem.id)).where(SyncTaskItem.taskId == task_id)
    total_result = await session.execute(total_query)
    total = total_result.scalar() or 0
    
    # 获取各状态数量
    pending_query = select(func.count(SyncTaskItem.id)).where(
        (SyncTaskItem.taskId == task_id) & (SyncTaskItem.status == "pending")
    )
    pending_result = await session.execute(pending_query)
    pending = pending_result.scalar() or 0
    
    running_query = select(func.count(SyncTaskItem.id)).where(
        (SyncTaskItem.taskId == task_id) & (SyncTaskItem.status == "running")
    )
    running_result = await session.execute(running_query)
    running = running_result.scalar() or 0
    
    completed_query = select(func.count(SyncTaskItem.id)).where(
        (SyncTaskItem.taskId == task_id) & (SyncTaskItem.status == "completed")
    )
    completed_result = await session.execute(completed_query)
    completed = completed_result.scalar() or 0
    
    failed_query = select(func.count(SyncTaskItem.id)).where(
        (SyncTaskItem.taskId == task_id) & (SyncTaskItem.status == "failed")
    )
    failed_result = await session.execute(failed_query)
    failed = failed_result.scalar() or 0
    
    # 计算任务总大小
    size_query = select(func.sum(SyncTaskItem.fileSize)).where(SyncTaskItem.taskId == task_id)
    size_result = await session.execute(size_query)
    total_size = size_result.scalar() or 0
    
    return {
        "total": total,
        "pending": pending,
        "running": running,
        "completed": completed,
        "failed": failed,
        "totalSize": total_size
    }

async def get_next_pending_item(
    session: AsyncSession,
    task_id: int
) -> Optional[SyncTaskItemSchema]:
    """
    获取下一个待处理的任务项
    
    参数:
        session (AsyncSession): 数据库会话
        task_id (int): 任务ID
    
    返回:
        Optional[SyncTaskItemSchema]: 任务项Pydantic模型，未找到返回None
    """
    # 优先查找文件夹创建操作
    folder_query = select(SyncTaskItem).where(
        (SyncTaskItem.taskId == task_id) &
        (SyncTaskItem.status == "pending") &
        (SyncTaskItem.type == "create_folder")
    ).order_by(SyncTaskItem.createTime.asc()).limit(1)
    
    folder_result = await session.execute(folder_query)
    folder_item = folder_result.scalars().first()
    
    if folder_item:
        return SyncTaskItemSchema.from_orm(folder_item)
    
    # 查找其他操作
    query = select(SyncTaskItem).where(
        (SyncTaskItem.taskId == task_id) &
        (SyncTaskItem.status == "pending")
    ).order_by(SyncTaskItem.createTime.asc()).limit(1)
    
    result = await session.execute(query)
    item = result.scalars().first()
    
    if item:
        return SyncTaskItemSchema.from_orm(item)
    
    return None 