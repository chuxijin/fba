# -*- coding: utf-8 -*-
import docx
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl

doc = docx.Document(r"D:\100_Work\101_Program\Proj\fba\backend\plugin\render_book\templates\basic_calculation\1.0.0\template.docx")
body = doc._body._element
for idx, child in enumerate(body):
    if isinstance(child, CT_P):
        p = docx.text.paragraph.Paragraph(child, doc)
        t = p.text.strip()
        if t:
            print(f"[{idx}] P: {t}")
    elif isinstance(child, CT_Tbl):
        tbl = docx.table.Table(child, doc)
        print(f"[{idx}] TBL: {len(tbl.rows)}x{len(tbl.columns)}, cell0: {[c.text.strip() for c in tbl.rows[0].cells]}")
