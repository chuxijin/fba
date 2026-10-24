# 站内登录会话策略

## 规则

- 普通账号：`账号 ID + 客户端类型` 下最多一个有效会话。新登录替换该端旧会话，其他端继续使用。
- `sys_user.is_multi_login=true`：允许同端多会话，不设会话数量上限。管理界面显示为「允许同端多会话」。
- 关闭例外时，各端保留最新会话；管理员修改自己时，自己所在端优先保留当前会话。
- 端类型仅有 `admin`、`web`、`miniapp`、`extension`。浏览器品牌、操作系统、登录方式、标签页都不增加类型。
- 同一浏览器的标签页复用已有会话。管理端登录要求账号具备 `is_staff` 权限。
- 付费权益和额度仍按账号累计；放开登录会话数量不增加额度或后台权限。

## 登录与刷新

密码、短信、订单号登录通过 `X-Client-Type` 提交类型。没有标识的旧密码客户端按 `web` 处理，非法类型拒绝。
微信小程序登录固定为 `miniapp`；小程序代码的 H5 运行形态使用 `web`。
第三方 OAuth 回调使用发起授权时保存在服务端 state 的类型。

JWT 中包含已签名的 `client_type` 与 `session_uuid`。刷新只轮换令牌，保持这两个字段，不执行新登录替换。
Redis 写操作（登录、刷新、撤销、策略收紧）共用账号级分布式锁，防止并发产生多个同端会话或使已撤销会话复活。

浏览器与小程序的刷新 Cookie 分别命名：

| 客户端 | Cookie |
| --- | --- |
| 管理端 | `fba_refresh_token_admin` |
| 网页端 | `fba_refresh_token_web` |
| 小程序端 | `fba_refresh_token_miniapp` |
| 插件端 | `fba_refresh_token_extension` |

浏览器使用 HttpOnly Cookie；插件登录与刷新响应额外返回 `refresh_token`，保存在扩展本地存储中，通过 JSON 请求体刷新。
刷新调用携带原访问令牌（可过期）或 `X-Session-ID`，后端校验它与刷新凭据属于同一会话，避免 Cookie 覆盖导致串号。
旧标签页发起退出时，仅撤销其指定会话，并且只删除与它匹配的 Cookie。

## 扫码登录

1. 发起电脑扫码时，保存目标端类型与发起端信息。
2. 手机确认只验证微信身份，按场景中保存的目标端签发会话。
3. 目标端在轮询领取结果时取得自己的刷新 Cookie；手机确认响应不携带电脑端 Cookie。
4. 结果只领取一次，类型不匹配的轮询不能消耗结果。重复手机确认不重复创建会话。

## 官网与插件

官网已有登录可以调用 `POST /api/v1/auth/extension-session` 为插件签发独立会话。
来源必须是有效的 `web` 会话，目标固定为 `extension`，不能换取后台会话。

桥接 v4 使用 `fba-site-auth-v2` 消息通道：

- 官网向插件提供自己的有效会话作为换票依据；插件使用后端签发的独立插件令牌。
- 插件不把访问/刷新凭据回传给官网；插件登录不会覆盖官网账号。
- 官网退出和插件退出独立。官网退出可以取消尚未完成的换票。
- 按来源 `session_uuid` 去重。官网 access token 的正常刷新不会创建新插件会话。
- 插件被踢或主动退出后，同一个官网会话的被动握手不会自动抢回名额。插件显式登录或官网新登录可重新建立会话。
- 现有桥接信任域名由 `extension/src/utils/auth-protocol.ts` 管理。

## 升级兼容

无需数据库迁移。新后端与四端客户端应配套更新，浏览器页面和插件重新加载后生效。
`frontend/`、`mini/` 是独立仓库；`web/` 当前被根仓库忽略，发布时需一并包含官网本地改动。
旧 JWT 没有可信端类型，不能通过刷新猜测/更换类型，需重新登录一次。
受限制账号新登录时会清理无法归类的旧版正式会话。生产环境直接拒绝没有端类型的旧版 JWT。
Swagger 调试登录仅限开发/测试环境的管理员；调试会话继续独立，不占各端名额，生产环境无法通过调试登录绕过限制。
重置密码、删除账号等账号级撤销仍影响所有端。

## 回归检查

```text
uv run --no-sync pytest --noconftest backend/common/tests/test_client_sessions.py backend/plugin/render_book/tests/test_public_auth_service.py -q
cd extension && pnpm test
cd mini && pnpm test:api
```

后端回归使用内存 Redis 替身与真实令牌签名/校验逻辑，覆盖同端替换、跨端共存、例外收紧、并发登录、刷新/退出竞争、旧版迁移、扫码及独立换票。

### 本轮验证记录（2026-10-23）

- 后端会话、公开接口鉴权与微信昵称回归：27 项通过；相关 Python 文件 Ruff 通过；认证路由与 OpenAPI Schema 可正常生成。
- 插件与官网桥接：50 项通过；插件 TypeScript 检查通过。
- 管理端 TypeScript 检查通过。定向 ESLint 需指定 `--parser-options '{"project":"./tsconfig.json"}'`，现有默认配置只匹配 `tsconfig.*.json`，未包含应用主配置。
- 小程序 HTTP 回归：17 项通过；其余一项为既有接口样本清单滞后（实际 177 个导出，fixture 为 174 个），本次未增减小程序 API 导出。
- 小程序全量类型检查仍报 `PageSkeleton.vue` 的 `vocabulary-home` 比较以及 Wot UI `useUpload.ts` 的类型错误。
- 官网定向类型检查仍受申论组件 `AnnotationCompare.vue`、`MaterialTabsBar.vue` 的空值类型错误及现有 Volar 插件解析提示影响；BFF 服务端定向类型检查通过。
- 本轮是本地代码、单元/契约验证；真实微信扫码与各端实际设备联调需在配套更新后验收。
