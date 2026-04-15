# @fba/api-sdk

FBA 刷题系统多端统一 API SDK，供 Web / 小程序 / App 共用接口层。

## 特性

- **平台无关**：通过可注入的 `RequestAdapter` 适配任意 HTTP 客户端（Axios、wx.request、fetch 等）
- **类型安全**：所有请求/响应均有完整 TypeScript 类型定义，与后端 Pydantic Schema 对齐
- **统一响应处理**：自动拆包 `{ code, msg, data }`，业务错误抛出 `ApiError`
- **认证内置**：Token 自动注入、401 统一处理
- **模块化导入**：按需导入 `bank`、`material`、`question`、`practice` 模块
- **OpenAPI 同步**：一条命令从后端 OpenAPI 更新类型定义

## 快速开始

### 安装

```bash
# 项目内引用（monorepo）
pnpm add @fba/api-sdk

# 或通过路径引用
pnpm add ../../packages/api-sdk
```

### Web 端接入（Axios）

```typescript
import axios from 'axios';
import { createFbaApiSdk } from '@fba/api-sdk';

const sdk = createFbaApiSdk({
  baseURL: 'http://127.0.0.1:8000',
  adapter: {
    request: (config) =>
      axios({
        url: config.url,
        method: config.method,
        params: config.params,
        data: config.data,
        headers: config.headers,
        timeout: config.timeout,
      }).then((res) => res.data),
  },
  getToken: () => localStorage.getItem('access_token') ?? undefined,
  onUnauthorized: () => {
    // 跳转登录页
    window.location.href = '/login';
  },
});

// 使用
const banks = await sdk.bank.getList({ keyword: '行测' });
const detail = await sdk.material.getDetail(42);
```

### 小程序端接入（wx.request）

```typescript
import { createFbaApiSdk } from '@fba/api-sdk';

const sdk = createFbaApiSdk({
  baseURL: 'https://api.example.com',
  adapter: {
    request: <T>(config) =>
      new Promise<T>((resolve, reject) => {
        wx.request({
          url: config.url,
          method: config.method as WechatMiniprogram.RequestOption['method'],
          data: config.method === 'GET' ? config.params : config.data,
          header: config.headers,
          timeout: config.timeout,
          success: (res) => resolve(res.data as T),
          fail: reject,
        });
      }),
  },
  getToken: () => wx.getStorageSync('token') || undefined,
  onUnauthorized: () => {
    wx.navigateTo({ url: '/pages/login/index' });
  },
});

// 调用方式完全一致！
const banks = await sdk.bank.getList({ keyword: '行测' });
```

### 与现有 @vben/request 集成

如果 admin-web 已使用 `@vben/request`（内置 Axios 封装），可直接桥接：

```typescript
import { createFbaApiSdk } from '@fba/api-sdk';
import { baseRequestClient } from '#/api/request';

const sdk = createFbaApiSdk({
  baseURL: '',  // baseRequestClient 已配置 baseURL
  apiPrefix: '', // 同上
  adapter: {
    request: (config) =>
      baseRequestClient({
        url: config.url,
        method: config.method,
        params: config.params,
        data: config.data,
        headers: config.headers,
        timeout: config.timeout,
      }).then((res) => res.data),
  },
  getToken: () => {
    const { accessStore } = useAccessStore();
    return accessStore.accessToken || undefined;
  },
});
```

## API 模块一览

### `sdk.bank` — 题库

| 方法 | 说明 |
|------|------|
| `getRecommend()` | 获取推荐题库 |
| `getDetail(id)` | 获取题库详情（含章节树） |
| `getList(params?)` | 获取题库树形列表 |
| `getAllQuestions(bankId, params?)` | 获取题库所有题目（含答案） |
| `create(data)` | 创建题库 |
| `update(id, data)` | 更新题库 |
| `remove(ids)` | 删除题库 |

### `sdk.material` — 材料

