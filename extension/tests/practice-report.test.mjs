import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const report = await importTypeScript(new URL('../src/adapters/fenbi/report.ts', import.meta.url))
const href = 'https://spa.fenbi.com/ti/exam/solution/1_1_3u7uapv?routecs=xingce&examcatid=1000185'
const modules = [
  ['政治理论',20,8,478], ['常识判断',15,12,262], ['言语理解与表达',30,20,1320],
  ['数量关系',10,9,932], ['判断推理',35,28,2719], ['资料分析',20,18,1252],
].map(([module_name,total_questions,correct_count,duration_seconds])=>({module_name,total_questions,correct_count,duration_seconds,children:[]}))
modules[0].children = [
  {module_name:'马克思主义',total_questions:2,correct_count:1,duration_seconds:33},
  {module_name:'新思想',total_questions:18,correct_count:7,duration_seconds:445},
  {module_name:'时事政治',total_questions:18,correct_count:7,duration_seconds:445},
]
const solution = { exerciseId:'1_1_3u7uapv', name:'2027年国考第一季行测模考大赛（地市级）',
  userAnswers:Object.fromEntries(Array.from({length:130},(_,i)=>[String(i),{status:i<95?1:-1,time:i===0?6963:0}])) }

test('only Fenbi settlement routes expose report import, independent of wrong counts',()=>{
  assert.equal(report.fenbiReportRoute(href).key,'1_1_3u7uapv')
  for (const url of ['https://spa.fenbi.com/ti/exam/practice/1_1_3u7uapv',href.replace('spa.fenbi.com','evil.example'),href.replace('https:','http:')])
    assert.equal(report.fenbiReportRoute(url),null)
})
test('real report totals and overlapping third-level statistics are preserved',()=>{
  const payload = report.buildFenbiPracticeReport(href,solution,modules,{exerciseKey:'1_1_3u7uapv',updatedTime:1792378634726,score:72.70000000000002,fullScore:100.00000000000004})
  assert.equal(payload.total_questions,130)
  assert.equal(payload.correct_count,95)
  assert.equal(payload.duration_seconds,6963)
  assert.equal(payload.score,72.7)
  assert.equal(payload.practiced_at,'2026-10-19')
  assert.equal(payload.modules[0].total_questions,20)
  assert.equal(payload.modules[0].children.reduce((s,m)=>s+m.total_questions,0),38)
})
test('missing or mismatched history requires a date and never substitutes today',()=>{
  const payload = report.buildFenbiPracticeReport(href,solution,modules,{exerciseKey:'other',updatedTime:1792378634726})
  assert.equal(payload.practiced_at,'')
  assert.equal(payload.time_source,'manual')
  assert.equal(payload.score,null)
  assert.equal(report.historyDate({exerciseKey:'x',updatedTime:Date.parse('2026-10-18T18:00:00Z')}).date,'2026-10-19')
})
test('stale report data, incomplete modules and missing per-question time cannot be imported',()=>{
  assert.throws(()=>report.buildFenbiPracticeReport(href,{...solution,exerciseId:'other'},modules),/当前报告/)
  assert.throws(()=>report.buildFenbiPracticeReport(href,solution,modules.slice(1)),/不一致/)
  assert.throws(()=>report.buildFenbiPracticeReport(href,{...solution,userAnswers:{a:{status:1}}},modules),/缺少逐题用时/)
  const answered=report.buildFenbiPracticeReport(
    href,
    {...solution,userAnswers:{a:{status:99,time:1,answer:{choice:'0'}}}},
    [{module_name:'数量关系',total_questions:1,correct_count:0,duration_seconds:1}],
  )
  assert.equal(answered.total_questions,1)
  assert.equal(answered.unanswered_count,0)
})
test('duration parser keeps seconds and missing values separate',()=>{
  assert.equal(report.parseReportDuration('7 分 58 秒'),478)
  assert.equal(report.parseReportDuration('1时56分3秒'),6963)
  assert.equal(report.parseReportDuration('0秒'),0)
  assert.equal(report.parseReportDuration('--'),null)
})

