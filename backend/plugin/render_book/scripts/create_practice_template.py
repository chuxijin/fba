#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成公考刷题本专属 Word 模板
优化项：
1. 封面去掉复杂的复盘错题表格，标题、基本信息表、名言警句均匀分布在 B5 页面上；
2. 做题区单栏排版，题号后紧跟真题来源标签，如：1. 【26·国考】 题干……；
3. 答案与解析保持简洁统一。
"""

from pathlib import Path
import docx
from docx.shared import Pt, RGBColor, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import qn, nsdecls

def create_template():
    target_dir = Path(r"backend/plugin/render_book/templates/gongkao_practice/1.0.0")
    target_dir.mkdir(parents=True, exist_ok=True)
    docx_path = target_dir / "template.docx"

    doc = docx.Document()

    # 辅助函数：设置东亚字体与英文字体
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

    # 辅助函数：设置单元格边框
    def set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="C5CAD0", sz="4"):
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

    def set_table_left_indent(table, indent_pt: float):
        tblPr = table._tbl.tblPr
        tblInd = parse_xml(
            f'<w:tblInd {nsdecls("w")} w:w="{int(indent_pt * 20)}" w:type="dxa"/>'
        )
        tblPr.append(tblInd)

    def set_cell_margins(cell, top=2, bottom=2, left=0, right=8):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(
            f'<w:tcMar {nsdecls("w")}>\n'
            f'  <w:top w:w="{int(top * 20)}" w:type="dxa"/>\n'
            f'  <w:left w:w="{int(left * 20)}" w:type="dxa"/>\n'
            f'  <w:bottom w:w="{int(bottom * 20)}" w:type="dxa"/>\n'
            f'  <w:right w:w="{int(right * 20)}" w:type="dxa"/>\n'
            f'</w:tcMar>'
        )
        tcPr.append(tcMar)

    def set_cell_shading(cell, color="F8FAFC"):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
        tcPr.append(shd)

    # 考卷排版核心常量（与国考试卷保持 100% 绝对一致）
    HANG_INDENT_PT = 24.0  # 约 2 字符基准悬挂缩进
    PAGE_WIDTH = Mm(182)
    PAGE_HEIGHT = Mm(257)
    MARGIN_LR = Mm(20)
    CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LR * 2
    OPT_TABLE_WIDTH = CONTENT_WIDTH - Pt(HANG_INDENT_PT)

    # ==================== 第 1 节：封面（B5 单栏，标题/表格/名言均匀分布） ====================
    sec1 = doc.sections[0]
    sec1.page_width = PAGE_WIDTH
    sec1.page_height = PAGE_HEIGHT
    sec1.top_margin = Mm(25)
    sec1.bottom_margin = Mm(25)
    sec1.left_margin = MARGIN_LR
    sec1.right_margin = MARGIN_LR

    # 封面大标题
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(40)
    p_title.paragraph_format.space_after = Pt(12)
    r_title = p_title.add_run("行 测 专 项 刷 题 本")
    set_font(r_title, east_asia="黑体", size_pt=26, bold=True)

    # 封面副标题（模块考点名称）
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(50)
    r_sub = p_sub.add_run("{{ paper.module_title }}")
    set_font(r_sub, east_asia="楷体", size_pt=14, bold=False, color_rgb=RGBColor(0x33, 0x33, 0x33))

    # 基本信息卡片表格（居中对称，段落留白舒适）
    info_table = doc.add_table(rows=3, cols=2)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    info_table.autofit = False
    info_widths = [Mm(71), Mm(71)]

    info_data = [
        ("学 员 昵 称：{{ user.nickname }}", "刷 题 题 量：共 {{ paper.question_count }} 题"),
        ("生 成 时 间：{{ user.generated_at }}", "建 议 用 时：{{ paper.suggested_time }} 分钟"),
        ("所 属 题 库：{{ paper.bank_name }}", "考 点 范 围：{{ paper.kp_names }}"),
    ]

    for r_idx, row in enumerate(info_table.rows):
        t0, t1 = info_data[r_idx]
        for c_idx, cell in enumerate(row.cells):
            cell.width = info_widths[c_idx]
            set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="C5CAD0", sz="5")
            set_cell_shading(cell, color="F8FAFC" if r_idx % 2 == 0 else "FFFFFF")
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(10)
            p.paragraph_format.left_indent = Pt(12)
            text = t0 if c_idx == 0 else t1
            r = p.add_run(text)
            set_font(r, east_asia="仿宋", size_pt=10.5, color_rgb=RGBColor(0x33, 0x33, 0x33))

    # 底部名言警句（自然推向下方，版面三等分均匀协调）
    p_motto = doc.add_paragraph()
    p_motto.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_motto.paragraph_format.space_before = Pt(100)
    p_motto.paragraph_format.space_after = Pt(12)
    r_motto = p_motto.add_run("“ 日拱一卒，功不唐捐；行则将至，做则必成。”")
    set_font(r_motto, east_asia="楷体", size_pt=11.5, color_rgb=RGBColor(0x66, 0x66, 0x66))

    # ==================== 第 2 节：做题正文（严格国考规范：悬挂缩进 + Tab 制表符 + 表格左缩进） ====================
    sec2 = doc.add_section(docx.enum.section.WD_SECTION.NEW_PAGE)
    sec2.page_width = PAGE_WIDTH
    sec2.page_height = PAGE_HEIGHT
    sec2.top_margin = Mm(20)
    sec2.bottom_margin = Mm(20)
    sec2.left_margin = MARGIN_LR
    sec2.right_margin = MARGIN_LR

    # 单栏
    sectPr2 = sec2._sectPr
    cols_xml2 = parse_xml(f'<w:cols {nsdecls("w")} w:num="1"/>')
    sectPr2.append(cols_xml2)
    sectPr2.append(parse_xml(f'<w:pgNumType {nsdecls("w")} w:start="1"/>'))

    # 正文原生动态页脚
    sec2.footer.is_linked_to_previous = False
    fp2 = sec2.footer.paragraphs[0]
    fp2.text = ""
    fp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp2.paragraph_format.space_before = Pt(6)
    fp2.paragraph_format.space_after = Pt(0)
    pPr2 = fp2._p.get_or_add_pPr()
    pPr2.append(parse_xml(f'<w:jc {nsdecls("w")} w:val="center"/>'))

    r1 = parse_xml(f'<w:r {nsdecls("w")}><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr><w:t xml:space="preserve">第 </w:t></w:r>')
    fld1 = parse_xml(f'<w:fldSimple {nsdecls("w")} w:instr="PAGE"><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>')
    r2 = parse_xml(f'<w:r {nsdecls("w")}><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr><w:t xml:space="preserve"> 页  共 </w:t></w:r>')
    fld2 = parse_xml(f'<w:fldSimple {nsdecls("w")} w:instr="NUMPAGES"><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>')
    r3 = parse_xml(f'<w:r {nsdecls("w")}><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr><w:t> 页</w:t></w:r>')
    fp2._p.append(r1)
    fp2._p.append(fld1)
    fp2._p.append(r2)
    fp2._p.append(fld2)
    fp2._p.append(r3)

    # 题目循环开始
    p_q_loop = doc.add_paragraph()
    p_q_loop.add_run("{% for q in paper.all_questions %}")

    # 1. 材料题引导语：黑体 10.5pt，左缩进 24pt（与下方题干首字垂直严格对齐）
    p_mat_intro = doc.add_paragraph()
    p_mat_intro.paragraph_format.space_before = Pt(6)
    p_mat_intro.paragraph_format.space_after = Pt(3)
    p_mat_intro.paragraph_format.left_indent = Pt(HANG_INDENT_PT)
    p_mat_intro.paragraph_format.line_spacing = 1.2
    p_mat_intro.paragraph_format.keep_with_next = True
    r_mat_intro = p_mat_intro.add_run("{% if q.material and q.material.intro %}{{ q.material.intro }}{% endif %}")
    set_font(r_mat_intro, east_asia="黑体", size_pt=10.5, bold=False)

    # 2. 材料题正文：仿宋 12.0pt，顶格通栏，首行缩进 2 字符 (24pt)；图片块居中展示
    doc.add_paragraph("{% if q.material and q.material.blocks %}{% for blk in q.material.blocks %}")
    doc.add_paragraph("{% if not blk.is_img %}")
    p_mat_line = doc.add_paragraph()
    p_mat_line.paragraph_format.space_before = Pt(1)
    p_mat_line.paragraph_format.space_after = Pt(2)
    p_mat_line.paragraph_format.left_indent = Pt(0)
    p_mat_line.paragraph_format.first_line_indent = Pt(HANG_INDENT_PT)
    p_mat_line.paragraph_format.line_spacing = 1.25
    p_mat_line.paragraph_format.keep_with_next = True
    r_mat_line = p_mat_line.add_run("{{ blk.text }}")
    set_font(r_mat_line, east_asia="仿宋", size_pt=12.0)
    doc.add_paragraph("{% else %}")
    p_mat_img = doc.add_paragraph()
    p_mat_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_mat_img.paragraph_format.space_before = Pt(4)
    p_mat_img.paragraph_format.space_after = Pt(4)
    p_mat_img.paragraph_format.keep_with_next = True
    p_mat_img.add_run("{{ blk.img }}")
    doc.add_paragraph("{% endif %}{% endfor %}{% elif q.material and q.material.lines %}{% for line in q.material.lines %}")
    p_mat_fb = doc.add_paragraph()
    p_mat_fb.paragraph_format.space_before = Pt(1)
    p_mat_fb.paragraph_format.space_after = Pt(2)
    p_mat_fb.paragraph_format.left_indent = Pt(0)
    p_mat_fb.paragraph_format.first_line_indent = Pt(HANG_INDENT_PT)
    p_mat_fb.paragraph_format.line_spacing = 1.25
    p_mat_fb.paragraph_format.keep_with_next = True
    r_mat_fb = p_mat_fb.add_run("{{ line }}")
    set_font(r_mat_fb, east_asia="仿宋", size_pt=12.0)
    doc.add_paragraph("{% endfor %}{% endif %}")

    # 3. 题干：国考标准悬挂缩进 (left_indent=24pt, first_line=-24pt, Tab=24pt)
    # 题号顶格左边缘，制表符跳转到 24pt，来源标签与题干正文首字在 24pt 垂线上，换行对齐 24pt
    p_stem = doc.add_paragraph()
    p_stem.paragraph_format.space_before = Pt(5)
    p_stem.paragraph_format.space_after = Pt(2)
    p_stem.paragraph_format.line_spacing = 1.25
    p_stem.paragraph_format.keep_with_next = True
    p_stem.paragraph_format.left_indent = Pt(HANG_INDENT_PT)
    p_stem.paragraph_format.first_line_indent = -Pt(HANG_INDENT_PT)
    p_stem.paragraph_format.tab_stops.add_tab_stop(Pt(HANG_INDENT_PT))

    # 序号 + 制表符
    r_no = p_stem.add_run("{{ q.number }}.\t")
    set_font(r_no, east_asia="仿宋", ascii_font="Times New Roman", size_pt=12.0)

    # 来源标签
    r_tag = p_stem.add_run("{% if q.source_tag %}【{{ q.source_tag }}】{% endif %}")
    set_font(r_tag, east_asia="仿宋", ascii_font="Times New Roman", size_pt=12.0)

    # 题干内容与反向设问加粗（官方仿宋 12pt，加粗设问词）
    r_stem_0 = p_stem.add_run("{% for seg in q.stem_segments %}{% if seg.bold %}")
    set_font(r_stem_0, east_asia="仿宋", size_pt=12.0)
    r_stem_bold = p_stem.add_run("{{ seg.text }}")
    set_font(r_stem_bold, east_asia="仿宋", size_pt=12.0, bold=True)
    r_stem_else = p_stem.add_run("{% else %}")
    set_font(r_stem_else, east_asia="仿宋", size_pt=12.0)
    r_stem_normal = p_stem.add_run("{{ seg.text }}")
    set_font(r_stem_normal, east_asia="仿宋", size_pt=12.0, bold=False)
    r_stem_end = p_stem.add_run("{% endif %}{% endfor %}")
    set_font(r_stem_end, east_asia="仿宋", size_pt=12.0)

    # 题干配图（几何图形、图形推理题干图、工程统计表等）
    doc.add_paragraph("{% if q.stem_images %}{% for simg in q.stem_images %}")
    p_simg = doc.add_paragraph()
    p_simg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_simg.paragraph_format.space_before = Pt(3)
    p_simg.paragraph_format.space_after = Pt(4)
    p_simg.paragraph_format.keep_with_next = True
    p_simg.add_run("{{ simg }}")
    doc.add_paragraph("{% endfor %}{% endif %}")

    # 4. 4 列选项表格：严格左对齐，左缩进 24pt 与题干首字垂直对齐
    doc.add_paragraph("{% if q.opt_cols == 4 %}")
    t4 = doc.add_table(rows=1, cols=4)
    t4.alignment = WD_TABLE_ALIGNMENT.LEFT
    set_table_borders_none(t4)
    set_table_left_indent(t4, HANG_INDENT_PT)
    t4.autofit = False
    col_width_4 = OPT_TABLE_WIDTH / 4
    for idx, c in enumerate(t4.rows[0].cells):
        c.width = col_width_4
        set_cell_margins(c, top=2, bottom=2, left=0, right=6)
        cp = c.paragraphs[0]
        cp.paragraph_format.space_before = Pt(0)
        cp.paragraph_format.space_after = Pt(0)
        cp.paragraph_format.line_spacing = 1.15
        # 支持图片选项与文字选项
        cp.add_run(f"{{% if q.opt_{idx}_img %}}")
        c_pre = cp.add_run(f"{{{{ q.opt_{idx}_prefix }}}} ")
        set_font(c_pre, east_asia="仿宋", size_pt=12.0)
        cp.add_run(f"{{{{ q.opt_{idx}_img }}}}")
        cp.add_run(f"{{% else %}}")
        cr = cp.add_run(f"{{{{ q.opt_{idx} }}}}")
        set_font(cr, east_asia="仿宋", size_pt=12.0)
        cp.add_run(f"{{% endif %}}")
    doc.add_paragraph("{% endif %}")

    # 5. 2 列选项表格：严格左对齐，左缩进 24pt 与题干首字垂直对齐
    doc.add_paragraph("{% if q.opt_cols == 2 %}")
    t2 = doc.add_table(rows=2, cols=2)
    t2.alignment = WD_TABLE_ALIGNMENT.LEFT
    set_table_borders_none(t2)
    set_table_left_indent(t2, HANG_INDENT_PT)
    t2.autofit = False
    col_width_2 = OPT_TABLE_WIDTH / 2
    t2_cells = [t2.rows[0].cells[0], t2.rows[0].cells[1], t2.rows[1].cells[0], t2.rows[1].cells[1]]
    for idx, c in enumerate(t2_cells):
        c.width = col_width_2
        set_cell_margins(c, top=2, bottom=2, left=0, right=6)
        cp = c.paragraphs[0]
        cp.paragraph_format.space_before = Pt(0)
        cp.paragraph_format.space_after = Pt(0)
        cp.paragraph_format.line_spacing = 1.15
        # 支持图片选项与文字选项
        cp.add_run(f"{{% if q.opt_{idx}_img %}}")
        c_pre = cp.add_run(f"{{{{ q.opt_{idx}_prefix }}}} ")
        set_font(c_pre, east_asia="仿宋", size_pt=12.0)
        cp.add_run(f"{{{{ q.opt_{idx}_img }}}}")
        cp.add_run(f"{{% else %}}")
        cr = cp.add_run(f"{{{{ q.opt_{idx} }}}}")
        set_font(cr, east_asia="仿宋", size_pt=12.0)
        cp.add_run(f"{{% endif %}}")
    doc.add_paragraph("{% endif %}")

    # 6. 1 列选项：独立段落，严格左缩进 24pt 与题干首字垂直对齐
    doc.add_paragraph("{% if q.opt_cols == 1 %}")
    for i in range(4):
        doc.add_paragraph(f"{{% if q.opt_{i} or q.opt_{i}_img %}}")
        p_opt = doc.add_paragraph()
        p_opt.paragraph_format.space_before = Pt(1)
        p_opt.paragraph_format.space_after = Pt(1)
        p_opt.paragraph_format.left_indent = Pt(HANG_INDENT_PT)
        p_opt.paragraph_format.line_spacing = 1.15
        p_opt.add_run(f"{{% if q.opt_{i}_img %}}")
        p_pre = p_opt.add_run(f"{{{{ q.opt_{i}_prefix }}}} ")
        set_font(p_pre, east_asia="仿宋", size_pt=12.0)
        p_opt.add_run(f"{{{{ q.opt_{i}_img }}}}")
        p_opt.add_run(f"{{% else %}}")
        r_opt = p_opt.add_run(f"{{{{ q.opt_{i} }}}}")
        set_font(r_opt, east_asia="仿宋", size_pt=12.0)
        p_opt.add_run(f"{{% endif %}}")
        doc.add_paragraph("{% endif %}")
    doc.add_paragraph("{% endif %}")

    # 结束题目循环
    doc.add_paragraph("{% endfor %}")

    # ==================== 第 3 节：参考答案与解析（朴素统一风格） ====================
    sec3 = doc.add_section(docx.enum.section.WD_SECTION.NEW_PAGE)
    sec3.page_width = PAGE_WIDTH
    sec3.page_height = PAGE_HEIGHT
    sec3.top_margin = Mm(20)
    sec3.bottom_margin = Mm(20)
    sec3.left_margin = MARGIN_LR
    sec3.right_margin = MARGIN_LR

    # 答案速查大标题
    p_ans_head = doc.add_paragraph()
    p_ans_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ans_head.paragraph_format.space_before = Pt(14)
    p_ans_head.paragraph_format.space_after = Pt(10)
    r_ans_head = p_ans_head.add_run("参考答案速查")
    set_font(r_ans_head, east_asia="黑体", size_pt=14, bold=True)

    # 5 列答案速查表
    doc.add_paragraph("{% for a_row in paper.answer_rows %}")
    ans_table = doc.add_table(rows=1, cols=5)
    ans_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c_idx, cell in enumerate(ans_table.rows[0].cells):
        set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="C0C0C0", sz="4")
        set_cell_shading(cell, color="F8FAFC" if c_idx % 2 == 0 else "FFFFFF")
        cp = cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_before = Pt(4)
        cp.paragraph_format.space_after = Pt(4)
        cr = cp.add_run(f"{{{{ a_row.c{c_idx} }}}}")
        set_font(cr, east_asia="仿宋", size_pt=10.5, bold=False)
    doc.add_paragraph("{% endfor %}")

    # 逐题解析大标题
    p_ana_head = doc.add_paragraph()
    p_ana_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ana_head.paragraph_format.space_before = Pt(20)
    p_ana_head.paragraph_format.space_after = Pt(10)
    r_ana_head = p_ana_head.add_run("参考答案与解析")
    set_font(r_ana_head, east_asia="黑体", size_pt=14, bold=True)

    # 逐题解析循环（统一规范：题号+答案置顶，解析整体悬挂左缩进 21pt 对齐）
    doc.add_paragraph("{% for q in paper.all_questions %}")

    p_item_ans = doc.add_paragraph()
    p_item_ans.paragraph_format.space_before = Pt(7)
    p_item_ans.paragraph_format.space_after = Pt(2)
    p_item_ans.paragraph_format.left_indent = Pt(0)
    p_item_ans.paragraph_format.keep_with_next = True
    r_no = p_item_ans.add_run("{{ q.number }}. 【答案】{{ q.answer_text }}")
    set_font(r_no, east_asia="黑体", size_pt=10.5, bold=True)

    p_item_ana = doc.add_paragraph()
    p_item_ana.paragraph_format.space_before = Pt(1)
    p_item_ana.paragraph_format.space_after = Pt(5)
    p_item_ana.paragraph_format.line_spacing = 1.25
    p_item_ana.paragraph_format.left_indent = Pt(21)
    p_item_ana.paragraph_format.first_line_indent = Pt(0)
    r_ana_lbl = p_item_ana.add_run("【解析】")
    set_font(r_ana_lbl, east_asia="黑体", size_pt=10.5, bold=True)
    r_ana_txt = p_item_ana.add_run("{{ q.analysis_text }}")
    set_font(r_ana_txt, east_asia="仿宋", size_pt=10.5, bold=False)

    # 解析配图（公式推导图、图解步骤等）
    doc.add_paragraph("{% if q.analysis_images %}{% for aimg in q.analysis_images %}")
    p_aimg = doc.add_paragraph()
    p_aimg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_aimg.paragraph_format.space_before = Pt(2)
    p_aimg.paragraph_format.space_after = Pt(4)
    p_aimg.paragraph_format.keep_with_next = True
    p_aimg.add_run("{{ aimg }}")
    doc.add_paragraph("{% endfor %}{% endif %}")

    doc.add_paragraph("{% endfor %}")

    doc.save(str(docx_path))
    print(f"[✓] 成功创建公考刷题本规范单栏模板: {docx_path}")

if __name__ == "__main__":
    create_template()
