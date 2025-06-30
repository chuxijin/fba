<div align="center">

<img alt="The logo includes the abstract combination of the three letters FBA, forming a lightning bolt that seems to spread out from the ground" width="320" src="https://wu-clan.github.io/picx-images-hosting/logo/fba.png">

# 🚀 FastAPI Best Architecture

**The Ultimate Enterprise-Grade Backend Architecture Solution**

*Empowering developers with cutting-edge technology stack and best practices*

English | [简体中文](./README.zh-CN.md)

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

## ✨ What Makes Us Special

### 🏗️ **Pseudo 3-Tier Architecture**
Revolutionary design pattern that goes beyond traditional MVC, bringing enterprise-level scalability to Python web development.

| Layer | Java | FBA |
|-------|------|-----|
| 🎨 **Presentation** | Controller | API |
| 📦 **Data Transfer** | DTO | Schema |
| 💼 **Business Logic** | Service + Impl | Service |
| 🗄️ **Data Access** | DAO / Mapper | CRUD |
| 📊 **Model** | Model / Entity | Model |

### 🔌 **Dynamic Plugin System**
- **ZIP Installation**: Drag & drop plugin packages
- **Git Integration**: Install directly from repositories  
- **Hot Reload**: Enable/disable plugins without restart
- **Dependency Management**: Automatic requirement handling

### ☁️ **Multi-Cloud Drive Management**
Unified interface for managing multiple cloud storage providers:

- 🔵 **Baidu NetDisk** - Full feature support
- 🟣 **Quark Drive** - Complete integration
- 🟠 **Alist Drive** - Universal compatibility
- 🔄 **Smart Sync** - Intelligent file synchronization
- 📊 **Resource Management** - Batch operations & analytics

### 🔐 **Enterprise Authorization System**
- **Device Binding**: Hardware-based authorization
- **Package Management**: Flexible pricing & discounts
- **Redemption Codes**: Bulk generation & management
- **Order Processing**: Complete e-commerce workflow

### ⚡ **High-Performance Task Engine**
- **Celery Integration**: Distributed task processing
- **Smart Scheduling**: Cron-based automation
- **Real-time Monitoring**: Task status & analytics
- **Failure Recovery**: Automatic retry mechanisms

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- MySQL 8.0+ / PostgreSQL 16.0+
- Redis 6.0+

### Installation

```bash
# Clone the repository
git clone https://github.com/fastapi-practices/fastapi_best_architecture.git
cd fastapi_best_architecture

# Setup environment
cp .env.example .env
# Edit .env with your configuration

# Install dependencies
pip install -r requirements.txt

# Initialize database
alembic upgrade head

# Start the server
python cli.py run
```

### 🐳 Docker Deployment

```bash
# Quick start with docker-compose
docker-compose up -d
```

---

## 🌟 Core Features

### 🎯 **Developer Experience**
- **Type Safety**: Full Pydantic v2 integration
- **Auto Documentation**: Interactive Swagger/ReDoc
- **Code Generation**: Automated CRUD operations
- **Hot Reload**: Lightning-fast development

### 🔒 **Security First**
- **JWT Authentication**: Stateless & scalable
- **RBAC Authorization**: Role-based access control
- **Data Encryption**: Multi-layer protection
- **CORS Management**: Cross-origin security

### 📈 **Performance Optimized**
- **Async/Await**: Non-blocking I/O operations
- **Connection Pooling**: Database optimization
- **Redis Caching**: Lightning-fast responses
- **Load Balancing**: Horizontal scalability

### 🛠️ **DevOps Ready**
- **Docker Support**: Containerized deployment
- **Health Checks**: System monitoring
- **Logging**: Structured & searchable
- **Metrics**: Performance analytics

---

## 📁 Project Structure

```
fastapi_best_architecture/
├── 🏠 backend/                 # Core backend application
│   ├── 📱 app/                 # Application modules
│   │   ├── 👥 admin/           # Admin management
│   │   ├── ☁️ coulddrive/      # Cloud drive integration
│   │   └── ⚡ task/            # Task management
│   ├── 🔌 plugin/              # Plugin ecosystem
│   ├── 🛠️ common/              # Shared utilities
│   ├── ⚙️ core/                # Core configurations
│   └── 🗃️ database/            # Database connections
├── 🎨 frontend/                # Modern web interface
└── 🚀 deploy/                  # Deployment configurations
```

---

## 🔧 Advanced Configuration

### Plugin Development
```python
# plugin.toml
[plugin]
summary = "My Awesome Plugin"
version = "1.0.0"
description = "Description of what this plugin does"
author = "Your Name"

[app]
extend = "admin"  # Extend existing app

[api.my_feature]
prefix = "/my-feature"
tags = "My Feature API"
```

### Cloud Drive Integration
```python
from backend.app.coulddrive.service.yp_service import BaseDrive

# Initialize drive manager
drive = BaseDrive()

# List files from Baidu NetDisk
files = await drive.get_disk_list(
    x_token="your_token",
    params=ListFilesParam(
        drive_type="BaiduDrive",
        file_path="/",
        recursive=True
    )
)
```

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
ruff format .

# Type checking
mypy .
```

---

## 📚 Documentation

For comprehensive documentation, visit our [Official Docs](https://fastapi-practices.github.io/fastapi_best_architecture_docs/)

### Quick Links
- 🚀 [Getting Started](https://fastapi-practices.github.io/fastapi_best_architecture_docs/getting-started/)
- 🔌 [Plugin Development](https://fastapi-practices.github.io/fastapi_best_architecture_docs/plugins/)
- ☁️ [Cloud Integration](https://fastapi-practices.github.io/fastapi_best_architecture_docs/cloud-drives/)
- 🔐 [Authentication](https://fastapi-practices.github.io/fastapi_best_architecture_docs/auth/)

---

## 🏆 Contributors

<a href="https://github.com/fastapi-practices/fastapi_best_architecture/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=fastapi-practices/fastapi_best_architecture"/>
</a>

---

## 🙏 Special Thanks

- [FastAPI](https://fastapi.tiangolo.com/) - The foundation of our architecture
- [Pydantic](https://docs.pydantic.dev/latest/) - Data validation & serialization
- [SQLAlchemy](https://docs.sqlalchemy.org/en/20/) - The Python SQL toolkit
- [Casbin](https://casbin.org/) - Authorization library
- [Ruff](https://beta.ruff.rs/docs/) - Lightning-fast Python linter

---

## 💬 Community

Join our vibrant community:

- 💬 [Discord Server](https://discord.com/invite/yNN3wTbVAC)
- 🐛 [Issue Tracker](https://github.com/fastapi-practices/fastapi_best_architecture/issues)
- 💡 [Feature Requests](https://github.com/fastapi-practices/fastapi_best_architecture/discussions)

---

## ☕ Support Us

If this project has helped you, consider supporting us:

[:coffee: **Sponsor Us** :coffee:](https://wu-clan.github.io/sponsor/)

Your support helps us maintain and improve this project!

---

## 📄 License

This project is licensed under the [MIT License](https://github.com/fastapi-practices/fastapi_best_architecture/blob/master/LICENSE).

---

<div align="center">

**⭐ Star us on GitHub — it motivates us a lot!**

[![Stargazers over time](https://starchart.cc/fastapi-practices/fastapi_best_architecture.svg?variant=adaptive)](https://starchart.cc/fastapi-practices/fastapi_best_architecture)

</div>
