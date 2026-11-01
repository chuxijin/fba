# 题库数字化与入库发布

功能标识 **`question-bank-import`**：源书/PDF/扫描件 → 结构化题库成果 → 打样与质检 → 发布至本轮授权环境。默认不连接数据库，不自动写入双环境。

## 新会话入口

把 [WORKFLOW.md](WORKFLOW.md) 发给新 AI，附上源文件、题库名称及本轮目标：

> 请按规范处理本轮题库。先调研、做一题及一章打样，审核后再全量制作。所有文件放对应run；未授权不联网或写库。导入前核对环境、分类/合集与当前服务限制，提交后独立核验，不重放历史脚本。

```text
question-bank-import/
  README.md
  WORKFLOW.md                  # 唯一现行规范
  scripts/
    new_bank_run.py            # 安全创建任务目录，不覆盖旧任务
    qc_validator.py            # 10列ABCD选择题的离线结构检查
  runs/YYYYMMDD-任务名/        # 源信息、最终成果、核验及本轮工具
```

从仓库根目录创建新任务（名称不可与已有任务重复）：

```powershell
uv run python skills/fba_work/question-bank-import/scripts/new_bank_run.py 20261102-example --name '本轮题库名' --code qb_example
```

## 已有任务

| 记录 | 题数 | 状态口径 |
|---|---|---|
| [肖193题](runs/20261030-xiao193/README.md) | 历史记载193 | 生产发布有历史ID；开发状态需证据核实，本次未查库 |
| [米李720题](runs/20261031-mili720/README.md) | 历史记载785 | 原记录载双环境发布与52题修复；本次只整理，实时状态未核验 |
| [苏一300题](runs/20261101-suyi300/README.md) | 历史调研642 | 待打样，题型/题量以完整源数据复核为准，不清理其唯一中间结果 |
| [米六套卷历史资料](runs/20261101-legacy-mi6/README.md) | 历史记载198 | 保留OCR与页图，原PDF旧路径缺失；本次未查库 |
| [腿姐八套卷历史资料](runs/20261101-legacy-tuijie8/README.md) | 待核实 | 原PDF仍在，清理可重建页图，OCR保留 |
| [徐涛十套卷历史资料](runs/20261101-legacy-xutao10/README.md) | 待核实 | 原PDF旧路径缺失，现存OCR与页图保留 |

## 使用边界与保留

10列质检器只检查两级章节、ABCD单选/多选；不证明语义正确，不覆盖其他题型。原生详析/批注/补充解析按规范分别处理。
手写精简解析使用 [question-explanation](../question-explanation/WORKFLOW.md)，接口来源采集使用 [kaoyantu](../kaoyantu/WORKFLOW.md) 或 [yunyxzx](../yunyxzx/WORKFLOW.md)。

源文件及哈希、唯一OCR/人工校正、最终Excel、必要预览、核验结果、精确ID和备份信息须保留。临时分片/图片/日志放run/work，完成且可追溯后才能清理。历史写库脚本只作审计，不直接执行。

本次规范审核移除了文档中的明文生产凭据。旧副本/历史版本可能仍存在，用户应评估轮换；整理资料不会自动更换凭据，也不会修改生产。

## 2026-11-01 清理结果

- 原根目录/scratch精确盘点1561个文件：删除254个（85,363,609字节，约81.41 MiB），归档1281个，原地保留26个；归档文件逐条大小/SHA256一致。
- 删除包括可由现存原PDF重建的腿姐页图、字节相同的重复Excel、已被替代的只读调试脚本与缓存；未删唯一OCR、米六/徐涛原PDF缺失情况下的页图、未完成苏一300资料。
- 根目录保留工程脚本start.py/deploy.sh、工程配置、个人资料及与本任务无关的近期渲染交付记录；scratch只留简短README入口。
- 文件级清单见 [cleanup-20261101.json](cleanup-20261101.json)；执行中的检查点保留于临时工具目录，不作为第二份现行规范。
- 另外清除了本轮命令引号解析产生的2个0字节重定向文件（`1))`、`2))`），不计入原1561条清单和释放空间。
