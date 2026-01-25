#!/bin/bash
# -*- coding: utf-8 -*-
# 部署脚本 - FBA 项目
# 用法: ./deploy.sh

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}       FBA 部署脚本开始执行${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 函数：打印步骤
step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

# 函数：打印成功
success() {
    echo -e "${GREEN}✔ $1${NC}"
}

# 函数：打印错误并退出
error() {
    echo -e "${RED}✖ 错误: $1${NC}"
    exit 1
}

# 步骤 1: Git Pull（强制拉取）
step "步骤 1/4: 拉取最新代码..."
cd "$PROJECT_DIR"

# 记录当前 commit，用于后续判断依赖是否变化
OLD_COMMIT=$(git rev-parse HEAD)

# 先获取远程更新
git fetch --all || error "git fetch 失败"

# 强制重置到远程分支（丢弃本地修改）
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
git reset --hard origin/$CURRENT_BRANCH || error "git reset 失败"

# 记录新的 commit
NEW_COMMIT=$(git rev-parse HEAD)

# 检查依赖文件是否有变化
DEPS_CHANGED=false
if [ "$OLD_COMMIT" != "$NEW_COMMIT" ]; then
    if git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT" | grep -qE "(pyproject\.toml|uv\.lock)$"; then
        DEPS_CHANGED=true
    fi
fi

# 拉取子模块（如果有）
if [ -f ".gitmodules" ]; then
    git submodule update --init --recursive || error "git submodule update 失败"
fi

success "代码拉取完成 (分支: $CURRENT_BRANCH)"
echo ""

# 步骤 2: 激活虚拟环境
step "步骤 2/4: 激活虚拟环境..."
cd "$BACKEND_DIR"

if [ ! -d "$VENV_DIR" ]; then
    error "虚拟环境不存在: $VENV_DIR"
fi

source "$VENV_DIR/bin/activate" || error "激活虚拟环境失败"
success "虚拟环境已激活"
echo ""

# 步骤 3: 同步依赖（仅在依赖文件变化时执行）
step "步骤 3/4: 检查依赖..."

if [ "$DEPS_CHANGED" = true ]; then
    echo "  检测到 pyproject.toml 或 uv.lock 有变化，正在同步依赖..."
    uv sync || error "uv sync 失败"
    success "依赖同步完成"
else
    echo "  依赖文件无变化，跳过 uv sync"
    success "依赖检查完成（无需更新）"
fi
echo ""

# 步骤 4: 重启服务
step "步骤 4/4: 重启服务..."

# 重新读取配置并应用变更
sudo supervisorctl reread || error "supervisorctl reread 失败"
sudo supervisorctl update || error "supervisorctl update 失败"

# 一次性重启所有 fba 服务
echo "  重启 fba:* ..."
sudo supervisorctl restart fba:* || error "重启 fba 服务失败"

success "所有服务重启完成"
echo ""

# 显示服务状态
step "当前服务状态:"
sudo supervisorctl status fba:*
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}       ✔ 部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
