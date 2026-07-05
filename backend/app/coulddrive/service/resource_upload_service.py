#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid

from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.common.log import log
from backend.plugin.oss.service.storage_service import storage_service
from backend.utils.pdf_preview import DEFAULT_PDF_PREVIEW_JPEG_QUALITY
from backend.utils.pdf_preview import DEFAULT_PDF_PREVIEW_MAX_SIDE
from backend.utils.pdf_preview import DEFAULT_PDF_PREVIEW_PAGE_COUNT
from backend.utils.pdf_preview import render_pdf_preview_images
from backend.utils.timezone import timezone

IMAGE_EXTENSIONS = {'bmp', 'gif', 'jpeg', 'jpg', 'png', 'webp'}
PDF_EXTENSION = 'pdf'
THUMBNAIL_VARIANTS = (
    {'name': 'cover', 'max_side': 960},
    {'name': 'medium', 'max_side': 640},
    {'name': 'small', 'max_side': 320},
)
MAX_THUMBNAIL_SOURCE_BYTES = 30 * 1024 * 1024
MAX_RESOURCE_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_RESOURCE_UPLOAD_MB = 5
MAX_PREVIEW_SOURCE_BYTES = 100 * 1024 * 1024
MAX_PREVIEW_SOURCE_MB = 100


class ResourceUploadSizeError(ValueError):
    """资源上传文件大小异常"""


class ResourceUploadTypeError(ValueError):
    """资源上传文件类型异常"""


