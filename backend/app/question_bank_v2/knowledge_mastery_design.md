# 题库 V2 知识点掌握度与能力报告设计

> 本文是 `question_bank_v2` 知识点掌握度、知识点雷达图和未来考试能力报告的长期设计契约。后续实现、数据库迁移、接口设计和前端展示都应以本文为准。

## 1. 目标与边界

系统需要回答三个不同问题：

1. **当前掌握度**：用户现在对某个知识点的掌握情况。
2. **知识点雷达图**：用户在当前知识体系各顶层模块上的掌握分布。
3. **考试能力报告**：在一组测评题目中，用户的潜在能力、题目难度和测评可靠性。

| 能力 | 推荐模型 | 主要用途 |
|---|---|---|
| 当前知识点掌握度 | 加权证据 + Beta 平滑 + 时间衰减；后续可升级 BKT | 学习看板、薄弱点推荐、雷达图 |
| 复习时间安排 | 现有客观重练阶梯；未来可接 FSRS | 错题重练、复习提醒 |
| 考试能力 | IRT（先 Rasch/1PL，后续 2PL） | 模拟考、考试报告、能力比较 |

不把题目掌握状态、知识点掌握度、FSRS 记忆保持率和 IRT 能力值混成一个字段。第一阶段不引入 DKT、LSTM 或 Transformer 等深度知识追踪模型。

## 2. 当前知识体系约定

### 2.1 默认体系

当前所有正式题目已经覆盖 `default` 知识体系，因此当前阶段采用：

```text
用户不主动选择知识体系
    -> 使用当前默认体系
    -> 当前默认体系为 version='default'
```

当前不向普通用户开放知识体系版本切换入口。现有 `knowledge_system_choice` 字段保留，作为未来开放版本选择时的扩展入口；当前不要删除，也不要在前端暴露。

代码和接口文档中应保留以下备注：

> 当前阶段默认使用 `default` 知识体系，用户暂不提供知识体系版本切换入口。后续开放版本选择后，使用 `knowledge_system_choice` 解析用户选择的 `system_id`。

### 2.2 `default` 的语义

`default` 只表示“没有显式选择版本时使用的默认知识体系”，不表示所有题目天然属于该体系、未标注题目可以自动归入该体系，或不同版本的掌握度可以混合计算。

掌握度数据始终按 `system_id` 隔离。

## 3. 知识体系细化规则

当前体系示例：

```text
A
├─ B
├─ C
└─ D
```

未来可能变为：

```text
A
├─ B
│  ├─ F
│  └─ G
├─ C
├─ D
└─ E
```

### 3.1 可以继续使用 `default` 的变更

以下变化不改变已有知识点语义，可以继续修改当前 `default`：

- 在 A 下增加 E；
- 在 B 下增加 F、G；
- 增加新的叶子知识点；
- 修改知识点描述；
- 调整同层排序。

### 3.2 必须新建体系版本的变更

以下变化会改变已有知识点含义，应创建新的体系版本：

- 已有知识点改名且教育语义发生变化；
- 已有知识点移动到另一个父节点且语义发生变化；
- 一个知识点被拆成多个互不等价的知识点；
- 多个知识点合并成一个新知识点；
- 删除或废弃已经产生作答数据的知识点。

正式发布后的体系版本应视为不可变快照。需要修正时创建新版本，不要直接修改历史版本的结构语义。

### 3.3 新增细分知识点的历史数据

当 B 下新增 F、G 时：

| 对象 | 处理 |
|---|---|
| B 的历史掌握度 | 保留 |
| F 的历史掌握度 | `unknown`，从新标注、新作答开始累计 |
| G 的历史掌握度 | `unknown`，从新标注、新作答开始累计 |
| 过去只标注 B 的题目 | 继续计入 B |
| 过去只标注 B 的题目 | 不自动分配给 F 或 G |
| B 的分数 | 不复制给 F、G |

宁可显示未评估，也不能制造没有证据的精确分数。

