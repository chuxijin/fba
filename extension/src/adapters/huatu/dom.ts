import { UnifiedPaper, UnifiedQuestion, RenderTypographySettings } from '../types'
import { applyNegativeKeywordsBold } from '../common'

/**
 * 华图在线做题页面 DOM 智能提取引擎 (屏幕可见即所得)
 * 适用于真题、模考大赛、错题集、专项集训等各类做题与解析页面
 */
export function extractHuatuPaperFromDom(settings: RenderTypographySettings): UnifiedPaper | null {
  // 1. 智能提取试卷/做题标题
  let title = '华图在线做题练习'
  const titleSelectors = [
    '.exam-title',
    '.paper-title',
    '.practice-title',
    '.title-box',
    '.head-title',
    '.header-title',
    'h1',
    'h2',
  ]

  for (const sel of titleSelectors) {
    const el = document.querySelector(sel)
    const txt = el?.textContent?.trim()
    if (txt && txt.length > 2 && !txt.includes('华图首页') && !txt.includes('退出')) {
      title = txt
      break
    }
  }

  if (title === '华图在线做题练习' && document.title) {
    const cleanDocTitle = document.title
      .replace(/[-_].*(华图|粉笔|题库|网校|公务员).*/i, '')
      .trim()
    if (cleanDocTitle) {
      title = cleanDocTitle
    }
  }

  // 2. 泛化匹配题目容器 (支持单题做题、列表解析、错题本)
  const questionSelectors = [
    '.question-box',
    '.question-item',
    '.timu-box',
    '.timu-item',
    '.exercise-item',
    '.test-item',
    '.exam-item',
    '.point-content-box',
    '[data-question-id]',
  ]

  let questionNodes: Element[] = []
  for (const sel of questionSelectors) {
    const nodes = Array.from(document.querySelectorAll(sel))
    if (nodes.length > 0) {
      questionNodes = nodes
      break
    }
  }

  // 若无成批题目列表，检查是否为单题沉浸模式容器 (如 .current-question, #app .question)
  if (questionNodes.length === 0) {
    const singleContainer = document.querySelector('.current-question, .single-question, .active-question')
    if (singleContainer) {
      questionNodes = [singleContainer]
    }
  }

  if (questionNodes.length === 0) {
    return null
  }

  // 3. 提取共用大材料 (若有)
  let pageMaterialHtml: string | undefined = undefined
  const materialSelectors = [
    '.material-box',
    '.material-content',
    '.material',
    '.article-box',
    '.paper-material',
  ]
  for (const sel of materialSelectors) {
    const matEl = document.querySelector(sel)
    if (matEl && matEl.innerHTML.trim().length > 10) {
      pageMaterialHtml = matEl.innerHTML.trim()
      break
    }
  }

  // 4. 逐题提取题干、选项、答案与解析
  const questions: UnifiedQuestion[] = []
  let order = 1

  for (const qEl of questionNodes) {
    // 题干匹配
    const stemSelectors = ['.stem', '.question-stem', '.timu-title', '.title', '.q-stem', '.stem-box']
    let stemEl: Element | null = null
    for (const sSel of stemSelectors) {
      stemEl = qEl.querySelector(sSel)
      if (stemEl) break
    }

    let stemHtml = stemEl ? stemEl.innerHTML.trim() : ''
    // 若找不到专属题干标签，尝试取前部文本
    if (!stemHtml) {
      stemHtml = qEl.firstElementChild ? qEl.firstElementChild.innerHTML.trim() : qEl.innerHTML.trim()
    }

    if (!stemHtml) continue

    // 反向设问陷阱词智能加粗
    if (settings.boldNegativeQuestion) {
      stemHtml = applyNegativeKeywordsBold(stemHtml)
    }

    // 选项匹配
    const optionSelectors = [
      '.choice-item',
      '.option-item',
      '.choices li',
      '.options label',
      '.option-box',
      '.answer-item',
      '.options > div',
    ]

    let optionNodes: Element[] = []
    for (const oSel of optionSelectors) {
      const nodes = Array.from(qEl.querySelectorAll(oSel))
      if (nodes.length >= 2) {
        optionNodes = nodes
        break
      }
    }

    const options: string[] = []
    for (const optEl of optionNodes) {
      const optHtml = optEl.innerHTML.trim()
      if (optHtml) {
        options.push(optHtml)
      }
    }

    // 答案与解析匹配
    let answer = ''
    let analysis = ''

    const answerEl = qEl.querySelector('.answer, .correct-answer, .right-answer, .key-answer')
    if (answerEl) {
      const ansMatch = (answerEl.textContent || '').match(/[A-E]/i)
      if (ansMatch) {
        answer = ansMatch[0].toUpperCase()
      }
    }

    const analysisEl = qEl.querySelector('.analysis, .explanation, .analysis-box, .resolve-box, .solution')
    if (analysisEl) {
      analysis = analysisEl.innerHTML.trim()
    }

    questions.push({
      id: order,
      order_num: order,
      type: 'single_choice',
      stem: stemHtml,
      options,
      answer,
      analysis,
      material: pageMaterialHtml,
    })

    order++
  }

  if (questions.length === 0) {
    return null
  }

  return {
    title,
    source_platform: 'huatu',
    total_questions: questions.length,
    sections: [
      {
        name: '行政职业能力测验',
        questions,
      },
    ],
    metadata: {
      is_dom_extracted: true,
      extracted_at: new Date().toISOString(),
      hasAnswers: questions.some((q) => Boolean(q.answer && q.answer.trim())),
    },
  }
}
