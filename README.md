<div align="center">

# 🎓 公考学习平台 · 后端服务

**基于 FastAPI Best Architecture 的公考备考一站式后端系统**

*题库练习 · 经验分享 · 云盘资源 · 智能推送 · 激活码管理*

English | [简体中文](./README.zh-CN.md)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.0%2B-%23336791)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-%23778877)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)
![Docker](https://img.shields.io/badge/Docker-%232496ED?logo=docker&logoColor=white)

</div>

---

## 📋 Overview

A comprehensive backend system for civil service exam preparation, built on top of FastAPI Best Architecture (FBA). It provides question bank management, cloud drive integration, activation code sales, push notification services, and more.

---

## 🧩 Module Architecture

### 📱 Business Apps (`backend/app/`)

| Module | Description |
|--------|-------------|
| `admin` | System admin: users, roles, departments, menus, RBAC |
| `gongkao` | Civil exam content: questions, categories, expert tips |
| `question_bank` | Question bank system: banks, questions, analysis, tags |
| `actcode` | Activation code system: batch generation, redemption, user activation |
| `coulddrive` | Multi-cloud drive management: Baidu, Quark, Alist |
| `bili` | Bilibili content integration |
| `jia` | Mobile push notification service (Firebase) |
| `social` | Social features |
| `job` | Job/career management |
| `task` | Async task engine (Celery) |
| `mcp` | MCP protocol support |

### 🔌 Plugins (`backend/plugin/`)

| Plugin | Description |
|--------|-------------|
| `agiso` | Agiso e-commerce: payment & delivery webhooks, order-based activation |
| `baidupan` | Baidu NetDisk OAuth integration |
| `oauth2` | Third-party login (GitHub, Google, LinuxDo) |
| `ai` | AI capabilities (embeddings, vector search) |
| `code_generator` | Automated CRUD code generation |
| `webhook` | Generic webhook handling |
| `visit_stats` | Visit statistics & analytics |
| `notice` | System notification management |
| `email` | Email service |
| `dict` | Data dictionary management |
| `config` | Dynamic system configuration |
| `links` | Link management |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 16.0+
- Redis 6.0+

## License

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your database, Redis, and API credentials

# Initialize database
cd backend
alembic upgrade head

# Start the server
python cli.py run
```

### 🐳 Docker

```bash
docker-compose up -d
```

---

## 🔑 Key Features

### 🎯 Question Bank System
- Multiple question banks with independent question pools
- Question types: single choice, multiple choice, true/false, short answer
- Rich analysis with multiple answer versions
- Category tree structure, tag system
- WeChat Mini Program login & API support

### 💳 Agiso E-Commerce Integration
- **Payment Push** (`aopic=2097152`): Log buyer payment notifications
- **Delivery Push** (`aopic=2048`): Auto-create activation codes from order numbers
- **Deduplication**: Same order + push type = exactly one record
- **User Activation**: `POST /api/v1/actcode/agiso/activate` — order number as activation code, auto-create user with designated role & department

### 🎫 Activation Code System
- Batch generation with configurable code format
- Multiple redemption modes (single/multi-use)
- Usage tracking & audit trail
- Order-based activation (Agiso integration)

### ☁️ Cloud Drive Management
- Unified API for Baidu NetDisk, Quark Drive, Alist
- File listing, upload, download, batch operations
- Resource synchronization

### 🔐 Security
- JWT authentication (stateless, scalable)
- RBAC authorization with data scope control
- Password security (bcrypt, expiry, history check)
- Account locking on failed attempts

### 📊 System Management
- User, role, department, menu CRUD
- Operation logging
- Server & Redis monitoring
- Celery task management

---

## 📁 Project Structure

```
fba/
├── backend/
│   ├── app/                    # Business modules
│   │   ├── admin/              # System admin (user/role/dept/menu)
│   │   ├── gongkao/            # Civil exam content
│   │   ├── question_bank/      # Question bank system
│   │   ├── actcode/            # Activation code management
│   │   ├── coulddrive/         # Cloud drive integration
│   │   ├── bili/               # Bilibili integration
│   │   ├── jia/                # Firebase push notifications
│   │   ├── social/             # Social features
│   │   ├── job/                # Job management
│   │   ├── task/               # Celery async tasks
│   │   └── mcp/                # MCP protocol
│   ├── plugin/                 # Plugin ecosystem
│   │   ├── agiso/              # Agiso payment & delivery
│   │   ├── baidupan/           # Baidu NetDisk OAuth
│   │   ├── oauth2/             # Third-party auth
│   │   ├── ai/                 # AI capabilities
│   │   └── ...                 # More plugins
│   ├── common/                 # Shared utilities & base classes
│   ├── core/                   # Configuration & path management
│   ├── database/               # Database connection & session
│   ├── middleware/              # JWT, CORS, logging middleware
│   └── utils/                  # Utility functions
└── deploy/                     # Deployment configs
```

---

## ⚙️ Environment Variables

Key `.env` configurations:

```env
# Database
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

# Agiso
AGISO_APP_SECRET=your_agiso_app_secret

# WeChat Mini Program
WX_MINIAPP_APPID=your_appid
WX_MINIAPP_SECRET=your_secret
```

---

## 📄 License

This project is based on [FastAPI Best Architecture](https://github.com/fastapi-practices/fastapi_best_architecture) and licensed under the [MIT License](LICENSE).
