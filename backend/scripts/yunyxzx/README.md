# 云易学题库导入工具

从**云易学（yunyxzx）**小程序/网页接口拉取单套试卷题目，导入本地 **V2 题库**并按合集挂载。

## 目录

| 文件 | 作用 |
|---|---|
| `import_yunyxzx_paper.py` | 拉取远端试卷题目（或读本地 JSON）→ 导入 V2 题库（开发/生产库）+ 挂载合集 |

## 流程概览

```
远端接口（queryoPaperSubjectList，需 Cookie / Authorization）
   或本地抓包 JSON（--input-json）
   │
   ▼
import_yunyxzx_paper.py
   │
   ▼
创建题库（qbank_v2_bank + revision）
+ 题目（question + answer + explanation）
+ 章节（按题型分组 / 统一章节 / 无章节）
+ 合集挂载（qbank_v2_collection_bank）
```

## 用法

> **重要**：每次导入前**务必先跑 `--dry-run` 预检**，确认无误后再去掉 `--dry-run` 正式导入，避免中断/参数错误导致库中留下半成品数据。

```bash
# 第 1 步：dry-run 预检（只读，不写入任何数据）
python backend/scripts/yunyxzx/import_yunyxzx_paper.py \
    --paper-id 12345 \
    --paper-name "2027 考研政治真题" \
    --collection-code qb_kp_yu_27 \
    --env dev --dry-run

# 第 2 步：确认预检无误后，正式导入开发库
python backend/scripts/yunyxzx/import_yunyxzx_paper.py \
    --paper-id 12345 \
    --paper-name "2027 考研政治真题" \
    --collection-code qb_kp_yu_27 \
    --env dev

# 导入生产库（读取 backend/.env.prod）
python backend/scripts/yunyxzx/import_yunyxzx_paper.py \
    --paper-id 12345 \
    --paper-name "2027 考研政治真题" \
    --collection-code qb_kp_yu_27 \
    --env prod

# 使用本地抓包 JSON（不请求网络），并挂载到新建的合集树
python backend/scripts/yunyxzx/import_yunyxzx_paper.py \
    --input-json response.json \
    --paper-name "2027 考研政治真题" \
    --bank-code qb_xxx_001 \
    --collection-code qb_kp_xxx_27 \
    --parent-collection-code qb_kp_xxx \
    --env dev
```

参数：
- `--paper-id`（必填）：远端 paperId
- `--paper-name`：试卷名称（不传则用 paperId 生成）
- `--mode`：远端接口 mode（默认 2）
- `--bank-code`：题库 code（不传则自动生成 `YUNYXZX_<paperId>`）
- `--bank-kind`：题库类型 `practice` / `paper`（默认 `practice`）
- `--collection-code`：要挂载的合集 code（按 code 查找，不存在则创建）
- `--collection-name`：合集不存在时使用的名称（默认等于 code）
- `--parent-collection-code`：父合集 code（合集不存在时创建父子层级）
- `--cookie` / `--authorization`：远端接口鉴权（需自行抓包获取）
- `--input-json`：本地接口响应 JSON 文件，传入后不请求网络
- `--chapter-name`：统一章节名称（所有题归入同一章节，不再按题型拆分）
- `--no-chapter`：不创建章节，题目直接挂载到题库
- `--dry-run`：只读预检。统计题目/题型分布，检查合集是否存在、item_key 是否与库中已有数据冲突，**不写入任何数据**
- `--env`：目标库环境 `dev` / `prod`（默认 `dev`）
- `--timeout`：接口超时时间（默认 30 秒）

## 题型映射

| 远端 subType | V2 题型 |
|---|---|
| 1 单选题 | `single_choice`（答案含多个字母时推断为 `multiple_choice`） |
| 2 多选题 | `multiple_choice` |
| 3 判断题 | `true_false`（自动识别"正确/错误"选项对） |
| 4 填空题 | `fill_blank` |
| 5 简答题 | `short_answer` |
| 6 材料题 | `short_answer` |

