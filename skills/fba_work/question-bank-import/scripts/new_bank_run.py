#!/usr/bin/env python3
"""
初始化题库数字化与入库任务目录模板。
用法：
    uv run python skills/fba_work/question-bank-import/scripts/new_bank_run.py 20261102-example --name "本轮题库名" --code "qb_example"
"""
import argparse
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RUNS_DIR = BASE_DIR / "runs"

README_TEMPLATE = """# {bank_name} 数字化与入库任务归档

- **题库全名**：`{bank_name}`
- **英文代号**：`{bank_code}`
- **归档目录**：`{run_id}`
- **执行状态**：`待开始`，尚未联网、连接数据库或执行导入。
- **授权环境及操作范围**：`待确认`（不默认双环境）
- **交接规范**：[WORKFLOW.md](../../WORKFLOW.md)
- **源文件路径**：
  - 试题文件：`待填写`
  - 解析/答案文件：`待填写`

## 1. 题库规格与元数据

| 维度 | 参数 | 备注 |
|---|---|---|
| **题库名称** | `{bank_name}` | 严格按括号与版次规范 |
| **英文代号** | `{bank_code}` | 数据库唯一标识 |
| **学科分类** | `待确认` | 每个环境分别核实分类及主分类ID |
| **挂载合集** | `待确认合集名称` (`collection_id=待填`) | 对应一级与二级合集 |
| **章节层级** | 两级树状（`section_l1` / `section_l2`） | 必须严格对齐原书目录 |
| **设计题量** | `待统计` 题（单选: X, 多选: Y） | 以实测有效题量为准 |

## 2. 解析三模式策略记录

- [ ] **模式 A（纯大段原生解析）**：若源文件自带完整文本解析，原汁原味提取并富文本清洗后入库。
- [ ] **模式 B（选项批注 · 腿姐模式）**：选项与批注分离；第二解析的创建、版本名和默认策略先确认，不自动改已有默认。
- [ ] **模式 C（原书仅答案字母 · 苏一模式）**：先说明解析缺失，用户要求补写后再逐题撰写并核验，不冒充原书解析。

## 3. 本轮任务执行产物

- `source_info.json`：源文件基本面、目录树与原始提取文本快照。
- `{bank_code}_full.xlsx`：全量标准化制作成果表（包含 10 个标准列）。
- `{bank_code}_preview.html`：全景卡片预览 HTML（供人工直观终验）。
- `qc_report.json`：实际离线结构检查报告，不能证明无语义错位，未执行不得标通过。
- `scripts/`：本轮专用工具，不含凭据，已执行写库脚本禁止重放。
- `import_result.json`：仅已授权环境的实际执行结果、精确ID与提交证据。
- `verify.json`：独立复核、来源映射、备份信息与未解决异常。

## 4. 执行状态更新流水线

1. [ ] 源文件逆向调研与两级章节定位
2. [ ] 先做一题与先做一套打样，并经人工审核通过
3. [ ] 全量状态机分题切片与解析组装
4. [ ] 运行 `qc_validator.py` 质量门禁质检（100% 达标）
5. [ ] 按本轮授权导入指定环境，保存实际结果
6. [ ] 独立核对提交、题量、章节、默认解析、分类与合集
7. [ ] 本地成果与桌面副本备份归档
"""

def main():
    parser = argparse.ArgumentParser(description="创建题库数字化与入库任务目录")
    parser.add_argument("run_id", help="任务目录名，建议格式 YYYYMMDD-题库简写，如 20261101-suyi300")
    parser.add_argument("--name", required=True, help="本轮确认的题库全名")
    parser.add_argument("--code", required=True, help="本轮确认的题库英文代号")
    args = parser.parse_args()

    if not re.fullmatch(r'\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*', args.run_id):
        parser.error('run_id必须为YYYYMMDD-lowercase-task，禁止路径或目录穿越')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', args.code):
        parser.error('code必须为1—64个字母、数字、下划线或连字符')
    if not args.name.strip() or any(c in args.name for c in '\r\n\x00'):
        parser.error('name必须为非空单行名称')
    target_dir = RUNS_DIR / args.run_id
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        target_dir.mkdir()
    except FileExistsError:
        parser.error(f'目录已存在，拒绝覆盖: {target_dir}')
    (target_dir / 'source').mkdir()
    (target_dir / 'final').mkdir()
    (target_dir / 'scripts').mkdir()
    work_dir = target_dir / "work"
    work_dir.mkdir(exist_ok=True)

    readme_content = README_TEMPLATE.format(
        run_id=args.run_id,
        bank_name=args.name,
        bank_code=args.code
    )
    (target_dir / "README.md").write_text(readme_content, encoding="utf-8")

    print(f"✅ 成功初始化题库任务目录：{target_dir}")
    print(f"   - 状态说明：{target_dir / 'README.md'}")
    print(f"   - 临时工作区：{work_dir}")

if __name__ == "__main__":
    main()
