# 题库错题解析手写与生产同步工作流（2026-10-26）

> 给下一个模型/接手人的完整操作说明。按本文执行即可复现本次工作，不需要重新摸索。
> 核心原则：**解析内容必须逐题手写，禁止用脚本生成**；脚本只负责导出题目、校验结构、写库和同步。

---

## 1. 本次成果

| 项目 | 结果 |
|---|---|
| 开发库用户 | `chuxijin` / `chuxijin`，`user_id=20`，昵称“桥水彼岸” |
| 生产库用户 | `test123`，`user_id=18`，昵称“桥水彼岸” |
| 范围 | 错题中的“政治理论”316 题 + “常识判断”204 题 = **520 题** |
| 分批 | 26 批 × 20 题 |
| 开发库写入 | 520 条 `default` 解析 + 520 条 `official` 降级保留 |
| 生产库同步 | 520 条 `default` 解析 + 520 条 `official` 降级保留 |
| 备份 | dev/prod 各有 `qbank_v2_question_explanation_bak_20261026`，520 行原始 official |
| 校验 | 26 批全部 `total_issues=0`；生产 `bad_questions=0` |

---

## 2. 环境与连接

### 2.1 本地仓库

```text
D:\100_Work\101_Program\Proj\fba
```

PowerShell 命令前先设置编码：

```powershell
$env:PYTHONIOENCODING='utf-8'
```

Python 用 `uv run python ...`。

### 2.2 开发库（dev）

- 通过 MCP `fba_dev` 查询/写入。
- 连接信息来自 `backend/.env`。
- 本次实际：database `fba`，schema `public`，端口 5432。
- 不要把密码写进任何文档或提交。

### 2.3 生产库（prod）

- 通过 MCP `fba_prob` 只读查询。
- MCP 实际连接：database `fba`，schema `fba`，端口 8100，用户 `yas`。
- 生产数据库主机是云服务器 `212.64.23.13`（SSH 配置名 `ssh-could`，用户 `ubuntu`）。
- 直接写库走服务器本机 psql：

```bash
sudo -u postgres /www/server/pgsql/bin/psql -p 8100 -d fba
```

- 注意：生产备份表由 `postgres` 创建，MCP 用户 `yas` **没有权限读备份表**；验证备份要用上面的 psql。
- 如确实需要给应用用户读权限：

```sql
GRANT SELECT ON fba.qbank_v2_question_explanation_bak_20261026 TO yas;
```

---

## 3. 目录与关键文件

```text
scratch/
  prepare_batches.py                 # 从 dev 库导出用户错题，切成 batch_XX.json
  batches/batch_01.json ... 26.json  # 输入：题目、选项、答案、官方解析
  final/batch_01.json ... 26.json    # 输出：手写精简解析
  validate_final.py                  # 校验结构/标签/答案/标色
  write_batch.py                     # 写入 dev 库，并把 official 降级
  build_prod_sync.py                 # 生成生产同步 SQL（base64 + COPY）
  prod_sync_map.json                 # dev_id -> prod_id 映射（520 条）
  prod_sync.sql                      # 生产同步 SQL（本地生成，约 786 KB）
  ../doc/question-explanation-sync-workflow.md  # 本文（完整流程）
```

输入 JSON 每题字段（至少）：

```json
{
  "question_id": 58655,
  "section": "政治理论",
  "stem": "...",
  "question_type": "...",
  "options": ["A", "B", "C", "D"],
  "answer": "B",
  "official": "<p>官方解析...</p>"
}
```

输出 JSON 每题字段：

```json
{
  "question_id": 58655,
  "section": "政治理论",
  "question_type": "选是题",
  "answer": "B",
  "content_html": "<p>...</p>"
}
```

---

## 4. 数据模型

### 4.1 错题范围

关键表：

- `qbank_v2_wrong_question_state`：用户错题状态，`user_id`、`question_id`、`entry_metadata`、`deleted`。
- `qbank_v2_bank_item`：`id`、`section_id`。
- `qbank_v2_bank_section`：`id`、`name`。
- `qbank_v2_question`：`id`、`stem`、`content_hash`、`option_data`。
- `qbank_v2_question_explanation`：解析主表。

范围 SQL（本次用的就是它）：

