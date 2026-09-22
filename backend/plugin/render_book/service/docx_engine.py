#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯原生通用 Word 题本渲染引擎
职责：
1. 接收 template.docx 模板路径与业务 context，执行 docxtpl 渲染；
2. 清除渲染过程产生的空段落，保留必要分页符与版式元素；
3. 将渲染好的 .docx 导出为高清矢量 .pdf；
4. 抽取封面与第一页高清预览图 .jpg。
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any

from docx import Document
from docxtpl import DocxTemplate, InlineImage
import fitz

from backend.common.log import log


def rebind_inline_images(obj: Any, tpl: DocxTemplate, seen: set | None = None) -> None:
    """递归遍历渲染上下文，将所有 InlineImage 对象安全绑定到当前正在渲染的 DocxTemplate 实例"""
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return
    seen.add(obj_id)

    if isinstance(obj, InlineImage):
        obj.tpl = tpl
    elif isinstance(obj, dict):
        for v in obj.values():
            rebind_inline_images(v, tpl, seen)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            rebind_inline_images(item, tpl, seen)


class DocxRenderEngine:
    """通用 Word (.docx) 模板渲染引擎"""

    @staticmethod
    def purge_empty_paragraphs(doc: Document) -> int:
        """物理清除因 Jinja2 标签遗留的空段落，保留硬分页符、分节符与图形"""
        removed = 0
        for p in list(doc.paragraphs):
            # 保留图片、图元、分页符、分节符
            if p._p.xpath('.//w:drawing|.//w:pict|.//w:br[@w:type="page"]|./w:pPr/w:sectPr'):
                continue
            if not p.text.strip():
                p._element.getparent().remove(p._element)
                removed += 1

        # 遍历所有表格单元格，清除多余的空段落（每个单元格至少保留一个段落以合规）
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    paras = list(cell.paragraphs)
                    if len(paras) <= 1:
                        continue
                    for p in paras:
                        if len(cell.paragraphs) <= 1:
                            break
                        if p._p.xpath('.//w:drawing|.//w:pict|.//w:br[@w:type="page"]|./w:pPr/w:sectPr'):
                            continue
                        if not p.text.strip():
                            p._element.getparent().remove(p._element)
                            removed += 1
        return removed

    @classmethod
    def render_docx(cls, template_file: Path, context: dict[str, Any], output_docx: Path) -> Path:
        """渲染生成 .docx 文件"""
        if not template_file.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_file}")

        output_docx.parent.mkdir(parents=True, exist_ok=True)
        tpl = DocxTemplate(str(template_file))
        rebind_inline_images(context, tpl)
        tpl.render(context)

        # 1. 自动转译文档中的 LaTeX 数学公式为 Word 原生矢量公式 (OMML)
        try:
            from backend.plugin.render_book.service.formula_converter import formula_converter
            formula_cnt = formula_converter.convert_formulas_in_document(tpl.docx)
            if formula_cnt > 0:
                log.info(f"[DocxRenderEngine] 成功转译 LaTeX 数学公式共 {formula_cnt} 处为 Word 原生矢量公式")
        except Exception as e:
            log.warning(f"[DocxRenderEngine] 公式转译过程发生异常，已安全跳过: {e}")

        # 2. 渲染后物理清除因 Jinja2 控制流标签遗留的虚无空段落
        removed_cnt = cls.purge_empty_paragraphs(tpl.docx)
        log.info(f"[DocxRenderEngine] 渲染后完成空段落物理净化，剔除无用空行共 {removed_cnt} 处")

        try:
            tpl.save(str(output_docx))
        except PermissionError:
            import time
            output_docx = output_docx.parent / f"{output_docx.stem}_{int(time.time())}.docx"
            tpl.save(str(output_docx))
            log.warning(f"[DocxRenderEngine] 目标 Word 文件被占用，安全另存为: {output_docx}")

        log.info(f"[DocxRenderEngine] 成功渲染 Word 题本: {output_docx}")
        return output_docx

    @staticmethod
    def convert_to_pdf(docx_file: Path, output_pdf: Path) -> Path:
        """
        将 .docx 安全转换为高清矢量 .pdf
        使用独立只读副本，规避本地 Word 进程打开时导致的独占锁或权限异常
        """
        import win32com.client

        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_docx = Path(tmp_dir) / "safe_copy.docx"
            temp_pdf = Path(tmp_dir) / "safe_copy.pdf"
            shutil.copyfile(docx_file, temp_docx)

            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            try:
                doc = word.Documents.Open(str(temp_docx), ReadOnly=1)
                doc.SaveAs(str(temp_pdf), FileFormat=17)  # 17 = wdFormatPDF
                doc.Close(0)
            finally:
                word.Quit()

            if not temp_pdf.exists():
                raise RuntimeError(f"Word 转 PDF 失败，未生成中间文件: {temp_pdf}")

            try:
                shutil.copyfile(temp_pdf, output_pdf)
            except PermissionError:
                import time
                output_pdf = output_pdf.parent / f"{output_pdf.stem}_{int(time.time())}.pdf"
                shutil.copyfile(temp_pdf, output_pdf)
                log.warning(f"[DocxRenderEngine] 目标 PDF 被占用，安全另存为: {output_pdf}")

            log.info(f"[DocxRenderEngine] 成功生成矢量 PDF: {output_pdf}")
            return output_pdf

    @staticmethod
    def extract_preview_images(pdf_file: Path, output_dir: Path, max_pages: int = 2) -> list[Path]:
        """从生成的 PDF 中抽取前 N 页作为前端展示的缩略图 (.jpg)"""
        output_dir.mkdir(parents=True, exist_ok=True)
        preview_paths: list[Path] = []
        if not pdf_file.exists():
            return preview_paths

        doc = fitz.open(pdf_file)
        pages_to_render = min(len(doc), max_pages)
        for i in range(pages_to_render):
            page = doc[i]
            pix = page.get_pixmap(dpi=150)
            img_path = output_dir / f"preview_page_{i + 1}.jpg"
            pix.save(str(img_path))
            preview_paths.append(img_path)

        doc.close()
        log.info(f"[DocxRenderEngine] 成功抽取预览图共 {len(preview_paths)} 张")
        return preview_paths

    @classmethod
    def render_all(
        cls,
        template_file: Path,
        context: dict[str, Any],
        output_dir: Path,
        base_name: str = "exam_paper",
        compile_pdf: bool = True,
        max_previews: int = 2,
    ) -> dict[str, Any]:
        """
        完整执行渲染流程，返回生成的文件字典
        :return: {'docx': Path, 'pdf': Path | None, 'previews': list[Path]}
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        docx_path = output_dir / f"{base_name}.docx"
        docx_path = cls.render_docx(template_file=template_file, context=context, output_docx=docx_path)

        pdf_path = None
        preview_paths = []
        if compile_pdf:
            pdf_path = output_dir / f"{base_name}.pdf"
            actual_pdf = cls.convert_to_pdf(docx_file=docx_path, output_pdf=pdf_path)
            pdf_path = actual_pdf
            preview_paths = cls.extract_preview_images(pdf_file=pdf_path, output_dir=output_dir, max_pages=max_previews)

        return {
            "docx": docx_path,
            "pdf": pdf_path,
            "previews": preview_paths,
        }


docx_render_engine = DocxRenderEngine()
