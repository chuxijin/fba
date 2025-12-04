# Task 模块

## 概述

Task 模块基于 Celery 实现异步任务处理，支持定时任务、队列任务等功能。

## 功能特性

- 异步任务处理
- 定时任务调度
- 任务状态跟踪
- 结果存储
- 错误重试机制

## 定时任务

### 系统维护任务

- **清理操作日志**: 每周六凌晨执行，清理过期的操作日志
- **清理登录日志**: 每月15日凌晨执行，清理过期的登录日志
- **清理过期文件同步数据**: 每天凌晨2点执行，清理30天以外的文件同步任务和任务项

### 业务任务

- **文件同步定时任务检查**: 每5分钟执行一次，检查并执行到期的文件同步任务
- **刷新网盘用户信息**: 每天晚上10点执行，刷新所有有效的网盘用户信息
- **检查并刷新过期资源**: 每天晚上11点执行，检查并刷新即将过期的资源
- **清理本地失效分享**: 每天凌晨5点执行，清理本地已失效的分享链接
- **刷新更新模式资源**: 每天早上7点执行，刷新设置为"定时更新"模式的资源

## 手动触发清理任务

1. 在 `backend/app/task/tasks` 目录下新建 python 包目录
2. 在新建目录下，务必添加 `tasks.py` 文件，并在此文件中编写相关任务代码

- `POST /api/v1/task/filesync/cleanup/expired-data` - 手动清理过期文件同步数据

### 使用场景

- 系统维护时手动清理历史数据
- 数据库空间不足时紧急清理
- 测试清理功能时使用

## 配置说明

你可以通过 `CELERY_BROKER` 控制消息代理选择，它支持 redis 和 rabbitmq

### Redis 配置

```env
CELERY_BROKER=redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password
CELERY_BROKER_REDIS_DATABASE=1
```

### RabbitMQ 配置

```env
CELERY_BROKER=rabbitmq
CELERY_RABBITMQ_HOST=localhost
CELERY_RABBITMQ_PORT=5672
CELERY_RABBITMQ_USERNAME=guest
CELERY_RABBITMQ_PASSWORD=guest
```

## 启动方式

### 启动 Worker

```bash
celery -A backend.app.task.celery:celery_app worker --loglevel=info
```

### 启动 Beat 调度器

```bash
celery -A backend.app.task.celery:celery_app beat --loglevel=info
```

### 使用 Docker Compose

```bash
docker-compose up -d
```

## 注意事项

1. **异步任务执行**: 所有异步函数都通过 `asyncio.run` 在同步环境中执行，确保 Celery 兼容性
2. **数据库连接**: 使用 `async_db_session` 管理数据库连接，避免连接泄漏
3. **错误处理**: 所有任务都包含完整的错误处理和日志记录
4. **事务管理**: 数据库操作使用事务确保数据一致性
5. **资源清理**: 定期清理过期数据，避免数据库无限增长
6. **外键约束**: 清理数据时先删除任务项再删除任务，避免外键约束冲突

## 故障排除

### 常见问题

1. **锁扩展失败**: 检查 Redis 连接和网络稳定性
2. **任务执行超时**: 调整任务超时配置和数据库连接池设置
3. **内存泄漏**: 确保异步事件循环正确关闭

### 日志查看

```bash
# 查看 Worker 日志
celery -A backend.app.task.celery:celery_app worker --loglevel=debug

# 查看 Beat 日志
celery -A backend.app.task.celery:celery_app beat --loglevel=debug
```