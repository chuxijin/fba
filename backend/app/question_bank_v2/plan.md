# question_bank_v2 错题本与复盘：设计与剩余工作

> 本轮已完成后端重构（去 FSRS、改客观派生调度、错题本状态机、自主录入可重练）与两处小程序止血。
> 本文前半是**已落地的设计**（读代码前先读这里），后半是**剩余工作**。
>
> 知识点掌握度、学习能力雷达图、知识体系细化规则和未来 IRT 考试能力报告见
> [`knowledge_mastery_design.md`](./knowledge_mastery_design.md)。

---

## 一、核心设计（已落地）

### 1.1 双时间线：重练自动、复盘手动

| | 重练线 | 复盘线 |
|---|---|---|
| 驱动 | 系统自动 | 用户主动 |
| 输入 | 客观作答（对错 × 用时） | 错因标签 / 知识点 / 总结 |
| 落点 | `wrong_state.next_practice_time` | `QbQuestionReview` 事件 |
| 推送 | **是** | **否** |
| 会过期 | 是 | 否 |

**推论：复盘不再打分。** 原 FSRS 要求用户主观评「记得牢不牢」，而系统从「这次对没对 + 比上次快还是慢」
就能客观推出来。所以 `CreateQuestionReviewParam` 已删掉 `rating` / `rating_source` / `outcome`，
`SubmitQuestionReviewResult` 已删掉 `forecast`。

### 1.2 三层职责

| 表 | 职责 | 本轮变化 |
|---|---|---|
| `QbWrongQuestionState` | 错题本状态 **+ 重练调度** | 新增 6 字段、3 个 partial index |
| `QbQuestionReview` | 复盘事件流（append-only） | 删 7 个 FSRS/调度字段 |
| `QbUserQuestionMastery` | **只**回答「掌握了没有」，供差异化导出 | 删 7 个调度字段、2 个到期索引 |

调度从 `mastery` 搬到 `wrong_state` 是规模决策：`mastery` 是**每道做过的题**一行
（日活 8000 × 人均 60 题/天 ≈ 48 万行/天，一年 1.7 亿行），`wrong_state` 只有做错过的题。
推送扫描因此变成**单表 partial index 扫描**，不再 join 大表。

`backend/common/fsrs` 未删 —— `app/vocab` 和 `app/gongkao` 仍在用，只是 `question_bank_v2` 不再引用。

### 1.3 客观派生调度（`service/practice_schedule_service.py`）

纯函数、整数运算、无外部库。

```
baseline = wrong_state.last_duration_ms（首次入本时那次答错的用时）

对 + 用时 ≤ baseline×0.8  → 4  又快又对
对 + 其他                  → 3  对但吃力
错 + 用时 ≥ baseline×1.2  → 2  慢且错，仍在调动记忆
错 + 其他                  → 1  又快又错，蒙或放弃

level: 1→归零  2→退一档  3→进一档  4→进两档
ladder = [10min, 30min, 1d, 2d, 4d, 7d, 15d, 30d]
next_practice_time = now + ladder[level]
```

退化分支：缺基线或缺用时 → 对 3 错 1；主观题 `is_correct is None` → 返回 None，不参与调度。

> 「错 + 更快 = 最差」这条需线上验证。建议先观察 `wrong_state.last_rating` 的四象限分布，
> 觉得反了就改 `derive_rating` 里那一行，其余全不用动。`DURATION_TOLERANCE = 0.2` 同理。

### 1.4 移出错题本的规则

```python
threshold = 1 if wrong_state.review_count > 0 else preference.mastery_threshold  # 默认 3
if wrong_state.correct_streak >= threshold:
    status = 'resolved'; next_practice_time = None; mastery.state = 'mastered'
```

**复盘过的题做对一次就够，没复盘的要连对 3 次。** 复盘意味着用户已经想清楚错因，
再做对就是真掌握；没复盘的做对可能只是蒙对或记住了选项位置。
这条规则让「复盘」这个动作产生实际收益，用户才有动机去做。

移出 = `status='resolved'`，**不是删除**。所以「考前看之前复盘过的题」零成本成立：
`GET /reviewed` 只按 `review_count > 0` 过滤，不看 status，已移出的题照样在。

再次答错会自动回到 active 并清掉 `resolved_time`。

### 1.5 用户旅程对照

