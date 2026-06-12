# AI 出题系统任务追踪

## 目标

建设一个可扩展的 AI 出题系统，当前先覆盖国考行测言语理解，后续可扩展到省考、其他科目或其他题型。

系统需要支持：

- 素材入库与状态追踪
- 素材来源发布时间记录，用于时效性判断和溯源
- 从文章素材中自动选取适合命题的连续片段，并判断适合出什么题
- 一个文章素材可以挖掘多个高价值片段，每个片段按自身题眼匹配最适合的题型
- 片段之间允许重叠，只要题型、题眼、答案逻辑或干扰项空间存在实质差异
- 系统自动决定题型和题量，不允许用户手动指定出题方向
- 系统从文章中自动选取连续命题片段，不能把整篇文章直接当题干文段
- 基于历年真题抽取真实命题规律，沉淀为可复用 profile
- 使用 Agent 按素材生成题目、选项、答案、解析、命题蓝图和质检结果
- 管理端查看素材、任务、候选题，并进行人工审核

## 核心判断

本功能采用“结构化 profile + Agent 编排”的混合方案。

- profile 负责沉淀命题规律、题型约束、选项设置规则和质检标准。
- Agent 负责任务拆解、文章结构分析、多片段挖掘、命题蓝图、题目生成、选项二次校准和复核。
- 出题 Agent 放在 `backend/plugin/agents` 下，业务数据和状态放在独立 app 中。
- 当前不把逻辑写成单一提示词，因为后续要扩展省考、不同题型、不同质量检查维度，单提示词会很快失控。

## 已完成内容

### 1. 命题规律分析

已基于 `backend/output/gk_yuyan_2019_2026.md` 做过首轮规律抽取，分析时刻意不依赖解析和标签链，重点看题干、文段、选项和答案之间的实际关系。

当前沉淀方向：

- 文段选择：国考言语常选结构清晰、论证关系明显、可形成单一考点的材料。
- 题干设置：题干往往要求考生回到文段结构，而不是只抓关键词。
- 例子处理：例子常服务于前后观点，不能把例子本身误当中心。
- 选项设置：干扰项常见方式包括偷换主体、扩大/缩小范围、把例子当观点、无中生有、偏离行文重点、过度推断。
- 质量要求：题目必须能从文段内闭合验证，不能靠常识硬补。

### 2. 后端独立 app

已新增 `backend/app/question_generation`，包含：

- model
- schema
- crud
- service
- api

主要能力：

- 出题素材管理
- 出题任务内部自动选段与命题规划
- 出题任务创建与查询
- 候选题查询
- 候选题审核

当前启动出题策略：

- 用户只选择素材并触发任务。
- Agent 会先从文章中选取适合国考言语命题的连续片段，再决定题型和题量。
- 如果调用方传入 `target_question_types` 或 `question_count`，后端会覆盖为系统自动规划结果。
- 选段不是自然段切分，可能是完整自然段、自然段内连续几句，或横跨相邻两个自然段的连续句群。
- 多个片段可以重叠。系统不做“禁止重叠”的机械限制，只要求重叠片段的命题价值不同。
- 逻辑填空当前已纳入题型体系，但只有片段具备搭配对象、上下文照应、程度轻重、感情色彩或文体语域约束时才允许生成。
- 选段后会按题型字数范围做硬过滤：逻辑填空 140-165 字，片段阅读 230-260 字，语句填空 180-240 字，语句排序 260-320 字。
- 用户端不提供预处理按钮，不允许用户手动指定题型或题量。

主要接口：

- `GET /api/v1/question-generation/materials`
- `POST /api/v1/question-generation/materials`
- `PUT /api/v1/question-generation/materials/{pk}`
- `DELETE /api/v1/question-generation/materials`
- `GET /api/v1/question-generation/tasks`
- `POST /api/v1/question-generation/tasks/start`
- `GET /api/v1/question-generation/candidates`
- `POST /api/v1/question-generation/candidates/{pk}/review`

