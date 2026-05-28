# 申论批改 Agent - 本 session 完成报告

> **时间**：2026-05-27
> **范围**：P0 任务 + 架构改进 + Prompt 调优 + 黄金回归测试
> **前提**：基于 `prompt_tuning_guide.md` 指导文档逐项推进

---

## 一、P0 任务完成情况

| 指南条目 | 任务 | 状态 | 实现方式 |
|---------|------|------|---------|
| **8.3** | 黄金集回归测试 | ✅ | 4 份大作文样卷 (A/B/C/D)，`extends` 继承机制，`grade_one.py` 支持 |
| **8.6** | token 用量统计持久化 | ✅ | 11 节点 + pipeline 全覆盖，`ctx.last_llm_stats` → `AgentTraceItem.tokens_in/out` |
| **8.4 D** | 改写超字数二次压缩 | ✅ | `rewriter.py` `_compress_to_limit()` 超限调 LLM 压缩 |
| **8.5** | OCR e2e 联调 | ✅ | LlamaParse 云解析跑通，识别率约 90% |
| **11.5** | 应用文格式代码层检测 | ✅ | `scorer.py` `_check_application_format()` 正则检测标题/称呼/落款/署名 |

---

## 二、架构改进

| 改进项 | 状态 | 实现方式 | 改动文件 |
|--------|------|---------|---------|
| LLM 超时/网络重试 | ✅ | `_call_with_retry` 指数退避 3 次 (2s/4s/8s) | `llm/client.py` |
| Pipeline checkpoint | ✅ | 每节点完成后 `on_checkpoint` 回调落库 state_snapshot | `orchestrator/pipeline.py` + `grading_service.py` |
| SSE 进度同步到 DB | ✅ | checkpoint 回调写 `update_progress`，前端可轮询 | `grading_service.py` |
| 评分 cap 越界兜底 | ✅ | LLM 给分 > 满分时自动按比例缩放 | `scorer.py` |
| score_total 覆盖 bug | ✅ | rubric_loader 用调用方 score_total 覆盖 YAML total | `rubric_loader.py` |
| 改写行内对比 | ✅ | LLM 输出 changes，代码生成 `~~删除~~**新增**` 格式 | `rewriter.py` + `schema/report.py` |
| 申论批改独立配额 | ✅ | 新增 `agent_shenlun` 资源类型 + 规则入库 | `constants.py` + `quota/provider.py` + DB |

---

## 三、Prompt 调优

### 3.1 scorer.yaml - B 档锚点细化

**改动**：B 档从单一区间拆分为 B-/B+，增加判定标准。

| 档位 | 分数区间 (40 分制) | 判定标准 |
|------|-------------------|---------|
| B- | 24-27 | 结构完整但论述偏概括，引用 ≤3 处，并列罗列 |
| B+ | 28-31 | 结构严谨有递进，引用 ≥4 处且具体，每个论点有独立分析角度 |

### 3.2 scorer.yaml - 三题型特异规则

**综合分析**：
- "复述材料" ≠ "准确把握观点"——必须区分引用原文和提炼观点
- "重复观点+修饰词" ≠ "深入分析"——看是否揭示"为什么"和"怎么办"
- B-：每个角度只写"是什么"；A：每个角度有"现象→原因→本质→对策"递进链

**提出对策**：
- "加强 X / 完善 Y" 无具体动词+对象+方法 → 操作性维度最高 C
- 单条对策缺"谁来做 + 用什么工具 + 做什么事"三要素 → 判为"偏原则化"
- B-：有方向但缺抓手；A：有路径有主体有工具

**应用文**：
- 格式 5 要素逐项检查：标题 / 称呼 / 正文 / 落款 / 日期
- 缺 1 项 → 格式最高 B；缺 2 项 → 最高 C；缺 3 项以上 → D
- B-：格式基本对但内容偏泛；A：每项措施有"主体+对象+方法+标准"

### 3.3 reference_analyzer.yaml - 要点切粒度

**改动**：
- 新增 5 个合并案例（守正创新、统筹兼顾、因地制宜、多元筹资、医养结合）
- 新增"常见错误拆分警示"：5G灯杆+传感器+远程控制 不要拆 3 条
- 新增自检口诀：能被同一个"动词+目标"概括的必须合并

---

## 四、真实 LLM 验证结果

### 4.1 大作文黄金回归

