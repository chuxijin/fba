<div align="center">

# FastAPI Best Architecture

**基于 [FastAPI Best Architecture](https://github.com/fastapi-practices/fastapi_best_architecture) 的公考备考一站式全栈平台**

*题库练习 · 微信小程序 · 管理后台 · 电商支付 · 云盘资源 · 推送通知*

简体中文 | [English](./README.md)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135%2B-%23009688?logo=fastapi&logoColor=white)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2B-%23336791?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-6%2B-%23DC382D?logo=redis&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-%234FC08D?logo=vue.js&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-%232496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## 项目简介

公考备考一站式全栈平台，基于 FastAPI Best Architecture (FBA) 构建。项目采用 **Monorepo** 结构，包含三大组件：

- **Backend** — 基于 FastAPI 的 API 服务，插件化架构
- **Frontend** — Vue 3 + Vben Admin 管理后台
- **Mini Program** — UniApp 微信小程序，面向终端用户

---

## 技术栈

| 层级 | 技术 |
|------|------|
| API 框架 | FastAPI + Granian (ASGI) |
| ORM | SQLAlchemy 2.0 (async) |
| 数据验证 | Pydantic v2 + Pydantic Settings |
| 数据库 | PostgreSQL 16+ / MySQL 8+ |
| 缓存 & 消息 | Redis 6+ / RabbitMQ |
| 任务队列 | Celery + Flower |
| 可观测性 | OpenTelemetry + Grafana + Loki + Tempo + Prometheus |
| 管理后台 | Vue 3 + Vben Admin + Ant Design Vue |
| 小程序 | UniApp + Vue 3 + Wot Design Uni |
| API SDK | TypeScript（共享 `@fba/api-sdk` 包） |
| 部署 | Docker Compose + Supervisor + Nginx |
| CLI 工具 | `fba` 命令（基于 Cappa） |

---

## 模块架构

### 业务模块 (`backend/app/`)

| 模块 | 功能说明 |
|------|----------|
| `admin` | 系统管理：用户、角色、部门、菜单、RBAC 权限控制 |
| `question_bank` | 题库系统：题库、试题、解析、标签、小程序 API |
| `gongkao` | 公考内容：分类体系、备考经验 |
| `actcode` | 激活码：批量生成、兑换、使用记录追踪 |
| `membership` | 会员系统：套餐管理、订阅生命周期 |
| `mall` | 商城 & 支付：微信支付 V3、订单、退款 |
| `coulddrive` | 云盘管理：百度网盘、夸克网盘、OpenList 统一 API |
| `bili` | B 站集成：内容同步（APScheduler 调度） |
| `jia` | 推送服务：Firebase Cloud Messaging |
| `invite` | 邀请系统 |
| `social` | 社交功能 |
| `trail` | 用户行为追踪 & 分析 |
| `job` | 岗位管理 |
| `task` | 异步任务引擎（Celery worker + beat + flower） |
| `mcp` | MCP 协议（SSE 端点） |

### 插件生态 (`backend/plugin/`)

| 插件 | 功能说明 |
|------|----------|
| `agiso` | 阿奇索电商：支付 / 发货推送、订单号激活 |
| `baidupan` | 百度网盘 OAuth 授权 |
| `oauth2` | 第三方登录（GitHub、Google、LinuxDo） |
| `ai` | AI 能力（OpenAI 向量化、pgvector） |
| `notify` | 多渠道通知（钉钉、企微、Telegram、Server 酱、SMTP） |
| `oss` | 云存储（阿里云 OSS、七牛 Kodo） |
| `app_auth` | 应用级认证 |
| `code_generator` | 自动化 CRUD 代码生成 |
| `render_book` | 文档渲染 |
| `webhook` | 通用 Webhook 处理 |
| `visit_stats` | 访问统计分析 |
| `notice` | 系统通知管理 |
| `email` | 邮件服务 |
| `dict` | 数据字典管理 |
| `config` | 动态系统配置 |
| `links` | 链接管理 |

---

## 快速开始

### 环境要求

- Python 3.10+
- PostgreSQL 16+（或 MySQL 8+）
- Redis 6+
- Node.js 20+ & pnpm 10+（前端 / 小程序）

### 后端

```bash
# 安装 uv（推荐）并同步依赖
pip install uv
uv sync

# 交互式初始化（配置 .env、创建数据库、初始化表结构）
fba init --auto

# 或手动配置
cp backend/.env.example backend/.env
# 编辑 backend/.env，配置数据库、Redis、API 密钥等
fba init

# 启动 API 服务
fba run
# API 地址：http://127.0.0.1:8000
# Swagger 文档：http://127.0.0.1:8000/docs

# 启动 Celery 服务
fba celery worker
fba celery beat
fba celery flower
```

### 管理后台

```bash
cd frontend
pnpm install
pnpm dev:antdv-next
```

### 微信小程序

```bash
cd mini
pnpm install
pnpm dev:mp       # 微信小程序
pnpm dev:h5       # H5 预览
```

### 🐳 Docker 部署（全栈）

```bash
docker-compose up -d
```

包含服务：PostgreSQL、Redis、RabbitMQ、API Server、Celery（Worker + Beat + Flower）、Nginx，以及完整的 Grafana 可观测性套件（Loki、Prometheus、Tempo、Alloy、Grafana）。

---

