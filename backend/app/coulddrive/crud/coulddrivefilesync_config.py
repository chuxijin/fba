"""
文件名: sync_config_crud.py
描述: 同步配置表的异步CRUD操作
作者: AI助手
创建日期: 2024-05-20
最后修改: 2024-05-22
版本: 1.1.0
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql.expression import or_, and_

from backend.app.coulddrive.model.coulddrivefilesync_config import CouldDriveFileSyncConfig as CouldDriveFileSyncConfigModel
from backend.app.coulddrive.schema.coulddrivefilesync_config import CouldDriveFileSyncConfig as CouldDriveFileSyncConfigSchema
from backend.app.coulddrive.model.coulddrive_user import CouldDriveUser as CouldDriveUserModel

# ==================== 基本查询函数 ====================

async def get_sync_config(session: AsyncSession, config_id: int) -> Optional[CouldDriveFileSyncConfigSchema]:
    """
    根据ID获取同步配置信息
    
    参数:
        session (AsyncSession): 数据库会话
        config_id (int): 配置ID
    
    返回:
        Optional[SyncConfigSchema]: SyncConfig Pydantic模型实例，未找到返回None
    """
    result = await session.execute(
        select(CouldDriveFileSyncConfigModel).where(CouldDriveFileSyncConfigModel.id == config_id)
    )
    config = result.scalars().first()
    if config:
        return CouldDriveFileSyncConfigSchema.from_orm(config)
    return None

async def get_sync_configs(
    session: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    account_id: Optional[int] = None,
    enabled: Optional[bool] = None
) -> List[CouldDriveFileSyncConfigSchema]:
    """
    获取同步配置列表
    
    参数:
        session (AsyncSession): 数据库会话
        skip (int): 跳过记录数
        limit (int): 返回记录数量限制，如果为0则返回所有记录
        account_id (Optional[int]): 按账户ID筛选
        enabled (Optional[bool]): 按启用状态筛选
    
    返回:
        List[SyncConfigSchema]: SyncConfig Pydantic模型实例列表
    """
    query = select(CouldDriveFileSyncConfigModel).order_by(CouldDriveFileSyncConfigModel.createTime.desc())
    
    if account_id is not None:
        query = query.where(CouldDriveFileSyncConfigModel.accountId == account_id)
    
    if enabled is not None:
        query = query.where(CouldDriveFileSyncConfigModel.enable == (1 if enabled else 0))
    
    if limit > 0:
        query = query.offset(skip).limit(limit)
    
    result = await session.execute(query)
    configs = result.scalars().all()
    
    return [CouldDriveFileSyncConfigSchema.from_orm(config) for config in configs]

# ==================== 新增操作函数 ====================

async def create_sync_config(
    session: AsyncSession,
    config_data: Dict[str, Any]
) -> CouldDriveFileSyncConfigSchema:
    """
    创建同步配置
    
    参数:
        session (AsyncSession): 数据库会话
        config_data (Dict[str, Any]): 配置数据
    
    返回:
        CouldDriveFileSyncConfigSchema: 创建的CouldDriveFileSyncConfig Pydantic模型实例
    """
    # Ensure JSON fields are strings if they are dict/list
    if "exclude" in config_data and isinstance(config_data["exclude"], (dict, list)):
        config_data["exclude"] = json.dumps(config_data["exclude"])
    if "rename" in config_data and isinstance(config_data["rename"], (dict, list)):
        config_data["rename"] = json.dumps(config_data["rename"])
    
    new_config = CouldDriveFileSyncConfigModel(**config_data)
    session.add(new_config)
    await session.commit()
    await session.refresh(new_config)
    
    return CouldDriveFileSyncConfigSchema.from_orm(new_config)

# ==================== 更新操作函数 ====================

async def update_sync_config(
    session: AsyncSession,
    config_id: int,
    config_data: Dict[str, Any]
) -> Optional[CouldDriveFileSyncConfigSchema]:
    """
    更新同步配置信息
    
    参数:
        session (AsyncSession): 数据库会话
        config_id (int): 配置ID
        config_data (Dict[str, Any]): 配置数据
    
    返回:
        Optional[CouldDriveFileSyncConfigSchema]: 更新后的CouldDriveFileSyncConfig Pydantic模型实例，未找到返回None
    """
    result = await session.execute(
        select(CouldDriveFileSyncConfigModel).where(CouldDriveFileSyncConfigModel.id == config_id)
    )
    config = result.scalars().first()
    
    if not config:
        return None
    
    # Ensure JSON fields are strings if they are dict/list
    if "exclude" in config_data and isinstance(config_data["exclude"], (dict, list)):
        config_data["exclude"] = json.dumps(config_data["exclude"])
    if "rename" in config_data and isinstance(config_data["rename"], (dict, list)):
        config_data["rename"] = json.dumps(config_data["rename"])
        
    for key, value in config_data.items():
        if hasattr(config, key) and value is not None:
            setattr(config, key, value)
    
    await session.commit()
    await session.refresh(config)
    
    return CouldDriveFileSyncConfigSchema.from_orm(config)

async def update_sync_config_last_sync(
    session: AsyncSession,
    config_id: int,
    last_sync: datetime
) -> Optional[CouldDriveFileSyncConfigSchema]:
    """
    更新同步配置的最后同步时间
    
    参数:
        session (AsyncSession): 数据库会话
        config_id (int): 配置ID
        last_sync (datetime): 最后同步时间
    
    返回:
        Optional[SyncConfigSchema]: 更新后的SyncConfig Pydantic模型实例，未找到返回None
    """
    result = await session.execute(
        select(CouldDriveFileSyncConfigModel).where(CouldDriveFileSyncConfigModel.id == config_id)
    )
    config = result.scalars().first()
    
    if not config:
        return None
    
    config.lastSync = last_sync
    await session.commit()
    await session.refresh(config)
    
    return CouldDriveFileSyncConfigSchema.from_orm(config)

# ==================== 删除操作函数 ====================

async def delete_sync_config(
    session: AsyncSession,
    config_id: int
) -> bool:
    """
    删除同步配置
    
    参数:
        session (AsyncSession): 数据库会话
        config_id (int): 配置ID
    
    返回:
        bool: 删除成功返回True，未找到返回False
    """
    result = await session.execute(
        select(CouldDriveFileSyncConfigModel).where(CouldDriveFileSyncConfigModel.id == config_id)
    )
    config = result.scalars().first()
    
    if not config:
        return False
    
    await session.delete(config)
    await session.commit()
    
    return True

async def delete_sync_configs_by_account(
    session: AsyncSession,
    account_id: int
) -> int:
    """
    删除指定账户的所有同步配置
    
    参数:
        session (AsyncSession): 数据库会话
        account_id (int): 账户ID
    
    返回:
        int: 删除的配置数量
    """
    result = await session.execute(
        select(CouldDriveFileSyncConfigModel).where(CouldDriveFileSyncConfigModel.accountId == account_id)
    )
    configs = result.scalars().all()
    
    count = len(configs)
    if count > 0:
        for config_model in configs: # Renamed to avoid confusion with config module
            await session.delete(config_model)
        await session.commit()
    return count

# ==================== 扩展查询函数 ====================

async def count_sync_configs(
    session: AsyncSession,
    account_id: Optional[int] = None,
    enabled: Optional[bool] = None
) -> int:
    """
    统计同步配置数量
    
    参数:
        session (AsyncSession): 数据库会话
        account_id (Optional[int]): 按账户ID筛选
        enabled (Optional[bool]): 按启用状态筛选
    
    返回:
        int: 配置总数
    """
    query = select(func.count(CouldDriveFileSyncConfigModel.id))
    
    if account_id is not None:
        query = query.where(CouldDriveFileSyncConfigModel.accountId == account_id)
    
    if enabled is not None:
        query = query.where(CouldDriveFileSyncConfigModel.enable == (1 if enabled else 0))
    
    result = await session.execute(query)
    count = result.scalar_one_or_none()
    return count or 0

async def get_enabled_configs_due_for_sync(session: AsyncSession) -> List[CouldDriveFileSyncConfigSchema]:
    """
    获取需要执行同步的配置列表（已启用且未设置最后同步时间，或已到达下次同步时间）
    
    参数:
        session (AsyncSession): 数据库会话
    
    返回:
        List[CouldDriveFileSyncConfigSchema]: CouldDriveFileSyncConfig Pydantic模型实例列表
    """
    now = datetime.now()
    
    valid_accounts_subquery = select(CouldDriveUserModel.id).where(CouldDriveUserModel.isValid == 1).scalar_subquery()
    
    from sqlalchemy.sql.expression import or_, and_

    query = select(CouldDriveFileSyncConfigModel).where(
        and_(
            CouldDriveFileSyncConfigModel.enable == 1,
            CouldDriveFileSyncConfigModel.accountId.in_(valid_accounts_subquery),
            or_(
                CouldDriveFileSyncConfigModel.lastSync == None,
                # For cron-based conditions, more robust parsing of cron and comparison 
                # against `now` would be needed. The current SQL-based interval logic is a simplification.
                # For example, a real cron parser library should be used to determine next run time.
                # The following is a direct translation of previous logic, but has limitations.
                and_(
                    CouldDriveFileSyncConfigModel.corn == "0 */1 * * *", 
                    CouldDriveFileSyncConfigModel.lastSync < (now - timedelta(hours=1)) # Using timedelta for comparison
                ),
                and_(
                    CouldDriveFileSyncConfigModel.corn == "0 0 */1 * *", 
                    CouldDriveFileSyncConfigModel.lastSync < (now - timedelta(days=1)) # Using timedelta for comparison
                )
            )
        )
    )
    
    result = await session.execute(query)
    configs = result.scalars().all()
    
    return [CouldDriveFileSyncConfigSchema.from_orm(config) for config in configs] 