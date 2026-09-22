# -*- coding: utf-8 -*-
"""
汉语词汇手册 (hanyu) 专属 Word (.docx) 模板生成脚本
定位：公考言语理解与表达高频成语、常考实词积累与考前背诵手册
核心特性：
1. 标准 B5 (176mm x 250mm) 便携背诵手册版心；
2. 雅致古典封面与词汇量概览；
3. 结构化【词汇精讲卡片】：
   - 词名、拼音、褒贬色彩徽章、考查频次；
   - 详细释义、公考真题经典例句、近义词反义词辨析、典故出处；
4. 原生动态页脚。
"""

from pathlib import Path
import docx
from docx.shared import Mm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn


def create_hanyu_template():
    target_dir = Path(r"backend/plugin/render_book/templates/hanyu/1.0.0")
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

    def set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="D1D5DB", sz="4"):
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

    def set_cell_margins(cell, top=4, bottom=4, left=8, right=8):
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

    def set_cell_shading(cell, color="FAFBFD"):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
        tcPr.append(shd)

    # 页面版心尺寸：标准 B5 (176mm x 250mm, 边距 20mm)
    PAGE_WIDTH = Mm(176)
    PAGE_HEIGHT = Mm(250)
    MARGIN = Mm(20)
    CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2

    # ==================== 第 1 节：封面 ====================
    sec1 = doc.sections[0]
    sec1.page_width = PAGE_WIDTH
    sec1.page_height = PAGE_HEIGHT
    sec1.top_margin = Mm(25)
    sec1.bottom_margin = Mm(20)
    sec1.left_margin = MARGIN
    sec1.right_margin = MARGIN

    # 徽章
    p_badge = doc.add_paragraph()
    p_badge.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_badge.paragraph_format.space_before = Pt(24)
    p_badge.paragraph_format.space_after = Pt(12)
    r_badge = p_badge.add_run("★ 言 语 提 分 · 高 频 积累 ★")
    set_font(r_badge, east_asia="黑体", size_pt=11.0, bold=True, color_rgb=RGBColor(0x01, 0x5D, 0x57))

    # 大标题
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(16)
    p_title.paragraph_format.space_after = Pt(8)
    r_title = p_title.add_run("{{ book.title if book.title else '公考高频汉语词汇手册' }}")
    set_font(r_title, east_asia="黑体", size_pt=24, bold=True, color_rgb=RGBColor(0x11, 0x18, 0x27))

    # 副标题
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(4)
    p_sub.paragraph_format.space_after = Pt(40)
    r_sub = p_sub.add_run("{{ book.subtitle if book.subtitle else '成语深度辨析 · 考点精准释义 · 典型语境例句' }}")
    set_font(r_sub, east_asia="仿宋", size_pt=11.0, color_rgb=RGBColor(0x55, 0x55, 0x55))

    # 封面统计信息栏
    info_table = doc.add_table(rows=3, cols=2)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    info_widths = [CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5]
    info_data = [
        ("收 录 词 汇：共 {{ paper.total_count }} 个", "学 员 姓 名：{{ metadata.nickname if metadata.nickname else '公务员考生' }}"),
        ("所 属 模 块：言语理解与表达", "复 习 进 度：[  ] 初背    [  ] 熟记"),
        ("词 汇 类 型：成语 / 实词辨析", "打 卡 状 态：[  ] 已掌握"),
    ]
    for r_idx, row in enumerate(info_table.rows):
        t0, t1 = info_data[r_idx]
        for c_idx, cell in enumerate(row.cells):
            cell.width = info_widths[c_idx]
            set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="D1D5DB", sz="5")
            set_cell_shading(cell, color="F4F9F8" if r_idx % 2 == 0 else "FFFFFF")
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(10)
            p.paragraph_format.left_indent = Pt(12)
            r = p.add_run(t0 if c_idx == 0 else t1)
            set_font(r, east_asia="仿宋", size_pt=10.5, color_rgb=RGBColor(0x33, 0x33, 0x33))

    p_motto = doc.add_paragraph()
    p_motto.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_motto.paragraph_format.space_before = Pt(90)
    p_motto.paragraph_format.space_after = Pt(12)
    r_motto = p_motto.add_run("“ 积跬步以至千里，积小流以成江海。”")
    set_font(r_motto, east_asia="楷体", size_pt=11.5, color_rgb=RGBColor(0x66, 0x66, 0x66))

    # ==================== 第 2 节：词汇卡片正文 ====================
    sec2 = doc.add_section(docx.enum.section.WD_SECTION.NEW_PAGE)
    sec2.page_width = PAGE_WIDTH
    sec2.page_height = PAGE_HEIGHT
    sec2.top_margin = Mm(20)
    sec2.bottom_margin = Mm(20)
    sec2.left_margin = MARGIN
    sec2.right_margin = MARGIN

    # 动态页脚
    sec2.footer.is_linked_to_previous = False
    fp2 = sec2.footer.paragraphs[0]
    fp2.text = ""
    fp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pPr2 = fp2._p.get_or_add_pPr()
    pPr2.append(parse_xml(f'<w:jc {nsdecls("w")} w:val="center"/>'))
    r1 = parse_xml(f'<w:r {nsdecls("w")}><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">第 </w:t></w:r>')
    fld1 = parse_xml(f'<w:fldSimple {nsdecls("w")} w:instr="PAGE"><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>')
    r2 = parse_xml(f'<w:r {nsdecls("w")}><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve"> 页  共 </w:t></w:r>')
    fld2 = parse_xml(f'<w:fldSimple {nsdecls("w")} w:instr="NUMPAGES"><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>')
    r3 = parse_xml(f'<w:r {nsdecls("w")}><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr><w:t> 页</w:t></w:r>')
    fp2._p.append(r1)
    fp2._p.append(fld1)
    fp2._p.append(r2)
    fp2._p.append(fld2)
    fp2._p.append(r3)

    # 词汇卡片循环
    doc.add_paragraph("{% for w in paper.words %}")

    card = doc.add_table(rows=1, cols=1)
    card.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = card.rows[0].cells[0]
    c.width = CONTENT_WIDTH
    # 设置左侧加粗强调边框（墨绿 3pt），其余三边为细线边框
    set_cell_borders(c, top="single", bottom="single", left="single", right="single", color="B8D6D3", sz="6")
    set_cell_margins(c, top=6, bottom=6, left=10, right=10)
    set_cell_shading(c, color="FAFDFC")

    # 1. 卡片头部：词语名称 + 拼音 + 褒贬 + 频次
    cp_head = c.paragraphs[0]
    cp_head.paragraph_format.space_before = Pt(2)
    cp_head.paragraph_format.space_after = Pt(4)
    cp_head.paragraph_format.line_spacing = 1.25

    r_num = cp_head.add_run("{{ loop.index }}.  ")
    set_font(r_num, east_asia="Times New Roman", ascii_font="Times New Roman", size_pt=12.0, bold=True, color_rgb=RGBColor(0x01, 0x6E, 0x67))

    r_wname = cp_head.add_run("{{ w.name }}")
    set_font(r_wname, east_asia="黑体", size_pt=13.0, bold=True, color_rgb=RGBColor(0x11, 0x18, 0x27))

    cp_head.add_run("{% if w.pinyin %}  ")
    r_py = cp_head.add_run(" [ {{ w.pinyin }} ] ")
    set_font(r_py, east_asia="Times New Roman", ascii_font="Times New Roman", size_pt=10.5, color_rgb=RGBColor(0x01, 0x84, 0x7C))
    cp_head.add_run("{% endif %}")

    cp_head.add_run("{% if w.baobian %}  ")
    r_bb = cp_head.add_run("【{{ w.baobian }}】")
    set_font(r_bb, east_asia="黑体", size_pt=9.5, bold=True, color_rgb=RGBColor(0x27, 0xAE, 0x60))
    cp_head.add_run("{% endif %}")

    cp_head.add_run("{% if w.frequency %}  ")
    r_freq = cp_head.add_run("★ 考查 {{ w.frequency }} 次")
    set_font(r_freq, east_asia="仿宋", size_pt=9.0, color_rgb=RGBColor(0xD9, 0x77, 0x06))
    cp_head.add_run("{% endif %}")

    # 2. 释义段落
    cp_def = c.add_paragraph()
    cp_def.paragraph_format.space_before = Pt(2)
    cp_def.paragraph_format.space_after = Pt(2)
    cp_def.paragraph_format.line_spacing = 1.25
    r_deflbl = cp_def.add_run("【释义】")
    set_font(r_deflbl, east_asia="黑体", size_pt=10.0, bold=True, color_rgb=RGBColor(0x1F, 0x29, 0x37))
    r_deftxt = cp_def.add_run("{{ w.definition }}")
    set_font(r_deftxt, east_asia="仿宋", size_pt=10.5, color_rgb=RGBColor(0x37, 0x41, 0x51))

    # 3. 经典例句段落
    doc.add_paragraph("{% if w.liju %}")
    cp_liju = c.add_paragraph()
    cp_liju.paragraph_format.space_before = Pt(2)
    cp_liju.paragraph_format.space_after = Pt(2)
    cp_liju.paragraph_format.line_spacing = 1.25
    r_ljlbl = cp_liju.add_run("【例句】")
    set_font(r_ljlbl, east_asia="黑体", size_pt=10.0, bold=True, color_rgb=RGBColor(0x01, 0x5D, 0x57))
    r_ljtxt = cp_liju.add_run("{{ w.liju }}")
    set_font(r_ljtxt, east_asia="楷体", size_pt=10.0, color_rgb=RGBColor(0x4B, 0x55, 0x63))
    doc.add_paragraph("{% endif %}")

    # 4. 近义词 / 反义词段落
    doc.add_paragraph("{% if w.synonyms or w.antonym %}")
    cp_syn = c.add_paragraph()
    cp_syn.paragraph_format.space_before = Pt(2)
    cp_syn.paragraph_format.space_after = Pt(2)
    cp_syn.paragraph_format.line_spacing = 1.25
    cp_syn.add_run("{% if w.synonyms %}")
    r_slbl = cp_syn.add_run("【近义】")
    set_font(r_slbl, east_asia="黑体", size_pt=10.0, bold=True, color_rgb=RGBColor(0x1F, 0x29, 0x37))
    r_stxt = cp_syn.add_run("{{ w.synonyms }}   ")
    set_font(r_stxt, east_asia="仿宋", size_pt=10.0, color_rgb=RGBColor(0x4B, 0x55, 0x63))
    cp_syn.add_run("{% endif %}")
    cp_syn.add_run("{% if w.antonym %}")
    r_albl = cp_syn.add_run("【反义】")
    set_font(r_albl, east_asia="黑体", size_pt=10.0, bold=True, color_rgb=RGBColor(0x1F, 0x29, 0x37))
    r_atxt = cp_syn.add_run("{{ w.antonym }}")
    set_font(r_atxt, east_asia="仿宋", size_pt=10.0, color_rgb=RGBColor(0x4B, 0x55, 0x63))
    cp_syn.add_run("{% endif %}")
    doc.add_paragraph("{% endif %}")

    # 5. 出处段落
    doc.add_paragraph("{% if w.chuchu %}")
    cp_cc = c.add_paragraph()
    cp_cc.paragraph_format.space_before = Pt(2)
    cp_cc.paragraph_format.space_after = Pt(2)
    cp_cc.paragraph_format.line_spacing = 1.25
    r_cclbl = cp_cc.add_run("【出处】")
    set_font(r_cclbl, east_asia="黑体", size_pt=9.5, bold=True, color_rgb=RGBColor(0x6B, 0x72, 0x80))
    r_cctxt = cp_cc.add_run("{{ w.chuchu }}")
    set_font(r_cctxt, east_asia="仿宋", size_pt=9.5, color_rgb=RGBColor(0x6B, 0x72, 0x80))
    doc.add_paragraph("{% endif %}")

    # 卡片间自然呼吸间隔
    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(2)
    p_sp.paragraph_format.space_after = Pt(4)

    doc.add_paragraph("{% endfor %}")

    doc.save(str(docx_path))
    print(f"[✓] 成功创建汉语词汇手册专属模板: {docx_path}")


if __name__ == "__main__":
    create_hanyu_template()
