# 统一认证体系架构指南

## 📋 架构概览

新的统一认证体系采用**策略模式**，支持无限扩展用户类型，核心特性：

- ✅ **统一 Token 结构**：所有用户类型使用相同的 JWT payload 格式
- ✅ **统一 Redis 存储**：所有 token 都存储在 Redis，支持多端登录控制
- ✅ **可插拔用户加载器**：新增用户类型只需实现一个 Loader 类
- ✅ **单一认证入口**：中间件统一处理，路由依赖自动注入
- ✅ **向后兼容**：可与现有代码共存，逐步迁移

## 🏗️ 核心组件

### 1. 用户加载器策略（auth_strategy.py）

```python
from backend.common.security.auth_strategy import (
    UserLoader,          # 抽象基类
    AuthUser,            # 统一用户对象
    register_user_loader,# 注册加载器
    load_user_by_type,   # 加载用户
)
```

### 2. 统一 Token 工具（unified_token.py）

```python
from backend.common.security.unified_token import (
    create_unified_token,  # 创建 token
    verify_unified_token,  # 验证 token
    refresh_unified_token, # 刷新 token
    revoke_unified_token,  # 撤销 token
)
```

### 3. 统一认证中间件（unified_auth_middleware.py）

```python
from backend.middleware.unified_auth_middleware import (
    UnifiedAuthMiddleware,  # 中间件
)
```

## 🚀 快速开始

### 示例 1：知识店铺用户登录

```python
# backend/app/question_bank/service/auth_service.py

from backend.common.security.unified_token import create_unified_token

class AuthService:
    @staticmethod
    async def test_login(*, db: AsyncSession, username: str = 'test_user') -> dict:
        # 1. 验证用户
        user = await user_account_dao.select_model_by_column(db, username=username)
        if not user:
            # 创建用户...
            pass

        # 2. 创建统一 token
        token_result = await create_unified_token(
            user_id=user.id,
            user_type='customer',  # 用户类型标识
            multi_login=True,
            # 可选的额外信息
            nickname=user.nickname,
            is_vip=user.is_vip,
        )

        return {
            'access_token': token_result.access_token,
            'expire_time': token_result.access_token_expire_time,
            'user_type': token_result.user_type,
        }
```

### 示例 2：路由依赖注入

```python
# backend/app/question_bank/api/v1/auth.py

from fastapi import Depends, Request
from backend.common.security.auth_strategy import AuthUser

async def get_current_customer(request: Request) -> AuthUser:
    """获取当前客户用户"""
    if not hasattr(request.state, 'auth_user'):
        raise errors.AuthorizationError(msg='未登录')

    user: AuthUser = request.state.auth_user
    if user.user_type != 'customer':
        raise errors.AuthorizationError(msg='权限不足')

    return user

# 使用依赖
@router.get('/me')
async def get_current_user(user: AuthUser = Depends(get_current_customer)):
    return {
        'user_id': user.user_id,
        'username': user.username,
        'is_vip': user.extra.get('is_vip'),
    }
```

## 📦 新增用户类型（软件用户示例）

### 步骤 1：创建用户加载器

```python
# backend/app/software/user_loader.py

from backend.common.security.auth_strategy import UserLoader, AuthUser
from sqlalchemy.ext.asyncio import AsyncSession

class SoftwareUserLoader(UserLoader):
    """软件用户加载器"""

    def get_user_type(self) -> str:
        return 'software'

    def get_redis_prefix(self) -> str:
        return 'fba:token:software'

    async def load_user(self, db: AsyncSession, user_id: int) -> AuthUser | None:
        # 1. 从数据库加载软件用户
        from backend.app.software.crud.crud_user import software_user_dao
        from backend.common.exception import errors

        user = await software_user_dao.get(db, user_id)
        if not user:
            return None

        # 2. 检查用户状态
        if user.status != 1:
            raise errors.AuthorizationError(msg='账户已被禁用')

        # 3. 检查许可证有效期
        if user.license_expired:
            raise errors.AuthorizationError(msg='软件许可证已过期')

        # 4. 返回统一的 AuthUser
        return AuthUser(
            user_id=user.id,
            user_type='software',
            username=user.username,
            extra={
                'company_name': user.company_name,
                'license_type': user.license_type,
                'expire_date': user.license_expire_date.isoformat(),
                'features': user.enabled_features,  # ['feature_a', 'feature_b']
            }
        )
```

