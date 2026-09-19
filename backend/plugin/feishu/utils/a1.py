import re

_CELL_RE = re.compile(r'^([A-Z]+)(\d+)$')


def column_index_to_letter(index: int) -> str:
    """
    列序号转列字母

    :param index: 1-based 列序号，如 1 -> A、27 -> AA
    :return:
    """
    if index < 1:
        raise ValueError(f'列序号必须大于 0，当前值: {index}')

    letters = ''
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def column_letter_to_index(letter: str) -> int:
    """
    列字母转列序号

    :param letter: 列字母，如 A -> 1、AA -> 27
    :return:
    """
    value = 0
    for char in letter.strip().upper():
        if not 'A' <= char <= 'Z':
            raise ValueError(f'非法列字母: {letter}')
        value = value * 26 + (ord(char) - 64)

    if value < 1:
        raise ValueError(f'非法列字母: {letter}')
    return value


def build_cell_range(
    start_row: int,
    row_count: int,
    column_count: int,
    start_column: int = 1,
) -> str:
    """
    构造单元格范围（不含子表前缀）

    :param start_row: 起始行号（1-based）
    :param row_count: 行数
    :param column_count: 列数
    :param start_column: 起始列序号（1-based）
    :return:
    """
    if start_row < 1:
        raise ValueError(f'起始行号必须大于 0，当前值: {start_row}')
    if row_count < 1 or column_count < 1:
        raise ValueError('行数与列数必须大于 0')

    start_letter = column_index_to_letter(start_column)
    end_letter = column_index_to_letter(start_column + column_count - 1)
    end_row = start_row + row_count - 1
    return f'{start_letter}{start_row}:{end_letter}{end_row}'


def with_sheet(sheet_id: str, cell_range: str) -> str:
    """
    为单元格范围拼接子表前缀

    :param sheet_id: 子表 id
    :param cell_range: 单元格范围，如 A1:F3
    :return:
    """
    return f'{sheet_id}!{cell_range}'


def parse_cell_range(cell_range: str) -> tuple[int, int, int, int]:
    """
    解析矩形单元格范围

    :param cell_range: 形如 A2:G12
    :return: (起始行号, 行数, 列数, 起始列序号)
    """
    text = cell_range.strip().upper().replace('$', '')
    parts = text.split(':')
    if len(parts) != 2:
        raise ValueError(f'非法单元格范围: {cell_range}')

    start_match = _CELL_RE.match(parts[0])
    end_match = _CELL_RE.match(parts[1])
    if not start_match or not end_match:
        raise ValueError(f'非法单元格范围: {cell_range}')

    start_column = column_letter_to_index(start_match.group(1))
    start_row = int(start_match.group(2))
    end_column = column_letter_to_index(end_match.group(1))
    end_row = int(end_match.group(2))

    if end_row < start_row or end_column < start_column:
        raise ValueError(f'非法单元格范围: {cell_range}')

    return start_row, end_row - start_row + 1, end_column - start_column + 1, start_column
