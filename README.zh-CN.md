<div align="center">

<img alt="Logo 包含了 FBA 三个字母抽象结合，形成了一个类似从地面扩散投影上来的闪电" width="320" src="https://wu-clan.github.io/picx-images-hosting/logo/fba.png">

# 🚀 FastAPI Best Architecture

**终极企业级后端架构解决方案**

*以前沿技术栈和最佳实践赋能开发者*

简体中文 | [English](./README.md)

[![GitHub](https://img.shields.io/github/license/fastapi-practices/fastapi_best_architecture)](https://github.com/fastapi-practices/fastapi_best_architecture/blob/master/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-%2300758f)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.0%2B-%23336791)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-%23778877)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
![Docker](https://img.shields.io/badge/Docker-%232496ED?logo=docker&logoColor=white)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?logo=discord&logoColor=white)](https://discord.com/invite/yNN3wTbVAC)
![Discord](https://img.shields.io/discord/1185035164577972344)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/fastapi-practices/fastapi_best_architecture)

---

## ✨ 项目亮点

### 🏗️ **伪三层架构**
超越传统 MVC 的革命性设计模式，为 Python Web 开发带来企业级可扩展性。

| 架构层 | Java | FBA |
|--------|------|-----|
| 🎨 **表现层** | Controller | API |
| 📦 **数据传输** | DTO | Schema |
| 💼 **业务逻辑** | Service + Impl | Service |
| 🗄️ **数据访问** | DAO / Mapper | CRUD |
| 📊 **数据模型** | Model / Entity | Model |

### 🔌 **动态插件系统**
- **ZIP 安装**: 拖拽式插件包安装
- **Git 集成**: 直接从代码仓库安装
- **热重载**: 无需重启即可启用/禁用插件
- **依赖管理**: 自动处理插件依赖关系

### ☁️ **多云盘统一管理**
为多个云存储提供商提供统一接口：

- 🔵 **百度网盘** - 完整功能支持
- 🟣 **夸克网盘** - 全面集成
- 🟠 **Alist 网盘** - 通用兼容性
- 🔄 **智能同步** - 智能文件同步
- 📊 **资源管理** - 批量操作和分析

### 🔐 **企业级授权系统**
- **设备绑定**: 基于硬件的授权机制
- **套餐管理**: 灵活的定价和折扣策略
- **兑换码**: 批量生成和管理
- **订单处理**: 完整的电商工作流程

### ⚡ **高性能任务引擎**
- **Celery 集成**: 分布式任务处理
- **智能调度**: 基于 Cron 的自动化
- **实时监控**: 任务状态和分析
- **故障恢复**: 自动重试机制

---

## 🚀 快速开始

### 环境要求
- Python 3.10+
- MySQL 8.0+ / PostgreSQL 16.0+
- Redis 6.0+

### 安装部署

```bash
# 克隆仓库
git clone https://github.com/fastapi-practices/fastapi_best_architecture.git
cd fastapi_best_architecture

# 配置环境
cp .env.example .env
# 编辑 .env 文件配置你的环境

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
alembic upgrade head

# 启动服务
python cli.py run
```

### 🐳 Docker 部署

```bash
# 使用 docker-compose 快速启动
docker-compose up -d
```

---

## 🌟 核心特性

### 🎯 **开发体验**
- **类型安全**: 完整的 Pydantic v2 集成
- **自动文档**: 交互式 Swagger/ReDoc
- **代码生成**: 自动化 CRUD 操作
- **热重载**: 闪电般的开发速度

### 🔒 **安全优先**
- **JWT 认证**: 无状态且可扩展
- **RBAC 授权**: 基于角色的访问控制
- **数据加密**: 多层保护机制
- **CORS 管理**: 跨域安全控制

### 📈 **性能优化**
- **异步处理**: 非阻塞 I/O 操作
- **连接池**: 数据库优化
- **Redis 缓存**: 闪电般的响应速度
- **负载均衡**: 水平扩展能力

### 🛠️ **DevOps 就绪**
- **Docker 支持**: 容器化部署
- **健康检查**: 系统监控
- **结构化日志**: 可搜索的日志系统
- **性能指标**: 性能分析

---

## 📁 项目结构

```
fastapi_best_architecture/
├── 🏠 backend/                 # 核心后端应用
│   ├── 📱 app/                 # 应用模块
│   │   ├── 👥 admin/           # 管理后台
│   │   ├── ☁️ coulddrive/      # 云盘集成
│   │   └── ⚡ task/            # 任务管理
│   ├── 🔌 plugin/              # 插件生态系统
│   ├── 🛠️ common/              # 共享工具
│   ├── ⚙️ core/                # 核心配置
│   └── 🗃️ database/            # 数据库连接
├── 🎨 frontend/                # 现代化 Web 界面
└── 🚀 deploy/                  # 部署配置
```

---

## 🔧 高级配置

### 插件开发
```python
# plugin.toml
[plugin]
summary = "我的超棒插件"
version = "1.0.0"
description = "插件功能描述"
author = "你的名字"

[app]
extend = "admin"  # 扩展现有应用

[api.my_feature]
prefix = "/my-feature"
tags = "我的功能 API"
```

### 云盘集成
```python
from backend.app.coulddrive.service.yp_service import BaseDrive

# 初始化云盘管理器
drive = BaseDrive()

# 从百度网盘获取文件列表
files = await drive.get_disk_list(
    x_token="your_token",
    params=ListFilesParam(
        drive_type="BaiduDrive",
        file_path="/",
        recursive=True
    )
)
```

### 任务调度
```python
from backend.app.task.celery_task.base import BaseTask

@celery_app.task(base=BaseTask)
def my_background_task(param1: str, param2: int):
    """自定义后台任务"""
    # 你的任务逻辑
    return {"status": "completed", "result": "success"}
```

---

## 🎨 界面预览

### 📊 管理后台
- 现代化的管理界面
- 响应式设计
- 深色/浅色主题切换
- 实时数据更新

### ☁️ 云盘管理
- 统一的文件管理界面
- 批量操作支持
- 同步状态监控
- 资源使用统计

### 🔌 插件管理
- 可视化插件安装
- 一键启用/禁用
- 依赖关系图
- 插件商店（开发中）

---

## 🤝 参与贡献

欢迎参与贡献！请查看我们的 [贡献指南](CONTRIBUTING.md) 了解详情。

### 开发环境配置
```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
pytest

# 代码格式化
ruff format .

# 类型检查
mypy .
```

---

## 📚 文档

访问我们的 [官方文档](https://fastapi-practices.github.io/fastapi_best_architecture_docs/) 获取完整文档。

### 快速链接
- 🚀 [快速开始](https://fastapi-practices.github.io/fastapi_best_architecture_docs/getting-started/)
- 🔌 [插件开发](https://fastapi-practices.github.io/fastapi_best_architecture_docs/plugins/)
- ☁️ [云盘集成](https://fastapi-practices.github.io/fastapi_best_architecture_docs/cloud-drives/)
- 🔐 [认证授权](https://fastapi-practices.github.io/fastapi_best_architecture_docs/auth/)

---

## 🏆 贡献者

<a href="https://github.com/fastapi-practices/fastapi_best_architecture/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=fastapi-practices/fastapi_best_architecture"/>
</a>

---

## 🙏 特别鸣谢

- [FastAPI](https://fastapi.tiangolo.com/) - 我们架构的基础
- [Pydantic](https://docs.pydantic.dev/latest/) - 数据验证和序列化
- [SQLAlchemy](https://docs.sqlalchemy.org/en/20/) - Python SQL 工具包
- [Casbin](https://casbin.org/zh/) - 权限管理库
- [Ruff](https://beta.ruff.rs/docs/) - 闪电般快速的 Python 代码检查工具

---

## 💬 社区

加入我们活跃的社区：

- 💬 [Discord 服务器](https://discord.com/invite/yNN3wTbVAC)
- 🐛 [问题追踪](https://github.com/fastapi-practices/fastapi_best_architecture/issues)
- 💡 [功能请求](https://github.com/fastapi-practices/fastapi_best_architecture/discussions)

---

## ☕ 赞助我们

如果这个项目对你有帮助，请考虑赞助我们：

[:coffee: **赞助我们** :coffee:](https://wu-clan.github.io/sponsor/)

你的支持帮助我们维护和改进这个项目！

---

## 📄 许可证

本项目基于 [MIT 许可证](https://github.com/fastapi-practices/fastapi_best_architecture/blob/master/LICENSE) 开源。

---

<div align="center">

**⭐ 在 GitHub 上给我们点个 Star — 这对我们意义重大！**

[![Stargazers over time](https://starchart.cc/fastapi-practices/fastapi_best_architecture.svg?variant=adaptive)](https://starchart.cc/fastapi-practices/fastapi_best_architecture)

</div>
