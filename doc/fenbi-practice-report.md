# 粉笔练习报告导入与对比

## 使用

- 插件结算页 `/ti/exam/solution/<exerciseKey>` 显示“导入练习记录”，与是否存在错题无关。
- 点击后只读取页面已经加载、插件已经拦截的报告、作答、解析和模块统计。重播内存缓存不会发起粉笔 HTTP 请求，也不主动翻页查询历史。
- 日期和得分取自已捕获的本卷报告元数据或练习历史；没有日期时手动填写。缺少本卷解析或逐题明细不完整时明确提示缺失数据，不自动请求补齐。
- 预览确认后保存到小程序“练习数据 → 导入/手动记录”。重复导入返回现有记录，不覆盖用户修改。
- 展开科目、模块，查看直属子模块；点击“对比”进入同路径的跨次比较。
- 对比支持整卷／模块／子模块、近 30／90 天／全部、来源和练习多选。正确率与每题用时、总用时或题量共同展示；同一天多次练习分别保留。
- “筛选”打开底部面板，层级、日期、来源和对比对象先编辑草稿，点击“应用”后生效；取消不改变图表。日期筛选后所选模块无数据时显示空状态，不自动切到另一个模块。

## 数据口径

- `getSolution` 提供题目作答状态与秒级用时；结算页面的 `report-keypoints-tree-container-0/1` 提供模块与直属子模块统计。
- 已拦截的 `getReport` 元数据提供 `submitTime`、得分和满分；已拦截的 `getExerciseBriefHistory` 按 `exerciseKey` 精确匹配，补充 `updatedTime`、得分与满分。历史题数和正确数可能是 0，不用于成绩统计。
- 历史 `updatedTime` 作为有来源标记的候选日期，按北京时间归日，可手动校正；不是未经核实的精确交卷时间。
- 各层保留原始统计。政治理论 20 题下的 2／18／18 题子模块允许重叠，不能向上相加。
- 得分和正确率独立。样本得分 72.7，正确率为 95/130 = 73.08%。
- 跨次正确率使用正确数合计 / 题数合计；每题用时只统计有用时数据的练习，不将缺失用时视为 0。
- 比较键为完整科目／模块路径，不合并不同父模块下的同名子模块，也不强行映射缺少对应关系的在线知识点。现有在线刷题记录保持原入口。

## 后端

- 扩展 `gongkao_practice_log`：科目、来源、报告编号、原链接、来源时间、日期来源、未答数、得分和满分。
- `gongkao_practice_module.parent_id` 关联直属子模块，API 最多接收这两层模块，即加上科目共三级。
- 唯一约束 `(user_id, source_platform, source_key)` 防止并发重复导入。
- `POST /api/v1/gk/practice-logs/import-report` 返回 `{created, record}`。
- `GET /api/v1/gk/practice-logs/comparisons` 支持开始／结束日期与来源，返回按完整路径分组的逐次统计；最多最近 500 次并明确返回 `limited`。
- 列表接口批量装配模块，避免列表丢失明细；编辑保留子模块与未知值。

## 逐题明细导入（完整报告）

### 请求

`POST /api/v1/gk/practice-logs/import-report` 的原有字段不变，新增可选 `questions`，一次最多 500 题：

| 字段 | 说明 |
| --- | --- |
| `source_question_key` | 平台内稳定题目标识，最长 160；同一报告内唯一 |
| `position` | 原卷题号，从 1 开始，不超过报告总题数；不能按答案字典顺序推断 |
| `module_path` | `["模块", "子模块", "具体题型"]`，1～3 段且不含科目，必须存在于本次报告的模块统计树 |
| `stem` / `content_format` | 题干与格式，题干支持富文本 |
| `question_type` / `options` | 题干类型与选项，选择题至少两个选项，选项编码不可重复 |
| `answer` | 标准答案；来源未给出时为空，后续导入可补全 |
| `explanations` | 解析列表，有解析时必须且只能有一个 `is_default` |
| `materials` / `assets` | 材料与资源引用，`link_key` 不可重复；同一 `link_key` 在不同题中内容必须一致 |
| `status` | `correct` / `wrong` / `unanswered` |
| `response_data` | 当次实际答案；`unanswered` 不得携带，已答题必须提供 |
| `duration_seconds` | 原平台逐题用时；未知传空，`0` 表示零秒而非未知 |
| `score` / `max_score` | 单题得分与满分，得分不得超过满分 |

返回新增 `practice`：`{session_key, imported_questions, detail_status, added_questions, supplemented_questions}`，`detail_status` 为 `partial` 或 `complete`。

