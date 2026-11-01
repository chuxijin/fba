# 云易学试卷采集与导入：AI 独立交接规范

更新：2026-11-01。本文件是本工作唯一现行规范，不依赖旧会话。先读仓库及 `skills/fba_work/AGENTS.md`。

## 1. 工作目标与边界

从用户有权使用的云易学单套试卷接口响应或本地 JSON，导入指定环境 V2 题库，并按要求挂载合集。
这不是手写精简解析任务；后者走 `../question-explanation/WORKFLOW.md`，不得在本工作中擅改已有解析默认、答案或题干。

开始先确定：来源试卷/sectionId、实际题数、试卷名称、目标环境、bank code、practice/paper 类型、章节与合集要求、源数据及写入授权。不明确就问，不自动沿用历史参数。

## 2. 目录与一轮任务

- `scripts/import_yunyxzx_paper.py`：主导入器，支持远端接口或本地 JSON。
- `archive/legacy-before-20261101/`：原 README、精确/模糊题干批量修复脚本；默认不读、不执行。
- `runs/YYYYMMDD-任务名/`：本轮独立文件夹，不覆盖上一轮。

每轮保留 `README.md`（真实状态/范围/下一步）、`source/response.json`（必要且脱敏的源响应）、`preflight.json`、`import-result.json`（精确ID）、`verify.json`（独立复核与备份信息）。分片、预览和调试日志只放 `work/`。
本地 JSON 分支不请求源站，但导入器随后仍会连接数据库；**本地 JSON + dry-run 也不是完全离线**。
2026-11-01归档时未发现本轮响应或导入记录；本次没有执行抓取、预检或导入，不能据此宣称历史任务已完成。

## 3. 输入和参数（以当前脚本为准）

- `--paper-id` 始终必填，包括 `--input-json` 分支；其值用作远端 `sectionId` 及默认 bank code，不能用任意占位值代替真实标识。
- `--paper-name` 建议显式指定，否则为“云易学试卷 <ID>”。
- `--type` 是接口 type，默认2；**没有 `--mode`**。
- `--bank-code` 建议显式唯一；默认 `YUNYXZX_<paper-id>`，会截断到64字符，须检查截断冲突。
- `--bank-kind` 默认 practice，不因文件叫试卷就自动变 paper；按用户意图显式确认。
- `--collection-code/--collection-name/--parent-collection-code` 控制挂载；缺失合集会新建，已有合集不保证自动调整层级。
- `--chapter-name` 为统一章节；`--no-chapter` 不建章节（同时传时不建章节优先），否则按远端 subType 分组，而非推断后题型。
- `--input-json` 读取本地文件，支持响应对象（code=0，data为分组列表）或分组列表；不是任意平铺题目数组。
- `--cookie/--authorization` 为当前授权信息，默认空；不要把真实值写进命令记录、文档、Git 或日志。
- `--env` 默认 dev；`--timeout` 默认30秒，只控制 HTTP 请求，不是数据库超时。

远端接口实际为 `https://www.yunyxzx.com/huikao_pc/querySubjectList`，GET 参数 `sectionId/type`，不是旧文所说的 queryoPaperSubjectList/mode。接口以本轮授权和实际响应为准，不尝试绕过认证。
为了可追溯，优先使用已保存的本地响应。若走接口直连，主脚本不会自动保存原始响应，须先建立受控源快照；不要将 Cookie/Authorization 存入快照。

### 内容预检

脚本从分组中提取 id、issue/stem、sOption、answer、analysis、subType，并递归展开 childre/children。必须检查：

- 分组、父子题是否重复/遗漏，源 ID 唯一、题序正确，实际题数不是零。
- 题干/图片/公式完整，`sOption` 用 `|` 分隔的拆分正确，答案对应真实选项。
- subType 1—6 对应单选、多选、判断、填空、简答、材料（材料暂按简答）。推断多选不能只看源标签。
- 判断题答案转换是旧启发式逻辑，不能假定所有 A/B 或文字均正确映射；逐种核对后再导入。
- 多选为 `answer_data.correct` 数组，单选为字符串，判断为布尔值。空解析会写“暂无解析”，须记录并获接受。
- 材料/子题并未实现通用材料表建模；有复杂材料结构时先评估，不把“递归展开”当完整支持。

## 4. 预检和正式导入的安全门

Python 优先 `uv run python`，从仓库根目录执行，PowerShell 设置 `$env:PYTHONIOENCODING='utf-8'`。
下面仅示范本地响应的**数据库只读预检**，路径/标识须替换成本轮已核实值：