| 档位 | 人工评分 | Agent 评分 | 偏差 | 档位一致 |
|------|---------|-----------|------|---------|
| A | 36/40 | 34.5/40 | -1.5 | A → A |
| B | 29/40 | 20.0/40 | -9.0 | B → C |
| C | 19/40 | 20.0/40 | +1.0 | C → C |
| D | 9/40 | 13.9/40 | +4.9 | D → D |

### 4.2 三题型验证（Prompt 调优前后对比）

| 题型 | 调优前 | 调优后 | 变化 | 质检 |
|------|--------|--------|------|------|
| 综合分析 | 8.0/10 | **7.6/10** | -0.4 | ✅ 0.96 |
| 提出对策 | 7.0/10 | **6.9/10** | -0.1 | ✅ 0.94 |
| 应用文 | 12.5/15 | **12.7/15** | +0.2 | ✅ 0.96 |

---

## 五、新增文件清单

| 文件 | 说明 |
|------|------|
| `scripts/test_ocr.py` | OCR e2e 测试脚本 (LlamaParse) |
| `scripts/test_ocr_baidu.py` | OCR e2e 测试脚本 (百度) |
| `tests/samples/golden_essay_materials.yaml` | 大作文公共材料 (题干+材料+参考答案) |
| `tests/golden/essay/essay_a_golden.yaml` | A 档样卷 (36/40) |
| `tests/golden/essay/essay_b_golden.yaml` | B 档样卷 (29/40) |
| `tests/golden/essay/essay_c_golden.yaml` | C 档样卷 (19/40) |
| `tests/golden/essay/essay_d_golden.yaml` | D 档样卷 (9/40) |

---

## 六、修改文件清单

| 文件 | 改动 |
|------|------|
| `service/common/llm/client.py` | 新增 `_call_with_retry` 指数退避重试，三种 invoke 方法包裹 |
| `service/common/orchestrator/pipeline.py` | 新增 `on_checkpoint` 回调 + `_build_snapshot` |
| `service/grading_service.py` | checkpoint 回调写 `update_progress` |
| `service/shenlun/nodes/scorer.py` | 新增 `_check_application_format` + 评分 cap 兜底 |
| `service/shenlun/nodes/rewriter.py` | 新增 `_build_inline_diff` + `_compress_to_limit` |
| `service/shenlun/nodes/rubric_loader.py` | 修复 score_total 覆盖 bug |
| `service/shenlun/prompts/scorer.yaml` | B 档锚点 + 三题型特异规则 |
| `service/shenlun/prompts/reference_analyzer.yaml` | 合并规则 + 错误拆分警示 |
| `schema/report.py` | 新增 `ChangeItem` + `RewrittenTextSection.inline_diff` |
| `schema/__init__.py` | 新增 `ChangeItem` 导出 |
| `access/constants.py` | 新增 `AGENT_SHENLUN` 资源类型 |
| `service/common/quota/provider.py` | 改为按 agent_type 映射 resource_type |
| `service/common/quota/__init__.py` | 更新导出 |
| `model/agent_task.py` | 已有 `state_snapshot` 字段 (无需改动) |
| `crud/crud_agent_task.py` | 已有 `update_progress` 方法 (无需改动) |

---

## 七、剩余问题

| 问题 | 说明 | 阻塞原因 |
|------|------|---------|
| B 档评分偏差 | 29/40 被评到 20/40，与 C 同分 | 需更多真实样卷，prompt 微调已到极限 |
| LLM 跨次波动 ±3 分 | temperature 已降到 0.1 | 需代码层方案 (如 scorer 双跑取均值) |
| 黄金集扩充 | 当前仅大作文 4 份 | 需用户提供真实样卷 + 人工评分 |
| quota 月度额度充值 | 规则已建，需给 `agent.shenlun.trial` 充值 | DB 操作 |

---

## 八、技术决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 改写对比格式 | `~~删除线~~**加粗**` (Markdown) | 小程序 towxml/wemark 支持，不依赖 HTML |
| inline_diff 生成方 | 代码生成，非 LLM 输出 | LLM 无法稳定输出格式化 diff |
| 评分硬约束策略 | 代码层 cap > prompt 软约束 | 代码权威 > LLM 建议，可复现 |
| LLM 重试策略 | 指数退避 3 次，仅网络异常 | 避免无限重试，区分网络错误和逻辑错误 |
| checkpoint 粒度 | 每节点完成后落库 | 平衡持久化开销和崩溃恢复粒度 |
| 配额隔离 | 独立 `agent_shenlun` 资源类型 | 避免和通用试看额度混淆 |