```sql
WITH scope AS (
  SELECT DISTINCT wq.question_id
  FROM qbank_v2_wrong_question_state wq
  LEFT JOIN qbank_v2_bank_item bi ON bi.id = wq.source_bank_item_id
  LEFT JOIN qbank_v2_bank_section s ON s.id = bi.section_id
  WHERE wq.user_id = 20 AND wq.deleted = 0
    AND COALESCE(wq.entry_metadata->>'section_name', s.name)
        IN ('政治理论', '常识判断')
)
SELECT * FROM scope;
```

生产把 `user_id=20` 换成 `18`，表名加 `fba.` 前缀。

### 4.2 解析表

`qbank_v2_question_explanation` 关键字段：

- `question_id`
- `content`
- `explanation_type`：`default` / `official`
- `is_default`
- `status`：`published`
- `deleted`：0
- 唯一约束：`(question_id, explanation_type, deleted)`

本次写入策略：

1. 插入/更新 `explanation_type='default'`，`is_default=TRUE`，`status='published'`。
2. 把该题原有 `official` 行改为 `is_default=FALSE`，内容保留，作为降级版本。
3. 不删除 official。

每题最终应满足：

- 恰好 1 条未删除 `default`
- 恰好 1 条未删除 `official`
- `default.is_default=1`
- `official.is_default=0`

---

## 5. 全流程

### 步骤 0：确认范围

先跑 4.1 的 SQL，确认用户、题量、章节。本次是 520 题。

### 步骤 1：导出并分批

```powershell
$env:PYTHONIOENCODING='utf-8'
uv run python scratch/prepare_batches.py
```

它会生成 `scratch/batches/batch_01.json` 到 `batch_26.json`，每批 20 题。

> 如果换用户/换范围，先改 `prepare_batches.py` 里的 `user_id` 和章节条件。
> 本次脚本里的用户是 20，章节是 `政治理论`、`常识判断`。

### 步骤 2：逐题手写解析

对每一批：

1. 读 `scratch/batches/batch_XX.json`。
2. 读每题 `official` 原文。
3. 手写 `scratch/final/batch_XX.json`。
4. **禁止**用循环/模板/脚本批量生成 `content_html`。
5. 20 题必须全部包含，顺序与输入一致，不能跳题、不能占位。

可以并行：本次 batch_12–26 由多个子代理分批处理（大部分各 2 批，batch_26 单独 1 批），主代理做最终全量校验。
并行时每个代理只碰自己的 `final/batch_XX.json`，不要交叉写。

### 步骤 3：校验

```powershell
$env:PYTHONIOENCODING='utf-8'
uv run python scratch/validate_final.py 12
```

全部批次：

```powershell
uv run python scratch/validate_final.py 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26
```

必须看到：

```text
total_issues=0
```

有 issue 就修 `final/batch_XX.json`，不要改 `batches/` 输入。

### 步骤 4：写入 dev 库

单批：

```powershell
uv run python scratch/write_batch.py 12 --apply
```

输出应为：

```text
batch_12: 已写入 20 题（backup=qbank_v2_question_explanation_bak_20261026）
```

`write_batch.py` 的行为：

1. 读取 `final/batch_XX.json`。
2. 建备份表（如果不存在）。
3. 把该批题目当前所有解析行备份进备份表（按 `id` 去重）。
4. upsert `default` 解析。
5. 把 `official` 设为非默认。
6. 全程事务；`--apply` 才提交，不加是 dry-run 回滚。

### 步骤 5：验证 dev 库

```sql
SELECT count(*) FILTER (WHERE default_ok)     AS default_ok_count,
       count(*) FILTER (WHERE official_demoted) AS demoted_count,
       count(*) AS total
FROM (
  SELECT question_id,
         bool_or(is_default AND explanation_type='default'
                 AND deleted=0 AND status='published') AS default_ok,
         bool_or(explanation_type='official' AND NOT is_default
                 AND deleted=0) AS official_demoted
  FROM qbank_v2_question_explanation
  WHERE question_id IN (...本批 20 个 id...)
  GROUP BY question_id
) t;
```

再查备份累计行数：

```sql
SELECT count(*) FROM qbank_v2_question_explanation_bak_20261026;
```

本次最终 dev：520 题、520 default、520 official 降级、备份 520 行。

---

## 6. 解析 HTML 规范

### 6.1 允许标签

只允许：`p`、`b`、`span`、`br`。

- **禁止** `<s>`。
- 删除线必须用：