## 4. 题目知识点标注规则

### 4.1 标注完整性

正式题库在当前生效知识体系下应尽量保持题目全覆盖。发布校验应检查正式题目是否至少有一个当前体系下的知识点关联。未完成标注的题目只能进入草稿或待标注状态，不应静默参与知识点统计。

### 4.2 未标注题目

如果题目在当前体系下没有知识点标注：

- 不参与任何知识点掌握度；
- 不自动归入 `default`；
- 不创建“其他知识点”；
- 计入 `unmapped_question_count`；
- 降低对应范围的 `coverage_rate`。

如果题目标注到父节点 B，但没有细分到 F/G，则题目已经覆盖 B，只是不能为 F/G 提供细粒度证据。

### 4.3 多知识点题目

题目关联使用现有字段：

- `role='primary'`：主要考察知识点；
- `role='secondary'`：次要考察知识点；
- `role='prerequisite'`：前置知识点。

掌握度证据规则：

- `primary` 和 `secondary` 参与本题证据分配；
- 同一题的参与权重按题内总权重归一化；
- 没有配置权重时，单知识点题目默认权重为 1；
- `prerequisite` 不直接计入主知识点掌握分数；
- `prerequisite` 用于学习路径、薄弱前置知识推荐和解释性提示。

示例：

```text
题目 Q：
  B: primary, weight=0.7
  C: secondary, weight=0.3
```

本题答对时，B 获得 0.7 的正确证据，C 获得 0.3 的正确证据。

## 5. 掌握度投影设计

### 5.1 与题目掌握度分离

现有 `QbUserQuestionMastery` 继续表示用户-题目状态：

```text
user_id + question_id
```

新增知识点掌握度投影，不修改题目掌握度的语义：

```text
qbank_v2_user_knowledge_mastery
```

建议字段：

```text
id
user_id
system_id
knowledge_point_id

mastery_score
confidence_score
effective_sample_size
attempt_count
correct_count
weighted_correct
weighted_wrong

last_attempt_time
state
model_version
calculated_time
deleted
created_time
updated_time
```

唯一约束建议为：

```text
user_id + system_id + knowledge_point_id + deleted
```

所有分数必须明确绑定 `system_id`，禁止跨知识体系版本直接聚合。

### 5.2 状态字段

建议状态：

```text
unknown     没有足够证据
learning    有证据但仍不稳定
stable      有足够证据且当前掌握稳定
mastered    达到产品定义的掌握阈值
```

`mastered` 不是永久状态。由于当前掌握度带时间衰减，长期没有复习时可以回落到 `stable` 或 `learning`。

### 5.3 当前掌握度与历史正确率分离

至少保留三个概念：

```text
mastery_score
    当前掌握度，带时间衰减

lifetime_accuracy
    历史累计正确率，不衰减

confidence_score
    当前掌握度的证据可信度
```

雷达图使用 `mastery_score`，历史报告可以使用 `lifetime_accuracy`。

### 5.4 第一阶段计算模型

第一阶段采用可解释、可重建的 Beta 平滑模型，并加入时间衰减。

每条作答证据包含：

```text
correctness
    客观题答对=1，答错=0
    主观题使用 score / max_score

knowledge_weight
    题目对当前知识点的归一化权重

decay
    随作答距今天数衰减
```

概念公式：

```text
alpha = alpha0 + sum(decay * knowledge_weight * correctness)
beta  = beta0  + sum(decay * knowledge_weight * (1 - correctness))

mastery_score = alpha / (alpha + beta)
effective_sample_size = sum(decay * knowledge_weight)
```

初始值建议：

```text
alpha0 = 1
beta0 = 1
half_life_days = 30（配置项 `QBANK_V2_MASTERY_HALF_LIFE_DAYS`）
```

半衰期必须配置化，不得散落在业务代码中。配置和算法变更要体现在 `model_version` 中。

### 5.5 作答证据范围

参与掌握度计算：已判分客观题、已完成人工或 AI 判分的主观题、可以换算为部分得分的主观题。

