<div align="center">

# 🎓 公考学习平台 · 后端服务

**基于 FastAPI Best Architecture 的公考备考一站式后端系统**

*题库练习 · 经验分享 · 云盘资源 · 智能推送 · 激活码管理*

简体中文 | [English](./README.md)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.0%2B-%23336791)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-%23778877)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)
![Docker](https://img.shields.io/badge/Docker-%232496ED?logo=docker&logoColor=white)

</div>

---

## 📋 项目简介

公考备考一站式后端系统，基于 [FastAPI Best Architecture (FBA)](https://github.com/fastapi-practices/fastapi_best_architecture) 构建。提供题库管理、云盘资源整合、激活码销售、推送通知、第三方支付对接等功能。

---

## 🧩 模块架构

### 📱 业务模块 (`backend/app/`)

| 模块 | 功能说明 |
|------|----------|
| `admin` | 系统管理：用户、角色、部门、菜单、RBAC 权限控制 |
| `gongkao` | 公考内容：试题管理、分类体系、备考经验 |
| `question_bank` | 题库系统：题库、试题、解析、标签、微信小程序 API |
| `actcode` | 激活码系统：批量生成、兑换、用户激活、使用记录 |
| `coulddrive` | 多云盘管理：百度网盘、夸克网盘、Alist 统一接口 |
| `bili` | B站内容整合 |
| `jia` | 移动端推送服务 (Firebase) |
| `social` | 社交功能 |
| `job` | 岗位管理 |
| `task` | 异步任务引擎 (Celery) |
| `mcp` | MCP 协议支持 |

### 🔌 插件系统 (`backend/plugin/`)

| 插件 | 功能说明 |
|------|----------|
| `agiso` | 阿奇索电商对接：支付/发货推送、订单号激活 |
| `baidupan` | 百度网盘 OAuth 授权 |
| `oauth2` | 第三方登录 (GitHub, Google, LinuxDo) |
| `ai` | AI 能力 (向量化、语义搜索) |
| `code_generator` | 自动化 CRUD 代码生成 |
| `webhook` | 通用 Webhook 处理 |
| `visit_stats` | 访问统计分析 |
| `notice` | 系统通知管理 |
| `email` | 邮件服务 |
| `dict` | 数据字典管理 |
| `config` | 动态系统配置 |
| `links` | 链接管理 |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- PostgreSQL 16.0+
- Redis 6.0+

### 安装部署

```bash
# 克隆仓库
git clone <your-repo-url>
cd fba

# 创建虚拟环境
python -m venv .venv
.venv/Scripts/activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，配置数据库、Redis、API 密钥等

# 初始化数据库
cd backend
alembic upgrade head

# 启动服务
python cli.py run
```

### 🐳 Docker 部署

```bash
docker-compose up -d
```

---

## 🔑 核心功能

### 🎯 题库系统
- 多题库独立题池管理
- 题型支持：单选、多选、判断、简答
- 多版本答案解析
- 分类树结构、标签体系
- 微信小程序登录 & API 支持

### 💳 阿奇索电商对接
- **买家付款推送** (`aopic=2097152`)：记录付款通知日志
- **自动发货推送** (`aopic=2048`)：自动以订单号创建激活码
- **推送去重**：同一订单号 + 推送类型，仅保存一条记录
- **用户激活**：`POST /api/v1/actcode/agiso/activate` — 用订单号作为激活码，自动创建用户并分配指定角色和部门

### 🎫 激活码系统
- 批量生成，可配置码格式（长度、分隔符、大小写、校验位）
- 单次/多次使用模式
- 使用记录追踪与审计
- 与阿奇索订单联动，支持订单号直接激活

### ☁️ 云盘资源管理
- 百度网盘、夸克网盘、Alist 统一 API
- 文件列表、上传、下载、批量操作
- 资源同步管理

### � 安全体系
- JWT 无状态认证
- RBAC 权限控制 + 数据范围
- 密码安全（bcrypt 加密、过期策略、历史检查）
- 登录失败锁定机制

### � 系统管理
- 用户 / 角色 / 部门 / 菜单 CRUD
- 操作日志记录
- 服务器 & Redis 监控
- Celery 任务管理

---

## 📁 项目结构

```
fba/
├── backend/
│   ├── app/                    # 业务模块
│   │   ├── admin/              # 系统管理 (用户/角色/部门/菜单)
│   │   ├── gongkao/            # 公考内容管理
│   │   ├── question_bank/      # 题库系统
│   │   ├── actcode/            # 激活码管理
│   │   ├── coulddrive/         # 云盘集成
│   │   ├── bili/               # B站集成
│   │   ├── jia/                # Firebase 推送
│   │   ├── social/             # 社交功能
│   │   ├── job/                # 岗位管理
│   │   ├── task/               # Celery 异步任务
│   │   └── mcp/                # MCP 协议
│   ├── plugin/                 # 插件生态
│   │   ├── agiso/              # 阿奇索支付发货
│   │   ├── baidupan/           # 百度网盘 OAuth
│   │   ├── oauth2/             # 第三方登录
│   │   ├── ai/                 # AI 能力
│   │   └── ...                 # 更多插件
│   ├── common/                 # 公共工具 & 基类
│   ├── core/                   # 配置 & 路径管理
│   ├── database/               # 数据库连接 & 会话
│   ├── middleware/              # JWT、CORS、日志中间件
│   └── utils/                  # 工具函数
└── deploy/                     # 部署配置
```

---

## ⚙️ 环境变量

`.env` 关键配置项：

```env
# 数据库
DATABASE_TYPE=postgresql
DATABASE_HOST=your_host
DATABASE_PORT=5432
DATABASE_USER=your_user
DATABASE_PASSWORD=your_password

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=your_password

# JWT Token
TOKEN_SECRET_KEY=your_secret_key

# 阿奇索
AGISO_APP_SECRET=your_agiso_app_secret

# 微信小程序
WX_MINIAPP_APPID=your_appid
WX_MINIAPP_SECRET=your_secret
```

---

## � 致谢

本项目基于 [FastAPI Best Architecture](https://github.com/fastapi-practices/fastapi_best_architecture) 构建，感谢原作者的开源贡献。

---

## 📄 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