class ResourceUploadService:
    """资源上传服务"""

    async def upload_file(self, *, db: AsyncSession, file: UploadFile) -> dict[str, Any]:
        """
        上传资源文件并生成缩略图

        :param db: 数据库会话
        :param file: 文件对象
        :return:
        """
        await self._validate_upload_size(file)

        filename = self._normalize_original_filename(file.filename)
        extension = self._get_extension(filename)
        today = timezone.now().strftime('%Y%m%d')
        object_basename = self._build_object_basename(filename)
        upload_path = f'resources/{today}'
        object_filename = f'{object_basename}.{extension}' if extension else object_basename

        uploaded_url, object_key = await storage_service.upload_with_filename(
            db=db,
            file=file,
            filename=object_filename,
            path=upload_path,
            use_signed_url=False,
        )

        thumbnails = await self._create_thumbnails(
            db=db,
            file=file,
            filename=filename,
            extension=extension,
            object_basename=object_basename,
            upload_path=upload_path,
        )
        thumbnail_urls = [item['url'] for item in thumbnails if item.get('url')]
        resource_images = thumbnail_urls or [uploaded_url]

        return {
            'url': uploaded_url,
            'storage_key': object_key,
            'filename': filename,
            'file_type': extension,
            'resource_image': resource_images,
            'thumbnail_urls': resource_images,
            'thumbnails': thumbnails,
        }

    async def upload_pdf_previews(
        self,
        *,
        db: AsyncSession,
        file: UploadFile,
        page_count: int = DEFAULT_PDF_PREVIEW_PAGE_COUNT,
        max_side: int = DEFAULT_PDF_PREVIEW_MAX_SIDE,
        quality: int = DEFAULT_PDF_PREVIEW_JPEG_QUALITY,
    ) -> dict[str, Any]:
        """
        上传 PDF 预览图但不保存原文件

        :param db: 数据库会话
        :param file: 文件对象
        :param page_count: 最大渲染页数
        :param max_side: 图片最长边像素
        :param quality: JPEG 质量
        :return:
        """
        filename = self._normalize_original_filename(file.filename)
        extension = self._get_extension(filename)
        if extension != PDF_EXTENSION:
            raise ResourceUploadTypeError('只支持上传 PDF 生成缩略图')

        content = await self._read_limited_upload_content(
            file=file,
            limit_bytes=MAX_PREVIEW_SOURCE_BYTES,
            limit_mb=MAX_PREVIEW_SOURCE_MB,
        )
        today = timezone.now().strftime('%Y%m%d')
        object_basename = self._build_object_basename(filename)
        upload_path = f'resources/{today}/previews'
        payloads = self._build_pdf_preview_payloads(
            content,
            object_basename,
            page_count=page_count,
            max_side=max_side,
            quality=quality,
        )
        thumbnails = await self._upload_thumbnail_payloads(
            db=db,
            payloads=payloads,
            upload_path=upload_path,
        )
        thumbnail_urls = [item['url'] for item in thumbnails if item.get('url')]

        return {
            'filename': filename,
            'file_type': extension,
            'resource_image': thumbnail_urls,
            'thumbnail_urls': thumbnail_urls,
            'thumbnails': thumbnails,
        }

    @staticmethod
    async def _validate_upload_size(file: UploadFile) -> None:
        """
        校验资源文件上传大小

        :param file: 文件对象
        :return:
        """
        file_size = getattr(file, 'size', None)
        if isinstance(file_size, int):
            if file_size > MAX_RESOURCE_UPLOAD_BYTES:
                raise ResourceUploadSizeError(f'资源文件大小不能超过 {MAX_RESOURCE_UPLOAD_MB}MB')
            return

        await file.seek(0)
        content = await file.read(MAX_RESOURCE_UPLOAD_BYTES + 1)
        await file.seek(0)

        if len(content) > MAX_RESOURCE_UPLOAD_BYTES:
            raise ResourceUploadSizeError(f'资源文件大小不能超过 {MAX_RESOURCE_UPLOAD_MB}MB')

    @staticmethod
    async def _read_limited_upload_content(
        *,
        file: UploadFile,
        limit_bytes: int,
        limit_mb: int,
    ) -> bytes:
        """
        读取有限大小的上传内容

        :param file: 文件对象
        :param limit_bytes: 最大字节数
        :param limit_mb: 最大 MB 数
        :return:
        """
        file_size = getattr(file, 'size', None)
        if isinstance(file_size, int) and file_size > limit_bytes:
            raise ResourceUploadSizeError(f'上传文件大小不能超过 {limit_mb}MB')

        await file.seek(0)
        content = await file.read(limit_bytes + 1)
        await file.seek(0)

        if len(content) > limit_bytes:
            raise ResourceUploadSizeError(f'上传文件大小不能超过 {limit_mb}MB')
        return content

    async def _create_thumbnails(
        self,
        *,
        db: AsyncSession,
        file: UploadFile,
        filename: str,
        extension: str,
        object_basename: str,
        upload_path: str,
    ) -> list[dict[str, Any]]:
        """
        创建并上传缩略图

        :param db: 数据库会话
        :param file: 文件对象
        :param filename: 原始文件名
        :param extension: 文件扩展名
        :param object_basename: 对象基础名
        :param upload_path: 上传目录
        :return:
        """
        payloads = await self._build_thumbnail_payloads(
            file=file,
            filename=filename,
            extension=extension,
            object_basename=object_basename,
        )
        if not payloads:
            return []

        thumbnail_path = f'{upload_path}/thumbnails'
        return await self._upload_thumbnail_payloads(
            db=db,
            payloads=payloads,
            upload_path=thumbnail_path,
        )

    @staticmethod
    async def _upload_thumbnail_payloads(
        *,
        db: AsyncSession,
        payloads: list[dict[str, Any]],
        upload_path: str,
    ) -> list[dict[str, Any]]:
        """
        上传缩略图载荷

        :param db: 数据库会话
        :param payloads: 缩略图载荷
        :param upload_path: 上传目录
        :return:
        """
        results: list[dict[str, Any]] = []
        for payload in payloads:
            upload_file = UploadFile(file=BytesIO(payload['content']), filename=payload['filename'])
            url, object_key = await storage_service.upload_with_filename(
                db=db,
                file=upload_file,
                filename=payload['filename'],
                path=upload_path,
                use_signed_url=False,
            )
            results.append({
                'url': url,
                'storage_key': object_key,
                'variant': payload['variant'],
                'width': payload['width'],
                'height': payload['height'],
                'source': payload['source'],
            })

        return results

    async def _build_thumbnail_payloads(
        self,
        *,
        file: UploadFile,
        filename: str,
        extension: str,
        object_basename: str,
    ) -> list[dict[str, Any]]:
        """
        构建缩略图上传载荷

        :param file: 文件对象
        :param filename: 原始文件名
        :param extension: 文件扩展名
        :param object_basename: 对象基础名
        :return:
        """
        if extension in IMAGE_EXTENSIONS:
            content = await self._read_thumbnail_source(file)
            if content:
                try:
                    return await run_in_threadpool(
                        self._build_image_thumbnail_payloads,
                        content,
                        object_basename,
                    )
                except UnidentifiedImageError:
                    log.warning(f'资源图片缩略图生成失败，无法识别图片: {filename}')
                except Exception as exc:
                    log.warning(f'资源图片缩略图生成失败: {filename}, {exc!s}')

        if extension == PDF_EXTENSION:
            content = await self._read_thumbnail_source(file)
            if content:
                try:
                    payloads = await run_in_threadpool(
                        self._build_pdf_preview_payloads,
                        content,
                        object_basename,
                    )
                    if payloads:
                        return payloads
                except Exception as exc:
                    log.warning(f'资源 PDF 预览图生成失败，回退占位图: {filename}, {exc!s}')

        return await run_in_threadpool(
            self._build_placeholder_thumbnail_payloads,
            filename,
            extension,
            object_basename,
        )

    @staticmethod
    async def _read_thumbnail_source(file: UploadFile) -> bytes | None:
        """
        读取缩略图源数据

        :param file: 文件对象
        :return:
        """
        file_size = getattr(file, 'size', None)
        if isinstance(file_size, int) and file_size > MAX_THUMBNAIL_SOURCE_BYTES:
            return None

        await file.seek(0)
        content = await file.read(MAX_THUMBNAIL_SOURCE_BYTES + 1)
        await file.seek(0)

        if len(content) > MAX_THUMBNAIL_SOURCE_BYTES:
            return None
        return content

    @staticmethod
    def _build_pdf_preview_payloads(
        content: bytes,
        object_basename: str,
        page_count: int = DEFAULT_PDF_PREVIEW_PAGE_COUNT,
        max_side: int = DEFAULT_PDF_PREVIEW_MAX_SIDE,
        quality: int = DEFAULT_PDF_PREVIEW_JPEG_QUALITY,
    ) -> list[dict[str, Any]]:
        """
        基于 PDF 前几页生成预览图载荷

        :param content: PDF 内容
        :param object_basename: 对象基础名
        :param page_count: 最大渲染页数
        :param max_side: 图片最长边像素
        :param quality: JPEG 质量
        :return:
        """
        payloads: list[dict[str, Any]] = []
        preview_images = render_pdf_preview_images(
            content=content,
            page_count=page_count,
            max_side=max_side,
            quality=quality,
        )
        for preview_image in preview_images:
            payloads.append({
                'filename': f'{object_basename}_page_{preview_image.page_no}.jpg',
                'content': preview_image.content,
                'variant': f'page_{preview_image.page_no}',
                'width': preview_image.width,
                'height': preview_image.height,
                'source': 'pdf',
            })

        return payloads

    @staticmethod
    def _build_image_thumbnail_payloads(content: bytes, object_basename: str) -> list[dict[str, Any]]:
        """
        基于图片内容生成缩略图载荷

        :param content: 图片内容
        :param object_basename: 对象基础名
        :return:
        """
        with Image.open(BytesIO(content)) as source_image:
            image = ImageOps.exif_transpose(source_image)
            image = ResourceUploadService._to_rgb_image(image)
            payloads: list[dict[str, Any]] = []

            for variant in THUMBNAIL_VARIANTS:
                max_side = int(variant['max_side'])
                thumbnail = image.copy()
                thumbnail.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
                payloads.append(
                    ResourceUploadService._encode_jpeg_payload(
                        image=thumbnail,
                        object_basename=object_basename,
                        variant=str(variant['name']),
                        source='image',
                    )
                )

            return payloads

    @staticmethod
    def _build_placeholder_thumbnail_payloads(
        filename: str,
        extension: str,
        object_basename: str,
    ) -> list[dict[str, Any]]:
        """
        为非图片文件生成占位缩略图载荷

        :param filename: 原始文件名
        :param extension: 文件扩展名
        :param object_basename: 对象基础名
        :return:
        """
        payloads: list[dict[str, Any]] = []
        file_label = extension.upper() if extension else 'FILE'
        base_title = Path(filename).stem[:36] or 'Resource File'

        for variant in THUMBNAIL_VARIANTS:
            width = int(variant['max_side'])
            height = int(width * 0.56)
            image = Image.new('RGB', (width, height), ResourceUploadService._file_card_color(extension))
            draw = ImageDraw.Draw(image)

            ResourceUploadService._draw_file_card(
                draw=draw,
                width=width,
                height=height,
                file_label=file_label,
                title=base_title,
            )
            payloads.append(
                ResourceUploadService._encode_jpeg_payload(
                    image=image,
                    object_basename=object_basename,
                    variant=str(variant['name']),
                    source='placeholder',
                )
            )

        return payloads

    @staticmethod
    def _draw_file_card(
        *,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        file_label: str,
        title: str,
    ) -> None:
        """
        绘制文件占位卡片

        :param draw: 绘图对象
        :param width: 宽度
        :param height: 高度
        :param file_label: 文件类型标签
        :param title: 文件标题
        :return:
        """
        margin = max(24, width // 18)
        badge_width = max(width // 3, 140)
        badge_height = max(height // 3, 72)
        badge_box = (margin, margin, margin + badge_width, margin + badge_height)
        draw.rounded_rectangle(badge_box, radius=max(14, width // 48), fill=(255, 255, 255))

        label_font = ResourceUploadService._load_font(max(28, width // 12), bold=True)
        title_font = ResourceUploadService._load_font(max(18, width // 28))
        meta_font = ResourceUploadService._load_font(max(14, width // 42))

        ResourceUploadService._draw_centered_text(
            draw=draw,
            box=badge_box,
            text=file_label[:8],
            font=label_font,
            fill=(28, 35, 43),
        )

        title_y = margin + badge_height + max(24, height // 12)
        draw.text((margin, title_y), title, fill=(255, 255, 255), font=title_font)
        draw.text((margin, height - margin - max(20, height // 18)), 'RESOURCE FILE', fill=(240, 244, 248), font=meta_font)

    @staticmethod
    def _draw_centered_text(
        *,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        text: str,
        font: ImageFont.ImageFont,
        fill: tuple[int, int, int],
    ) -> None:
        """
        在矩形区域居中文本

        :param draw: 绘图对象
        :param box: 文本区域
        :param text: 文本内容
        :param font: 字体
        :param fill: 填充色
        :return:
        """
        text_box = draw.textbbox((0, 0), text, font=font)
        text_width = text_box[2] - text_box[0]
        text_height = text_box[3] - text_box[1]
        x = box[0] + (box[2] - box[0] - text_width) / 2
        y = box[1] + (box[3] - box[1] - text_height) / 2
        draw.text((x, y), text, fill=fill, font=font)

    @staticmethod
    def _encode_jpeg_payload(
        *,
        image: Image.Image,
        object_basename: str,
        variant: str,
        source: str,
    ) -> dict[str, Any]:
        """
        编码 JPEG 缩略图载荷

        :param image: 图片对象
        :param object_basename: 对象基础名
        :param variant: 缩略图变体
        :param source: 缩略图来源
        :return:
        """
        output = BytesIO()
        image.save(output, format='JPEG', quality=86, optimize=True)
        content = output.getvalue()
        return {
            'filename': f'{object_basename}_{variant}.jpg',
            'content': content,
            'variant': variant,
            'width': image.width,
            'height': image.height,
            'source': source,
        }

    @staticmethod
    def _to_rgb_image(image: Image.Image) -> Image.Image:
        """
        转换为 RGB 图片

        :param image: 图片对象
        :return:
        """
        if image.mode == 'RGB':
            return image.copy()

        converted = image.convert('RGBA')
        background = Image.new('RGBA', converted.size, (255, 255, 255, 255))
        background.alpha_composite(converted)
        return background.convert('RGB')

    @staticmethod
    def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
        """
        加载字体

        :param size: 字号
        :param bold: 是否加粗
        :return:
        """
        font_candidates = (
            'DejaVuSans-Bold.ttf',
            'Arial Bold.ttf',
        ) if bold else (
            'DejaVuSans.ttf',
            'Arial.ttf',
        )
        for font_name in font_candidates:
            try:
                return ImageFont.truetype(font_name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _file_card_color(extension: str) -> tuple[int, int, int]:
        """
        获取文件卡片背景色

        :param extension: 文件扩展名
        :return:
        """
        color_map = {
            'pdf': (221, 61, 72),
            'doc': (54, 101, 196),
            'docx': (54, 101, 196),
            'xls': (28, 142, 78),
            'xlsx': (28, 142, 78),
            'ppt': (216, 96, 54),
            'pptx': (216, 96, 54),
            'zip': (111, 78, 55),
            'rar': (111, 78, 55),
            '7z': (111, 78, 55),
            'mp4': (88, 86, 214),
            'mov': (88, 86, 214),
            'avi': (88, 86, 214),
        }
        return color_map.get(extension, (37, 99, 235))

    @staticmethod
    def _normalize_original_filename(filename: str | None) -> str:
        """
        归一化原始文件名

        :param filename: 原始文件名
        :return:
        """
        value = str(filename or '').replace('\\', '/').split('/')[-1].strip()
        return value or 'resource-file'

    @staticmethod
    def _get_extension(filename: str) -> str:
        """
        获取文件扩展名

        :param filename: 文件名
        :return:
        """
        if '.' not in filename:
            return ''
        return filename.rsplit('.', 1)[-1].lower().strip()

    @staticmethod
    def _build_object_basename(filename: str) -> str:
        """
        构建对象基础名

        :param filename: 文件名
        :return:
        """
        stem = filename.rsplit('.', 1)[0] if '.' in filename else filename
        stem = stem.strip() or 'resource'
        return f'{stem}_{uuid.uuid4().hex[:8]}'


resource_upload_service = ResourceUploadService()
