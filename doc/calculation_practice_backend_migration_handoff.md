# 计算练习后端迁移：本地验证与验收交接

更新时间：2026-10-03  
当前状态：**代码收尾与本地自动化验证完成，工作区未提交，等待用户真机验收。**

> 这不是上线完成说明。后端 423 项测试、小程序 34 项测试、相关静态检查、全量类型检查及小程序构建已通过；完整后端启动、真实服务联调和真机验收尚未执行。本轮不提交、不部署、不恢复 SDK，也不主动操作生产服务。

## 1. 目标与范围

将小程序“资料分析”下三个入口的题目生成能力迁移至 `backend/app/gongkao`：

1. **基础计算练习**：17 个预设题型 + 自定义四则/幂运算。
2. **资料分析专项**：11 类填空/比较题，以及 16 类实战选择题 + 随机模式。
3. **进阶计算练习**：除法放缩、乘法放缩、假设分配、范围估算、特征分数、差分法，以及混合速算。

核心要求：随机数、出题规则、答案、干扰选项、解析在后端产生；小程序获取题单后展示和交互。后续 Agent / skill 可以直接调用同一 service 或 HTTP 接口。

当前实现中，输入、草稿、计时、作答交互、即时判定和记录上报仍由小程序处理。若后续需要服务端统一判分/会话持久化，可在这套生成能力上继续扩展。

## 2. 先确认工作区，避免混入同事的改动

这里有 **两个独立 Git 工作区**：

| 工作区 | 路径 | 说明 |
| --- | --- | --- |
| FBA 主仓库 | `D:\100_Work\101_Program\Proj\fba` | 后端和本文档所在仓库 |
| 小程序仓库 | `D:\100_Work\101_Program\Proj\fba\mini` | 独立 Git 仓库；主仓库 `.gitignore` 忽略了 `mini/` |

继续工作时，分别在这两个目录执行 `git status --short` 和相关文件的 `git diff`。**仅查看主仓库状态，会漏掉全部小程序改动。**

- 两个工作区都存在其他任务的未提交改动；有些小程序文件也可能混有同事的修改。
- 本次没有提交、推送或部署代码。
- 主仓库原有 OAuth、`render_book`、`pnpm-lock.yaml`、`pnpm-workspace.yaml` 等改动不属于本次迁移；`backend/core/conf.py` 仅追加本迁移的 5 条精确公开路径，保留已有 OAuth 正则改动。
- `mini` 中 `App.vue`、`QuestionCard.vue`、资料分析配置页、其他练习页面等也有其他改动；以实际 diff 为准。
- 本次覆盖了 `mini/src/pkg/ability/utils/calcConfig.ts` 的生成部分；该文件当前为未跟踪文件，后续整理小程序提交时应一起核对。

## 3. 已落地的后端结构

以下路径均相对主仓库根目录：

```text
backend/app/gongkao/
├── api/router.py                          # 已注册新路由
├── api/v1/calculation_practice.py          # 目录 + 四个生成接口
├── schema/calculation_practice.py          # 请求、题目、题单、目录模型
├── service/calculation_practice_service.py # 对外独立 service
├── service/calculation/
│   ├── __init__.py
│   ├── common.py                          # 独立随机状态、难度、偏向、选项工具
│   ├── basic.py                           # 基础计算和耗时评价阈值
│   ├── fill_blank.py                      # 专项填空与比较题
│   ├── data_practice.py                   # 专项实战选择题
│   └── advanced.py                        # 进阶六类算法与混合模式
└── tests/
    ├── test_calculation_practice.py       # 406 项数学与接口测试
    └── test_calculation_practice_auth.py  # 17 项主路由/鉴权与白名单边界测试
```

对外实例：`calculation_practice_service`。主要方法：

```python
get_catalog()
generate_basic(*, obj)
generate_fill_blank(*, obj)
generate_data_practice(*, obj)
generate_advanced(*, obj)
```

这是纯计算生成服务，没有新建数据库表，也没有引入数据库会话或 HTTP Request 参数。

### 已顺带修正的生成问题

- 原“混合速算”实际上回退为除法放缩，现改为随机混合 6 类算法。
- 下降场景的增长率答案保留负号，并按展示出来的现期/基期数据核算。
- 混合增长率改为按基期总量计算，避免错误地用现期量作权重。
- 增长贡献率材料补充具体的部分增量，公式模式也提供可计算的数字。
- 下降率限制在合理范围，避免 `1 + r` 为零或负数。
- 部分/整体关系在两期都保持成立；差值增长率避免基期差接近零。
- 负数、零答案的干扰项生成有界，选项去重且保留正确答案。
- 差分题让接近的两个分式真正决定最大/最小值，并修正解析关系。
- 特征分数的小增长率采用相对扰动，参考答案按题干增长率核算，同时给出速算近似。
- 自定义幂运算限制生成的答案在 JavaScript 安全整数范围内。