```
第1天 刷题答错2道
  → status=active, review_count=0, last_duration_ms=那次用时, next_practice_time=+10min
第2天 别处做错 → POST /external
  → entry_source=manual, 同时写一条 event_type='capture'，时间线第一格不留空
第2天 「回顾错题模式」= POST /sessions {source_type:'wrong'}（已有，过滤 active）
  → 全错 → 派生 1 或 2 级 → 阶梯归零/退档
第2天 「错题复盘模式」= GET /pending-review 队列 + POST /{id}/reviews
  → review_count += 1；★ status 不变、next_practice_time 不变
第3天 全部连续做对
  → review_count>0 → 阈值降为 1 → 做对一次即 resolved + mastered
考前 GET /reviewed
  → 已移出的题仍在列表；GET /{id}/events 看完整时间线
```

### 1.6 自主录入的错题可进刷题系统

`CreateExternalWrongQuestionParam.answer` **已改为必填**。原来可空会让题目没有权威答案，
交卷时 `practice_service` 直接抛「题目缺少权威答案」500 —— 录入的题根本没法练。

其余链路本来就通，已确认：
- `crud_practice.get_user_candidates` 对 `QbBankItem` 是 outerjoin，`max_score` coalesce 到
  `question.default_score`，`display_config` 兜底 `{}`
- `QbPracticeSessionItem.bank_item_id` 可空
- `user_bank_item_progress_dao.apply_attempt(bank_item_id=None)` 提前返回 None
- 题库权限校验挂在 `if obj.bank_id is not None` 里，`source_type='wrong'` 不受影响

### 1.7 接口一览（`/api/v1/qbank-v2/wrong-questions`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `''` | 列表，支持 `status` / `entry_source` / `entry_scope(all\|bank\|external)` |
| GET | `/statistics` | 含 `reviewed_count` / `pending_review_count` / `due_count` |
| GET | `/due` | 到期重练；`limit` 空则取 `preference.review_daily_limit` |
| GET | `/reviewed` | ★ 复盘档案，不过滤 status，支持 `mastery_state` / `tag_id` / `knowledge_point_id` |
| GET | `/pending-review` | ★ 待复盘队列（`review_count=0 AND status=active`） |
| GET | `/dashboard` | ★ 错因与知识点分布 |
| GET | `/{id}` | ★ 详情，含答案解析 + `resolve_threshold`（还需连对几次） |
| PATCH | `/{id}` | ★ `{action}` = resolve/reopen/suspend/resume/pin/unpin |
| GET | `/{id}/events` | ★ 复盘时间线（capture + 所有 review） |
| POST | `/{id}/reviews` | 提交复盘，无评分 |
| POST | `/external` | 录入外部错题，答案必填 |

**路由顺序**：字面量路由全部注册在 `/{wrong_state_id}` 之前，否则被当路径参数解析成 422。
`api/v1/review.py` 顶部有注释标注。

看板的语义陷阱：分布来自 `QbQuestionReviewTag` / `QbQuestionReviewKnowledgePoint`
（用户复盘时**主观**选的），**不是** `QbQuestionKnowledgePoint`（题目**客观**标注）。
`get_statistics(group_by='knowledge_point')` 走的是后者，两者别混用。

### 1.8 接上了原本悬空的偏好配置

`mastery_threshold` / `review_reminder_*` / `review_daily_limit` 早就在 model + schema + 测试里，
但业务逻辑零消费方。本轮 `mastery_threshold` 和 `review_daily_limit` 已接上，
`review_reminder_*` 留给推送任务（见二.1）。

---

## 二、剩余工作

### 2.1 推送定时任务（未做）

`crud_review.scan_due_users()` 和 `notification_service.notify_practice_due()` 已就绪，缺调度器。

新建 `backend/app/task/tasks/qbank_v2/practice_due_tasks.py`，**每小时**跑一次
（因为 `review_reminder_time` 是用户本地时间 + 自定义时区）：

1. 按 `review_reminder_timezone` 分组换算，找出「当前本地小时 == `review_reminder_time` 小时」
   且 `review_reminder_enabled` 为真的用户
2. `scan_due_users(now=..., user_ids=候选)` 单表聚合
3. `due_count` 按 `review_daily_limit` 截断，超出前端显示 "30+"
4. 一个用户一条消息，`notify_practice_due(local_date=用户本地日期)` 已做同日幂等

`beat.py` 里 crontab 用 `7 * * * *`，别用 `0 * * * *` 撞整点任务。

> `app/task/tasks/qbank/mastery_tasks.py` 还 import V1 的 `question_bank.model.mastery`，
> 不要改它，等 V1 下线一起删。

### 2.2 差异化导出（未做）

维度全部现成，`mastery.state` 现在是可靠的单一来源：

