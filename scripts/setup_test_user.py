#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理重复测试用户并创建标准测试用户

运行方式：python scripts/setup_test_user.py
"""
import asyncio
import sys
from datetime import timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.app.question_bank.model.user import UserAccount, UserMembership
from backend.core.conf import settings
from backend.utils.timezone import timezone


async def setup_test_user():
    """清理重复测试用户并创建标准测试用户"""

    # 创建数据库引擎
    database_url = (
        f'{settings.DATABASE_TYPE}+asyncmy://'
        f'{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@'
        f'{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/'
        f'{settings.DATABASE_SCHEMA}?charset={settings.DATABASE_CHARSET}'
    )

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print('🔍 检查现有测试用户...')

        # 1. 查找所有测试相关的用户
        stmt = select(UserAccount).where(
            (UserAccount.username.like('wx_%')) |
            (UserAccount.open_id.like('test_openid_%')) |
            (UserAccount.username == 'test_user')
        )
        result = await session.execute(stmt)
        test_users = result.scalars().all()

        if test_users:
            print(f'📋 找到 {len(test_users)} 个测试用户：')
            for user in test_users:
                print(f'   - ID: {user.id}, Username: {user.username}, OpenID: {user.open_id}')

            # 2. 删除这些测试用户（级联删除会员记录）
            print('\n🗑️  删除所有测试用户...')
            user_ids = [user.id for user in test_users]

            # 先删除会员记录
            await session.execute(
                delete(UserMembership).where(UserMembership.user_id.in_(user_ids))
            )

            # 再删除用户
            await session.execute(
                delete(UserAccount).where(UserAccount.id.in_(user_ids))
            )

            await session.commit()
            print('✅ 已删除所有测试用户')
        else:
            print('✅ 没有找到旧的测试用户')

        # 3. 创建标准测试用户
        print('\n👤 创建标准测试用户...')
        test_user = UserAccount(
            username='test_user',
            nickname='测试用户',
            open_id='test_openid_test_user',
            session_key='test_session_key',
            avatar=None,
            register_channel='test',
            status=1,
            is_vip=True,  # 直接设置为 VIP
        )

        session.add(test_user)
        await session.flush()  # flush 以获取 user.id

        print(f'✅ 创建测试用户成功')
        print(f'   Username: {test_user.username}')
        print(f'   ID: {test_user.id}')
        print(f'   OpenID: {test_user.open_id}')

        # 4. 创建全分类 VIP 会员权益
        print('\n💎 创建 VIP 会员权益...')
        now = timezone.now()
        end_time = now + timedelta(days=365)  # 1年后到期

        membership = UserMembership(
            user_id=test_user.id,
            category=0,  # 0=全部分类（最高权限）
            res_type='category',  # 整个分类的会员
            method='manual',  # 手动开通
            start_time=now,
            end_time=end_time,
            res_id=None,
            res_name='全部资源',
            status=1  # 有效
        )

        session.add(membership)
        await session.commit()

        print(f'✅ VIP 会员权益创建成功')
        print(f'   会员类型: 全部分类 (最高权限)')
        print(f'   生效时间: {now}')
        print(f'   到期时间: {end_time}')

    await engine.dispose()

    print('\n' + '='*60)
    print('🎉 完成！测试用户设置成功')
    print('='*60)
    print('📝 测试账号信息：')
    print('   用户名: test_user')
    print('   昵称: 测试用户')
    print('   权限: 全部资源访问权限（VIP）')
    print('   有效期: 1年')
    print('\n💡 现在可以：')
    print('   1. 启动后端服务: python main.py')
    print('   2. 启动小程序: npm run dev:mp-weixin')
    print('   3. 小程序会自动使用 test_user 登录')
    print('='*60)


if __name__ == '__main__':
    asyncio.run(setup_test_user())
