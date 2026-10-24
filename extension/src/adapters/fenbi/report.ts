export interface ReportModule {
  module_name: string
  total_questions: number
  correct_count: number
  duration_seconds: number | null
  unanswered_count?: number | null
  children?: ReportModule[]
}

export interface PracticeReportPayload {
  source_platform: 'fenbi'
  source_key: string
  source_url: string
  subject_name: string
  material_type: 'exam' | 'practice' | 'special'
  material_title: string
  total_questions: number
  correct_count: number
  unanswered_count: number
  duration_seconds: number
  practiced_at: string
  source_updated_at: string | null
  time_source: 'history_updated' | 'manual'
  score: number | null
  full_score: number | null
  modules: ReportModule[]
}

export interface FenbiHistoryItem {
  exerciseKey: string
  updatedTime?: number
  score?: number
  fullScore?: number
}

export function fenbiReportRoute(href: string): { key: string; routecs: string; examcatid: string } | null {
  try {
    const url = new URL(href)
    const key = url.pathname.match(/^\/ti\/exam\/solution\/(\d+_\d+_[a-zA-Z0-9]+)\/?$/)?.[1]
    if (url.protocol !== 'https:' || url.hostname !== 'spa.fenbi.com' || !key) return null
    return { key, routecs: url.searchParams.get('routecs') || 'xingce', examcatid: url.searchParams.get('examcatid') || '' }
  } catch { return null }
}

export function parseReportDuration(text: string): number | null {
  const normalized = text.replace(/\s/g, '')
  if (!normalized || normalized === '--') return null
  let seconds = 0
  let found = false
  for (const match of normalized.matchAll(/(\d+(?:\.\d+)?)(小时|时|分钟|分|秒)/g)) {
    found = true
    seconds += Number(match[1]) * (/时/.test(match[2]) ? 3600 : /分/.test(match[2]) ? 60 : 1)
  }
  return found ? Math.round(seconds) : null
}

export function historyDate(item?: FenbiHistoryItem | null): { date: string; timestamp: string | null } {
  if (!item?.updatedTime || !Number.isFinite(item.updatedTime)) return { date: '', timestamp: null }
  const date = new Date(item.updatedTime)
  if (Number.isNaN(date.getTime())) return { date: '', timestamp: null }
  // 粉笔练习按北京时间归日，避免浏览器所在地或 UTC 导致日期偏移。
  return { date: new Date(date.getTime() + 8 * 3600000).toISOString().slice(0, 10), timestamp: date.toISOString() }
}

function readModule(container: Element): ReportModule {
  const row = Array.from(container.children).find(el => el.classList.contains('report-keypoints-tree-item'))
  if (!row) throw new Error('模块统计尚未加载完整，请稍后重试')
  const name = row.querySelector('.report-keypoints-tree-item-name-text')?.textContent?.trim() || ''
  const values = new Map<string, string>()
  for (const field of row.querySelectorAll('.report-keypoints-tree-item-right-info')) {
    const label = field.querySelector('.report-keypoints-tree-item-right-info-name')?.textContent?.trim() || ''
    values.set(label, field.querySelector('.report-keypoints-tree-item-right-info-box')?.textContent || '')
  }
  const count = (label: string) => {
    const value = values.get(label)?.match(/\d+/)?.[0]
    return value === undefined ? NaN : Number(value)
  }
  const total = count('总题数'), correct = count('答对')
  if (!name || !Number.isInteger(total) || total <= 0 || !Number.isInteger(correct) || correct > total)
    throw new Error(`“${name || '模块'}”的题数或正确数不完整`)
  return { module_name: name, total_questions: total, correct_count: correct, duration_seconds: parseReportDuration(values.get('用时') || '') }
}

/** 只读取六大模块及直属子模块；保留各层统计，不能对重叠知识点求和。 */
export function readFenbiReportModules(root: ParentNode): ReportModule[] {
  return Array.from(root.querySelectorAll('.report-keypoints-tree-container-0')).map(container => ({
    ...readModule(container),
    children: Array.from(container.querySelectorAll('.report-keypoints-tree-container-1')).map(readModule),
  }))
}