| 维度 | 字段 |
|---|---|
| 掌握状态 | `mastery.state` = new/learning/review/mastered |
| 错题本 | `wrong_state.status` |
| 是否复盘 | `wrong_state.review_count > 0` |
| 来源 | `wrong_state.entry_source` |
| 错因 / 知识点 | `QbQuestionReviewTag` / `QbQuestionReviewKnowledgePoint` |

典型用法：「导出还没掌握的」`mastery_states=[learning]`；
「导出复盘过但还没做对的」`reviewed=true, wrong_statuses=[active]`。

**必须异步**：百万级下同步导出会打爆 worker 超时。接口只返回 `task_id`，
celery 生成后落对象存储，完成时发站内信带下载链接。PDF 走 9000 端口服务。

### 2.3 小程序页面收敛（部分完成）

**已改**：
- `pkg/mine/wrong-questions/index.vue` 统计字段改成 `active_count` / `pending_review_count` /
  `resolved_count`（原来用 `unmastered_count` / `mastered_count`，V2 没这两个字段，页面上是两个空白）
- `pkg/charts/wrong-review/index.vue` 三处 V1 端点（整页 404）换成 `api.qbankV2GetWrongReviewDashboard`；
  删掉依赖 V1 `knowledge-point-distribution?parent_id=` 的知识点下钻弹窗（V2 返回扁平列表）；
  死路由 `review-action`（`pages.json` 里不存在）改指错题列表

**未改**，目标形态：

```
我的错题  pkg/mine/wrong-questions/index.vue
├─ tab 待重练   → GET /due            红点 = total_due
├─ tab 待复盘   → GET /pending-review 红点 = 未复盘数
├─ tab 全部错题 → GET ''?status=active
├─ tab 已掌握   → GET ''?status=resolved
├─ 筛选 来源(题库/自主录入) · 题库分组 · 知识点分组 · 掌握状态
├─ 折叠卡片 错因/知识点分布 → GET /dashboard（把 charts/wrong-review 整页降级进来）
└─ 悬浮按钮 录入错题

错题复盘  pkg/mine/wrong-review/detail.vue   合并原 review-single.vue
├─ 题目 + 我的错答(last_wrong_response) + 答案解析
├─ 状态条 掌握状态 · 连对 N/M · 下次重练时间
├─ 复盘时间线 → GET /{id}/events
├─ 本次复盘表单 错因标签 + 知识点 + 总结 + 防错策略   ★ 无评分控件
└─ 提交 → POST /{id}/reviews
```

待迁移的 V1 页面（~3000 行）：`custom-import.vue`、`recognition-preview.vue`、`review-single.vue`。

「回顾错题模式」**不需要新页面** —— 就是 `createSession({source_type:'wrong'})`，复用现有 session 页。

> ⚠️ `backend/common/schema.py` 的 `SchemaBase` 是 `extra='ignore'`。小程序若还在发已删除的
> `rating` / `outcome`，**服务端静默丢弃不报错**。不能指望接口报错兜底，必须逐页核对字段。

### 2.4 图片 / OCR 录入（已完成）

- `POST /wrong-questions/assets` 上传用户私有错题图片，同时登记 `QbAsset` 和 `QbAssetLocation`
- `POST /wrong-questions/recognize` 复用视觉识别服务生成可编辑草稿
- `POST /wrong-questions/external` 通过 `assets` 保存原图和题干、选项、解析图片关联
- 小程序导入页不再调用 V1 `/qbank/wrong-review/recognize` 或直接调用 `/oss/upload`

---

## 三、本轮验证状态

- `pytest backend/app/question_bank_v2/tests/ -q` → **52 passed**
  （原先 39 项含 2 个 `DummyDB` 失败；那 2 个失败源于 `capture_external` 里的站内信调用，
  该调用已按二.1 的推送策略删除，失败随之消失）
- `test_review_service.py` 已按新设计重写：2×2 派生矩阵、阶梯边界、连对阈值、
  复盘过的题单次移出、复发重激活、无题库上下文的外部题、复盘不碰调度、手动状态迁移
- `ruff check` → 本轮改动的 9 个源文件 + 3 个测试文件全部 clean
  （`question_bank_v2` 下其余 ~58 项是既有迁移 diff 里的，未动）
- `npx vue-tsc --noEmit` → clean
- SDK 已重新生成（`dump_openapi.py` → 839 paths / 1166 ops / 1602 schemas）
- OpenAPI 契约断言已同步：paths 74→79，operation_ids 101→107

**未做迁移文件**：按要求，V2 表尚未上线，直接改 model 即可。
若已有测试库需要重建：`qbank_v2_wrong_question_state`、`qbank_v2_question_review`、
`qbank_v2_user_question_mastery` 三张表的结构变了。