## 4. 接口约定

统一前缀：`/api/v1/gk/calculation-practice`，实际 `/api/v1` 取自项目配置。

| 方法 | 路径 | 请求重点 |
| --- | --- | --- |
| GET | `/catalog` | 获取所有题型 key、显示名称、分组、参数选项和默认自定义配置 |
| POST | `/basic/generate` | `type_key`、`count`、`seed`、可选 `custom_config` |
| POST | `/fill-blank/generate` | `type_key`、`difficulty`、`method_bias`、`count`、`seed` |
| POST | `/data-practice/generate` | 同上；`type_key=random` 时混合题型 |
| POST | `/advanced/generate` | `method`、`mode`、`count`、`seed` |

这 5 个精确路径同时列入后端 JWT 白名单；无凭证和携带失效凭证均可取题。不以 `/gk` 或计算练习路径前缀整体放行，练习记录上报、申论批改等接口仍需原有鉴权。

### 通用参数

- `count`：整数，1～100，默认 10。
- `seed`：可选非负安全整数；省略时由后端生成并返回。`0` 是合法种子。
- `difficulty`：`easy / normal / hard`，默认 `normal`。
- `method_bias`：`auto / scaling_div / char_fraction / allocation`，默认 `auto`。
- `mode`：进阶训练使用 `formula / question`，默认 `formula`。
- `method`：进阶训练使用 `scaling_div / scaling_mul / allocation / range_est / char_fraction / difference / mixed_speed`。
- `type_key` 使用稳定字符串，不直接依赖旧页面索引；基础目录通过 `type_index` 保留旧页面顺序。
- 哪些专项题型支持 `method_bias`，查 `/catalog` 的 `supports_method_bias`。
- 未知字段、未知枚举、非法题量和非法自定义参数由 Schema 拒绝。

### 自定义基础计算

```json
{
  "type_key": "custom",
  "count": 10,
  "seed": 20261003,
  "custom_config": {
    "mode": "standard",
    "firstDigits": 3,
    "operators": ["×", "÷"],
    "secondMode": "fixed",
    "secondDigits": 2,
    "fixedSecond": 15,
    "rangeStart": 10,
    "rangeEnd": 99
  }
}
```

- 位数范围 1～4；固定数、范围端点为 1～999999 的整数。
- `secondMode`：`random_digits / fixed / range`。
- `mode=power` 时，按现有规则将第二个数限制为 2～4 次幂。
- `custom_config` 仅允许用于 `type_key=custom`；省略则使用默认值。
- `custom_config` 接受 camelCase 和 Python snake_case 字段。

### 返回结构

继续使用 `{ "code": 200, "msg": "...", "data": ... }` 包装。

`data` 通用字段为：

```text
generator_version   出题算法版本，目前 1.0.0
seed                本题单种子
count               实际题量
questions           完整题单，包含参考答案和解析
```

- 基础题单额外返回 `type_key`、实际 `custom_config`、`performance_thresholds`。
- 题目对象沿用小程序 **camelCase**：例如 `correctIndex`、`correctDeltaB`、`leftDisplay`。
- 基础题提供 `expression / answer / relativeTolerance / explanation`。
- 专项选择题提供 `material / question / options / correctIndex / answer / answerUnit / formulaHint / operands / explanation`。
- 进阶题通过 `method` 区分强类型结构，包含原数、目标数、改变量等算法所需字段。
- `correctIndex` 从 0 开始；进阶输入题为 -1、`options=[]`，差分题在两种模式下都是选择题。
- 重现题单需要保存 **完整请求参数 + seed + generator_version**。跨算法版本不保证同种子得到同样的题。

## 5. 小程序已经改到哪里

以下路径相对 `mini` 仓库根目录。

### 新增

| 文件 | 用途 |
| --- | --- |
| `src/api/calculationPractice.ts` | 四种生成请求、目录接口、返回类型和统一拆包 |
| `src/composables/useGeneratedPractice.ts` | 取题状态、失败重试、取题后启动计时、页面卸载后忽略迟到响应 |
| `src/components/common/PracticeLoadState.vue` | 加载提示与重试入口 |
| `src/utils/calculationCatalog.ts` | 展示/历史使用的共享静态题型标识与名称 |

