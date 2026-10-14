# 开放平台授权中心（OpenAuth）

为第三方 Skill、CLI 和外部工具提供用户授权能力，支持授权码与 PKCE、权限校验、令牌刷新、设备退出和应用解绑

与负责第三方账号登录的 `oauth2` 插件不同，本插件让你的系统作为授权服务器，为外部程序签发受控凭据

## 插件类型

- 应用级插件

## 配置说明

插件目录下 `plugin.toml` 的 `[settings]` 中包含以下内容：

```toml
[settings]
OPENAUTH_CODE_EXPIRE_SECONDS = 300
OPENAUTH_ACCESS_TOKEN_EXPIRE_SECONDS = 7200
OPENAUTH_REFRESH_TOKEN_EXPIRE_SECONDS = 2592000
```

## 配置项说明

- `OPENAUTH_CODE_EXPIRE_SECONDS`：一次性授权码的有效时长
- `OPENAUTH_ACCESS_TOKEN_EXPIRE_SECONDS`：访问令牌的有效时长
- `OPENAUTH_REFRESH_TOKEN_EXPIRE_SECONDS`：刷新令牌与设备会话的有效时长

## 使用方式

1. 核对数据库迁移状态，选择项目迁移或插件安装脚本初始化开放平台表
2. 为外部程序注册客户端、回调地址与最小权限，公开分发的 CLI 使用公开客户端与 PKCE
3. 用户在站内登录并确认授权后，由外部程序完成换票、保存凭据与自动刷新
4. 业务服务端通过开放平台鉴权依赖检查身份与权限，不依赖 CLI 的自检结果
5. 接入前阅读 [当前进度与接入交接](docs/integration.md)，其中记录了数据库现状、接口契约与尚未完成的前端和 Skill 工作

## 卸载说明

- 先停止客户端与业务接入，移除相关授权入口和鉴权依赖
- 清理本插件配置、授权数据与临时凭据，不删除旧版 Skill 模块的数据

## 联系方式

- 作者：`fba`
- 反馈方式：提交 Issue 或 PR
