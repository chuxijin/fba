import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const { normalizeFenbiQuestion } = await importTypeScript(
  new URL('../src/adapters/fenbi/normalize.ts', import.meta.url),
)
const { buildFenbiPracticeQuestions } = await importTypeScript(
  new URL('../src/adapters/fenbi/report.ts', import.meta.url),
)
const { buildWrongImportItems } = await importTypeScript(
  new URL('../src/adapters/importer.ts', import.meta.url),
)

const settings = {
  includeAnswer: true,
  answerPlacement: 'merged',
  outputFormat: 'pdf',
  boldNegativeQuestion: true,
}

/**
 * 两个入口共同消费的同一份粉笔原始题。
 * parity 断言必须始终使用同一个对象，禁止用不同题/不同选项凑等价。
 */
function rawQuestion(overrides = {}) {
  return {
    globalId: 'fb-q1',
    id: 1001,
    content: '<p>下列说法正确的是（ ）。</p>',
    accessories: [{ type: 101, options: ['甲', '乙', '丙', '丁'] }],
    correctAnswer: { choice: '0' },
    solution: '<p>解析</p>',
    keypoints: [{ name: '常识判断' }],
    ...overrides,
  }
}

/** 入口一：normalizeFenbiQuestion -> UnifiedPaper -> buildWrongImportItems */
function wrongImportItem(raw) {
  const question = normalizeFenbiQuestion(raw, 1, settings)
  question.is_wrong = true
  const result = buildWrongImportItems({
    title: '入口一致性回归',
    source_platform: 'fenbi',
    sections: [{ name: '常识判断', questions: [question] }],
  })
  assert.equal(result.skipped.length, 0, '同一道原始题不应被错题入口跳过')
  assert.equal(result.items.length, 1, '同一道原始题应产出且只产出一条错题导入项')
  return result.items[0]
}

/** 入口二：buildFenbiPracticeQuestions（报告/记录导入） */
function practiceQuestion(raw, { time, userChoice = '0' } = {}) {
  const key = raw.globalId
  const staticSolution = {
    card: { children: [{ name: '常识判断', children: [{ key, materialKeys: [] }] }] },
    materials: [],
    solutions: [raw],
  }
  const solution = {
    exerciseId: 'e1',
    userAnswers: { [key]: { status: 0, time, answer: { choice: userChoice } } },
  }
  const details = [{ name: '常识判断', children: [] }]
  const modules = [
    { module_name: '常识判断', total_questions: 1, correct_count: 0, duration_seconds: 10, children: [] },
  ]
  const questions = buildFenbiPracticeQuestions({ solution, staticSolution, details, modules })
  assert.equal(questions.length, 1, '同一道原始题应产出且只产出一条记录导入项')
  assert.equal(questions[0].source_question_key, key, '两个入口必须指向同一道原始题')
  return questions[0]
}

function optionPairs(item) {
  return item.options.map((option) => [option.option_code, option.content])
}

function assertEntryParity(raw) {
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw)
  // 先确认比较的是同一道题，再比较归一化结果
  assert.match(wrong.external_key, new RegExp(`:${raw.id}$`))
  assert.equal(wrong.stem, practice.stem, '两入口题干必须等价')
  assert.deepEqual(optionPairs(wrong), optionPairs(practice), '两入口选项必须等价')
  assert.equal(wrong.question_type, practice.question_type, '两入口题型必须等价')
  return { wrong, practice }
}

test('entry parity: plain stem and options keep the same normalized content', () => {
  assertEntryParity(rawQuestion())
})

test('entry parity: negative-question bold is visual only and never leaks into imported stem', () => {
  const { wrong, practice } = assertEntryParity(
    rawQuestion({ content: '<p>下列说法不正确的是（ ）。</p>' }),
  )
  assert.equal(wrong.stem, '<p>下列说法不正确的是（ ）。</p>')
  assert.equal(practice.stem, '<p>下列说法不正确的是（ ）。</p>')
})

test('entry parity: fill-in underlines normalize to the same blanks', () => {
  assertEntryParity(rawQuestion({ content: '<p>发展生态。<u>&nbsp;&nbsp;</u>。</p>' }))
})

test('entry parity: inline arrow icons normalize to the same glyph', () => {
  assertEntryParity(rawQuestion({ content: '<p>甲<img src="/static/arrow.png">乙</p>' }))
})

test('entry parity: option prefixes are stripped by both entry points', () => {
  assertEntryParity(
    rawQuestion({ accessories: [{ type: 101, options: ['A. 甲', 'B、乙', 'C：丙', 'D 丁'] }] }),
  )
})

test('entry parity: formula images in the stem normalize identically', () => {
  assertEntryParity(
    rawQuestion({ content: '<p>求值 <img flag="tex" src="//fb.fenbi.cn/formulas?latex=x%2B1" />。</p>' }),
  )
})

