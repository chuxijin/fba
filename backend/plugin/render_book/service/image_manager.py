# -*- coding: utf-8 -*-
"""
题本渲染专用图片下载与自适应缓存管理器
1. 支持公网 CDN 图片本地高效缓存（基于 URL MD5）；
2. 兼容过期 SSL 证书（verify=False）及网络重试兜底；
3. 基于 PIL 智能识别图片尺寸，按版心规格等比自适应缩放；
4. 构造并返回 docxtpl.InlineImage 对象。
"""

import hashlib
import logging
from pathlib import Path
from typing import Any
import httpx
from PIL import Image
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage

logger = logging.getLogger(__name__)

# 统一缓存目录
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output" / "image_cache"
DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class ImageManager:
    """图片下载与缓存管理"""

    def __init__(self, cache_dir: Path | str | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # 使用 verify=False 以兼容证书过期的 CDN
        self.client = httpx.Client(verify=False, timeout=15.0, follow_redirects=True)

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_local_path(self, url: str) -> Path | None:
        """获取本地图片路径，若不存在则下载"""
        if not url or not url.strip():
            return None

        url = url.strip()
        if url.startswith("//"):
            url = f"https:{url}"

        # 智能解密映射：粉笔 fenbike.cn 为私有混淆流，必须替换为 fbstatic.cn 获取标准未加密图片
        if "fenbike.cn" in url:
            url = url.replace("fb.fenbike.cn", "fb.fbstatic.cn").replace("fenbike.cn", "fbstatic.cn")

        # 如果本身就是本地有效文件
        p = Path(url)
        if p.exists() and p.is_file():
            return p

        # 基于 URL 计算 MD5
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        ext = ".png"
        clean_url = url.split("?")[0].lower()
        for candidate_ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
            if clean_url.endswith(candidate_ext):
                ext = candidate_ext
                break

        cache_path = self.cache_dir / f"{url_hash}{ext}"
        if cache_path.exists() and cache_path.stat().st_size > 0:
            # 校验缓存文件完整性，若损坏则删除并重新下载
            try:
                with Image.open(cache_path) as test_img:
                    test_img.verify()
                return cache_path
            except Exception:
                try:
                    cache_path.unlink(missing_ok=True)
                except Exception:
                    pass

        # 尝试下载
        try:
            resp = self.client.get(url)
            if resp.status_code == 200 and resp.content:
                cache_path.write_bytes(resp.content)
                # 下载后二次校验是否为有效图片
                try:
                    with Image.open(cache_path) as test_img:
                        test_img.verify()
                    return cache_path
                except Exception as verify_err:
                    logger.warning(f"下载的图片不是合法图片格式: {url}, 错误: {verify_err}")
                    try:
                        cache_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return None
            else:
                logger.warning(f"下载图片失败 [HTTP {resp.status_code}]: {url}")
                return None
        except Exception as e:
            logger.warning(f"下载图片异常: {url}, 错误: {e}")
            return None

    def create_inline_image(
        self,
        doc: DocxTemplate,
        url: str,
        max_width_mm: float = 135.0,
        max_height_mm: float | None = None,
    ) -> InlineImage | None:
        """
        下载并构造 docxtpl.InlineImage 对象
        :param doc: DocxTemplate 实例
        :param url: 图片公网 URL 或本地路径
        :param max_width_mm: 最大允许宽度（毫米）
        :param max_height_mm: 最大允许高度（毫米，可选）
        """
        local_path = self.get_local_path(url)
        if not local_path or not local_path.exists():
            return None

        try:
            with Image.open(local_path) as img:
                w_px, h_px = img.size
                if w_px <= 0 or h_px <= 0:
                    return None

                # 物理拦截微型字符级图标（如逻辑推导小箭头 18x9、连字符 15x15 等，坚决避免作为独占行大配图渲染）
                if h_px <= 20 or (w_px <= 30 and h_px <= 30):
                    return None

                # 假设 96 DPI 下的自然宽度 (mm = px * 25.4 / 96)
                natural_width_mm = w_px * 25.4 / 96.0
                natural_height_mm = h_px * 25.4 / 96.0

                # 判定最终宽度
                target_width_mm = min(natural_width_mm, max_width_mm)

                # 如果设定了最大高度且超过，按高度再做收缩
                if max_height_mm and natural_height_mm > 0:
                    target_height_mm = target_width_mm * (h_px / w_px)
                    if target_height_mm > max_height_mm:
                        target_width_mm = max_height_mm * (w_px / h_px)

                return InlineImage(doc, str(local_path), width=Mm(target_width_mm))
        except Exception as e:
            logger.warning(f"解析并构造图片失败: {local_path}, 错误: {e}")
            return None


# 单例实例
image_manager = ImageManager()
