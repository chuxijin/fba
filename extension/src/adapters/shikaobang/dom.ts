import { UnifiedPaper, UnifiedQuestion, RenderTypographySettings } from '../types'
import { applyNegativeKeywordsBold } from '../common'

/**
 * 事考帮在线做题页面 DOM 智能提取引擎 (屏幕可见即所得)
 * 适用于真题、模考大赛、错题集、专项集训等各类做题与解析页面
 */
export function extractShikaobangPaperFromDom(settings: RenderTypographySettings): UnifiedPaper | null {
  // 1. 提取试卷/做题标题
  let title = '事业单位在线练习'
  const titleSelectors = [
    '.exam-title',
    '.paper-name',
    '.paper-title',
    '.exercise-title',
    '.head-title',
    'h1',
    'h2',
  ]

  for (const sel of titleSelectors) {
    const el = document.querySelector(sel)
    const txt = el?.textContent?.trim()
    if (txt && txt.length > 2 && !txt.includes('首页') && !txt.includes('退出')) {
      title = txt
      break
    }
  }

  if (title === '事业单位在线练习' && document.title) {
    const cleanDocTitle = document.title
      .replace(/[-_].*(事考帮|题库|网校|事业单位|公务员).*/i, '')
      .trim()
    if (cleanDocTitle) {
      title = cleanDocTitle
    }
  }

  // 2. 匹配题目容器
  const questionSelectors = [
    '.question-box',
    '.question-item',
    '.exercise-item',
    '.timu-box',
    '.timu-item',
    '.test-item',
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

  if (questionNodes.length === 0) {
    const singleContainer = document.querySelector('.current-question, .single-question, .active-question, .question-content')
    if (singleContainer) {
      questionNodes = [singleContainer]
    }
  }

  if (questionNodes.length === 0) {
    return null
  }

  // 3. 提取共用材料
  let pageMaterialHtml: string | undefined = undefined
  const materialSelectors = [
    '.material-box',
    '.material-content',
    '.qd-content',
    '.article-box',
  ]
  for (const sel of materialSelectors) {
    const matEl = document.querySelector(sel)
    if (matEl && matEl.innerHTML.trim().length > 10) {
      pageMaterialHtml = matEl.innerHTML.trim()
      break
    }
  }

  // 4. 逐题提取
  const questions: UnifiedQuestion[] = []
  let order = 1

  for (const qEl of questionNodes) {
    // 题干匹配
    const stemSelectors = ['.stem', '.question-title', '.title', '.timu-title', '.content', '.q-stem']
    let stemEl: Element | null = null
    for (const sSel of stemSelectors) {
      stemEl = qEl.querySelector(sSel)
      if (stemEl) break
    }

    let stemHtml = stemEl ? stemEl.innerHTML.trim() : ''
    if (!stemHtml) {
      stemHtml = qEl.firstElementChild ? qEl.firstElementChild.innerHTML.trim() : qEl.innerHTML.trim()
    }
    if (!stemHtml) continue

    if (settings.boldNegativeQuestion) {
      stemHtml = applyNegativeKeywordsBold(stemHtml)
    }

    // 选项匹配
    const optionSelectors = [
      '.option-item',
      '.opt-item',
      '.choice-item',
      '.options li',
      '.options > div',
      '.answer-item',
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

    const analysisEl = qEl.querySelector('.analysis, .analyze, .explanation, .resolve-box')
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
    source_platform: 'shikaobang' as any,
    total_questions: questions.length,
    sections: [
      {
        name: '职业能力倾向测验',
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