不参与：未作答、自动保存草稿、待判分主观题、判分失败或结果不完整的作答。

## 6. 版本与历史作答

### 6.1 作答时保存知识点快照

知识点标注会变化，因此不能只在查询时根据当前题目标注回溯历史。

建议新增作答-知识点快照表：

```text
qbank_v2_question_attempt_knowledge_point

attempt_id
user_id
question_id
system_id
knowledge_point_id
weight
role
mapping_source
```

作答提交时保存当时生效的知识点关联。管理员后续调整题目标注，不应让历史雷达图无故变化。

如果当时没有标注，记录为未映射事实，不要猜测补齐。

### 6.2 新版本的历史继承

默认策略：

```text
能够明确映射的旧知识点
    -> 可以继承历史作答证据

旧父节点拆成多个新子节点，但历史无法区分
    -> 新子节点不继承分数，显示 unknown

没有可靠映射
    -> 新版本从新作答开始统计
```

如果未来确实需要跨版本继承，应增加显式映射表，而不是通过名称或 code 猜测。

## 7. 知识点雷达图

### 7.1 展示范围

雷达图只展示当前生效体系的顶层知识点，建议最多 6-8 个轴。不跨版本混合，不把所有叶子节点都直接展示在雷达图上。

### 7.2 返回字段

建议接口返回：

```json
{
  "system_id": 12,
  "system_version": "default",
  "points": [
    {
      "knowledge_point_id": 88,
      "name": "数据结构",
      "mastery_score": 0.76,
      "confidence_score": 0.84,
      "effective_sample_size": 18.5,
      "coverage_rate": 0.91,
      "state": "stable",
      "last_attempt_time": "2026-08-20T10:00:00+08:00"
    }
  ],
  "unmapped_question_count": 0,
  "coverage_rate": 1.0
}
```

`unknown` 不应在前端转换为 0 分。应该显示为未评估、灰色或缺少证据。

父节点聚合时，按有效样本量加权，而不是简单平均子节点分数：

```text
parent_score =
    sum(child_score * child_effective_sample_size)
    / sum(child_effective_sample_size)
```

## 8. 接口规划

当前版本不向用户开放版本切换，但接口设计应预留 `system_id`。

建议接口：

```text
GET /knowledge-systems/{system_id}/mastery
GET /knowledge-systems/{system_id}/mastery/radar
GET /knowledge-points/{point_id}/mastery
```

调用规则：

- 前端当前传入系统解析出的 `default system_id`；
- 后端必须校验用户有权访问该知识体系和对应题库范围；
- 未传 `system_id` 时，后端按当前用户偏好解析，当前回落 `default`；
- 后续开放版本选择时，使用 `knowledge_system_choice`。

## 9. 未来考试能力报告与 IRT

### 9.1 IRT 是什么

IRT（Item Response Theory，项目反应理论）用于同时估计用户潜在能力 `theta`、题目难度 `b`、题目区分度 `a`，以及可选的猜测参数。

简单 Rasch/1PL 模型主要使用用户能力和题目难度；2PL 再增加题目区分度。

IRT 适合回答：用户的测评能力是多少、这道题相对于用户能力是否过难、这套试卷能否有效区分不同水平的用户。

IRT 不替代知识点掌握度：

```text
知识点掌握度：学习看板和雷达图
IRT 能力值：考试和测评报告
重练调度：复习时间安排
```

### 9.2 IRT 后续数据表

未来可以新增：

```text
qbank_v2_question_calibration

question_id
model_type
difficulty
discrimination
guessing
sample_count
standard_error
model_version
calculated_time
```

```text
qbank_v2_user_ability

user_id
system_id
assessment_scope
ability_theta
standard_error
answered_count
model_version
calculated_time
```

实施顺序建议：先 Rasch/1PL，再根据样本量和题目质量升级到 2PL。不要在样本不足时手工填写 IRT 参数。

## 10. 实施顺序

