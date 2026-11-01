"""Offline structural checks for the two-level, ten-column ABCD choice workbook."""

import argparse
import json
import re
from pathlib import Path

import openpyxl

EXPECTED_HEADERS = [
    'section_l1', 'section_l2', 'question_type', 'stem',
    'option_A', 'option_B', 'option_C', 'option_D',
    'answer', 'explanation_default',
]
ILLEGAL_CHAR_REGEX = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
TITLE_PATTERN = re.compile(r'(?:^|[\r\n>])\s*(?:[一二三四五六七八九十]+[、.．]\s*)?[单多]项选择题')


def validate_excel(file_path: Path, expected_count: int | None = None) -> dict:
    """Return all structural issues; never infer content correctness or touch a database."""
    workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=False)
    try:
        sheet = workbook.worksheets[0]
        rows = iter(sheet.iter_rows())
        header = next(rows, ())
        headers = [str(cell.value if cell.value is not None else '').strip() for cell in header]
        file_issues = []
        if headers != EXPECTED_HEADERS:
            file_issues.append('表头必须严格等于约定的10列且顺序一致')
        issues = []
        total = clean = singles = multiples = 0
        for excel_row, cells in enumerate(rows, start=2):
            values = [cell.value for cell in cells]
            if all(value is None or value == '' for value in values):
                continue
            total += 1
            row_issues = []
            fields = {
                name: str(values[index] if index < len(values) and values[index] is not None else '').strip()
                for index, name in enumerate(EXPECTED_HEADERS)
            }
            for name, value in fields.items():
                if not value:
                    row_issues.append(f'{name}为空')
            for index, cell in enumerate(cells):
                value = str(cell.value if cell.value is not None else '')
                if cell.data_type == 'f':
                    row_issues.append(f'第{index + 1}列包含公式，须转换为已核实的字面值')
                if ILLEGAL_CHAR_REGEX.search(value):
                    row_issues.append(f'第{index + 1}列包含非法控制字符')
                if len(value) > 32767:
                    row_issues.append(f'第{index + 1}列超出Excel单元格长度限制')
            answer = fields['answer']
            qtype = fields['question_type']
            if qtype in ('单选', '单选题'):
                singles += 1
                if not re.fullmatch(r'[A-D]', answer):
                    row_issues.append('单选答案必须为一个大写A—D')
            elif qtype in ('多选', '多选题'):
                multiples += 1
                if not re.fullmatch(r'[A-D]{2,4}', answer) or len(set(answer)) != len(answer):
                    row_issues.append('多选答案必须为2—4个不重复的大写A—D')
                elif answer != ''.join(sorted(answer)):
                    row_issues.append('多选答案须按A—D顺序排列')
            else:
                row_issues.append('题型不受当前10列选择题契约支持')
            for name in ('option_A', 'option_B', 'option_C', 'option_D', 'explanation_default'):
                value = fields[name]
                if TITLE_PATTERN.search(value):
                    row_issues.append(f'{name}疑似拼入章节标题，需对照原页确认')
                if name.startswith('option_') and re.match(r'^[A-DＡ-Ｄ][.．、]\s*', value):
                    row_issues.append(f'{name}疑似残留选项标号')
            if fields['explanation_default'] == '暂无解析':
                row_issues.append('发布成品不能以暂无解析占位')
            if row_issues:
                issues.append({'row': excel_row, 'issues': row_issues})
            else:
                clean += 1
        if total == 0:
            file_issues.append('工作簿没有有效题目')
        if expected_count is not None and total != expected_count:
            file_issues.append(f'实际题数{total}与预期{expected_count}不一致')
        return {
            'file': str(file_path), 'sheet': sheet.title,
            'scope': '结构检查，不代表语义正确或已完成数据库核验',
            'total_questions': total, 'expected_count': expected_count,
            'single_choice_count': singles, 'multiple_choice_count': multiples,
            'clean_questions': clean, 'issue_questions_count': len(issues),
            'pass_rate': f'{clean / total * 100:.2f}%' if total else '0%',
            'status': 'PASS' if not file_issues and not issues else 'FAIL',
            'file_issues': file_issues, 'issues': issues,
        }
    finally:
        workbook.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('excel_path')
    parser.add_argument('--expected-count', type=int)
    parser.add_argument('--output', help='本轮JSON报告路径，不得覆盖输入Excel')
    args = parser.parse_args()
    source = Path(args.excel_path)
    if args.expected_count is not None and args.expected_count <= 0:
        parser.error('expected-count必须大于0')
    target = Path(args.output) if args.output else None
    if target is not None and target.resolve() == source.resolve():
        parser.error('报告路径不得等于输入文件')
    try:
        report = validate_excel(source, args.expected_count)
    except Exception as exc:
        report = {
            'file': str(source), 'status': 'FAIL',
            'file_issues': [f'读取/校验失败: {type(exc).__name__}: {exc}'], 'issues': [],
        }
    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'issues'}, ensure_ascii=False))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