```html
<span style='color:#DA291C;text-decoration:line-through;font-weight:bold'>错误原文</span>
```

### 6.2 固定结构

选是题示例：

```html
<p><b>【题型】</b>选是题（选正确项）</p>
<p><b>【考点精析】</b></p>
<p>A <span style='color:#008A00;font-weight:bold'>✓</span> 正确表述</p>
<p>B <span style='color:#DA291C;font-weight:bold'>✗</span> 表述，其中<span style='color:#DA291C;text-decoration:line-through;font-weight:bold'>错误文字</span><span style='color:#0066CC;font-weight:bold'>正确文字</span></p>
<p>故选 B。</p>
<p><b style='color:#008A00'>【答案】B</b></p>
```

计数题/组合题示例：

```html
<p><b>【题型】</b>组合选择题（选正确项）</p>
<p><b>【考点精析】</b></p>
<p>① <span style='color:#008A00;font-weight:bold'>✓</span> ...</p>
<p>② <span style='color:#DA291C;font-weight:bold'>✗</span> ...<span style='color:#DA291C;text-decoration:line-through;font-weight:bold'>错误</span><span style='color:#0066CC;font-weight:bold'>正确</span></p>
<p>③ <span style='color:#008A00;font-weight:bold'>✓</span> ...</p>
<p>正确的为①③，故选 B。</p>
<p><b style='color:#008A00'>【答案】B</b></p>
```

计数题结论必须带数量：

```html
<p>正确的为①②，共 2 项，故选 C。</p>
```

### 6.3 题型判断

| 题型 | 判断 |
|---|---|
| 选是题 | A-D 是实质表述，只有一个正确 |
| 选非题 | 题干问“错误/不正确/没有体现/不恰当” |
| 计数题 | 选项是“1”“2 项”“3 项”等数量 |
| 组合题 | 选项是“①②③”等组合 |

### 6.4 标色

| 含义 | 样式 |
|---|---|
| 正确项 ✓ | `color:#008A00;font-weight:bold` |
| 错误项 ✗ | `color:#DA291C;font-weight:bold` |
| 错误原文 | `color:#DA291C;text-decoration:line-through;font-weight:bold` |
| 更正文字 | `color:#0066CC;font-weight:bold` |

规则：

- 选是题：只有答案项绿 ✓，其余红 ✗。
- 选非题：除错误项外全部绿 ✓；错误项红 ✗。
- 计数/组合：每个①-⑩判断句单独标 ✓/✗，不要标 A-D 选项。
- 错误项如果无法写成“原文→更正”，可以用 `｜` 后接原因，例如：
  `✗ 某表述｜题干未强调该点`
- “正确的为...”里的序号必须与绿色 ✓ 的序号完全一致，数量 N 必须一致。
- 解析要精简：复用选项/判断句原文，只高亮错误处和更正处，不要长篇展开。

### 6.5 校验器实际检查项

`validate_final.py` 会检查：

1. 数量与原题一致。
2. question_id 集合一致。
3. answer 与输入一致。
4. 只允许 `p/b/span/br`，禁止 `<s>`。
5. 必须包含 `【答案】`。
6. 计数/组合题必须包含“正确的为”，且序号与绿色 ✓ 一致。
7. 选是/选非题绿色集合必须等于预期：
   - 选是：`{answer}`
   - 选非：`set(options) - {answer}`
8. 每个选项行必须恰好一个 ✓ 或 ✗。
9. 错误项必须有 `line-through` 或 `｜`。

---

## 7. 生产同步

### 7.1 关键前提：题目 ID 不同

本次 dev 与 prod 是同一批题，但题目 ID 不同：

- dev：58655–62570
- prod：98276–102051

**不能按 question_id 直接复制。**
必须按 `qbank_v2_question.content_hash` 匹配。

本次验证：

- dev 520 题，`content_hash` 520 个唯一值。
- prod 520 题，`content_hash` 集合与 dev 完全一致。
- 两边 `stem` 哈希也一致。

### 7.2 生成映射

分别从 dev/prod 查：

```sql
SELECT question_id, content_hash
FROM qbank_v2_question
WHERE id IN (...范围...);
```

得到 `dev_id -> content_hash` 和 `prod_id -> content_hash`，反推出：

```text
dev_id -> content_hash -> prod_id
```

本次映射保存在：

```text
scratch/prod_sync_map.json
```

### 7.3 生成同步 SQL

