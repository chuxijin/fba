# OpenAuth 当前进度与 Skill 接入交接

更新：2026-10-05

第三轮已按夸克式流程统一安装更新、欢迎语、login --token、get-user-info、unauthorize 和卸载，详见 [0.2.0 本地试用与交接](local-quickstart.md)。下文保留最初排查时的数据库状态与协议设计，当前使用方式以该交接文档和最新 Skill 为准。

## 结论

最初实现已经具备客户端、授权关系、授权码换票、刷新和解绑的骨架，但从 `backend/app/skill` 拆成 `backend/plugin/openauth` 的迁移没有完成。它当时还不是可直接交付的开放平台。

第一轮把 OpenAuth 收到“后端授权基础可测试”的阶段；第二轮已实现可本地试用的最小 Skill 链路，**不是生产 Skill 已上线**。未创建生产客户端、改生产配置、提交或推送 Git。

| 环节 | 检查时状态 | 本次收尾后 |
| --- | --- | --- |
| 模型、API、Service、CRUD | 已有骨架 | 已修复并增加回归测试 |
| 插件安装 | 缺雪花主键 SQL，启动校验失败；SQL 操作旧表 | 四份 PostgreSQL 脚本齐全，仅操作 `openauth_*` |
| 路由挂载 | 与旧模块有同名路由，阻止全局注册 | OpenAuth 路由名称加前缀隔离 |
| 数据写入 | 写接口只 flush，无事务提交 | 写接口使用事务依赖 |
| 公开 CLI 授权 | 需要分发共享 client_secret | 新增 public 客户端 + 强制 S256 PKCE |
| 安全边界 | 并发重复换票、刷新可能扩大权限、停用不生效 | 原子 GETDEL、权限取交集、检查应用/用户状态 |
| 撤销 | Redis 全局 KEYS 扫描，重新授权可能恢复旧凭据 | 授权代次隔离；整应用解绑和单设备退出分开 |
| 资源 API 鉴权 | 只有 CLI 自检，没有服务端依赖 | `RequireOpenAuth` 已保护最小账号资料接口，其他业务未开放 |
| 管理接口 | RBAC 无具体权限标识，查询只验登录 | 增加具体权限标识，列表不再暴露密钥哈希 |
| 凭据传输 | token、新密钥通过 URL 参数 | 改为 Bearer 或 JSON body，增加日志敏感字段脱敏 |
| 浏览器授权页 | 未找到接入实现 | 已接入用户网站，待真人登录验收 |
| CLI 与可安装 Skill 包 | 未找到实现 | 已完成本地版本和安装包 |

## 与夸克式 Skill 的对应关系

目标结构是：**Skill 文档 → 本地 CLI → 浏览器登录/用户确认 → OpenAuth → 受保护的业务 API**。

可借鉴夸克的安装脚本、`login`、自动刷新、业务子命令、JSON/NDJSON 输出和退出授权体验。不应照搬把共享密钥放进公开脚本的模式，也不需要默认上传用户原始对话作追踪。

OpenAuth 只负责授权，不负责生成 Skill，也不会把现有后台管理 API 自动变成开放 API。

## 数据库与旧模块：执行任何部署前先看这里

本次只读查询开发库得到：

- `skill_client`：存在，0 行
- `skill_user_authorization`：存在，0 行
- `openauth_*`：不存在
- `alembic_version`：`e4f5a6b7c8d9`
- 当前代码在收尾前的 Alembic head：`a1b2c3d4e5f7`

这意味着**数据库表和迁移版本记录并不完全同步**。旧 Skill 表已经存在，而创建它们的迁移可能尚未被版本表记录。不要未经核对就运行 `alembic upgrade head`，也不要盲目 stamp。

本次新增迁移 `b7c8d9e0f1a2`，接在 `a1b2c3d4e5f7` 后，仅创建 OpenAuth 的两张表，不复制、重命名或删除旧表。独立插件安装则使用 `sql/postgresql/init.sql` 或 `init_snowflake.sql`。**项目迁移和插件建表脚本二选一，不能重复建同一组表**。

部署步骤：

1. 备份，核对目标库实际结构和 `alembic current/history`，先解决历史版本不一致
2. 在隔离测试库执行建表、回滚及真实事务/Redis 联调，再按确定的安装路径部署
3. 注册一个最小权限的 public 测试客户端，完成浏览器 → CLI → 资源 API 的完整联调
4. 核查旧 `/skill` 接口的消费者；确认无依赖后，单独停用旧路由，再规划旧代码清理

本次保留了旧 `backend/app/skill`、其挂载、旧迁移和数据，未替它补安全修复。**不要将旧接口与新 OpenAuth 一并当成已加固服务直接暴露公网**。新旧 token、授权记录和 Redis 命名空间互不兼容，应让客户端重新授权。

