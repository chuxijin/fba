# 番茄 Todo 集成方案

## 1. 背景与目标

本文档用于指导在当前系统中集成类似“番茄 ToDo”的专注任务能力，重点覆盖微信小程序场景和 FastAPI 后端实现。

本功能不包含锁机、防沉迷强制管控、系统级应用限制等能力。微信小程序不适合实现系统级锁机，当前方案只做任务管理、番茄专注、习惯打卡、提醒和统计。

## 2. 实施进度

最后更新：2026-06-30

### 2.1 已完成

- [x] 后端新增 `pomodoro` 模块
- [x] 后端任务模型、schema、CRUD、service、API
- [x] 后端专注记录模型、schema、CRUD、service、API
- [x] 后端习惯模型、习惯打卡模型、schema、CRUD、service、API
- [x] 后端用户专注设置模型、schema、CRUD、service、API
- [x] 后端休息会话模型、schema、CRUD、service、API
- [x] 后端重复任务实例生成能力
- [x] 后端今日统计接口
- [x] 后端周统计、月统计、日历统计接口
- [x] 后端每日 / 每周专注目标字段和统计进度
- [x] 后端成就规则表、用户成就领取记录表、schema、CRUD、service、API
- [x] 后端成就评估：累计专注小时数、连续专注天数、连续习惯打卡天数、完成番茄数量
- [x] 后端排行榜接口：今日专注榜、本周专注榜、全站范围、Redis 排名缓存
- [x] 后端白噪音预设接口：雨声、咖啡厅、白噪音
- [x] 背景音偏好复用番茄设置字段 `sound_enabled` / `background_sound`
- [x] 小程序新增本地背景音播放 composable，支持预设切换、播放、暂停、停止、销毁
- [x] 后端路由注册到 `backend/app/router.py`
- [x] OpenAPI 工具兼容 FastAPI 延迟路由，保证 SDK 方法名稳定
- [x] SDK 已通过 OpenAPI 生成番茄相关接口方法
- [x] 小程序新增 `mini/src/api/pomodoro.ts`，统一通过 `@fba/api-sdk` 调用接口
- [x] 小程序 SDK 包装新增成就、排行榜、白噪音接口方法
- [x] 编写集成方案文档

### 2.2 已验证

- [x] `uv run python -m py_compile ...` 通过
- [x] `uv run python backend/scripts/dump_openapi.py` 通过
- [x] `pnpm --filter @fba/api-sdk run gen:sdk` 通过
- [x] `pnpm --filter @fba/api-sdk run build` 通过
- [ ] `pnpm --dir mini run type-check` 未通过，阻断点为既有 `wrong-review` / `QuestionNotePanel` 类型问题，非本次番茄模块新增错误
- [ ] `pnpm --dir mini run build:mp` 未执行，用户要求暂不构建

### 2.3 待完成

- [ ] 小程序页面落点确认
- [ ] 小程序今日页 / 任务页 / 计时页 / 统计页 / 习惯页
- [x] 专注设置：默认番茄时长、短休息、长休息、长休息间隔
- [x] 休息流程：短休息 / 长休息会话
- [x] 重复任务：每日 / 每周 / 每月任务生成
- [x] 目标系统：每日 / 每周专注目标
- [ ] 微信订阅消息提醒
- [x] 白噪音 / 背景音
- [x] 成就系统
- [ ] 自习室
- [x] 排行榜
- [ ] 学习计划联动
- [ ] AI 推荐今日任务和专注安排

### 2.4 当前文件落点

后端：

```text
backend/app/pomodoro/
  api/v1/task.py
  api/v1/focus.py
  api/v1/break_session.py
  api/v1/achievement.py
  api/v1/ranking.py
  api/v1/sound.py
  api/v1/habit.py
  api/v1/setting.py
  api/v1/statistic.py
  crud/crud_task.py
  crud/crud_focus.py
  crud/crud_break.py
  crud/crud_achievement.py
  crud/crud_habit.py
  crud/crud_setting.py
  model/task.py
  model/focus.py
  model/break_session.py
  model/achievement.py
  model/habit.py
  model/setting.py
  schema/task.py
  schema/focus.py
  schema/break_session.py
  schema/achievement.py
  schema/ranking.py
  schema/sound.py
  schema/habit.py
  schema/setting.py
  schema/statistic.py
  service/task_service.py
  service/focus_service.py
  service/break_service.py
  service/achievement_service.py
  service/ranking_service.py
  service/sound_service.py
  service/habit_service.py
  service/setting_service.py
  service/statistic_service.py
```