### 已接入生成接口的页面

- `src/pkg/ability/basic-calculation/session/index.vue`
- `src/pkg/ability/data-analysis/fill-blank/session/index.vue`
- `src/pkg/ability/data-analysis/practice/session/index.vue`
- `src/pkg/ability/adv-calc/session.vue`
- `src/pkg/ability/basic-calculation/index.vue`：导出题单时先异步向后端取题，再走原有 render-book 任务。

### 配套改动

- `src/pkg/ability/utils/basicCalculation.ts`、`dataAnalysis.ts`、`dataPractice.ts`、`calcConfig.ts` 已去掉对应生成逻辑，保留类型、表单和展示辅助。
- `src/pkg/ability/adv-calc/utils/generator-*.ts` 共 6 个生成器已删除。
- `src/pkg/charts/utils/basicCalculation.ts`、`dataAnalysis.ts`、`dataPractice.ts` 三份旧副本已删除；历史页改用共享目录。
- `src/utils/practiceShared.ts`：结果及上报 metadata 增加种子/版本与基础题阈值；数字输入可指定长度。
- `src/composables/usePracticeSession.ts`：重开/停止时清理结束与聚焦定时器，取消迟到的 nextTick 聚焦；最后一题重复确认不会重复记录/结算；取题完成后重置时间，输入长度可配置。
- `src/components/common/PracticeAnswerPanel.vue`：新增 `maxLength`，基础幂运算页面设为 16，其他页面默认 12。
- `src/pkg/ability/basic-calculation/result/index.vue`：优先读取后端返回并保存的阈值，旧记录保留本地兜底。
- `src/utils/auth-request.ts`：新生成接口作为公开练习接口跳过自动附加登录凭证。

- 各页面的 `generation` ref 初始化顺序、导入排序与填空页样式类排序已复查并通过 ESLint。
- 填空历史使用 `formatDataAnalysisExpression()` 保存双分式两边、比较题后缀及普通表达式，不再只存左侧分式。
- 新增 `tests/load-ts.cjs`、`tests/calculation-practice.test.cjs` 和 `tests/shenlun-evaluation.test.cjs`，使用本地 TS 加载器和测试替身，不调用真实 AI。

当前选择器仍使用共享静态显示目录；`getCalculationPracticeCatalog()` 已封装，但页面尚未切换成动态目录。它不包含随机出题逻辑。

## 6. 验证结果与边界（2026-10-03）

### 后端

最终执行：

```powershell
# 在 FBA 主仓库运行
uv run --no-sync pytest --noconftest backend/app/gongkao/tests/test_calculation_practice.py backend/app/gongkao/tests/test_calculation_practice_auth.py -q -o addopts= --disable-warnings --tb=short
```

结果：**423 passed，676 warnings**（包含框架依赖弃用提示）。

- 原 406 项覆盖所有题型/难度/偏向组合、答案与材料数学一致性、唯一选项、负数和零答案、混合速算、种子复现、参数拒绝、HTTP 包装和 OpenAPI。
- 新 17 项覆盖主应用 5 个入口 × 无凭证/残留 Bearer 的 10 种请求，以及 7 个不应放开的路径边界。
- Ruff check 通过，范围为迁移 Python 文件及 `backend/core/conf.py`；迁移的 12 个 Python 文件通过 Ruff format --check。未整文件格式化并发修改中的 conf。
- 已处理类型导入、浮点近似断言、数学测试辅助函数复杂度及长行问题，没有删去数学断言。

**测试隔离边界**：`--noconftest` 避开全局数据库初始化。原测试自行构建 FastAPI 测试应用；新增测试调用真实 `register_app()` 并保留内建路由和中间件，但替换动态插件发现/钩子与 IP 定位 helper，关闭 metrics，不进入 lifespan。显式拦截同步/异步 Redis、SQLAlchemy 连接、asyncio TCP 建连和非本地 socket 连接。这是隔离环境的 ASGI 路由/鉴权验证，不是完整后端启动或端到端验证。

**隔离修正记录**：早期新增集成测试曾意外尝试连接配置中的 Redis 并超时（目标环境未核实），当时仅拦截 `socket.connect`，未覆盖 Windows Proactor 的异步连接。最终测试补齐上述阻断，并替换仍会读取 Redis 的 IP 定位 helper 后通过。未主动执行数据库或 Redis 业务写操作，但不能将早期失败运行描述为“完全没有外部连接尝试”。

### 小程序

在 mini 仓库最终执行：

