"""Create an isolated local explanation task directory; never access a database."""

import argparse
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name', help='Run name such as 20261108-season42')
    parser.add_argument('--title', default='题库解析任务')
    args = parser.parse_args()
    if not re.fullmatch(r'\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*', args.name):
        parser.error('name must be YYYYMMDD-lowercase-task-name')
    root = Path(__file__).resolve().parent.parent
    target = root / 'runs' / args.name
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.mkdir()
    except FileExistsError:
        parser.error(f'Run already exists; refusing to overwrite: {target}')
    (target / 'work').mkdir()
    (target / 'README.md').write_text(
        f'# {args.title}\n\n'
        '- 状态：待定位，尚未连接数据库或写入生产。\n'
        '- 环境、完整来源、用户、科目、题目集合及题数：执行前查询并填写。\n'
        '- 默认策略：模考新default设默认；练习库新增非默认简短版。执行前明确本轮类型。\n'
        '- 原始快照：source.json；手写成品：final.json；复核：verify.json。\n'
        '- 备份表、dry-run结果、提交结果：操作后据实记录，不得提前标为已完成。\n'
        '- 临时分片、调试日志、预览仅放work/；完成并验证后按规范清理。\n'
        '- 交接规范：[WORKFLOW.md](../../WORKFLOW.md)。\n',
        encoding='utf-8',
    )
    print(target)


if __name__ == '__main__':
    main()
