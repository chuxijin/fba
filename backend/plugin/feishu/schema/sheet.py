from typing import Any, Literal

from pydantic import BaseModel, Field

# 边框类型
BorderType = Literal[
    'FULL_BORDER',
    'OUTER_BORDER',
    'INNER_BORDER',
    'HORIZONTAL_BORDER',
    'VERTICAL_BORDER',
    'LEFT_BORDER',
    'RIGHT_BORDER',
    'TOP_BORDER',
    'BOTTOM_BORDER',
    'NONE',
]


class SheetTargetParam(BaseModel):
    """表格定位参数"""

    workbook: str = Field(
        default='',
        description='表格链接或 token，支持 /sheets/ 直链与 /wiki/ 知识库链接，留空使用 FEISHU_SHEET_URL',
    )
    sheet: str | None = Field(default=None, description='子表名称或 sheet_id，留空使用默认子表')


class SheetInfo(BaseModel):
    """子表信息"""

    sheet_id: str = Field(..., description='子表 id')
    title: str = Field(..., description='子表名称')
    index: int = Field(..., description='子表顺序')
    row_count: int = Field(..., description='总行数')
    column_count: int = Field(..., description='总列数')
    hidden: bool = Field(default=False, description='是否隐藏')


class SheetWriteParam(SheetTargetParam):
    """指定范围写入参数"""

    cell_range: str = Field(..., min_length=1, description='A1 范围，如 A1:F3，不含子表前缀')
    values: list[list[Any]] = Field(..., min_length=1, description='二维数据，每个元素是一行')


class SheetAppendParam(SheetTargetParam):
    """追加参数"""

    rows: list[list[Any]] = Field(..., min_length=1, description='二维数据，每个元素是一行')
    header_rows: int = Field(default=1, ge=0, description='表头行数，追加时会跳过这些行')


class SheetBatchAppendParam(BaseModel):
    """批量追加参数（同一工作簿内的多个子表会合并为一次请求）"""

    jobs: list[SheetAppendParam] = Field(..., min_length=1, description='追加任务列表')


class SheetInsertRowsParam(SheetTargetParam):
    """插入行参数"""

    position: int = Field(..., ge=1, description='插入位置（1-based 行号），新行插入到该行之前')
    count: int = Field(..., ge=1, description='插入行数')
    inherit_style: Literal['before', 'after', 'none'] = Field(default='after', description='新行样式继承来源')


class SheetStyle(BaseModel):
    """单元格样式"""

    bold: bool | None = Field(default=None, description='是否加粗')
    italic: bool | None = Field(default=None, description='是否斜体')
    font_size: int | None = Field(default=None, ge=9, le=36, description='字号 9~36')
    font_color: str | None = Field(default=None, description='字体颜色，如 #FFFFFF')
    background_color: str | None = Field(default=None, description='背景色，如 #4472C4')
    horizontal_alignment: Literal['left', 'center', 'right'] | None = Field(default=None, description='水平对齐')
    vertical_alignment: Literal['top', 'middle', 'bottom'] | None = Field(default=None, description='垂直对齐')
    border_type: BorderType | None = Field(default=None, description='边框类型')
    border_color: str | None = Field(default=None, description='边框颜色，如 #B7C9D9')


class SheetStyleParam(SheetTargetParam):
    """设置样式参数"""

    cell_range: str = Field(..., min_length=1, description='A1 范围，如 A1:F1，不含子表前缀')
    style: SheetStyle = Field(..., description='样式配置')


class SheetDropdownParam(SheetTargetParam):
    """设置下拉列表参数"""

    cell_range: str = Field(..., min_length=1, description='A1 范围，如 E2:E1000，不含子表前缀')
    options: list[str] = Field(..., min_length=1, description='下拉选项，不能包含英文逗号')
    multiple: bool = Field(default=False, description='是否允许多选')
    highlight: bool = Field(default=True, description='是否开启选项胶囊高亮')
    colors: list[str] | None = Field(default=None, description='选项配色，数量需与选项数量一致')


class SheetResizeParam(SheetTargetParam):
    """调整行列尺寸参数"""

    dimension: Literal['rows', 'columns'] = Field(default='columns', description='rows 行高 / columns 列宽')
    start: int = Field(default=1, ge=1, description='起始序号（1-based，含）')
    end: int = Field(default=1, ge=1, description='结束序号（1-based，含）')
    size: int = Field(default=100, ge=1, description='像素值')


class SheetUpdateResult(BaseModel):
    """单元格更新结果"""

    revision: int = Field(default=0, description='文档版本号')
    updated_range: str = Field(default='', description='实际更新范围')
    updated_rows: int = Field(default=0, description='更新行数')
    updated_columns: int = Field(default=0, description='更新列数')
    updated_cells: int = Field(default=0, description='更新单元格数')

    @classmethod
    def from_updates(cls, updates: dict[str, Any]) -> 'SheetUpdateResult':
        """
        由飞书返回的 updates 构造

        :param updates: 飞书 updates 字段
        :return:
        """
        return cls(
            revision=int(updates.get('revision') or 0),
            updated_range=str(updates.get('updatedRange') or ''),
            updated_rows=int(updates.get('updatedRows') or 0),
            updated_columns=int(updates.get('updatedColumns') or 0),
            updated_cells=int(updates.get('updatedCells') or 0),
        )


class SheetAppendResult(BaseModel):
    """追加结果"""

    sheet_id: str = Field(..., description='子表 id')
    range: str = Field(..., description='实际写入范围')
    updates: SheetUpdateResult = Field(..., description='更新结果')

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> 'SheetAppendResult':
        """
        由服务层返回结果构造

        :param raw: 服务层返回结果
        :return:
        """
        return cls(
            sheet_id=str(raw.get('sheet_id') or ''),
            range=str(raw.get('range') or ''),
            updates=SheetUpdateResult.from_updates(raw.get('updates') or {}),
        )


class SheetBatchAppendResult(BaseModel):
    """批量追加结果"""

    workbook_token: str = Field(..., description='表格 token')
    ranges: list[str] = Field(default_factory=list, description='各子表实际写入范围')
    revision: int = Field(default=0, description='文档版本号')


class SheetDropdownInfo(BaseModel):
    """下拉列表配置"""

    ranges: list[str] = Field(default_factory=list, description='生效范围')
    options: list[str] = Field(default_factory=list, description='选项列表')
    multiple: bool = Field(default=False, description='是否多选')
    highlight: bool = Field(default=False, description='是否开启选项高亮')

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> 'SheetDropdownInfo':
        """
        由飞书返回的 dataValidation 构造

        :param raw: 飞书 dataValidation
        :return:
        """
        options = raw.get('options') or {}
        return cls(
            ranges=[str(item) for item in raw.get('ranges') or []],
            options=[str(item) for item in raw.get('conditionValues') or []],
            multiple=bool(options.get('multipleValues')),
            highlight=bool(options.get('highlightValidData')),
        )
