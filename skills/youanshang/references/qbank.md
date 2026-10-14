# 题库检索（真题库 / 题目目录 / 题目详情）

调用下列命令前必须已成功 `bash scripts/install.sh` 且本地配置包含 `qbank:read` scope（旧配置请重新 login 升级）。当用户需要浏览题库、查真题、看题目答案解析时使用本页。

> [!NOTE] 三个命令均为**只读**：不会答题、不会落练习记录。检索结果（qbank-search）不含答案解析，需要答案请按题目 ID 调用 `qbank-detail`。

## 命令参数

### `qbank-banks [--category-id ID] [--bank-kind practice|paper|mock] [--keyword 词] [--page N] [--size N]`
列出已发布的公开题库目录。`bank-kind`：`practice` 刷题册 / `paper` 真题卷 / `mock` 模拟卷；`size` 默认 20、上限 200。返回分页数据 `items: [{id, name, bank_kind, ...}]`。

### `qbank-search [--bank-id ID] [--question-type 题型] [--keyword 词] [--page N] [--size N]`
在题库内检索题目列表。`question-type` 枚举：`single_choice | multiple_choice | true_false | fill_blank | short_answer | composite | interactive`；`keyword` 命中题干。返回题目列表项（含 `id, code, stem, question_type, difficulty` 等），**不含选项与答案**。

### `qbank-detail --id <题目 ID>`
取单题聚合详情：题干（`stem`，可能含 HTML）、`options` 有序选项、`answer.answer_data` 标准答案、`explanations` 解析、`knowledge_points` 知识点标注、`materials` 关联材料。

示例：

```bash
# 看"2026年7月时政"题库里有什么题
node scripts/youanshang.cjs qbank-banks --keyword "2026" --bank-kind practice --session-id "当前对话ID"
node scripts/youanshang.cjs qbank-search --bank-id 2559 --size 5 --session-id "当前对话ID"
node scripts/youanshang.cjs qbank-detail --id 29199 --session-id "当前对话ID"
```

**注意事项**

- 参数值一律传字符串；ID 类参数必须是正整数，非法值会直接返回 `INVALID_ARGUMENT`
- 推荐路径：`qbank-banks` 选题库 → `qbank-search` 拿题目列表 → `qbank-detail` 按需取答案解析；不要对列表里每道题都抓详情，避免放大请求量
- `qbank-banks` 仅返回已发布版本对应的公开题库；管理端草稿/下线题库不会出现

## 错误码含义速查

| code | 责任方建议动作 |
|---|---|
| -1 | INVALID_ARGUMENT / INVALID_CONFIG：参数不合法或本地配置过旧（缺 `qbank:read`），请重新 login |
| -1408 | AUTH_REQUIRED：尚未授权/已过期，先执行 login |
| 403 | 服务端拒绝：token 缺 `qbank:read` scope 或会员资格不足。scope 缺失请重新 login；会员问题原样转告服务端 `msg` |
| 404 | 题目或题库不存在：不要把 404 当重试信号，向用户说明编号无效即可 |
| 422 | 查询参数被 Schema 校验拒绝，按 `msg` 修正参数 |

---

提示：题目详情中的题干/选项/解析可能是 HTML 富文本，转述给用户时应做纯文本化（去标签），不要把原始标签贴在回答里。
