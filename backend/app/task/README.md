# 任务系统

基于 Celery 的异步任务处理系统，支持定时任务调度和文件同步任务。

## 功能特性

### 🔄 文件同步任务
- **定时同步**: 根据 cron 表达式自动执行同步任务
- **立即执行**: 支持手动触发同步任务
- **批量执行**: 一键执行所有启用的同步配置
- **任务监控**: 实时查看任务执行状态和结果

### ⏰ 任务调度
- **动态调度**: 从数据库动态加载同步配置
- **cron 支持**: 完整的 cron 表达式支持
- **任务管理**: 添加、更新、删除定时任务
- **状态监控**: 查看调度器状态和活跃任务

## 使用方法

### 1. 配置 cron 表达式

在同步配置中设置 cron 表达式，格式为：`分 时 日 月 周`

**示例：**
```
0 2 * * *     # 每天凌晨2点执行
*/30 * * * *  # 每30分钟执行一次
0 9,18 * * 1-5  # 工作日上午9点和下午6点执行
0 0 1 * *     # 每月1号凌晨执行
```

### 2. API 端点

#### 任务调度管理
- `POST /api/v1/task/scheduler/refresh-tasks` - 刷新定时任务
- `GET /api/v1/task/scheduler/task-status` - 获取任务状态
- `POST /api/v1/task/scheduler/validate-cron` - 验证 cron 表达式
- `DELETE /api/v1/task/scheduler/clear-tasks` - 清空所有定时任务

#### 任务执行
- `POST /api/v1/task/scheduler/execute-sync/{config_id}` - 立即执行指定配置的同步任务
- `POST /api/v1/task/scheduler/execute-all-enabled` - 执行所有启用的同步任务
- `GET /api/v1/task/scheduler/task-result/{task_id}` - 获取任务执行结果

### 3. 程序化使用

```python
from backend.app.task.service.sync_scheduler import get_sync_scheduler
from backend.app.task.celery_task.filesync.tasks import sync_file_task

# 获取调度器
scheduler = get_sync_scheduler()

# 刷新所有任务
await scheduler.sync_all_tasks_from_db()

# 验证 cron 表达式
result = scheduler.validate_cron_expression("0 2 * * *")

# 立即执行同步任务
task_result = sync_file_task.delay(config_id=1)
```

## 系统架构

### 组件说明

1. **Celery 任务** (`celery_task/filesync/tasks.py`)
   - `sync_file_task`: 执行单个同步配置的任务
   - `sync_all_enabled_configs`: 批量执行所有启用配置的任务

2. **任务调度器** (`service/sync_scheduler.py`)
   - `SyncTaskScheduler`: 核心调度器类
   - 支持动态添加/删除/更新定时任务
   - cron 表达式解析和验证

3. **API 接口** (`api/v1/scheduler.py`)
   - RESTful API 接口
   - 任务管理和监控功能

4. **启动服务** (`service/startup.py`)
   - 应用启动时自动加载定时任务
   - 应用关闭时清理资源

### 工作流程

1. **应用启动**
   ```
   应用启动 → 加载数据库配置 → 创建定时任务 → 启动调度器
   ```

2. **定时执行**
   ```
   Celery Beat → 触发任务 → 执行同步 → 记录结果
   ```

3. **手动执行**
   ```
   API 调用 → 提交任务 → 异步执行 → 返回任务ID
   ```

## 配置要求

### 数据库字段
确保同步配置表包含以下字段：
- `cron`: cron 表达式字符串
- `enable`: 是否启用（布尔值）
- `remark`: 任务描述

### Celery 配置
在 `backend/core/conf.py` 中配置：
```python
CELERY_BROKER = "redis"  # 或 "rabbitmq"
CELERY_SCHEDULE = {}     # Beat 调度配置
```

## 监控和日志

### 任务状态
- `PENDING`: 任务等待执行
- `STARTED`: 任务开始执行
- `SUCCESS`: 任务执行成功
- `FAILURE`: 任务执行失败
- `RETRY`: 任务重试中

### 日志记录
系统会记录以下信息：
- 任务调度添加/删除
- 任务执行开始/结束
- 错误和异常信息
- 性能统计数据

## 故障排除

### 常见问题

1. **任务不执行**
   - 检查 Celery Beat 是否启动
   - 验证 cron 表达式格式
   - 确认配置已启用

2. **任务执行失败**
   - 查看任务日志
   - 检查网盘认证信息
   - 验证同步路径

3. **调度器状态异常**
   - 重启 Celery Beat
   - 调用刷新任务 API
   - 检查数据库连接

### 调试命令

```bash
# 启动 Celery Worker
celery -A backend.app.task.celery worker --loglevel=info

# 启动 Celery Beat
celery -A backend.app.task.celery beat --loglevel=info

# 查看任务状态
celery -A backend.app.task.celery inspect active

# 查看调度任务
celery -A backend.app.task.celery inspect scheduled
```

## 最佳实践

1. **cron 表达式设计**
   - 避免在高峰期执行大量任务
   - 合理设置任务间隔
   - 考虑网盘 API 限制

2. **任务监控**
   - 定期检查任务执行状态
   - 监控失败任务并及时处理
   - 设置任务超时时间

3. **性能优化**
   - 避免同时执行过多同步任务
   - 合理配置 Celery Worker 数量
   - 使用 Redis 作为消息代理

4. **错误处理**
   - 设置任务重试机制
   - 记录详细的错误日志
   - 实现任务失败通知
