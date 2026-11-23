import hashlib
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document
from docxtpl import DocxTemplate, InlineImage
from lxml import etree
from PIL import Image

from backend.plugin.render_book.schema.payload import RenderDocumentPayload
from backend.plugin.render_book.service.adapters.gongkao_adapter import adapt_gongkao_payload
from backend.plugin.render_book.service.adapters.mistake_adapter import adapt_mistake_payload
from backend.plugin.render_book.service.adapters.practice_adapter import adapt_practice_payload
from backend.plugin.render_book.service.docx_engine import DocxRenderEngine, rebind_inline_images
from backend.plugin.render_book.service.image_manager import ImageManager
from backend.plugin.render_book.service.inline_option_content import InlineOptionContent
from backend.plugin.render_book.service.rich_text_parser import parse_option_data
from backend.plugin.render_book.utils.template_catalog import TEMPLATES_ROOT

FIXTURES = Path(__file__).parent / 'fixtures' / 'option_symbols'
FORMULA_URL = 'https://fb.fbstatic.cn/api/planet/accessories/formulas?latex='
ARROW = 'ZTOlaBDvSjUyr1AgzQ77iA'
ROOT_OPTIONS = [
    'dl-0jWuIqdxiTR5JZBuMcZLo9Wal7smW17pARcdoFQc',
    'grGKxJ6Ufu888wRG8Mi56V3Um5OPv8Ymr7IT5v-NwU4',
    'XnySjcIQ3us4hCsHho1OktkAlNd3b3hNUtjxEZUsEyc',
    'JSxt3qd6IS4iRp4EPrl_boYgsTU5lzJNOpN1mlNlGkU',
]
NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


def image_tag(value: str) -> str:
    return f'<img flag="tex" src="//fb.fbstatic.cn/api/planet/accessories/formulas?latex={value}">'


@pytest.fixture
def manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cache = tmp_path / 'cache'
    cache.mkdir()
    for image in FIXTURES.glob('*.png'):
        shutil.copyfile(image, cache / image.name)
    with ImageManager(cache) as instance:
        def forbid_network(*args, **kwargs):
            pytest.fail('符号导出回归必须离线，不得访问 CDN')

        monkeypatch.setattr(instance.client, 'get', forbid_network)
        monkeypatch.setattr('backend.plugin.render_book.service.rich_text_parser.image_manager', instance)
        yield instance


@pytest.mark.parametrize('value', [ARROW, *ROOT_OPTIONS])
def test_real_small_images_are_preserved(value: str, manager: ImageManager, tmp_path: Path) -> None:
    tpl = DocxTemplate(str(tmp_path / 'unused.docx'))
    image = manager.create_inline_image(tpl, FORMULA_URL + value, max_width_mm=30)
    assert isinstance(image, InlineImage)
    with Image.open(image.image_descriptor) as source:
        width, height = source.size
    assert (width, height) == ((18, 9) if value == ARROW else (90, 20))
    assert image.width.mm == pytest.approx(width * 25.4 / 96, abs=0.001)


def test_images_only_shrink_and_keep_aspect_ratio(manager: ImageManager, tmp_path: Path) -> None:
    path = tmp_path / 'diagram.png'
    Image.new('RGB', (1200, 800), 'white').save(path)
    tpl = DocxTemplate(str(tmp_path / 'unused.docx'))
    image = manager.create_inline_image(tpl, str(path), max_width_mm=30, max_height_mm=10)
    assert image is not None
    assert image.width.mm == pytest.approx(15, abs=0.001)


def test_option_preserves_three_arrows_in_order(manager: ImageManager, tmp_path: Path) -> None:
    tpl = DocxTemplate(str(tmp_path / 'unused.docx'))
    html = f'<p>A. 原理 {image_tag(ARROW)} 结构 {image_tag(ARROW)} 功能 {image_tag(ARROW)} 应用</p>'
    option = parse_option_data(html, 'A', tpl, manager)
    assert option['has_img']
    content = option['img']
    assert isinstance(content, InlineOptionContent)
    assert [part if isinstance(part, str) else '图片' for part in content.parts] == [
        '原理 ', '图片', ' 结构 ', '图片', ' 功能 ', '图片', ' 应用',
    ]
    assert option['prefix'] == 'A.'


@pytest.mark.parametrize('html, expected', [
    ('<p>A. 甲→乙 √2</p>', '甲→乙 √2'),
    ('<p>A. 甲<img src="https://cdn/22356dff5dbcdc4c37e6632600979a0e.png">乙</p>', '甲 → 乙'),
    ('<p>A. 甲<img alt="→" src="https://cdn/symbol.png">乙</p>', '甲 → 乙'),
    ('<p>A. &lt;甲&gt; &amp; 乙</p>', '<甲> & 乙'),
])
def test_text_and_known_symbols_do_not_duplicate_images(
    html: str, expected: str, manager: ImageManager, tmp_path: Path,
) -> None:
    tpl = DocxTemplate(str(tmp_path / 'unused.docx'))
    option = parse_option_data(html, 'A', tpl, manager)
    assert option['text'] == expected
    assert option['img'] is None
    assert not option['has_img']


