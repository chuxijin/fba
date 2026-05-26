# SDK 同步流程

后端 OpenAPI → SDK 自动生成的端到端流程,**改完后端跑一条命令就完事**。

## 一键命令

```bash
cd packages/api-sdk
npm run gen
```

内部串行执行三步:

| 步骤 | 命令 | 产物 |
|---|---|---|
| 1. dump | `python ../../backend/scripts/dump_openapi.py` | `packages/api-sdk/openapi.json` |
| 2. codegen | `openapi-ts` (读 `openapi-ts.config.ts`) | `packages/api-sdk/src/generated/` |
| 3. build | `tsup` | `packages/api-sdk/dist/` |

完成后 `mini` / `youanshang` 通过 `link:` 协议**立即**看到新方法和类型,不需要 reinstall。

## 何时应该跑

- 后端**新增、删除、改动任何路由或 schema**
- 后端给某个路由加了 `Pydantic` 字段 / 改了入参类型
- 前端 IDE 出现"找不到方法"或"类型不匹配"红线
- CI 部署前(确保 dist 是最新)

> 不需要跑的情况:仅改后端业务逻辑、内部 service 实现,API 表面没变。

## 端到端校验链

```
后端改 schema
  └─ python dump_openapi.py
      └─ openapi.json  ← 包含 630 operations / 802 schemas
          └─ openapi-ts (hey-api)
              └─ src/generated/{sdk.gen.ts, types.gen.ts, client.gen.ts}
                  └─ tsup build → dist/
                      └─ mini/node_modules/@fba/api-sdk (symlink)
                          └─ vue-tsc 报错 / IDE 红线  ← 这就是"自动同步"
```

## 路径关键文件

| 路径 | 角色 |
|---|---|
| `backend/scripts/dump_openapi.py` | 不启服务器 dump openapi.json |
| `backend/utils/openapi.py:simplify_operation_ids` | 让 operation_id = endpoint 函数名 (snake_case) |
| `packages/api-sdk/openapi-ts.config.ts` | hey-api 配置(axios client + asClass:false) |
| `packages/api-sdk/src/runtime/axios.ts` | 跨端 setupSdk + ResponseModel 拆包 |
| `packages/api-sdk/src/generated/` | **自动生成,不要手改** |
| `packages/api-sdk/.gitignore 之外的 dist/` | 编译产物(此处也 gitignore) |
| `mini/src/api/sdk.ts` | 业务入口,导出 `api`(generated 别名)+ `unwrap` helper |

## 业务调用形态

统一走 generated SDK 方法 + 拆包后的 `data`:

```ts
import * as api from '@fba/api-sdk/generated'

// 1. 无参数
const { data: me } = await api.getCurrentUserMembership()

// 2. query 参数 (运行时透传, 类型按 generated XxxData)
const { data: list } = await api.getBankList({ query: { page: 1, size: 20 } })

// 3. path 参数
const { data: detail } = await api.qbankGetBank({ path: { pk: 123 } })

// 4. body 参数
const { data: result } = await api.qbankPracticeCreateSession({
  body: { practice_name: 'X' },
})

// 5. 取消请求
const ac = new AbortController()
const promise = api.getBankList({ query: { page: 1 }, signal: ac.signal })
ac.abort()  // promise reject CanceledError
```

> `runtime/axios.ts` 已自动拆 `ResponseModel`, 业务侧读 `.data` 直接拿到 `T`. 仍出现 `as any` 的位置通常是类型定义晚于运行时, 需要 `pnpm gen` 重新生成.

## mini / web 接入

### mini (`mini/src/api/sdk.ts` 已配好)

`setupSdk` 已在文件末尾自动调用,业务代码只需:
```ts
import { api, sdkReady } from '@/api/sdk'
// (sdkReady 是 Promise<void>; main.ts 启动时 `void sdkReady` 触发即可)
```

### youanshang (web)

复制 mini 的 `sdk.ts` 末尾 `setupSdk(...)` 那段,**去掉 `mpAdapter`**(浏览器原生 axios 即可):
```ts
import axios from 'axios'
import { setupSdk } from '@fba/api-sdk/runtime'

export const sdkReady = setupSdk({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  // adapter 不传 → 使用 axios 浏览器默认 adapter
  getToken: () => useAuthStore().token,
  onUnauthorized: () => router.push('/login'),
}).then(() => undefined)
```

## CI 守护(推荐)

`.github/workflows/sdk-sync.yml`:

```yaml
- name: Verify SDK in sync with backend
  run: |
    cd packages/api-sdk
    npm run gen
    git diff --exit-code openapi.json src/generated/ \
      || (echo "SDK out of sync — run 'npm run gen' locally and commit" && exit 1)
```

> 注意:`openapi.json` 和 `src/generated/` 在 `.gitignore` 里,所以 CI 用法是先 unignore + commit,或者保留 ignore 但确保 dist build 成功不报 type 错。

## 故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| `dump_openapi.py` ImportError | venv 不对或后端依赖未装 | `cd .. && uv sync` 或 `pip install -e .` |
| `openapi-ts` 报 schema 错 | openapi.json 损坏或后端 schema 不规范 | 重跑 `npm run gen:openapi`;后端用 Pydantic v2 标准写法 |
| `tsup` build 报 TS 错 | runtime/axios.ts 与 generated 类型对不上 | 看是不是 `@hey-api/client-axios` 升级了 API,对照 `client.gen.ts` 调整 runtime |
| mini 看不到新方法 | `link:` 协议没生效 / mini 装的还是 file: 拷贝 | `cd mini && pnpm install` 重新建立 link |
| mini 报 `Cannot find module '@fba/api-sdk/generated'` | SDK 没 build | `cd packages/api-sdk && npm run build` |

## 遗留历史接口迁移状态

✅ **全量迁移完毕**。当前小程序端所有业务组件、页面均使用基于 `hey-api` 的统一方案。

对于**后端确切没有 OpenAPI 路由注册**（或者非标写法无法生成规范 schema）的接口（Ghost Routes），我们在 `mini/src/api/sdk.ts` 末尾单独暴露了专门的对象，以便在补齐后端路由前能够继续使用：

| 独立暴露接口 | 对应后端路由 |
|---|---|
| `authApi.wxLogin` | `/api/v1/oauth2/wechat/miniapp/login` |
| `renderBookApi.*` | `/api/v1/render-books/*` |