### 3. Agent 编排

已新增 `backend/plugin/agents/service/question_generation`。

当前节点：

- profile loader
- article analyzer
- passage miner
- blueprint planner
- question drafter
- option designer
- reviewer

当前 profile：

- `gk_xingce_yuyan_base.yaml`

当前 prompt：

- article analyzer
- passage miner
- blueprint planner
- question drafter
- option designer
- reviewer

### 4. Celery 任务

已新增出题任务入口：

- `backend/app/task/tasks/question_generation/tasks.py`

任务名：

- `question_generation_run_task`

### 5. 路由接入

已将 question generation 路由接入后端主路由。

已将 Agent 类型补充到 report schema。

### 5.1 菜单和接口权限

已新增后端菜单插入脚本：

- `backend/scripts/insert_question_generation_menu.py`

脚本会在 `Gongkao` 父菜单下插入：

- `GongkaoQuestionGeneration`
- 素材读取 / 写入 / 删除按钮权限
- 任务读取 / 启动按钮权限
- 候选题读取 / 审核按钮权限

已给 question generation API 补充 `RequestPermission`，使 RBAC 可以按菜单按钮权限校验接口。

说明：素材预处理接口已移除，选段与命题规划只在出题任务内部执行。

当前说明：脚本和代码已完成，本地数据库尚未成功执行插入。尝试通过数据库工具校验/写入时，审批服务返回 `503 Service Unavailable`，因此未绕过执行。

### 6. 管理端

已在 `frontend/apps/web-antdv-next` 中新增管理端页面。

新增文件：

- `apps/web-antdv-next/src/api/question-generation.ts`
- `apps/web-antdv-next/src/views/gongkao/question-generation/index.vue`

修改文件：

- `apps/web-antdv-next/src/api/index.ts`
- `apps/web-antdv-next/src/router/routes/modules/gongkao.ts`

页面路径：

- `/gongkao/question-generation`

页面模块：

- 素材库：新增、编辑、删除、搜索、状态筛选、启动出题
- 出题任务：任务状态、阶段、进度、错误、输入参数、状态快照、结果摘要
- 候选题：题干、选项、答案、解析、命题蓝图、质检结果、审核通过、驳回

## 已验证内容

后端：

- Python 编译检查通过
- 后端 router import 检查通过
- Celery 任务名检查通过

前端：

- `pnpm exec eslint apps/web-antdv-next/src/api/question-generation.ts apps/web-antdv-next/src/views/gongkao/question-generation/index.vue apps/web-antdv-next/src/router/routes/modules/gongkao.ts apps/web-antdv-next/src/api/index.ts` 通过
- `pnpm --filter @vben/web-antdv-next typecheck` 通过

## 当前阶段

当前处于“文章级多片段出题链路已改造，进入数据库迁移和真实联调前收尾”阶段。

更具体地说：

- 代码结构已成型。
- 数据模型、接口、任务、Agent 目录、管理端页面都已经有了。
- Agent 已从旧单片段处理改为文章分析、多片段挖掘、片段质检与回修、题型机会判断、题型质检、蓝图规划、题目生成、选项校准、成题质检与回修。
- 静态检查和关键导入检查通过。
- 还没有完成数据库迁移、权限配置和真实端到端联调。

## 剩余事项

### 必须完成

1. 数据库迁移

   需要为以下表生成并执行 Alembic migration：

   - `ai_question_generation_material`
   - `ai_question_generation_task`
   - `ai_question_generation_candidate`

   素材表还需要包含 `source_publish_time` 字段，用于记录来源原文发布时间。

   候选题表还需要包含 `selected_passage`、`passage_id`、`passage_meta` 字段，用于记录每道候选题实际依据的命题片段和片段元信息。

