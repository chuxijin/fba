# 文件同步任务系统使用指南

## 🎯 概述

本系统基于 Celery 实现了完整的文件同步任务调度功能，支持根据 cron 表达式自动执行同步任务。

## 🚀 快速开始

### 1. 启动 Redis 服务

```bash
# Windows (使用 Docker)
docker run -d -p 6379:6379 redis:latest

# 或者使用本地 Redis 服务
redis-server
```

### 2. 启动 Celery Worker

```bash
# 在 backend 目录下执行
cd backend
celery -A app.task.celery worker --loglevel=info
```

### 3. 启动 Celery Beat (定时任务调度器)

```bash
# 在另一个终端中执行
cd backend
celery -A app.task.celery beat --loglevel=info
```

### 4. 启动 FastAPI 应用

```bash
# 在第三个终端中执行
cd backend
python main.py
```

## 📅 Cron 表达式格式

格式：`分 时 日 月 周`

### 常用示例

| 表达式 | 说明 |
|--------|------|
| `0 2 * * *` | 每天凌晨2点执行 |
| `*/30 * * * *` | 每30分钟执行一次 |
| `0 9,18 * * 1-5` | 工作日上午9点和下午6点执行 |
| `0 0 1 * *` | 每月1号凌晨执行 |
| `0 6 * * 0` | 每周日早上6点执行 |
| `0 */2 * * *` | 每2小时执行一次 |

### 字段说明

- **分钟** (0-59)
- **小时** (0-23)
- **日期** (1-31)
- **月份** (1-12)
- **星期** (0-7，0和7都表示周日)

### 特殊字符

- `*` : 匹配任何值
- `,` : 分隔多个值
- `-` : 表示范围
- `/` : 表示步长

## �� API 使用

### 任务管理

#### 刷新定时任务
```http
POST /api/v1/task/scheduler/refresh-tasks
```

#### 获取任务状态
```http
GET /api/v1/task/scheduler/task-status
```

#### 验证 cron 表达式
```http
POST /api/v1/task/scheduler/validate-cron
Content-Type: application/json

"0 2 * * *"
```

#### 清空所有定时任务
```http
DELETE /api/v1/task/scheduler/clear-tasks
```

### 任务执行

#### 立即执行指定配置的同步任务
```http
POST /api/v1/task/scheduler/execute-sync/1
```

#### 执行所有启用的同步任务
```http
POST /api/v1/task/scheduler/execute-all-enabled
```

#### 获取任务执行结果
```http
GET /api/v1/task/scheduler/task-result/{task_id}
```

## 💻 程序化使用

### 基本用法

```python
from backend.app.task.service.sync_scheduler import get_sync_scheduler
from backend.app.task.celery_task.filesync.tasks import sync_file_task

# 获取调度器
scheduler = get_sync_scheduler()

# 刷新所有任务
result = await scheduler.sync_all_tasks_from_db()
print(f"任务同步结果: {result}")

# 验证 cron 表达式
validation = scheduler.validate_cron_expression("0 2 * * *")
print(f"cron 验证: {validation}")

# 立即执行同步任务
task_result = sync_file_task.delay(config_id=1)
print(f"任务ID: {task_result.id}")
```

### 高级用法

```python
import asyncio
from backend.app.task.service.sync_scheduler import get_sync_scheduler
from backend.database.db import async_db_session
from backend.app.coulddrive.crud.crud_filesync import sync_config_dao

async def manage_sync_tasks():
    scheduler = get_sync_scheduler()
    
    # 获取当前状态
    status = scheduler.get_task_status()
    print(f"当前活跃任务: {status['scheduled_config_ids']}")
    
    # 从数据库同步任务
    result = await scheduler.sync_all_tasks_from_db()
    if result["success"]:
        print(f"成功添加 {result['added_count']} 个任务")
    
    # 获取启用的配置
    async with async_db_session() as db:
        configs = await sync_config_dao.get_enabled_configs(db)
        print(f"数据库中有 {len(configs)} 个启用的配置")

# 运行示例
asyncio.run(manage_sync_tasks())
```

## 🔍 监控和调试

### 查看 Celery 状态

```bash
# 查看活跃任务
celery -A app.task.celery inspect active

# 查看已调度任务
celery -A app.task.celery inspect scheduled

# 查看注册的任务
celery -A app.task.celery inspect registered

# 查看统计信息
celery -A app.task.celery inspect stats
```

### 日志监控

系统会记录详细的日志信息：
- 任务调度添加/删除
- 任务执行开始/结束
- 错误和异常信息
- 性能统计数据

### 任务状态说明

- `PENDING`: 任务等待执行
- `STARTED`: 任务开始执行
- `SUCCESS`: 任务执行成功
- `FAILURE`: 任务执行失败
- `RETRY`: 任务重试中

## ⚠️ 注意事项

### 1. 任务并发

- 避免同时执行过多同步任务
- 合理设置 Celery Worker 数量
- 考虑网盘 API 限制

### 2. 错误处理

- 任务失败会自动重试
- 检查网盘认证信息
- 验证同步路径有效性

### 3. 性能优化

- 使用 Redis 作为消息代理
- 设置合理的任务超时时间
- 监控系统资源使用

## 🛠️ 故障排除

### 常见问题

#### 1. 任务不执行
**可能原因：**
- Celery Beat 未启动
- cron 表达式格式错误
- 配置未启用

**解决方法：**
```bash
# 检查 Celery Beat 状态
ps aux | grep "celery.*beat"

# 验证 cron 表达式
curl -X POST "http://localhost:8000/api/v1/task/scheduler/validate-cron" \
  -H "Content-Type: application/json" \
  -d '"0 2 * * *"'

# 刷新任务
curl -X POST "http://localhost:8000/api/v1/task/scheduler/refresh-tasks"
```

#### 2. 任务执行失败
**可能原因：**
- 网盘认证信息过期
- 同步路径不存在
- 网络连接问题

**解决方法：**
```bash
# 查看任务结果
curl "http://localhost:8000/api/v1/task/scheduler/task-result/{task_id}"

# 检查日志
tail -f logs/app.log
```

#### 3. Redis 连接失败
**可能原因：**
- Redis 服务未启动
- 连接配置错误

**解决方法：**
```bash
# 检查 Redis 状态
redis-cli ping

# 检查配置
grep -r "CELERY_BROKER" backend/core/conf.py
```

### 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 同步执行任务（用于调试）
from backend.app.task.celery_task.filesync.tasks import sync_file_task
result = sync_file_task.apply(args=[config_id])
print(result.result)
```

## 📈 最佳实践

### 1. Cron 表达式设计

- 避免在高峰期执行大量任务
- 错开不同配置的执行时间
- 考虑网盘服务器时区

### 2. 任务监控

- 定期检查任务执行状态
- 设置任务失败告警
- 监控系统资源使用

### 3. 配置管理

- 及时更新失效的认证信息
- 定期清理无效配置
- 备份重要的同步配置

### 4. 扩展性

- 使用 Redis Cluster 支持高并发
- 部署多个 Worker 节点
- 实现任务结果持久化

## 🔗 相关链接

- [Celery 官方文档](https://docs.celeryproject.org/)
- [Redis 官方文档](https://redis.io/documentation)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)

## 📞 技术支持

如果遇到问题，请：

1. 查看日志文件
2. 检查配置是否正确
3. 参考故障排除章节
4. 提交 Issue 或联系开发团队 