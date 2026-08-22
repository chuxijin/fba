# 申论 Agent 生产上线与后续交接

更新时间：2026-08-22

## 1. 本次上线范围

本次生产环境只上线申论批改 Agent：

- Agent 键：`shenlun.grading`
- 工作流键：`shenlun-grading`
- 当前工作流版本：`shenlun-grading-v5`
- 数据源：`backend/app/question_bank_v2`
- 额度档案：`agent.shenlun.grade`
- 部署方式：单个后端 worker

申论教练相关代码保留在同一插件中，但默认关闭，不属于本次上线范围：

```toml
AGENT_SHENLUN_ENABLED = true
AGENT_SHENLUN_COACH_ENABLED = false
```

路由注册和应用启动恢复均受上述开关控制。生产环境保持
`AGENT_SHENLUN_COACH_ENABLED = false`，不会暴露教练接口，也不会启动教练后台任务。

## 2. 申论批改已具备的能力

- 从题库 V2 作答事实读取题目、材料、参考答案和已发布解析
- 多参考答案共识、Rubric 构建、持久化与复用
- 逐采分点命中、部分命中、遗漏判断
- 答案原文和材料证据定位
- 结构、表达、格式、字数和内容评分
- 独立复核、Schema Repair 和质量校验
- 总体评价、采分点表格、原文批注、材料领读、优化建议和修改版答案
- 历史作答和相似题检索，相似题只作评分先例
- 人工整卷分锚点校准，无有效策略时使用原始评分
- Agent 运行持久化、步骤审计、幂等、失败重试、SSE 和重启恢复
- 人工纠正采分点，并按范围失效当前报告或题目 Rubric
- 成功结果投影回 `question_bank_v2`
- 强制重新批改时更新到最新运行引用，但不重复累计题库统计
- 额度预检、幂等消耗和最终失败退款

## 3. 生产接口

```text
POST /api/v1/agent/shenlun/attempts/{attempt_id}/grading
GET  /api/v1/agent/shenlun/runs/{run_id}
POST /api/v1/agent/shenlun/runs/{run_id}/retry
POST /api/v1/agent/shenlun/runs/{run_id}/feedback
GET  /api/v1/agent/shenlun/runs/{run_id}/stream
```

启动请求示例：

```json
{
  "force_regenerate": false,
  "model_name": null
}
```

启动成功后返回 `run_id` 和 `stream_url`。客户端可以订阅 SSE，也必须保留
`GET /runs/{run_id}` 轮询或断线恢复能力。

## 4. 输入前置条件

批改入口要求：

- `attempt_id` 属于当前登录用户
- 作答内容非空
- 题目存在于 `question_bank_v2`
- `qbank_v2_question_answer.grading_method = 'rubric'`
- 题目关联材料版本可读取
- 至少有可用参考答案、解析或材料证据用于构建 Rubric

如果申论题只导入了题干，没有材料、参考答案或解析，接口即使能启动，也无法保证批改质量。

## 5. 数据库部署

按生产数据库类型执行初始化脚本：

```text
backend/plugin/agent/sql/postgresql/init.sql
backend/plugin/agent/sql/postgresql/init_snowflake.sql
backend/plugin/agent/sql/mysql/init.sql
backend/plugin/agent/sql/mysql/init_snowflake.sql
```

只选择与当前数据库和主键模式匹配的一份，不要重复执行不同数据库版本。

本插件会使用以下批改相关表：

- `agent_run`
- `agent_run_step`
- `agent_rubric`
- `agent_grading_feedback`
- `agent_calibration_anchor`
- `agent_calibration_policy`

初始化脚本还包含后续教练表。保留这些空表没有副作用；教练开关关闭时不会使用。

## 6. 额度配置

批改使用：

```text
profile_code = agent.shenlun.grade
resource_type = agent_shenlun
resource_id = 1
action = access
```

处理顺序：

1. 创建运行前执行额度预检，不扣减。
2. 后台任务成功认领后按 `shenlun_grading_run:{run_id}` 幂等扣减。
3. 成功完成后记录 `consumed`。
4. 最终失败时按原账本或每日体验记录退款。
5. 退款暂时失败时保存 `refund_pending`，不得直接当作已退款。

上线前必须由业务侧确认生产会员授权、每日体验次数和实际扣减规则。

## 7. 单 worker 部署约束

当前 `AgentEventBus` 是进程内 SSE 事件总线，因此本次使用单 worker：

- 不要开启 Uvicorn/Gunicorn 多 worker。
- 不要同时运行多个相同后端实例并通过负载均衡随机分发 SSE。
- 当前默认 Agent 并发数为 2，这表示一个 worker 内最多同时执行两个批改任务。
- 单 worker 不等于只能同时服务一个普通 HTTP 请求。

推荐配置：

```toml
AGENT_SHENLUN_MAX_CONCURRENCY = 2
AGENT_SHENLUN_STALE_SECONDS = 900
```

如果未来要多 worker 或多实例，必须先把事件总线迁移到 Redis Stream、Redis Pub/Sub
或其他跨进程消息系统，并验证断线重连和终态事件重放。

