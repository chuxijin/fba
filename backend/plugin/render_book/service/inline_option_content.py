from html import escape

from docxtpl import InlineImage


class InlineOptionContent:
    """在已有模板的图片插槽中输出完整选项图文流，不提前生成图片关系。"""

    def __init__(self, parts: list[str | InlineImage]) -> None:
        self.parts = parts

    def __str__(self) -> str:
        # 与 InlineImage 一样，在模板渲染时才生成 DrawingML；文字必须转义，
        # 否则选项中的 <、>、& 会破坏 Word XML，甚至被后续净化器吞掉。
        return ''.join(escape(part, quote=False) if isinstance(part, str) else str(part) for part in self.parts)

    def __html__(self) -> str:
        return str(self)