依赖 PostgreSQL、Redis 6.2+（GETDEL），以及项目现有站内用户认证与签名配置。三个过期时间单位均为秒，必须为正数，修改后重启服务。

## 当前接口契约

前缀默认为 `/api/v1/openauth`，随项目 `FASTAPI_API_V1_PATH` 变化。采用项目 JSON 响应 `{code, msg, data}`，**不是可直接接入任意 OAuth SDK 的标准 form-urlencoded token endpoint**。不要宣称完整 OAuth/OIDC 兼容；目前没有 discovery、JWKS、设备码流程。

| 方法与路径 | 凭据 | 用途 |
| --- | --- | --- |
| `POST /authorize/preview` | 站内用户 JWT | 检查请求并展示客户端、权限、已有授权状态 |
| `POST /authorize` | 站内用户 JWT | 用户明确确认后签发授权码 |
| `GET /authorizations` | 站内用户 JWT | 当前用户的授权记录；不可指定他人 user_id |
| `POST /revoke` | 站内用户 JWT | 按 client_id 解绑当前用户的整个应用 |
| `POST /token` | PKCE；confidential 额外需要密钥 | 授权码换票 |
| `POST /refresh` | refresh_token；confidential 额外需要密钥 | 原子旋转刷新 |
| `POST /check` | OpenAuth Bearer | 身份与权限自检 |
| `POST /logout` | OpenAuth Bearer | 仅退出该 token 所属设备会话 |
| `POST /unauthorize` | OpenAuth Bearer | 为当前设备创建用户确认票据，不直接退出 |
| `POST /device-revoke/preview`、`POST /device-revoke` | 站内用户 JWT | 同一账号预览与确认设备解绑 |
| `GET /skill-config`、`GET /skill-package` | 公开 | 获取最新 Skill 配置与完整 ZIP |
| `GET /profile` | OpenAuth Bearer + profile:read | 仅返回当前账号的 ID、昵称、头像 |
| `/clients` 管理接口 | 站内 JWT + 专用 RBAC 权限 | 创建、查询、编辑、删除、重置密钥 |

### 注册公开客户端

管理员创建请求示例（scopes 是示意，必须与实际业务资源约定一致）：

```json
{
  "name": "公考助手 CLI",
  "client_type": "public",
  "scopes": ["profile:read"],
  "redirect_uris": ["http://127.0.0.1:17888/callback"]
}
```

返回的 `client_id` 可以放在公开 CLI 中，`client_secret` 为 null。confidential 客户端仅用于能够保密的服务端；默认随机生成密钥，只在创建/重置响应出现。客户端类型创建后不能通过更新接口切换。

回调地址精确匹配，包括端口与路径；不要使用通配符。目前未实现 RFC 8252 动态 loopback 端口匹配，CLI 应使用预注册固定本机地址，并在端口占用时明确提示。

### 浏览器授权与 PKCE

1. CLI 生成随机 `state`（至少 16 字符）和 `code_verifier`（43–128 字符）；计算 `BASE64URL(SHA256(verifier))`，去掉 `=` 得到 challenge
2. CLI 仅监听本机回调，打开站内 `/openauth/authorize`，查询参数传 client_id、scope（空格分隔）、redirect_uri、state、code_challenge、code_challenge_method=S256；页面再转成后端 scopes 数组
3. 前端完成站内登录，保留原授权参数，先调用 preview，再让用户确认应用与权限
4. 用户确认后调用 authorize，按返回的 redirect_uri 构造 URL，加入 code 和 state；取消时不签发 code
5. CLI 严格验证回调的 state，使用本地保存的 verifier 换票，成功/取消/超时后关闭监听并清理待授权状态

不要仅因为 `already_authorized=true` 就在页面加载时无提示授权；新增 scope 必须重新确认。不要让 Agent 代替用户点击同意授权。

换票请求：

```json
{
  "client_id": "管理员实际创建后返回的标识",
  "code": "回调返回的授权码",
  "redirect_uri": "http://127.0.0.1:17888/callback",
  "code_verifier": "CLI 本次登录开始时生成并保留的 verifier"
}
```

返回 `access_token`、`refresh_token`、`token_type=Bearer`、`expires_in`。授权码默认 5 分钟有效且只能成功消费一次。

### 刷新、退出和解绑