小程序：

```text
mini/src/api/pomodoro.ts
mini/src/composables/usePomodoroSound.ts
```

迁移：

```text
无
```

说明：番茄模块当前都是新建表，不保留 Alembic 迁移文件，开发环境重启时由项目自动建表。

## 3. 功能范围

### 3.1 MVP 版本

第一版建议只做能闭环的核心功能：

- [x] 任务创建、编辑、完成、删除
- [x] 快速开始番茄专注
- [x] 任务关联专注记录
- [x] 专注开始、暂停、继续、完成、取消
- [x] 今日专注统计
- [x] 今日任务完成统计

### 3.2 增强版本

第二阶段可增加：

- [x] 重复任务
- [x] 习惯打卡
- [x] 周统计、月统计、日历统计
- [x] 专注目标设置
- [x] 白噪音
- [ ] 微信订阅消息提醒
- [ ] 专注结束总结

### 3.3 高级版本

后续可扩展：

- [ ] 自习室
- [x] 排行榜
- [x] 成就系统
- [ ] 学习计划联动
- [ ] AI 推荐今日任务和专注安排

## 4. 业务模块命名

建议新增后端模块 `pomodoro`：

```text
backend/app/pomodoro/
  api/v1/
    task.py
    focus.py
    habit.py
    statistic.py
  crud/
    crud_task.py
    crud_focus.py
    crud_habit.py
  model/
    task.py
    focus.py
    habit.py
  schema/
    task.py
    focus.py
    habit.py
    statistic.py
  service/
    task_service.py
    focus_service.py
    habit_service.py
    statistic_service.py
```

如果后续要和学习计划深度绑定，也可以命名为 `study_focus`。从产品表达看，`pomodoro` 更直观；从业务扩展看，`study_focus` 更宽。

## 4. 后端架构设计

后端遵循当前项目的 FBA 分层方式：

| 层级 | 职责 |
|---|---|
| API | 路由、参数接收、响应返回 |
| Schema | 请求和响应模型 |
| Service | 业务逻辑、状态机、异常处理 |
| CRUD | 数据库读写 |
| Model | SQLAlchemy ORM 模型 |

实现顺序建议：

1. 定义数据库模型
2. 定义请求和响应 schema
3. 定义 CRUD
4. 定义 Service
5. 定义 API 路由
6. 接入小程序接口
7. 增加统计和缓存优化

## 5. 数据库模型设计

### 5.1 任务表 `pomodoro_task`

用于存储用户待办任务。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint | 是 | 主键 |
| user_id | bigint | 是 | 用户 ID |
| title | varchar(100) | 是 | 任务标题 |
| description | text | 否 | 任务描述 |
| status | varchar(20) | 是 | pending、doing、completed、archived |
| priority | int | 是 | 优先级，数字越大优先级越高 |
| estimated_minutes | int | 否 | 预计完成分钟数 |
| due_at | datetime | 否 | 截止时间 |
| repeat_type | varchar(20) | 是 | none、daily、weekly、monthly |
| completed_at | datetime | 否 | 完成时间 |
| created_time | datetime | 是 | 创建时间 |
| updated_time | datetime | 是 | 更新时间 |

索引建议：

```text
idx_pomodoro_task_user_status(user_id, status)
idx_pomodoro_task_user_due_at(user_id, due_at)
idx_pomodoro_task_user_created_time(user_id, created_time)
```

### 5.2 专注记录表 `pomodoro_focus_session`

