# 学习规划（Study Plan）模块设计与追踪文档

> 范围：公考领域的每日学习计划，覆盖复习/刷题/错题复盘/能力提升四类模块，
> 由导师手动配置（含模板机制），灰度内测，未开放给所有用户。
> 本文档同时是 **设计依据** 和 **开发追踪表**，从启动到上线全周期维护。

---

## 1. 决策记录（Decision Log）

每条决策包含：**结论 + 关键约束 + 后续可变性**。修改决策时追加新行，不要直接覆盖。

| # | 主题 | 结论 | 约束 / 备注 |
|---|---|---|---|
| D1 | tab 位置 | 新增 `规划` tab，与现有 `刷题`、`我的` 并列 | 解开 `mini/src/tabbar/config.ts` 中已注释的 `pages/study/index` 配置；practice 文案改回 `刷题` |
| D2 | 业务领域 | 首版仅 `公考（civil_service）` | 模型字段 `domain` 预留，未来扩展其他领域不动表结构 |
| D3 | 每日模块数 | 默认 4 个，可动态增减 | 由 `study_plan_item` 一对多关系天然支持，无需额外配置 |
| D4 | 模块类型枚举 | `review` / `practice` / `wrong_review` / `ability` | `ability` MVP 阶段**不实现**（前端独立功能未接后端）；枚举留位 |
| D5 | 复习内容承载 | 复用 `sys_content`，`app_code='gongkao'` | 学习内容与复习内容**共用同一池**；网盘链接放 `extra.cloud_links` JSONB |
| D6 | 刷题任务定义 | 双形态：①按知识点 + 固定题数筛选 ②导师指定题目 ID 列表 | 利用现有 `Question.knowledge_point` JSONB 字段，无需新增关联表 |
| D7 | 错题复盘 | 复用 `WrongQuestionReview` 表，不重复造轮子 | `study_plan_item` 与 `WrongQuestionReview` 通过 `study_plan_record.extra_data` 软关联 |
| D8 | 能力提升 | MVP 砍掉（前端已有独立功能但未对接后端） | 枚举保留 `ability`，待后端能力练习模块上线后接入 |
| D9 | 计划模板机制 | **需要**，避免导师 1v1 手配压力 | 新增 `study_plan_template` + `study_plan_template_item` 两张表 |
| D10 | 完成判定·复习 | 点击 `已读` 按钮即视为完成 | 不做停留时长判断（首版） |
| D11 | 完成判定·刷题 | 考试模式：交卷即完成，分数不卡进度 | `extra` 存 `question_count` / `required_accuracy` 供导师参考；交卷后 session_hook 自动标 completed |
| D12 | 完成判定·错题复盘 | 所有动态选出的错题均填完 `reasons` + `summary` | 与 `WrongQuestionReview` 表的 `reasons` + `summary` 字段对齐 |
| D27 | practice session 绑定 | lazy 创建：首次 start_item 时按需调题库 create_session，session_key 写回 item.extra | 幂等：已有 session_key 则复用；不做预生成 |
| D28 | practice 交卷回调 | question_bank session.py submit endpoint 末尾 lazy import study_plan hook | hook 用真实 correct_count/total_count 写 record 并标 completed；不卡正确率 |
| D29 | practice 退出行为 | 做一半退出 = in_progress，下次继续同一个 session | 无"放弃"概念；session abandoned 时不标 skipped，清 session_key 让下次重建 |
| D13 | 跨天处理 | 当日未完成 → 进历史记录，次日不在今日列表显示，仅提醒 | 计划按日期驱动；中断时全链条**顺延**（不丢失内容） |
| D14 | 导师 ↔ 学员关系 | 多对多，**管理员分配** | 新增 `study_mentor_student` 关联表；学员不能自行申请导师 |
| D15 | 灰度策略 | 方案 A：硬编码 `STUDY_PLAN_WHITELIST` 配置 | 用户量上来后切换数据库白名单表；不做百分比 / 标签灰度 |
| D16 | tab 名称 | `规划`（已写入 tabbar 注释草案） | 强调每日任务流属性；后续也可在 customTabbarList 微调 |
| D17 | 资料大厅归位 | 旧 `pages/study/index.vue` 迁移至 `pages/resource/index.vue` | 让 `pages/study/` 完全归学习规划；不上 tabbar，作为辅助入口由学习规划首页引出 |
| D18 | 日历策略 | 严格日历（含周末） | 计划本身可对周末做规划（包括"休息也是规划"），简单且可被 D13 顺延机制兜底 |
| D19 | 跨天处理时机 | 方案 A：Celery beat 定时扫 | 项目已有 Celery + 18 个定时任务，零新增基础设施；status 自描述、统计便利 |
| D20 | 错题选题策略 | MVP 用"近 7 天 + 未掌握 top N=10"，TODO 升级 | 算法侧未来对接能力评估模型，避免堵住 MVP（U10）|
| D21 | 后台鉴权 | RBAC：superuser 自动通过 admin；运营在后台给用户加"导师"角色 | 复用项目现有 RBAC 体系；学员/导师/管理员三层闸门各管各的 |
| D22 | 模板 ref 失效处理 | 不预先校验，直接复制 ref_id | 作者维护，失效罕见；T2.6/T2.8 单点校验已足够 |
| D23 | 多 active 计划 | 允许并存 | 多导师各管一个模块（行测/申论），共享学员 |
| D24 | 今日页展示形态 | 合并展示，不按 plan 分卡 | 学员心智单元是"今日要做的事"，主计划取 start_date 最早者 |
| D25 | 模板 extra 克隆策略 | 完全克隆（deepcopy），不支持 override | 真要调整就先改模板再实例化；schema 简洁 |
| D26 | 灰度可见机制 | 白名单 = 虚拟角色 `study_plan_internal`；命中后 /me 接口追加该角色 | 复用前端现成的"按角色过滤 tabbar"机制；未命中用户完全看不到规划 tab |