```powershell
node --test tests/http.test.cjs tests/calculation-practice.test.cjs tests/shenlun-evaluation.test.cjs
pnpm run type-check
$env:SKIP_OPEN_DEVTOOLS='true'; pnpm run build:mp
```

- **34 passed**：原 HTTP 15 项、计算练习 12 项、申论契约/交互 7 项。
- **全量 type-check 通过**：此前 `useSubjectiveEvaluation.ts` 的 9 处类型错误已修复，未恢复 SDK 或用 any 强行兼容旧申论 DTO。
- **迁移相关文件 ESLint 通过**，包含计算页面/共享辅助、历史页以及申论 API、DTO、转换函数、composable 和 contracts。
- **build:mp 通过**：保留 `pkg/shared/index` 找不到、4 个 carbon 图标加载和小程序不支持 p 标签选择器的警告；不将这些警告视为已解决。
- 本轮未改依赖声明或锁文件；`fs-extra`、`zrender`、`tslib` 已由并发的去 SDK 工作补齐，相关锁文件改动保留。

新增计算测试验证：取题单飞、成功才计时、失败显式重试且无本地生成兜底、卸载后忽略迟到响应、重复结算防护、重开/停止清理定时器及聚焦、16 位输入、seed/version/阈值和旧记录兼容、双分式历史、四种接口题量与单层拆包。导出任务、账号切换和真实交互只做代码复查，仍需实际验收。

### 申论类型错误的真实契约修复

- 依据 `backend/plugin/agent/schema/grading.py`、`api/v1/shenlun_grading.py` 和 `service/shenlun/validation.py`（不是旧 `plugin/agents`）维护 `src/api/types/shenlun.ts`。
- `POST /api/v1/agent/shenlun/attempts/{attempt_id}/grading` 真正发送 `{ force_regenerate }`，以返回的 `run_id` 轮询 `GET /api/v1/agent/shenlun/runs/{run_id}`。qbank 兼容启动接口没有请求体，不能代替重新批改。
- `status` 按后端字符串契约处理，成功为 `succeeded`；`failed/cancelled` 终止轮询，`completed` 是阶段名，不再误当成功状态；同题加载期间不重复启动，成功但空报告明确报错。
- `result_payload` 是未强类型化的 JSON dict，转换函数逐项校验数字/字符串，读取实际的 `summary`、`point_matches`、`optimization_suggestions`、`revised_answer` 等字段。UI 使用投影类型，不捏造后端未返回的 `user_id/created_time`，也不回退到旧 `report/state_snapshot`。
- 7 项测试覆盖真实字段映射、零分/异常 JSON、重新批改参数、排队到成功、重复启动抑制、失败/取消、空报告；没有调用真实 AI 或产生计费请求。

**尚未执行**：完整后端启动、微信开发者工具交互/真机、登录态记录上报、真实 render-book 导出和真实 AI 批改。由用户安排验收，不为勾选清单连接未知配置的服务。

## 7. 交接清单

### A. 对齐并发改动

- [x] 在两个仓库分别查看状态和相关 diff，保留并发任务改动，不恢复 SDK。
- [x] 复查共享 session、输入面板、记录辅助函数，新增本地测试；键盘焦点等平台行为仍待真机验收。
- [x] 核对未跟踪的新文件；后续提交时两个仓库分别整理。
- [ ] 提交前由用户/同事最终确认共享文件及并发任务的归属。

### B. 完成代码收尾

- [x] Ruff 与生产代码格式检查通过。
- [x] 历史页导入排序和相关 ESLint 通过。
- [x] 复查 4 个页面的 `generation` 及记录保存代码，全量类型检查通过。
- [x] 静态复查首次进入、重开、再练一次、导出均从后端取题，无本地生成兜底。
- [x] 验证单次拆包及题量校验。
- [x] 对齐前后端公开路径，并用真实鉴权中间件测试无凭证和残留无效凭证取题。

### C. 接口和交互联调

- [ ] 确认配置指向开发环境后，本地完整启动后端并联调目录/四个 POST；隔离 ASGI 测试不代替该项。
- [ ] 基础：预设加减、除法容差、自定义范围/固定数/幂运算、16 位答案输入、后端阈值展示。
- [ ] 填空：正负增长量、分式、双分式、比较题、三种难度和方法偏向。
- [ ] 实战：文字/公式两种呈现、随机模式的实际 `typeKey`、答案单位、负数和零选项。
- [ ] 进阶：6 类方法 × 2 种模式，双输入假设分配题、差分选择题、混合切题时组件切换。
- [ ] 异步：首次加载不计入做题时间；断网失败可重试；连续点击重开不重复发请求。
- [ ] 生命周期：取题中返回页面、选项反馈期间重开/返回，都不会被迟到响应或旧定时器推进。
- [ ] 导出：多选题型后从后端取题并合并成题单；取题中离开页面或切换账号不会继续提交旧任务。
- [ ] 结算/历史：答案、解析、种子/版本和阈值可保存；旧记录依然能回看；原练习记录上报正常。
- [ ] 申论：真实账号首次批改/重新批改、排队进度、评分报告和失败重试；确认后端 `agent` 插件已启用。