用于存储一次专注会话。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint | 是 | 主键 |
| user_id | bigint | 是 | 用户 ID |
| task_id | bigint | 否 | 关联任务 ID |
| mode | varchar(20) | 是 | pomodoro、countdown、stopwatch |
| status | varchar(20) | 是 | running、paused、completed、canceled |
| planned_minutes | int | 是 | 计划专注分钟数 |
| focused_seconds | int | 是 | 实际专注秒数 |
| paused_seconds | int | 是 | 暂停秒数 |
| interrupt_count | int | 是 | 中断次数 |
| started_at | datetime | 是 | 服务端开始时间 |
| paused_at | datetime | 否 | 最近暂停时间 |
| ended_at | datetime | 否 | 结束时间 |
| client_started_at | datetime | 否 | 小程序本地开始时间 |
| source | varchar(20) | 是 | mini、web、admin |
| remark | text | 否 | 备注 |
| created_time | datetime | 是 | 创建时间 |
| updated_time | datetime | 是 | 更新时间 |

索引建议：

```text
idx_pomodoro_focus_user_status(user_id, status)
idx_pomodoro_focus_user_started_at(user_id, started_at)
idx_pomodoro_focus_user_task(user_id, task_id)
```

### 5.3 习惯表 `pomodoro_habit`

用于存储用户习惯。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint | 是 | 主键 |
| user_id | bigint | 是 | 用户 ID |
| name | varchar(100) | 是 | 习惯名称 |
| target_count | int | 是 | 每日目标次数 |
| status | varchar(20) | 是 | enabled、disabled |
| created_time | datetime | 是 | 创建时间 |
| updated_time | datetime | 是 | 更新时间 |

### 5.4 习惯打卡表 `pomodoro_habit_checkin`

用于记录每日习惯打卡。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint | 是 | 主键 |
| user_id | bigint | 是 | 用户 ID |
| habit_id | bigint | 是 | 习惯 ID |
| checkin_date | date | 是 | 打卡日期 |
| count | int | 是 | 当日打卡次数 |
| checked_at | datetime | 是 | 最近打卡时间 |
| created_time | datetime | 是 | 创建时间 |
| updated_time | datetime | 是 | 更新时间 |

唯一索引建议：

```text
uk_pomodoro_habit_checkin_user_habit_date(user_id, habit_id, checkin_date)
```

## 6. 状态枚举

### 6.1 任务状态

| 状态 | 说明 |
|---|---|
| pending | 待完成 |
| doing | 进行中 |
| completed | 已完成 |
| archived | 已归档 |

### 6.2 专注状态

| 状态 | 说明 |
|---|---|
| running | 进行中 |
| paused | 已暂停 |
| completed | 已完成 |
| canceled | 已取消 |

### 6.3 专注模式

| 模式 | 说明 |
|---|---|
| pomodoro | 标准番茄钟 |
| countdown | 自定义倒计时 |
| stopwatch | 正向计时 |

### 6.4 重复类型

| 类型 | 说明 |
|---|---|
| none | 不重复 |
| daily | 每日 |
| weekly | 每周 |
| monthly | 每月 |

## 7. 后端接口设计

接口统一从登录态获取 `user_id`，前端不得传入 `user_id`。

### 7.1 任务接口

#### 任务列表

