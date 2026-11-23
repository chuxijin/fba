import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFile } from 'node:fs/promises'
import { importTypeScript } from './helpers/typescript.mjs'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const { applyReportTiming } = await importTypeScript(new URL('../src/adapters/fenbi/report-timing.ts', import.meta.url))
const draft = { duration_seconds: 10, modules: [{ duration_seconds: 10 }], questions: [{ duration_seconds: 10 }] }

test('补录保留各级原计时，实际整卷时间不分配到题目', () => {
  const result = applyReportTiming(draft, true, 7200)
  assert.deepEqual(draft, { duration_seconds: 10, modules: [{ duration_seconds: 10 }], questions: [{ duration_seconds: 10 }] })
  assert.equal(result.exclude_source_timing, true)
  assert.equal(result.manual_duration_seconds, 7200)
  assert.equal(result.modules[0].duration_seconds, 10)
  assert.equal(result.questions[0].duration_seconds, 10)
})
test('未知与真实0区分，关闭开关不修改源计时', () => {
  assert.equal(applyReportTiming(draft, true, '').manual_duration_seconds, null)
  assert.equal(applyReportTiming(draft, true, '0').manual_duration_seconds, 0)
  assert.equal(applyReportTiming(draft, false, '').exclude_source_timing, false)
})
test('实际计时拒绝负数、分数和非数字', () => {
  for (const value of ['-1', '1.5', 'NaN', 'Infinity']) assert.throws(() => applyReportTiming(draft, true, value))
})
test('导入UI脚本与模板编译并包含计时控件', async () => {
  const filename = new URL('../src/content/ui/PracticeReportImport.vue', import.meta.url)
  const source = await readFile(filename, 'utf8')
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'report-timing' })
  assert.match(script.content, /applyReportTiming/)
  const template = compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'report-timing' })
  assert.deepEqual(template.errors, [])
  assert.match(source, /纸上作答／仅补录答案/)
})
