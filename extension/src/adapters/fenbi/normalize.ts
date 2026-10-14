import { UnifiedQuestion, RenderTypographySettings } from '../types'
import { applyNegativeKeywordsBold } from '../common'

/**
 * 标准化解析参考答案（兼容对象 choice、字符串与数字索引）
 */
export function formatAnswerChoice(rawAnswer: any): string {
  if (typeof rawAnswer === 'string') {
    if (/^\d+$/.test(rawAnswer)) {
      const idx = parseInt(rawAnswer, 10)
      return ['A', 'B', 'C', 'D', 'E', 'F'][idx] || rawAnswer
    }
    return rawAnswer.trim().toUpperCase()
  }
  if (typeof rawAnswer === 'number') {
    return ['A', 'B', 'C', 'D', 'E', 'F'][rawAnswer] || String(rawAnswer)
  }
  if (rawAnswer && typeof rawAnswer === 'object') {
    const choice = rawAnswer.choice ?? rawAnswer.answer ?? rawAnswer.correct ?? rawAnswer.val
    if (typeof choice === 'number') {
      return ['A', 'B', 'C', 'D', 'E', 'F'][choice] || String(choice)
    }
    if (typeof choice === 'string') {
      if (/^\d+$/.test(choice)) {
        const idx = parseInt(choice, 10)
        return ['A', 'B', 'C', 'D', 'E', 'F'][idx] || choice
      }
      return choice.trim().toUpperCase()
    }
  }
  return ''
}

/**
 * 提取并清洗题目选项（全面兼容 accessories 富文本附件与 options 数组）
 */
export function extractQuestionOptions(raw: any): string[] {
  let optionsList: string[] = []

  // 1. 优先提取 accessories 结构 (粉笔标准富文本附件)
  if (Array.isArray(raw.accessories)) {
    const optAcc = raw.accessories.find((acc: any) => acc && acc.options && Array.isArray(acc.options))
    if (optAcc && Array.isArray(optAcc.options)) {
      optionsList = optAcc.options.map((item: any) => (typeof item === 'string' ? item : item.content || ''))
    }
  }

  // 2. 降级提取平铺的 options 数组
  if (optionsList.length === 0 && Array.isArray(raw.options)) {
    optionsList = raw.options.map((item: any) => (typeof item === 'string' ? item : item.content || ''))
  }

  // 3. 去除可能混入的 A. / B. / A、等冗余选项前缀
  return optionsList.map((opt) => opt.replace(/^[A-Da-d][\.\、\s\:\：\s]*/, '').trim())
}

/**
 * 清洗并规范化粉笔行内推导符号（将微型箭头、横线等小图标转为原生 Unicode 文本字符）
 */
export function normalizeInlineSymbols(html: string): string {
  if (!html) return ''
  return html
    // 1. 保护填空挖空：将 <u> 内包含的空白/&nbsp;占位符转换为公考标准下划线
    .replace(/<u[^>]*>[\s\u00a0\xa0&nbsp;]*<\/u>/gi, '______')
    // 2. 域名智能解密替换：将 fenbike.cn 纠偏为 fbstatic.cn 以免获取加密混淆图片
    .replace(/fb\.fenbike\.cn/g, 'fb.fbstatic.cn')
    .replace(/fenbike\.cn/g, 'fbstatic.cn')
    .replace(/<img[^>]*?(?:22356dff5dbcdc4c37e6632600979a0e|arrow|rightarrow)[^>]*?>/gi, ' → ')
    .replace(/<img[^>]*?(?:abe086ab947f7a5b37c464c4ce74f115|dash)[^>]*?>/gi, ' — ')
    .replace(/<img[^>]*?alt=["']([^"']+)["'][^>]*?>/gi, (_match, alt) => {
      const cleanAlt = (alt || '').trim()
      if (['→', '->', '=>', 'arrow'].includes(cleanAlt)) return ' → '
      if (['—', '-', '--', 'dash'].includes(cleanAlt)) return ' — '
      return cleanAlt ? ` ${cleanAlt} ` : ''
    })
}

/**
 * 单道粉笔原始题目的单一归一化纯函数 (DRY: 模考、练习、错题、反查全量复用)
 */
export function normalizeFenbiQuestion(
  raw: any,
  orderNum: number,
  settings: RenderTypographySettings,
  materialHtml?: string,
  fallbackSource?: string
): UnifiedQuestion {
  // 1. 题干与反向陷阱词智能加粗
  let stem = normalizeInlineSymbols(raw.content || raw.stem || '')
  if (settings.boldNegativeQuestion) {
    stem = applyNegativeKeywordsBold(stem)
  }

  // 2. 选项清洗
  const options = extractQuestionOptions(raw)

  // 3. 参考答案标准化映射 (兼容 choice: 1 -> 'B')
  const answer = formatAnswerChoice(raw.correctAnswer ?? raw.answer)

  // 4. 逐题名师深度解析
  const analysis = normalizeInlineSymbols(raw.solution || raw.analysis || raw.explanation || '')

  // 5. 真实真题出处 (如: 2026年福建事业单位联考《职业能力倾向测验》（网友回忆版）第94题)
  const source = raw.source || raw.paperName || fallbackSource || undefined

  const qid = Number(raw.id || raw.questionId || raw.globalId || orderNum)

  return {
    id: qid,
    question_id: qid,
    order_num: orderNum,
    type: raw.type === 1 ? 'single_choice' : String(raw.type || 'single_choice'),
    stem,
    options,
    answer: answer || undefined,
    analysis: analysis || undefined,
    material: materialHtml,
    source,
  }
}

/**
 * 试卷大标题规范化纯函数（确保错题带上“粉笔”，规范统一）
 */
export function formatFenbiPaperTitle(rawTitle: string, isMistakeScene: boolean, keypointName: string = ''): string {
  let title = (rawTitle || '').trim()

  if (isMistakeScene) {
    const cleanKp = (keypointName || title)
      .replace(/粉笔/g, '')
      .replace(/错题/g, '')
      .replace(/题库/g, '')
      .replace(/[-_].*$/, '')
      .trim() || '专项'
    return `粉笔${cleanKp}错题`
  }

  if (!title) {
    return '粉笔全真模拟考卷'
  }

  if (!title.includes('粉笔') && !title.includes('模考') && !title.includes('真题')) {
    title = `粉笔${title}`
  }

  return title
}
