import { UnifiedPaper, UnifiedSection, UnifiedQuestion, RenderTypographySettings, DEFAULT_TYPOGRAPHY_SETTINGS } from '../types'
import { extractFenbiPaperFromDom } from './dom'
import { getActiveTikuPrefix, getGlobalSolutionsPool } from './mistake'
import { normalizeFenbiQuestion, formatFenbiPaperTitle, formatAnswerChoice } from './normalize'

/**
 * 粉笔 (fenbi.com) 真实接口试卷数据精准归一化适配器
 */
export function adaptFenbiPaper(raw: any, settings: RenderTypographySettings): UnifiedPaper {
  const isMistakeScene = raw.scene === 'mistake' || (raw.title && raw.title.includes('错题'))
  const rawTitle = raw.name || raw.title || raw.examName || ''
  const paperTitle = formatFenbiPaperTitle(rawTitle, isMistakeScene)
  const isMockExam = Boolean(
    raw.isMockExam ||
    raw.scene === 'mock_exam' ||
    paperTitle.includes('模考') ||
    paperTitle.includes('大赛')
  )

  // 提取已知错题 ID、Key、序号集合 (支持全局池与数据包自带)
  const wrongIds = new Set<number>(
    Array.isArray(raw.wrongQuestionIds) && raw.wrongQuestionIds.length > 0
      ? raw.wrongQuestionIds
      : typeof window !== 'undefined' && Array.isArray((window as any).__FENBI_MOCK_WRONG_IDS__)
      ? (window as any).__FENBI_MOCK_WRONG_IDS__
      : []
  )
  const wrongKeys = new Set<string>(
    Array.isArray(raw.wrongQuestionKeys) && raw.wrongQuestionKeys.length > 0
      ? raw.wrongQuestionKeys
      : typeof window !== 'undefined' && Array.isArray((window as any).__FENBI_MOCK_WRONG_KEYS__)
      ? (window as any).__FENBI_MOCK_WRONG_KEYS__
      : []
  )
  const wrongOrders = new Set<number>(
    Array.isArray(raw.wrongQuestionOrders) && raw.wrongQuestionOrders.length > 0
      ? raw.wrongQuestionOrders
      : typeof window !== 'undefined' && Array.isArray((window as any).__FENBI_MOCK_WRONG_ORDERS__)
      ? (window as any).__FENBI_MOCK_WRONG_ORDERS__
      : []
  )

  // 1. 建立快速索引
  const rawQuestionList: any[] = Array.isArray(raw.questions)
    ? raw.questions
    : Array.isArray(raw.solutions)
    ? raw.solutions
    : Array.isArray(raw.exercises)
    ? raw.exercises
    : []

  const questionMap = new Map<string, any>()
  for (const q of rawQuestionList) {
    if (q.globalId) questionMap.set(String(q.globalId), q)
    if (q.key) questionMap.set(String(q.key), q)
    if (q.id) questionMap.set(String(q.id), q)
  }

  const materialMap = new Map<string, any>()
  if (Array.isArray(raw.materials)) {
    for (const m of raw.materials) {
      if (m.globalId) materialMap.set(String(m.globalId), m)
      if (m.key) materialMap.set(String(m.key), m)
      if (m.id) materialMap.set(String(m.id), m)
    }
  }

  const sections: UnifiedSection[] = []
  let globalOrder = 1

  // 模式 A: 规范 card.children 结构
  if (raw.card && Array.isArray(raw.card.children) && raw.card.children.length > 0) {
    for (const secNode of raw.card.children) {
      const secName = secNode.name || secNode.title || '专项模块'
      const questions: UnifiedQuestion[] = []
      const qNodes = secNode.children || []

      for (const qNode of qNodes) {
        const qKey = String(qNode.key || qNode.globalId || qNode.id || '')
        const rawQ = questionMap.get(qKey)
        if (!rawQ) continue

        let materialHtml: string | undefined = undefined
        if (Array.isArray(qNode.materialKeys) && qNode.materialKeys.length > 0) {
          const matObj = materialMap.get(String(qNode.materialKeys[0]))
          if (matObj) materialHtml = matObj.content
        }

        const currentOrder = globalOrder++
        // 统一归一化
        const normQ = normalizeFenbiQuestion(rawQ, currentOrder, settings, materialHtml)
        const qidNum = Number(normQ.question_id || normQ.id)

        // 综合判定是否为错题 (核心: state === -1)
        const isWrong =
          (qidNum && wrongIds.has(qidNum)) ||
          (qKey && wrongKeys.has(qKey)) ||
          wrongOrders.has(currentOrder) ||
          rawQ.state === -1 ||
          String(rawQ.state) === '-1' ||
          rawQ.State === -1 ||
          String(rawQ.State) === '-1' ||
          rawQ.status === -1 ||
          String(rawQ.status) === '-1' ||
          qNode.state === -1 ||
          String(qNode.state) === '-1' ||
          qNode.State === -1 ||
          String(qNode.State) === '-1' ||
          qNode.status === -1 ||
          String(qNode.status) === '-1' ||
          rawQ.isWrong === true ||
          rawQ.is_wrong === true ||
          rawQ.result === 2 ||
          rawQ.result === -1 ||
          qNode.result === 2 ||
          qNode.result === -1 ||
          qNode.isWrong === true ||
          qNode.correct === false ||
          (qNode.userAnswer && qNode.correctAnswer && String(qNode.userAnswer).trim().toUpperCase() !== String(qNode.correctAnswer).trim().toUpperCase())

        if (isWrong) {
          normQ.is_wrong = true
          if (qidNum && !isNaN(qidNum)) wrongIds.add(qidNum)
        }
        questions.push(normQ)
      }

      if (questions.length > 0) {
        sections.push({ name: secName, questions })
      }
    }
  }
  // 模式 B: 平铺试题数组
  else if (rawQuestionList.length > 0) {
    const questions: UnifiedQuestion[] = []
    for (const rawQ of rawQuestionList) {
      const currentOrder = globalOrder++
      const normQ = normalizeFenbiQuestion(rawQ, currentOrder, settings)
      const qidNum = Number(normQ.question_id || normQ.id)
      const qKey = String(rawQ.globalId || rawQ.key || rawQ.id || '')

      const isWrong =
        (qidNum && wrongIds.has(qidNum)) ||
        (qKey && wrongKeys.has(qKey)) ||
        wrongOrders.has(currentOrder) ||
        rawQ.state === -1 ||
        String(rawQ.state) === '-1' ||
        rawQ.State === -1 ||
        String(rawQ.State) === '-1' ||
        rawQ.status === -1 ||
        String(rawQ.status) === '-1' ||
        rawQ.isWrong === true ||
        rawQ.is_wrong === true ||
        rawQ.result === 2 ||
        rawQ.result === -1

      if (isWrong) {
        normQ.is_wrong = true
        if (qidNum && !isNaN(qidNum)) wrongIds.add(qidNum)
      }
      questions.push(normQ)
    }
    sections.push({
      name: isMistakeScene ? '错题集训' : '行政职业能力测验',
      questions,
    })
  }

  const totalQuestions = sections.reduce((sum, sec) => sum + sec.questions.length, 0)

  // 模式 C: 兜底屏幕 DOM 提取
  if (totalQuestions === 0 && typeof document !== 'undefined') {
    const domPaper = extractFenbiPaperFromDom(settings)
    if (domPaper && domPaper.sections && domPaper.sections.length > 0 && domPaper.total_questions > 0) {
      return domPaper
    }
  }

  // 统计实际打上错题标记的题目总数
  let actualWrongCount = 0
  for (const sec of sections) {
    for (const q of sec.questions) {
      if (q.is_wrong) actualWrongCount++
    }
  }

  return {
    title: paperTitle,
    source_platform: 'fenbi',
    total_questions: totalQuestions,
    sections,
    metadata: {
      exam_id: raw.id || raw.examId,
      tiku_prefix: raw.tikuPrefix || 'xingce',
      scene: isMockExam ? 'mock_exam' : (isMistakeScene ? 'mistake' : 'paper'),
      isMockExam,
      wrongQuestionIds: Array.from(wrongIds),
      wrongQuestionKeys: Array.from(wrongKeys),
      wrongQuestionOrders: Array.from(wrongOrders),
      totalWrong: actualWrongCount || wrongIds.size || wrongOrders.size,
      created_at: new Date().toISOString(),
    },
  }
}

