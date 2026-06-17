# 申论批改 Agent - Prompt 调优接手指南

> **接手对象**：负责 agents 插件下一阶段 prompt 工程的同事
> **当前状态**：Sprint 1 walking skeleton + 大作文/归纳概括两题型可用，**质量层面仍需持续打磨**
> **作者**：fba claude code 接手 (2026-05)

---

## 1. 快速上手（5 分钟）

### 1.1 跑一个样本看效果

```bash
# Mock 模式（不调 LLM，验证流程通畅，0.5 秒）
.venv/Scripts/python -m backend.plugin.agents.scripts.grade_one \
  --sample backend/plugin/agents/tests/samples/sample_essay.yaml \
  --mode mock

# 真实模式（调 mimo-v2.5-pro，60-150 秒）
.venv/Scripts/python -m backend.plugin.agents.scripts.grade_one \
  --sample backend/plugin/agents/tests/samples/sample_essay.yaml \
  --mode real
```

### 1.2 跑测试

```bash
.venv/Scripts/python -m pytest backend/plugin/agents/tests/test_shenlun_pipeline.py -v
```

12 个 mock 测试覆盖：12 节点全跑通、9 section 字段齐全、SSE 推送、并行组 race-free、节点角色映射。**改任何 prompt 或节点代码前后都跑一遍**。

### 1.3 看一份完整跑通的样本

`backend/plugin/agents/tests/samples/sample_essay.yaml` 是大作文样本（H 市协同发展题），含完整题干+材料+3 份参考答案+学生作答。继承样本（D/C/A 档对照）：

- `sample_essay_d_grade.yaml`（D 档，332 字偏题）
- `sample_essay_c_grade.yaml`（C 档，720 字论据空）
- `sample_essay_a_grade.yaml`（A 档，1100 字优秀）

归纳概括样本同理（`sample_1.yaml` + `sample_d/c/a_grade.yaml`）。

---

## 2. 关键文件结构

```
backend/plugin/agents/
├── service/
│   ├── shenlun/
│   │   ├── rubrics/                ⭐ 评分细则 YAML（按题型, 5 套）
│   │   │   ├── essay.yaml          大作文（40 分制，5 维度: 立意/结构/论证/文采/规范）
│   │   │   ├── summary.yaml        归纳概括（10 分制，4 维度: 全面/准确/条理/语言）
│   │   │   ├── analysis.yaml       综合分析（10 分制，4 维度: 观点/分析深度/逻辑/语言）
│   │   │   ├── countermeasure.yaml 提出对策（10 分制，4 维度: 针对性/可行性/全面性/操作性）
│   │   │   └── application.yaml    应用文（15 分制，4 维度: 格式/对象/任务/语言）
│   │   ├── outputs.py              ⭐⭐⭐ 11 节点 LLM 输出 Pydantic schema（output_type 强类型）
│   │   ├── prompts/                ⭐⭐ Prompt 模板 YAML（11 套）
│   │   │   ├── classifier.yaml         题型识别
│   │   │   ├── material_parser.yaml    材料要点提取
│   │   │   ├── reference_analyzer.yaml 参考答案聚合（含共识度）
│   │   │   ├── answer_analyzer.yaml    考生要点提取
│   │   │   ├── point_matcher.yaml      要点匹配（覆盖/缺失）
│   │   │   ├── structure_analyzer.yaml 段落结构分析
│   │   │   ├── scorer.yaml             ⭐⭐⭐ 评分（5 维度评分）
│   │   │   ├── diagnoser.yaml          问题诊断
│   │   │   ├── suggester.yaml          提升建议
│   │   │   ├── rewriter.yaml           改写示范
│   │   │   └── reviewer.yaml           质检
│   │   ├── nodes/                  节点 Python 实现（每节点 ~30 行）
│   │   └── graph.py                Pipeline 装配（12 节点编排）
│   ├── common/                     ⛔ 通用基础设施，**不要随便改**
│   │   ├── llm/                    LLM 客户端 + 节点角色路由
│   │   ├── prompts/                Jinja2 模板加载器
│   │   ├── streaming/              SSE 事件总线
│   │   ├── quota/                  access 权益封装
│   │   ├── ocr/                    OCR 封装
│   │   └── orchestrator/           DAG runner（pipeline.py）
│   └── grading_service.py          API 业务服务
├── schema/                         ⛔ 协议层，**改字段=影响前端**
│   ├── report.py                   AgentReport / 9 sections / 枚举
│   ├── event.py                    SSE 事件协议
│   ├── state.py                    GradingState（节点间共享状态）
│   └── grading.py                  API 入参出参
├── tests/
│   ├── samples/                    ⭐ 样本 YAML
│   ├── fake_llm.py                 Mock LLM
│   └── test_shenlun_pipeline.py    端到端测试
└── scripts/
    └── grade_one.py                CLI 工具（mock + real 两种模式）
```

