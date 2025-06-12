#!/bin/bash

# FastAPI Best Architecture - Celery 启动脚本
# 适用于 Linux 环境

echo "启动 Celery Worker..."

# 启动 Celery Worker
celery -A backend.app.task.celery worker --loglevel=info --concurrency=4

# 如果需要在后台运行，可以使用以下命令：
# nohup celery -A backend.app.task.celery worker --loglevel=info --concurrency=4 > celery.log 2>&1 &

echo "Celery Worker 已启动" 