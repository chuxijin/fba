# 前端任务交接文档

> **使用约定**：本文件是给前端同事的"任务包"。每次新任务覆盖式重写整份文档；当前任务以下方"当前任务"为准，历史任务不保留。

---

## 当前任务：小程序端渲染"资源"模块

**版本**：v1
**更新时间**：2026-06-16
**负责后端 / 数据契约**：null（已落地，可联调）
**负责前端实现**：（待同事填）

---

## 0. 背景一句话

学习计划新增了一种 `module_type='resource'` 的模块类型，承载网盘链接（百度/夸克/阿里/微云等）。后端、管理端、数据库 CHECK 约束都已就位，**只剩小程序学员端的渲染部分**。

学员路径：今日学习页看到"资源"卡片 → 点击 → 弹出抽屉看到链接列表 → 复制链接到浏览器打开 → 点击"我已查阅"完成模块。

---

## 1. 后端契约（已就位，无需改动）

### 1.1 启动接口

```http
POST /api/v1/study/student/items/{item_id}/start
Authorization: Bearer <token>
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "item_id": 123,
    "status": "in_progress",
    "payload": {
      "cloud_links": [
        {
          "title": "行程问题讲义",
          "url": "https://pan.baidu.com/s/1xxx",
          "password": "8x9k",
          "provider": "baidu"
        }
      ],
      "empty_hint": null
    }
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `cloud_links` | `CloudLink[]` | 资源链接数组，可能为空 |
| `cloud_links[].title` | `string` | 链接标题，必有 |
| `cloud_links[].url` | `string` | 链接 URL，必有 |
| `cloud_links[].password` | `string?` | 提取码，可能缺失/空 |
| `cloud_links[].provider` | `'baidu' \| 'quark' \| 'aliyun' \| 'weiyun' \| 'other' \| undefined` | 网盘类型 |
| `empty_hint` | `string \| null` | 资源未配置时返回 `"该资源模块尚未配置链接"`，否则为 `null` |

### 1.2 完成接口

```http
POST /api/v1/study/student/items/{item_id}/complete
Content-Type: application/json