/**
 * 试卷参考答案、名师解析与真题来源反查全量补齐引擎
 */
export async function backfillPaperAnswers(paper: UnifiedPaper): Promise<UnifiedPaper> {
  const missingQMap = new Map<number, UnifiedQuestion>()
  for (const sec of paper.sections) {
    for (const q of sec.questions) {
      const qid = Number(q.question_id || q.id)
      if (qid && (!q.answer || !q.analysis || !q.source || !q.options || q.options.length < 2)) {
        missingQMap.set(qid, q)
      }
    }
  }

  if (missingQMap.size === 0) return paper

  // 1. 优先从全局题目池中直接命中回填 (纯内存静默读取，0网络请求)
  const globalPool = getGlobalSolutionsPool()
  for (const [qid, targetQ] of missingQMap.entries()) {
    const cachedSol = globalPool.get(qid)
    if (cachedSol) {
      const normalized = normalizeFenbiQuestion(
        cachedSol,
        targetQ.order_num || 1,
        DEFAULT_TYPOGRAPHY_SETTINGS
      )
      if (!targetQ.answer && normalized.answer) targetQ.answer = normalized.answer
      if (!targetQ.analysis && normalized.analysis) targetQ.analysis = normalized.analysis
      if (!targetQ.source && normalized.source) targetQ.source = normalized.source
      if ((!targetQ.options || targetQ.options.length < 2) && normalized.options && normalized.options.length >= 2) {
        targetQ.options = normalized.options
      }
    }
  }

  // 严格杜绝主动发网络请求反查，恪守 100% 零外发被动拦截原则
  return paper
}

export * from './api'
export * from './dom'
export * from './mistake'
export * from './normalize'
export * from './session'