test('entry parity: formula images in an option normalize identically', () => {
  assertEntryParity(
    rawQuestion({
      accessories: [
        { type: 101, options: ['<img flag="tex" src="//fb.fenbi.cn/formulas?latex=a" />', '乙', '丙', '丁'] },
      ],
    }),
  )
})

test('entry parity: sized/classed images normalize identically', () => {
  assertEntryParity(
    rawQuestion({
      content: '<p>图<img class="lazy" src="//fbstatic.cn/a.png" style="width:640px;height:480px" /></p>',
    }),
  )
})

test('entry parity: multi-select keeps the same type and letter answer codes', () => {
  const raw = rawQuestion({ correctAnswer: { choice: '0,1' } })
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw, { userChoice: '0,1' })
  assert.equal(wrong.question_type, 'multiple_choice')
  assert.equal(practice.question_type, 'multiple_choice')
  assert.deepEqual(optionPairs(wrong), optionPairs(practice))
  assert.deepEqual(
    wrong.answer.answer_data.correct,
    practice.answer.answer_data.correct,
    '同一道多选题的答案编码必须一致（alpha codes）',
  )
})

test('entry parity: english answer text, AB and A+B options are not truncated by the prefix regex', () => {
  const raw = rawQuestion({
    accessories: [{ type: 101, options: ['Answer A', 'AB', 'A+B', 'D'] }],
  })
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw)
  const expected = ['A', 'B', 'C', 'D'].map((code, index) => [code, ['Answer A', 'AB', 'A+B', 'D'][index]])
  assert.deepEqual(optionPairs(wrong), expected, '英文文案/连续字母/数学表达式不能被选项前缀正则吞掉首字母')
  assert.deepEqual(optionPairs(practice), optionPairs(wrong), '两入口必须保留同样的选项原文')
})

test('entry parity: arithmetic option bodies never lose their leading letter', () => {
  const options = ['A + B', 'A   + B', 'A - B', 'A / B', 'A = B', 'A × B', 'A ÷ B', 'A ^ B']
  const raw = rawQuestion({ accessories: [{ type: 101, options }] })
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw)
  const expected = options.map((text, index) => ['ABCDEFGH'[index], text])
  assert.deepEqual(optionPairs(wrong), expected, '数学表达式的首字母不能被选项前缀正则吞掉')
  assert.deepEqual(optionPairs(practice), expected, '两个入口都必须保留数学选项原文')
})

test('entry parity: option prefix strip only removes the letter equal to the option code', () => {
  const options = ['B + C', 'A + B', 'D / E', 'C = D']
  const raw = rawQuestion({ accessories: [{ type: 101, options }] })
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw)
  const expected = options.map((text, index) => ['ABCD'[index], text])
  assert.deepEqual(optionPairs(wrong), expected, '只有与选项 code 一致的字母才可作为前缀移除')
  assert.deepEqual(optionPairs(practice), optionPairs(wrong))
})

test('entry parity: genuine code prefixes still strip while math bodies stay intact', () => {
  const options = ['A. 甲', 'B   + 乙', 'C：丙', 'D 丁']
  const raw = rawQuestion({ accessories: [{ type: 101, options }] })
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw)
  const expected = [['A', '甲'], ['B', 'B   + 乙'], ['C', '丙'], ['D', '丁']]
  assert.deepEqual(optionPairs(wrong), expected, '真实选项前缀照常剥离，运算符前的字母保留')
  assert.deepEqual(optionPairs(practice), expected)
})

test('entry parity: real text inside <u> is preserved instead of becoming a blank', () => {
  const raw = rawQuestion({ content: '<p>发展生态。<u>重点</u>是（ ）。</p>' })
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw)
  for (const stem of [wrong.stem, practice.stem]) {
    assert.match(stem, /<u>重点<\/u>/, '<u> 内的真实文字必须保留')
    assert.doesNotMatch(stem, /______/, '真实文字不能被当成填空占位符')
  }
  assert.equal(wrong.stem, practice.stem)
})

test('entry parity: arrow and dash option icons normalize to the same glyphs', () => {
  const raw = rawQuestion({
    accessories: [
      {
        type: 101,
        options: [
          '甲<img src="/static/arrow.png">乙',
          '丙<img src="/static/dash.png">丁',
          '戊',
          '己',
        ],
      },
    ],
  })
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw)
  assert.deepEqual(optionPairs(wrong), optionPairs(practice))
  assert.match(wrong.options[0].content, /→/, '箭头图标应转为箭头字符')
  assert.match(wrong.options[1].content, /—/, '短横图标应转为短横字符')
})