export function buildFenbiPracticeReport(
  href: string, solution: any, modules: ReportModule[], history?: FenbiHistoryItem | null,
): PracticeReportPayload {
  const route = fenbiReportRoute(href)
  const data = solution?.data || solution
  if (!route || data?.exerciseId !== route.key) throw new Error('未捕获当前报告的数据，请刷新结算页面后重试')
  const answers: any[] = Object.values(data.userAnswers || {})
  if (!answers.length || !modules.length) throw new Error('报告尚未加载完成，请稍后重试')
  if (answers.some(a => ![-1, 0, 1].includes(Number(a.status)) || !Number.isFinite(a.time) || a.time < 0))
    throw new Error('这份报告包含暂不支持的作答状态或缺少用时，无法准确导入')
  const correct = answers.filter(a => Number(a.status) === 1).length
  if (modules.reduce((s,m) => s+m.total_questions,0) !== answers.length || modules.reduce((s,m) => s+m.correct_count,0) !== correct)
    throw new Error('模块统计与整卷不一致，请等待结算页面加载完整')
  const matchedHistory = history?.exerciseKey === route.key ? history : null
  const time = historyDate(matchedHistory)
  const source = new URL(`/ti/exam/solution/${route.key}`, 'https://spa.fenbi.com')
  source.searchParams.set('routecs', route.routecs)
  if (route.examcatid) source.searchParams.set('examcatid', route.examcatid)
  const score = Number(matchedHistory?.score), fullScore = Number(matchedHistory?.fullScore)
  return {
    source_platform:'fenbi', source_key:route.key, source_url:source.href,
    subject_name:route.routecs === 'xingce' ? '行测' : route.routecs,
    material_type: /模考|大赛/.test(data.name || '') ? 'exam' : 'practice', material_title:String(data.name || '粉笔练习'),
    total_questions:answers.length, correct_count:correct,
    unanswered_count:answers.filter(a => Number(a.status) === 0).length,
    duration_seconds:answers.reduce((sum,a) => sum+a.time,0),
    practiced_at:time.date, source_updated_at:time.timestamp, time_source:time.timestamp ? 'history_updated' : 'manual',
    score:matchedHistory?.score != null && Number.isFinite(score) ? Math.round(score*100)/100 : null,
    full_score:matchedHistory?.fullScore != null && Number.isFinite(fullScore) ? Math.round(fullScore*100)/100 : null,
    modules,
  }
}

/** 用户点击导入后才查历史，固定粉笔接口、同一报告、游标去重和总时限。 */
export async function findFenbiReportHistory(
  href: string, fetcher: typeof fetch, signal?: AbortSignal,
): Promise<FenbiHistoryItem | null> {
  const route = fenbiReportRoute(href)
  if (!route) throw new Error('当前页面不是粉笔结算报告')
  const visited = new Set<string>()
  let cursor = ''
  for (let page=0; page<20; page++) {
    if (visited.has(cursor)) break
    visited.add(cursor)
    const url = new URL('https://tiku.fenbi.com/combine/exercise/getExerciseBriefHistory')
    const params = { categoryId:route.key.split('_')[0], limit:'15', cursor, routecs:route.routecs, app:'web', kav:'131', av:'134', hav:'128', version:'3.0.0.0', deviceId:'', gav:'2', apcId:'0', examcatid:route.examcatid }
    Object.entries(params).forEach(([key,value])=>url.searchParams.set(key,value))
    url.searchParams.set('noCacheTag', String(Date.now()))
    const response = await fetcher(url.href, { credentials:'include', signal })
    if (!response.ok) throw new Error('暂时无法读取粉笔练习日期，可手动填写后导入')
    const body = await response.json()
    if (body.code !== 1) throw new Error('粉笔练习历史不可用，可手动填写日期')
    const match = (body.data?.historyItems || []).find((item:any)=>item.exerciseKey === route.key)
    if (match) return { exerciseKey:match.exerciseKey, updatedTime:match.updatedTime, score:match.score, fullScore:match.fullScore }
    cursor = String(body.data?.cursor || '')
    if (!cursor) break
  }
  return null
}