---

## 2. 数据模型

### 2.1 新建表（`app/study_plan`）

#### `study_plan` — 学习计划主表
```
id              BIGINT PK
user_id         BIGINT FK -> study_user_account.user_id
domain          VARCHAR(32)         -- 'civil_service'
title           VARCHAR(255)
start_date      DATE
end_date        DATE
status          VARCHAR(16)         -- 'active' / 'paused' / 'finished'
template_id     BIGINT FK NULL      -- 来源模板（可空）
created_by      BIGINT              -- 导师 user_id
created_at, updated_at
```

#### `study_plan_item` — 每日计划项（核心表）
```
id              BIGINT PK
plan_id         BIGINT FK -> study_plan.id
plan_date       DATE                -- 该项所属日期
order_index     INT                 -- 当日顺序

module_type     VARCHAR(16)         -- review/practice/wrong_review/ability
title           VARCHAR(255)
ref_type        VARCHAR(32)         -- content/question_set/wrong_dynamic/ability_task
ref_id          BIGINT NULL         -- 引用目标 ID（错题复盘可为 null）
extra           JSONB NULL          -- 模块特定配置（如刷题正确率、知识点筛选条件）

expected_minutes INT
status          VARCHAR(16)         -- pending/in_progress/completed/skipped
created_at, updated_at

INDEX (plan_id, plan_date, order_index)
INDEX (plan_date, status)           -- 用于"今日待办"查询
```

**`extra` 字段约定**：
- `module_type='practice'`：`{"knowledge_points": ["xxx"], "question_count": 20, "required_accuracy": 0.6}` 或 `{"question_ids": [1,2,3]}`
- `module_type='review'`：`{"cloud_links": [{"name":"补充资料","url":"https://..."}]}`（可选）