**⭐ 标记 = Prompt 工程师常改的文件**
**⛔ 标记 = 改动会影响前端/其他 agent，先和团队商量**

---

## 3. 典型调优工作流（每次改 prompt 都按这个走）

```
                ┌──────────────────────────────┐
                │ 1. 发现问题（跑真实样本看输出） │
                └──────────────┬───────────────┘
                               ▼
                ┌──────────────────────────────┐
                │ 2. 定位是哪个节点的 prompt   │
                │   （看 traces 顺序+输出内容） │
                └──────────────┬───────────────┘
                               ▼
                ┌──────────────────────────────┐
                │ 3. 改对应 prompts/xxx.yaml    │
                │   （加反例/正例/硬规则）       │
                └──────────────┬───────────────┘
                               ▼
                ┌──────────────────────────────┐
                │ 4. 跑 mock pytest（0.5 秒）   │
                │   验证流程不破                │
                └──────────────┬───────────────┘
                               ▼
                ┌──────────────────────────────┐
                │ 5. 跑真实样本（60-150 秒）    │
                │   验证 LLM 实际表现           │
                └──────────────┬───────────────┘
                               ▼
                ┌──────────────────────────────┐
                │ 6. 跑 4 档对照样本验证回归    │
                │   D/C/B/A 档位是否仍归位     │
                └──────────────────────────────┘
```

---

## 4. 如何加新样本

最便利的方式：**用 `extends` 机制继承基础样本**，只写差异。

```yaml
# tests/samples/my_new_sample.yaml
extends: sample_essay.yaml

# 只重写需要改的字段，其他从父样本继承
user_answer_text: |
  这是我的新学生作答...
```

跑：

```bash
.venv/Scripts/python -m backend.plugin.agents.scripts.grade_one \
  --sample backend/plugin/agents/tests/samples/my_new_sample.yaml \
  --mode real
```

---

## 5. 常见调优场景

### 场景 A：评分系统性偏高（D 档评 C，C 档评 B）

**症状**：所有档位评分都往上偏 1 档。
**根因**：LLM 倾向"维度宽容"——每个维度都打中位数偏高。
**修复手段（按优先级）**：

1. **代码层硬约束**（首选）：见 `nodes/scorer.py` 的 `_compute_cap_factor`。
   - 字数硬规则、引用硬规则、缺失要点硬规则
   - 改阈值或加新 factor
2. **scorer.yaml 加 few-shot 评分锚点**：在 system 段加"评分锚定示例"表，给 4 档典型作答的标杆评分
3. **降 temperature**：scorer 节点的 `temperature` 从 0.3 → 0.1 让评分更稳定

### 场景 B：评分系统性偏低（A 档评 B，B 档评 C）

**症状**：所有档位评分都往下偏 1 档。
**修复**：调高 `nodes/scorer.py` 的 cap factor 阈值，或放宽 prompt 里的"严判硬规则"。

### 场景 C：缺失要点数过多/过少

**症状**：A 档作答缺 5 条要点（应缺 0-2）；或 D 档作答只缺 1 条（应缺 4-5）。
**根因**：`reference_analyzer.yaml` 切要点的粒度。
**修复**：
- 缺多 → reference_analyzer 切要点太细，加强"5-8 条上限"指令
- 缺少 → reference_analyzer 切要点太粗，加更多反例（什么不应合并）

### 场景 D：改写超字数

**症状**：`rewritten_text` 超过题目字数上限。
**修复**：
1. 改 `rewriter.yaml` 加更强字数硬指令
2. 在 `nodes/rewriter.py` 加 post-processing：超字数时调 LLM 二次压缩

### 场景 E：要点判定过严/过宽

**症状**：考生提到了类似概念但被判缺失，或泛泛而谈也被判覆盖。
**根因**：`point_matcher.yaml` 的"部分覆盖"判定边界。
**修复**：调整 prompt 里"严判核心信息 + 宽容上位概念"的具体例子。

