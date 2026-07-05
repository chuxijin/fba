<div align="center">

# FastAPI Best Architecture

**A full-stack application platform for civil service exam preparation, built on [FastAPI Best Architecture](https://github.com/fastapi-practices/fastapi_best_architecture)**

*Question Bank · WeChat Mini Program · Admin Dashboard · E-Commerce · Cloud Drive · Push Notifications*

English | [简体中文](./README.zh-CN.md)

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

## Overview

A comprehensive full-stack platform for civil service exam preparation, powered by FastAPI Best Architecture (FBA). The project adopts a **monorepo** structure with three major components:

- **Backend** — FastAPI-based API server with plugin-driven architecture
- **Frontend** — Vue 3 + Vben Admin management dashboard
- **Mini Program** — UniApp-based WeChat Mini Program for end users

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| API Framework | FastAPI + Granian (ASGI) |
| ORM | SQLAlchemy 2.0 (async) |
| Data Validation | Pydantic v2 + Pydantic Settings |
| Database | PostgreSQL 16+ / MySQL 8+ |
| Cache & MQ | Redis 6+ / RabbitMQ |
| Task Queue | Celery + Flower |
| Observability | OpenTelemetry + Grafana + Loki + Tempo + Prometheus |
| Frontend Admin | Vue 3 + Vben Admin + Ant Design Vue |
| Mini Program | UniApp + Vue 3 + Wot Design Uni |
| API SDK | TypeScript (shared `@fba/api-sdk` package) |
| Deployment | Docker Compose + Supervisor + Nginx |
| CLI | `fba` command powered by Cappa |

---

## Module Architecture

### Business Apps (`backend/app/`)

| Module | Description |
|--------|-------------|
| `admin` | System admin: users, roles, departments, menus, RBAC |
| `question_bank` | Question bank system: banks, questions, analysis, tags, Mini Program API |
| `gongkao` | Civil exam content: categories, expert tips |
| `actcode` | Activation code: batch generation, redemption, usage tracking |
| `membership` | Membership system: plans, subscription management |
| `mall` | Mall & payments: WeChat Pay V3, orders, refunds |
| `coulddrive` | Cloud drive: Baidu NetDisk, Quark Drive, OpenList unified API |
| `bili` | Bilibili integration: content sync with APScheduler |
| `jia` | Push notifications: Firebase Cloud Messaging |
| `invite` | Invite system |
| `social` | Social features |
| `trail` | User trails & analytics |
| `job` | Job/career management |
| `task` | Async task engine (Celery worker + beat + flower) |
| `mcp` | MCP protocol (SSE endpoint) |

### Plugin Ecosystem (`backend/plugin/`)

| Plugin | Description |
|--------|-------------|
| `agiso` | Agiso e-commerce: payment & delivery webhooks, order-based activation |
| `baidupan` | Baidu NetDisk OAuth integration |
| `oauth2` | Third-party login (GitHub, Google, LinuxDo) |
| `ai` | AI capabilities (OpenAI embeddings, pgvector) |
| `notify` | Multi-channel notifications (DingTalk, WeChat Work, Telegram, Server Chan, SMTP) |
| `oss` | Cloud storage (Aliyun OSS, Qiniu Kodo) |
| `app_auth` | App-level authentication |
| `code_generator` | Automated CRUD code generation |
| `render_book` | Document rendering |
| `webhook` | Generic webhook handling |
| `visit_stats` | Visit statistics & analytics |
| `notice` | System notification management |
| `email` | Email service |
| `dict` | Data dictionary management |
| `config` | Dynamic system configuration |
| `links` | Link management |

---

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 16+ (or MySQL 8+)
- Redis 6+
- Node.js 20+ & pnpm 10+ (for frontend / mini program)

### Backend

```bash
# Install uv (recommended) and sync dependencies
pip install uv
uv sync

# Interactive initialization (configure .env, create database, init tables)
fba init --auto

# Or manual setup
cp backend/.env.example backend/.env
# Edit backend/.env with your database, Redis, and API credentials
fba init

# Start the API server
fba run
# API available at http://127.0.0.1:8000
# Swagger docs at http://127.0.0.1:8000/docs

# Start Celery services
fba celery worker
fba celery beat
fba celery flower
```

### Frontend Admin

```bash
cd frontend
pnpm install
pnpm dev:antdv-next
```

### Mini Program

```bash
cd mini
pnpm install
pnpm dev:mp       # WeChat Mini Program
pnpm dev:h5       # H5 preview
```

### 🐳 Docker (Full Stack)

```bash
docker-compose up -d
```

Services included: PostgreSQL, Redis, RabbitMQ, API Server, Celery (Worker + Beat + Flower), Nginx, and the full Grafana observability stack (Loki, Prometheus, Tempo, Alloy, Grafana).

---

## CLI Reference

The project provides a rich CLI via the `fba` command:

```
fba init [--auto]           # Initialize project
fba run [--host] [--port]   # Start API server
fba celery worker|beat|flower   # Celery services
fba alembic revision|upgrade|downgrade|current|history|heads
fba codegen [import]        # Code generation
fba add --path|--repo-url   # Install plugin
fba remove [plugin]         # Remove plugin
fba format                  # Format code (ruff)
fba --sql PATH              # Execute SQL script
```

---

## Key Features

### 🎯 Question Bank System
- Multiple independent question banks
- Question types: single choice, multiple choice, true/false, short answer
- Rich analysis with multiple answer versions
- Category tree structure & tag system
- WeChat Mini Program login & API support

### 💳 E-Commerce & Payments
- **Agiso integration**: payment/delivery webhooks, auto activation code creation
- **WeChat Pay V3**: native payment, refund support
- **Membership system**: plan management, subscription lifecycle

### 🎫 Activation Code System
- Batch generation with configurable format (length, separator, case, checksum)
- Single / multi-use redemption modes
- Usage tracking & audit trail
- Order-based activation (Agiso integration)

### ☁️ Cloud Drive
- Unified API for Baidu NetDisk, Quark Drive, OpenList
- File listing, upload, download, batch operations

### 🔐 Security & Auth
- JWT stateless authentication with refresh tokens
- RBAC authorization with data scope control
- Password security (bcrypt, expiry policy, history check)
- Account locking on failed login attempts
- OAuth2 login (GitHub, Google, LinuxDo)
- Response encryption (AES)

### 📊 Observability
- OpenTelemetry instrumentation (FastAPI, SQLAlchemy, Redis, Celery, HTTPX)
- Grafana dashboards (server metrics, Celery task monitoring)
- Loki log aggregation + Tempo distributed tracing
- Prometheus metrics export

### 🔔 Multi-Channel Notifications
- DingTalk Robot, WeChat Work Bot, Telegram Bot
- Server Chan, SMTP Email
- Configurable priority & fallback

### 📱 Mini Program (WeChat)
- UniApp + Vue 3 + Wot Design Uni
- Question practice with real-time scoring
- Membership & invitation system
- Shared `@fba/api-sdk` TypeScript package

---

## Project Structure

```
fba/
├── backend/                    # FastAPI backend
│   ├── app/                    # Business modules (15 modules)
│   ├── plugin/                 # Plugin ecosystem (16 plugins)
│   ├── common/                 # Shared: models, schemas, security, cache, observability
│   ├── core/                   # Settings (conf.py) & path management
│   ├── database/               # Database engine & Redis client
│   ├── middleware/              # JWT, CORS, access log, opera log, i18n, encrypt
│   ├── utils/                  # Utilities: console, serializers, snowflake, timezone
│   ├── alembic/                # Database migrations
│   ├── cli.py                  # FBA CLI (cappa-based)
│   └── main.py                 # ASGI application entry
├── frontend/                   # Vue 3 + Vben Admin (antdv-next)
│   ├── apps/web-antdv-next/    # Admin dashboard app
│   ├── packages/               # Shared internal packages
│   └── internal/               # Build & config internals
├── mini/                       # UniApp WeChat Mini Program
│   └── src/                    # Mini program source
├── packages/
│   └── api-sdk/                # Shared TypeScript API SDK
├── scripts/                    # Data import & utility scripts
├── deploy/                     # Deployment configs
│   └── backend/
│       ├── docker-compose/     # Docker env files
│       ├── grafana/            # Grafana, Prometheus, Loki, Tempo configs
│       ├── supervisor/         # Supervisor process configs
│       └── nginx.conf          # Nginx reverse proxy
├── docker-compose.yml          # Full-stack Docker Compose
├── Dockerfile                  # Multi-stage build (server, worker, beat, flower)
├── deploy.sh                   # One-click deployment script
├── pyproject.toml              # Python project config (uv / hatch)
└── start.py                    # Windows dev launcher (FastAPI + Celery)
```

---

## Environment Variables

Key `.env` configurations (see `backend/.env.example`):

```env
# Environment
ENVIRONMENT='dev'               # dev | prod

# Database
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
TOKEN_SECRET_KEY='your_secret'  # auto-generated via fba init
```

For full configuration reference, see [`backend/core/conf.py`](./backend/core/conf.py).

---

## Acknowledgements

- [FastAPI Best Architecture](https://github.com/fastapi-practices/fastapi_best_architecture) — Upstream architecture framework
- [Vben Admin](https://www.vben.pro/) — Frontend admin template
- [UniApp](https://uniapp.dcloud.net.cn/) + [unibest](https://unibest.tech/) — Mini program framework

---

## License

This project is licensed under the [MIT License](LICENSE).
