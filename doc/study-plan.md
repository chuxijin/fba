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
| D11 | 完成判定·刷题 | 题目全部做完 **且** 达到设定正确率 | `study_plan_item.extra` 存 `required_accuracy`（默认 0.6） |
| D12 | 完成判定·错题复盘 | 所有动态选出的错题均填完 `reasons` + `summary` | 与 `WrongQuestionReview` 表的 `reasons` + `summary` 字段对齐 |
| D13 | 跨天处理 | 当日未完成 → 进历史记录，次日不在今日列表显示，仅提醒 | 计划按日期驱动；中断时全链条**顺延**（不丢失内容） |
| D14 | 导师 ↔ 学员关系 | 多对多，**管理员分配** | 新增 `study_mentor_student` 关联表；学员不能自行申请导师 |
| D15 | 灰度策略 | 方案 A：硬编码 `STUDY_PLAN_WHITELIST` 配置 | 用户量上来后切换数据库白名单表；不做百分比 / 标签灰度 |
| D16 | tab 名称 | `规划`（已写入 tabbar 注释草案） | 强调每日任务流属性；后续也可在 customTabbarList 微调 |
| D17 | 资料大厅归位 | 旧 `pages/study/index.vue` 迁移至 `pages/resource/index.vue` | 让 `pages/study/` 完全归学习规划；不上 tabbar，作为辅助入口由学习规划首页引出 |

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
| POST | `/api/v1/study/plan/items/{item_id}/start` | 标记开始；错题复盘类型在此动态计算并返回错题列表 |
| POST | `/api/v1/study/plan/items/{item_id}/complete` | 提交完成；服务端校验是否满足完成条件 |
| GET | `/api/v1/study/plan/history` | 历史计划（含未完成项） |
| GET | `/api/v1/study/plan/me` | 当前用户的计划概览（含绑定导师） |

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

### 3.3 完成判定逻辑（service 层伪代码）
```
def can_complete(item, payload):
    if item.module_type == 'review':
        return payload.get('read_acknowledged') is True
    if item.module_type == 'practice':
        required = item.extra.get('required_accuracy', 0.6)
        accuracy = payload['correct_count'] / payload['total_count']
        return payload['total_count'] == expected_total and accuracy >= required
    if item.module_type == 'wrong_review':
        # 校验所有动态错题均已写入 WrongQuestionReview，且 reasons + summary 非空
        return all_reviewed_with_reasons_and_summary(item, payload)
    if item.module_type == 'ability':
        raise NotImplementedError  # MVP 不实现
```

---

## 4. 前端结构

### 4.1 tabbar 调整
- 解开 `mini/src/tabbar/config.ts` 中 `pages/study/index` 配置
- practice 文案 `学习` → `刷题`
- 新 tab 文案待定（D16）

### 4.2 页面结构
```
pages/study/index                # 规划 tab 首页：今日计划 + 进度 + 子模块入口
pages/study/item/[id]            # 计划项详情（按 module_type 渲染不同视图）
pages/study/history              # 历史记录（含未完成提醒）
pages/study/mentor               # 我的导师（P2 加）
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
| T1.3 | 建模：`study_plan_template` + `study_plan_template_item` | ⬜ | |
| T1.4 | 建模：`study_mentor_student` | ⬜ | |
| T1.5 | Alembic 迁移脚本生成 | ⬜ | |
| T1.6 | `STUDY_PLAN_WHITELIST` 配置 + 依赖注入校验 | ⬜ | 写在 `core/conf.py` + 路由依赖 |
| T1.7 | Schema 定义（Pydantic） | ⬜ | 严格遵循 `app/admin/schema/user.py` 风格 |

### Phase 2 — 后端业务（约 4 天）
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T2.1 | CRUD：`study_plan` / `item` / `record` | ⬜ | |
| T2.2 | CRUD：`template` / `mentor_student` | ⬜ | |
| T2.3 | Service：今日计划查询（含进度计算） | ⬜ | |
| T2.4 | Service：模板 → 实例化为 plan + items | ⬜ | 关键复杂度点 |
| T2.5 | Service：跨天处理（按日期定时 job 标记未完成） | ⬜ | 可用 APScheduler 或独立 cron |
| T2.6 | Service：错题复盘动态选题（首版规则：近 7 天未掌握 top N） | ⬜ | |
| T2.7 | Service：完成判定四类逻辑 | ⬜ | 参见 §3.3 |
| T2.8 | API 路由（学员端 6 个 + 后台端 9 个） | ⬜ | 见 §3.1/§3.2 |
| T2.9 | 关键 service 单元测试 | ⬜ | 重点测完成判定、模板实例化、跨天 |

### Phase 3 — 前端（小程序）（约 3 天）
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| T3.1 | 调整 `tabbar/config.ts`，新增规划 tab | ⬜ | D1 |
| T3.2 | `pages/study/index.vue` 重构为今日计划首页 | ⬜ | 复用现有 935 行视情决定 |
| T3.3 | `pages/study/item/[id].vue` 模块详情页（多态渲染） | ⬜ | |
| T3.4 | 复习模块组件（文章 + 网盘链接 + 已读按钮） | ⬜ | |
| T3.5 | 刷题模块跳转 + 完成回调 | ⬜ | 与现有 practice 模块联动 |
| T3.6 | 错题复盘模块跳转 + 完成回调 | ⬜ | 与现有错题复盘联动 |
| T3.7 | 历史记录页 | ⬜ | |
| T3.8 | 灰度判断：根据用户白名单显示/隐藏 tab | ⬜ | |

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

---

## 7. 关键引用文件清单

| 文件 | 作用 |
|---|---|
| `backend/app/content/model/content.py` | 复习内容承载（`sys_content`） |
| `backend/app/question_bank/model/question.py` | 题目源 + `knowledge_point` 字段 |
| `backend/app/question_bank/model/wrong_review.py` | 错题复盘记录表 |
| `backend/app/question_bank/model/practice.py` | 错题本（`WrongQuestionBook`） |
| `mini/src/tabbar/config.ts` | tabbar 配置（已在注释中预留 `规划` tab，开发完成后解开） |
| `mini/src/pages/study/index.vue` | 新建占位页面，待学习规划首页实现 |
| `mini/src/pages/resource/index.vue` | 资料大厅（旧 `pages/study/index.vue` 迁移而来，保留原功能） |
| `mini/src/pkg/resource/` | 资料搜索 + 资料详情子页 |
| `mini/src/pkg/ability/` | 已有 7 个能力练习子模块（待 U1 接入后端）|
| `backend/core/conf.py` | 白名单配置位置 |

---

## 8. 变更日志

| 日期 | 变更人 | 内容 |
|---|---|---|
| 2026-06-08 | null | 初版：完成 P0/P1 决策梳理，建立追踪体系 |
| 2026-06-09 | null | D17 + T1.0：资料大厅迁移至 `pages/resource/`，`pages/study/` 让位给学习规划；tabbar 注释化预留 `规划` tab |
| 2026-06-09 | null | T1.1：`app/study_plan` 五件套骨架就位 + 挂载主路由 + 导入链验证 |
| 2026-06-09 | null | T1.2：3 张核心表落地（plan / item / record），10 条 CHECK + 10 条索引；mapper 关系链验证通过 |