| 方法 | 说明 |
|------|------|
| `getDetail(id)` | 获取材料详情 |
| `getList(params?)` | 获取材料列表 |
| `getByBank(bankId, params?)` | 获取指定题库的材料 |
| `create(data)` | 创建材料 |
| `update(id, data)` | 更新材料 |
| `remove(ids)` | 删除材料 |
| `linkQuestions(id, data)` | 关联题目 |
| `unlinkQuestions(id, data)` | 解除关联 |

### `sdk.question` — 题目

| 方法 | 说明 |
|------|------|
| `getDetail(id)` | 获取题目详情 |
| `getList(params?)` | 获取题目列表（分页） |
| `getCollections(params?)` | 按筛选条件获取题目合集/题库卡片 |
| `collect(data)` | 统一筛题，返回稳定 question_ids |
| `getAnalysis(id)` | 获取题目解析 |
| `getSolution(id, userAnswer?)` | 获取答案和解析 |
| `markAnalysisHelpful(id, bool)` | 标记解析是否有帮助 |
| `getStatistics(id)` | 获取题目统计 |
| `getOptionStats(id, params?)` | 获取选项统计 |
| `checkFavorites(ids)` | 批量检查收藏状态 |
| `getNotes(ids)` | 批量查询笔记 |
| `create(data)` | 创建题目 |
| `update(id, data)` | 更新题目 |
| `remove(ids)` | 删除题目 |
| `batchImport(data)` | 批量导入 |

统一筛题典型用法：

```typescript
const collections = await sdk.question.getCollections({
  cat_id: 12,
  region: '江苏',
  year_start: 2021,
  year_end: 2025,
  knowledge_names: ['资料分析', '判断推理'],
});

const collected = await sdk.question.collect({
  source_type: 'placement',
  cat_id: 12,
  region: '江苏',
  year_start: 2021,
  year_end: 2025,
  question_types: ['single'],
  difficulties: ['medium'],
  limit: 100,
});

const questionIds = collected.question_ids;
```

### `sdk.practice` — 刷题

| 方法 | 说明 |
|------|------|
| `getQuestions(params?)` | 获取练习题目 |
| `getQuestionsByBank(bankId, params?)` | 按题库获取练习题 |
| `getQuestionsByChapter(chapterId, params?)` | 按章节获取练习题 |
| `getQuestionDetail(id)` | 获取单题详情 |
| `getQuestionAnalysis(id)` | 查看题目解析 |

## 错误处理

SDK 提供三种错误类型：

```typescript
import { ApiError, UnauthorizedError, NetworkError } from '@fba/api-sdk';

try {
  const banks = await sdk.bank.getList();
} catch (err) {
  if (err instanceof UnauthorizedError) {
    // 401 认证失败
    console.log('请重新登录');
  } else if (err instanceof ApiError) {
    // 业务错误（code !== 200）
    console.log(`错误码: ${err.code}, 信息: ${err.msg}`);
  } else if (err instanceof NetworkError) {
    // 网络错误 / 超时
    console.log('网络异常', err.cause);
  }
}
```

## 类型导入

所有后端 Schema 类型均可按需导入：

```typescript
import type {
  GetBankDetail,
  GetQuestionListItem,
  QuestionType,
  Difficulty,
  SessionType,
} from '@fba/api-sdk';
```

## OpenAPI 类型同步

当后端接口变更后，运行以下命令自动更新类型：

```bash
cd packages/api-sdk

# 开发环境（默认 http://127.0.0.1:8000）
pnpm generate

# 指定地址
OPENAPI_URL=https://api.example.com/openapi.json pnpm generate
```

生成的类型位于 `src/types/__generated__.ts`，可在自定义类型中引用。

## 构建

```bash
cd packages/api-sdk
pnpm install
pnpm build        # 产出 dist/（ESM + CJS + .d.ts）
pnpm typecheck    # 类型检查
```
