from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image

DEFAULT_PDF_PREVIEW_PAGE_COUNT = 3
DEFAULT_PDF_PREVIEW_MAX_SIDE = 960
DEFAULT_PDF_PREVIEW_JPEG_QUALITY = 86


@dataclass(slots=True)
class PdfPreviewImage:
    """PDF 预览图"""

    page_no: int
    content: bytes
    width: int
    height: int
    content_type: str = 'image/jpeg'


def render_pdf_preview_images(
    *,
    content: bytes,
    page_count: int = DEFAULT_PDF_PREVIEW_PAGE_COUNT,
    max_side: int = DEFAULT_PDF_PREVIEW_MAX_SIDE,
    quality: int = DEFAULT_PDF_PREVIEW_JPEG_QUALITY,
) -> list[PdfPreviewImage]:
    """
    渲染 PDF 前几页为 JPEG 预览图

    :param content: PDF 文件内容
    :param page_count: 最大渲染页数
    :param max_side: 图片最长边像素
    :param quality: JPEG 质量
    :return:
    """
    _validate_preview_options(page_count=page_count, max_side=max_side, quality=quality)

    fitz = _load_pymupdf()
    images: list[PdfPreviewImage] = []

    with fitz.open(stream=content, filetype='pdf') as document:
        if document.is_encrypted:
            return []

        resolved_page_count = min(page_count, document.page_count)
        for page_index in range(resolved_page_count):
            page = document.load_page(page_index)
            image = _render_pdf_page_to_image(fitz=fitz, page=page, max_side=max_side)
            image_content = _encode_image_to_jpeg(image=image, quality=quality)
            images.append(
                PdfPreviewImage(
                    page_no=page_index + 1,
                    content=image_content,
                    width=image.width,
                    height=image.height,
                )
            )

    return images


def _validate_preview_options(*, page_count: int, max_side: int, quality: int) -> None:
    """
    校验 PDF 预览参数

    :param page_count: 最大渲染页数
    :param max_side: 图片最长边像素
    :param quality: JPEG 质量
    :return:
    """
    if page_count <= 0:
        raise ValueError('PDF 预览页数必须大于 0')

    if max_side <= 0:
        raise ValueError('PDF 预览图片最长边必须大于 0')

    if quality < 1 or quality > 95:
        raise ValueError('PDF 预览 JPEG 质量必须在 1 到 95 之间')


def _load_pymupdf() -> Any:
    """加载 PyMuPDF"""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError('PyMuPDF 未安装，无法生成 PDF 预览图') from exc
    return fitz


def _render_pdf_page_to_image(*, fitz: Any, page: Any, max_side: int) -> Image.Image:
    """
    渲染 PDF 页面为图片

    :param fitz: PyMuPDF 模块
    :param page: PDF 页面
    :param max_side: 图片最长边像素
    :return:
    """
    page_rect = page.rect
    max_dimension = max(float(page_rect.width), float(page_rect.height), 1.0)
    zoom = max_side / max_dimension
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = Image.frombytes('RGB', (pixmap.width, pixmap.height), pixmap.samples)
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return image


def _encode_image_to_jpeg(*, image: Image.Image, quality: int) -> bytes:
    """
    编码图片为 JPEG

    :param image: 图片对象
    :param quality: JPEG 质量
    :return:
    """
    output = BytesIO()
    image.save(output, format='JPEG', quality=quality, optimize=True)
    return output.getvalue()
