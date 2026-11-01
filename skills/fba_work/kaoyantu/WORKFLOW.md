# 考研兔题库采集与导入：AI 独立交接规范

更新：2026-11-01。本文件是本工作唯一现行规范；不需要旧会话。开始前阅读仓库及 `skills/fba_work/AGENTS.md`。

## 1. 工作边界

将用户有权使用的考研兔题目，从本地 Burp 抓包提取为 V2 Excel，核对后导入指定环境题库，并按要求挂载合集。
这是**原始题库采集/导入**，不是逐题撰写精简解析。后者使用 `../question-explanation/WORKFLOW.md`，不得在导入时擅自添加“简短版”或切换已有解析默认。

若用户未提供本次来源、题库名、目标环境或合集要求，先询问；不把历史题库、旧签名、ID 当作本轮参数。归档任务本身不授权抓取或写库。

## 2. 目录与记录

- `scripts/extract_kaoyantu_from_burp.py`：离线解析 XML/文本，一个或多个输入，输出 V2 Excel。
- `scripts/import_to_v2.py`：Excel 导入器，可读库预检，也能实际写库。它是旧实现，使用前必须完成下面的安全检查。
- `runs/YYYYMMDD-任务名/`：本轮任务。只处理当前 run，不默认加载 archive。
- `archive/legacy-before-20261101/`：原 README 和绑定旧请求参数的 HTTP 导出器，仅供历史查证，不直接执行。

每轮建议保留：

```text
README.md          # 来源、授权、环境、题库/合集code、状态、下一步
source/            # 必要的源响应/抓包（本地保护，先移除无关认证信息）
questions.xlsx     # 核对后用于导入的最终Excel
preflight.json     # 离线内容检查及只读数据库检查
import-result.json # 实际执行结果及精确bank_id/revision_id
verify.json        # 独立复核、备份位置、异常项
work/              # 可重建的分片、预览、调试日志
```

没有执行就标“待定位/待导入”，中断标“部分提交，待核对”。日志中的成功不替代实时核验。
2026-11-01只整理文档和脚本，没有恢复历史抓包/Excel，也没有执行新导入。

## 3. 提取与内容核验

从仓库根目录运行，Python 优先 `uv run python`，PowerShell 设置 `$env:PYTHONIOENCODING='utf-8'`。以下变量是本轮真实路径，不是默认任务：

```powershell
$run = 'skills/fba_work/kaoyantu/runs/20261101-example'
uv run python skills/fba_work/kaoyantu/scripts/extract_kaoyantu_from_burp.py --input "$run/source/burp.xml" --output "$run/questions.xlsx"
```

- 输入可为 XML 或普通文本，可在 `--input` 后传多个文件；始终显式指定 `--output`，不要覆盖旧成品。
- `--only-with-analysis` 只适合明确要求的补充包，会过滤无真实解析题，不是全量导出默认策略。
- 对照输出中的题数、解析覆盖率、缺解析 ID，记录未提取/过滤数量；不能把接口页数或显示“1000题”当实际题量。
- 核对多文件合并和题目去重，题干/选项完整、答案在选项内、多选/简答识别、章节路径、图片与公式有效性。不能将 HTML 剥离后猜图片内容。
- 缺解析与“暂无解析”要明确计数；如确实接受缺失，记录用户决定，不能假称全部有解析。

### Excel 契约

第一张表是题目表（建议命名 `题目`），导入器按 `sheet_name=0` 读取；可选材料表名为 `材料`。

| 字段 | 说明 |
|---|---|
| `question_type` | single_choice / multiple_choice / true_false / fill_blank / short_answer |
| `stem`, `answer` | 题干与答案；单选 A、多选 AB、判断对/错，主观题文本 |
| `explanation_*` | 解析版本，如 explanation_default；列顺序中首个非空版本会设为默认 |
| `option_A` … `option_J` | 导入器支持到 J；提取器具体输出列以实际文件为准 |
| `score` | 分值，必须核对；导入器缺值回退1，不会按多选自动补2 |
| `section_l1/l2/l3` | 章节路径；同名不同父级章节必须额外检查 |
| `item_key` | 去重标识，不得丢失或随意重编 |
| `material_code` | 多个材料用逗号分隔，须与材料表对应 |

材料表：`material_code/material_title/material_content`。导入器会吞掉材料表读取异常并当作无材料，必须在导入前主动核验，不能只看退出码。

## 4. 数据库预检与实际行为