#### `study_plan_record` — 完成记录
```
id              BIGINT PK
item_id         BIGINT FK -> study_plan_item.id
user_id         BIGINT
completed_at    TIMESTAMPTZ
duration_seconds INT
score           INT NULL
correct_count   INT NULL
total_count     INT NULL
extra_data      JSONB NULL          -- 软关联 WrongQuestionReview.ids 等
```

#### `study_plan_template` — 计划模板
```
id              BIGINT PK
name            VARCHAR(255)
domain          VARCHAR(32)
duration_days   INT
created_by      BIGINT              -- 导师
is_active       BOOL
created_at, updated_at
```

#### `study_plan_template_item` — 模板项
```
id              BIGINT PK
template_id     BIGINT FK
day_index       INT                 -- 第几天（1..duration_days）
order_index     INT
module_type     VARCHAR(16)
title           VARCHAR(255)
ref_type        VARCHAR(32)
ref_id          BIGINT NULL
extra           JSONB NULL
expected_minutes INT

INDEX (template_id, day_index, order_index)
```

#### `study_mentor_student` — 导师学员关联（多对多）
```
id              BIGINT PK
mentor_id       BIGINT              -- 导师 user_id
student_id      BIGINT              -- 学员 user_id
assigned_by     BIGINT              -- 管理员 user_id
assigned_at     TIMESTAMPTZ
status          VARCHAR(16)         -- 'active' / 'paused'

UNIQUE (mentor_id, student_id)
INDEX (student_id)                  -- 查"我的导师"
INDEX (mentor_id)                   -- 查"我带的学员"
```

### 2.2 复用现有表
| 表 | 用途 |
|---|---|
| `sys_content` (`app_code='gongkao'`) | 复习/学习内容承载 |
| `study_question` | 刷题题目源 |
| `study_wrong_question_book` | 系统自动收录错题（错题复盘候选） |
| `study_wrong_question_custom` | 用户自定义错题（错题复盘候选） |
| `study_wrong_question_review` | 错题复盘记录（完成时写入） |

### 2.3 配置项（`backend/core/conf.py`）
```python
STUDY_PLAN_WHITELIST: list[int] = []  # 灰度白名单，user_id 列表
```

---

## 3. API 契约（MVP）

### 3.1 学员端（小程序）

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/study/plan/today` | 获取今日计划（含模块列表 + 进度） |
| GET | `/api/v1/study/plan/items/{item_id}` | 获取单个模块详情（含 ref 实体数据） |
| POST | `/api/v1/study/plan/items/{item_id}/start` | 标记开始；practice 类按需创建题库 session 并返回 session_key |
| POST | `/api/v1/study/plan/items/{item_id}/complete` | 提交完成；review 类手动调用，practice 类由交卷 hook 自动调用 |
| GET | `/api/v1/study/plan/me/plans` | 我的计划列表 |
| GET | `/api/v1/study/plan/me/plans/{plan_id}/items` | 某计划的全部 items（总体规划页用） |
| GET | `/api/v1/study/plan/me/plans/{plan_id}/progress` | 某计划的整体进度 |
| GET | `/api/v1/study/plan/me/uncompleted-count` | 历史未完成项数量（铃铛） |

### 3.2 导师端 / 管理端（PC 后台）

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/study/plans` | 创建计划（可基于模板批量生成 items） |
| GET | `/api/v1/study/plans` | 计划列表（按学员/导师/状态筛选） |
| PUT | `/api/v1/study/plan/items/{item_id}` | 编辑单个模块 |
| POST | `/api/v1/study/plan/items` | 新增单个模块 |
| DELETE | `/api/v1/study/plan/items/{item_id}` | 删除模块 |
| GET | `/api/v1/study/plans/{plan_id}/progress` | 查看学员计划完成情况 |
| POST | `/api/v1/study/templates` | 创建模板 |
| GET | `/api/v1/study/templates` | 模板列表 |
| POST | `/api/v1/study/mentors/assign` | 管理员分配导师 ↔ 学员 |

