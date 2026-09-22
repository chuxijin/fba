#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国考考场真卷两页全真封面 + 试卷正文全流程生成器
- 第 1 页：正面试卷封面
  * 左侧密封线：垂直装订虚线 + 准考证号/姓名竖排填涂栏
  * 中间卷头：年度大赛标题 + 行政职业能力测验（超大黑体） + 类别（行政执法类）
  * 下方：【重要提示】（两名代表验封、雷同卷零分、禁考处罚）
- 第 2 页：注意事项内页
  * 顶部：居中“注 意 事 项”大标题
  * 正文：考场六大注意事项公文段落
  * 底部：带虚线警示黑框的“停！请不要往下翻！听候监考老师的指示。否则，会影响你的成绩”
- 第 3 页起：正式试卷正文
  * 模块分页 + 双居中 + 悬挂题号 + 选项透明表格绝对对齐 + 零空行
"""
from __future__ import annotations

import re
import sys
import shutil
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL, WD_ROW_HEIGHT_RULE
from docx.enum.section import WD_SECTION_START
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls
from docxtpl import DocxTemplate

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output" / "exam_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_TEMPLATE = OUTPUT_DIR / "国考行测标准题本_模板底稿.docx"
TARGET_PREVIEW_DOCX = OUTPUT_DIR / "国考行测标准题本_全真模考最终版.docx"
TARGET_PREVIEW_PDF = OUTPUT_DIR / "国考行测标准题本_全真模考最终版.pdf"

PLUGIN_TEMPLATE_DIR = BASE_DIR / "plugin" / "render_book" / "templates" / "gongkao_xingce" / "1.0.0"
PLUGIN_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
PLUGIN_TARGET_TEMPLATE = PLUGIN_TEMPLATE_DIR / "template.docx"

HANG_INDENT_PT = 24.0


def apply_official_font(
    run,
    cn_font: str = "仿宋",
    ascii_font: str = "Times New Roman",
    size_pt: float = 12.0,
    bold: bool = False,
    color_rgb: RGBColor | None = None
):
    """底层公文双字体属性绑定"""
    run.font.name = ascii_font
    run.font.size = Pt(size_pt)
    run.bold = bold
    if color_rgb:
        run.font.color.rgb = color_rgb

    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), cn_font)
    rFonts.set(qn('w:ascii'), ascii_font)
    rFonts.set(qn('w:hAnsi'), ascii_font)
    rFonts.set(qn('w:cs'), cn_font)


def set_table_borders_none(table):
    """清除表格边框"""
    tblPr = table._tbl.tblPr
    tblBorders = tblPr.find(qn('w:tblBorders'))
    if tblBorders is not None:
        tblPr.remove(tblBorders)
    new_borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="none"/>\n'
        f'  <w:left w:val="none"/>\n'
        f'  <w:bottom w:val="none"/>\n'
        f'  <w:right w:val="none"/>\n'
        f'  <w:insideH w:val="none"/>\n'
        f'  <w:insideV w:val="none"/>\n'
        f'</w:tblBorders>'
    )
    tblPr.append(new_borders)


def set_table_left_indent(table, indent_pt: float):
    """设置表格左缩进"""
    tblPr = table._tbl.tblPr
    tblInd = tblPr.find(qn('w:tblInd'))
    if tblInd is not None:
        tblPr.remove(tblInd)
    new_tblInd = parse_xml(
        f'<w:tblInd {nsdecls("w")} w:w="{int(indent_pt * 20)}" w:type="dxa"/>'
    )
    tblPr.append(new_tblInd)


def set_cell_margins(cell, top=8, bottom=8, left=0, right=15):
    """单元格极紧凑边距"""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>\n'
        f'  <w:top w:w="{top}" w:type="dxa"/>\n'
        f'  <w:bottom w:w="{bottom}" w:type="dxa"/>\n'
        f'  <w:left w:w="{left}" w:type="dxa"/>\n'
        f'  <w:right w:w="{right}" w:type="dxa"/>\n'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def create_vert270_textbox_run(
    text: str,
    width_cm: float = 1.2,
    height_cm: float = 7.5,
    font_size_pt: float = 10.5,
    doc_pr_id: int = 101
):
    """
    创建一个整行逆时针旋转 90 度（自下而上阅读，文字向外侧仰视）的考场密封线文本框
    完全 1:1 复刻国考考场真题左侧准考证号与姓名竖向填涂栏
    """
    cx = int(width_cm * 360000)
    cy = int(height_cm * 360000)
    xml = f"""
    <w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
         xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
         xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
         xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
      <w:drawing>
        <wp:inline distT="0" distB="0" distL="0" distR="0">
          <wp:extent cx="{cx}" cy="{cy}"/>
          <wp:docPr id="{doc_pr_id}" name="SealBox{doc_pr_id}"/>
          <a:graphic>
            <a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
              <wps:wsp>
                <wps:cNvSpPr txBox="1"/>
                <wps:spPr>
                  <a:xfrm>
                    <a:off x="0" y="0"/>
                    <a:ext cx="{cx}" cy="{cy}"/>
                  </a:xfrm>
                  <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                  <a:noFill/>
                  <a:ln><a:noFill/></a:ln>
                </wps:spPr>
                <wps:txbx>
                  <w:txbxContent>
                    <w:p>
                      <w:pPr><w:jc w:val="left"/></w:pPr>
                      <w:r>
                        <w:rPr>
                          <w:rFonts w:ascii="Times New Roman" w:eastAsia="仿宋"/>
                          <w:sz w:val="{int(font_size_pt * 2)}"/>
                        </w:rPr>
                        <w:t>{text}</w:t>
                      </w:r>
                    </w:p>
                  </w:txbxContent>
                </wps:txbx>
                <wps:bodyPr vert="vert270" lIns="0" tIns="0" rIns="0" bIns="0"/>
              </wps:wsp>
            </a:graphicData>
          </a:graphic>
        </wp:inline>
      </w:drawing>
    </w:r>
    """
    return parse_xml(xml)


def build_two_page_cover_template(save_path: Path):
    """构建具备像素级考场双页封面（密封线、重要提示、注意事项、警示框）的真题模板"""
    doc = Document()

    # 版面设置：考场与电商通用 JIS B5 (18.2cm × 25.7cm)
    sec1 = doc.sections[0]
    sec1.page_width = Cm(18.2)
    sec1.page_height = Cm(25.7)
    sec1.top_margin = Cm(1.8)
    sec1.bottom_margin = Cm(1.8)
    sec1.left_margin = Cm(1.6)
    sec1.right_margin = Cm(1.6)
    CONTENT_WIDTH = Cm(15.0)  # 版心精确 15.0cm，完美容纳一行 33 个仿宋小四号字符

    # 封面节（第1、2页）：绝对禁止出现页眉和页脚！
    sec1.header.is_linked_to_previous = False
    for p in sec1.header.paragraphs:
        p.text = ""
    sec1.footer.is_linked_to_previous = False
    for p in sec1.footer.paragraphs:
        p.text = ""

    # ==================== 第 1 页：正面试卷封面（带左侧密封线） ====================
    # 采用两列表格：左列为密封线竖排填涂区，右列为主标题与重要提示区
    t_cover = doc.add_table(rows=2, cols=2)
    t_cover.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders_none(t_cover)
    t_cover.autofit = False

    # 设置整表各列宽度与精确行高（支撑起整页密封线，JIS B5版心宽15.0cm）
    col_widths = [Cm(1.8), Cm(13.2)]
    for row in t_cover.rows:
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        row.height = Cm(10.8)
        for idx, width in enumerate(col_widths):
            row.cells[idx].width = width

    # 左列第1格（准考证号，逆时针90度竖排居中）
    c_seal_1 = t_cover.cell(0, 0)
    c_seal_1.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    tcPr_s1 = c_seal_1._tc.get_or_add_tcPr()
    tcPr_s1.append(parse_xml(
        f'<w:tcBorders {nsdecls("w")}>\n'
        f'  <w:right w:val="dashed" w:sz="6" w:space="0" w:color="888888"/>\n'
        f'</w:tcBorders>'
    ))
    set_cell_margins(c_seal_1, top=0, bottom=0, left=6, right=12)
    p_s1 = c_seal_1.paragraphs[0]
    p_s1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_s1._p.append(create_vert270_textbox_run(
        "准考证号：____________________________",
        width_cm=1.2,
        height_cm=7.5,
        font_size_pt=10.5,
        doc_pr_id=101
    ))

    # 左列第2格（姓名，逆时针90度竖排居中）
    c_seal_2 = t_cover.cell(1, 0)
    c_seal_2.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    tcPr_s2 = c_seal_2._tc.get_or_add_tcPr()
    tcPr_s2.append(parse_xml(
        f'<w:tcBorders {nsdecls("w")}>\n'
        f'  <w:right w:val="dashed" w:sz="6" w:space="0" w:color="888888"/>\n'
        f'</w:tcBorders>'
    ))
    set_cell_margins(c_seal_2, top=0, bottom=0, left=6, right=12)
    p_s2 = c_seal_2.paragraphs[0]
    p_s2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_s2._p.append(create_vert270_textbox_run(
        "姓    名：____________________________",
        width_cm=1.2,
        height_cm=7.5,
        font_size_pt=10.5,
        doc_pr_id=102
    ))

    # 右列第1格（合并右列上下两格为主卷面区）
    c_main = t_cover.cell(0, 1)
    c_main.merge(t_cover.cell(1, 1))
    c_main.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    set_cell_margins(c_main, top=10, bottom=10, left=24, right=10)

    # 1. 大赛年份与主卷名称（居中）
    p_main_top = c_main.paragraphs[0]
    p_main_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_main_top.paragraph_format.space_before = Pt(12)
    p_main_top.paragraph_format.space_after = Pt(12)
    r_sub_t = p_main_top.add_run("{{ paper.exam_name }}")
    apply_official_font(r_sub_t, cn_font="宋体", size_pt=13.0, bold=False)

    # 2. 试卷大标题（超大黑体，居中加粗）
    p_main_title = c_main.add_paragraph()
    p_main_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_main_title.paragraph_format.space_before = Pt(8)
    p_main_title.paragraph_format.space_after = Pt(14)
    p_main_title.paragraph_format.line_spacing = 1.2
    r_mt = p_main_title.add_run("{{ paper.title }}")
    apply_official_font(r_mt, cn_font="黑体", size_pt=24.0, bold=True)

    # 3. 试卷类别（如：行政执法类）
    p_cat = c_main.add_paragraph()
    p_cat.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cat.paragraph_format.space_before = Pt(0)
    p_cat.paragraph_format.space_after = Pt(65)  # 优雅纵向下推，让重要提示位于下半部
    r_cat = p_cat.add_run("{{ paper.category }}")
    apply_official_font(r_cat, cn_font="黑体", size_pt=13.5, bold=False)

    # 4. 【重要提示】区域
    p_tip_head = c_main.add_paragraph()
    p_tip_head.paragraph_format.space_before = Pt(10)
    p_tip_head.paragraph_format.space_after = Pt(4)
    p_tip_head.paragraph_format.left_indent = Pt(18)
    r_th = p_tip_head.add_run("重要提示：")
    apply_official_font(r_th, cn_font="黑体", size_pt=11.5, bold=True)

    # 第 1 条提示
    p_tip_1 = c_main.add_paragraph()
    p_tip_1.paragraph_format.space_before = Pt(2)
    p_tip_1.paragraph_format.space_after = Pt(4)
    p_tip_1.paragraph_format.line_spacing = 1.25
    p_tip_1.paragraph_format.left_indent = Pt(18)
    r_t1 = p_tip_1.add_run(
        "1. 为维护考生的个人权益，确保公务员考试的公平公正。请您协助我们监督考试实施工作。\n"
        "本场考试规定：监考人员要向本考场全体考生展示题本密封情况，并邀请 2 名考生代表验封签字后，方能开启试卷袋。"
        "如果您发现本考场监考人员存在违规启用试卷袋的情况，请向人力资源和社会保障部人事考试中心举报。举报电话：000-12345678。"
    )
    apply_official_font(r_t1, cn_font="仿宋", size_pt=10.0)

    # 第 2 条提示
    p_tip_2 = c_main.add_paragraph()
    p_tip_2.paragraph_format.space_before = Pt(4)
    p_tip_2.paragraph_format.space_after = Pt(10)
    p_tip_2.paragraph_format.line_spacing = 1.25
    p_tip_2.paragraph_format.left_indent = Pt(18)
    r_t2 = p_tip_2.add_run(
        "2. 在阅卷过程中发现报考者之间同一科目作答内容雷同，并经阅卷专家组确认的，考试机构将给予其该科目（场次）考试成绩为零分的处理，录用程序终止。"
        "请您妥善看护好自己的考试试卷和答题信息，防止被他人抄袭。"
    )
    apply_official_font(r_t2, cn_font="仿宋", size_pt=10.0)

    # 封面第 1 页结束，强制换页到第 2 页！
    doc.add_page_break()

    # ==================== 第 2 页：封二【注意事项与虚线警示框】 ====================
    # 顶部居中大标题（四个字，无多余空格，完全匹配截图）
    p_note_title = doc.add_paragraph()
    p_note_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_note_title.paragraph_format.space_before = Pt(18)
    p_note_title.paragraph_format.space_after = Pt(18)
    r_nt = p_note_title.add_run("注意事项")
    apply_official_font(r_nt, cn_font="黑体", size_pt=15.0, bold=True)

    # 六大核心考场注意事项公文段落
    notes_texts = [
        "一、此项测验分为五个部分，共 130 题，总时限 120 分钟，各部分不单独计时，但都给出参考时限，供答题时合理分配时间。",
        "二、请按照要求在答题卡上填写好自己的姓名，涂写好准考证号，严禁折叠答题卡。",
        "三、必须在答题卡上答题；在题本上答题，一律无效。",
        "四、监考人员宣布考试开始时，方可答题，宣布考试结束时，应立即停止答题。题本、答题卡、草稿纸一律留在桌上，待监考人员确认数量无误，允许离开后，方可离开考场。如果你违反了以上任何一项要求，都将影响你的成绩。",
        "五、在这项测验中，可能有些试题较难，因此你不要在一道题上思考时间太久，遇到不会答的题目可先跳过去，如果有时间再去思考，否则，你可能没有时间完成后面的题目。",
        "六、试题答错不倒扣分。",
        "严禁折叠答题卡！"
    ]
    for idx, text in enumerate(notes_texts):
        p_n = doc.add_paragraph()
        p_n.paragraph_format.space_before = Pt(3)
        p_n.paragraph_format.space_after = Pt(3)
        p_n.paragraph_format.line_spacing = 1.35
        p_n.paragraph_format.first_line_indent = Pt(21)  # 首行缩进2字符
        p_n.paragraph_format.left_indent = Pt(12)
        p_n.paragraph_format.right_indent = Pt(12)
        is_bold = (idx == len(notes_texts) - 1)  # “严禁折叠答题卡！”加粗
        r_n = p_n.add_run(text)
        apply_official_font(r_n, cn_font="仿宋", size_pt=10.5, bold=is_bold)

    # 底部粗虚线警示方框（完全复刻截图 2）
    p_box_space = doc.add_paragraph()
    p_box_space.paragraph_format.space_before = Pt(36)
    p_box_space.paragraph_format.space_after = Pt(0)

    t_warn_box = doc.add_table(rows=1, cols=1)
    t_warn_box.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_wbox = t_warn_box.cell(0, 0)
    c_wbox.width = Cm(11.0)
    tcPr_wbox = c_wbox._tc.get_or_add_tcPr()
    tcBorders_wbox = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="dashed" w:sz="12" w:space="0" w:color="000000"/>\n'
        f'  <w:left w:val="dashed" w:sz="12" w:space="0" w:color="000000"/>\n'
        f'  <w:bottom w:val="dashed" w:sz="12" w:space="0" w:color="000000"/>\n'
        f'  <w:right w:val="dashed" w:sz="12" w:space="0" w:color="000000"/>\n'
        f'</w:tcBorders>'
    )
    tcPr_wbox.append(tcBorders_wbox)
    set_cell_margins(c_wbox, top=24, bottom=24, left=16, right=16)

    p_wbox = c_wbox.paragraphs[0]
    p_wbox.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_wbox.paragraph_format.space_before = Pt(4)
    p_wbox.paragraph_format.space_after = Pt(4)
    p_wbox.paragraph_format.line_spacing = 1.3
    r_wb1 = p_wbox.add_run("停！请不要往下翻！听候监考老师的指示。\n")
    apply_official_font(r_wb1, cn_font="黑体", size_pt=12.0, bold=True)
    r_wb2 = p_wbox.add_run("否则，会影响你的成绩")
    apply_official_font(r_wb2, cn_font="黑体", size_pt=12.0, bold=True)

    # ==================== 分节符：从第 3 页起进入试卷正式作答区 ====================
    sec2 = doc.add_section(WD_SECTION_START.NEW_PAGE)
    sec2.page_width = Cm(18.2)
    sec2.page_height = Cm(25.7)
    sec2.top_margin = Cm(1.8)
    sec2.bottom_margin = Cm(1.8)
    sec2.left_margin = Cm(1.6)
    sec2.right_margin = Cm(1.6)

    # 设置文档网格为只指定行网格（避免 Word 网格对齐强制拉伸字距，确保一行精准容纳 33 字符）
    sectPr2 = sec2._sectPr
    docGrid2 = sectPr2.find(qn('w:docGrid'))
    if docGrid2 is not None:
        sectPr2.remove(docGrid2)
    sectPr2.append(parse_xml(f'<w:docGrid {nsdecls("w")} w:type="lines" w:linePitch="360"/>'))
    # 正文从第 1 页开始动态编号
    sectPr2.append(parse_xml(f'<w:pgNumType {nsdecls("w")} w:start="1"/>'))

    # 第2节：彻底断开与封面的页眉/页脚链接，正式展示正文原生动态页码页脚
    sec2.header.is_linked_to_previous = False
    for p in sec2.header.paragraphs:
        p.text = ""

    sec2.footer.is_linked_to_previous = False
    footer2 = sec2.footer
    fp2 = footer2.paragraphs[0]
    fp2.text = ""
    fp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp2.paragraph_format.space_before = Pt(6)
    fp2.paragraph_format.space_after = Pt(0)

    pPr2 = fp2._p.get_or_add_pPr()
    pPr2.append(parse_xml(f'<w:jc {nsdecls("w")} w:val="center"/>'))

    r1 = parse_xml(
        f'<w:r {nsdecls("w")}>'
        f'  <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr>'
        f'  <w:t xml:space="preserve">第 </w:t>'
        f'</w:r>'
    )
    fld1 = parse_xml(
        f'<w:fldSimple {nsdecls("w")} w:instr="PAGE">'
        f'  <w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr><w:t>1</w:t></w:r>'
        f'</w:fldSimple>'
    )
    r2 = parse_xml(
        f'<w:r {nsdecls("w")}>'
        f'  <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr>'
        f'  <w:t xml:space="preserve"> 页  共 </w:t>'
        f'</w:r>'
    )
    fld2 = parse_xml(
        f'<w:fldSimple {nsdecls("w")} w:instr="NUMPAGES">'
        f'  <w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr><w:t>1</w:t></w:r>'
        f'</w:fldSimple>'
    )
    r3 = parse_xml(
        f'<w:r {nsdecls("w")}>'
        f'  <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr>'
        f'  <w:t> 页</w:t>'
        f'</w:r>'
    )
    fp2._p.append(r1)
    fp2._p.append(fld1)
    fp2._p.append(r2)
    fp2._p.append(fld2)
    fp2._p.append(r3)

    # ==================== 第 3 页起：试卷正式作答区 ====================
    p_sec_loop = doc.add_paragraph()
    p_sec_loop.paragraph_format.space_before = Pt(0)
    p_sec_loop.paragraph_format.space_after = Pt(0)
    p_sec_loop.add_run("{% for part in paper.parts %}")

    # 模块大标题（每部分独立新开一页 + 严格居中 + 黑体加粗）
    p_part = doc.add_paragraph()
    p_part.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_part.paragraph_format.space_before = Pt(14)
    p_part.paragraph_format.space_after = Pt(4)
    p_part.paragraph_format.keep_with_next = True
    p_part.paragraph_format.page_break_before = True  # 每个大模块强制换页！
    r_pt = p_part.add_run("{{ part.name }}")
    apply_official_font(r_pt, cn_font="黑体", size_pt=14, bold=True)

    # 模块题量与时限说明段落：【严格居中】
    p_part_sub = doc.add_paragraph()
    p_part_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_part_sub.paragraph_format.space_before = Pt(0)
    p_part_sub.paragraph_format.space_after = Pt(8)
    p_part_sub.paragraph_format.keep_with_next = True
    r_ps = p_part_sub.add_run("（共 {{ part.question_count }} 题，参考时限 {{ part.time_limit }} 分钟）")
    apply_official_font(r_ps, cn_font="仿宋", size_pt=10.5)

    # 答题指导语与“请开始答题：”：与题干首字垂直对齐（左缩进 24pt），黑体
    p_intro = doc.add_paragraph()
    p_intro.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_intro.paragraph_format.left_indent = Pt(HANG_INDENT_PT)
    p_intro.paragraph_format.space_before = Pt(0)
    p_intro.paragraph_format.space_after = Pt(6)
    p_intro.paragraph_format.line_spacing = 1.2
    p_intro.paragraph_format.keep_with_next = True
    r_intro = p_intro.add_run("{{ part.intro }}")
    apply_official_font(r_intro, cn_font="黑体", size_pt=10.5, bold=False)

    # 题目循环开头
    p_q_start = doc.add_paragraph()
    p_q_start.paragraph_format.space_before = Pt(0)
    p_q_start.paragraph_format.space_after = Pt(0)
    p_q_start.add_run("{% for q in part.questions %}")

    # ------------------ 材料题标准排版区域 ------------------
    # 1. 引导语段落：黑体 10.5pt，左缩进 24pt（与下方题干首字垂直对齐）
    p_mat_intro = doc.add_paragraph()
    p_mat_intro.paragraph_format.space_before = Pt(6)
    p_mat_intro.paragraph_format.space_after = Pt(3)
    p_mat_intro.paragraph_format.left_indent = Pt(HANG_INDENT_PT)
    p_mat_intro.paragraph_format.line_spacing = 1.2
    p_mat_intro.paragraph_format.keep_with_next = True
    p_mat_intro.add_run("{% if q.material and q.material.intro %}")
    r_mi = p_mat_intro.add_run("{{ q.material.intro }}")
    apply_official_font(r_mi, cn_font="黑体", size_pt=10.5, bold=False)
    p_mat_intro.add_run("{% endif %}")

    # 2. 材料主体图文段落循环：文字块首行缩进，图片块居中展示
    p_mat_line_start = doc.add_paragraph()
    p_mat_line_start.paragraph_format.space_before = Pt(0)
    p_mat_line_start.paragraph_format.space_after = Pt(0)
    p_mat_line_start.add_run("{% if q.material and q.material.blocks %}{% for blk in q.material.blocks %}")

    # 文本段落分支
    p_mat_text_tag = doc.add_paragraph()
    p_mat_text_tag.paragraph_format.space_before = Pt(0)
    p_mat_text_tag.paragraph_format.space_after = Pt(0)
    p_mat_text_tag.add_run("{% if not blk.is_img %}")

    p_mat_text = doc.add_paragraph()
    p_mat_text.paragraph_format.space_before = Pt(1)
    p_mat_text.paragraph_format.space_after = Pt(2)
    p_mat_text.paragraph_format.left_indent = Pt(0)
    p_mat_text.paragraph_format.first_line_indent = Pt(HANG_INDENT_PT)
    p_mat_text.paragraph_format.line_spacing = 1.25
    p_mat_text.paragraph_format.keep_with_next = True
    r_ml = p_mat_text.add_run("{{ blk.text }}")
    apply_official_font(r_ml, cn_font="仿宋", size_pt=12.0)

    # 图片段落分支
    p_mat_img_tag = doc.add_paragraph()
    p_mat_img_tag.paragraph_format.space_before = Pt(0)
    p_mat_img_tag.paragraph_format.space_after = Pt(0)
    p_mat_img_tag.add_run("{% else %}")

    p_mat_img = doc.add_paragraph()
    p_mat_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_mat_img.paragraph_format.space_before = Pt(4)
    p_mat_img.paragraph_format.space_after = Pt(4)
    p_mat_img.paragraph_format.keep_with_next = True
    p_mat_img.add_run("{{ blk.img }}")

    p_mat_line_end = doc.add_paragraph()
    p_mat_line_end.paragraph_format.space_before = Pt(0)
    p_mat_line_end.paragraph_format.space_after = Pt(0)
    p_mat_line_end.add_run("{% endif %}{% endfor %}{% elif q.material and q.material.lines %}{% for line in q.material.lines %}")

    p_mat_line_fallback = doc.add_paragraph()
    p_mat_line_fallback.paragraph_format.space_before = Pt(1)
    p_mat_line_fallback.paragraph_format.space_after = Pt(2)
    p_mat_line_fallback.paragraph_format.left_indent = Pt(0)
    p_mat_line_fallback.paragraph_format.first_line_indent = Pt(HANG_INDENT_PT)
    p_mat_line_fallback.paragraph_format.line_spacing = 1.25
    p_mat_line_fallback.paragraph_format.keep_with_next = True
    r_ml_fb = p_mat_line_fallback.add_run("{{ line }}")
    apply_official_font(r_ml_fb, cn_font="仿宋", size_pt=12.0)

    p_mat_fallback_end = doc.add_paragraph()
    p_mat_fallback_end.paragraph_format.space_before = Pt(0)
    p_mat_fallback_end.paragraph_format.space_after = Pt(0)
    p_mat_fallback_end.add_run("{% endfor %}{% endif %}")

    # 题干段落（标准悬挂缩进 + Tab 制表符对齐）
    p_stem = doc.add_paragraph()
    p_stem.paragraph_format.space_before = Pt(4)
    p_stem.paragraph_format.space_after = Pt(2)
    p_stem.paragraph_format.line_spacing = 1.2
    p_stem.paragraph_format.keep_with_next = True
    p_stem.paragraph_format.left_indent = Pt(HANG_INDENT_PT)
    p_stem.paragraph_format.first_line_indent = -Pt(HANG_INDENT_PT)
    p_stem.paragraph_format.tab_stops.add_tab_stop(Pt(HANG_INDENT_PT))

    r_no = p_stem.add_run("{{ q.no }}.\t")
    apply_official_font(r_no, cn_font="仿宋", size_pt=12.0)
    p_stem.add_run("{% for seg in q.stem_segments %}{% if seg.bold %}")
    r_seg_b = p_stem.add_run("{{ seg.text }}")
    apply_official_font(r_seg_b, cn_font="仿宋", size_pt=12.0, bold=True)
    p_stem.add_run("{% else %}")
    r_seg_n = p_stem.add_run("{{ seg.text }}")
    apply_official_font(r_seg_n, cn_font="仿宋", size_pt=12.0, bold=False)
    p_stem.add_run("{% endif %}{% endfor %}")

    # 题干配图（几何图形、图形推理题干图、工程统计表等）
    p_simg_start = doc.add_paragraph()
    p_simg_start.paragraph_format.space_before = Pt(0)
    p_simg_start.paragraph_format.space_after = Pt(0)
    p_simg_start.add_run("{% if q.stem_images %}{% for simg in q.stem_images %}")

    p_simg = doc.add_paragraph()
    p_simg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_simg.paragraph_format.space_before = Pt(3)
    p_simg.paragraph_format.space_after = Pt(4)
    p_simg.paragraph_format.keep_with_next = True
    p_simg.add_run("{{ simg }}")

    p_simg_end = doc.add_paragraph()
    p_simg_end.paragraph_format.space_before = Pt(0)
    p_simg_end.paragraph_format.space_after = Pt(0)
    p_simg_end.add_run("{% endfor %}{% endif %}")

    # 选项行：4 列分支
    p_opt_4 = doc.add_paragraph()
    p_opt_4.paragraph_format.space_before = Pt(0)
    p_opt_4.paragraph_format.space_after = Pt(0)
    p_opt_4.add_run("{% if q.layout == '4col' %}")

    t_4 = doc.add_table(rows=1, cols=4)
    t_4.alignment = WD_TABLE_ALIGNMENT.LEFT
    set_table_borders_none(t_4)
    set_table_left_indent(t_4, HANG_INDENT_PT)
    t_4.autofit = False
    opt_table_width = CONTENT_WIDTH - Pt(HANG_INDENT_PT)
    col_width_4 = opt_table_width / 4
    for i in range(4):
        c = t_4.cell(0, i)
        c.width = col_width_4
        set_cell_margins(c, top=4, bottom=4, left=0, right=10)
        cp = c.paragraphs[0]
        cp.paragraph_format.space_before = Pt(0)
        cp.paragraph_format.space_after = Pt(0)
        cp.paragraph_format.line_spacing = 1.15
        # 支持图片选项与文字选项
        cp.add_run(f"{{% if q.opt_{i}_img %}}")
        crun_pre = cp.add_run(f"{{{{ q.opt_{i}_prefix }}}} ")
        apply_official_font(crun_pre, cn_font="仿宋", size_pt=12.0)
        cp.add_run(f"{{{{ q.opt_{i}_img }}}}")
        cp.add_run(f"{{% else %}}")
        crun = cp.add_run(f"{{{{ q.opt_{i} }}}}")
        apply_official_font(crun, cn_font="仿宋", size_pt=12.0)
        cp.add_run(f"{{% endif %}}")

    # 选项行：2 列分支
    p_opt_2 = doc.add_paragraph()
    p_opt_2.paragraph_format.space_before = Pt(0)
    p_opt_2.paragraph_format.space_after = Pt(0)
    p_opt_2.add_run("{% elif q.layout == '2col' %}")

    t_2 = doc.add_table(rows=2, cols=2)
    t_2.alignment = WD_TABLE_ALIGNMENT.LEFT
    set_table_borders_none(t_2)
    set_table_left_indent(t_2, HANG_INDENT_PT)
    t_2.autofit = False
    col_width_2 = opt_table_width / 2
    for r_idx, c_pair in enumerate([(0, 1), (2, 3)]):
        for c_idx, opt_num in enumerate(c_pair):
            c = t_2.cell(r_idx, c_idx)
            c.width = col_width_2
            set_cell_margins(c, top=4, bottom=4, left=0, right=10)
            cp = c.paragraphs[0]
            cp.paragraph_format.space_before = Pt(0)
            cp.paragraph_format.space_after = Pt(0)
            cp.paragraph_format.line_spacing = 1.15
            # 支持图片选项与文字选项
            cp.add_run(f"{{% if q.opt_{opt_num}_img %}}")
            crun_pre = cp.add_run(f"{{{{ q.opt_{opt_num}_prefix }}}} ")
            apply_official_font(crun_pre, cn_font="仿宋", size_pt=12.0)
            cp.add_run(f"{{{{ q.opt_{opt_num}_img }}}}")
            cp.add_run(f"{{% else %}}")
            crun = cp.add_run(f"{{{{ q.opt_{opt_num} }}}}")
            apply_official_font(crun, cn_font="仿宋", size_pt=12.0)
            cp.add_run(f"{{% endif %}}")

    # 选项行：1 列分支
    p_opt_1 = doc.add_paragraph()
    p_opt_1.paragraph_format.space_before = Pt(0)
    p_opt_1.paragraph_format.space_after = Pt(0)
    p_opt_1.add_run("{% else %}{% for opt in q.raw_options %}")

    p_opt = doc.add_paragraph()
    p_opt.paragraph_format.space_before = Pt(1)
    p_opt.paragraph_format.space_after = Pt(1)
    p_opt.paragraph_format.left_indent = Pt(HANG_INDENT_PT)
    p_opt.paragraph_format.line_spacing = 1.15
    p_opt.add_run("{% if opt.img %}")
    r_opt_pre = p_opt.add_run("{{ opt.prefix }} ")
    apply_official_font(r_opt_pre, cn_font="仿宋", size_pt=12.0)
    p_opt.add_run("{{ opt.img }}")
    p_opt.add_run("{% else %}")
    r_opt = p_opt.add_run("{{ opt.raw if opt.raw else opt }}")
    apply_official_font(r_opt, cn_font="仿宋", size_pt=12.0)
    p_opt.add_run("{% endif %}")

    # 闭合题目循环标签
    p_q_end = doc.add_paragraph()
    p_q_end.paragraph_format.space_before = Pt(0)
    p_q_end.paragraph_format.space_after = Pt(0)
    p_q_end.add_run("{% endfor %}{% endif %}{% endfor %}")

    # 模块结束提示语（严格居中 + 考场规范黑体）
    p_part_end = doc.add_paragraph()
    p_part_end.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_part_end.paragraph_format.space_before = Pt(16)
    p_part_end.paragraph_format.space_after = Pt(16)
    p_part_end.paragraph_format.line_spacing = 1.2
    p_part_end.add_run("{% if part.end_notice %}")
    r_pe = p_part_end.add_run("{{ part.end_notice }}")
    apply_official_font(r_pe, cn_font="黑体", size_pt=11.0, bold=True)
    p_part_end.add_run("{% endif %}")

    # 闭合模块循环标签
    p_part_end_tag = doc.add_paragraph()
    p_part_end_tag.paragraph_format.space_before = Pt(0)
    p_part_end_tag.paragraph_format.space_after = Pt(0)
    p_part_end_tag.add_run("{% endfor %}")

    doc.save(str(save_path))
    print(f"[✓] 双页全真封面 B5 模板构建完毕: {save_path}")


def highlight_reverse_questions(stem: str) -> list[dict]:
    """智能加粗反向设问词"""
    pattern = r"(不正确的是|不正确|不属于的是|不属于|错误的是|最不恰当的是|最不恰当|不符合的是|不符合|不同的是)"
    parts = re.split(pattern, stem)
    segments = []
    for part in parts:
        if not part:
            continue
        if re.match(pattern, part):
            segments.append({"text": part, "bold": True})
        else:
            segments.append({"text": part, "bold": False})
    return segments


# 公考官方真题六大标准模块规范注册表（1:1 复刻考场真题与截图 2~5）
GONGKAO_STANDARD_MODULES = [
    {
        "key": "changshi",
        "title": "常识判断",
        "intro": "根据题目要求，在四个选项中选出一个最恰当的答案。",
        "time_limit": 10,
    },
    {
        "key": "yanyu",
        "title": "言语理解与表达",
        "intro": "本部分包含表达与理解两方面的内容。请在四个选项中选出一个最恰当的答案。",
        "time_limit": 35,
    },
    {
        "key": "shuliang",
        "title": "数量关系",
        "intro": "在这部分试题中，每道题呈现一段表达数字关系的文字，要求你迅速准确地计算出答案。",
        "time_limit": 15,
    },
    {
        "key": "panduan",
        "title": "判断推理",
        "intro": "本部分包含图形推理、定义判断、类比推理与逻辑判断四种类型的试题。请在四个选项中选出一个最恰当的答案。",
        "time_limit": 35,
    },
    {
        "key": "ziliao",
        "title": "资料分析",
        "intro": "所给出的图、表、文字或综合性资料均有若干个问题要你回答。你应根据资料提供的信息进行分析、比较、计算和判断处理。",
        "time_limit": 25,
    },
]

CN_NUMS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def prepare_b5_question_data(
    no: int,
    stem: str,
    options: list[dict],
    material: dict | str | None = None
):
    """
    包装单道题目数据，支持标准选项分栏智能判断、设问词加粗，
    以及材料题结构化（引导语 24pt 黑体缩进 + 材料主体 0pt 仿宋顶格）
    """
    def visual_len(text: str) -> float:
        return sum(1.0 if ord(c) > 127 else 0.5 for c in text)

    formatted_opts = [f"{o['code']}. {o['text']}" for o in options]
    max_len = max(visual_len(text) for text in formatted_opts)

    if max_len <= 6.0 and len(options) == 4:
        layout = "4col"
    elif max_len <= 14.0 and len(options) == 4:
        layout = "2col"
    else:
        layout = "1col"

    stem_segments = highlight_reverse_questions(stem)

    # 规范化材料题数据结构
    norm_material = None
    if material:
        if isinstance(material, str):
            norm_material = {
                "intro": "",
                "lines": [material]
            }
        elif isinstance(material, dict):
            intro = material.get("intro", "")
            lines = material.get("lines", [])
            if not lines and "text" in material:
                lines = [line.strip() for line in material["text"].split("\n") if line.strip()]
            norm_material = {
                "intro": intro,
                "lines": lines
            }

    q_data = {
        "no": no,
        "material": norm_material,
        "stem_segments": stem_segments,
        "layout": layout,
        "raw_options": formatted_opts,
    }

    for i in range(len(formatted_opts)):
        q_data[f"opt_{i}"] = formatted_opts[i]

    return q_data


def build_exam_parts(raw_modules: list[dict]) -> list[dict]:
    """
    公考大模块智能包装器：
    1. 动态跳过题目为空的模块，不生成任何空白页面；
    2. 自动从 1 到 N 顺延编号（第一部分、第二部分...）；
    3. 自动匹配各模块官方标准指导语（匹配图 2~5），并注入“请开始答题：”；
    4. 自动生成各部分过渡语与试卷结束语。
    """
    # 过滤非空模块
    active_modules = [m for m in raw_modules if m.get("questions")]
    total_parts = len(active_modules)
    packaged_parts = []

    for idx, mod in enumerate(active_modules, 1):
        cn_idx = CN_NUMS[idx - 1]
        raw_title = mod.get("title", f"第{cn_idx}部分")
        clean_title = re.sub(r"^第[一二三四五六七八九十]+部分\s*", "", raw_title).strip()
        part_name = f"第{cn_idx}部分 {clean_title}"

        # 匹配指导语
        intro = mod.get("intro", "")
        if not intro:
            for std in GONGKAO_STANDARD_MODULES:
                if std["title"] in clean_title:
                    intro = std["intro"]
                    break
            if not intro:
                intro = "根据题目要求，在四个选项中选出一个最恰当的答案。"

        if not intro.endswith("请开始答题："):
            intro = f"{intro}\n请开始答题："

        # 结束过渡提示语
        if idx < total_parts:
            next_cn = CN_NUMS[idx]
            end_notice = f"※※※第{cn_idx}部分结束，请继续做第{next_cn}部分！※※※"
        else:
            end_notice = "※※※全部测验到此结束！※※※"

        packaged_parts.append({
            "name": part_name,
            "question_count": len(mod["questions"]),
            "time_limit": mod.get("time_limit", 15),
            "intro": intro,
            "end_notice": end_notice,
            "questions": mod["questions"],
        })

    return packaged_parts


def prepare_mock_exam_pack():
    """构造覆盖五大公考核心模块、包含材料题的完整全真模考数据"""
    # 1. 第一部分 常识判断（含单选4列、长题干33字测试）
    m_changshi = {
        "title": "常识判断",
        "time_limit": 5,
        "questions": [
            prepare_b5_question_data(
                no=24,
                stem="根据《全国农业普查条例》规定，下列说法正确的是（  ）。",
                options=[
                    {"code": "A", "text": "农业普查的对象包括村民委员会、乡镇人民政府"},
                    {"code": "B", "text": "农业普查每5年进行一次"},
                    {"code": "C", "text": "普查人员执行农业普查任务时，无需出示证件"},
                    {"code": "D", "text": "农业普查行业范围仅包括种植业、畜牧业"},
                ],
            ),
            prepare_b5_question_data(
                no=25,
                stem="下列古代治国思想与其提出者对应错误的是：",
                options=[
                    {"code": "A", "text": "为政以德，譬如北辰——孔子"},
                    {"code": "B", "text": "民为贵，社稷次之，君为轻——孟子"},
                    {"code": "C", "text": "法不阿贵，绳不挠曲——韩非子"},
                    {"code": "D", "text": "兼爱、非攻、尚贤——老子"},
                ],
            ),
            prepare_b5_question_data(
                no=26,
                stem="关于我国重大水利工程及其历史作用，下列各项不属于战国时期修建的是：",
                options=[
                    {"code": "A", "text": "都江堰"},
                    {"code": "B", "text": "郑国渠"},
                    {"code": "C", "text": "灵渠"},
                    {"code": "D", "text": "西门豹渠"},
                ],
            ),
            prepare_b5_question_data(
                no=53,
                stem="随着区域合作日趋成为当今国际合作的主流，区域公共产品的提供是解决全球公共产品供需矛盾的重要途径。区域公共产品遵循“受益人支付”的原则，由相关国家共同提供、共同消费。由于区域公共产品的成本收益边界较为清晰，因此能有效避免全球公共产品中存在的“搭便车”行为。在投融资国际合作领域，区域公共产品的提供应从技术性、普惠性、非政治性领域起步，坚持不同国家负有“共同但有区别”的责任，最终形成“由易到难，从内至外”的区域公共产品供给新路径。",
                options=[
                    {"code": "A", "text": "受益人支付原则有效防范了搭便车行为"},
                    {"code": "B", "text": "国际投融资合作应从政治性领域逐步起步"},
                    {"code": "C", "text": "区域合作已彻底消除全球公共产品供需矛盾"},
                    {"code": "D", "text": "由易到难、从内至外是区域公共产品供给路径"},
                ],
            ),
        ],
    }

    # 2. 第二部分 言语理解与表达（对应图 5，含第 36 题）
    m_yanyu = {
        "title": "言语理解与表达",
        "time_limit": 30,
        "questions": [
            prepare_b5_question_data(
                no=36,
                stem="面对人工智能时代日益猖獗且复杂多变的网络犯罪，传统法律的应对困境日渐凸显。许多在现实空间中运行良好的刑事法律规则，一旦移植到网络空间便显露出滞后与不适。",
                options=[
                    {"code": "A", "text": "传统法律移植到网络空间具有一定的局限性"},
                    {"code": "B", "text": "人工智能时代的网络犯罪呈现复杂化特征"},
                    {"code": "C", "text": "网络犯罪的滋生亟待完善现行法律法规"},
                    {"code": "D", "text": "现实空间的刑事法律规则无法适用于网络"},
                ],
            ),
        ],
    }

    # 3. 第三部分 数量关系（对应图 4）
    m_shuliang = {
        "title": "数量关系",
        "time_limit": 10,
        "questions": [
            prepare_b5_question_data(
                no=61,
                stem="某商场举行促销活动，一件商品按标价打八折出售仍可获利20%。若标价为300元，则进价为多少元？",
                options=[
                    {"code": "A", "text": "180"},
                    {"code": "B", "text": "200"},
                    {"code": "C", "text": "220"},
                    {"code": "D", "text": "240"},
                ],
            ),
        ],
    }

    # 4. 第四部分 判断推理（对应图 3 指导语 + 图 1 的材料题 106 题）
    mat_106 = {
        "intro": "根据以下资料，回答 106～110 题。",
        "lines": [
            "某园区为保障日常管理工作有序开展，将赵琳、孙越、吴浩、郑佳、王玥、冯哲、高洋这7名工作人员安排在周一至周日值班，每天安排1人，每人每周仅值班1天，且相邻两天值班人员的学历不同。已知：",
            "（1）所有工作人员要么是初中学历，要么是高中学历；",
            "（2）孙越和郑佳的学历相同；",
            "（3）吴浩在周四值班，且吴浩是初中学历；",
            "（4）赵琳的值班日期在王玥和冯哲的值班日期之间；",
            "（5）高洋的学历与吴浩相同，且高洋不在周六、周日值班。",
        ],
    }
    m_panduan = {
        "title": "判断推理",
        "time_limit": 35,
        "questions": [
            prepare_b5_question_data(
                no=106,
                material=mat_106,
                stem="以下从左到右列出的工作人员，哪项可能是从周一至周日的值班安排？",
                options=[
                    {"code": "A", "text": "高洋、孙越、赵琳、吴浩、王玥、郑佳、冯哲"},
                    {"code": "B", "text": "赵琳、吴浩、孙越、高洋、王玥、郑佳、冯哲"},
                    {"code": "C", "text": "孙越、高洋、王玥、吴浩、赵琳、冯哲、郑佳"},
                    {"code": "D", "text": "冯哲、王玥、吴浩、赵琳、高洋、郑佳、孙越"},
                ],
            ),
        ],
    }

    # 5. 第五部分 资料分析（对应图 2 指导语）
    mat_ziliao = {
        "intro": "根据以下资料，回答 111～115 题。",
        "lines": [
            "2026年上半年，全国规模以上工业增加值同比增长6.0%。分三大门类看，采矿业增加值同比增长2.4%，制造业增长6.5%，电力、热力、燃气及水生产和供应业增长6.0%。",
            "高技术制造业增加值同比增长8.7%，快于规模以上工业2.7个百分点。其中，航空航天器及设备制造业、电子及通信设备制造业分别增长11.5%和10.8%。",
        ],
    }
    m_ziliao = {
        "title": "资料分析",
        "time_limit": 25,
        "questions": [
            prepare_b5_question_data(
                no=111,
                material=mat_ziliao,
                stem="2026年上半年，下列行业增加值同比增速最快的是：",
                options=[
                    {"code": "A", "text": "采矿业"},
                    {"code": "B", "text": "制造业"},
                    {"code": "C", "text": "航空航天器及设备制造业"},
                    {"code": "D", "text": "电力、热力、燃气及水生产和供应业"},
                ],
            ),
        ],
    }

    # 执行大模块智能装配
    raw_modules = [m_changshi, m_yanyu, m_shuliang, m_panduan, m_ziliao]
    packaged_parts = build_exam_parts(raw_modules)

    return {
        "paper": {
            "exam_name": "2027年国考第三十五季行测模考大赛",
            "title": "行政职业能力测验",
            "category": "行政执法类",
            "current_page": 1,
            "total_pages": 47,
            "parts": packaged_parts,
        }
    }


def purge_empty_paragraphs(doc: Document):
    """物理清除空段落，保留硬分页、分节符与必要图形结构"""
    for p in list(doc.paragraphs):
        if p._p.xpath('.//w:br[@w:type="page"]|.//w:drawing|.//w:sectPr'):
            continue
        if not p.text.strip():
            p._element.getparent().remove(p._element)


def cleanup_intermediate_files():
    """清理所有中间测试和草稿文件，只保留正式模板和最终版题本"""
    keep_files = {
        "国考行测标准题本_模板底稿.docx",
        "国考行测标准题本_全真模考最终版.docx",
        "国考行测标准题本_全真模考最终版.pdf",
        "国考行测标准题本_全真模考最终版_最新.docx",
        "国考行测标准题本_全真模考最终版_最新.pdf",
    }
    cleaned_count = 0
    for f in list(OUTPUT_DIR.iterdir()):
        if f.is_file() and f.name not in keep_files and not f.name.startswith("~$"):
            try:
                f.unlink()
                cleaned_count += 1
            except Exception:
                pass
    print(f"[✓] 已清理历史中间版本文件共 {cleaned_count} 个，目录已保持整洁。")


def export_docx_to_pdf(docx_file: Path, pdf_file: Path):
    """通过独立的只读临时副本安全转换为 PDF，完美规避本地 Word 打开时的独占锁冲突与卡顿"""
    import tempfile
    import win32com.client
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_docx = Path(tmp_dir) / "safe_copy.docx"
        temp_pdf = Path(tmp_dir) / "safe_copy.pdf"
        shutil.copyfile(docx_file, temp_docx)
        
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        try:
            doc = word.Documents.Open(str(temp_docx), ReadOnly=1)
            doc.SaveAs(str(temp_pdf), FileFormat=17)
            doc.Close(0)
        finally:
            word.Quit()
            
        if temp_pdf.exists():
            try:
                shutil.copyfile(temp_pdf, pdf_file)
                print(f"[✓] 已成功生成矢量 PDF: {pdf_file}")
            except PermissionError:
                alt_pdf = pdf_file.parent / f"{pdf_file.stem}_最新{pdf_file.suffix}"
                shutil.copyfile(temp_pdf, alt_pdf)
                print(f"[!] 原 PDF 被占用，已保存为最新 PDF: {alt_pdf}")


def main():
    print("=== 开始生成双页全真封面 + B5 真题全流程题本 ===")

    # 1. 构建模板
    build_two_page_cover_template(TARGET_TEMPLATE)
    shutil.copy(str(TARGET_TEMPLATE), str(PLUGIN_TARGET_TEMPLATE))
    print(f"[✓] 已同步更新至插件目录: {PLUGIN_TARGET_TEMPLATE}")

    # 2. 渲染效果
    tpl = DocxTemplate(str(TARGET_TEMPLATE))
    context = prepare_mock_exam_pack()
    tpl.render(context)

    # 3. 清理幽灵空行并安全保存
    purge_empty_paragraphs(tpl.docx)
    try:
        tpl.save(str(TARGET_PREVIEW_DOCX))
        final_docx_path = TARGET_PREVIEW_DOCX
        print(f"[✓] 已成功生成全真模考最终版题本: {TARGET_PREVIEW_DOCX}")
    except PermissionError:
        final_docx_path = OUTPUT_DIR / f"{TARGET_PREVIEW_DOCX.stem}_最新{TARGET_PREVIEW_DOCX.suffix}"
        tpl.save(str(final_docx_path))
        print(f"[!] 原文件被打开占用，已保存为最新版: {final_docx_path}")

    # 4. 安全转换为矢量 PDF
    export_docx_to_pdf(final_docx_path, TARGET_PREVIEW_PDF)

    # 5. 清理旧的中间测试版本
    cleanup_intermediate_files()

    print("=== 全部处理完毕 ===")


if __name__ == "__main__":
    main()