### D. 验收与后续 Agent 接入

- [x] 后端测试和本次文件静态检查通过。
- [x] 修复申论 9 处错误，全量 type-check 和小程序构建通过。
- [x] 将验证结果、隔离边界和接口使用说明补回文档及 mini API README。
- [ ] 等用户明确安排后，再进行两个仓库各自的提交/发布与部署。
- [ ] 后续 skill 直接包装本 service 或 HTTP 接口；复用 `/catalog` 和 Pydantic Schema 描述参数，不再另写生成规则。

## 8. 可直接使用的检查命令

### FBA 主仓库

```powershell
uv run --no-sync ruff check backend/app/gongkao/schema/calculation_practice.py backend/app/gongkao/service/calculation backend/app/gongkao/service/calculation_practice_service.py backend/app/gongkao/api/v1/calculation_practice.py backend/app/gongkao/api/router.py backend/app/gongkao/tests/test_calculation_practice.py backend/app/gongkao/tests/test_calculation_practice_auth.py backend/core/conf.py

uv run --no-sync ruff format --check backend/app/gongkao/schema/calculation_practice.py backend/app/gongkao/service/calculation backend/app/gongkao/service/calculation_practice_service.py backend/app/gongkao/api/v1/calculation_practice.py backend/app/gongkao/api/router.py backend/app/gongkao/tests/test_calculation_practice.py backend/app/gongkao/tests/test_calculation_practice_auth.py

uv run --no-sync pytest --noconftest backend/app/gongkao/tests/test_calculation_practice.py backend/app/gongkao/tests/test_calculation_practice_auth.py -q -o addopts= --disable-warnings --tb=short
```

### mini 仓库

```powershell
pnpm exec eslint src/api/calculationPractice.ts src/utils/calculationCatalog.ts src/utils/practiceShared.ts src/utils/auth-request.ts src/composables/useGeneratedPractice.ts src/composables/usePracticeSession.ts src/components/common/PracticeLoadState.vue src/components/common/PracticeAnswerPanel.vue src/pkg/ability/utils/basicCalculation.ts src/pkg/ability/utils/calcConfig.ts src/pkg/ability/utils/dataAnalysis.ts src/pkg/ability/utils/dataPractice.ts src/pkg/ability/basic-calculation/index.vue src/pkg/ability/basic-calculation/session/index.vue src/pkg/ability/basic-calculation/result/index.vue src/pkg/ability/data-analysis/fill-blank/session/index.vue src/pkg/ability/data-analysis/practice/session/index.vue src/pkg/ability/adv-calc/session.vue src/pkg/charts/ability-history/index.vue

pnpm exec eslint src/api/shenlunGrading.ts src/api/types/shenlun.ts src/api/types/contracts.ts src/utils/aiEvaluation.ts src/utils/shenlunEvaluation.ts src/pkg/practice/session/composables/useSubjectiveEvaluation.ts

node --test tests/http.test.cjs tests/calculation-practice.test.cjs tests/shenlun-evaluation.test.cjs

pnpm run type-check

$env:SKIP_OPEN_DEVTOOLS='true'; pnpm run build:mp
```

## 9. 后续 Agent / skill 调用示例

Python 内部调用：

```python
from backend.app.gongkao.schema.calculation_practice import GenerateAdvancedCalculationParam
from backend.app.gongkao.service.calculation_practice_service import calculation_practice_service

params = GenerateAdvancedCalculationParam(
    method='mixed_speed',
    mode='question',
    count=10,
    seed=20261003,
)
batch = calculation_practice_service.generate_advanced(obj=params)
payload = batch.model_dump(mode='json', by_alias=True)
```

HTTP 调用：

```http
POST /api/v1/gk/calculation-practice/advanced/generate
Content-Type: application/json

{
  "method": "mixed_speed",
  "mode": "question",
  "count": 10,
  "seed": 20261003
}
```

建议的验收起点：**先阅读第 6 节的验证边界，再按第 7 节 C 部分进行用户真机/开发环境联调；提交、发布和部署仍需另行授权。**
