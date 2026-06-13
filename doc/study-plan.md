# 学习规划（Study Plan）模块设计与追踪文档

> 范围：公考领域的每日学习计划，覆盖复习/刷题/错题复盘/能力提升四类模块，
> 由导师手动配置（含模板机制），灰度内测，未开放给所有用户。
> 本文档同时是 **设计依据** 和 **开发追踪表**，从启动到上线全周期维护。

---

## 1. 决策记录（Decision Log）

每条决策包含：**结论 + 关键约束 + 后续可变性**。修改决策时追加新行，不要直接覆盖。

| # | 主题 | 结论 | 约束 / 备注 |
|---|---|---|---|
| D1 | 入口位置 | `规划` 不再占底部 tab，改放到用户中心 `学习资产` 区 | 移除 `mini/src/tabbar/config.ts` 中 `pages/study/index` 配置；入口由 `mini/src/pages/mine/index.vue` 控制 |
| D2 | 业务领域 | 首版仅 `公考（civil_service）` | 模型字段 `domain` 预留，未来扩展其他领域不动表结构 |
| D3 | 每日模块数 | 默认 4 个，可动态增减 | 由 `study_plan_item` 一对多关系天然支持，无需额外配置 |
| D4 | 模块类型枚举 | `review` / `practice` / `wrong_review` / `ability` | `ability` MVP 阶段**不实现**（前端独立功能未接后端）；枚举留位 |
| D5 | 复习内容承载 | 复用 `sys_content`，`app_code='gongkao'` | 学习内容与复习内容**共用同一池**；网盘链接放 `extra.cloud_links` JSONB |
| D6 | 刷题任务定义 | 多来源表达：题库 / 题库篇章 / 题库篇章+题型 / 知识点 / 指定题目 ID | 统一落到 `study_plan_item.ref_id + extra`；首次 start 时由题库 session 服务 lazy 创建 |
| D7 | 错题复盘 | 复用 `WrongQuestionReview` 表，不重复造轮子 | `study_plan_item` 与 `WrongQuestionReview` 通过 `study_plan_record.extra_data` 软关联 |
| D8 | 能力提升 | 先以静态能力目录接入学习计划，结果由小程序能力模块回写 | 后续再做能力数据持久化、能力画像和智能推荐 |
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
| D16 | 入口文案 | 用户中心入口文案为 `学习规划` | 仍由虚拟角色 `study_plan_internal` 控制可见性 |
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
| D30 | 能力画像知识节点 | 复用 `sys_category`，不新建 `study_question_category` | 知识点 / 解题思路 / 能力节点统一挂 `sys_category.id`，避免维护重复树 |
| D31 | 能力练习目录 | 后端维护 `study_ability_catalog`，静态目录作为兜底 | 管理端和小程序都以同一份能力 key / URL / 目标配置为准 |
| D32 | 能力绑定 | `study_ability_category_binding` 单独维护能力 key + mode 到分类节点的映射 | 一项能力可挂多个知识点 / 解题思路 / 能力节点，支持权重 |
| D33 | 能力原始记录 | 登录用户回写 `study_ability_attempt`，未登录用户保留本地练习和补传队列 | 导师端只看已同步到后端的数据 |
| D34 | 能力画像算法 | v1 采用正确率 75% + 速度 15% + 样本置信度 10% | 记录 `algorithm_version='ability_profile_v1'`，后续可升级 IRT/BKT |
| D35 | AI 接入预留 | AI 读取同一组画像表，不新增核心事实表 | 未来仅在需要缓存 AI 报告时另加报告/快照表 |
| D36 | 画像推荐计划项 | 首版不建推荐表，按画像实时生成计划项草稿 | API 返回 `strategy` / `strategy_version` / `reason_codes` / `payload`，后续可替换为 AI、缓存或人工干预策略 |

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
- `module_type='practice'`：`source_mode` 标识来源，支持 `bank` / `chapter` / `chapter_type` / `knowledge_point` / `question_ids`；常用字段包括 `chapter_id`、`question_types`、`knowledge_points`、`question_ids`、`question_count`、`required_accuracy`、`time_limit`、`shuffle`
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

