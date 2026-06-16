# 能力练习接入学习计划规范

> **Owner**：null（内部维护文档，能力 catalog 注册/调整请直接找 owner，无需自行参照本文操作）  
> **范围**：本文档约束"能力练习如何被学习计划纳管"。  
> 独立的能力页（如 essay-terms 闪卡、formula-ref 公式查阅）不接入学习计划，**不受本规范约束**。
>
> **更新策略**：本文件覆盖式更新。最近一次更新：2026-06-16（v2，新增第 8 节 param_schema 落地）。

---

## 0. 一图看懂

```
管理端                  后端 catalog                   学员小程序
─────────              ──────────────                ──────────────
配置能力                 study_ability_catalog          /pkg/ability/.../session
+ 子模块参数      ──→    + url_base                ──→  - 解析 query
+ 题数/正确率           + param_schema                  - 解析 studyPlanItemId
                       + 业务字段                      - 完成时上报 study_plan_item_id
                                                       - 回跳 /pages/study/item/?id=
```

学习计划 → 能力练习 → 学习计划 形成闭环。

---

## 1. 能力子模块的 3 种模式

接入前先判断你的能力属于哪种，决定改造工作量。

### 模式 A：参数驱动（推荐，工作量最小）

一个 session 页 + 通过 URL query 切换子模块。

| 现有例子 | 子模块切换参数 |
|---|---|
| `basic-calculation/session` | `?typeIndex=0..17`（18 种计算类型） |
| `data-analysis/fill-blank/session` | `?key=base_value/...`（公式类型） |
| `data-analysis/practice/session` | `?type=random&difficulty=normal` |
| `spatial/cube-box/session` | `?mode=opposite&kind=test` |

**适合**：子模块共用同一套交互逻辑，只是题型/参数不同。
**接入工作量**：1 个 session 页改造（解析 studyPlanItemId + 提交 attempt）→ 多个子能力可注册到 catalog。

### 模式 B：子页驱动

每个子模块一个独立 .vue 文件，子模块之间没有公共参数。

| 现有例子 | 子模块 |
|---|---|
| `thinking-training` | 24point / schulte / sudoku / mental-math 等 9 个 |

**适合**：子模块交互完全不同（数独 vs 24 点）。
**接入工作量**：每个子页都要单独改造一次（N 倍工作量）。**接入前请评估优先级**。

### 模式 C：浏览类（不接入）

非练习场景：闪卡背诵、公式查阅、术语字典。

**约束**：本文档不要求这类能力接入学习计划。

---

## 2. 接入清单（必填，模式 A）

接入一个新能力到学习计划，必须同时满足以下 7 项。

### 后端契约

#### ✅ 1. 在 `study_ability_catalog` 注册一条记录

走以下两条路径之一：

**1a. 静态兜底**：在 `backend/app/study_plan/service/ability_catalog.py:_ABILITY_CATALOG` 添加

```python
{
    'key': 'your_ability_key',
    'title': '展示名',
    'category': '业务分类',
    'url': '/pkg/ability/your-ability/session/index?param=default',
    'domain': 'civil_service',
    'default_minutes': 10,
    'default_question_count': 20,
    'default_accuracy': 0.8,
    'benchmark_seconds': 22,
    'supports_study_plan': True,    # 必须 True
    'supports_result': True,        # 必须 True
}
```

**1b. 数据库落库**：管理端 → 学习规划 → 能力练习目录 → 新增。

> 两条路径不要同时用。落库优先级 > 静态兜底（同 key 时落库覆盖）。

#### ✅ 2. catalog 字段约束

| 字段 | 必填 | 约束 |
|---|---|---|
| `key` | ✅ | 全局唯一，snake_case |
| `url` | ✅ | 以 `/pkg/ability/` 开头，必须包含可被覆盖的参数 |
| `supports_study_plan` | ✅ | 必须 `True`，否则不出现在学习计划下拉 |
| `supports_result` | ✅ | 必须 `True`，否则不能自动结算 |
| `default_question_count` | 推荐 | URL 里 `count` 的初始值 |
| `default_accuracy` | 推荐 | 0~1 浮点 |

### 小程序端契约

#### ✅ 3. session 页解析 `studyPlanItemId`

