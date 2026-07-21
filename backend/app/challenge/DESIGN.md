# 闯关模块设计交接

## 当前范围

当前闯关模块先围绕“资料分析”能力做分关训练。关卡不是直接从题库材料里随机抽，而是支持用生成器即时出题；每个关卡通过 `source_config.params.concept_ids` 控制本关只考哪些概念。

关键原则：

- 每一关只考本关定义的概念，不把后续概念提前混入。
- 第一、第二关都是 8 题，每个概念出现 2 次。
- 每关要求连续达标 5 次才算真正通过。
- 文档教学资料不绑定闯关内容本身，统一绑定到系统分类/知识点。
- 自动生成题只适合兜底和早期验证；正式体验优先使用真实材料里的数据锚点出题。

## 数据锚点驱动方向

自动生成题干容易“像题但不像真题”，资料分析闯关后续优先走真实材料锚点：

1. 先把材料里的关键数字、时间、比较对象标成 `study_material_anchor`，只保存位置和内容，不保存题目语义。
2. 用 `QuestionInteractionAnnotation.config.anchor_roles` 保存“本题中哪个锚点对应哪个语义角色”。
3. 用 `QuestionInteractionAnnotation` 生成定位题或概念识别题。
4. 闯关 section 使用题库来源，并通过 `interaction_type = anchorLocate` 等交互标注加载真实锚点。

基础锚点角色约定：

| role | 展示名 | 所属关卡 | 说明 |
| --- | --- | --- | --- |
| `current_value` | 现期 | 第 1 关 | 当前统计时期的数据 |
| `base_value` | 基期 | 第 1 关 | 用来比较的过去统计时期数据 |
| `growth_rate` | 增长率 | 第 1 关 | 增长量相对基期的比例 |
| `growth_amount` | 增长量 | 第 1 关 | 现期与基期的差值 |
| `yoy` | 同比 | 第 2 关 | 与上年同期比较 |
| `mom` | 环比 | 第 2 关 | 与上一个相邻统计周期比较 |
| `change_amount` | 变化量 | 第 2 关 | 数值变化了多少 |
| `change_rate` | 变化幅度 | 第 2 关 | 变化的百分比幅度 |

锚点示例：

```json
{
  "anchor_key": "m1001_current_value_income_2024",
  "anchor_type": "text_range",
  "text": "2024年全市文旅收入154亿元",
  "extra_data": {
    "concept_name": "现期",
    "metric": "全市文旅收入",
    "period": "2024年",
    "value": "154",
    "unit": "亿元",
    "confidence": "manual"
  }
}
```

题目交互标注中的角色映射示例：

```json
{
  "interaction_type": "anchorLocate",
  "candidate_anchor_ids": [101, 102, 103, 104],
  "answer_data": {
    "correct": "101"
  },
  "config": {
    "anchor_roles": {
      "101": "current_value",
      "102": "base_value",
      "103": "growth_rate",
      "104": "growth_amount"
    }
  }
}
```

交互标注示例：

```json
{
  "interaction_type": "anchorLocate",
  "instruction": "请在题干中选出“现期”对应的数据。",
  "selection_mode": "single",
  "candidate_anchor_ids": [101, 102, 103, 104],
  "answer_data": {
    "correct": 101
  },
  "config": {
    "concept_id": "current_value",
    "concept_name": "现期"
  }
}
```

这样第一关可以变成“看真实题干，点/选出哪个数据是现期、基期、增长率、增长量”，而不是让生成器编材料。生成器后续只保留为无锚点时的兜底方案。

### 闯关锚点题源配置

后端已经支持在 `pool` 题源中启用锚点角色池，不需要新增 `source_type`。配置方式：

```json
{
  "source_type": "pool",
  "question_count": 8,
  "source_config": {
    "mode": "anchor_role_pool",
    "bank_id": 1,
    "anchor_roles": [
      "current_value",
      "base_value",
      "growth_rate",
      "growth_amount"
    ],
    "display_scope": "block",
    "min_candidates": 4
  }
}
```

出题逻辑：

1. 按 `anchor_roles` 循环抽题，8 题 / 4 个角色时每个角色出现 2 次。
2. 每题先随机抽一个带有目标角色映射的 `QuestionInteractionAnnotation`。
3. 再使用该题目标注的候选锚点和答案锚点，角色只在本题上下文中生效。
4. 题型输出为 `anchorLocate`，答案为目标锚点 ID。
5. 前端使用 `interaction_config.anchors` 和 `interaction_config.material.blocks` 渲染可点击定位。

展示范围通过 `display_scope` 控制：

| display_scope | 展示范围 | 适用场景 |
| --- | --- | --- |
| `sentence` | 锚点所在句子 | 最简单的识别训练，但要求一句里至少有足够候选锚点，否则太简单 |
| `block` | 锚点所在材料块 | 第一关推荐默认值，信息量适中 |
| `material` | 整篇材料 | 后续综合关卡使用，最接近真实资料分析 |

第一关可用配置：

```json
{
  "mode": "anchor_role_pool",
  "anchor_roles": [
    "current_value",
    "base_value",
    "growth_rate",
    "growth_amount"
  ],
  "display_scope": "block",
  "min_candidates": 4
}
```

第二关可用配置：

```json
{
  "mode": "anchor_role_pool",
  "anchor_roles": [
    "yoy",
    "mom",
    "change_amount",
    "change_rate"
  ],
  "display_scope": "block",
  "min_candidates": 4
}
```

## 已完成关卡

