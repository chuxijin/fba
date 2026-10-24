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
test('stale report data, incomplete modules and unsupported states cannot be imported',()=>{
  assert.throws(()=>report.buildFenbiPracticeReport(href,{...solution,exerciseId:'other'},modules),/当前报告/)
  assert.throws(()=>report.buildFenbiPracticeReport(href,solution,modules.slice(1)),/不一致/)
  assert.throws(()=>report.buildFenbiPracticeReport(href,{...solution,userAnswers:{a:{status:99,time:1}}},modules),/暂不支持/)
})
test('history lookup follows cursors and uses the exact report key, ignoring title and zero counts',async()=>{
  const urls=[]
  const result = await report.findFenbiReportHistory(href,async(url,options)=>{
    urls.push(new URL(url))
    assert.equal(options.credentials,'include')
    return {ok:true,json:async()=>({code:1,data:urls.length===1
      ? {cursor:'next/2',historyItems:[{exerciseKey:'other',sheetName:solution.name}]}
      : {cursor:'',historyItems:[{exerciseKey:'1_1_3u7uapv',questionCount:0,correctCount:0,updatedTime:1792378634726,score:72.7}]}})}
  })
  assert.equal(urls.length,2)
  assert.equal(urls[1].searchParams.get('cursor'),'next/2')
  assert.equal(result.exerciseKey,'1_1_3u7uapv')
  assert.equal(result.questionCount,undefined)
})
test('history lookup terminates on repeated cursors',async()=>{
  let count=0
  assert.equal(await report.findFenbiReportHistory(href,async()=>{
    count++
    return {ok:true,json:async()=>({code:1,data:{cursor:'same',historyItems:[]}})}
  }),null)
  assert.equal(count,2)
})
test('duration parser keeps seconds and missing values separate',()=>{
  assert.equal(report.parseReportDuration('7 分 58 秒'),478)
  assert.equal(report.parseReportDuration('1时56分3秒'),6963)
  assert.equal(report.parseReportDuration('0秒'),0)
  assert.equal(report.parseReportDuration('--'),null)
})