```ts
import { onLoad } from '@dcloudio/uni-app'
import { parseStudyPlanItemId } from '@/utils/studyPlanQuery'

const studyPlanItemId = ref<null | number>(null)

onLoad((query) => {
  studyPlanItemId.value = parseStudyPlanItemId(query as Record<string, unknown>)
  // ... 解析其它业务参数
})
```

#### ✅ 4. session 页支持 URL 参数覆盖

URL 里的所有参数（典型如 `count`、`difficulty`、`mode`）必须**支持外部覆盖**且有默认值兜底：

```ts
session.totalCount.value = Math.max(1, Math.min(100, toNumber(query?.count, 10)))
//                                                                       ^^ 默认值
```

**原因**：管理员在学习计划里改了"题数 30"，系统会派生新 URL `?count=30...`，session 页必须能消费这个新值。

#### ✅ 5. 完成时上报 `study_plan_item_id`

```ts
await api.studyAbilityAttemptSubmit({
  body: {
    ability_key: 'your_ability_key',
    study_plan_item_id: studyPlanItemId.value,   // 关键
    client_session_id: sessionId,
    total_count: 20,
    correct_count: 18,
    duration_seconds: 240,
    // ...
  }
})
```

后端会自动按 `study_plan_item_id` 触发 `complete_item`，无需前端再调 `studyPlanComplete`。

#### ✅ 6. 完成后回跳学习计划项

```ts
const sourceBackUrl = studyPlanItemId.value
  ? `/pages/study/item/index?id=${studyPlanItemId.value}`
  : null
```

session 页结算完成后跳 `sourceBackUrl`（已通过 study plan 来）或回到能力首页（独立入口来）。

### 验收

#### ✅ 7. 端到端流程跑通

1. 管理员造一个 ability 类型的模板项，绑定你的新 ability_key
2. 学员从今日页点能力卡片 → 进入 session 页 → URL 应包含 `studyPlanItemId=xxx`
3. session 页应正确显示参数（如题数 = 管理员设置值）
4. 学员完成做题 → 计划项状态自动变 `completed`
5. 计划项的"实际耗时""正确率"应有数据

任何一步失败 → 回到对应清单项排查。

---

## 3. catalog URL 参数约定（避免漂移）

### 当前现状（隐性契约，需要正规化）

各能力 URL 里的参数命名**没有统一**：

| 能力 | URL 里"题数"参数名 |
|---|---|
| basic-calculation | `count` |
| data-analysis/fill-blank | `count` |
| data-analysis/practice | `count` |
| spatial/cube-box | `count` |

幸运的是题数都叫 `count`，但其它参数（typeIndex / key / type / mode）就五花八门了。

### 推荐规范（新接入能力遵守）

| 参数语义 | 标准命名 | 类型 | 学习计划绑定字段 |
|---|---|---|---|
| 题数 | `count` | int 1-500 | `extra.question_count` |
| 子模块/子类型 | `type` 或具体语义命名 | string/int | `extra.ability_subtype` |
| 顺序 | `order` | `asc` / `shuffle` | - |
| 难度 | `difficulty` | `easy` / `normal` / `hard` | - |
| 学习计划标记 | `studyPlanItemId` | int | 自动注入 |
| 学习计划来源 | `fromStudyPlan` | `1` | 自动注入 |

> `count` 字段必须支持双向绑定到 `extra.question_count`，否则会出现"管理员配 30 题但学员做 20 题"的状态错位。

### 反例：不要这样写

```python
# ❌ 不可被覆盖的硬编码 URL
'url': '/pkg/ability/foo/session/index'

# ❌ 题数参数命名为非标准
'url': '/pkg/ability/foo/session/index?qNum=20'

# ❌ 没有默认值的参数
'url': '/pkg/ability/foo/session/index?count='
```

---

## 4. 完成判定规则（后端）

参考 `backend/app/study_plan/service/completion.py:_check_ability`：

| 判定条件 | 通过 | 不通过返回 |
|---|---|---|
| 都没配 `question_count` 和 `required_accuracy` | ✅ 任意完成即通过 | - |
| 配了 `question_count` 但学员做的题数不够 | ❌ | "未完成全部训练（X/Y）" |
| 配了 `required_accuracy` 但学员正确率不达标 | ❌ | "正确率 X% 未达到要求 Y%" |

