# 智能批改 Agent

本插件位于 `backend/plugin/agent`，与旧的 `backend/plugin/agents` 完全隔离。
当前实现 `shenlun.grading` 和 `shenlun.coach`，输入只来自 `question_bank_v2` 的作答事实、题目材料、权威答案配置和已发布解析。

当前生产上线范围、单 worker 约束和后续交接见 [HANDOFF.md](./HANDOFF.md)。申论教练默认通过
`AGENT_SHENLUN_COACH_ENABLED = false` 关闭。

申论批改报告包含：

- 多参考答案轻量语义聚类、融合和可复用评分基准快照
- 逐点命中、部分命中、未命中和答案原文证据定位
- 题型维度评分、总分、置信度和质量校验
- 原文批注、材料领读、优化建议和修改版答案
- 按 25 格答题纸核算修改版答案字数，超限时在模型调用额度内自动压缩
- 内部百分制评分、题目实际满分展示分，以及基于真实整卷人工分的考场锚点校准
- 锚点与策略独立持久化；至少 4 个锚点、3 套试卷且留一试卷验证改善后才会激活
- 批改时按特定试卷、题型、全局顺序自动选择策略，无有效策略时保持原始评分
- 从 `question_bank_v2` 检索同题型历史作答，个性化结论必须引用稳定 `evidence_id`
- 混合召回相似申论题与已校验 Rubric；相似题只作为评分先例，不能越过本题材料证据
- 优先复用题库 V2 向量空间，缺失或不可用时自动降级为确定性中文特征哈希检索
- Agent 运行状态、分节点轨迹、并发幂等、失败重试、SSE 进度和人工采分点纠正
- 应用启动时自动恢复排队与陈旧运行；多进程通过数据库原子认领避免重复执行
- 正常关停会将中断运行放回恢复队列，恢复后沿用原运行并继续追加审计轨迹
- 接入 `app/access` 的 `agent.shenlun.grade` 档案：启动预检、运行认领后幂等扣减、付费额度或每日体验失败后退款
- `report` 级纠正只标记当前报告过期；`question` 级纠正还会失效旧 Rubric 并影响后续构建

申论教练能力包含：

- YanShen 风格自然语言意图识别：诊断、复盘、结构判断、改写、选题推荐、方法指导和概念解释
- 最近批改报告、题目、个人笔记和长期记忆组成的证据卡上下文；涉及用户事实时返回稳定 `evidence_id`
- 基于题库 V2 掌握度、正确率、难度和历史作答的下一题推荐
- 多轮会话、长期记忆、训练计划、任务完成和训练数据分析
- 同步消息接口和异步运行接口共用同一套业务逻辑；异步运行提供持久化步骤轨迹、幂等、恢复和 SSE

接口：

- `POST /api/v1/agent/shenlun/attempts/{attempt_id}/grading`
- `GET /api/v1/agent/shenlun/runs/{run_id}`
- `POST /api/v1/agent/shenlun/runs/{run_id}/retry`
- `POST /api/v1/agent/shenlun/runs/{run_id}/feedback`
- `GET /api/v1/agent/shenlun/runs/{run_id}/stream`

教练接口：

- `POST /api/v1/agent/shenlun/coach/sessions`
- `GET /api/v1/agent/shenlun/coach/sessions`
- `GET /api/v1/agent/shenlun/coach/sessions/{session_id}`
- `POST /api/v1/agent/shenlun/coach/sessions/{session_id}/messages`（同步）
- `POST /api/v1/agent/shenlun/coach/sessions/{session_id}/message-runs`（异步）
- `GET /api/v1/agent/shenlun/coach/runs/{run_id}`
- `GET /api/v1/agent/shenlun/coach/runs/{run_id}/stream`
- `GET /api/v1/agent/shenlun/coach/memories`
- `GET /api/v1/agent/shenlun/coach/recommendations?module=summary`
- `POST /api/v1/agent/shenlun/coach/plans`
- `GET /api/v1/agent/shenlun/coach/plans`
- `GET /api/v1/agent/shenlun/coach/plans/{plan_id}`
- `POST /api/v1/agent/shenlun/coach/plan-items/{item_id}/complete`
- `GET /api/v1/agent/shenlun/coach/analytics`

教练消息和训练计划均接入 `app/access` 的 `agent.shenlun.coach` 档案，成功消耗，模型或业务失败自动退款。

后续英语作文、面试和申论训练教练会继续放在本插件内，通过不同的 `agent_key` 和 `workflow_key` 扩展。
