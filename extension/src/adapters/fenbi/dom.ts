import { UnifiedPaper, UnifiedQuestion, RenderTypographySettings } from '../types'
import { applyNegativeKeywordsBold } from '../common'

/**
 * 粉笔通用做题页面 DOM 智能提取引擎 (屏幕可见即所得)
 * 适用于错题本、真题模拟、专项练习等各类做题与解析页面
 */
export function extractFenbiPaperFromDom(settings: RenderTypographySettings): UnifiedPaper | null {
  // 1. 智能提取考点名称与试卷标题
  let detectedKeypoint = ''
  const kpSelectors = [
    '.ant-breadcrumb li:last-child',
    '.breadcrumb-item:last-child',
    '.crumb:last-child',
    '.keypoint-name',
    '.category-name',
    '.header-title',
    '.node-title',
  ]
  for (const sel of kpSelectors) {
    const el = document.querySelector(sel)
    const txt = el?.textContent?.trim()
    if (txt && txt.length >= 2 && !txt.includes('首页') && !txt.includes('错题') && !txt.includes('题库')) {
      detectedKeypoint = txt
      break
    }
  }

  const isMistakeUrl = typeof location !== 'undefined' && (location.href.includes('/error') || location.href.includes('/errors/'))
  let title = isMistakeUrl ? `粉笔${detectedKeypoint || '数学运算'}错题` : '粉笔在线练习'

  const titleSelectors = [
    '.exam-title',
    '.paper-title',
    '.title-box',
    '.head-title',
    '.exercise-title',
    '.page-title',
    'h1',
    'h2',
  ]

  for (const sel of titleSelectors) {
    const el = document.querySelector(sel)
    const txt = el?.textContent?.trim()
    if (txt && txt.length > 2 && !txt.includes('首页') && !txt.includes('退出') && !txt.includes('粉笔题库')) {
      title = txt
      break
    }
  }

  // 2. 泛化匹配题目容器 (支持错题、单题、列表)
  const questionSelectors = [
    '.exercise-item',
    '.question-item',
    '.ti-item',
    '.fb-question',
    '.exam-item',
    '.wrong-item',
    '.error-item',
    '.mistake-item',
    '.question-container',
    '.question-wrapper',
    '.solution-item',
    '[data-question-id]',
    '[data-exercise-id]',
    '.practice-item',
  ]

  let qElements: Element[] = []
  for (const sel of questionSelectors) {
    const els = Array.from(document.querySelectorAll(sel))
    if (els.length > 0) {
      qElements = els
      break
    }
  }

  // 单题视口兜底 (如一页一题模式)
  if (qElements.length === 0) {
    const singleQ = document.querySelector(
      '.single-question, .question-card, .exam-content, .question-main'
    )
    if (singleQ) {
      qElements = [singleQ]
    }
  }

  if (qElements.length === 0) {
    return null
  }

  const questions: UnifiedQuestion[] = []
  let order = 1

  for (const qEl of qElements) {
    // 1. 选项提取与前缀去重
    const options: string[] = []
    const optEls = qEl.querySelectorAll(
      '.options li, .option-item, .choice-item, .fb-option, .options .item, .select-item'
    )
    optEls.forEach((optEl) => {
      let txt = (optEl.textContent || '').trim()
      txt = txt.replace(/^[A-Da-d][\.\、\s\:\：\s]*/, '').trim()
      if (txt) options.push(txt)
    })

    // 2. 题干靶向精准提取 (优先提取真实题干容器，绝不使用宽泛通配符误杀)
    const directStemEl = qEl.querySelector(
      '.desc, .question-stem, .stem, .item-stem, .stem-wrap, .question-content, .question-main'
    )

    let stem = ''
    if (directStemEl) {
      // 克隆题干容器并仅剔除其可能嵌套的选项
      const stemClone = directStemEl.cloneNode(true) as Element
      stemClone.querySelectorAll('.options, .choice-list, ul').forEach((el) => el.remove())
      stem = (stemClone as HTMLElement).innerHTML?.trim() || stemClone.textContent?.trim() || ''
    } else {
      // 降级克隆整个节点，仅精准移除已知的选项和材料容器
      const qClone = qEl.cloneNode(true) as Element
      qClone
        .querySelectorAll('.options, .choice-list, .material, .material-content, .material-box, ul')
        .forEach((el) => el.remove())
      stem = (qClone as HTMLElement).innerHTML?.trim() || qClone.textContent?.trim() || ''
    }

    if (!stem) continue

    if (settings.boldNegativeQuestion) {
      stem = applyNegativeKeywordsBold(stem)
    }

    // 3. 材料提取
    let material: string | undefined = undefined
    const matEl =
      qEl.querySelector('.material, .material-content, .material-box, .article-content') ||
      document.querySelector('.material-wrapper, .common-material')
    if (matEl) {
      material = matEl.innerHTML || matEl.textContent || undefined
    }

    // 4. 答案与深度解析提取
    let answer = ''
    let analysis = ''
    const answerEl = qEl.querySelector(
      '.correct-answer, .answer, .right-answer, .solution-answer'
    )
    if (answerEl) {
      const match = answerEl.textContent?.match(/[A-E]/i)
      if (match) answer = match[0].toUpperCase()
    }

    const analysisEl = qEl.querySelector(
      '.solution-content, .analysis, .solution, .explain, .detail'
    )
    if (analysisEl) {
      analysis = (analysisEl as HTMLElement).innerHTML || (analysisEl.textContent || '').trim()
    }

    // 提取题目全局真实 ID
    const domQId = qEl.getAttribute('data-question-id') || qEl.getAttribute('data-id')
    const finalQId = domQId && /^\d+$/.test(domQId) ? Number(domQId) : order

    questions.push({
      id: finalQId,
      question_id: finalQId,
      order_num: order,
      type: 'single_choice',
      stem,
      options,
      answer: answer || undefined,
      analysis: analysis || undefined,
      material,
    })
    order++
  }

  if (questions.length === 0) {
    return null
  }

  const hasAnswers = questions.some((q) => Boolean(q.answer || q.analysis))

  return {
    title,
    source_platform: 'fenbi',
    total_questions: questions.length,
    sections: [
      {
        name: '行政职业能力测验',
        questions,
      },
    ],
    metadata: {
      from_dom: true,
      hasAnswers,
      scene: isMistakeUrl ? 'mistake' : undefined,
      keypointName: detectedKeypoint || undefined,
      created_at: new Date().toISOString(),
    },
  }
}

