import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const { FenbiReportCache } = await importTypeScript(new URL('../src/adapters/fenbi/report-cache.ts', import.meta.url))
const { questionReference, reportReference } = await importTypeScript(new URL('../src/adapters/fenbi/reference.ts', import.meta.url))
const { buildFenbiPracticeQuestions } = await importTypeScript(new URL('../src/adapters/fenbi/report.ts', import.meta.url))
const href = 'https://spa.fenbi.com/ti/exam/solution/5_1_report?routecs=xingce'
const captured = Date.parse('2026-11-18T09:18:40.810Z')
const solution = { exerciseId: '5_1_report', switchVO: { requestKey: 'fixture-key' }, userAnswers: { q1: { status: 1, time: 0, answer: { choice: '0' } } } }
const metaUrl = 'https://tiku.fenbi.com/combine/question/getMeta?requestKey=fixture-key&routecs=xingce'

test('actual meta numbers are already percents; null is not zero and malformed values remain unknown', () => {
  const ref = questionReference({ correctRatio: 51.73736595255701, totalCount: 288051, wrongCount: 0 }, captured)
  assert.equal(ref.correct_ratio_percent, 51.73736595255701)
  assert.equal(ref.wrong_count_raw, 0)
  assert.equal(ref.total_count_raw, 288051)
  assert.equal(ref.captured_at, '2026-11-18T09:18:40.810Z')
  for (const v of [null, undefined, '', ' ', false, {}, -1, 101, Infinity, NaN])
    assert.equal(questionReference({ correctRatio: v }, captured).correct_ratio_percent, null)
  assert.equal(questionReference({ correctRatio: 0 }, captured).correct_ratio_percent, 0)
  assert.equal(questionReference({ correctRatio: 100 }, captured).correct_ratio_percent, 100)
  assert.equal(questionReference({ totalCount: 1.5 }, captured).total_count_raw, null)
})

test('overall statistics use report types rather than array indices; no score/accuracy conflation', () => {
  const ref = reportReference({ subReports: [{ type: 3, average: '60.3', beatRate: '88.3', sigma: 12.208, totalUser: 0 },
    { type: 9 }, { type: 0, difficulty: 5, score: 72.7 }] }, captured)
  assert.equal(ref.average_score, 60.3)
  assert.equal(ref.beat_rate_percent, 88.3)
  assert.equal(ref.difficulty_raw, 5)
  assert.equal(ref.total_user_raw, 0)
  assert.equal(ref.highest_score, null)
  assert.equal(reportReference({ subReports: [] }, captured), null)
})

test('getMeta captured before solution binds by exact requestKey and does not leak foreign keys or credentials', () => {
  const cache = new FenbiReportCache()
  cache.capture(metaUrl, { code: 1, data: { q1: { correctRatio: 51.73736595255701, totalCount: 288051, wrongCount: 0 }, foreign: { correctRatio: 100 } } }, href, captured)
  cache.capture('https://tiku.fenbi.com/combine/exercise/getSolution?key=5_1_report', solution, href, captured)
  const first = cache.read(href)
  assert.deepEqual(Object.keys(first.questionReferences), ['q1'])
  assert.equal(first.questionReferences.q1.correct_ratio_percent, 51.73736595255701)
  assert.equal(first.questionReferences.q1.captured_at, new Date(captured).toISOString())
  assert.doesNotMatch(JSON.stringify(first.questionReferences), /fixture-key|requestKey|cookie|sess/)
  const other = href.replace('5_1_report', '5_1_other')
  cache.capture('https://tiku.fenbi.com/combine/exercise/getSolution?key=5_1_other', { ...solution, exerciseId: '5_1_other', switchVO: { requestKey: 'other-key' } }, other)
  assert.deepEqual(cache.read(other).questionReferences, {})
})

test('cache replay retains original response timestamps and untrusted meta hosts are ignored', () => {
  const cache = new FenbiReportCache()
  cache.capture('https://tiku.fenbi.com/combine/exercise/getSolution?key=5_1_report', solution, href, captured)
  cache.capture(metaUrl.replace('tiku.fenbi.com', 'evil.example'), { q1: { correctRatio: 100 } }, href, captured)
  assert.deepEqual(cache.read(href).questionReferences, {})
  cache.capture(metaUrl, { q1: { correctRatio: 0 } }, href, captured)
  cache.capture(metaUrl, { q1: { correctRatio: 0 } }, href, captured)
  assert.equal(cache.read(href).questionReferences.q1.captured_at, new Date(captured).toISOString())
})

test('real question builder attaches matching statistics without changing answer, order or zero duration', () => {
  const ref = questionReference({ correctRatio: 51.73736595255701, totalCount: 288051 }, captured)
  const questions = buildFenbiPracticeQuestions({ solution, modules: [{ module_name: '数量关系', total_questions: 1, correct_count: 1, duration_seconds: 0 }],
    questionReferences: { q1: ref, foreign: questionReference({ correctRatio: 100 }, captured) },
    staticSolution: { solutions: [{ globalId: 'q1', content: '<p>题干</p>', correctAnswer: { choice: '0' }, accessories: [{ options: ['甲', '乙'] }] }],
      card: { children: [{ name: '数量关系', children: [{ key: 'q1' }] }] } } })
  assert.equal(questions.length, 1)
  assert.equal(questions[0].position, 1)
  assert.equal(questions[0].status, 'correct')
  assert.equal(questions[0].duration_seconds, 0)
  assert.deepEqual(questions[0].platform_reference, ref)
})