// 最小 DOM fixture：只实现采集器使用的 class 查询，保留真实的父子容器结构。
function element(className, children = [], textContent = '') {
  const node = { children, textContent, classList: { contains: name => className.split(' ').includes(name) } }
  node.querySelectorAll = selector => children.flatMap(child => [
    ...(child.classList.contains(selector.slice(1)) ? [child] : []), ...child.querySelectorAll(selector),
  ])
  node.querySelector = selector => node.querySelectorAll(selector)[0] || null
  return node
}
function reportContainer(depth, name, total, correct, duration, children = []) {
  const field = (label, value) => element('report-keypoints-tree-item-right-info', [
    element('report-keypoints-tree-item-right-info-name', [], label),
    element('report-keypoints-tree-item-right-info-box', [], value),
  ])
  return element(`report-keypoints-tree-container-${depth}`, [
    element('report-keypoints-tree-item', [
      element('report-keypoints-tree-item-name-text', [], name),
      field('总题数', String(total)), field('答对', String(correct)), field('用时', duration),
    ]), ...children,
  ])
}
test('report DOM keeps math topics under their own parent without flattening or summing overlaps', () => {
  const root = element('report', [reportContainer(0, '数量关系', 10, 9, '15分32秒', [
    reportContainer(1, '数学运算', 10, 9, '15分32秒', [
      reportContainer(2, '行程问题', 4, 3, '6分40秒'),
      reportContainer(2, '工程问题', 3, 3, '0秒'),
      reportContainer(2, '应用题', 6, 5, '--'),
    ]),
    reportContainer(1, '数字推理', 1, 1, '--'),
  ])])
  const parsed = report.readFenbiReportModules(root)
  assert.deepEqual(parsed[0].children.map(m => m.module_name), ['数学运算', '数字推理'])
  const math = parsed[0].children[0]
  assert.equal(math.total_questions, 10)
  assert.equal(math.duration_seconds, 932)
  assert.deepEqual(math.children.map(m => [m.module_name, m.total_questions, m.duration_seconds]), [
    ['行程问题', 4, 400], ['工程问题', 3, 0], ['应用题', 6, null],
  ])
  assert.deepEqual(parsed[0].children[1].children, [])
  const payload = report.buildFenbiPracticeReport(href, { ...solution, userAnswers: Object.fromEntries(
    Array.from({ length: 10 }, (_, i) => [i, { status: i < 9 ? 1 : -1, time: i === 0 ? 932 : 0 }]),
  ) }, parsed)
  assert.deepEqual(payload.modules, parsed)
  assert.equal(payload.total_questions, 10)
})
test('a malformed fine-grained topic cannot silently disappear from an imported report', () => {
  const root = element('report', [reportContainer(0, '数量关系', 10, 9, '15分32秒', [
    reportContainer(1, '数学运算', 10, 9, '15分32秒', [reportContainer(2, '行程问题', 4, 5, '1分')]),
  ])])
  assert.throws(() => report.readFenbiReportModules(root), /行程问题.*不完整/)
})

// ---- 逐题明细：用真实接口形状的最小 fixture ----
const detailTree = [{ name: '数量关系', children: [{ name: '数学运算', children: [
  { name: '行程问题', children: [{ name: '相遇追及' }] }, { name: '工程问题', children: [] },
] }] }]
const reportModules = [{ module_name: '数量关系', total_questions: 2, correct_count: 1, duration_seconds: 70, children: [
  { module_name: '数学运算', total_questions: 2, correct_count: 1, duration_seconds: 70, children: [
    { module_name: '行程问题', total_questions: 1, correct_count: 1, duration_seconds: 30, children: [] },
    { module_name: '工程问题', total_questions: 1, correct_count: 0, duration_seconds: 40, children: [] },
  ] },
] }]
const staticSolution = {
  card: { children: [{ name: '数量关系', children: [
    { key: 'q1', materialKeys: [] }, { key: 'q2', materialKeys: ['m1'] },
  ] }] },
  materials: [{ globalId: 'm1', content: '<p>共享材料</p>' }],
  solutions: [
    { globalId: 'q1', content: '<p>题干一</p>', type: 1, accessories: [{ type: 101, options: ['甲', '乙', '丙', '丁'] }],
      correctAnswer: { choice: '2', type: 201 }, solution: '<p>解析一</p>', keypoints: [{ name: '相遇追及' }] },
    { globalId: 'q2', content: '<p>题干二</p>', type: 1, accessories: [{ type: 102, options: ['<p>1</p>', '<p>2</p>'] }],
      correctAnswer: { choice: '1', type: 201 }, solution: '<p>解析二</p>', keypoints: [{ name: '工程问题' }] },
  ],
}
const questionSolution = { exerciseId: '1_1_3u7uapv', userAnswers: {
  q1: { status: 1, time: 66, answer: { choice: '2' } },
  q2: { status: 0, time: 3 },
} }