### 场景 F：档位术语错（如显示"良好卷"而非"二类卷"）

**根因**：`rubrics/xxx.yaml` 的 `grade_labels` 字段值。
**修复**：直接改 YAML（**不改代码**），数据驱动。
- `essay.yaml`: A=一类卷 / B=二类卷 / C=三类卷 / D=四类卷
- `summary.yaml`: A=优秀 / B=良好 / C=合格 / D=不合格

### 场景 G：档位阈值不友好（如 5 分 / 10 分判 D 不合格）

**位置**：`nodes/scorer.py` 的 `_level_from_ratio` 函数。
**当前阈值**（C 端友好版）：
- A ≥ 0.85
- B ≥ 0.65
- C ≥ 0.40
- D < 0.40

改阈值会影响所有 agent，**改前先和产品/运营商量**。

---

## 6. 代码层硬约束 vs Prompt 软约束

| 类型 | 位置 | 适用场景 | 强度 |
|---|---|---|---|
| **Pydantic AI Agent 强类型输出** | `outputs.py` 各 Output schema | LLM 返回字段必须符合 schema, 失败自动重试 2 次 | **最强**：SDK 内建校验 |
| **节点入口契约 (NodeContractError)** | 节点函数开头 | 上游产物缺失则直接 fail, 不污染下游 | **强**：raise 即任务失败 |
| **Pydantic @model_validator 交叉校验** | `schema/report.py` 各 Section | 跨字段一致性 (如 rubric_scores 之和 ≈ score) | **强**：Pydantic 构造时检查 |
| **代码层硬规则扣分** | `nodes/scorer.py` `_compute_cap_factor` | 客观可机器判断的规则（字数/引用次数/缺失数）| 强制覆盖 LLM |
| **Prompt 严判指令** | `prompts/xxx.yaml` system 段 | 主观需要 LLM 判断的（立意/论证质量）| 软建议 |
| **Few-shot 锚点** | `prompts/xxx.yaml` system 段 | LLM 输出粒度引导（如"X 字泛泛而谈 → 10-14 分"）| 中等 |
| **Temperature** | `nodes/xxx.py` 的 `invoke_structured` 参数 | 评分一致性 | 弱（仅影响波动）|

**经验法则**：
- 想约束 LLM **输出结构** → 改 `outputs.py` 的 Output schema（加 min_length / Literal / ge/le 等 Field 约束）
- 想要求 **上游必须有产物** → 节点入口加 `raise NodeContractError(...)`
- 想约束 **跨字段一致性** → 给 Section 加 `@model_validator(mode='after')`
- 想根据**客观硬指标**强制扣分 → 改 `nodes/scorer.py` 的 `_compute_cap_factor` 加新 factor
- LLM **主观判断**问题 → 改 prompt 严判 + few-shot 锚点
- LLM **跨次波动**大 → 降 temperature 到 0.1, 或加 `output_retries`

---

## 7. 关键设计原则（不要破坏）

### 7.1 节点是 pure async function

每个节点函数签名都是 `async def func(ctx: NodeContext) -> None`，**只读 `ctx.state`，只改 `ctx.state`**。不要：
- 引入全局变量
- 直接调 `ctx.db` 写数据库（grading_service 负责持久化）
- 跨节点 import（如 diagnoser 直接 import scorer 的内部函数）

### 7.2 ParallelGroup 内的节点写不同 state 字段

`material_parser / reference_analyzer / answer_analyzer` 在并行组里，三者分别写 `state.key_points.material_points / reference_points / answer_points` 不同字段——**race-free**。

**新加节点时**：如果要放入并行组，确保你写的 state 字段没和其他并行节点冲突。

### 7.3 LLM 调用必须用 `invoke_structured`（强类型）

新写的所有节点调 LLM 必须用 `ctx.llm.invoke_structured(output_type=XxxOutput)` 而非 `invoke_json`。理由：
- Pydantic AI Agent 自动校验 + 失败重试 2 次（`output_retries=2`）
- 节点拿到的是强类型 Pydantic 对象（不需要 `.get()` 兜底）
- LLM 输出错误会立即 raise 而不是默默 fallback

**`invoke_json` 仅作为兜底接口保留**，加新节点不要用它。

### 7.4 节点入口加 `NodeContractError` 契约检查