### 步骤 2：注册加载器

```python
# backend/app/software/__init__.py

from backend.common.security.auth_strategy import register_user_loader
from backend.app.software.user_loader import SoftwareUserLoader

# 在应用启动时注册
register_user_loader('software', SoftwareUserLoader())
```

### 步骤 3：创建登录接口

```python
# backend/app/software/api/v1/auth.py

from fastapi import APIRouter
from backend.common.security.unified_token import create_unified_token

router = APIRouter()

@router.post('/login')
async def software_login(db: AsyncSession, license_key: str):
    # 1. 验证许可证密钥
    user = await software_user_dao.get_by_license(db, license_key)
    if not user:
        raise errors.NotFoundError(msg='许可证无效')

    # 2. 创建 token
    token_result = await create_unified_token(
        user_id=user.id,
        user_type='software',
        multi_login=False,  # 软件用户不允许多端登录
        company_name=user.company_name,
    )

    return {
        'access_token': token_result.access_token,
        'expire_time': token_result.access_token_expire_time,
    }
```

### 步骤 4：创建路由依赖

```python
# backend/app/software/security.py

from fastapi import Depends, Request
from backend.common.security.auth_strategy import AuthUser
from backend.common.exception import errors

async def get_current_software_user(request: Request) -> AuthUser:
    """获取当前软件用户"""
    if not hasattr(request.state, 'auth_user'):
        raise errors.AuthorizationError(msg='未登录')

    user: AuthUser = request.state.auth_user
    if user.user_type != 'software':
        raise errors.AuthorizationError(msg='需要软件用户权限')

    return user

async def require_feature(feature_name: str):
    """检查用户是否拥有指定功能"""
    async def _check(user: AuthUser = Depends(get_current_software_user)):
        features = user.extra.get('features', [])
        if feature_name not in features:
            raise errors.AuthorizationError(msg=f'缺少功能权限: {feature_name}')
        return user
    return _check

# 使用示例
@router.get('/advanced-report')
async def get_advanced_report(
    user: AuthUser = Depends(require_feature('advanced_reports'))
):
    return {'report': 'data'}
```

## 🔄 迁移现有代码

### Option 1：渐进式迁移（推荐）

1. **保留旧代码**，新功能使用新架构
2. **逐步迁移**登录接口使用 `create_unified_token`
3. **最后替换**中间件

### Option 2：一次性迁移

1. **替换中间件**：
```python
# main.py
from backend.middleware.unified_auth_middleware import UnifiedAuthMiddleware

# 替换
# app.add_middleware(AuthenticationMiddleware, backend=JwtAuthMiddleware())
app.add_middleware(AuthenticationMiddleware, backend=UnifiedAuthMiddleware())
```

2. **修改登录接口**：使用 `create_unified_token`

3. **修改路由依赖**：使用 `request.state.auth_user`

## 🎯 最佳实践

### 1. Token Payload 设计

```python
# 统一 Payload（所有用户类型）
{
    "user_id": 123,
    "user_type": "customer",  # admin, customer, software, etc.
    "session_uuid": "uuid-string",
    "exp": 1234567890,
    "iat": 1234567890,
}
```

### 2. 用户类型命名规范

- 使用小写字母和下划线
- 语义清晰：`admin`, `customer`, `software`, `api_client`
- 避免：`type1`, `user_a`

### 3. Extra 字段使用

```python
# ✅ 推荐：只存储必要信息
AuthUser(
    user_id=1,
    user_type='customer',
    extra={
        'is_vip': True,
        'vip_level': 3,
    }
)

# ❌ 避免：存储大量数据
AuthUser(
    extra={
        'full_user_object': {...},  # 太大
        'all_orders': [...]  # 不必要
    }
)
```