## 注意事项

- **先 dry-run 再正式导入**：正式导入是逐题写库并随进度提交（每道题 `commit`），一旦中途超时/断网/被杀，会留下**已导入的部分数据（题库、题目、解析、章节、挂载都可能不完整）**。因此导入前必须先用 `--dry-run` 确认题目、合集 code、item_key 无冲突，再正式执行。
- **中途失败不要直接重跑**：脚本每次运行都会**新建**一个 bank + revision。若上次导入被中断，残留的半成品会形成"题库里部分题目+挂载缺失"的脏数据。需先手工清理残留（见下文"中断后的清理"），否则重跑只会把剩余题目导进另一个新 bank。
- **生产库超时**：生产库位于远程服务器，网络延迟高，导入大批量题目时易超时。正式导入生产库建议把 shell 超时调大（如 600 秒），或分批导入。
- **item_key 是去重键**：`item_key` 取远端题目 id，同一 id 在库中已存在时该题会被跳过（计入 `skipped`），不会重复插入。若误导了内容，需先删掉旧的再重导。
- **章节按远端 subType 分组**：如"单选题/多选题/判断题"各自成章节；但 subType=1 中推断出的多选题仍会落在"单选题"章节（因为分组用的是远端 subType）。如需按题型精确分组，可用 `--no-chapter` 或 `--chapter-name` 统一起名。

## 中断后的清理

上次导入中断（如超时）导致残留时，按以下顺序清理（以 bank code `qb_xxx` 为例，先查到其 `bank_id` 和 `revision_id`）：

```sql
-- 1. 找到残留的 bank 与 revision
SELECT b.id AS bank_id, br.id AS revision_id, br.revision_no, br.question_count
FROM qbank_v2_bank b
LEFT JOIN qbank_v2_bank_revision br ON br.bank_id = b.id
WHERE b.code = 'qb_xxx' AND b.deleted = 0;

-- 2. 按依赖顺序删除（必须按此顺序，否则外键约束报错）
DELETE FROM qbank_v2_collection_bank WHERE bank_id = <bank_id>;
DELETE FROM qbank_v2_bank_item WHERE bank_revision_id = <revision_id>;
DELETE FROM qbank_v2_bank_section WHERE bank_revision_id = <revision_id>;
DELETE FROM qbank_v2_question_answer WHERE question_id IN (SELECT id FROM qbank_v2_question WHERE code LIKE 'qb_xxx%');
DELETE FROM qbank_v2_question_explanation WHERE question_id IN (SELECT id FROM qbank_v2_question WHERE code LIKE 'qb_xxx%');
DELETE FROM qbank_v2_question WHERE code LIKE 'qb_xxx%';
-- 先解除 bank 对 revision 的引用（current_revision_id 外键），否则删 revision 会失败
UPDATE qbank_v2_bank SET current_revision_id = NULL WHERE id = <bank_id>;
DELETE FROM qbank_v2_bank_revision WHERE id = <revision_id>;
DELETE FROM qbank_v2_bank WHERE id = <bank_id>;
```

> 清理语句彼此有外键依赖，**必须一条一条执行**（不要放在同一事务里一起跑，否则中途报错会整体回滚、一条都没生效）。
>
> **常见报错与解决**：
> - `qbank_v2_bank_revision` 被 `qbank_v2_bank_section` 引用 → 先删 section（上面的顺序已覆盖）
> - `qbank_v2_bank_section` 被 `qbank_v2_bank_item` 引用 → 先删 item（上面的顺序已覆盖）
> - `qbank_v2_bank_revision` 被 `qbank_v2_bank.current_revision_id` 引用 → 必须先 `UPDATE qbank_v2_bank SET current_revision_id = NULL`
> - `qbank_v2_bank_revision` 又引用 `qbank_v2_bank`（bank_id 外键）→ 需先置空 `current_revision_id` 再按"先 revision 后 bank"的顺序删