## CLI 命令参考

项目通过 `fba` 命令提供丰富的 CLI 工具：

```
fba init [--auto]           # 初始化项目
fba run [--host] [--port]   # 启动 API 服务
fba celery worker|beat|flower   # Celery 服务
fba alembic revision|upgrade|downgrade|current|history|heads
fba codegen [import]        # 代码生成
fba add --path|--repo-url   # 安装插件
fba remove [plugin]         # 卸载插件
fba format                  # 格式化代码（ruff）
fba --sql PATH              # 执行 SQL 脚本
```

---

## 核心功能

### 🎯 题库系统
- 多题库独立题池管理
- 题型支持：单选、多选、判断、简答
- 多版本答案解析
- 分类树结构 & 标签体系
- 微信小程序登录 & API 支持

### 💳 电商 & 支付
- **阿奇索对接**：支付 / 发货推送、自动创建激活码
- **微信支付 V3**：小程序支付、退款
- **会员系统**：套餐管理、订阅生命周期

### 🎫 激活码系统
- 批量生成，可配置码格式（长度、分隔符、大小写、校验位）
- 单次 / 多次使用模式
- 使用记录追踪与审计
- 与阿奇索订单联动，支持订单号直接激活

### ☁️ 云盘资源管理
- 百度网盘、夸克网盘、OpenList 统一 API
- 文件列表、上传、下载、批量操作

### 🔐 安全 & 认证
- JWT 无状态认证 + Refresh Token
- RBAC 权限控制 + 数据范围
- 密码安全（bcrypt 加密、过期策略、历史检查）
- 登录失败锁定机制
- OAuth2 登录（GitHub、Google、LinuxDo）
- 响应加密（AES）

### 📊 可观测性
- OpenTelemetry 全链路埋点（FastAPI、SQLAlchemy、Redis、Celery、HTTPX）
- Grafana 仪表盘（服务器指标、Celery 任务监控）
- Loki 日志聚合 + Tempo 分布式追踪
- Prometheus 指标导出

### 🔔 多渠道通知
- 钉钉机器人、企业微信机器人、Telegram Bot
- Server 酱、SMTP 邮件
- 可配置优先级 & 降级策略

### 📱 微信小程序
- UniApp + Vue 3 + Wot Design Uni
- 题库练习 & 实时评分
- 会员 & 邀请系统
- 共享 `@fba/api-sdk` TypeScript 包

---

## 项目结构

```
fba/
├── backend/                    # FastAPI 后端
│   ├── app/                    # 业务模块（15 个模块）
│   ├── plugin/                 # 插件生态（16 个插件）
│   ├── common/                 # 公共：模型、Schema、安全、缓存、可观测性
│   ├── core/                   # 配置（conf.py）& 路径管理
│   ├── database/               # 数据库引擎 & Redis 客户端
│   ├── middleware/              # JWT、CORS、访问日志、操作日志、i18n、加密
│   ├── utils/                  # 工具：控制台、序列化器、雪花 ID、时区
│   ├── alembic/                # 数据库迁移
│   ├── cli.py                  # FBA CLI（基于 Cappa）
│   └── main.py                 # ASGI 应用入口
├── frontend/                   # Vue 3 + Vben Admin（antdv-next）
│   ├── apps/web-antdv-next/    # 管理后台应用
│   ├── packages/               # 共享内部包
│   └── internal/               # 构建 & 配置内部模块
├── mini/                       # UniApp 微信小程序
│   └── src/                    # 小程序源码
├── packages/
│   └── api-sdk/                # 共享 TypeScript API SDK
├── scripts/                    # 数据导入 & 工具脚本
├── deploy/                     # 部署配置
│   └── backend/
│       ├── docker-compose/     # Docker 环境变量文件
│       ├── grafana/            # Grafana、Prometheus、Loki、Tempo 配置
│       ├── supervisor/         # Supervisor 进程配置
│       └── nginx.conf          # Nginx 反向代理
├── docker-compose.yml          # 全栈 Docker Compose
├── Dockerfile                  # 多阶段构建（server、worker、beat、flower）
├── deploy.sh                   # 一键部署脚本
├── pyproject.toml              # Python 项目配置（uv / hatch）
└── start.py                    # Windows 开发启动器（FastAPI + Celery）
```

---

## 环境变量

`.env` 关键配置项（参见 `backend/.env.example`）：

```env
# 环境
ENVIRONMENT='dev'               # dev | prod

# 数据库
DATABASE_TYPE='postgresql'      # postgresql | mysql
DATABASE_HOST='127.0.0.1'
DATABASE_PORT=5432
DATABASE_USER='postgres'
DATABASE_PASSWORD='123456'

# Redis
REDIS_HOST='127.0.0.1'
REDIS_PORT=6379
REDIS_PASSWORD=''

# Token
TOKEN_SECRET_KEY='your_secret'  # 通过 fba init 自动生成
```

完整配置参考请查看 [`backend/core/conf.py`](./backend/core/conf.py)。

---

## 致谢

- [FastAPI Best Architecture](https://github.com/fastapi-practices/fastapi_best_architecture) — 上游架构框架
- [Vben Admin](https://www.vben.pro/) — 前端管理模板
- [UniApp](https://uniapp.dcloud.net.cn/) + [unibest](https://unibest.tech/) — 小程序开发框架

---

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
