# 考研兔题库工具集

专门用于**考研兔（kaoyantu）题目数据**的完整流程：解析原始抓包文件 → 导出 V2 格式 Excel → 导入本地 V2 题库并挂载到合集。

## 目录

| 文件 | 作用 |
|---|---|
| `extract_kaoyantu_from_burp.py` | 解析考研兔 Burp 抓包 XML/文本，提取题目并导出 V2 格式 Excel（题目表 + 材料表） |
| `import_to_v2.py` | 将 V2 格式 Excel 导入本地 V2 题库（开发/生产库），支持创建合集并挂载 |
| `README.md` | 本说明 |

## 流程概览

```
考研兔抓包文件（Burp 导出的 XML / 原始文本）
   │
   ▼
extract_kaoyantu_from_burp.py
   │
   ▼
V2 格式 Excel（题目 + 材料 两个 sheet）
   │
   ▼
import_to_v2.py（导入开发/生产库）
   │
   ▼
创建题库 + 题目 + 解析 + 章节
+ 合集（米系列/米27…）+ 挂载
```

## V2 格式 Excel 说明

生成/导入的 Excel 包含两个 sheet：

### 题目表（sheet: 题目）

| 列 | 说明 |
|---|---|
| `question_type` | V2 题型枚举：`single_choice` / `multiple_choice` / `true_false` / `fill_blank` / `short_answer` |
| `stem` | 题干（支持 HTML） |
| `answer` | 答案。单选如 `A`、多选如 `AB`、判断题 `对/错`、简答题为文本 |
| `explanation_default` | 解析（可拆分 `explanation_official` / `explanation_expert` 等） |
| `option_A` ~ `option_E` | 选项 |
| `score` | 分值（多选默认 2 分，其余 1 分） |
| `section_l1` / `section_l2` / `section_l3` | 章节三级层级（自动创建章节树） |
| `item_key` | 题目去重键（跨库/重复导入时用于跳过） |
| `material_code` | 关联材料表，多个用逗号分隔（如 `m1,m2`） |

### 材料表（sheet: 材料）

| 列 | 说明 |
|---|---|
| `material_code` | 材料唯一编号，供题目表 `material_code` 列引用 |
| `material_title` | 材料标题 |
| `material_content` | 材料正文（支持 HTML） |

> 考研兔数据当前不含材料，材料表会保留表头但无数据；后续数据源补充材料后可直接填入。

## 用法

### 1. 从 Burp 抓包文件解析并导出 Excel

```bash
# 单文件
python backend/scripts/kaoyantu/extract_kaoyantu_from_burp.py \
    --input "C:\Users\19396\Desktop\27mi1000" \
    --output "C:\Users\19396\Desktop\27mi1000_v2.xlsx"

# 多文件合并（用于补充包）
python backend/scripts/kaoyantu/extract_kaoyantu_from_burp.py \
    --input old.xml patch.xml \
    --output backend/scripts/kaoyantu/outputs/merged.xlsx

# 只导出有真实解析的题目
python backend/scripts/kaoyantu/extract_kaoyantu_from_burp.py \
    --input burp.txt --only-with-analysis \
    --output backend/scripts/kaoyantu/outputs/questions.xlsx
```

参数：
- `--input`（必填）：Burp 导出的 XML 或普通文本文件，可传多个
- `--output`：输出 Excel 路径（默认 `backend/scripts/outputs/kaoyantu_burp_questions.xlsx`）
- `--only-with-analysis`：只导出有真实解析的题目

### 2. 导入到数据库

> **重要**：每次导入前**务必先跑 `--dry-run` 预检**，确认无误后再去掉 `--dry-run` 正式导入，避免中断/参数错误导致库中留下半成品数据。

```bash
# 第 1 步：dry-run 预检（只读，不写入任何数据）
python backend/scripts/kaoyantu/import_to_v2.py \
    --file "C:\Users\19396\Desktop\27mi1000_v2_final.xlsx" \
    --bank-name "27米1000题" \
    --bank-code qb_mi_27_1000 \
    --collection-code qb_kp_mi_27 \
    --parent-collection-code qb_kp_mi \
    --env prod --dry-run

# 第 2 步：确认预检无误后，正式导入
python backend/scripts/kaoyantu/import_to_v2.py \
    --file "C:\Users\19396\Desktop\27mi1000_v2_final.xlsx" \
    --bank-name "27米1000题" \
    --bank-code qb_mi_27_1000 \
    --collection-code qb_kp_mi_27 \
    --parent-collection-code qb_kp_mi \
    --env prod
```

参数：
- `--file`（必填）：V2 格式 Excel 路径
- `--bank-name`（必填）：题库名称，如 `27米1000题`
- `--bank-code`：题库 code（可选，默认按文件名生成）
- `--bank-kind`：题库类型 `practice` / `paper`（默认 `practice`）
- `--collection-code`：要挂载的合集 code（按 code 查找，不存在则创建）
- `--collection-name`：合集不存在时使用的名称（默认等于 code）
- `--parent-collection-code`：父合集 code（合集不存在时创建父子层级）
- `--env`：目标库环境 `dev` / `prod`（默认 `dev`）
- `--dry-run`：只读预检。统计题目/题型分布，检查合集是否存在、item_key 是否与库中已存在数据冲突，**不写入任何数据**

> **注意**：`--env prod` 会写入生产数据库，执行前请务必在开发库验证通过。

## 注意事项

- **先 dry-run 再正式导入**：正式导入是逐题写库并随进度提交（每道题 `commit`），一旦中途超时/断网/被杀，会留下**已导入的部分数据（题库、题目、解析、章节、挂载都可能不完整）**。因此导入前必须先用 `--dry-run` 确认文件、合集 code、item_key 无冲突，再正式执行。
- **中途失败不要直接重跑**：脚本每次运行都会**新建**一个 bank + revision。若上次导入被中断，残留的半成品会形成"题库里部分题目+挂载缺失"的脏数据。需先手工清理残留（见下文"中断后的清理"），否则重跑只会把剩余题目导进另一个新 bank。
- **生产库超时**：生产库位于远程服务器，网络延迟高，导入大批量题目时易超时。正式导入生产库建议把 shell 超时调大（如 600 秒），或分批导入。
- **item_key 是去重键**：同一 item_key 在库中已存在时，该题会被跳过（计入 `skipped`），不会重复插入。若误导了内容，需先删掉旧的再重导。

### 中断后的清理

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

## 题型识别规则

`extract_kaoyantu_from_burp.py` 中题型自动识别：

1. **答案整体为字母组合**（如 `A`、`AB`、`A,B`）→ 单选 / 多选（按字母数量判定）
2. **答案为长文本**（非字母组合）→ 简答题 `short_answer`
3. 无答案时回退到接口 `type` 字段 → 章节名映射 → 默认单选

## 已用示例（27米1000题）

`C:\Users\19396\Desktop\27mi1000`（考研兔 Burp 抓包文件）：
1. 解析导出 → `27mi1000_v2_final.xlsx`（1010 题：单选 468 / 多选 525 / 简答 17）
2. 导入开发库 → 创建 `考研题库→考研政治→米系列题库→米27考研` 合集树，题库 `27米1000题`（1010 题）挂载成功
3. 导入生产库 → 复用已有 `考研政治`，新增 `米系列题库(2500)→米27考研(2501)`，题库 `27米1000题`（bank 2489，1010 题）挂载成功