test('per-question import keeps paper order, option codes and a three-level module path', () => {
  const questions = report.buildFenbiPracticeQuestions({
    solution: questionSolution, staticSolution, details: detailTree, modules: reportModules,
  })
  assert.equal(questions.length, 2)
  assert.deepEqual(questions.map(q => [q.position, q.source_question_key, q.status]), [[1, 'q1', 'correct'], [2, 'q2', 'unanswered']])
  assert.deepEqual(questions[0].module_path, ['数量关系', '数学运算', '行程问题'])
  assert.deepEqual(questions[0].options.map(o => o.option_code), ['A', 'B', 'C', 'D'])
  assert.deepEqual(questions[0].answer, { answer_data: { correct: 'C' }, grading_method: 'exact' })
  assert.equal(questions[0].response_data, 'C')
  assert.equal(questions[0].duration_seconds, 66)
  assert.deepEqual(questions[0].explanations.map(e => e.content), ['<p>解析一</p>'])
  assert.deepEqual(questions[0].materials, [])
})
test('unanswered questions import content but no submitted answer', () => {
  const questions = report.buildFenbiPracticeQuestions({
    solution: questionSolution, staticSolution, details: detailTree, modules: reportModules,
  })
  assert.equal(questions[1].response_data, null)
  assert.equal(questions[1].status, 'unanswered')
  assert.deepEqual(questions[1].answer, { answer_data: { correct: 'B' }, grading_method: 'exact' })
  assert.equal(questions[1].materials.length, 1)
  assert.equal(questions[1].materials[0].link_key, 'm1')
})
test('fenbi status 10 without a submitted answer is treated as unanswered', () => {
  const questions = report.buildFenbiPracticeQuestions({
    solution: { exerciseId: '1_1_3u7uapv', userAnswers: {
      q1: { status: 1, time: 66, answer: { choice: '2' } },
      q2: { status: 10, time: 0 },
    } },
    staticSolution, details: detailTree, modules: reportModules,
  })
  assert.equal(questions.length, 2)
  assert.deepEqual(questions.map(q => q.status), ['correct', 'unanswered'])
  assert.equal(questions[1].response_data, null)
  assert.equal(questions[1].duration_seconds, 0)
})
test('module path falls back to what the report tree actually contains', () => {
  const shallow = [{ module_name: '数量关系', total_questions: 2, correct_count: 1, duration_seconds: 70, children: [] }]
  const questions = report.buildFenbiPracticeQuestions({
    solution: questionSolution, staticSolution, details: detailTree, modules: shallow,
  })
  assert.deepEqual(questions[0].module_path, ['数量关系'])
})
test('a question with no matching module is skipped instead of being put in the first module', () => {
  const unrelated = [{ module_name: '资料分析', total_questions: 2, correct_count: 1, duration_seconds: 70, children: [] }]
  const questions = report.buildFenbiPracticeQuestions({
    solution: questionSolution, staticSolution, details: detailTree, modules: unrelated,
  })
  assert.deepEqual(questions, [])
})

test('report module tree is converted with depth limit', () => {
  const tree = [
    {
      name: '数量关系', questionCount: 15, correctCount: 9, time: 900,
      children: [
        {
          name: '数学运算', questionCount: 10, correctCount: 6, time: 600,
          children: [
            { name: '行程问题', questionCount: 3, correctCount: 2, time: 180, children: [
              { name: '第四层', questionCount: 1, correctCount: 1, time: 60 },
            ] },
          ],
        },
      ],
    },
    { name: '   资料分析  ', questionCount: 20, correctCount: 15 },
  ]
  const modules = report.buildReportModules(tree)
  assert.equal(modules.length, 2)
  assert.equal(modules[0].module_name, '数量关系')
  assert.equal(modules[0].duration_seconds, 900)
  assert.equal(modules[0].children[0].children[0].module_name, '行程问题')
  assert.equal(modules[0].children[0].children[0].children, undefined)
  assert.equal(modules[1].module_name, '资料分析')
  assert.equal(modules[1].duration_seconds, null)
})