**关键**：后端按 `extra` 里的 `question_count / required_accuracy` 校验，不是按 catalog 默认值。所以 URL 派生时必须把 `question_count` 同步到 URL `count`。

---

## 5. 现有 4 个能力的接入参考

| ability_key | session 页 | URL 参数 |
|---|---|---|
| `basic_calculation` | `/pkg/ability/basic-calculation/session/index` | `typeIndex` (0-17), `count` (1-100), `order`, `custom`, `customConfig` |
| `data_analysis_fill_blank` | `/pkg/ability/data-analysis/fill-blank/session/index` | `key` (base_value/...), `count` (1-100), `order` |
| `data_analysis_practice` | `/pkg/ability/data-analysis/practice/session/index` | `type` (random/...), `difficulty` (normal/...), `display` (text_chart/formula), `count` (1-100) |
| `spatial_cube_box` | `/pkg/ability/spatial/cube-box/session/index` | `mode` (opposite/net), `kind` (training/test), `count` (1-50) |

---

## 6. 验证脚本（推荐每次新增能力后跑）

```bash
# 后端：检查 catalog URL 是否包含必需参数
python backend/scripts/check_ability_catalog_urls.py

# 前端：检查 session 页是否实现 study plan 契约
# （未来计划增加，目前手动 grep）
grep -L "parseStudyPlanItemId" mini/src/pkg/ability/*/session/index.vue
```

> 上述脚本暂未实现，列在这里作为后续工程化目标。

---

## 7. 常见问题

### Q1: 我的能力是模式 B（子页驱动），怎么接？

每个子页单独走第 2 节的 7 项清单，每个子页对应一条 catalog 记录（key 类似 `thinking_24point` / `thinking_schulte`）。工作量是模式 A 的 N 倍。

### Q2: 学员从独立入口（不是学习计划）进 session 页，会不会出错？

不会。`studyPlanItemId` 默认为 null，session 页应做兜底：null 时不上报、不回跳，按独立练习处理。

### Q3: 同一个 ability_key 能不能注册两条 catalog（不同参数预设）？

技术上可以（catalog 用 `(domain, ability_key)` 唯一），业务上不推荐——会让管理员困惑选哪个。如果确实需要"同一能力的两个预设"，建议拆成两个 ability_key，比如 `basic_calc_easy` / `basic_calc_hard`。

### Q4: catalog 落库后能改 URL/url_base/param_schema 吗？

能。但**已存在的学习计划项的 `extra.ability_url` 是写入瞬间的派生快照**，不会随 catalog 改动而自动重派生——避免历史数据被污染。新建或编辑的计划项会用最新 catalog 重新派生。

> 如果业务上确需把历史项也批量同步到最新 catalog，参考第 9 节"批量重派生 URL"管理工具（暂未实现）。

### Q5: 新增 catalog 必须配 `url_base + param_schema` 吗？

**强烈推荐**。如果只配老的 `url` 字段，能力依然能工作（向后兼容），但管理员无法在表单里改子模块参数（typeIndex / difficulty 等），也无法享受"改题数 → URL 自动同步"的能力。详见第 8 节。

### Q6: 同一能力既有 catalog `url`（旧字段）又有 `url_base + param_schema`（新字段），后端用哪个？

**`url_base + param_schema` 优先**。两者都有时，后端的 `derive_ability_url()` 总是基于 schema 派生，`url` 字段只在 schema 缺失时作为回退。所以迁移老 catalog 时不需要删 `url`，加 `url_base + param_schema` 即可。

---

## 8. param_schema 与 URL 派生（B 方案，已落地）

### 8.1 一句话原理

catalog 表新增两个字段：

- `url_base`：URL 不带 query 部分，如 `/pkg/ability/basic-calculation/session/index`
- `param_schema`：URL query 参数的 schema 声明，结构如下

后端在保存计划项时根据 `url_base + param_schema + extra` 自动派生最终 URL，前端不再需要拼 URL。**原 `url` 字段保留，作为 schema 缺失时的回退**。

### 8.2 param_schema 字段格式