### 阶段 0：先修正语义（代码已落地）

- [x] 将知识点统计中的硬编码 `version='default'` 改成解析当前生效 `system_id`；
- [x] 在文档和接口注释中明确当前用户暂不切换体系版本；
- [ ] 明确正式题目在当前体系下的知识点覆盖校验（待题库与领域/科目体系的关联契约明确后接入发布校验）；
- [x] 明确题目知识点权重和角色规则。

### 阶段 1：掌握度基础设施（代码已落地，回填需上线后执行）

- [x] 新增 `qbank_v2_user_knowledge_mastery`；
- [x] 新增 `qbank_v2_question_attempt_knowledge_point` 快照表；
- [x] 建立作答后知识点投影更新服务；
- [x] 支持 Beta 平滑、时间衰减、有效样本量和置信度；
- [x] 支持投影按 `model_version` 重建；
- [ ] 为已有 `default` 作答历史执行一次回填（脚本：`backend/scripts/backfill_qbank_v2_knowledge_mastery.py`，迁移上线后执行）。

### 阶段 2：雷达图和知识点看板（基础接口已落地）

- [x] 增加知识点掌握度查询接口；
- [x] 增加顶层知识点雷达图接口；
- [x] 返回 `mastery_score`、`confidence_score`、`coverage_rate`；
- [x] 未评估知识点不得显示为 0；
- [ ] 增加薄弱知识点排序和推荐练习范围。

### 阶段 3：知识体系细化

- [ ] 新增 F/G 时保留 B 的历史掌握度；
- [ ] F/G 从新标注、新作答开始统计；
- [ ] 需要拆分、合并或改义时创建新体系版本；
- [ ] 如需跨版本继承，增加显式知识点映射表；
- [ ] 禁止通过名称相似度自动迁移历史掌握度。

### 阶段 4：考试能力报告

- [ ] 统计题目作答样本量和质量；
- [ ] 建立题目难度校准任务；
- [ ] 先实现 Rasch/1PL 能力估计；
- [ ] 返回能力值、标准误和测评覆盖范围；
- [ ] 数据量足够后评估 2PL；
- [ ] 能力报告与知识点掌握度使用不同接口和字段。

## 11. 验收标准

### 数据正确性

- [ ] 同一用户在不同 `system_id` 下的掌握度互不覆盖；
- [ ] 未标注题目不会出现在任何知识点掌握度分子或分母中；
- [ ] 标注到 B 的旧题不会自动分配给新建 F/G；
- [ ] 待判分主观题不会更新掌握度；
- [ ] 多知识点题目按归一化权重分配证据；
- [ ] 题目标注修改后，历史作答快照仍保持不变。

### 展示正确性

- [ ] 当前默认展示 `default` 体系；
- [ ] 当前前端没有版本切换入口；
- [ ] 未评估知识点显示 unknown，而不是 0；
- [ ] 雷达图只展示当前体系顶层知识点；
- [ ] 雷达图同时显示掌握度、置信度和覆盖率。

### 可演进性

- [ ] 掌握度投影包含 `model_version`；
- [x] 可以从 `QbQuestionAttempt` 和知识点快照重建投影；
- [ ] 新增知识点不需要修改历史题目才能上线；
- [ ] 新体系版本不覆盖旧体系掌握度；
- [ ] 未来 IRT 能力报告不依赖修改当前知识点掌握度字段。

## 12. 当前不要做的事情

- 不要把 `QbUserQuestionMastery` 直接改成知识点掌握表；
- 不要只按 `knowledge_point_id` 存用户掌握度；
- 不要把所有版本合并成一棵“万能知识树”；
- 不要把未标注题目塞进“其他”；
- 不要把 B 的历史分数复制给新增 F/G；
- 不要把 IRT、BKT、FSRS 的结果混成一个字段；
- 不要在体系已经产生作答数据后随意修改已有知识点的教育语义；
- 不要在没有题目和用户样本时提前上线复杂 IRT 参数。