如果节点依赖上游产物（如 scorer 依赖 rubric+key_points），入口必须检查并 raise `NodeContractError`，不要 silent return。这让 failure 早暴露：

```python
from backend.plugin.agents.service.common.orchestrator import NodeContractError


async def my_node(ctx: NodeContext) -> None:
    if ctx.state.score_card is None:
        raise NodeContractError('my_node 要求 score_card 已就绪')
    ...
```

### 7.5 代码权威 > LLM 建议

- 评分总分由代码 `sum(rubric_scores.score)` 算（**不用 LLM 返回的 score_total**）
- 档位由 `_level_from_ratio` 按总分算（**不用 LLM 返回的 level**）
- level_label 由 `rubric.grade_labels[level]` 查（**不用 LLM 返回的 level_label**）
- LLM 返回的这些字段只作为参考（fallback 用）

### 7.4 系统级提示走 `ScoreCardSection.system_notes`

代码层强制扣分时，**不要污染 `summary`**，把原因 append 到 `system_notes: list[str]`。前端可选展示。

---

## 8. 已知问题和后续待办

### 8.1 LLM 跨次评分波动 ±3 分

**现象**：同一份样本两次跑评分能差 3-5 分（如 A 档样本 36 → 31）。
**根因**：mimo-v2.5-pro 在 temperature=0.1 下仍有随机性 + MIMO 转发可能 routing 到不同实例。
**对策**：建黄金集回归测试（见 8.3）。**Pydantic AI 的 `output_retries=2` 已经能缓解 schema 校验类的波动**。

### 8.2 LLM 对低分作答的判定仍偏宽（部分缓解）

**现象**：332 字偏题作答 LLM 给立意 9/12（B 档）。
**根因**：LLM 性格——"找作答的优点而非缺点"。
**对策（已就位）**：
- 代码层 cap（`_compute_cap_factor`）按字数/引用/缺失硬扣分
- Output schema 的 `Literal['A','B','C','D']` 约束让 LLM 至少不能编造档位
- Prompt few-shot 锚点引导"D 档典型分数 10-14"

**继续打磨方向**：加更多 few-shot 例子，或者节点级二次审核（如 scorer 跑两次取平均）。

### 8.3 黄金集回归测试（推荐 Sprint 2 做）

收集 20-50 份真实样卷 + 真人评分作 baseline，每次改 prompt 后跑黄金集，看：
- 平均评分差距（MAE）
- 评分相关性（Pearson）
- 档位匹配率

**实现思路**：在 `tests/golden/` 目录放 yaml 样本 + 真人评分，写一个 `tests/test_golden_regression.py` 跑 mock/real 比对。

### 8.4 5 题型 rubric 已全部就位（仍需 prompt 微调）

5 套 rubric 已就位映射如下，**架构完整覆盖 5 题型**：
- `essay.yaml` → 大作文
- `summary.yaml` → 归纳概括
- `analysis.yaml` → 综合分析
- `countermeasure.yaml` → 提出对策
- `application.yaml` → 应用文

**但 prompt 层面只针对大作文 + 归纳概括做过真实样本验证**。综合分析/对策/应用文的 rubric 是按公考通行框架写的，**需要同事按"题型特异微调要点"（见第 11 节）持续调优**。

### 8.5 OCR endpoint 已就位（仍需端到端 e2e 联调）

OCR endpoint `POST /api/v1/agents/grading/ocr` 已实现，逻辑：上传图片 → 调 `OCRClient`（默认走 settings.OCR_PROVIDER）→ 返回归一化文本。前端调用流程：
1. 用户拍照上传到 `/grading/ocr` → 拿 text
2. text + 题目数据 → 调 `/grading/start` → 拿 task_id
3. SSE 订阅 `/grading/{id}/stream` → 看实时结果

**仍需联调**：用真实手写照片测试 OCR 准确率（subjective_answer scene）。如果 OCR 识别率低，需要调 OCR provider 配置（settings.OCR_PROVIDER）或者切换到 LlamaParse provider。

### 8.6 token 用量统计不持久化

`LLMClient` 的 `LLMCallStats` 没接到 `Pipeline` 的 trace。需改造 `NodeContext` 或在 invoke_json 注入 trace 字段。**对成本核算很重要**。

---

## 9. 调试技巧

### 9.1 看 LLM 实际返回什么

临时在节点里加 print：

```python
data, _ = await ctx.llm.invoke_json(...)
print(f'[DEBUG {节点名}] LLM 返回: {data}')
```