2. 权限与菜单配置

   后端菜单插入脚本已补充，但仍需要在目标环境执行脚本，并把菜单权限分配给实际角色。

   执行脚本：

   ```bash
   uv run python backend/scripts/insert_question_generation_menu.py
   ```

3. Celery 联调

   需要确认 worker 已加载 `question_generation_run_task`。

   需要真实创建一个素材，启动任务，观察任务状态从 pending 到 completed 或 failed。

4. Agent 输出落库联调

   需要验证 Agent 生成的候选题字段完整写入：

   - stem
   - options
   - answer_data
   - analysis
   - blueprint
   - qc_result
   - difficulty
   - knowledge_point
   - selected_passage
   - passage_id
   - passage_meta

6. 有界回修联调

   当前出题链路已按生产化思路拆为多道质量闸：

   - `article_analyzer`：分析整篇素材结构。
   - `passage_miner`：挖掘候选连续片段。
   - `passage_reviewer`：片段质检，输出 `pass / revise / discard`。
   - `passage_reviser`：只修复可修片段，最多 2 轮。
   - `question_type_planner`：判断片段适合出什么题。
   - `type_reviewer`：题型适配质检，输出 `pass / revise / discard`。
   - `blueprint_planner`：只基于通过题型质检的机会规划蓝图。
   - `question_drafter`：按蓝图出题。
   - `option_designer`：二次校准选项。
   - `question_reviewer`：成题质检，输出 `pass / revise / discard`。
   - `question_reviser`：只修复可修题，最多 2 轮。

   需要真实素材验证：

   - 片段可修时能否正确移动边界。
   - 题型不成立时能否准确舍弃而不是硬凑。
   - 成题质检打回后，修复题是否保留同一 `passage_id` 并完整包含所选片段。

5. 真实样例质检

   至少拿 3 到 5 段素材跑通：

   - 可出题素材
   - 不适合出题素材
   - 文段过短素材
   - 文段过长素材
   - 结构明显但干扰项容易跑偏的素材

### 建议补强

1. 深化命题规律 profile

   当前 profile 是首版，需要继续把真题规律拆得更细：

   - 主旨概括
   - 意图判断
   - 细节理解
   - 语句填空
   - 语句排序
   - 逻辑填空

2. 强化选项生成约束

   建议把干扰项类型结构化：

   - 偷换主体
   - 范围扩大
   - 范围缩小
   - 例子主旨化
   - 绝对化表达
   - 无中生有
   - 与文段方向相反
   - 过度推断

3. 增加发布链路

   当前候选题可审核，但还没有完整打通“审核通过后发布到正式题库”的流程。

4. 增加批量素材导入

   当前管理端支持单条素材创建，后续可加批量粘贴、文件导入、URL 抓取。

5. 增加任务重试和取消

   当前任务有失败状态，但管理端还没有重试、取消、重新生成按钮。

6. 增加质量评分面板

   可将 Agent 的 qc_result 可视化为：

   - 文段回扣
   - 答案唯一性
   - 干扰项有效性
   - 国考风格相似度
   - 解析闭合度

## 风险点

- 如果不做迁移，接口无法真实落库。
- 如果 RBAC 未授权，管理端会出现接口无权限。
- 如果 Celery worker 没加载新任务，启动出题只会创建任务，不会执行生成。
- 选段与命题规划完全依赖 Agent 质量，需要用真实文章样例持续校准，尤其是重叠片段、多题眼和逻辑填空场景。
- 当前管理端 dev server 未能启动验证，原因是本地权限审批服务返回 503；代码层面已通过 lint 和 typecheck。

## 下一步建议

优先顺序：

1. 生成并检查 Alembic migration。
2. 配置菜单和接口权限。
3. 启动后端、前端、Celery worker，跑一条素材到候选题的端到端链路。
4. 用真题规律继续打磨 `gk_xingce_yuyan_base.yaml` 和 prompt。
5. 增加候选题发布到正式题库的流程。