## 8. 重启与恢复

- 运行状态保存在 `agent_run`，不是只存在内存。
- 后台运行通过数据库条件更新原子认领，避免同一任务被重复执行。
- 执行期间定时刷新心跳。
- 服务正常关闭时，已认领但未完成的运行会重新进入恢复队列。
- 应用启动时恢复 `queued` 和超过陈旧阈值的 `running` 任务。
- SSE 连接在服务重启时会断开，客户端需重新查询运行详情或重新建立 SSE。

## 9. 已完成验证

代码验证：

```text
ruff: passed
backend/plugin/agent tests: 46 passed
Python compile/import: passed
```

开发数据库真实验证：

- 开发库共有 79 条题库 V2 作答。
- 其中 2 条符合 `rubric` 申论批改入口，来自同一道归纳概括题。
- 该题包含 4 份材料和 8 份已发布解析。
- 已成功完成 3 次新 Agent 批改。
- 最近一次真实重跑：`run_id=3`，耗时约 48 秒。
- 结果：10/10、5 个采分点、质量校验通过、150 字修改版答案。
- 额度状态：`consumed`。
- 题库作答已更新并指向最新 `run_id=3`。

当前真实样本只覆盖归纳概括题，不能据此证明综合分析、提出对策、公文和大作文的模型质量。

## 10. 上线后观察项

上线初期建议每日检查：

- `agent_run` 的成功率、平均耗时和失败原因
- 长时间停留在 `queued` 或 `running` 的任务
- `config_snapshot.quota.status = 'refund_pending'` 的运行
- `result_payload.status` 和 `score_status` 是否为 `valid`
- `quality_check.passed` 是否为真
- 报告是否包含有效修改版答案
- `qbank_v2_question_attempt.grading_result.agent_run_id` 是否指向最新成功运行
- 分数是否明显集中在满分或极低分
- 用户对采分点错误、证据不符和修改版答案的反馈

建议先灰度给少量用户，积累不同题型样本后再扩大流量。

## 11. 暂不上线但已存在的申论教练能力

代码位置：

```text
backend/plugin/agent/api/v1/shenlun_coach.py
backend/plugin/agent/schema/coach.py
backend/plugin/agent/service/coach_service.py
backend/plugin/agent/service/coach_intent.py
backend/plugin/agent/service/coach_recommendation.py
backend/plugin/agent/crud/crud_coach.py
backend/plugin/agent/model/coach.py
```

已实现：

- 教练会话创建、列表、详情和归档
- 多轮消息持久化和最近消息注入
- 批改报告上下文注入
- 长期记忆
- 训练计划生成、查询和任务完成
- 训练数据分析
- 自然语言意图规划
- 基于题库 V2 的下一题推荐
- 批改报告、题目、个人笔记和记忆组成的证据卡
- 同步对话和异步运行
- AgentRun 步骤轨迹、SSE、幂等、心跳和重启恢复
- `agent.shenlun.coach` 额度消耗和失败退款

暂不上线原因：

- 尚未用足够真实多轮会话做质量验收
- 知识库 RAG、模块级全量历史分析和 YanShen 评测体系尚未完全对齐
- 当前事件总线不支持多 worker
- 前端交互尚未接入

不要删除上述代码；后续通过开启 `AGENT_SHENLUN_COACH_ENABLED` 继续联调。

## 12. 后续开发顺序

建议按以下顺序推进：

1. 扩充不同申论题型的真实批改评测集。
2. 建立 YanShen 与新 Agent 的并行报告对比和质量阈值。
3. 补齐教练的知识库索引、模块级覆盖统计、笔记专用检索和证据充足度分级。
4. 补教练多轮对话评测、事实一致性和长期记忆管理接口。
5. 将 SSE 事件总线迁移到 Redis，支持多 worker、多实例。
6. 接入申论教练前端并进行小范围灰度。
7. 在相同运行平台中扩展英语作文 Agent 和面试 Agent，使用独立的 `agent_key`、`workflow_key` 和额度档案。

## 13. 关键参考文件

批改入口与运行：

```text
backend/plugin/agent/api/v1/shenlun_grading.py
backend/plugin/agent/service/shenlun_service.py
backend/plugin/agent/service/shenlun/pipeline.py
backend/plugin/agent/service/shenlun/report.py
backend/plugin/agent/service/adapter/qbank_v2_adapter.py
backend/plugin/agent/service/adapter/qbank_v2_projection.py
backend/plugin/agent/service/access/quota.py
backend/plugin/agent/hooks.py
```

YanShen 对齐参考：

```text
D:/100_Work/101_Program/Proj/YanShen/gongkao/agent_graph.py
D:/100_Work/101_Program/Proj/YanShen/gongkao/agent_rag.py
D:/100_Work/101_Program/Proj/YanShen/gongkao/agent_chat.py
D:/100_Work/101_Program/Proj/YanShen/gongkao/agent_coach.py
D:/100_Work/101_Program/Proj/YanShen/gongkao/agent_eval.py
```

旧目录 `backend/plugin/agents` 已废弃，不属于本实现，不应继续作为申论 Agent 的开发基础。
