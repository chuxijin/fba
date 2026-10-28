import { normalizeInlineSymbols } from './normalize'

export interface ReportModule {
  module_name: string
  total_questions: number
  correct_count: number
  duration_seconds: number | null
  unanswered_count?: number | null
  children?: ReportModule[]
}

export interface PracticeReportOption {
  option_code: string
  content: string
  sort_order: number
}

export interface PracticeReportQuestion {
  source_question_key: string
  position: number
  module_path: string[]
  stem: string
  content_format: 'html'
  question_type: 'single_choice' | 'multiple_choice'
  options: PracticeReportOption[]
  answer: { answer_data: { correct: string | string[] }; grading_method: 'exact' | 'set' } | null
  explanations: { content: string; explanation_type: string; version_no: number; is_default: boolean }[]
  materials: {
    link_key: string
    title: string
    content: string
    content_format: 'html'
    role: 'passage'
    sort_order: number
  }[]
  status: 'correct' | 'wrong' | 'unanswered'
  response_data: string | string[] | null
  duration_seconds: number | null
  score: number | null
  max_score: number | null
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
  questions?: PracticeReportQuestion[]
}

/** 报告统计树的节点；从已捕获的 getReport 子报告中按结构定位。 */
export interface ReportDetailModule {
  name: string
  children?: ReportDetailModule[]
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

/** 读取模块、直属子模块和细分题型；保留原始统计，不对重叠知识点求和。 */
export function readFenbiReportModules(root: ParentNode): ReportModule[] {
  return Array.from(root.querySelectorAll('.report-keypoints-tree-container-0')).map(container => ({
    ...readModule(container),
    children: Array.from(container.querySelectorAll('.report-keypoints-tree-container-1')).map(child => ({
      ...readModule(child),
      children: Array.from(child.querySelectorAll('.report-keypoints-tree-container-2')).map(readModule),
    })),
  }))
}

/** 报告接口里的模块树（getReport.subReports）转成导入结构，供页面没有渲染统计时兜底。 */
export function buildReportModules(nodes: any[], depth = 1): ReportModule[] {
  if (!Array.isArray(nodes)) return []
  return nodes
    .filter(node => node && String(node.name || '').trim())
    .map(node => ({
      module_name: String(node.name).trim(),
      total_questions: Number(node.questionCount) || 0,
      correct_count: Number(node.correctCount) || 0,
      duration_seconds: node.time != null && Number.isFinite(Number(node.time)) ? Number(node.time) : null,
      ...(depth < MAX_MODULE_DEPTH && Array.isArray(node.children) && node.children.length
        ? { children: buildReportModules(node.children, depth + 1) }
        : {}),
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
  if (answers.some(a => !Number.isFinite(a.time) || a.time < 0))
    throw new Error('这份报告缺少逐题用时，无法准确导入')
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
    unanswered_count:answers.filter(a => !a.answer?.choice).length,
    duration_seconds:answers.reduce((sum,a) => sum+a.time,0),
    practiced_at:time.date, source_updated_at:time.timestamp, time_source:time.timestamp ? 'history_updated' : 'manual',
    score:matchedHistory?.score != null && Number.isFinite(score) ? Math.round(score*100)/100 : null,
    full_score:matchedHistory?.fullScore != null && Number.isFinite(fullScore) ? Math.round(fullScore*100)/100 : null,
    modules,
  }
}

const OPTION_CODES = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
// 题型只到“数量关系／数学运算／行程问题”这一层，再深会造成节点爆炸。
const MAX_MODULE_DEPTH = 3

function choiceToCodes(choice: unknown): string[] | null {
  if (choice === null || choice === undefined || choice === '') return null
  const parts = Array.isArray(choice) ? choice : String(choice).split(',')
  const codes: string[] = []
  for (const part of parts) {
    const index = Number(String(part).trim())
    if (!Number.isInteger(index) || index < 0 || index >= OPTION_CODES.length) return null
    codes.push(OPTION_CODES[index])
  }
  return codes.length ? codes : null
}

function readCardMap(card: any): Map<string, { moduleName: string; materialKeys: string[] }> {
  const map = new Map<string, { moduleName: string; materialKeys: string[] }>()
  for (const module of card?.children || []) {
    for (const child of module?.children || []) {
      const key = String(child?.key || '')
      if (!key) continue
      map.set(key, {
        moduleName: String(module?.name || ''),
        materialKeys: (child?.materialKeys || []).map((value: any) => String(value)),
      })
    }
  }
  return map
}

function collectDetailPaths(nodes: ReportDetailModule[], prefix: string[] = []): string[][] {
  const result: string[][] = []
  for (const node of nodes) {
    const path = [...prefix, String(node.name || '')]
    result.push(path, ...collectDetailPaths(node.children || [], path))
  }
  return result
}

function hasModulePath(modules: ReportModule[], path: string[]): boolean {
  let level: ReportModule[] | undefined = modules
  for (const name of path) {
    const node: ReportModule | undefined = level?.find(item => item.module_name === name)
    if (!node) return false
    level = node.children
  }
  return path.length > 0
}

/** 报告统计与逐题知识点层级可能不一致，逐级回退到报告中确实存在的路径。 */
function fitModulePath(modules: ReportModule[], path: string[]): string[] {
  for (let length = Math.min(path.length, MAX_MODULE_DEPTH); length >= 1; length -= 1) {
    if (hasModulePath(modules, path.slice(0, length))) return path.slice(0, length)
  }
  // 找不到归属时返回空路径并跳过该题，避免把题静默塞进第一个模块造成章节统计错误
  return []
}

/** 用 getSolution 的逐题状态、static/solution 的题目内容和 getReport 的模块层级组装逐题导入参数。 */
export function buildFenbiPracticeQuestions(input: {
  solution: any
  staticSolution: any
  details?: ReportDetailModule[] | null
  modules: ReportModule[]
}): PracticeReportQuestion[] {
  const solutions: any[] = Array.isArray(input.staticSolution?.solutions) ? input.staticSolution.solutions : []
  if (!solutions.length) return []
  const userAnswers: Record<string, any> = (input.solution?.data || input.solution)?.userAnswers || {}
  const cardMap = readCardMap(input.staticSolution?.card)
  const materialMap = new Map<string, any>(
    (input.staticSolution?.materials || []).map((item: any) => [String(item?.globalId || ''), item]),
  )
  const detailPaths = collectDetailPaths(input.details || [])
  const questions: PracticeReportQuestion[] = []

  solutions.forEach((item, index) => {
    const key = String(item?.globalId || '')
    const user = userAnswers[key]
    const stem = normalizeInlineSymbols(String(item?.content || '').trim())
    if (!key || !user || !stem) return
    const optionTexts: string[] = Array.isArray(item?.accessories?.[0]?.options) ? item.accessories[0].options : []
    const options: PracticeReportOption[] = []
    optionTexts.forEach((content, order) => {
      const text = normalizeInlineSymbols(String(content || '').trim())
      if (text && order < OPTION_CODES.length) options.push({ option_code: OPTION_CODES[order], content: text, sort_order: order })
    })
    if (options.length < 2) return
    const correct = choiceToCodes(item?.correctAnswer?.choice)
    // 粉笔的 status 语义不统一（-1 也可能是答错，10 是无作答记录），统一以是否提交答案判定。
    const answered = choiceToCodes(user?.answer?.choice)
    const status = !answered ? 'unanswered' : Number(user.status) === 1 ? 'correct' : 'wrong'
    const isMultiple = (correct?.length || 0) > 1 || (answered?.length || 0) > 1

    const moduleName = cardMap.get(key)?.moduleName || ''
    const keypointNames = new Set<string>(
      (item.keypoints || []).map((value: any) => String(value?.name || '')).filter(Boolean),
    )
    let candidates = detailPaths.filter(path => path[0] === moduleName && keypointNames.has(path[path.length - 1]))
    if (!candidates.length) candidates = detailPaths.filter(path => keypointNames.has(path[path.length - 1]))
    const best = candidates.reduce<string[] | null>((acc, path) => (!acc || path.length > acc.length ? path : acc), null)
    const modulePath = fitModulePath(input.modules, (best || [moduleName]).slice(0, MAX_MODULE_DEPTH))
    if (!modulePath.length) return

    const materials: PracticeReportQuestion['materials'] = []
    ;(cardMap.get(key)?.materialKeys || []).forEach(linkKey => {
      const content = String(materialMap.get(linkKey)?.content || '').trim()
      if (!content) return
      materials.push({
        link_key: linkKey,
        title: '材料',
        content,
        content_format: 'html',
        role: 'passage',
        sort_order: materials.length,
      })
    })

    const explanation = String(item?.solution || '').trim()
    const duration = Number(user.time)
    questions.push({
      source_question_key: key,
      position: index + 1,
      module_path: modulePath,
      stem,
      content_format: 'html',
      question_type: isMultiple ? 'multiple_choice' : 'single_choice',
      options,
      answer: correct
        ? {
            answer_data: { correct: correct.length === 1 ? correct[0] : correct },
            grading_method: correct.length === 1 ? 'exact' : 'set',
          }
        : null,
      explanations: explanation
        ? [{ content: explanation, explanation_type: 'official', version_no: 1, is_default: true }]
        : [],
      materials,
      status,
      response_data: answered ? (answered.length === 1 ? answered[0] : answered) : null,
      duration_seconds: Number.isFinite(duration) && duration >= 0 ? Math.round(duration) : null,
      score: null,
      max_score: null,
    })
  })

  return questions
}