```http
GET /api/v1/pomodoro/tasks
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| status | string | 否 | 任务状态 |
| keyword | string | 否 | 标题关键词 |
| page | int | 否 | 页码 |
| size | int | 否 | 每页数量 |

#### 创建任务

```http
POST /api/v1/pomodoro/tasks
```

请求体：

```json
{
  "title": "刷申论材料题",
  "description": "完成第 3 套材料分析",
  "priority": 2,
  "estimated_minutes": 50,
  "due_at": "2026-07-01T20:00:00+08:00",
  "repeat_type": "none"
}
```

#### 任务详情

```http
GET /api/v1/pomodoro/tasks/{task_id}
```

#### 更新任务

```http
PUT /api/v1/pomodoro/tasks/{task_id}
```

#### 完成任务

```http
PATCH /api/v1/pomodoro/tasks/{task_id}/complete
```

#### 删除任务

```http
DELETE /api/v1/pomodoro/tasks/{task_id}
```

### 7.2 专注接口

#### 开始专注

```http
POST /api/v1/pomodoro/focus/start
```

请求体：

```json
{
  "task_id": 1001,
  "mode": "pomodoro",
  "planned_minutes": 25,
  "client_started_at": "2026-06-30T09:30:00+08:00"
}
```

响应体：

```json
{
  "id": 2001,
  "task_id": 1001,
  "mode": "pomodoro",
  "status": "running",
  "planned_minutes": 25,
  "focused_seconds": 0,
  "paused_seconds": 0,
  "started_at": "2026-06-30T09:30:01+08:00"
}
```

#### 暂停专注

```http
POST /api/v1/pomodoro/focus/{session_id}/pause
```

#### 继续专注

```http
POST /api/v1/pomodoro/focus/{session_id}/resume
```

#### 完成专注

```http
POST /api/v1/pomodoro/focus/{session_id}/finish
```

请求体：

```json
{
  "focused_seconds": 1500,
  "paused_seconds": 120,
  "interrupt_count": 1,
  "remark": "完成一轮材料阅读"
}
```

#### 取消专注

```http
POST /api/v1/pomodoro/focus/{session_id}/cancel
```

#### 当前专注

```http
GET /api/v1/pomodoro/focus/current
```

#### 专注记录

```http
GET /api/v1/pomodoro/focus/records
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| start_date | date | 否 | 开始日期 |
| end_date | date | 否 | 结束日期 |
| task_id | int | 否 | 任务 ID |
| page | int | 否 | 页码 |
| size | int | 否 | 每页数量 |

### 7.3 习惯接口

#### 习惯列表

```http
GET /api/v1/pomodoro/habits
```

#### 创建习惯

```http
POST /api/v1/pomodoro/habits
```

请求体：

```json
{
  "name": "每日申论积累",
  "target_count": 1
}
```

#### 习惯打卡

```http
POST /api/v1/pomodoro/habits/{habit_id}/checkin
```

请求体：

```json
{
  "checkin_date": "2026-06-30",
  "count": 1
}
```

### 7.4 统计接口

#### 今日统计

```http
GET /api/v1/pomodoro/statistics/today
```

响应体：

```json
{
  "focused_seconds": 7200,
  "completed_task_count": 5,
  "finished_session_count": 4,
  "habit_checkin_count": 3,
  "current_streak_days": 6
}
```

#### 周统计

```http
GET /api/v1/pomodoro/statistics/weekly
```

#### 月统计

```http
GET /api/v1/pomodoro/statistics/monthly
```

#### 日历统计

```http
GET /api/v1/pomodoro/statistics/calendar
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| year | int | 是 | 年 |
| month | int | 是 | 月 |

### 7.5 成就接口

#### 成就列表

```http
GET /api/v1/pomodoro/achievements
```

返回当前用户所有成就规则、当前进度、是否达成、是否已领取。

覆盖指标：

- 累计专注小时数
- 连续专注天数
- 连续习惯打卡天数
- 完成番茄数量

#### 评估成就

```http
POST /api/v1/pomodoro/achievements/evaluate
```

后端会按当前专注和习惯数据计算成就，达标后写入用户成就记录。

#### 领取成就

```http
POST /api/v1/pomodoro/achievements/{achievement_id}/claim
```

`achievement_id` 是用户成就记录 ID，不是规则 ID。已领取时重复调用会返回当前记录。

### 7.6 排行榜接口

#### 今日专注榜

```http
GET /api/v1/pomodoro/rankings/today
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| scope | string | 否 | 当前仅支持 global |
| limit | int | 否 | 返回数量，默认 50，最大 100 |

#### 本周专注榜

```http
GET /api/v1/pomodoro/rankings/weekly
```

当前已完成全站范围排行榜。好友 / 小组范围需要先接入真实好友关系或小组成员关系，避免生成不可信榜单。

返回内容：

- 排名
- 用户 ID
- 昵称
- 头像
- 专注秒数
- 完成番茄数量
- 我的排名

### 7.7 白噪音接口

#### 背景音预设

