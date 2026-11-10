import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { importTypeScript } from './helpers/typescript.mjs'

const { attachFenbiWrongOccurrences } = await importTypeScript(new URL('../src/adapters/fenbi/wrong-occurrence.ts', import.meta.url))
const { buildWrongImportItems } = await importTypeScript(new URL('../src/adapters/importer.ts', import.meta.url))
const paper = {
  title: '同一张试卷', source_platform: 'fenbi', total_questions: 1,
  sections: [{ name: '言语理解', questions: [{ id: 123, source_question_key: 'fb-q1', stem: '题干', options: ['甲', '乙'], answer: 'A', user_answer: 'A', is_wrong: true }] }],
}
const href = key => `https://spa.fenbi.com/ti/exam/solution/${key}`
function cached(key = '1_1_a', time = 14, updatedTime = Date.UTC(2026, 10, 1)) {
  return {
    solution: { exerciseId: key, userAnswers: { 'fb-q1': { status: -1, answer: { choice: '1' }, time } } },
    history: { exerciseKey: key, updatedTime },
  }
}

test('同一报告同一真实作答同时提供答案与用时，稳定键使用报告而非卷名', () => {
  const before = buildWrongImportItems(paper)
  const built = attachFenbiWrongOccurrences(before, href('1_1_a'), cached())
  assert.equal(built.items[0].wrong_response, 'B')
  assert.equal(built.items[0].external_key, 'fenbi:1_1_a:fb-q1')
  assert.deepEqual(built.items[0].wrong_occurrence, { source_key: '1_1_a', submitted_time: '2026-11-01T00:00:00.000Z', duration_seconds: 14 })
  assert.equal(before.items[0].wrong_response, 'A')
  assert.equal(before.items[0].wrong_occurrence, undefined)
})

test('同卷不同报告再次答错拥有不同幂等键，重读同一报告保持稳定', () => {
  const built = buildWrongImportItems(paper)
  const first = attachFenbiWrongOccurrences(built, href('1_1_a'), cached()).items[0]
  const second = attachFenbiWrongOccurrences(built, href('1_1_b'), cached('1_1_b')).items[0]
  const repeat = attachFenbiWrongOccurrences(built, href('1_1_a'), cached()).items[0]
  assert.notEqual(first.idempotency_key, second.idempotency_key)
  assert.equal(first.idempotency_key, repeat.idempotency_key)
})

test('未知用时/日期保持null，真实零秒保留0，不借别的报告时间', () => {
  const built = buildWrongImportItems(paper)
  for (const time of [null, undefined, '', ' ', -1, 'bad']) {
    const source = cached('1_1_a', time, 0)
    source.solution.userAnswers['fb-q1'].time = time
    assert.deepEqual(attachFenbiWrongOccurrences(built, href('1_1_a'), source).items[0].wrong_occurrence,
      { source_key: '1_1_a', submitted_time: null, duration_seconds: null })
  }
  assert.equal(attachFenbiWrongOccurrences(built, href('1_1_a'), cached('1_1_a', 0)).items[0].wrong_occurrence.duration_seconds, 0)
  const source = cached()
  source.history.exerciseKey = '1_1_other'
  assert.equal(attachFenbiWrongOccurrences(built, href('1_1_a'), source).items[0].wrong_occurrence.submitted_time, null)
})

test('其他报告、正确题、无稳定题号或无真实答案时不制造错误记录', () => {
  const built = buildWrongImportItems(paper)
  assert.equal(attachFenbiWrongOccurrences(built, href('1_1_b'), cached()).items[0].wrong_occurrence, undefined)
  for (const user of [{ status: 1, answer: { choice: '0' }, time: 50 }, { status: -1, time: 50 }]) {
    const source = cached()
    source.solution.userAnswers['fb-q1'] = user
    assert.equal(attachFenbiWrongOccurrences(built, href('1_1_a'), source).items[0].wrong_occurrence, undefined)
  }
  const noIdentity = { ...built, items: [{ ...built.items[0], entry_metadata: { source: '原卷' } }] }
  assert.equal(attachFenbiWrongOccurrences(noIdentity, href('1_1_a'), cached()).items[0].wrong_occurrence, undefined)
  assert.equal(attachFenbiWrongOccurrences(built, 'https://spa.fenbi.com/ti/mistake', cached()).items[0].wrong_occurrence, undefined)
})

test('网页真实导入入口接入同报告的错误上下文', async () => {
  const content = await readFile(new URL('../src/content/index.ts', import.meta.url), 'utf8')
  assert.match(content, /attachFenbiWrongOccurrences\(buildWrongImportItems\(paper\), location\.href, reportCache\.read\(location\.href\)\)/)
})