test('entry parity: raw array multi-select answers become the same letter set', () => {
  const raw = rawQuestion({
    correctAnswer: { choice: [0, 1] },
    userAnswer: { choice: [0, 1] },
  })
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw, { userChoice: [0, 1] })
  assert.equal(wrong.question_type, 'multiple_choice')
  assert.equal(practice.question_type, 'multiple_choice')
  assert.deepEqual(wrong.answer.answer_data.correct, ['A', 'B'])
  assert.deepEqual(practice.answer.answer_data.correct, ['A', 'B'])
  assert.deepEqual(wrong.wrong_response, ['A', 'B'])
  assert.deepEqual(practice.response_data, ['A', 'B'])
})

// ---------- 逐题用时只来自真实练习报告；独立错题快照不伪造作答事实 ----------

function practiceDuration(time) {
  return practiceQuestion(rawQuestion(), { time }).duration_seconds
}

test('practice entry: missing per-question time is null for undefined/null/empty string', (t) => {
  for (const missing of [undefined, null, '']) {
    t.diagnostic(`input=${JSON.stringify(missing)} -> ${JSON.stringify(practiceDuration(missing))}`)
    assert.equal(practiceDuration(missing), null, `time=${JSON.stringify(missing)} 必须为 null，不能变成 0`)
  }
})

test('practice entry: real zero seconds stays zero and is never confused with missing', () => {
  for (const zero of [0, '0', ' 0 ']) {
    assert.equal(practiceDuration(zero), 0, `time=${JSON.stringify(zero)} 必须为 0`)
  }
})

test('practice entry: non-finite or negative time is unknown instead of zero', () => {
  for (const invalid of [NaN, Infinity, -1, 'abc']) {
    assert.equal(practiceDuration(invalid), null, `time=${JSON.stringify(invalid)} 必须为 null`)
  }
})

test('practice entry: fractional seconds are rounded, never NaN-coerced', () => {
  assert.equal(practiceDuration(12.6), 13)
  assert.equal(practiceDuration(' 7 '), 7)
})

test('wrong import entry: standalone snapshot never fabricates timing or practice identity', () => {
  const wrong = wrongImportItem(rawQuestion())
  for (const field of [
    'duration_seconds',
    'duration_ms',
    'status',
    'response_data',
    'score',
    'max_score',
    'source_question_key',
    'session_id',
  ]) {
    assert.equal(field in wrong, false, `独立错题快照不得携带 ${field}`)
  }
})

test('practice report: the same raw question carries real 0 and 30 second timings', () => {
  const raw = rawQuestion()
  assert.equal(practiceQuestion(raw, { time: 0 }).duration_seconds, 0)
  assert.equal(practiceQuestion(raw, { time: 30 }).duration_seconds, 30)
})

test('wrong import entry: keeps the real wrong response and matches the same original question number', () => {
  const raw = rawQuestion({ userAnswer: { choice: '1' } })
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw, { time: 30 })
  assert.equal(wrong.order, 1, '错题保留原站题号')
  assert.equal(practice.position, 1, '报告按原站题号对齐')
  assert.equal(wrong.wrong_response, 'B', '错题快照保留当次错答')
  assert.equal(wrong.stem, practice.stem, '复盘可按题号+内容关联同一道题')
  assert.match(wrong.external_key, /:1001$/)
})

// ---------- source_question_key 必须来自原始稳定标识，两入口保持一致 ----------

test('entry parity: raw globalId and numeric id differ, both entries keep the normalizer source key', () => {
  const raw = rawQuestion()
  assert.equal(raw.globalId, 'fb-q1', 'fixture 的 raw globalId 与 id 必须不同，才能覆盖稳定键优先级')
  assert.equal(raw.id, 1001)
  const question = normalizeFenbiQuestion(raw, 1, settings)
  const wrong = wrongImportItem(raw)
  const practice = practiceQuestion(raw)
  // metadata 必须由真实 normalizer 产出，且与记录导入入口指向同一道原始题
  assert.equal(question.source_question_key, 'fb-q1', '稳定键优先取 raw.globalId')
  assert.equal(wrong.entry_metadata.source_question_key, question.source_question_key)
  assert.equal(wrong.entry_metadata.source_question_key, practice.source_question_key)
  // 数值 id 仍用于稳定外部键，不能与稳定键混为一谈
  assert.match(wrong.external_key, /:1001$/)
})

test('wrong import entry: missing raw stable id never fabricates source_question_key from order', () => {
  const raw = rawQuestion()
  delete raw.globalId
  delete raw.id
  const wrong = wrongImportItem(raw)
  assert.equal(wrong.order, 1, '缺稳定标识时仍保留顺序号用于展示')
  assert.equal(
    'source_question_key' in wrong.entry_metadata,
    false,
    '缺 raw 稳定 id 时不得用 order 伪造 source_question_key',
  )
  assert.equal('source_question_key' in wrong, false, '稳定键只能放在 entry_metadata 且必须来自原始题目')
})