### 3.3 完成判定逻辑
```
review:      手动点"我已读完" → 服务端校验 read_acknowledged=True
practice:    交卷自动回调（session_hook）→ 交卷即完成，不卡正确率
             手动 complete 路径仍走 completion check（兜底）
wrong_review: 本期不实现
ability:     MVP 不实现
```

### 3.4 题库 session 交卷回调机制
```
question_bank session.py POST /{key}/submit
  → session_service.submit_session()（判题 + 统计）
  → lazy import study_plan.session_hook.handle_session_completed
    → 查 plan_item by extra->>'session_key'
    → 写 StudyPlanRecord（correct_count / total_count）
    → 标 plan_item.status = 'completed'
    → 不卡正确率，交卷即完成

question_bank session.py POST /{key}/abandon
  → 不调 hook，plan_item 保持 in_progress
  → session abandoned 后 session_key 清除，下次 start_item 创建新 session
```

---

## 4. 前端结构

### 4.1 tabbar 调整
- 解开 `mini/src/tabbar/config.ts` 中 `pages/study/index` 配置
- practice 文案 `学习` → `刷题`
- 新 tab 文案待定（D16）

### 4.2 页面结构
```
pages/study/index                # 规划 tab 首页：今日计划 + 进度 + 子模块入口 + 查看总体规划
pages/study/item/[id]            # 计划项详情（按 module_type 渲染不同视图）
pages/study/overview             # 总体规划：日历网格 + 进度环 + 当日明细展开
pages/study/history              # 历史记录（含未完成提醒，T3.7 占位）
```

### 4.3 学员端组件复用
- 复习模块 → 文章渲染（Tiptap）+ 网盘链接卡片 + `已读` 按钮
- 刷题模块 → 跳转 practice 已有页面，完成后 callback 回 study
- 错题复盘 → 复用错题复盘已有页面，完成后 callback 回 study

---

## 5. 开发任务追踪

> **状态约定**：⬜ 待办 / 🟡 进行中 / ✅ 完成 / ⏸️ 阻塞
> 每次开工请把状态更新到这里，配合 git commit 引用任务编号。

### Phase 1 — 后端骨架（约 3 天）
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T1.0 | 资料大厅迁移：`pages/study` → `pages/resource`、`pkg/study` → `pkg/resource` | ✅ | D17；含 6 处路径引用更新、tabbar 注释清理、新建 `pages/study/index.vue` 占位 |
| T1.1 | 创建 `app/study_plan` 五件套目录 | ✅ | model/schema/crud/service/api 占位 + 主 router 挂载；导入链验证通过 |
| T1.2 | 建模：`study_plan` + `study_plan_item` + `study_plan_record` | ✅ | 含 10 条 CHECK 约束、10 条索引；关系链双向打通；template_id 软引用待 T1.3 补 FK |
| T1.3 | 建模：`study_plan_template` + `study_plan_template_item` | ✅ | 含 6 条 CHECK + 5 条索引；模板↔模板项关系双向；plan.template_id FK 已补上 |
| T1.4 | 建模：`study_mentor_student` | ✅ | 多对多关联表；含 mentor≠student 自指约束 + status 枚举；2 条业务索引 |
| T1.5 | Alembic 迁移脚本生成 | ✅ | 改用 SQLAlchemy 渲染 SQL（init_tables.sql）；6 表已由 create_all 自动建好；待执行 1 条 ALTER 修 mentor.assigned_by 可空 |
| T1.6 | `STUDY_PLAN_WHITELIST` 配置 + 依赖注入校验 | ✅ | 配置位 core/conf.py；utils/permission.py 含 is_user_in_whitelist 纯函数 + StudyPlanWhitelistGate 校验类；空白名单 = 全员放行（开发友好） |
| T1.7 | Schema 定义（Pydantic） | ✅ | 21 个 schema 分 7 个文件（plan/item/record/template/mentor/today/_types）；Literal 枚举约束；Create/Update/Detail 三档分明；CHECK 与 Field 内置约束齐全；未引入校验器（遵循 CLAUDE.md） |

