# -*- coding: utf-8 -*-
"""
基础计算与资料分析专项练习本 (basic_calculation) 官方母模板生成脚本
定位：公考行测基础速算（纯双列算式）、资料分析专项实战（4列数据盒）、资料分析分数比大小（2列数据盒）、以及多题型组合卷
设计原则：
1. Single Source of Truth（单一母模板自适应所有形态）
2. 统一的高级质感：深青蓝强调色 (#1F4E79)、浅灰细线网格 (#E5E7EB)、清爽交替底色
3. 标准 A4 版心（210mm x 297mm，18mm 边距，174mm 内容宽）
4. 顶部 5 格自律打卡条（带【练习日期：____月____日】严格单行 + 单元格绝对上下垂直居中）
5. 纯净算式（无末尾方括号）与纯净数据盒（大面积自然演算留白，文字绝对上下垂直居中）
6. 2 列宽版分数大小比较实战数据盒（支持上下竖立分数真公式与填空括号）
7. 卷末统一 5 列顿号答案速查表（如 1、78.0 或 1、>，彻底消除小数点混淆）
"""

from pathlib import Path
import docx
from docx.shared import Mm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn


def create_basic_calculation_template():
    target_dir = Path(__file__).resolve().parents[1] / "templates" / "basic_calculation" / "1.0.0"
    target_dir.mkdir(parents=True, exist_ok=True)
    docx_path = target_dir / "template.docx"

    doc = docx.Document()

    def set_font(run, east_asia="仿宋", ascii_font="Times New Roman", size_pt=10.5, bold=False, color_rgb=None):
        run.font.name = ascii_font
        if size_pt:
            run.font.size = Pt(size_pt)
        run.font.bold = bold
        if color_rgb:
            run.font.color.rgb = color_rgb
        rPr = run._r.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = parse_xml(f'<w:rFonts {nsdecls("w")} w:ascii="{ascii_font}" w:eastAsia="{east_asia}" w:hAnsi="{ascii_font}" w:cs="{east_asia}"/>')
            rPr.append(rFonts)
        else:
            rFonts.set(qn("w:eastAsia"), east_asia)
            rFonts.set(qn("w:ascii"), ascii_font)
            rFonts.set(qn("w:hAnsi"), ascii_font)
            rFonts.set(qn("w:cs"), east_asia)

    def set_cell_vcenter(cell):
        """设置单元格内容绝对垂直居中"""
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        tcPr = cell._tc.get_or_add_tcPr()
        # 移除已有的 vAlign 避免重复
        for child in list(tcPr):
            if child.tag.endswith("vAlign"):
                tcPr.remove(child)
        tcPr.append(parse_xml(f'<w:vAlign {nsdecls("w")} w:val="center"/>'))

    def set_row_cant_split(row):
        """禁止表格行在分页时被横向切断"""
        trPr = row._tr.get_or_add_trPr()
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

    def set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="E5E7EB", sz="4"):
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>\n'
            f'  <w:top w:val="{top}" w:sz="{sz}" w:space="0" w:color="{color}"/>\n'
            f'  <w:left w:val="{left}" w:sz="{sz}" w:space="0" w:color="{color}"/>\n'
            f'  <w:bottom w:val="{bottom}" w:sz="{sz}" w:space="0" w:color="{color}"/>\n'
            f'  <w:right w:val="{right}" w:sz="{sz}" w:space="0" w:color="{color}"/>\n'
            f'</w:tcBorders>'
        )
        tcPr.append(borders)

    def set_table_borders_none(table):
        tblPr = table._tbl.tblPr
        borders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>\n'
            f'  <w:top w:val="none"/>\n'
            f'  <w:left w:val="none"/>\n'
            f'  <w:bottom w:val="none"/>\n'
            f'  <w:right w:val="none"/>\n'
            f'  <w:insideH w:val="none"/>\n'
            f'  <w:insideV w:val="none"/>\n'
            f'</w:tblBorders>'
        )
        tblPr.append(borders)

    def set_cell_margins(cell, top=2, bottom=2, left=4, right=4):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(
            f'<w:tcMar {nsdecls("w")}>\n'
            f'  <w:top w:w="{int(top * 20)}" w:type="dxa"/>\n'
            f'  <w:bottom w:w="{int(bottom * 20)}" w:type="dxa"/>\n'
            f'  <w:left w:w="{int(left * 20)}" w:type="dxa"/>\n'
            f'  <w:right w:w="{int(right * 20)}" w:type="dxa"/>\n'
            f'</w:tcMar>'
        )
        tcPr.append(tcMar)

    def set_cell_shading(cell, color="F8FAFC"):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
        tcPr.append(shd)

    # 页面版心尺寸：标准 A4 (210mm x 297mm, 边距 18mm)
    PAGE_WIDTH = Mm(210)
    PAGE_HEIGHT = Mm(297)
    MARGIN = Mm(18)
    CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2  # 174mm

    sec = doc.sections[0]
    sec.page_width = PAGE_WIDTH
    sec.page_height = PAGE_HEIGHT
    sec.top_margin = MARGIN
    sec.bottom_margin = MARGIN
    sec.left_margin = MARGIN
    sec.right_margin = MARGIN

    # 原生动态页脚：第 1 页 共 2 页
    fp = sec.footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pPr = fp._p.get_or_add_pPr()
    pPr.append(parse_xml(f'<w:jc {nsdecls("w")} w:val="center"/>'))
    r1 = parse_xml(f'<w:r {nsdecls("w")}><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">第 </w:t></w:r>')
    fld1 = parse_xml(f'<w:fldSimple {nsdecls("w")} w:instr="PAGE"><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>')
    r2 = parse_xml(f'<w:r {nsdecls("w")}><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve"> 页  共 </w:t></w:r>')
    fld2 = parse_xml(f'<w:fldSimple {nsdecls("w")} w:instr="NUMPAGES"><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>')
    r3 = parse_xml(f'<w:r {nsdecls("w")}><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr><w:t> 页</w:t></w:r>')
    fp._p.append(r1)
    fp._p.append(fld1)
    fp._p.append(r2)
    fp._p.append(fld2)
    fp._p.append(r3)

    # 1. 顶部大标题
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(4)
    p_title.paragraph_format.space_after = Pt(2)
    r_title = p_title.add_run("{{ book.title if book.title else '基础计算与速算专项练习' }}")
    set_font(r_title, east_asia="黑体", size_pt=20, bold=True, color_rgb=RGBColor(0x1F, 0x29, 0x37))

    # 2. 副标题
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(6)
    r_sub = p_sub.add_run("{{ book.subtitle if book.subtitle else '资料分析极速直除 · 核心数字敏感度强化' }}")
    set_font(r_sub, east_asia="仿宋", size_pt=10.0, color_rgb=RGBColor(0x6B, 0x72, 0x80))

    # 3. 顶部 5 格自律打卡条（严格单行 + 单元格上下绝对居中）
    header_table = doc.add_table(rows=1, cols=5)
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders_none(header_table)
    
    # 强制固定列宽布局
    tblPr = header_table._tbl.tblPr
    tblPr.append(parse_xml(f'<w:tblLayout {nsdecls("w")} w:type="fixed"/>'))

    h_col_widths_mm = [40, 28, 38, 34, 34]
    h_texts = [
        "练习日期：____月____日",
        "题量：共 {{ paper.question_count }} 题",
        "建议用时：{{ paper.suggested_time if paper.suggested_time else '10' }} 分钟",
        "实际用时：_____ 分",
        "得分/正确率：_____",
    ]
    for c_idx, cell in enumerate(header_table.rows[0].cells):
        w_mm = h_col_widths_mm[c_idx]
        w_dxa = int(w_mm * 56.7)
        cell.width = Mm(w_mm)
        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{w_dxa}" w:type="dxa"/>'))
        tcPr.append(parse_xml(f'<w:noWrap {nsdecls("w")}/>'))

        set_cell_vcenter(cell)
        set_cell_margins(cell, top=2, bottom=2, left=2, right=2)
        set_cell_shading(cell, color="F3F4F6")
        set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="E5E7EB", sz="4")
        cp = cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_before = Pt(1)
        cp.paragraph_format.space_after = Pt(1)
        cr = cp.add_run(h_texts[c_idx])
        set_font(cr, east_asia="仿宋", size_pt=9.0, bold=True, color_rgb=RGBColor(0x37, 0x41, 0x51))

    # 分割微留白
    p_gap = doc.add_paragraph()
    p_gap.paragraph_format.space_before = Pt(2)
    p_gap.paragraph_format.space_after = Pt(0)

    # 4. 循环各 Section
    doc.add_paragraph("{% for sec in paper.sections %}")
    doc.add_paragraph("{% if sec.title %}")
    p_sec_title = doc.add_paragraph()
    p_sec_title.paragraph_format.space_before = Pt(8)
    p_sec_title.paragraph_format.space_after = Pt(4)
    p_sec_title.paragraph_format.keep_with_next = True
    r_sec_title = p_sec_title.add_run("◆ {{ sec.title }}")
    set_font(r_sec_title, east_asia="黑体", size_pt=11.5, bold=True, color_rgb=RGBColor(0x1F, 0x4E, 0x79))
    r_sec_hint = p_sec_title.add_run("{% if sec.hint %}（{{ sec.hint }}）{% endif %}")
    set_font(r_sec_hint, east_asia="仿宋", size_pt=9.5, color_rgb=RGBColor(0x6B, 0x72, 0x80))
    doc.add_paragraph("{% endif %}")

    # ── 表格形态 A：双列基础算式网格（纯算式，无末尾方括号，垂直居中） ──
    doc.add_paragraph("{% for row in sec.calc_rows %}")
    calc_table = doc.add_table(rows=1, cols=2)
    calc_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_row_cant_split(calc_table.rows[0])
    calc_col_width = CONTENT_WIDTH / 2
    for c_idx, cell in enumerate(calc_table.rows[0].cells):
        cell.width = calc_col_width
        set_cell_vcenter(cell)
        set_cell_margins(cell, top=4, bottom=4, left=8, right=8)
        set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="E5E7EB", sz="4")
        set_cell_shading(cell, color="FAFBFD" if c_idx == 0 else "FFFFFF")
        cp = cell.paragraphs[0]
        cp.paragraph_format.space_before = Pt(1)
        cp.paragraph_format.space_after = Pt(1)
        cp.paragraph_format.line_spacing = 1.3
        # 题号：Times New Roman 粗体深青蓝
        r_num = cp.add_run(f"{{{{ row.c{c_idx}_number }}}}")
        set_font(r_num, east_asia="Times New Roman", ascii_font="Times New Roman", size_pt=11.5, bold=True, color_rgb=RGBColor(0x1F, 0x4E, 0x79))
        cp.add_run(f"{{% if row.c{c_idx}_number %}}.  {{% endif %}}")
        # 算式：深黑纯净留白
        r_expr = cp.add_run(f"{{{{ row.c{c_idx}_stem }}}}")
        set_font(r_expr, east_asia="Times New Roman", ascii_font="Times New Roman", size_pt=11.5, bold=False, color_rgb=RGBColor(0x11, 0x18, 0x27))
    doc.add_paragraph("{% endfor %}")

    # ── 表格形态 B：4 列实战数据盒（求基期量、求增长量等数据对，垂直居中） ──
    doc.add_paragraph("{% for box in sec.box_blocks %}")
    box_table = doc.add_table(rows=3, cols=5)
    box_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tblPr = box_table._tbl.tblPr
    tblPr.append(parse_xml(f'<w:tblLayout {nsdecls("w")} w:type="fixed"/>'))

    # 列 0 为标签列 (14mm)，列 1~4 为 4 个题目盒 (每列 40mm)
    col_widths_mm = [14, 40, 40, 40, 40]
    col_widths_dxa = [int(w * 56.7) for w in col_widths_mm]

    # Row 0: 题干行 (垂直居中)
    r0 = box_table.rows[0]
    set_row_cant_split(r0)
    r0.height = Mm(8.5)
    r0.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    # 标签格
    c0_lbl = r0.cells[0]
    c0_lbl.width = Mm(col_widths_mm[0])
    tcPr0 = c0_lbl._tc.get_or_add_tcPr()
    tcPr0.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{col_widths_dxa[0]}" w:type="dxa"/>'))
    set_cell_vcenter(c0_lbl)
    set_cell_borders(c0_lbl, color="E5E7EB")
    set_cell_shading(c0_lbl, color="F3F4F6")
    set_cell_margins(c0_lbl, top=2, bottom=2, left=2, right=2)
    p0 = c0_lbl.paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p0.paragraph_format.space_before = Pt(1)
    p0.paragraph_format.space_after = Pt(1)
    p0.paragraph_format.keep_with_next = True
    run0 = p0.add_run("题干")
    set_font(run0, east_asia="宋体", size_pt=9.0, bold=True, color_rgb=RGBColor(0x47, 0x55, 0x69))

    # 4 题题干格 (垂直居中)
    for col_idx in range(1, 5):
        cell = r0.cells[col_idx]
        cell.width = Mm(col_widths_mm[col_idx])
        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{col_widths_dxa[col_idx]}" w:type="dxa"/>'))
        set_cell_vcenter(cell)
        set_cell_borders(cell, color="E5E7EB")
        set_cell_shading(cell, color="FAFBFD")
        set_cell_margins(cell, top=2, bottom=2, left=4, right=4)
        cp = cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_before = Pt(1)
        cp.paragraph_format.space_after = Pt(1)
        cp.paragraph_format.keep_with_next = True
        c_var = f"c{col_idx - 1}"
        # 题号：Times 粗体深青蓝
        r_num = cp.add_run("{% if box." + c_var + "_num %}{{ box." + c_var + "_num }}.  {% endif %}")
        set_font(r_num, east_asia="Times New Roman", ascii_font="Times New Roman", size_pt=10.5, bold=True, color_rgb=RGBColor(0x1F, 0x4E, 0x79))
        # 题干数据对：如 4971  8.8%
        r_stem = cp.add_run("{{ box." + c_var + "_stem }}")
        set_font(r_stem, east_asia="Times New Roman", ascii_font="Times New Roman", size_pt=10.5, bold=True, color_rgb=RGBColor(0x11, 0x18, 0x27))

    # Row 1: 演算留白行（精确定高 18mm，纯净自然演算空间，锁定与答案行连结）
    r1 = box_table.rows[1]
    set_row_cant_split(r1)
    r1.height = Mm(18)
    r1.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    c1_lbl = r1.cells[0]
    c1_lbl.width = Mm(col_widths_mm[0])
    tcPr1 = c1_lbl._tc.get_or_add_tcPr()
    tcPr1.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{col_widths_dxa[0]}" w:type="dxa"/>'))
    set_cell_vcenter(c1_lbl)
    set_cell_borders(c1_lbl, color="E5E7EB")
    set_cell_shading(c1_lbl, color="FAFAFA")
    set_cell_margins(c1_lbl, top=2, bottom=2, left=2, right=2)
    c1_lbl.paragraphs[0].paragraph_format.keep_with_next = True

    for col_idx in range(1, 5):
        cell = r1.cells[col_idx]
        cell.width = Mm(col_widths_mm[col_idx])
        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{col_widths_dxa[col_idx]}" w:type="dxa"/>'))
        set_cell_borders(cell, color="E5E7EB")
        set_cell_margins(cell, top=2, bottom=2, left=4, right=4)
        cell.paragraphs[0].paragraph_format.keep_with_next = True

    # Row 2: 答案作答行 (垂直居中)
    r2 = box_table.rows[2]
    set_row_cant_split(r2)
    r2.height = Mm(7.5)
    r2.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    c2_lbl = r2.cells[0]
    c2_lbl.width = Mm(col_widths_mm[0])
    tcPr2 = c2_lbl._tc.get_or_add_tcPr()
    tcPr2.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{col_widths_dxa[0]}" w:type="dxa"/>'))
    set_cell_vcenter(c2_lbl)
    set_cell_borders(c2_lbl, color="E5E7EB")
    set_cell_shading(c2_lbl, color="F3F4F6")
    set_cell_margins(c2_lbl, top=2, bottom=2, left=2, right=2)
    p2 = c2_lbl.paragraphs[0]
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_before = Pt(1)
    p2.paragraph_format.space_after = Pt(1)
    run2 = p2.add_run("答案")
    set_font(run2, east_asia="宋体", size_pt=9.0, bold=True, color_rgb=RGBColor(0x47, 0x55, 0x69))

    for col_idx in range(1, 5):
        cell = r2.cells[col_idx]
        cell.width = Mm(col_widths_mm[col_idx])
        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{col_widths_dxa[col_idx]}" w:type="dxa"/>'))
        set_cell_vcenter(cell)
        set_cell_borders(cell, color="E5E7EB")
        set_cell_margins(cell, top=2, bottom=2, left=4, right=4)

    doc.add_paragraph("{% endfor %}")

    # ── 表格形态 C：2 列分数比较数据盒（分数大小比较，垂直居中） ──
    doc.add_paragraph("{% for cbox in sec.compare_blocks %}")
    cmp_table = doc.add_table(rows=3, cols=3)
    cmp_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cmp_tblPr = cmp_table._tbl.tblPr
    cmp_tblPr.append(parse_xml(f'<w:tblLayout {nsdecls("w")} w:type="fixed"/>'))

    # 列 0 标签列 14mm，列 1~2 比较盒每列 80mm
    cmp_col_widths_mm = [14, 80, 80]
    cmp_col_widths_dxa = [int(w * 56.7) for w in cmp_col_widths_mm]

    # Row 0: 题干行（分数对，高 10mm，垂直居中，与留白行绑定）
    cr0 = cmp_table.rows[0]
    set_row_cant_split(cr0)
    cr0.height = Mm(10.0)
    cr0.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    # 标签格
    cc0_lbl = cr0.cells[0]
    cc0_lbl.width = Mm(cmp_col_widths_mm[0])
    ctcPr0 = cc0_lbl._tc.get_or_add_tcPr()
    ctcPr0.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{cmp_col_widths_dxa[0]}" w:type="dxa"/>'))
    set_cell_vcenter(cc0_lbl)
    set_cell_borders(cc0_lbl, color="E5E7EB")
    set_cell_shading(cc0_lbl, color="F3F4F6")
    set_cell_margins(cc0_lbl, top=2, bottom=2, left=2, right=2)
    cp0 = cc0_lbl.paragraphs[0]
    cp0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp0.paragraph_format.space_before = Pt(1)
    cp0.paragraph_format.space_after = Pt(1)
    cp0.paragraph_format.keep_with_next = True
    crun0 = cp0.add_run("题干")
    set_font(crun0, east_asia="宋体", size_pt=9.0, bold=True, color_rgb=RGBColor(0x47, 0x55, 0x69))

    # 2 题分数比较题干格
    for col_idx in range(1, 3):
        cell = cr0.cells[col_idx]
        cell.width = Mm(cmp_col_widths_mm[col_idx])
        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{cmp_col_widths_dxa[col_idx]}" w:type="dxa"/>'))
        set_cell_vcenter(cell)
        set_cell_borders(cell, color="E5E7EB")
        set_cell_shading(cell, color="FAFBFD")
        set_cell_margins(cell, top=2, bottom=2, left=6, right=6)
        cp = cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_before = Pt(1)
        cp.paragraph_format.space_after = Pt(1)
        cp.paragraph_format.keep_with_next = True
        c_var = f"c{col_idx - 1}"
        # 题号：Times 粗体深青蓝
        r_num = cp.add_run("{% if cbox." + c_var + "_num %}{{ cbox." + c_var + "_num }}.  {% endif %}")
        set_font(r_num, east_asia="Times New Roman", ascii_font="Times New Roman", size_pt=10.5, bold=True, color_rgb=RGBColor(0x1F, 0x4E, 0x79))
        # 题干表达式（如分数比大小公式）
        r_stem = cp.add_run("{{ cbox." + c_var + "_stem }}")
        set_font(r_stem, east_asia="Times New Roman", ascii_font="Times New Roman", size_pt=11.0, bold=False, color_rgb=RGBColor(0x11, 0x18, 0x27))

    # Row 1: 演算留白行（精确定高 18mm，宽敞直除/差分草稿区，锁定与答案行连结）
    cr1 = cmp_table.rows[1]
    set_row_cant_split(cr1)
    cr1.height = Mm(18)
    cr1.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    cc1_lbl = cr1.cells[0]
    cc1_lbl.width = Mm(cmp_col_widths_mm[0])
    ctcPr1 = cc1_lbl._tc.get_or_add_tcPr()
    ctcPr1.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{cmp_col_widths_dxa[0]}" w:type="dxa"/>'))
    set_cell_vcenter(cc1_lbl)
    set_cell_borders(cc1_lbl, color="E5E7EB")
    set_cell_shading(cc1_lbl, color="FAFAFA")
    set_cell_margins(cc1_lbl, top=2, bottom=2, left=2, right=2)
    cc1_lbl.paragraphs[0].paragraph_format.keep_with_next = True

    for col_idx in range(1, 3):
        cell = cr1.cells[col_idx]
        cell.width = Mm(cmp_col_widths_mm[col_idx])
        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{cmp_col_widths_dxa[col_idx]}" w:type="dxa"/>'))
        set_cell_borders(cell, color="E5E7EB")
        set_cell_margins(cell, top=2, bottom=2, left=6, right=6)
        cell.paragraphs[0].paragraph_format.keep_with_next = True

    # Row 2: 答案作答行 (符号作答，垂直居中)
    cr2 = cmp_table.rows[2]
    set_row_cant_split(cr2)
    cr2.height = Mm(7.5)
    cr2.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    cc2_lbl = cr2.cells[0]
    cc2_lbl.width = Mm(cmp_col_widths_mm[0])
    ctcPr2 = cc2_lbl._tc.get_or_add_tcPr()
    ctcPr2.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{cmp_col_widths_dxa[0]}" w:type="dxa"/>'))
    set_cell_vcenter(cc2_lbl)
    set_cell_borders(cc2_lbl, color="E5E7EB")
    set_cell_shading(cc2_lbl, color="F3F4F6")
    set_cell_margins(cc2_lbl, top=2, bottom=2, left=2, right=2)
    cp2 = cc2_lbl.paragraphs[0]
    cp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp2.paragraph_format.space_before = Pt(1)
    cp2.paragraph_format.space_after = Pt(1)
    crun2 = cp2.add_run("答案")
    set_font(crun2, east_asia="宋体", size_pt=9.0, bold=True, color_rgb=RGBColor(0x47, 0x55, 0x69))

    for col_idx in range(1, 3):
        cell = cr2.cells[col_idx]
        cell.width = Mm(cmp_col_widths_mm[col_idx])
        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{cmp_col_widths_dxa[col_idx]}" w:type="dxa"/>'))
        set_cell_vcenter(cell)
        set_cell_borders(cell, color="E5E7EB")
        set_cell_margins(cell, top=2, bottom=2, left=6, right=6)

    doc.add_paragraph("{% endfor %}")
    doc.add_paragraph("{% endfor %}")

    # 5. 卷末答案速查（统一 5 列顿号卡，垂直居中）
    doc.add_paragraph("{% if paper.show_answers %}")
    p_ans_head = doc.add_paragraph()
    p_ans_head.paragraph_format.space_before = Pt(14)
    p_ans_head.paragraph_format.space_after = Pt(6)
    p_ans_head.paragraph_format.keep_with_next = True
    r_ahead = p_ans_head.add_run("【参考答案速查】")
    set_font(r_ahead, east_asia="黑体", size_pt=11.5, bold=True, color_rgb=RGBColor(0x1F, 0x4E, 0x79))

    # 5 列紧凑答案表格
    doc.add_paragraph("{% for arow in paper.answer_rows %}")
    ans_table = doc.add_table(rows=1, cols=5)
    ans_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_row_cant_split(ans_table.rows[0])
    ans_col_w = CONTENT_WIDTH / 5
    for c_idx, cell in enumerate(ans_table.rows[0].cells):
        cell.width = ans_col_w
        set_cell_vcenter(cell)
        set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="E5E7EB", sz="4")
        set_cell_shading(cell, color="F9FAFB" if c_idx % 2 == 0 else "FFFFFF")
        cp = cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_before = Pt(2)
        cp.paragraph_format.space_after = Pt(2)
        cr = cp.add_run(f"{{{{ arow.c{c_idx} }}}}")
        set_font(cr, east_asia="仿宋", ascii_font="Times New Roman", size_pt=10.0, bold=False, color_rgb=RGBColor(0x11, 0x18, 0x27))
    doc.add_paragraph("{% endfor %}")
    doc.add_paragraph("{% endif %}")

    doc.save(str(docx_path))
    print(f"[✓] 成功重构并生成统一母模板: {docx_path}")


if __name__ == "__main__":
    create_basic_calculation_template()