{
  "duration_seconds": 150,
  "read_acknowledged": true
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `duration_seconds` | `number` | 实际查阅秒数（前端用 `Date.now()` 计算差值） |
| `read_acknowledged` | `true` | **必须传 `true`**，否则后端返回 `'请确认已查阅资源后再提交'` |

**响应**：

```json
{
  "code": 200,
  "data": {
    "id": 456,
    "item_id": 123,
    "user_id": 789,
    "duration_seconds": 150,
    "completed_at": "2026-06-16T10:23:45+08:00"
  }
}
```

### 1.3 错误处理

| 场景 | code | msg | 前端应对 |
|---|---|---|---|
| `read_acknowledged !== true` | 400 | "请确认已查阅资源后再提交" | toast 提示 |
| item 已完成 | 400 | "该模块已完成，无需重复提交" | toast + 关闭抽屉、刷新列表 |
| item 不存在/越权 | 404/403 | … | toast，关闭抽屉 |
| 网络异常 | - | - | 按钮恢复 disabled=false，toast "提交失败，请重试" |

---

## 2. UI 行为规约

### 2.1 入口位置

- 文件：`pages/study/today/index.vue`（今日学习页）
- 在卡片列表渲染分支里加：`v-if="item.module_type === 'resource'"` 时渲染 `<ResourceCard>`

### 2.2 资源卡片（ResourceCard.vue）

| 区域 | 内容 |
|---|---|
| 卡片左上 | 绿色 `wd-tag` "资源" |
| 卡片主标题 | `item.title` |
| 摘要行 | `"X 个网盘链接 · 预计 N 分钟"`（X 取 `item.extra.cloud_links.length`，N 取 `item.expected_minutes`） |
| 右侧状态 | 待开始（灰）/ 进行中（蓝）/ 已完成（绿）`wd-badge` |
| 整卡可点 | 调 `startItem` 接口 → 拿 `cloud_links` → 弹抽屉 |

### 2.3 资源抽屉（ResourceDrawer.vue）

用 `wd-popup position="bottom"`，高度约 70vh。

**抽屉头部**：模块标题 + 关闭按钮（`✕`）

**抽屉中部**（vertical scroll）：链接子卡片列表，每条结构：

```
┌────────────────────────────────────┐
│ 行程问题讲义  [百度网盘]         │ ← 标题 + provider 标签
│ pan.baidu.com                     │ ← 显示 host 而不是完整 URL
│ [📋 复制链接]                     │
│ 提取码：8x9k  [📋 复制提取码]    │ ← 仅在 password 存在时显示
└────────────────────────────────────┘
```

**抽屉底部固定栏**（`position: sticky; bottom: 0`）：

```
┌────────────────────────────────────┐
│ 已查阅 02:30        [✓ 我已查阅]  │
└────────────────────────────────────┘
```

- 左侧计时器：抽屉打开瞬间记 `startTime = Date.now()`，每秒刷新展示
- 右侧主按钮：`wd-button type="primary"`，点击调完成接口

**底部提示文案**（放在链接列表下方）：

> 复制后到浏览器粘贴打开

### 2.4 空态

当 `payload.cloud_links.length === 0`：

- 抽屉中部展示 `payload.empty_hint`（已经包含提示文案）
- 底部按钮改成"返回"，**不允许调用完成接口**（避免误标记完成）

---

## 3. 关键交互细节

| 项 | 规约 |
|---|---|
| 复制反馈 | 调 `uni.setClipboardData`，成功 toast "已复制"；失败 toast "复制失败，请手动选择" |
| 计时启动时机 | 抽屉**打开瞬间**记 `startTime`，完成时 `duration_seconds = Math.floor((Date.now() - startTime) / 1000)` |
| 防重复点击 | "我已查阅"按钮在请求未返回时 `loading=true && disabled=true` |
| 网络失败 | 抽屉不关、按钮恢复，toast 错误信息；**不自动重试** |
| 复制后是否自动完成 | **不要**自动完成。学员可能复制多个链接，自动完成会误结束 |
| 已完成后再次点卡片 | 仍允许打开抽屉查看链接，但底部按钮置灰显示"已完成"，复制功能照常 |
| URL 展示 | 只显示 `new URL(url).host`，完整 URL 在复制时给出（视觉降噪） |
| Provider 标签颜色 | baidu 蓝、quark 紫、aliyun 橙、weiyun 青、other/null 灰 |

### 3.1 ⚠️ 微信小程序限制提示

- 网盘域名（pan.baidu.com、pan.quark.cn 等）**不在业务域名白名单**，无法 `navigateTo` 或 `web-view` 打开
- 唯一可行的学员动作：**复制 → 切到浏览器粘贴**
- UI 必须明示"复制后到浏览器粘贴打开"，不要给"点击打开"按钮，否则学员点了没反应会以为坏了

### 3.2 不做的事（避免过度设计）

- **不做 QR 码渲染**：包体积成本高，学员长按文本就能在微信里粘贴
- **不做"是否真的复制了"埋点**：后端只校验 `read_acknowledged`，不监控行为
- **不做 web-view 嵌入**：会被白名单挡住，徒增报错

---

## 4. 数据流图

```
[学员点资源卡片]
        ↓
[POST /items/{id}/start]
        ↓
后端读 item.extra.cloud_links → 返回 payload
        ↓
[前端打开抽屉] startTime = Date.now()
        ↓
学员看链接、复制、切浏览器粘贴
        ↓
[学员点"我已查阅"]
        ↓
[POST /items/{id}/complete]
  body: { duration_seconds, read_acknowledged: true }
        ↓
后端 _check_resource 校验 read_acknowledged
        ↓
✅ 写 record + item.status = 'completed'
        ↓
[前端关抽屉，刷新今日页]

容错路径：
- start 接口 4xx → 不打开抽屉，toast 错误信息
- complete 接口 4xx → 抽屉不关，按钮恢复，toast 错误信息
- 网络超时 → 同上
```

---

## 5. 文件 / 位置指引

```
src/
├─ pages/study/today/index.vue
│    └─ 在 cardList 渲染时加 v-if="item.module_type === 'resource'" 分支
│       渲染 <ResourceCard :item="item" />
│
├─ components/study/ResourceCard.vue           ← 【新建】资源类型的卡片
│    └─ 点击事件触发抽屉打开 + 调 startItem 接口
│
├─ components/study/ResourceDrawer.vue         ← 【新建】底部抽屉
│    └─ props: { item, payload }
│       slots: 链接列表 + 完成按钮
│       emits: ['complete', 'close']
│
├─ api/study.ts
│    └─ 已有 startItem / completeItem
│       【需补类型】payload.cloud_links: CloudLink[]
│
└─ utils/clipboard.ts                          ← 复用现有的复制工具（无则新建）
```

### 5.1 类型补丁（直接复制进 `api/study.ts`）

```typescript
export type CloudLinkProvider = 'baidu' | 'quark' | 'aliyun' | 'weiyun' | 'other'

export interface CloudLink {
  title: string
  url: string
  password?: string
  provider?: CloudLinkProvider
}

export interface StartItemPayload {
  // 错题动态
  question_ids?: number[]
  // 题库 session
  session_key?: string
  // 通用空态提示
  empty_hint?: string | null
  // 资源模块
  cloud_links?: CloudLink[]
}

export interface StartItemResult {
  item_id: number
  status: 'pending' | 'in_progress' | 'completed' | 'skipped'
  payload?: StartItemPayload
}

export interface CompleteItemParam {
  duration_seconds: number
  // 资源 / 学习类必传 true
  read_acknowledged?: boolean
  // 刷题类
  score?: number
  correct_count?: number
  total_count?: number
  extra_data?: Record<string, unknown>
}
```

### 5.2 Provider 颜色映射工具（建议放 `components/study/resource-utils.ts`）

```typescript
import type { CloudLinkProvider } from '@/api/study'

export const PROVIDER_LABELS: Record<CloudLinkProvider, string> = {
  baidu: '百度网盘',
  quark: '夸克网盘',
  aliyun: '阿里云盘',
  weiyun: '腾讯微云',
  other: '其它',
}

export const PROVIDER_COLORS: Record<CloudLinkProvider, string> = {
  baidu: '#1677ff',
  quark: '#722ed1',
  aliyun: '#fa8c16',
  weiyun: '#13c2c2',
  other: '#8c8c8c',
}

export function getProviderLabel(provider?: string): string {
  if (provider && provider in PROVIDER_LABELS) {
    return PROVIDER_LABELS[provider as CloudLinkProvider]
  }
  return '网盘'
}

export function getProviderColor(provider?: string): string {
  if (provider && provider in PROVIDER_COLORS) {
    return PROVIDER_COLORS[provider as CloudLinkProvider]
  }
  return PROVIDER_COLORS.other
}

export function getHost(url: string): string {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}
```

---

## 6. 验收清单

### 6.1 正向 path

- [ ] 今日页能看到资源卡片，标签为绿色"资源"
- [ ] 点卡片能打开抽屉，看到正确数量的链接
- [ ] 每条链接的"复制链接"和"复制提取码"都能成功复制（uni-app toast 反馈）
- [ ] 计时器从打开抽屉开始走，秒级刷新
- [ ] 点"我已查阅"后抽屉关闭、卡片变"已完成"
- [ ] 今日页顶部 progress 数字 +1

### 6.2 反向 path

- [ ] 链接为空时，抽屉显示 `empty_hint` 文案，底部按钮为"返回"
- [ ] 网络断开时，"我已查阅"按钮 loading → 失败 toast → 按钮恢复 disabled=false
- [ ] 同一 item 重复点完成只触发一次 record（后端有幂等，前端别重发）
- [ ] 后端返回 `'该模块已完成'` 时，toast + 关闭抽屉 + 刷新

### 6.3 回归 path

- [ ] review / practice / wrong_review / ability 四种模块都不受影响
- [ ] 今日页计时器、未完成铃铛数字依然正确
- [ ] 已完成的 item 再次点击不会改变 record 数量

---

## 7. UI 草图（文字版参考）

```
┌──────────────────────────────────────┐
│  [✕]  复习资源·数量关系合集      │   ← 抽屉头部
├──────────────────────────────────────┤
│ ┌──────────────────────────────────┐ │
│ │ 行程问题讲义  [百度网盘]      │ │
│ │ pan.baidu.com                   │ │
│ │ [📋 复制链接]                   │ │
│ │ 提取码: 8x9k  [📋 复制提取码]  │ │
│ └──────────────────────────────────┘ │
│ ┌──────────────────────────────────┐ │
│ │ 工程问题答疑  [夸克网盘]      │ │
│ │ pan.quark.cn                    │ │
│ │ [📋 复制链接]                   │ │
│ │ （无提取码）                    │ │
│ └──────────────────────────────────┘ │
│                                      │
│  💡 复制后到浏览器粘贴打开        │
├──────────────────────────────────────┤
│ ⏱ 已查阅 02:30   [✓ 我已查阅 →]  │   ← 底部固定栏
└──────────────────────────────────────┘
```

---

## 8. 沟通约定

- 实现中如果对契约/UX 有疑问，请直接在群里 at null（不要私下脑补改）
- 后端任何字段变更会**先改文档再改代码**，本文件以后端为准
- 联调时遇到 500 / 400，直接把 `trace_id` 发给 null 排查日志
- 该功能后端已可联调（dev 环境），可立即开干