### Phase 2 — 后端业务（约 4 天）
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T2.1 | CRUD：`study_plan` / `item` / `record` | ✅ | crud_plan/item/record + 业务命名查询；真实 db smoke 验证通过 |
| T2.2 | CRUD：`template` / `mentor_student` | ✅ | crud_template/mentor，含按导师/学员维度反查 |
| T2.3 | Service：今日计划查询（含进度计算） | ✅ | today_service.get_today_plan + count_uncompleted_history；严格日历计算 day_index；支持多 active 合并展示（D24）|
| T2.4 | Service：模板 → 实例化为 plan + items | ✅ | template_service.instantiate_template；含 deepcopy extra、严格日历 + duration_days 计算 end_date；端到端 db smoke 验证（5 天模板 → 10 个 items）|
| T2.5 | Service：跨天处理（按日期定时 job 标记未完成） | ✅ | tasks/study_plan/tasks.py + beat 注册（每天 0:30）；底层调 bulk_skip_pending_before；私有实现可独立测试 |
| T2.6 | Service：错题复盘动态选题（首版规则：近 7 天未掌握 top N） | ✅ | wrong_review_service.select_wrong_review_questions；MVP 默认 30 天窗口（贴合公考节奏）；返回空属正常业务结果，由调用方兜底 |
| T2.7 | Service：完成判定四类逻辑 | ✅ | service/completion.py，纯函数 + CompletionCheckResult；10 条真值表测试通过 |
| T2.8 | API 路由（学员端 6 个 + 后台端 9 个） | ✅ | 实际落地 20 个 endpoint：student.py 6 / mentor.py 5 / admin.py 9；学员端用白名单闸 + JWT；后台端用 RequestPermission + DependsRBAC（superuser 自动通过）；权限标识 study_plan:mentor:* / study_plan:admin:* |
| T2.9 | 关键 service 单元测试 | ✅ | tests/test_completion.py 22 case + tests/test_today_service.py 8 case 全 PASS（60ms）；纯函数 0 db 依赖；端到端业务验证以 commit smoke 形式留档 |

### Phase 3 — 前端（小程序）（约 3 天）
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T3.1 | 调整 `tabbar/config.ts`，新增规划 tab | ✅ | tab 配 roles=['study_plan_internal']；后端 /me 接口命中白名单时追加虚拟角色；不命中用户完全看不到规划 tab |
| T3.2 | `pages/study/index.vue` 重构为今日计划首页 | ✅ | 完整今日聚合视图：进度卡 + 模块列表（4 类 module_type 各异图标）+ 历史提醒铃铛 + 资料大厅入口 + 查看总体规划入口；4 种异常态（loading/error/empty plan/empty items）；SDK 自动同步 20 个 study_plan 接口 |
| T3.3 | `pages/study/item/index.vue` 模块详情页（多态渲染） | ✅ | review：拉文章 + 网盘链接 + 我已读完按钮；practice：信息卡 + 开始/继续练习按钮 → 跳题库 session 页，交卷自动回调完成；wrong_review / ability 占位 |
| T3.4 | 复习模块组件（文章 + 网盘链接 + 已读按钮） | ✅ | 合并入 T3.3 的 review 类实现 |
| T3.5 | 刷题模块：lazy session 创建 + 交卷自动回调 | ✅ | D27/D28/D29；start_item 按需调题库 create_session，session_key 存 extra；交卷 hook 自动标 completed；做一半退出保持 in_progress 可继续 |
| T3.6 | 错题复盘模块 | ⏸️ | 本期不做，待错题反思能力完成后开放 |
| T3.7 | 历史记录页 | ⬜ | 占位页已建 |
| T3.8 | 灰度判断：根据用户白名单显示/隐藏 tab | ✅ | 已通过 T3.1 的虚拟角色机制完成（D26）|
| T3.9 | 总体规划页（日历网格） | ✅ | `pages/study/overview/index.vue`：拉 active 计划全量 items + progress，7 列日历网格 + 模块圆点 + 当日明细展开 |
| T3.10 | 学员端总体规划 API | ✅ | GET /me/plans/{id}/items + /progress，含 ownership 校验 |