```http
GET /api/v1/pomodoro/sounds/presets
```

当前预设：

| key | 名称 | 小程序本地资源路径 |
|---|---|---|
| rain | 雨声 | `/static/sounds/pomodoro/rain.mp3` |
| cafe | 咖啡厅 | `/static/sounds/pomodoro/cafe.mp3` |
| white_noise | 白噪音 | `/static/sounds/pomodoro/white-noise.mp3` |

背景音偏好通过设置接口保存：

```http
PUT /api/v1/pomodoro/settings
```

请求体示例：

```json
{
  "sound_enabled": true,
  "background_sound": "rain"
}
```

## 8. 后端业务规则

### 8.1 专注会话规则

- 同一用户同一时间只允许存在一个 `running` 或 `paused` 的专注会话。
- 创建专注前需要检查是否有未结束会话。
- 暂停只能从 `running` 状态进入。
- 继续只能从 `paused` 状态进入。
- 完成只能从 `running` 或 `paused` 状态进入。
- 取消只能从 `running` 或 `paused` 状态进入。
- 已完成和已取消的会话不可再次修改状态。

### 8.2 专注时长校验

- 小程序负责倒计时展示，后端负责最终记录。
- `focused_seconds` 不能完全信任前端，需要结合服务端 `started_at`、`ended_at` 做上限校验。
- 上报的 `focused_seconds` 不应大于服务端可计算时长。
- 如果客户端上报时长异常，后端应使用服务端可计算的最大合理值。
- `planned_minutes` 建议限制在 1 到 240 分钟之间。

### 8.3 任务规则

- 任务只能由所属用户操作。
- 删除任务不应删除历史专注记录。
- 任务完成后仍然可以查看关联专注记录。
- 专注完成不自动完成任务，由用户确认是否完成任务。
- 重复任务可以在每日首次访问或定时任务中生成当天实例。

### 8.4 习惯规则

- 同一习惯同一天只保留一条打卡记录。
- 重复打卡时累加 `count`。
- 用户可以关闭习惯，关闭后不参与今日待办展示。

## 9. 小程序页面设计

当前小程序基于 uni-app、Vue3、Pinia、Wot UI，建议新增以下页面：

```text
mini/src/pages/focus/index.vue
mini/src/pages/focus/timer.vue
mini/src/pages/focus/settings.vue
mini/src/pages/task/index.vue
mini/src/pages/task/edit.vue
mini/src/pages/statistic/index.vue
mini/src/pages/habit/index.vue
```

### 9.1 今日页

页面目标：让用户快速知道今天要做什么，并立即开始专注。

核心区域：

- 今日专注时长
- 今日完成任务数
- 今日番茄数
- 快速开始 25 分钟
- 今日待办任务
- 今日习惯打卡

主要操作：

- 创建任务
- 开始专注
- 完成任务
- 打卡习惯

### 9.2 任务页

页面目标：管理待办事项。

核心能力：

- 待办任务列表
- 已完成任务列表
- 任务搜索
- 按优先级排序
- 新增任务
- 编辑任务
- 完成任务
- 删除任务

### 9.3 计时页

页面目标：承载专注过程。

核心元素：

- 当前任务标题
- 倒计时圆环
- 已专注时间
- 暂停按钮
- 继续按钮
- 放弃按钮
- 完成按钮

交互规则：

- 进入页面时从后端确认当前会话。
- 如果存在进行中会话，恢复本地倒计时。
- 页面隐藏时记录本地时间。
- 页面恢复时按当前时间重新计算倒计时。
- 专注结束后弹出总结弹窗。

### 9.4 统计页

页面目标：展示用户的长期专注反馈。

核心内容：

- 今日专注时长
- 本周专注趋势
- 本月专注日历
- 任务完成数量
- 番茄钟完成数量
- 连续专注天数

### 9.5 习惯页

页面目标：完成轻量习惯养成。

核心能力：

- 习惯列表
- 新增习惯
- 今日打卡
- 连续打卡天数
- 关闭习惯

## 10. 小程序状态管理

建议拆分 Pinia store：