```jsonc
{
  "<param_name>": {
    "type": "int" | "enum" | "string",
    "label": "管理端显示名（可选）",
    "default": <默认值>,
    "min": <int 类型最小值，可选>,
    "max": <int 类型最大值，可选>,
    "options": [<value1>, <value2>, ...],   // enum 类型必填
    "bind_to": "<extra 里的逻辑字段>"         // 可选，绑定到学习计划字段
  }
}
```

`bind_to` 是关键设计：声明这个 URL 参数的值由 extra 里的某个逻辑字段决定。例如 `count.bind_to: 'question_count'` 让"目标题数"控件直接控制 URL 的 `count`，避免学员做的题数与计划设置不一致。

### 8.3 4 个能力的 param_schema 范本

直接在 `backend/app/study_plan/service/ability_catalog.py` 的 `_ABILITY_CATALOG` 列表里维护。完整示例：

```python
{
    'key': 'basic_calculation',
    'url_base': '/pkg/ability/basic-calculation/session/index',
    'param_schema': {
        'typeIndex': {'type': 'int', 'default': 0, 'min': 0, 'max': 17, 'label': '计算类型'},
        'count': {'type': 'int', 'default': 20, 'min': 1, 'max': 100, 'label': '题数', 'bind_to': 'question_count'},
        'order': {'type': 'enum', 'default': 'asc', 'options': ['asc', 'shuffle'], 'label': '顺序'},
    },
    # ... 其它字段同 1.2
}
```

其它 3 个能力（data_analysis_fill_blank / data_analysis_practice / spatial_cube_box）的 param_schema 已就位，参考代码即可。

### 8.4 派生流程

```
管理员表单选 ability_key + 设置参数
        ↓
extra = {ability_key, question_count: 30, typeIndex: 5, ...}
        ↓ POST 后端
enrich_ability_item_extra(db, extra):
   1. 读 extra.ability_key → 查 catalog
   2. 看 catalog.param_schema
   3. 对每个 schema 参数：
      - extra 里有同名字段 → 用之
      - 否则查 bind_to → 取 extra[bind_to]
      - 否则用 default
      - 按 type 做边界裁剪（min/max/options 校验）
   4. 拼 url_base + ?key1=v1&key2=v2... → 写回 extra.ability_url
        ↓
入库 extra.ability_url
        ↓
学员深链 → 准确做对应题数 / 子模块 / 难度
```

### 8.5 前端管理端 UI

`<AbilityParamFields>` 组件在 `frontend/.../views/study-plan/components/AbilityParamFields.vue`：

- 接收 `schema` 和 `modelValue`，根据 schema 动态渲染 a-input-number / a-select / a-input
- `bindKeys` prop 控制哪些字段由外层（如"目标题数"）接管，组件内不渲染
- catalog 没 param_schema 时，组件自动隐藏

template/index.vue 和 plan/index.vue 已经接入：选 ability_key → 自动渲染对应控件 → 切 ability_key 时清空 `ability_params` 防止脏数据。

### 8.6 验证清单

新增 / 调整 catalog 的 param_schema 后跑：

- [ ] 创建一个使用该 catalog 的模板项，所有控件可见
- [ ] 改一个 int 参数 → 保存后查 DB，`extra.ability_url` 应包含新值
- [ ] 改"目标题数" → URL 的 `count`（或 schema 里 `bind_to=question_count` 的字段）同步更新
- [ ] 切换到其它 ability_key → 老参数被清空，新控件正确加载
- [ ] 学员深链跳进 session 页 → URL query 与管理员配置一致

---

## 9. 后续规划（待决策）

以下是规范化的下一步候选项，**未启动**：

- [ ] 接入指南文档化的 lint：CI 检查 catalog 注册项是否同时有 mini session 页
- [ ] catalog 表落库的"批量重派生 URL"管理工具（针对 catalog url_base/param_schema 改动后，把历史已存计划项的 ability_url 一次性同步）
- [ ] catalog 数据从静态兜底正式迁入 DB（让管理员能在前端"能力练习目录"页面看到 url_base/param_schema）

需要时讨论后再启动，避免过度设计。

---

## 9. 联系人

- 后端 / DB / catalog schema：null
- 小程序 session 页：（待补）
- 管理端：（待补）
