#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from io import BytesIO

from playwright.async_api import async_playwright

from backend.app.gongkao.model import GkShiping


class PDFService:
    """PDF 导出服务"""

    @staticmethod
    def _generate_html(shiping: GkShiping) -> str:
        """
        生成用于 PDF 渲染的 HTML

        :param shiping: 时评数据
        :return: HTML 字符串
        """
        content_html = shiping.content or ''
        sidebar_html = shiping.sidebar or ''
        mind_map_md = shiping.mind_map or ''

        # 生成思维导图部分（如果有）
        mindmap_section = ''
        if mind_map_md:
            mindmap_section = f'''
            <div class="page-break"></div>
            <div class="mindmap-page">
                <h2>思维导图</h2>
                <div id="mindmap"></div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
            <script src="https://cdn.jsdelivr.net/npm/markmap-view@0.18.12/dist/browser/index.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/markmap-lib@0.18.12/dist/browser/index.js"></script>
            <script>
                const markdown = {repr(mind_map_md)};
                const {{ Transformer }} = window.markmap;
                const {{ Markmap }} = window.markmapView;
                const transformer = new Transformer();
                const {{ root }} = transformer.transform(markdown);
                const container = document.getElementById('mindmap');
                container.style.width = '100%';
                container.style.height = '800px';
                const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                svg.setAttribute('width', '100%');
                svg.setAttribute('height', '100%');
                container.appendChild(svg);
                Markmap.create(svg, {{}}, root);
            </script>
            '''

        # 右边栏区域
        sidebar_section = ''
        if sidebar_html:
            sidebar_section = f'''
            <div class="sidebar">
                {sidebar_html}
            </div>
            '''

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{shiping.title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: "Microsoft YaHei", "SimHei", sans-serif;
            font-size: 14px;
            line-height: 1.8;
            color: #333;
            padding: 40px;
            background: #fff;
        }}
        .header {{
            border-bottom: 3px solid #c00;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .title {{
            font-size: 24px;
            color: #c00;
            margin-bottom: 10px;
        }}
        .meta {{
            font-size: 13px;
            color: #666;
        }}
        .meta span {{
            margin-right: 20px;
        }}
        .content-wrapper {{
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .content {{
            flex: 1;
            text-align: justify;
        }}
        .content p {{
            text-indent: 2em;
            margin-bottom: 1em;
        }}
        .sidebar {{
            width: 280px;
            flex-shrink: 0;
            background: #fffbe6;
            border: 1px solid #ffe58f;
            border-radius: 4px;
            padding: 15px;
            font-size: 13px;
        }}
        .sidebar p {{
            margin-bottom: 8px;
        }}
        .sidebar hr {{
            border: none;
            border-top: 1px solid #ffe58f;
            margin: 10px 0;
        }}

        /* 标注样式 */
        .golden, .jj {{
            text-decoration: underline;
            text-decoration-color: #c00;
            text-decoration-thickness: 2px;
        }}
        .idiom, .cy {{
            border: 1px solid #c00;
            color: #c00;
            padding: 0 4px;
            border-radius: 2px;
        }}
        .main-point, .zxld {{
            background: #ffccc7;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        .sub-point, .fld {{
            background: #ffd591;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        .evidence, .lj {{
            background: #d9f7be;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        .solution, .dc {{
            background: #bae7ff;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        .case, .al {{
            background: #fffbe6;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        mark {{
            background: #fff3cd;
            padding: 2px 4px;
            border-radius: 3px;
        }}

        .annotation-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            padding: 15px;
            background: #f9f9f9;
            border-top: 1px solid #eee;
            margin-top: 20px;
            font-size: 13px;
        }}
        .annotation-legend span {{
            padding: 2px 8px;
            border-radius: 3px;
        }}
        .annotation-legend .zxld {{ background: #ffccc7; }}
        .annotation-legend .fld {{ background: #ffd591; }}
        .annotation-legend .lj {{ background: #d9f7be; }}
        .annotation-legend .dc {{ background: #bae7ff; }}
        .annotation-legend .al {{ background: #fffbe6; }}
        .annotation-legend .jj {{
            text-decoration: underline;
            text-decoration-color: #c00;
        }}
        .annotation-legend .cy {{
            border: 1px solid #c00;
            color: #c00;
        }}

        .page-break {{
            page-break-before: always;
            margin-top: 40px;
        }}
        .mindmap-page {{
            padding-top: 20px;
        }}
        .mindmap-page h2 {{
            font-size: 20px;
            color: #333;
            margin-bottom: 20px;
            text-align: center;
        }}
        #mindmap {{
            width: 100%;
            min-height: 600px;
        }}

        @media print {{
            body {{
                padding: 20px;
            }}
            .page-break {{
                page-break-before: always;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1 class="title">{shiping.title}</h1>
        <div class="meta">
            {'<span>来源：' + shiping.source + '</span>' if shiping.source else ''}
            {'<span>作者：' + shiping.author + '</span>' if shiping.author else ''}
            {'<span>关键词：' + shiping.keywords + '</span>' if shiping.keywords else ''}
            {'<span>' + str(shiping.daily_date) + '</span>' if shiping.daily_date else ''}
        </div>
    </div>

    <div class="content-wrapper">
        <div class="content">
            {content_html}
        </div>
        {sidebar_section}
    </div>

    <div class="annotation-legend">
        <strong>标注说明：</strong>
        <span class="zxld">中心论点</span>
        <span class="fld">分论点</span>
        <span class="lj">论据</span>
        <span class="dc">对策</span>
        <span class="al">案例</span>
        <span class="jj">金句</span>
        <span class="cy">成语</span>
    </div>

    {mindmap_section}
</body>
</html>'''
        return html

    @staticmethod
    async def export_pdf(shiping: GkShiping) -> bytes:
        """
        导出时评为 PDF

        :param shiping: 时评数据
        :return: PDF 字节数据
        """
        html_content = PDFService._generate_html(shiping)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # 设置 HTML 内容
            await page.set_content(html_content, wait_until='networkidle')

            # 等待思维导图渲染完成（如果有）
            if shiping.mind_map:
                await asyncio.sleep(2)  # 等待 markmap 渲染

            # 生成 PDF
            pdf_bytes = await page.pdf(
                format='A4',
                print_background=True,
                margin={
                    'top': '20mm',
                    'bottom': '20mm',
                    'left': '15mm',
                    'right': '15mm'
                }
            )

            await browser.close()

        return pdf_bytes


pdf_service: PDFService = PDFService()