```text
mini/src/store/modules/pomodoro/task.ts
mini/src/store/modules/pomodoro/focus.ts
mini/src/store/modules/pomodoro/statistic.ts
mini/src/store/modules/pomodoro/habit.ts
```

### 10.1 `useFocusStore`

核心状态：

```ts
interface FocusState {
  currentSessionId?: number
  taskId?: number
  status: 'idle' | 'running' | 'paused' | 'completed' | 'canceled'
  mode: 'pomodoro' | 'countdown' | 'stopwatch'
  plannedSeconds: number
  focusedSeconds: number
  pausedSeconds: number
  remainingSeconds: number
  startedAt?: string
  pausedAt?: string
  interruptCount: number
}
```

核心 action：

```text
fetchCurrentSession
startFocus
pauseFocus
resumeFocus
finishFocus
cancelFocus
syncLocalTimer
resetFocus
```

### 10.2 计时策略

小程序不应依赖后台 `setInterval` 的持续执行。

建议策略：

1. 开始专注时请求后端创建会话。
2. 后端返回 `session_id` 和 `started_at`。
3. 小程序本地开启 `setInterval` 更新 UI。
4. `onHide` 时记录当前时间。
5. `onShow` 时根据当前时间和 `started_at` 重新计算剩余时间。
6. 点击完成时上报 `focused_seconds`、`paused_seconds`、`interrupt_count`。
7. 如果结束接口失败，本地保存待同步记录，下次进入应用时补偿同步。

## 11. 小程序接口封装

建议新增接口目录：

```text
mini/src/service/pomodoro/task.ts
mini/src/service/pomodoro/focus.ts
mini/src/service/pomodoro/habit.ts
mini/src/service/pomodoro/statistic.ts
```

建议新增类型文件：

```text
mini/src/types/pomodoro.ts
```

### 11.1 任务接口方法

```ts
export function getTaskList(params: TaskQuery) {
  return http.get<TaskListVO>('/api/v1/pomodoro/tasks', { params })
}

export function createTask(data: TaskCreateRequest) {
  return http.post<TaskVO>('/api/v1/pomodoro/tasks', data)
}

export function updateTask(taskId: number, data: TaskUpdateRequest) {
  return http.put<TaskVO>(`/api/v1/pomodoro/tasks/${taskId}`, data)
}

export function completeTask(taskId: number) {
  return http.patch<TaskVO>(`/api/v1/pomodoro/tasks/${taskId}/complete`)
}
```

### 11.2 专注接口方法

```ts
export function startFocus(data: StartFocusRequest) {
  return http.post<FocusSessionVO>('/api/v1/pomodoro/focus/start', data)
}

export function pauseFocus(sessionId: number) {
  return http.post<FocusSessionVO>(`/api/v1/pomodoro/focus/${sessionId}/pause`)
}

export function resumeFocus(sessionId: number) {
  return http.post<FocusSessionVO>(`/api/v1/pomodoro/focus/${sessionId}/resume`)
}

export function finishFocus(sessionId: number, data: FinishFocusRequest) {
  return http.post<FocusSessionVO>(`/api/v1/pomodoro/focus/${sessionId}/finish`, data)
}

export function cancelFocus(sessionId: number) {
  return http.post<FocusSessionVO>(`/api/v1/pomodoro/focus/${sessionId}/cancel`)
}

export function getCurrentFocus() {
  return http.get<FocusSessionVO | null>('/api/v1/pomodoro/focus/current')
}
```

### 11.3 当前 SDK 包装方法

当前小程序已在 `mini/src/api/pomodoro.ts` 通过 `@fba/api-sdk` 封装以下新增方法：

```ts
getPomodoroAchievementList()
evaluatePomodoroAchievements()
claimPomodoroAchievement(achievementId)
getPomodoroTodayRanking(query)
getPomodoroWeeklyRanking(query)
getPomodoroSoundPresets()
updatePomodoroSetting({ sound_enabled, background_sound })
```

专注页播放 / 暂停可复用：

```ts
const { playSound, pauseSound, toggleSound, stopSound } = usePomodoroSound()
```