### 4. Redis Key 设计

```python
# 格式：{prefix}:{user_id}:{session_uuid}
fba:token:{user_id}:{session_uuid}              # Admin
fba:token:customer:{user_id}:{session_uuid}     # Customer
fba:token:software:{user_id}:{session_uuid}     # Software
```

### 5. 权限检查层次

```python
# 层次 1：中间件（Token 有效性）
UnifiedAuthMiddleware  # 验证 token 是否有效

# 层次 2：路由依赖（用户类型）
Depends(get_current_customer)  # 验证是否是 customer 用户

# 层次 3：业务逻辑（具体权限）
async def check_vip_permission(user: AuthUser):
    if not user.extra.get('is_vip'):
        raise errors.AuthorizationError(msg='需要 VIP 权限')
```

## 🔧 常见问题

### Q1：如何支持多种认证方式（密码、OAuth、API Key）？

A：在 UserLoader 中实现不同的认证逻辑，但都返回 AuthUser：

```python
class CustomerUserLoader(UserLoader):
    async def load_user(self, db: AsyncSession, user_id: int) -> AuthUser | None:
        # 这里只负责加载用户，不管怎么登录的
        user = await user_account_dao.get(db, user_id)
        return AuthUser(...)

# 认证逻辑在 Service 层
class AuthService:
    async def password_login(self, username, password):
        # 密码登录
        user = await self.verify_password(username, password)
        return await create_unified_token(user.id, 'customer')

    async def oauth_login(self, oauth_code):
        # OAuth 登录
        user = await self.verify_oauth(oauth_code)
        return await create_unified_token(user.id, 'customer')

    async def api_key_login(self, api_key):
        # API Key 登录
        user = await self.verify_api_key(api_key)
        return await create_unified_token(user.id, 'api_client')
```

### Q2：如何实现不同用户类型的 token 过期时间？

A：在 UserLoader 中定义：

```python
class SoftwareUserLoader(UserLoader):
    def get_token_expire_seconds(self) -> int:
        """软件用户 token 7 天过期"""
        return 60 * 60 * 24 * 7

# 在 unified_token.py 中使用
expire_seconds = loader.get_token_expire_seconds() or settings.TOKEN_EXPIRE_SECONDS
```

### Q3：如何处理用户信息变更（如禁用用户）？

A：每次请求都会通过 `load_user` 重新加载用户，会自动检查状态：

```python
async def load_user(self, db: AsyncSession, user_id: int) -> AuthUser | None:
    user = await user_dao.get(db, user_id)
    if user.status != 1:  # 每次请求都检查
        raise errors.AuthorizationError(msg='账户已被禁用')
    return AuthUser(...)
```

## 📊 性能优化

### 缓存用户信息

```python
class CustomerUserLoader(UserLoader):
    async def load_user(self, db: AsyncSession, user_id: int) -> AuthUser | None:
        # 1. 先从 Redis 缓存读取
        cache_key = f'user_cache:customer:{user_id}'
        cached = await redis_client.get(cache_key)
        if cached:
            return AuthUser.model_validate_json(cached)

        # 2. 从数据库加载
        user = await user_account_dao.get(db, user_id)
        if not user:
            return None

        auth_user = AuthUser(...)

        # 3. 写入缓存（5分钟）
        await redis_client.setex(cache_key, 300, auth_user.model_dump_json())

        return auth_user
```

## 🎉 总结

使用统一认证体系的优势：

1. **扩展性**：新增用户类型只需 3 个文件（Loader、Service、API）
2. **一致性**：所有用户类型使用相同的认证流程
3. **可维护性**：中间件代码不需要修改
4. **可测试性**：每个 Loader 可以独立测试
5. **向后兼容**：可与现有代码共存

未来新增用户类型的步骤：
1. 实现 UserLoader（5 分钟）
2. 注册加载器（1 行代码）
3. 创建登录接口（10 分钟）
4. 创建路由依赖（5 分钟）

总计：**约 20 分钟**即可完成一个新用户类型的接入！