### 查询

`GET /api/v1/gk/practice-logs/{pk}/questions` 返回 `GetImportedPracticeDetail`：

- `detail_status`：`none`（仅有汇总）/ `partial` / `complete`，`complete` 表示题量齐全且每题都有答案与解析。
- `items[]` 复用导入参数结构，并附带 `session_item_id`、`question_id`、`attempt_id` 与 `missing_content`（尚缺的答案/解析）。
- `source_summary` 为平台原始汇总，独立于用户对记录的编辑。

### 语义

- 逐题明细落在题库 v2 的会话／条目／作答表，`session_key` 固定为 `external-<log_id>`，全部记录标记来源 `external_practice`。
- 重复导入按 `source_question_key` 与题号对齐：一致则幂等，缺答案／解析则补全；已存在且不同的不可变内容（题干、选项、题型、答案、用时、得分）返回冲突并回滚整次导入。
- 逐题数量、正确数、未答数、用时与报告汇总及一级模块比对；只校验互斥的一级模块，不累加可能重叠的细分知识点。
- 历史会话在题库读接口可见（详情、报告、解析），但**只读**：提交、隐藏等写操作返回冲突；删除练习记录时同步软删会话、条目与作答。
- 编辑记录日期会同步会话锚点，保证列表与统计日期一致。
- 导入会话不计入在线练习列表、今日汇总、难度重算、统计、学情分析与数据重置；也不写入错题本、复盘与学习计划能力画像。

## 迁移与联调

- Alembic：`e1f2a3b4c5d6`，前置本地版本 `d9e0f1a2b3c4`。
- PostgreSQL 等价增量脚本：`backend/scripts/migrate_practice_report.sql`。
- 2026-10-23 已通过 `fba_dev` MCP 事务执行增量脚本。原有 11 条记录、66 条模块保持不变。
- 开发库原版本为 `e4f5a6b7c8d9`，与本地迁移链不同，因此未修改版本表。以后按 Alembic 管理前应先对齐原有版本链；本次 upgrade 允许已有字段／约束跳过。
- 生产库未变更、代码未发布。发布时需先应用相同增量结构，再更新后端与小程序。
- 插件当前 `extension/dist` 为本地联调构建，后端 `http://127.0.0.1:8000`。在扩展管理页重新加载该目录的插件后，刷新粉笔结算页面试用。

## 验证与预览

- 后端 SQLite 实际 ORM 测试覆盖三级持久化、重叠统计、去重保留编辑、用户隔离、同日多次及日期筛选。
- 逐题明细回归（`backend/app/gongkao/tests/test_imported_practice.py`）覆盖：完整导入与统计校验、幂等补全、冲突回滚、私有隔离与在线统计排除、只读保护、日期同步、删除与重导、非法结构拒绝。连同报告与路由回归共 37 条通过。
- 插件测试覆盖结算路由、130/95/6963 样本、日期时区、缓存读取、缺失日期、跨报告隔离、JSON 格式 XHR 拦截及导入准备阶段零主动网络请求。
- 小程序测试覆盖加权指标、缺失用时、编辑保留层级、同日多次、子模块直达和真实微信模板编译。
- 只读预览使用真实 H5 页面，API 被隔离为样本和明确标记的示例对比数据，不写入用户账号。
- 启动 H5 开发服务器：在 `mini` 中运行 `pnpm exec uni -p h5 --host 127.0.0.1 --port 5193`。
- 启动只读预览：`node scripts/preview-practice-report.cjs`，地址 `http://127.0.0.1:5192/#/pkg/charts/practice-log/index`。
- 已检查 390px 手机浅色纸质、768px 平板深色玻璃；无横向溢出，勾选练习会刷新加权统计。
- 截图：`mini/tests/artifacts/practice-comparison-preview.jpg`。
- 全量类型检查仍有既有 `PageSkeleton.vue` 与 Wot `useUpload.ts` 两处错误；本次修改文件未报告类型错误。

## 本地路由排查补充

- `/{pk:int}` 将详情、修改、删除接口限定为整数 ID，静态路径不会再被解析为 `pk`。
- 本次 `/comparisons` 返回 `pk` 校验错误，实际原因是旧 Granian 工作进程仍在响应。仅结束旧主进程不会保证 Windows 上的子进程一并退出；已清理核实过的旧工作进程并重新确认运行服务的 `/openapi` 包含两个新接口。
- 图表采用 ECharts CanvasRenderer，经 lime-echart 适配 uni-app，再由 `AppEChart` 封装初始化和更新。