## 12. 微信小程序提醒设计

小程序可以使用微信订阅消息做提醒，但需要用户授权。

适合提醒的场景：

- 任务到期提醒
- 番茄休息结束提醒
- 每日计划提醒
- 习惯打卡提醒

注意事项：

- 订阅消息必须由用户主动授权。
- 不能依赖订阅消息做强控制。
- 提醒失败不影响业务主流程。
- 后端需要记录提醒模板 ID、授权状态和发送日志。

## 13. 统计设计

### 13.1 实时统计

MVP 阶段可直接从业务表实时聚合：

- 今日专注秒数：查询今日已完成专注记录求和
- 今日完成任务数：查询今日完成任务数量
- 今日番茄数：查询今日完成专注会话数量
- 今日习惯打卡数：查询今日打卡记录数量

### 13.2 汇总表

数据量增大后可新增每日汇总表 `pomodoro_daily_statistic`：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 主键 |
| user_id | bigint | 用户 ID |
| statistic_date | date | 统计日期 |
| focused_seconds | int | 专注秒数 |
| completed_task_count | int | 完成任务数 |
| finished_session_count | int | 完成专注数 |
| habit_checkin_count | int | 习惯打卡数 |
| created_time | datetime | 创建时间 |
| updated_time | datetime | 更新时间 |

汇总表可以在专注完成、任务完成、习惯打卡时同步更新，也可以由定时任务异步汇总。

## 14. 缓存设计

可以使用 Redis 缓存以下数据：

- 当前用户正在进行的专注会话
- 今日统计
- 用户专注设置
- 首页今日概览
- 今日 / 本周全站排行榜

建议 key：

```text
pomodoro:focus:current:{user_id}
pomodoro:statistic:today:{user_id}:{date}
pomodoro:settings:{user_id}
pomodoro:overview:{user_id}:{date}
pomodoro:ranking:global:{today|weekly}:{period_start_date}:{limit}
```

缓存失效场景：

- 创建任务
- 完成任务
- 开始专注
- 完成专注
- 取消专注
- 习惯打卡
- 成就评估或领取
- 排行榜缓存按短 TTL 自动过期，当前实现为 180 秒

## 15. 异常处理

建议定义清晰的业务错误：

| 场景 | 错误说明 |
|---|---|
| 已存在进行中的专注 | 请先完成或取消当前专注 |
| 任务不存在 | 任务不存在或无权访问 |
| 专注记录不存在 | 专注记录不存在或无权访问 |
| 状态不允许暂停 | 当前专注状态不能暂停 |
| 状态不允许继续 | 当前专注状态不能继续 |
| 状态不允许完成 | 当前专注状态不能完成 |
| 专注时长非法 | 专注时长不合法 |
| 习惯不存在 | 习惯不存在或无权访问 |

异常响应需要遵循当前项目统一响应格式。

## 16. 权限与安全

- 所有数据必须按当前登录用户隔离。
- 所有详情、更新、删除接口都必须校验资源归属。
- 前端不得传 `user_id`。
- 后端不得相信前端传入的专注时长，需要做服务端校验。
- 删除任务只删除任务本身，不删除历史专注记录。
- 统计接口只返回当前用户数据。

## 17. 小程序本地容错

建议本地保存以下状态：

- 当前专注 session ID
- 当前任务 ID
- 本地开始时间
- 暂停累计时长
- 待同步结束记录

当网络异常时：

1. 用户点击完成专注。
2. 小程序本地标记已完成。
3. 写入待同步队列。
4. 下次进入小程序时调用补偿同步。
5. 后端根据 session 状态做幂等处理。

## 18. 实施计划

### 阶段一：任务模块

- 新增任务模型
- 新增任务 schema
- 新增任务 CRUD
- 新增任务 service
- 新增任务 API
- 小程序接入任务列表、创建任务、完成任务

### 阶段二：专注模块

- 新增专注模型
- 新增专注 schema
- 新增专注 CRUD
- 新增专注 service
- 实现专注状态机
- 小程序接入计时页

### 阶段三：统计模块