### Phase 4 — 管理后台（PC，约 3 天）
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T4.1 | 计划管理页（列表 / 创建 / 编辑） | ⬜ | |
| T4.2 | 模板管理页 | ⬜ | |
| T4.3 | 导师 ↔ 学员分配页 | ⬜ | |
| T4.4 | 学员计划进度查看页（导师视角） | ⬜ | |

### Phase 5 — 联调与灰度上线
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T5.1 | 端到端联调（导师配 → 学员做 → 完成回写） | ⬜ | |
| T5.2 | 白名单加入种子用户 | ⬜ | |
| T5.3 | 内测反馈收集 | ⬜ | |

---

## 6. 未决事项 / P2 暂缓项

> 这些**不阻塞 MVP**，但需要在 MVP 上线后排期。

- **U1** 能力提升模块的后端化（D8）：前端 `mini/src/pkg/ability/` 已有 7 个子模块（basic-calculation / data-analysis / essay-terms / formula-ref / hanyu-assistant / spatial / thinking-training），需要梳理出接口需求后再建表
- **U2** 知识图谱可视化
- **U3** 能力评估雷达 / 标签云呈现
- **U4** 算法驱动的薄弱点推荐（替换导师手动配置）
- **U5** 导师在小程序端配置计划（首版只支持 PC 后台）
- **U6** 学员申请导师 + 导师审批流程（首版只支持管理员分配）
- **U7** 灰度方案从 A 升级到 B（数据库白名单表）
- **U8** 错题复盘的艾宾浩斯遗忘曲线策略（首版用简单规则）
- **U9** 计划完成提醒推送（订阅消息 / 公众号）
- **U10** 错题复盘动态选题算法升级：首版用"近 7 天 + 未掌握 top N"，未来需对接能力评估模型实现智能推荐

---

## 7. 关键引用文件清单

| 文件 | 作用 |
|---|---|
| `backend/app/study_plan/service/session_hook.py` | 题库 session 交卷回调：自动完成 plan_item |
| `backend/app/study_plan/service/student_service.py` | 学员端业务编排：start/complete + practice session lazy 创建 |
| `backend/app/study_plan/service/completion.py` | 完成判定四类逻辑（review/practice/wrong_review/ability） |
| `backend/app/study_plan/service/template_service.py` | 模板实例化为 plan + items |
| `backend/app/study_plan/utils/permission.py` | 灰度白名单 + 虚拟角色 |
| `backend/app/question_bank/api/v1/session.py` | 题库 session API（submit/abandon endpoint 末尾挂 hook） |
| `backend/scripts/instantiate_plan_for_user.py` | 一次性脚本：为指定用户实例化模板 |
| `mini/src/pages/study/index.vue` | 今日计划首页 |
| `mini/src/pages/study/item/index.vue` | 模块详情页（多态渲染） |
| `mini/src/pages/study/overview/index.vue` | 总体规划（日历网格） |
| `mini/src/pages/resource/index.vue` | 资料大厅（旧 study/index 迁移而来） |
| `mini/src/pkg/practice/session/index.vue` | 题库做题页（practice 跳转目标） |
| `backend/core/conf.py` | 白名单配置位置 |

---

## 8. 变更日志