查询开发库用 `fba_dev`，生产库用 `fba_prob`；生产服务器登录用 SSH MCP。凭据来自当前配置，不抄进文档或日志。
导入器定位仓库中的 `backend`；dev 使用后端 settings，prod 读取 `backend/.env.prod`，旧实现生产数据库名固定为 `fba`。
务必只读核实真实服务器、数据库、schema/search_path、表结构、权限和操作者。SQL 没有 schema 前缀，不能假定一定命中生产 `fba` schema；dev 设置也必须核实实际指向，不能只信 `--env`。

参数：`--file/--bank-name` 必填；`--bank-code` 应显式唯一；`--bank-kind` 默认 practice，可选 paper；合集用 `--collection-code/--collection-name/--parent-collection-code`；`--env` 默认 dev。

```powershell
uv run python skills/fba_work/kaoyantu/scripts/import_to_v2.py --file "$run/questions.xlsx" --bank-name '本轮确认名称' --bank-code '本轮唯一code' --env dev --dry-run
```

上例会连接数据库，**不是离线检查命令**。只有本轮数据库查询已获授权才运行。合集有要求时追加已确认的合集参数。

`--dry-run` 仅统计题型/行数、已有 item_key 数量和合集信息；它**不是完整事务预演**，不会验证全部 INSERT、外键、bank code 冲突或最终结果。还需独立查题库 code、材料 code、源 ID 重复和预期挂载。

现有导入器的重要限制（不能因预检通过忽略）：

1. 每次都新建 bank + revision，不是更新模式；重复执行可能冲突或留下新空壳。
2. `item_key` 在全库范围查重，命中直接跳过，不会把旧题自动挂到新库；相同来源在多个卷中使用时先评估。
3. 多处 `commit()`，章节/题目/材料/合集可先于整轮完成提交；中断会留下半成品。
4. `fix_sequences()` 会调整多个全局序列，不仅本轮数据，且 PostgreSQL 序列变更不可当作普通事务回滚；有并发写入或权限不明时停止，由主控制定方案。
5. 创建者硬编码为1，解析按首个非空列设默认，缺失则“暂无解析”。须核实当前业务允许这些语义。
6. 章节 code 只包含层级和名称，同名不同父级可能误合并；遇到这种数据不能盲导。

本轮导入前备份目标关联数据，审核上述影响，确认明确写库授权后才能执行。正式命令是已审核预检命令去掉 `--dry-run`；这里只提供预检示例，不能把该转换视作自动授权。生产先在合适的隔离环境验证。
本次归档仅修正文件路径定位及输出归属，没有重构这些事务/去重限制，不宣称已生产验证。

## 5. 提交后独立核验

保存输出的 bank_id、revision_id、collection_id、imported/skipped，独立查询并记录：

- 当前 revision 指向正确，名称/类型/状态符合要求。
- 独立题目数、条目数、题型数与源数据及 skip 原因相符；question_count、总分与实际条目一致。
- 答案、选项、解析覆盖、每题默认唯一、材料关联与章节树正确。
- 合集层级与挂载正确，未意外创建其他合集；既有题目、解析及学习记录无越界改动。
- 不能只看脚本输出 imported 数就标记“完成”。

## 6. 中断、恢复与清理

中断立刻停止，不直接重跑，也不“分批重跑”同一 bank code。先从实时数据库定位精确 bank/revision/新增题目 ID，核对是否有其他题库、练习记录或用户数据引用；保留当前快照和执行日志。
修复/补齐/回滚必须另定精确方案，先备份、获授权、事务内按依赖处理，先预演回滚、再提交并独立复核。序列恢复需单独评估，不擅自回拨。

**旧 README 的按 code 前缀删题、不要放同一事务的指导已撤销**。禁止按前缀批量删除共享题目，禁止为了恢复直接删除答案/解析或学习记录。事务回滚是保护，不是应当规避的错误。

长期保留：最终源数据（受控且必要）、Excel、任务状态、核验、精确 ID、备份信息。原始抓包可能含令牌，先脱敏并限制访问，不加入 Git 或分享；旧 HTTP 导出器同样可能含旧认证参数，不对外发布。
仅在确认完整可追溯后清理 `work/` 的重复分片、日志和预览，不自动删除源文件、最终成品或生产备份。

## 7. 新会话提示词

> 请先完整阅读 `skills/fba_work/kaoyantu/WORKFLOW.md`，根据我提供的本轮考研兔抓包整理 V2 Excel。所有文件放本功能 runs 下。先核对数据和目标环境；未授权不要连接数据库或正式导入。需要导入时先报告预检、旧导入器限制和精确范围，获确认后执行并独立核验，不运行历史 HTTP 导出器或旧删除示例。