- 新增今日统计接口
- 新增周统计接口
- 新增月统计接口
- 小程序接入统计页
- 首页展示今日概览

### 阶段四：习惯模块

- 新增习惯模型
- 新增习惯打卡模型
- 新增习惯接口
- 小程序接入习惯页

### 阶段五：体验增强

- [x] 增加白噪音
- 增加订阅消息提醒
- [x] 增加成就和连续天数
- [x] 增加今日 / 本周全站排行榜
- 增加学习计划联动

## 19. 验证清单

### 19.1 后端验证

新增功能后需要至少验证以下文件能互相导入和编译：

```text
uv run python -m py_compile backend/app/pomodoro/model/task.py
uv run python -m py_compile backend/app/pomodoro/model/focus.py
uv run python -m py_compile backend/app/pomodoro/model/habit.py
uv run python -m py_compile backend/app/pomodoro/model/achievement.py
uv run python -m py_compile backend/app/pomodoro/schema/task.py
uv run python -m py_compile backend/app/pomodoro/schema/focus.py
uv run python -m py_compile backend/app/pomodoro/schema/habit.py
uv run python -m py_compile backend/app/pomodoro/schema/statistic.py
uv run python -m py_compile backend/app/pomodoro/schema/achievement.py
uv run python -m py_compile backend/app/pomodoro/schema/ranking.py
uv run python -m py_compile backend/app/pomodoro/schema/sound.py
uv run python -m py_compile backend/app/pomodoro/crud/crud_task.py
uv run python -m py_compile backend/app/pomodoro/crud/crud_focus.py
uv run python -m py_compile backend/app/pomodoro/crud/crud_habit.py
uv run python -m py_compile backend/app/pomodoro/crud/crud_achievement.py
uv run python -m py_compile backend/app/pomodoro/service/task_service.py
uv run python -m py_compile backend/app/pomodoro/service/focus_service.py
uv run python -m py_compile backend/app/pomodoro/service/habit_service.py
uv run python -m py_compile backend/app/pomodoro/service/statistic_service.py
uv run python -m py_compile backend/app/pomodoro/service/achievement_service.py
uv run python -m py_compile backend/app/pomodoro/service/ranking_service.py
uv run python -m py_compile backend/app/pomodoro/service/sound_service.py
uv run python -m py_compile backend/app/pomodoro/api/v1/task.py
uv run python -m py_compile backend/app/pomodoro/api/v1/focus.py
uv run python -m py_compile backend/app/pomodoro/api/v1/habit.py
uv run python -m py_compile backend/app/pomodoro/api/v1/statistic.py
uv run python -m py_compile backend/app/pomodoro/api/v1/achievement.py
uv run python -m py_compile backend/app/pomodoro/api/v1/ranking.py
uv run python -m py_compile backend/app/pomodoro/api/v1/sound.py
```

### 19.2 小程序验证

```text
pnpm --dir mini run type-check
pnpm --dir mini run build:mp
```

### 19.3 业务验证

- 创建任务后，任务列表能看到新任务。
- 开始专注后，当前专注接口能返回进行中会话。
- 已有进行中会话时，不能再次开始新专注。
- 暂停后只能继续或取消，不能重复暂停。
- 完成专注后，今日专注时长增加。
- 完成任务后，今日完成任务数增加。
- 删除任务后，历史专注记录仍可查询。
- 网络中断后，小程序能恢复当前专注状态。
- 完成专注或习惯打卡后，成就评估能生成达成记录。
- 已达成成就领取后，状态变为 `claimed` 并记录领取时间。
- 今日 / 本周排行榜能返回全站排名和当前用户排名。
- 背景音预设接口能返回雨声、咖啡厅、白噪音，设置接口能保存用户偏好。

## 20. MVP 接入建议

第一版建议只实现：

- `pomodoro_task`
- `pomodoro_focus_session`
- 任务增删改查
- 专注开始、暂停、继续、完成、取消
- 当前专注查询
- 今日统计
- 小程序今日页、任务页、计时页

这样可以最快形成用户可用闭环，后续再逐步增加习惯、提醒、统计图表和自习室。
