# Celery 启动指南 - Linux 环境

## 快速启动

### 方式一：使用脚本启动
```bash
cd backend
chmod +x start-celery.sh
./start-celery.sh
```

### 方式二：直接命令启动
```bash
# 前台运行
celery -A backend.app.task.celery worker --loglevel=info --concurrency=4

# 后台运行
nohup celery -A backend.app.task.celery worker --loglevel=info --concurrency=4 > celery.log 2>&1 &
```

## 参数说明

- `--loglevel=info`: 设置日志级别
- `--concurrency=4`: 设置并发工作进程数（根据CPU核心数调整）

## 查看状态

```bash
# 查看活动任务
celery -A backend.app.task.celery inspect active

# 查看注册的任务
celery -A backend.app.task.celery inspect registered

# 查看工作进程状态
celery -A backend.app.task.celery inspect stats
```

## 停止 Celery

```bash
# 如果是前台运行，直接 Ctrl+C

# 如果是后台运行，查找进程并终止
ps aux | grep celery
kill <PID>
```

## 定时任务

系统会自动执行以下定时任务：
- 每分钟检查一次文件同步 cron 任务
- 每周日删除过期操作日志
- 每月15日删除过期登录日志

## API 接口

- `POST /api/v1/task/filesync/check-cron-tasks` - 手动检查定时任务
- `POST /api/v1/task/filesync/execute/{config_id}` - 执行指定配置的同步任务
- `GET /api/v1/task/filesync/configs-with-cron` - 获取设置了定时的配置列表

## 注意事项

1. 确保 Redis 服务正常运行
2. 确保数据库连接配置正确
3. 建议在生产环境使用进程管理工具（如 supervisor） 