| 日期 | 变更人 | 内容 |
|---|---|---|
| 2026-06-08 | null | 初版：完成 P0/P1 决策梳理，建立追踪体系 |
| 2026-06-09 | null | D17 + T1.0：资料大厅迁移至 `pages/resource/`，`pages/study/` 让位给学习规划；tabbar 注释化预留 `规划` tab |
| 2026-06-09 | null | T1.1：`app/study_plan` 五件套骨架就位 + 挂载主路由 + 导入链验证 |
| 2026-06-09 | null | T1.2：3 张核心表落地（plan / item / record），10 条 CHECK + 10 条索引；mapper 关系链验证通过 |
| 2026-06-09 | null | T1.3 + T1.4：模板 2 张表 + 导师学员关联表落地，补上 plan.template_id 外键；6 张表 18 条 CHECK + 19 条索引 |
| 2026-06-09 | null | T1.5：6 表已由 create_all 自动建好（列/约束/索引 100% 对齐 model）；落盘 init_tables.sql；mentor.assigned_by 改可空，待执行 1 条 ALTER |
| 2026-06-09 | null | T1.6 + T1.7：灰度白名单 + 依赖注入校验 + 21 个 Pydantic schema 落地；**Phase 1 全部 7 个任务完成** |
| 2026-06-09 | null | Phase 2 决策落定：D18 严格日历 / D19 Celery beat 跨天扫 / D20 错题选题 TODO（U10）/ D21 RBAC（superuser admin + mentor 角色） |
| 2026-06-09 | null | T2.1 + T2.2 + T2.3 + T2.7：6 个 dao + 完成判定 + 今日计划聚合服务；真实 db smoke + 10 条真值表测试通过 |
| 2026-06-09 | null | Phase 2 决策深化：D22-D25（ref 失效不校验 / 多 active / 合并展示 / extra 完全克隆）|
| 2026-06-09 | null | T2.4：模板实例化 service 完成；plan dao 重构（list_active_covering_date 替代单 plan 取法）；today_service 适配多 plan；端到端 db smoke 验证通过 |
| 2026-06-09 | null | T2.5 + T2.6：Celery 定时清理过期项任务（每天 0:30）+ 错题动态选题 MVP；任务自动注册 + beat schedule 落定 |
| 2026-06-09 | null | T2.8：20 个 endpoint 全部落地（学员/导师/管理三端），含 student_service 完整封装启动+完成业务流；FastAPI app 整体装配验证通过 |
| 2026-06-09 | null | T2.9：30 个 pytest 真值表测试通过；统一 20 个 endpoint 函数名加 study_plan_ 前缀（解决 fba 项目级唯一性约束）；**Phase 2 全部 9 个任务完成 → 后端 MVP 闭环就绪** |
| 2026-06-09 | null | T3.1 + D26：tabbar 启用规划 tab；后端 /me 追加虚拟角色 study_plan_internal；未命中用户完全看不到 tab |
| 2026-06-09 | null | T3.2：今日计划首页完整实现；SDK 同步生成 20 个 study_plan 方法；修复 dump_openapi.py 的陈旧 import 路径 |
| 2026-06-09 | null | 种子数据 + T3.3a：示范模板 SQL 落盘（国考 7 天试用）；review 类详情页完整闭环（学员可看 → 提交 → 进度更新）|
| 2026-06-09 | null | 修复 qbank/auth/me 遗漏虚拟角色（/me 接口统一 apply_virtual_roles）；user_id=18 加白名单 |
| 2026-06-09 | null | T3.9 + T3.10：总体规划页（日历网格）+ 学员端 /me/plans/{id}/items 和 /progress 接口；实例化脚本 instantiate_plan_for_user.py |
| 2026-06-09 | null | D27 + T3.5：practice lazy 绑定 session_key（start_item 按需调题库 create_session）；前端 practice 跳转题库 session 页 |
| 2026-06-09 | null | D28：题库 session 交卷自动回调 plan_item（session_hook.py，lazy import 避免循环依赖）；交卷即完成不卡正确率 |
| 2026-06-09 | null | D29：practice 退出行为明确——做一半退出保持 in_progress 可继续；无"放弃"无"跳过"；删 handle_session_abandoned |