```powershell
$env:PYTHONIOENCODING='utf-8'
uv run python scratch/build_prod_sync.py
```

当前脚本读取的是两个 MCP 查询结果文件（`tool-output` 下的 Python list），并：

1. 校验 dev/prod `content_hash` 集合一致。
2. 校验 `final/*.json` 共 520 题且与 dev 范围一致。
3. 用 base64 编码 `content_html`，避免引号/换行转义问题。
4. 生成 `scratch/prod_sync.sql`。
5. 生成 `scratch/prod_sync_map.json`。

> 下次换数据时，需要把脚本顶部的 `DEV_PAIRS` / `PROD_PAIRS` 换成新查询结果文件；
> 或者把查询结果保存成 JSON 后改读取方式。

### 7.4 SQL 做了什么

`prod_sync.sql` 结构：

```text
BEGIN
CREATE TEMP TABLE sync_map(question_id, content_b64)
COPY 520 行 base64 数据
DO 块做 4 项断言：
  - 映射 520 行
  - 生产题目存在 520 题
  - 官方解析存在 520 条
  - 当前没有默认解析
备份原解析到 qbank_v2_question_explanation_bak_20261026
INSERT 520 条 default（base64 解码）
UPDATE 520 条 official 降级
输出 4 个计数
ROLLBACK 或 COMMIT
```

### 7.5 上传并 dry-run

```powershell
# 上传
ssh-could_upload 本地 scratch/prod_sync.sql -> /tmp/prod_sync.sql
```

```bash
chmod 644 /tmp/prod_sync.sql
sudo -u postgres /www/server/pgsql/bin/psql -p 8100 -d fba \
  -v commit=0 -f /tmp/prod_sync.sql
```

`-v commit=0` 时脚本末尾执行 `ROLLBACK`，只预演不落库。

本次 dry-run 输出：

```text
COPY 520
INSERT 0 520
INSERT 0 520
UPDATE 520
backup_rows      520
default_ok       520
official_demoted 520
stage            520
ROLLBACK
```

### 7.6 正式提交

```bash
sudo -u postgres /www/server/pgsql/bin/psql -p 8100 -d fba \
  -v commit=1 -f /tmp/prod_sync.sql
```

看到 `COMMIT` 即成功。

### 7.7 生产验证

MCP `fba_prob` 查（不要把备份表放进来，`yas` 无权）：

```sql
WITH scope AS (
  SELECT DISTINCT wq.question_id
  FROM fba.qbank_v2_wrong_question_state wq
  LEFT JOIN fba.qbank_v2_bank_item bi ON bi.id = wq.source_bank_item_id
  LEFT JOIN fba.qbank_v2_bank_section s ON s.id = bi.section_id
  WHERE wq.user_id = 18 AND wq.deleted = 0
    AND COALESCE(wq.entry_metadata->>'section_name', s.name)
        IN ('政治理论', '常识判断')
)
SELECT
  (SELECT count(*) FROM scope) AS scope_questions,
  (SELECT count(*) FROM scope sc
     JOIN fba.qbank_v2_question_explanation e
       ON e.question_id = sc.question_id
      AND e.explanation_type='default'
      AND e.is_default AND e.status='published' AND e.deleted=0) AS defaults_ok,
  (SELECT count(*) FROM scope sc
     JOIN fba.qbank_v2_question_explanation e
       ON e.question_id = sc.question_id
      AND e.explanation_type='official'
      AND NOT e.is_default AND e.deleted=0) AS officials_demoted;
```

本次结果：`520 / 520 / 520`。

备份表用服务器 psql 查：

```bash
sudo -u postgres /www/server/pgsql/bin/psql -p 8100 -d fba -Atc \
"SELECT count(*), count(*) FILTER (WHERE explanation_type='official' AND is_default), count(DISTINCT question_id)
 FROM fba.qbank_v2_question_explanation_bak_20261026;"
```

本次结果：`520|520|520`。

### 7.8 清理

```bash
rm -f /tmp/prod_sync.sql
```

---

## 8. 踩过的坑

### 8.1 备份表出现重复题号

`write_batch.py` 的备份 SQL 是：

```sql
INSERT INTO backup
SELECT e.* FROM qbank_v2_question_explanation e
WHERE e.question_id = ANY($1)
  AND NOT EXISTS (SELECT 1 FROM backup b WHERE b.id = e.id)
```

