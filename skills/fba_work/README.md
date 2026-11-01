# FBA 工作手册与任务归档

按工作类型集中管理AI工作规范、脚本、成品与执行记录，不再把任务文件散放到doc、scratch或仓库根目录。

## 工作索引

| 文件夹 | 功能 | 入口 |
|---|---|---|
| `question-bank-import/` | 题库数字化与入库发布 | [工作入口](question-bank-import/README.md) · [完整AI交接规范](question-bank-import/WORKFLOW.md) |
| `question-explanation/` | 题库解析精编与发布 | [工作入口](question-explanation/README.md) · [完整AI交接规范](question-explanation/WORKFLOW.md) |
| `kaoyantu/` | 考研兔题库采集与导入 | [工作入口](kaoyantu/README.md) · [完整AI交接规范](kaoyantu/WORKFLOW.md) |
| `yunyxzx/` | 云易学试卷采集与导入 | [工作入口](yunyxzx/README.md) · [完整AI交接规范](yunyxzx/WORKFLOW.md) |

选择方式：从考研兔/云易学取得原始题库并入库，使用对应来源的规范；题目已在库中，需要手写精简解析或切换解析默认，使用 `question-explanation`。这三项工作可衔接，但不得混用默认策略或重放历史导入/修复脚本。

## 新增其他工作

每种工作单独创建一个语义明确的文件夹，并在上表登记。建议统一结构：

```text
<功能名称>/
  README.md       # 功能入口、目录说明和使用方式
  WORKFLOW.md     # 可独立发给AI的完整规则
  scripts/        # 真正可复用的工具，不放固定某次任务的脚本
  runs/           # 按日期和任务名归档，含状态与成品
  archive/        # 旧流程，仅在需要时阅读
```

任务临时文件只能放在对应run的`work/`，完成后按功能清理规则及时清理。
不要将凭据、密码或访问令牌写入本目录。这里是本地工作资料入口，不会自动安装或注册为AI Skill。