#### `study_ability_catalog` — 能力练习目录
```
id              BIGINT PK
ability_key     VARCHAR(64)         -- 小程序能力唯一标识
title           VARCHAR(128)
category        VARCHAR(64)
url             VARCHAR(512)        -- 小程序入口 URL
domain          VARCHAR(32)
default_question_count INT NULL
default_minutes INT         -- 默认预计分钟
default_accuracy NUMERIC(5,4) NULL  -- 0..1
benchmark_seconds NUMERIC(8,2) NULL -- 单题速度基准
supports_study_plan BOOL
supports_result BOOL
is_active       BOOL
extra           JSONB NULL
```

#### `study_ability_category_binding` — 能力与分类节点绑定
```
id              BIGINT PK
ability_key     VARCHAR(64)
mode            VARCHAR(64) NULL    -- 可按能力模式细分
category_id     BIGINT FK -> sys_category.id
role            VARCHAR(32)         -- knowledge_point / solution_method / ability
weight          NUMERIC(6,4)
is_primary      BOOL
source          VARCHAR(32)         -- manual / ai / import
confidence      NUMERIC(6,4)
```

#### `study_ability_attempt` — 能力练习原始记录
```
id              BIGINT PK
user_id         BIGINT FK -> study_user_account.user_id
ability_key     VARCHAR(64)
client_session_id VARCHAR(64)       -- 幂等键
mode / difficulty / source
study_plan_item_id BIGINT NULL
study_plan_record_id BIGINT NULL
total_count / correct_count / wrong_count
duration_seconds / avg_seconds / score
metric_data     JSONB NULL
records         JSONB NULL          -- 小题明细
completed_at    TIMESTAMPTZ
completed_date  DATE
```

#### `study_ability_attempt_category` — 单次练习对分类节点的贡献
```
id              BIGINT PK
attempt_id      BIGINT FK -> study_ability_attempt.id
user_id         BIGINT
category_id     BIGINT FK -> sys_category.id
role / weight
total_count / correct_count / duration_seconds / score
completed_at / completed_date
```

#### `study_user_category_profile` — 用户分类画像
```
id              BIGINT PK
user_id         BIGINT
category_id     BIGINT FK -> sys_category.id
source_type     VARCHAR(32)         -- ability / question_bank
attempt_count / total_count / correct_count / duration_seconds
accuracy_rate / avg_seconds
mastery_score / speed_score / confidence_score / trend_score / weakness_score
last_attempt_at TIMESTAMPTZ
algorithm_version VARCHAR(32)

UNIQUE (user_id, category_id, source_type)
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
| POST | `/api/v1/study/student/ability-attempts` | 提交能力练习记录并更新画像 |
| POST | `/api/v1/study/student/ability-attempts/batch-sync` | 批量补传本地能力练习记录 |
| GET | `/api/v1/study/student/ability-profile` | 学员查看自己的能力画像 |

### 3.2 导师端 / 管理端（PC 后台）

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/study/plans` | 创建计划（可基于模板批量生成 items） |
| GET | `/api/v1/study/plans` | 计划列表（按学员/导师/状态筛选） |
| PUT | `/api/v1/study/plan/items/{item_id}` | 编辑单个模块 |
| POST | `/api/v1/study/plan/items` | 新增单个模块 |
| DELETE | `/api/v1/study/plan/items/{item_id}` | 删除模块 |
| GET | `/api/v1/study/plans/{plan_id}/progress` | 查看学员计划完成情况 |
| GET | `/api/v1/study/mentor/students/{student_id}/ability-profile` | 导师查看学员能力画像 |
| GET | `/api/v1/study/mentor/students/{student_id}/plan-item-recommendations` | 基于学员画像生成推荐计划项草稿 |
| POST | `/api/v1/study/templates` | 创建模板 |
| GET | `/api/v1/study/templates` | 模板列表 |
| POST | `/api/v1/study/mentors/assign` | 管理员分配导师 ↔ 学员 |
| POST | `/api/v1/study/admin/practice-sources/preview` | 管理端预览刷题来源可用题量 |
| GET/POST/PUT/DELETE | `/api/v1/study/admin/ability-catalog*` | 管理能力练习目录与默认目标 |
| GET/POST/PUT/DELETE | `/api/v1/study/admin/ability-bindings*` | 管理能力 key/mode 到 `sys_category` 的分类绑定 |

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