跑 `grade_one.py --mode real` 看实际输出。**用完删掉**。

### 9.2 看 state 流转

在 `grade_one.py` 的 `_print_report` 加：

```python
print(f'[DEBUG state.extras]: {state.extras}')
```

可以看到节点间共享数据（如 structure_analyzer 写的结构信息）。

### 9.3 单独跑某个节点

写一个 throwaway script：

```python
import asyncio
from pathlib import Path
from backend.plugin.agents.schema import GradingState
from backend.plugin.agents.service.common.llm import LLMClient
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.common.prompts import PromptLoader
from backend.plugin.agents.service.common.streaming import EventBus
from backend.plugin.agents.service.shenlun.nodes.scorer import score


async def main():
    state = GradingState(...)  # 手动构造你要测的状态
    ctx = NodeContext(
        state=state,
        db=None,
        event_bus=EventBus(),
        llm=LLMClient(provider_id=5, primary_model_id='mimo-v2.5-pro'),
        prompts=PromptLoader(Path('backend/plugin/agents/service/shenlun/prompts')),
    )
    await score(ctx)
    print(state.score_card)


asyncio.run(main())
```

---

## 10. 联系人 & 资源

- **API provider**：MIMO (id=5, model_id=mimo-v2.5-pro, https://token-plan-cn.xiaomimimo.com/anthropic)
- **数据库表**：`plugin_agents_task`（PostgreSQL + MySQL 两套 init.sql）
- **API endpoints**：
  - `POST /api/v1/agents/grading/start` 启动批改（JSON body）
  - `POST /api/v1/agents/grading/ocr` OCR 识别考生答卷图片（multipart, 返回 text）
  - `GET /api/v1/agents/grading/{id}/stream` SSE 订阅
  - `GET /api/v1/agents/grading/{id}` 拉取详情
- **现有完整工程文档**：`backend/CLAUDE.md`、`backend/app/access/权益订阅系统说明.md`

---

## 11. 题型特异微调要点（同事接手的重点）

5 套 rubric 是按公考通行框架写的初版，**实际跑真实样本时每个题型都有自己的 LLM 盲点**。下面是每个题型最容易出问题的位置 + 建议微调方向。

### 11.1 大作文（essay.yaml + scorer/rewriter prompt）

**LLM 高频盲点**：
- **立意维度**：LLM 倾向于"立意明确"打 B 档，但实际很多作文立意浅显（"很重要/应该加强"），应判 C 档
- **文采维度**：LLM 把"有修辞" = "文采好"，但实际堆砌典故 ≠ 文采，需要在 prompt 加反例
- **改写示范字数**：800-1200 字硬上限有时被突破（mimo-v2.5-pro 想多写）——已有代码层 cap 但仍可加强 prompt

**建议微调位置**：
- `prompts/scorer.yaml` 加"立意深度判定"的具体反例（"很重要/应该加强 → C 档"）
- `prompts/rewriter.yaml` 强化"字数硬上限"语气
- `rubrics/essay.yaml` 各维度 levels 描述更具体

### 11.2 归纳概括（summary.yaml + reference_analyzer prompt）

**LLM 高频盲点**：
- **要点切粒度**：LLM 容易把同一参考要点切成 2-3 条（"5G 智慧灯杆/智能感知/远程控制"被拆三条）——需要在 reference_analyzer prompt 加合并案例
- **共识度判定**：LLM 偏严格——"完善配套智能设施" 和 "5G 智慧灯杆" 都明确提到时仍可能不合并

**建议微调位置**：
- `prompts/reference_analyzer.yaml` 加"上位概念 ≡ 具体设施"的合并案例
- `rubrics/summary.yaml` 全面性维度 levels 描述需要更具体

### 11.3 综合分析（analysis.yaml）⚠️ 未真实样本验证

**预期 LLM 盲点**（推测，需同事真实样本验证）：
- **分析深度维度**：LLM 容易把"重复观点 + 添加修饰词" 当成深入分析，需在 prompt 加"重复 vs 深入"反例
- **观点维度**：LLM 把"复述材料" 当成"准确把握观点"——应区分"复述" 和 "提炼观点"

**建议微调步骤**：
1. 准备 3-5 份综合分析真题（含真人评分）
2. 跑 `grade_one.py --mode real`，看 LLM 评分与真人差距
3. 重点观察"分析深度"维度的 comment 是否说出"为什么深/为什么浅"
4. 在 `prompts/scorer.yaml` 加综合分析特异的 few-shot 锚点

### 11.4 提出对策（countermeasure.yaml）⚠️ 未真实样本验证

**预期 LLM 盲点**：
- **可行性维度**：LLM 容易把"加强 X / 完善 Y" 这种空话当成"可行对策"——应严判
- **操作性维度**：LLM 对"具体步骤" vs "原则口号"区分不清

**建议微调步骤**：
1. 准备 3-5 份对策题真题
2. 重点检查每条对策的"可执行性"——能不能找到"在 X 部门用 Y 工具做 Z 事"这种具体抓手
3. 在 `prompts/scorer.yaml` 加"对策硬规则"：单条对策若无具体动词+对象+方法 → 操作性 ≤ 满分*0.5

### 11.5 应用文（application.yaml）⚠️ 未真实样本验证

**预期 LLM 盲点**：
- **格式维度**：LLM 容易忽略"标题/称呼/落款/日期"等格式要素——需要在 prompt 明确列举检查清单
- **对象维度**：LLM 把"恭敬用语" 当成"对象意识强"，但实际应用文要根据上下级关系/场合调整语气

**建议微调步骤**：
1. 准备 3-5 份应用文真题（含通知/讲话稿/工作方案等不同文体）
2. 在 `prompts/scorer.yaml` 加应用文专属"格式检查清单"：标题/称呼/正文/落款/日期 5 个要素逐项检查
3. 在 `nodes/scorer.py` 考虑加代码层格式检测（正则查"尊敬的""此致敬礼""落款"等关键词）

### 11.6 通用：建议同事的"3 步迭代法"

每次接到一个题型/Bug 都按这个走：

```
Step 1: 准备 5+ 份真实样卷（覆盖 D/C/B/A 4 档）
     └→ 用 sample_xxx.yaml 模板, 通过 extends 机制继承

Step 2: 跑 grade_one.py --mode real 拿 LLM 评分
     └→ 与真人评分对比, 找出系统性偏差（偏高/偏低/某维度盲点）

Step 3: 改 prompt yaml 或 scorer.py 硬规则
     └→ 跑 mock pytest 验证流程, 跑 real 验证质量
```

---

## 12. 建议的迭代计划（同事接手的 Sprint）

| 优先级 | 任务 | 工作量 | 难度 |
|---|---|---|---|
| 🔴 P0 | 建黄金集回归测试（见 8.3）| 1-2 天 | 中 |
| 🔴 P0 | 综合分析/对策/应用文真实样本验证 + prompt 微调（见 11.3-11.5）| 每题型 4-6 小时 | 中 |
| 🟡 P1 | OCR e2e 联调（用真实手写照片测试，见 8.5）| 半天 | 低 |
| 🟡 P1 | scorer 加应用文格式代码层检测（见 11.5）| 2-3 小时 | 中 |
| 🟢 P2 | token 用量统计接到 trace（见 8.6）| 半天 | 中 |
| 🟢 P2 | 改写示范 fallback 二次压缩（超字数时调 LLM 再压缩）| 半天 | 中 |

---

## 13. 架构升级（Sprint 1.5 已完成）—— 同事接手注意事项

这是 Sprint 1.5 的架构升级清单（A/B/C 改造已完成）。**新加节点/新加 agent 时必须遵守这些约定**。

### 13.1 加新节点的标准模板

```python
# nodes/my_new_node.py
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext, NodeContractError
from backend.plugin.agents.service.shenlun.outputs import MyNewNodeOutput  # 在 outputs.py 加


async def my_new_node(ctx: NodeContext) -> None:
    """节点说明"""
    # ① 入口契约检查 (B 改造)
    if ctx.state.xxx is None:
        raise NodeContractError('my_new_node 要求 xxx 已就绪')

    # ② 渲染 prompt
    system, user, _ = ctx.prompts.load_and_render(
        'my_new_node',  # prompts/my_new_node.yaml
        {...},
    )

    # ③ 用 invoke_structured 强类型调用 (A 改造)
    output, _ = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=MyNewNodeOutput,  # ⭐ 强类型约束
        temperature=0.1,
        max_tokens=2000,
        output_retries=2,
    )

    # ④ 强类型属性访问（不需要 .get() 兜底）
    ctx.state.xxx = MyXxxSection(
        some_field=output.some_field,
        ...
    )
```

### 13.2 加新 Output schema 的位置

`service/shenlun/outputs.py`，添加 Pydantic `BaseModel` 子类：

```python
class MyNewNodeOutput(BaseModel):
    """my_new_node 节点输出"""

    # 用 Field 约束让 LLM 返回错误自动 retry
    some_field: str = Field(min_length=2)
    items: list[ItemPayload] = Field(min_length=1, max_length=10)  # 强制 1-10 条
    grade: Literal['A', 'B', 'C', 'D']  # 强制枚举
    score: float = Field(ge=0, le=100)  # 强制范围
```

**所有约束（min_length / Literal / ge/le）违反时 Pydantic AI 会自动反馈错误给 LLM 重试 2 次**。

### 13.3 加新跨字段一致性校验 (C 改造)

如果新 Section 有内部不变量（如"分项之和 ≈ 总分"），用 `@model_validator`：

```python
from pydantic import model_validator


class MyNewSection(SchemaBase):
    score: float
    items: list[ItemPayload]

    @model_validator(mode='after')
    def _check_consistency(self) -> 'MyNewSection':
        actual = sum(i.weight for i in self.items)
        if abs(actual - self.score) > 0.5:
            raise ValueError(f'MyNewSection 内部矛盾: items 之和 ({actual}) ≠ score ({self.score})')
        return self
```

**这种校验在 Pydantic 构造时自动跑——构造失败立刻 raise，bug 早暴露**。

### 13.4 加新 agent 类型的检查清单

如果要加新 agent（如 english_essay/xingce/interview）：

1. **新建 `service/<agent>/` 目录**：复制 `service/shenlun/` 结构
2. **写 `outputs.py`**：定义该 agent 各节点的 Output schema
3. **写 `rubrics/*.yaml`**：评分细则
4. **写 `prompts/*.yaml`**：prompt 模板
5. **写 `nodes/*.py`**：节点函数（按 §13.1 模板）
6. **写 `graph.py`**：Pipeline 装配
7. **改 `grading_service.py`**：在 `_PIPELINE_BUILDERS` 加注册
8. **写测试**：参考 `tests/test_shenlun_pipeline.py`

**所有通用基础设施**（LLM client / prompts loader / streaming / quota / ocr / orchestrator）**完全复用**，不要在 agent 目录里重新实现。

### 13.5 调试 Pydantic AI Agent 模式的常见错误

| 错误 | 原因 | 修复 |
|---|---|---|
| `'ModelResponse' object has no attribute 'xxx'` | 用了 `result.response`（底层）而非 `result.output`（强类型）| 检查 LLMClient 是否用 `result.output` |
| `ValidationError: field required` | LLM 返回缺字段，重试 2 次仍失败 | 改 Output schema 让字段 Optional 或 default factory |
| `ValidationError: input should be ... ` (Literal) | LLM 返回值不在 Literal 列表 | 改 Output schema 加更宽的 Literal 或转 str |
| `NodeContractError: xxx 要求 yyy 已就绪` | 上游节点失败导致下游契约不满足 | 看 traces 找上游错误，修复或放宽契约 |

### 13.6 升级 SDK 版本时的注意事项

`pydantic_ai` 是核心依赖（当前 1.93.0）。升级版本时：
- API 改名风险：1.0 → 1.x 有过 `result_type → output_type`、`result.data → result.output` 等改名
- **升级前先在 PoC 脚本验证**：写一个最小 Agent 调用，确认 API 还能工作
- 不要直接 batch 改 11 节点然后才发现兼容性问题

---

## 附录：3 种常见错误及处理

| 错误信息 | 可能原因 | 处理 |
|---|---|---|
| `LLM 返回的 JSON 解析失败` | mimo-v2.5-pro 输出含 Markdown 包装或自然语言 | 改 prompt 强化"只返回 JSON"，或检查 LLMClient `_parse_json_object` 容错 |
| `Prompt 渲染失败: ... has no attribute ...` | YAML 模板里引用了 Pydantic 对象不存在的字段 | 检查 prompt 里的 `{{ p.xxx }}` 字段名与 schema 是否对齐 |
| `sqlalchemy.exc.InvalidRequestError: This session is provisioning a new connection` | LLM client 重用了节点的 db session 并发跑 | 已修复：`LLMClient` 内部自己开新 session（见 `common/llm/client.py`）|