- access_token 默认 2 小时，refresh_token 默认 30 天；刷新成功后必须原子保存整对新 token
- CLI 对同一账号的刷新应使用进程间锁，禁止多个命令并行复用一个 refresh_token
- 刷新仅保留“原凭据 scopes ∩ 当前用户授权 scopes ∩ 当前客户端 scopes”，不会自动获得后来新增的权限
- `check`、`logout` 只接受 `Authorization: Bearer ...`，不接受 URL 中的 token
- `logout` 使一个设备会话的 access/refresh 全部失效，不影响其他设备；签名有效但已过期的 token 仅允许用于退出，不触发刷新。默认仅供卸载内部使用，普通用户退出使用 unauthorize 网页确认
- `revoke` 请求体只有 `{"client_id":"..."}`，使整个应用的旧 code/access/refresh 失效；重新授权也不会复活旧凭据
- 被撤销的 Redis 凭据按原 TTL 自然过期，数据库授权代次和设备会话是判定是否可用的依据，不执行 Redis 全库扫描
- 不在终端、对话、日志、截图或版本库中输出 token/secret/verifier；CLI 凭据保存到用户级受限目录，不能放在 Skill 包中
- 自动回调验证 state 与 PKCE；手动 `login --token` 接收 code，但必须使用同一本机待授权流程保留的 verifier，通过服务端验证绑定。没有前置待授权会话不能换票

## 业务接口接入：必须在服务端校验

```python
from typing import Annotated
from fastapi import Depends
from backend.plugin.openauth.dependencies import RequireOpenAuth
from backend.plugin.openauth.schema.authorization import GetOpenAuthCheckResult


# 用于专门的开放资源路由，不要把它叠加在要求站内 JWT 的管理接口上
async def resource_example(
    identity: Annotated[GetOpenAuthCheckResult, Depends(RequireOpenAuth('profile:read'))],
):
    # 用 identity.user_id 绑定数据归属；仍需执行业务权限、会员权益、配额等检查
    ...
```

还需在该资源所属插件的 setup 中，将**明确列举的资源路径**加入 `settings.TOKEN_REQUEST_PATH_EXCLUDE`，避免全局站内 JWT 中间件抢先拒绝 OpenAuth token；这只是绕过站内 JWT，不能省略 `RequireOpenAuth`。动态路径使用有起止锚点的精确正则。不要把整个业务或后台路由前缀加入白名单。

OpenAuth 自己仅为 check/logout/profile/unauthorize 做了上述设置。它的 authorize、revoke、device-revoke 和客户端管理仍使用站内 JWT。鉴权依赖返回的 `identity` 是第三方身份，不会将 `request.user` 自动提升成管理员。

待接入第一个真实业务 API 时，必须验证：允许自己的数据，拒绝他人数据，拒绝缺 scope、禁用用户、解绑授权和过期会话。scope 不是会员资格，也不是原站内权限的替代品。

## 管理台后续工作

用户网站已完成授权确认页与授权管理页；管理后台客户端 CRUD 页尚未完成。客户端管理对应权限标识：

- `openauth:client:add`
- `openauth:client:edit`
- `openauth:client:delete`
- `openauth:client:secret`
- `openauth:client:view`
- `openauth:client:list`

应通过现有菜单/角色配置分配权限；本次未自动写入菜单表。重置密钥使用 JSON `{"new_secret":"..."}` 或 `{}` 由服务端生成，不能通过 URL 传密钥。

## 验证与交付边界

第一轮历史验证结果：49 项隔离测试通过、注册 14 个 OpenAuth 操作；新增迁移升级与回滚 SQL 可离线生成。本轮 0.2.0 的测试计数、接口增加与本地安装链路验证结果见 local-quickstart.md。

隔离测试命令（项目根目录执行，不连接真实数据库或 Redis）：

```powershell
uv run --no-sync pytest --confcutdir=backend/plugin/openauth/tests backend/plugin/openauth/tests -q
uv run --no-sync ruff check backend/plugin/openauth
```

测试覆盖：公开/机密客户端、PKCE 标准向量、错误请求不消耗 code、并发换票和刷新、scope 不升级、禁用应用/用户、撤销后不恢复、设备退出隔离、JWT 用途隔离、真实 FastAPI 事务依赖和 RBAC、Bearer 中间件兼容、SQL 与模型列的一致性。

这些测试不能替代真实 PostgreSQL/Redis 事务联调和浏览器授权验收。正式公网接入前还需配置网关限流、HTTPS/CORS、日志保留和审计策略，并测试异常网络、刷新响应丢失、撤销与换票并发以及 Redis 故障恢复。

额外发现：整个项目调用 `app.openapi()` 仍被非 OpenAuth 的 `ResponseSchemaModel[GetKnowledgeMasteryRadar]` 类型未完整定义错误阻断；OpenAuth 的独立 OpenAPI 已通过路由测试。本次未越界修改该业务模块。项目现有 uv 虚拟环境实际使用 Python 3.14.2，以上测试基于该环境，不代表已在全局 Python 3.12.12 上验证。

第二轮之后的下一步：**真人登录验收 → 确定正式域名和生产客户端 → 核对历史迁移并部署 → 扩展一个真实业务能力**。不要一开始就同时开放全部后台业务接口。