```powershell
$run = 'skills/fba_work/yunyxzx/runs/20261101-example'
uv run python skills/fba_work/yunyxzx/scripts/import_yunyxzx_paper.py --paper-id '已确认sectionId' --input-json "$run/source/response.json" --paper-name '本轮确认名称' --bank-code '本轮唯一code' --bank-kind paper --env dev --dry-run
```

只有本轮数据库查询已获授权才执行。需要合集时追加已确认参数。

查询 dev 使用 `fba_dev`，prod 使用 `fba_prob`；生产服务器登录使用 SSH MCP。导入器 dev 使用后端 settings，prod 读取 `backend/.env.prod` 且数据库名固定 fba。
只读核实实际 host/database/schema/search_path/权限与操作者；SQL 未带 schema 前缀，不能假定命中正确 schema；不能只相信 `--env dev` 的标签。

`--dry-run` 只统计题型/行数、全库 item_key 冲突数及合集信息；不是模拟所有 INSERT 的事务预演，不能证明实际写库安全。另查 bank code 唯一性、源ID重复、题目引用、合集层级和实际表结构。

以下是旧导入器现存限制，不是归档后已经修复：

1. 每次都新建 bank + revision，不是更新或断点续传；重复执行可能报错或新建残缺题库。
2. item_key 使用远端题目 id，在全库查重，命中直接跳过，不会自动关联到新试卷；跨卷共享题应先规划。
3. 多处 commit，章节/题目/合集可先提交；中断会留下半成品，延长超时或分批重跑不等于解决问题。
4. 开始时 fix_sequences 会调整多个全局序列，有并发竞态及权限风险；序列变更不可当作普通事务回滚。有并发写入时停下由主控处理。
5. 新建题目解析写 `default/published/is_default=true`，创建者硬编码为1；复用旧题不会更新其解析。不要用于批量修复旧解析。
6. 所有题默认1分，不能假定保留了原试卷分值。推断多选仍可能落入远端“单选题”章节，需确认接受或另定映射。

备份相关范围，报告预检、限制和目标影响，获明确授权后才能正式执行。正式命令为已审核预检命令去掉 `--dry-run`，这不是自动授权。生产先在合适的隔离环境验证。
本次归档只适配文件路径，不重构导入事务或去重策略，也没有连接生产验证。

## 5. 完成标准与中断恢复

保存实际 bank_id/revision_id/collection_id/imported/skipped 后，独立查询：

- 实际条目数及独立题目数与源范围、跳过明细一致；章节分布、总分、question_count、current_revision_id一致。
- 题干/选项/答案及默认解析完整，每题默认唯一；抽查复杂题型，重要异常逐题核对。
- 合集层级和挂载正确，无越界修改。仅看到脚本“success”不能标完成。

中断先记“部分提交，待核对”，只读定位精确 bank/revision/题目ID及共享引用，保存当前快照，不直接重跑。
修复、补齐、回滚另行授权；先备份，依外键顺序在事务中精确处理，先预演回滚、再提交、再独立核验。序列恢复单独评估，不擅自回拨。

**撤销旧 README 的按 code 前缀删题和“不要放同一事务”的指导**。禁止粗放删除共享题目、答案、解析或学习记录。

## 6. 历史修复脚本不得直接重放

- `fix_analysis_by_stem.py`：按题干匹配，但更新范围覆盖同题全部解析及答案，没有版本/软删精确限定。
- `fix_analysis_fuzzy.py`：阈值0.8择优匹配，还会覆盖题干、全部解析与答案，存在误匹配风险。
- 两者硬编码旧仓库路径、默认生产，没有可靠备份与完整边界保护。仅归档源码供查证，不适配为通用脚本、不尝试执行来“验证”。

若确实要修复，另建 run，以精确 question_id、题库范围、解析版本、旧内容断言为边界，明确是否允许改答案，逐题核对；不能将模糊相似度作为自动写库依据。

## 7. 保留与清理、新会话提示词

长期保留受控源响应、最终输入、任务状态、独立核验、精确ID与备份信息；认证数据不写入目录。完成且可追溯后仅清理 work 中可重建分片、预览与日志；不自动清理生产备份或原始成品。

> 请先完整阅读 `skills/fba_work/yunyxzx/WORKFLOW.md`，按我提供的本轮试卷标识和本地响应规划导入。所有文件放本功能 runs 下，先核对题型、答案、去重和目标环境。未授权不联网或写库，报告预检与现有导入器限制后再确认正式操作。不执行 archive 中的修复脚本，不照搬旧删除说明，完成后独立核验并记录状态。