它备份的是这些题目的**所有**解析行，不只是 official。
如果同一批写了两次，第二次会把第一次新建的 `default` 行也备份进去，导致备份表题号重复。

本次 dev 出现过 20 条重复（batch_16 修正后重写、batch_20 漏题后补写），清理方式：

```sql
DELETE FROM qbank_v2_question_explanation_bak_20261026
WHERE explanation_type = 'default';
```

前提：原始库里这些题只有 official，没有 default。

### 8.2 备用脚本不要用 `<s>`

校验器明确禁止 `<s>`，必须用 `span` + `text-decoration:line-through`。

### 8.3 计数/组合题最容易错

- 每个判断句都要标 ✓/✗。
- “正确的为”必须和绿色 ✓ 完全一致。
- 计数题必须写“共 N 项”。
- 组合题不要标 A-D，只标①②③。

### 8.4 dev/prod 题目 ID 不同

本次 dev 58k、prod 98k，必须用 `content_hash` 映射。
不要凭题干相似度手工猜，`content_hash` 已唯一且两边一致。

### 8.5 生产备份表权限

生产 MCP 用户 `yas` 只能查主表，查备份表会报：

```text
permission denied for table qbank_v2_question_explanation_bak_20261026
```

用服务器 `sudo -u postgres psql` 查，或给 `yas` 授权。

### 8.6 解析是全局数据

`qbank_v2_question_explanation` 按 `question_id` 存，不按用户。
同步后，所有能看到这 520 题的生产用户都会使用新默认解析，不只 test123。
如果只想影响某个用户，当前表结构做不到，需要额外的用户级覆盖表。

### 8.7 不影响用户错题状态

本次只写解析表，没有改 `qbank_v2_wrong_question_state`。
test123 的错题、答案、复习状态保持不变。

---

## 9. 回滚思路

如果生产需要撤回本次解析：

```sql
BEGIN;

-- 1. 删掉本次新增的 default（按映射表/题目范围）
DELETE FROM fba.qbank_v2_question_explanation e
WHERE e.question_id IN (...520 个 prod_id...)
  AND e.explanation_type = 'default'
  AND e.deleted = 0;

-- 2. 恢复 official 为默认
UPDATE fba.qbank_v2_question_explanation e
SET is_default = TRUE
WHERE e.question_id IN (...520 个 prod_id...)
  AND e.explanation_type = 'official'
  AND e.deleted = 0;

COMMIT;
```

注意：

- 执行前确认这些题原本没有别的 default。
- 520 个 prod_id 可从 `scratch/prod_sync_map.json` 提取。
- 更稳妥的做法是先在同库演练一次 `BEGIN ... ROLLBACK`。

---

## 10. 下次继续做别的用户/题库

1. 改 `scratch/prepare_batches.py` 的 `user_id` 和章节条件。
2. 重新生成 `batches/`。
3. 按批次手写 `final/`。
4. 跑 `validate_final.py`。
5. 跑 `write_batch.py XX --apply` 写 dev。
6. 按第 5 节 SQL 验证 dev。
7. 如需同步生产：
   - 找出生产对应 user_id；
   - 用 `content_hash` 做 dev→prod 映射；
   - 修改 `build_prod_sync.py` 的输入文件；
   - 生成 SQL；
   - `-v commit=0` dry-run；
   - `-v commit=1` 提交；
   - 验证 520/520/520 和备份。

---

## 11. 给下一个模型的最短提示词

```text
请阅读 D:\100_Work\101_Program\Proj\fba\doc\question-explanation-sync-workflow.md，
按里面的流程继续处理题库解析。解析必须逐题手写，禁止脚本生成；
每批先 validate_final.py 通过，再 write_batch.py --apply；
生产同步必须用 content_hash 映射，先 dry-run 再 commit。
```

---

## 12. 本次变更记录

| 时间 | 环境 | 操作 |
|---|---|---|
| 2026-10-26 | dev | batch_01–26 共 520 题写入 default，official 降级 |
| 2026-10-26 | dev | 备份表 520 行，清理 20 条重复 default 备份 |
| 2026-10-26 | prod | 通过 content_hash 映射 520 题，dry-run 通过 |
| 2026-10-26 | prod | 正式提交：520 default + 520 official 降级 + 520 备份 |

生产库变更需谨慎：后续操作前先备份、先 dry-run；回滚见第 9 节。
