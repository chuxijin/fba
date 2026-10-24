import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const { buildWrongImportItems } = await importTypeScript(new URL('../src/adapters/importer.ts', import.meta.url))

function imported(analysis, extras = {}) {
  return buildWrongImportItems({
    title: '图片回归', source_platform: 'fenbi',
    sections: [{ questions: [{ id: 83710, is_wrong: true, stem: '题干', answer: 'C', analysis, ...extras }] }],
  }).items[0]
}

test('explanation formulas retain inline layout and original pixel dimensions', () => {
  const image = '<img flag="tex" src="//fb.fbstatic.cn/api/planet/accessories/formulas?latex=a" width="63" height="16" class="formula">'
  const result = imported(`解得：${image}，即增长105%。`).explanations[0].content
  assert.match(result, /width="63" height="16"/)
  assert.match(result, /display:inline-block/)
  assert.doesNotMatch(result, /display:block|width:auto|class=/)
  assert.match(result, /解得：<img.*>，即增长105%。/)
})

test('CSS-only small formulas and URL-only formulas work in explanations, stems, options and materials', () => {
  const cssImage = '<IMG src="x.png" style="width:63px;height:16px;display:inline-block">'
  const urlImage = '<img src="https://fb.fbstatic.cn/api/planet/accessories/formulas?latex=a">'
  const result = imported(cssImage, { stem: urlImage, options: [cssImage], material: urlImage })
  assert.match(result.explanations[0].content, /width="63" height="16"/)
  for (const html of [result.stem, result.options[0].content, result.materials[0].content]) {
    assert.match(html, /display:inline-block/)
    assert.match(html, /data-image-layout="inline"/)
  }
  assert.match(result.stem, /flag="tex"/)
})

test('large diagrams remain block images without dropping their dimensions', () => {
  const result = imported('<img src="chart.png" width="900" height="600">').explanations[0].content
  assert.match(result, /display:block/)
  assert.match(result, /width="900" height="600"/)
  assert.match(result, /max-width:100%/)
})