def test_formula_at_start_does_not_remove_later_text(manager: ImageManager, tmp_path: Path) -> None:
    tpl = DocxTemplate(str(tmp_path / 'unused.docx'))
    option = parse_option_data(f'<p>{image_tag(ROOT_OPTIONS[0])} A. 说明</p>', 'A', tpl, manager)
    assert isinstance(option['img'], InlineOptionContent)
    assert isinstance(option['img'].parts[0], InlineImage)
    assert option['img'].parts[1] == ' A. 说明'


def test_unavailable_image_is_not_an_empty_option(
    manager: ImageManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(manager, 'get_local_path', lambda url: None)
    tpl = DocxTemplate(str(tmp_path / 'unused.docx'))
    option = parse_option_data(image_tag(ROOT_OPTIONS[0]), 'A', tpl, manager)
    assert option['text'] == '[图片未能加载]'
    assert option['img'] is None


def test_mixed_content_escapes_xml_and_rebinds_nested_images(manager: ImageManager, tmp_path: Path) -> None:
    template = tmp_path / 'small_template.docx'
    document = Document()
    document.add_paragraph('{{ prefix }} {{ content }}')
    document.save(template)
    old_tpl = DocxTemplate(str(template))
    html = f'<p>A. &lt;甲&gt; &amp; 乙 {image_tag(ARROW)} 丙</p><p>下一行</p>'
    option = parse_option_data(html, 'A', old_tpl, manager)
    new_tpl = DocxTemplate(str(template))
    context = {'prefix': option['prefix'], 'content': option['img']}
    rebind_inline_images(context, new_tpl)
    for part in option['img'].parts:
        if isinstance(part, InlineImage):
            assert part.tpl is new_tpl
    new_tpl.render(context, autoescape=True)
    output = tmp_path / 'small_result.docx'
    new_tpl.save(output)
    rendered = Document(output)
    assert rendered.paragraphs[0].text == 'A. <甲> & 乙  丙\n下一行'
    assert len(rendered.inline_shapes) == 1


def make_payload(template_key: str) -> RenderDocumentPayload:
    arrows = [
        {'key': key, 'content_text': f'<p>{key}. {key}首 {image_tag(ARROW)} {key}中 '
         f'{image_tag(ARROW)} {key}后 {image_tag(ARROW)} {key}末</p>'}
        for key in 'ABCD'
    ]
    roots = [
        {'key': key, 'content_text': f'<p>{image_tag(value)}</p>'}
        for key, value in zip('ABCD', ROOT_OPTIONS, strict=True)
    ]
    return RenderDocumentPayload.model_validate({
        'template_key': template_key,
        'render_plan': {
            'book_kind': 'exam', 'content_mode': 'questions_only', 'answer_layout': None,
            'delivery_mode': 'single_pdf', 'solution_mode': 'none',
            'output_targets': {'question_pdf': True, 'solution_pdf': False},
            'render_variants': ['questions_only'],
        },
        'book': {'title': '行内符号导出定向回归', 'subtitle': '箭头与四个根号选项'},
        'options': {},
        'paper': {
            'question_count': 2,
            'sections': [{'key': 'yanyu', 'title': '言语理解与表达', 'questions': [
                {'number': 1, 'question_id': 106868, 'type': 'single', 'type_label': '单选题',
                 'stem_text': '说明结构顺序测试', 'options': arrows},
                {'number': 2, 'question_id': 106894, 'type': 'single', 'type_label': '单选题',
                 'stem_text': '三层蛋糕体积测试', 'options': roots},
            ]}],
        },
    })


@pytest.mark.parametrize('template_key, filename, adapter', [
    ('gongkao_mistake', 'template.docx', adapt_mistake_payload),
    ('gongkao_practice', 'template.docx', adapt_practice_payload),
    ('gongkao_practice', 'template_questions_only.docx', adapt_practice_payload),
    ('gongkao_xingce', 'template.docx', adapt_gongkao_payload),
])
def test_existing_templates_export_all_arrows_and_four_root_options(
    template_key: str, filename: str, adapter, manager: ImageManager, tmp_path: Path,
) -> None:
    template = TEMPLATES_ROOT / template_key / '1.0.0' / filename
    context = adapter(make_payload(template_key), template_file=template)
    output = tmp_path / f'{template_key}_{filename}'
    DocxRenderEngine.render_docx(template, context, output)
    with ZipFile(output) as archive:
        xml = etree.fromstring(archive.read('word/document.xml'))
        drawings = xml.findall('.//a:blip', NS)
        assert len(drawings) == 16, '四选项各三个箭头，另四个选项各一个完整根号公式'
        media = [name for name in archive.namelist() if name.startswith('word/media/')]
        assert len(media) == 5, '箭头复用一次，四个不同公式各嵌入一次'
        expected_hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in FIXTURES.glob('*.png')}
        assert {hashlib.sha256(archive.read(name)).hexdigest() for name in media} == expected_hashes
        paragraphs = xml.findall('.//w:p', NS)
        for key in 'ABCD':
            matching = [p for p in paragraphs if f'{key}首' in ''.join(p.itertext())]
            assert len(matching) == 1
            paragraph = matching[0]
            pieces = []
            for node in paragraph.iter():
                if node.tag == f'{{{NS["w"]}}}t' and node.text:
                    pieces.append(node.text)
                elif node.tag == f'{{{NS["a"]}}}blip':
                    pieces.append('[图片]')
            assert ''.join(pieces) == f'{key}. {key}首 [图片] {key}中 [图片] {key}后 [图片] {key}末'
