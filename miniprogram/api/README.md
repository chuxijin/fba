# API 使用说明

## 📁 目录结构

```
api/
├── index.ts          # 统一出口
├── types.ts          # 通用类型定义
├── request.ts        # 请求封装（拦截器、Token 管理）
├── auth.ts           # 认证相关 API
└── README.md         # 使用说明（本文件）
```

---

## 🚀 快速开始

### 1. 基础配置

在 `request.ts` 中修改 `baseURL`：

```typescript
const config = {
  baseURL: import.meta.env.DEV
    ? 'http://127.0.0.1:8000'           // 开发环境
    : 'https://your-api-domain.com',    // 生产环境
}
```

### 2. 使用示例

#### 方式一：通过模块导入（推荐）

```typescript
import { authApi, setToken } from '@/api'

// 测试登录
async function handleLogin() {
  try {
    const res = await authApi.testLogin({
      username: 'test_user',
      nickname: '测试用户'
    })

    // 保存 Token
    setToken(res.access_token)

    console.log('登录成功', res.user_info)
  } catch (error) {
    console.error('登录失败', error)
  }
}
```

#### 方式二：直接导入方法

```typescript
import { testLogin } from '@/api/auth'
import { setToken } from '@/api'

const res = await testLogin({ username: 'test' })
setToken(res.access_token)
```

#### 方式三：使用基础 request 方法

```typescript
import { get, post } from '@/api'

// GET 请求
const data = await get('/api/v1/qbank/banks', {
  category: 1,
  page: 1
})

// POST 请求
const result = await post('/api/v1/qbank/answers/submit', {
  questionId: '123',
  userAnswer: 'C'
}, {
  showLoading: true,
  loadingText: '提交中...'
})
```

---

## 🔧 请求配置项

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | `string` | - | 请求地址（必填） |
| `method` | `HttpMethod` | `'GET'` | 请求方法 |
| `data` | `any` | - | 请求体数据（POST/PUT） |
| `params` | `Record<string, any>` | - | URL 查询参数（GET） |
| `header` | `Record<string, string>` | `{}` | 自定义请求头 |
| `timeout` | `number` | `10000` | 超时时间（毫秒） |
| `needToken` | `boolean` | `true` | 是否需要 Token |
| `showLoading` | `boolean` | `false` | 是否显示 loading |
| `loadingText` | `string` | `'加载中...'` | loading 提示文字 |

---

## 📝 创建新的 API 模块

### 1. 创建 API 文件（如 `bank.ts`）

```typescript
import { get, post } from './request'
import type { PageData } from './types'

/** 题库信息 */
export interface Bank {
  id: string
  name: string
  description: string
  totalQuestions: number
}

/** 获取推荐题库 */
export function getRecommendedBanks(limit: number = 3) {
  return get<Bank[]>('/api/v1/qbank/banks/recommended', { limit })
}

/** 获取题库详情 */
export function getBankDetail(id: string) {
  return get<Bank>(`/api/v1/qbank/banks/${id}`)
}

export default {
  getRecommendedBanks,
  getBankDetail,
}
```

### 2. 在 `index.ts` 中注册

```typescript
export * as bankApi from './bank'
```

### 3. 使用

```typescript
import { bankApi } from '@/api'

const banks = await bankApi.getRecommendedBanks(3)
```

---

## 🔐 Token 管理

```typescript
import { setToken, clearToken } from '@/api'

// 登录后保存 Token
setToken('your-access-token')

// 退出登录清除 Token
clearToken()

// Token 会自动添加到请求头：
// Authorization: Bearer your-access-token
```

---

## ⚠️ 错误处理

请求封装已经内置了错误处理：

- **401**: 自动清除 Token，跳转登录页
- **403**: 提示"暂无权限访问"
- **404**: 提示"请求的资源不存在"
- **500**: 提示"服务器错误，请稍后重试"
- **网络错误**: 自动识别超时、断网等情况

你也可以手动捕获错误：

```typescript
try {
  const data = await authApi.testLogin(params)
} catch (error) {
  // 自定义错误处理
  console.error('请求失败', error)
}
```

---

## 📦 后端响应格式

后端需要返回以下标准格式：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    // 实际数据
  }
}
```

---

## 🧪 测试步骤

### 1. 确保后端服务启动

```bash
cd D:\100-Work\101_Programming\Projs\01.python_projs\fastapi_best_architecture
python backend/app/main.py
```

### 2. 在小程序页面中调用

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { authApi, setToken } from '@/api'

onMounted(async () => {
  try {
    // 测试登录
    const res = await authApi.testLogin({
      username: 'test_user',
      nickname: '测试用户'
    })

    // 保存 Token
    setToken(res.access_token)

    console.log('登录成功:', res.user_info)

    uni.showToast({
      title: '登录成功',
      icon: 'success'
    })
  } catch (error) {
    console.error('登录失败:', error)
  }
})
</script>
```

---

## 🎯 下一步

1. ✅ 基础请求封装完成
2. ✅ 认证 API 完成
3. ⬜ 创建 `user.ts` - 用户相关 API
4. ⬜ 创建 `bank.ts` - 题库相关 API
5. ⬜ 创建 `question.ts` - 题目相关 API
6. ⬜ 创建 `answer.ts` - 答题相关 API

---

## 💡 提示

- 开发环境会自动使用 `http://127.0.0.1:8000`
- 生产环境需要修改 `request.ts` 中的 `baseURL`
- 所有请求默认携带 Token（除非设置 `needToken: false`）
- 可以通过 `showLoading: true` 显示加载提示