### 第 1 关：四概念识别

目标：让用户能区分资料分析最基础的四个概念。

概念范围：

- 现期
- 基期
- 增长率
- 增长量

开发库当前配置：

- `challenge_key = data_analysis`
- `stage = stage_1`
- `level_no = 1`
- `global_no = 1`
- `question_count = 8`
- `source_type = pool`
- `source_config.mode = anchor_role_pool`
- `anchor_roles = ['current_value', 'base_value', 'growth_rate', 'growth_amount']`
- `display_scope = block`
- `required_attempts = 5`

注意：

- 第一关不能出现“同比、环比、变化量、变化幅度、变化率”等概念。
- 锚点题源按 `anchor_roles` 循环出题，题干展示真实材料块，并从同一材料中提供四类角色候选。
- 当前开发库已有材料锚点，但还需要为具体题目创建 `anchorLocate` 标注并补齐上述四类 `anchor_roles` 映射后才能正式出题。

同步脚本：

```bash
uv run python backend/scripts/configure_data_analysis_first_level.py --env-file backend/.env --execute
```

生产环境使用：

```bash
uv run python backend/scripts/configure_data_analysis_first_level.py --env-file backend/.env.prod --execute
```

### 第 2 关：比较口径与变化表达

目标：让用户区分比较口径和变化表达。

概念范围：

- 同比
- 环比
- 变化量
- 变化幅度

开发库当前配置：

- `challenge_key = data_analysis`
- `stage = stage_1`
- `level_no = 2`
- `global_no = 2`
- `previous_level_id = 第 1 关 ID`
- `question_count = 8`
- `source_type = generator`
- `generator_key = data_analysis_concept_identification_v1`
- `concept_ids = ['yoy', 'mom', 'change_amount', 'change_rate']`
- `required_attempts = 5`

注意：

- 第二关不要再考“现期值、基期值、增长率、增长量”。
- `change_rate` 的展示名是“变化幅度”，不是“变化率”。

同步脚本：

```bash
uv run python backend/scripts/configure_data_analysis_second_level.py --env-file backend/.env --execute
```

生产环境使用：

```bash
uv run python backend/scripts/configure_data_analysis_second_level.py --env-file backend/.env.prod --execute
```

## 生成器约定

核心文件：

- `backend/app/challenge/service/generator.py`
- `backend/app/challenge/service/challenge_service.py`

当前概念生成器：

- `data_analysis_concept_identification_v1`
- `data_analysis_concept_matching_v1` 是同一个生成逻辑的别名

生成流程：

1. 关卡 section 配置 `source_type = generator`。
2. `challenge_service._build_section_questions` 按 `section.question_count` 循环生成题目。
3. 每次生成会传入：
   - `question_index`
   - `question_count`
   - `source_config.params`
4. 生成器根据 `question_index % len(concept_ids)` 决定本题考哪个概念。
5. 当题量是 8、概念是 4 个时，每个概念刚好出现 2 次。
6. 第二轮会使用另一套题干表达，避免同概念两次只是数字不同。

如果后续新增关卡，优先复用这个结构：

```python
'source_config': {
    'generator_key': 'data_analysis_concept_identification_v1',
    'params': {
        'concept_ids': [
            '...',
        ],
    },
}
```

## 关卡规则约定

当前前两关都采用连续达标模式：

- `mode = consecutive_attempts`
- `required_attempts = 5`
- 前两次允许 75% 正确率
- 后三次要求 100% 正确率
- 时间限制逐步收紧

规则存储在 `ChallengeLevel.display_config['completion_rule']` 中，挑战开始时会进入 `rule_snapshot`，用于提交时判定本次是否达标。

## 后续新增关卡建议

建议每新增一关都写一个独立配置脚本，避免手工改数据库：

- `backend/scripts/configure_data_analysis_third_level.py`
- `backend/scripts/configure_data_analysis_fourth_level.py`

脚本至少要明确：

- `level_no`
- `global_no`
- `previous_level_id`
- `question_count`
- `concept_ids`
- `completion_rule`
- `display_config.concepts`
- `section.source_config`

不要只改前端显示。实际出题范围以后端数据库里的 `section.source_config.params.concept_ids` 为准。

## 测试

已有测试文件：

- `backend/app/challenge/tests/test_challenge_service.py`

当前覆盖点：

- 概念识别生成器可生成单选题。
- 第一关限定四基础概念后，不会混入同比、环比等概念。
- 第二关限定比较口径与变化表达后，8 道题中四个概念各出现 2 次。

运行：

```bash
uv run pytest backend/app/challenge/tests/test_challenge_service.py -q
```

## 已知容易踩坑

### 1. `concept_ids` 为空会回退到总概念池

如果数据库中 `source_config.params = {}`，生成器会从总概念池抽题。这样第一关就可能出现同比、环比、变化量等概念。

所以新增/修改关卡后必须复查数据库里的 `source_config`。

### 2. 题干也要跟着概念范围收窄

不能只限制选项，还要限制题干。否则题干里出现“比上月增加”这种内容，用户会觉得题目已经在考环比/变化量。

### 3. 变化幅度和变化率目前按同一类概念处理

当前系统里第二关展示“变化幅度”，内部 ID 是 `change_rate`。不要在题目里展示成“变化率”，避免和第一关“增长率”混淆。

### 4. 教学文档绑定不走 challenge

Halo 文档绑定到系统分类表：

- 表：`sys__doc_binding`
- 关联：`sys_category.id`

不要再新增 challenge 专用文档绑定表。