### 4.1 入口调整
- `规划` 不再作为底部 tab 展示
- `mini/src/pages/mine/index.vue` 的 `学习资产` 区增加 `学习规划` 入口
- `mini/src/tabbar/config.ts` 仅保留 `学习` / `我的` 两个底部 tab
- 学习规划入口继续根据虚拟角色 `study_plan_internal` 显示 / 隐藏

### 4.2 页面结构
```
pages/study/index                # 学习规划驾驶舱：首页阶段计划 + 本周目标 + 学习日历弹层 + 考点目标
pages/study/item/[id]            # 计划项详情（按 module_type 渲染不同视图）
pages/study/overview             # 总体规划：日历网格 + 进度环 + 当日明细展开
pages/study/history              # 历史记录（含未完成提醒、完成耗时、刷题正确率）
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
| T3.1 | 调整学习规划入口 | ✅ | `规划` 从底部 tab 移至用户中心 `学习资产`；后端 /me 接口命中白名单时追加虚拟角色，不命中用户看不到入口 |
| T3.2 | `pages/study/index.vue` 重构为今日计划首页 | ✅ | 完整今日聚合视图：进度卡 + 模块列表（4 类 module_type 各异图标）+ 历史提醒铃铛 + 资料大厅入口 + 查看总体规划入口；4 种异常态（loading/error/empty plan/empty items）；SDK 自动同步 20 个 study_plan 接口 |
| T3.3 | `pages/study/item/index.vue` 模块详情页（多态渲染） | ✅ | review：拉文章 + 网盘链接 + 我已读完按钮；practice：信息卡 + 开始/继续练习按钮 → 跳题库 session 页，交卷自动回调完成；wrong_review / ability 占位 |
| T3.4 | 复习模块组件（文章 + 网盘链接 + 已读按钮） | ✅ | 合并入 T3.3 的 review 类实现 |
| T3.5 | 刷题模块：lazy session 创建 + 交卷自动回调 | ✅ | D27/D28/D29；start_item 按需调题库 create_session，session_key 存 extra；交卷 hook 自动标 completed；做一半退出保持 in_progress 可继续 |
| T3.6 | 错题复盘模块 | ⏸️ | 本期不做，待错题反思能力完成后开放 |
| T3.7 | 历史记录页 | ✅ | 小程序历史页已落地：拉取我的计划全量 items，按历史待补 / 已完成 / 全部聚合展示，完成记录显示实际耗时与刷题正确率 |
| T3.8 | 灰度判断：根据用户白名单显示/隐藏 tab | ✅ | 已通过 T3.1 的虚拟角色机制完成（D26）|
| T3.9 | 总体规划页（日历网格） | ✅ | `pages/study/overview/index.vue`：拉 active 计划全量 items + progress，7 列日历网格 + 模块圆点 + 当日明细展开 |
| T3.10 | 学员端总体规划 API | ✅ | GET /me/plans/{id}/items + /progress，含 ownership 校验 |

### Phase 4 — 管理后台（PC，约 3 天）
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T4.1 | 计划管理页（列表 / 创建 / 编辑） | ✅ | PC 页已落地：按学员查计划、基于模板/空计划创建、计划主信息编辑/状态变更、计划项新增/编辑/删除 |
| T4.2 | 模板管理页 | ✅ | PC 页已落地：模板列表、新建、详情、基础信息编辑、模板项新增/编辑/删除 |
| T4.3 | 导师 ↔ 学员分配页 | ✅ | PC 页已落地：导师学员关系列表筛选、新增分配、按关系 ID 更新状态；后端 GET /api/v1/study/admin/mentors 已补齐 |
| T4.4 | 学员计划进度查看页（导师视角） | ✅ | PC 页已落地：按学员查询计划、选择计划、查看完成进度与每日明细 |
| T4.5 | 刷题任务来源构建器 | ✅ | PC 计划项/模板项统一支持题库、篇章、篇章题型、知识点树、指定题目 ID；含题量预览、题型/限时/正确率/题数目标配置 |

### Phase 5 — 联调与灰度上线
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T5.1 | 端到端联调（导师配 → 学员做 → 完成回写） | ✅ | 用户已确认真实账号链路 OK：admin 给 test123 / 桥水彼岸配任务，小程序做题交卷，PC 端查看回写 |
| T5.2 | 白名单加入种子用户 | ✅ | 用户确认 OK |
| T5.3 | 内测反馈收集 | ⏸️ | 用户确认本期不做 |

### Phase 6 — 能力画像与能力练习同步
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T6.1 | 建模：能力目录 / 绑定 / 练习记录 / 分类贡献 / 用户画像 5 表 | ✅ | 复用 `sys_category`；不创建 `study_question_category`；SQL 落盘 `ability_profile_tables.sql` |
| T6.2 | 后端 service + API：提交能力记录、批量补传、学员/导师画像查询 | ✅ | 能力提交会尝试自动完成 study_plan_item；完成失败不影响原始记录和画像沉淀 |
| T6.3 | 小程序能力练习结算回写与未登录补传队列 | ✅ | 登录时提交后端；未登录时本地排队，App 启动账号初始化后自动补传 |
| T6.4 | PC 管理后台能力画像展示 | ✅ | 新增导师端能力画像页，按学员 ID 查看掌握度 / 薄弱度 / 正确率 / 速度 |
| T6.5 | 题库答题数据接入 `study_user_category_profile(source_type='question_bank')` | ✅ | 代码已接入题库交卷链路；系统启动自动建表后即可按知识点沉淀题库画像 |

### Phase 7 — 能力画像产品化
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T7.1 | 小程序个人能力画像页 | ✅ | 规划首页新增入口；首屏雷达图，支持综合 / 能力练习 / 题库刷题切换，点节点查看详情 |
| T7.2 | PC 导师端画像增强 | ✅ | 导师端画像页已升级为学员选择、综合 / 能力 / 题库视图、知识点树筛选、雷达图与节点详情联动 |
| T7.3 | 能力目录与分类绑定运营页 | ✅ | PC 新增能力运营页；后端支持目录 CRUD、绑定 CRUD、静态目录落库与 sys_category 树选择 |
| T7.4 | 画像驱动推荐计划项 | ✅ | 基于薄弱节点推荐能力练习 / 刷题来源 / 目标题数与正确率，PC 端可一键加入学员计划 |

### Phase 8 — 小程序学习规划体验优化
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T8.1 | 小程序学习规划主页面产品化改版 | ✅ | 参考竞品学习计划页，主页面改为阶段计划 / 本周目标 / 学习日历弹层 / 考点目标；首版复用现有 plan/items/progress 聚合 |
| T8.2 | 小程序学习规划主页面视觉精修 | ✅ | 收敛主页面视觉层级：统一轻卡片、细边框、低阴影、标题标识、周目标圆环与学习日历弹层选中态 |
| T8.3 | 小程序学习规划阶段导航组件化 | ✅ | 阶段导航从手写异形卡切换为 `wd-tabs`，用局部 CSS 变量和深度样式控制导航视觉，并支持切换加载对应阶段计划 |
| T8.4 | 小程序学习规划考点目标组件化 | ✅ | 考点目标路径从手写虚线节点切换为 `wd-steps` 竖向点状步骤条，统一考点标题、题量和预计时长展示 |

---

### T5.1 端到端联调清单

| 环节 | 检查结论 |
|---|---|
| 管理员分配导师学员 | ✅ 管理端 `GET/POST/PUT /api/v1/study/admin/mentors*` 已可维护关系 |
| 后台 RBAC 菜单角色 | ✅ `学习规划管理员` 绑定 12 个菜单 / 按钮权限；`学习规划导师` 绑定 8 个导师端菜单 / 按钮权限 |
| 真实账号联调数据 | ✅ 导师 `admin`(user_id=1) 已绑定学习规划角色；学员 `test123` / `桥水彼岸`(user_id=18) 已建立 active 关系；联调计划 `plan_id=3` |
| 导师创建/维护计划 | ✅ 导师端创建、查询、编辑计划时校验当前导师与学员 active 关系；superuser 保留旁路 |
| 导师维护计划项 | ✅ 新增导师端 `POST/PUT/DELETE /api/v1/study/mentor/items*`；PC 计划项保存已切到导师端接口 |
| 学员查看今日任务 | ✅ 学员端 `today` 按 active 计划和当日 items 聚合，保留多 active 计划合并展示 |
| review 完成回写 | ✅ `complete_item` 校验 `read_acknowledged=True` 后写 record 并标 completed |
| practice 启动 | ✅ `start_item` lazy 创建题库 session；支持题库、篇章、篇章题型、知识点、指定题目 ID；已失效 / abandoned `session_key` 会重建 |
| practice 交卷回写 | ✅ 题库 submit 后调用 `session_hook.handle_session_completed`，按 `extra.session_key` 回写 record 并标 completed |
| 进度查看 | ✅ 学员端和导师端 progress 均按 plan items 统计 completed / total / percent |

---

## 6. 剩余任务 / 细节优化 Backlog

> 当前学习规划主链路已经完成：导师配计划 → 学员执行 → 刷题 / 能力数据回写 → PC 查看进度、历史、能力画像和画像推荐计划项。
> 下面事项属于**不阻塞内测的增强项**，后续按真实使用反馈逐项优化。

### 6.1 建议优先处理

| # | 事项 | 状态 | 优先级 | 说明 |
|---|---|---|---|---|
| U1 | 错题复盘计划项闭环 | ⬜ | P1 | `wrong_review` 枚举和完成判定已预留；待错题反思页稳定后，接入小程序执行页、动态选题、完成回写 |
| U2 | 计划项体验细节优化 | ⬜ | P1 | 根据真实使用微调 PC / 小程序的标题、目标展示、日期选择、排序、空状态、错误提示 |
| U3 | 画像推荐规则调参 | ⬜ | P1 | 基于真实数据观察推荐质量，调整权重、阈值、目标题量和目标正确率；每次调整递增 `strategy_version` |
| U4 | 能力画像解释增强 | ⬜ | P1 | 在学员端和导师端补充更清楚的薄弱原因、样本量可信度、速度偏慢说明，降低误读 |

### 6.2 中期增强

| # | 事项 | 状态 | 优先级 | 说明 |
|---|---|---|---|---|
| U5 | 知识图谱可视化 | ⬜ | P2 | 复用 `sys_category`，围绕知识点 / 解题思路 / 能力节点做图谱展示；等知识点树更完整后再做 |
| U6 | 高级推荐算法 / AI 推荐 | ⬜ | P2 | 当前 T7.4 为规则引擎；后续可升级为 AI、IRT、BKT 或混合策略，继续复用 `payload` / `strategy_version` 契约 |
| U7 | 计划完成提醒推送 | ⬜ | P2 | 可接订阅消息、公众号或站内提醒；优先提醒今日未完成、历史待补、连续中断 |
| U8 | 运营报表与导出 | ⬜ | P2 | 面向导师 / 运营统计计划完成率、刷题正确率、薄弱点变化、学员活跃度，可后续补导出 |
| U9 | 错题复盘策略升级 | ⬜ | P2 | 首版动态选题规则较简单；后续可接艾宾浩斯遗忘曲线、错因标签、能力画像薄弱点 |

### 6.3 暂缓项

| # | 事项 | 状态 | 优先级 | 说明 |
|---|---|---|---|---|
| U10 | 导师在小程序端配置计划 | ⏸️ | P3 | 首版只支持 PC 后台；若导师移动端使用频繁，再做小程序导师端 |
| U11 | 学员申请导师 + 导师审批 | ⏸️ | P3 | 当前为管理员分配导师学员关系；业务需要开放自助绑定时再做 |
| U12 | 灰度方案数据库化 | ⏸️ | P3 | 当前白名单 / 虚拟角色可用；用户明确灰度方案先放一下，后续再从配置升级为数据库白名单或标签灰度 |

---

## 7. 关键引用文件清单

| 文件 | 作用 |
|---|---|
| `backend/app/study_plan/service/session_hook.py` | 题库 session 交卷回调：自动完成 plan_item |
| `backend/app/study_plan/service/student_service.py` | 学员端业务编排：start/complete + practice session lazy 创建 |
| `backend/app/study_plan/service/mentor_service.py` | 导师端关系归属校验 |
| `backend/app/study_plan/service/completion.py` | 完成判定四类逻辑（review/practice/wrong_review/ability） |
| `backend/app/study_plan/service/ability_profile.py` | 能力练习记录提交、分类贡献和用户画像聚合 |
| `backend/app/study_plan/service/ability_catalog.py` | 能力目录静态兜底、数据库运营目录与分类绑定管理 |
| `backend/app/study_plan/service/recommendation_service.py` | 画像驱动计划项推荐规则引擎，输出可直接创建的计划项草稿 |
| `backend/app/study_plan/schema/recommendation.py` | 推荐计划项响应结构与扩展字段约定 |
| `backend/app/study_plan/sql/ability_profile_tables.sql` | 能力画像 5 表建表脚本 |
| `backend/app/study_plan/service/template_service.py` | 模板实例化为 plan + items |
| `backend/app/study_plan/utils/permission.py` | 灰度白名单 + 虚拟角色 |
| `backend/app/question_bank/api/v1/session.py` | 题库 session API（submit/abandon endpoint 末尾挂 hook） |
| `backend/scripts/insert_study_plan_menu.py` | 一次性脚本：录入 PC 管理后台学习规划菜单 |
| `backend/scripts/bind_study_plan_roles.py` | 一次性脚本：创建学习规划角色并绑定菜单权限 |
| `backend/scripts/prepare_study_plan_e2e.py` | 一次性脚本：准备真实账号端到端联调数据 |
| `backend/scripts/instantiate_plan_for_user.py` | 一次性脚本：为指定用户实例化模板 |
| `mini/src/pages/study/index.vue` | 学习规划驾驶舱：首页阶段计划、本周目标、学习日历弹层、考点目标 |
| `mini/src/pages/study/item/index.vue` | 模块详情页（多态渲染） |
| `mini/src/pages/study/overview/index.vue` | 总体规划（日历网格） |
| `mini/src/pages/study/ability-profile/index.vue` | 小程序个人能力画像页 |
| `frontend/apps/web-antdv-next/src/views/study-plan/ability-profile/index.vue` | PC 导师端学员能力画像页 |
| `frontend/apps/web-antdv-next/src/views/study-plan/ability-catalog/index.vue` | PC 能力目录与分类绑定运营页 |
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
| 2026-06-10 | null | Phase 4 PC 管理后台状态同步：计划/模板/导师分配页进入可用骨架（🟡），导师进度查看页完成（✅）；全量 `pnpm run typecheck` 已通过 |
| 2026-06-10 | null | T4.3：导师学员关系列表接口 + PC 筛选列表补齐；分配/更新状态后自动刷新列表 |
| 2026-06-10 | null | T4.1：计划主信息编辑 + 状态变更补齐；PC 计划管理页支持完整计划生命周期维护 |
| 2026-06-10 | null | T4.2：模板项新增/编辑/删除接口 + PC 模板详情抽屉维护能力补齐；**Phase 4 全部完成** |
| 2026-06-10 | null | T5.1 代码级联调：补导师端 active 关系校验、导师计划项 CRUD、practice 多配置 session 创建与 abandoned session_key 兜底重建；待真实账号自测后转 ✅ |
| 2026-06-10 | null | T5.1 RBAC 落库：录入 PC 菜单并新增 `学习规划管理员` / `学习规划导师` 两个专用角色，分别绑定全量管理权限与导师端权限 |
| 2026-06-10 | null | T5.1 真实账号联调数据：`admin`(1) → `test123` / `桥水彼岸`(18)，基于 `国考冲刺 · 数量关系 7 天试用` 模板创建 `plan_id=3` |
| 2026-06-10 | null | T4.5：PC 刷题任务来源构建器完成，支持题库/篇章/篇章题型/知识点/指定 ID + 题量预览；后端新增 admin practice source preview 接口 |
| 2026-06-10 | null | T3.7：小程序历史记录页完成，支持历史待补 / 已完成 / 全部筛选，展示完成耗时与刷题正确率；T5.1/T5.2 按真实账号联调确认转 ✅，T5.3 本期暂停 |
| 2026-06-10 | null | D30-D35 + T6.1/T6.2：能力画像数据形态落定，新增 5 表 ORM/SQL、能力练习提交与学员/导师画像 API |
| 2026-06-10 | null | T6.3/T6.4：小程序能力结算改走能力练习提交接口，支持未登录本地队列补传；PC 新增导师端能力画像页 |
| 2026-06-10 | null | T6.5：题库交卷后按 `study_question.knowledge_point` 聚合到 `study_user_category_profile(source_type='question_bank')`；未建表时不影响交卷主链路 |
| 2026-06-10 | null | T7.1：小程序规划首页新增能力画像入口，画像页以雷达图为首屏，点击节点进入掌握度 / 正确率 / 速度 / 样本详情 |
| 2026-06-10 | null | T7.3：PC 能力运营页完成，支持维护能力目录、默认目标、启停状态，以及能力 key/mode 到 `sys_category` 的绑定权重 |
| 2026-06-11 | null | T7.2：PC 导师端能力画像增强完成，支持导师学员选择、综合画像、分类树筛选、雷达图节点点击和来源拆分详情 |
| 2026-06-11 | null | D36 + T7.4：画像推荐计划项完成；后端实时生成能力 / 刷题计划项草稿，PC 端支持按推荐加入学员计划，并保留策略版本与 payload 扩展口 |
| 2026-06-12 | null | 学习规划主链路进入细节优化阶段；整理剩余 Backlog，按 P1/P2/P3 区分错题复盘闭环、体验优化、推荐调参、图谱/AI/提醒等后续事项 |
| 2026-06-12 | null | D1/D16/T3.1 调整：学习规划不再占底部 tab，入口迁移到用户中心 `学习资产` 区，并继续沿用 `study_plan_internal` 白名单可见控制 |
| 2026-06-12 | null | T8.1 完成首版：小程序学习规划主页面改为产品化驾驶舱，先用现有计划数据聚合阶段、本周目标、学习日历与考点目标 |
| 2026-06-12 | null | T8.2 完成：小程序学习规划主页面做视觉精修，降低阴影和杂色，统一卡片层级、标题标识、周目标圆环与日历弹层状态 |
| 2026-06-13 | null | T8.3 完成：小程序学习规划阶段导航改用 `wd-tabs`，减少手写异形 UI，并在切换阶段时加载对应计划项和进度 |
| 2026-06-13 | null | T8.4 完成：小程序学习规划考点目标改用 `wd-steps` 竖向点状步骤条，替代手写虚线路径节点 |
