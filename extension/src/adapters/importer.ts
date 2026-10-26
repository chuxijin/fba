/**
 * 错题库导入适配层
 *
 * 职责：把当前页面捕获到的「错题」统一映射成后端
 * `POST /api/v1/qbank-v2/wrong-questions/external` 所需的请求体。
 *
 * 约束（来自后端 schema，违反会 400/422）：
 *  1. `entry_source` 必须是 manual / ocr / import 之一 → 这里固定为 import
 *  2. `answer` 为必填权威答案 → 缺答案的题直接跳过，不带病提交
 *  3. `entry_metadata.source` 必须非空 → 统一写入平台中文名
 *  4. `source_system` 与 `external_key` 必须成对出现（后端模型校验）
 *  5. 绝对不能传 summary / review_data / tag_ids / knowledge_point_ids，
 *     否则后端会把该题直接标记成「已复盘」，从待复盘队列里消失
 */

import { UnifiedPaper, UnifiedQuestion } from './types'

const OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

const PLATFORM_LABELS: Record<string, string> = {
  fenbi: '粉笔',
  huatu: '华图',
  shikaobang: '事考帮',
  other: '外部导入',
}

export interface WrongImportOption {
  option_code: string
  content: string
  sort_order: number
}

/** 后端 CreateExternalWrongQuestionParam 的最小可用子集 */
export interface WrongImportMaterial {
  link_key: string
  title: string
  content: string
  content_format: 'html'
  role: 'passage'
  sort_order: number
}

export interface WrongImportItem {
  idempotency_key: string
  entry_source: 'import'
  stem: string
  content_format: 'html'
  question_type: 'single_choice' | 'multiple_choice' | 'fill_blank'
  options: WrongImportOption[]
  answer: { answer_data: { correct: string | string[] }; grading_method: 'exact' | 'set' }
  /** 用户当时的作答；供错题本回显，不参与判分 */
  wrong_response?: string | string[]
  explanations: { content: string; is_default: boolean }[]
  /** 材料：服务端据此创建材料实体并关联，不再拼进题干 */
  materials?: WrongImportMaterial[]
  entry_metadata: { source: string }
  source_system: string
  external_key: string
  /** 仅用于 UI 展示与失败定位，不会提交给后端 */
  order?: number
}

export interface SkippedQuestion {
  order?: number
  reason: string
}

export interface ImportBuildResult {
  items: WrongImportItem[]
  skipped: SkippedQuestion[]
}

export type ImportStatus = 'idle' | 'running' | 'done' | 'error'

export interface ImportState {
  status: ImportStatus
  done: number
  total: number
  imported: number
  failed: number
  skipped: number
  message?: string
  /** 最近一次成功导入的批次 ID，用于整批撤销 */
  batchId?: string
}

export const IDLE_IMPORT_STATE: ImportState = {
  status: 'idle',
  done: 0,
  total: 0,
  imported: 0,
  failed: 0,
  skipped: 0,
}

export function platformLabelOf(paper: UnifiedPaper): string {
  return PLATFORM_LABELS[String(paper?.source_platform || 'other')] || PLATFORM_LABELS.other
}

/**
 * 错题来源展示名。
 *
 * 用「用户当时做的那套卷子的名称」，而不是平台名 ——
 * "粉笔" 这种平台级称呼太宽泛，无法区分是哪一套题；
 * 试卷标题才是有意义的来源标识。标题缺失时才回落到平台名。
 */
export function buildSourceLabel(paper: UnifiedPaper): string {
  const title = String(paper?.title || '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!title) return platformLabelOf(paper)
  return title.slice(0, 100)
}

/**
 * 统计当前试卷里的错题数量。
 * 优先按 is_wrong 实打实计数，取不到再回落到适配器算好的元数据。
 */
export function countWrongQuestions(paper: UnifiedPaper | null | undefined): number {
  if (!paper || !Array.isArray(paper.sections)) return 0
  let count = 0
  for (const section of paper.sections) {
    for (const question of section.questions || []) {
      if (question.is_wrong === true) count += 1
    }
  }
  if (count > 0) return count
  const fromMeta = Number((paper.metadata as any)?.totalWrong || 0)
  return Number.isFinite(fromMeta) && fromMeta > 0 ? fromMeta : 0
}

/**
 * 收集错题并保留所属章节（原试卷模块名，如「资料分析」）。
 * 章节写入 entry_metadata.section_name，供小程序答题卡按章节分组跳题。
 */
export function collectWrongQuestionsWithSection(
  paper: UnifiedPaper
): { question: UnifiedQuestion; sectionName?: string }[] {
  if (!paper || !Array.isArray(paper.sections)) return []
  const meta: any = paper.metadata || {}
  const wrongIds = new Set<number>((meta.wrongQuestionIds || []).map(Number))
  const wrongOrders = new Set<number>((meta.wrongQuestionOrders || []).map(Number))

  const picked: { question: UnifiedQuestion; sectionName?: string }[] = []
  for (const section of paper.sections) {
    const sectionName = String(section?.name || '').trim() || undefined
    for (const question of section.questions || []) {
      const qid = Number(question.question_id ?? question.id)
      const isWrong =
        question.is_wrong === true ||
        (Number.isFinite(qid) && wrongIds.has(qid)) ||
        (question.order_num != null && wrongOrders.has(Number(question.order_num)))
      if (isWrong) picked.push({ question, sectionName })
    }
  }
  return picked
}

/**
 * 收集错题。
 * 判定顺序与既有「仅导出错题」逻辑保持一致，避免两处口径不同：
 * is_wrong 标记 → 错题 ID 集合 → 错题题号集合
 */
export function collectWrongQuestions(paper: UnifiedPaper): UnifiedQuestion[] {
  return collectWrongQuestionsWithSection(paper).map((item) => item.question)
}

/**
 * 图片尺寸规范化。
 *
 * 问题：原站靠 CSS class 控制图片尺寸，这些 class 在我们这边没有对应样式，
 * 于是富文本渲染时图片会被拉满整行（选项里、解析里都撑破排版）。
 *
 * 保留像素尺寸和公式的行内语义，移除站点 class 与全宽拉伸样式。
 * 原站只提供图片 URL 时，由客户端加载图片后读取自然尺寸。
 */
function normalizeRichTextImages(
  html: string,
  context: 'stem' | 'option' | 'explanation'
): string {
  const text = String(html || '')
  if (!/<img\b/i.test(text))
    return text

  return text.replace(/<img\b[^>]*>/gi, (tag) => {
    const attrs: Record<string, string> = {}
    for (const match of tag.matchAll(/\s([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g)) {
      attrs[match[1].toLowerCase()] = match[2] ?? match[3] ?? match[4]
    }
    const dimension = (name: string) => {
      const styleValue = attrs.style?.match(new RegExp(`(?:^|;)\\s*${name}\\s*:\\s*([^;]+)`, 'i'))?.[1]
      for (const value of [styleValue?.replace(/!important/gi, '').trim(), attrs[name]]) {
        if (value && /^\d+(?:\.\d+)?(?:px)?$/i.test(value) && parseFloat(value) > 0)
          return parseFloat(value)
      }
      return undefined
    }
    const width = dimension('width')
    const height = dimension('height')
    const formula = attrs.flag?.toLowerCase() === 'tex' || Boolean(attrs['data-latex'])
      || /\/accessories\/formulas\b|\/formulas\?latex=/i.test(attrs.src || '')
    const inline = context === 'option' || formula || attrs['data-image-layout'] === 'inline'
      || /(?:^|;)\s*display\s*:\s*inline(?:-block)?\b/i.test(attrs.style || '')
      || Boolean(width && height && width <= 120 && height <= 60)
    const layout = inline
      ? 'display:inline-block;vertical-align:middle;margin:0 2px;'
      : 'display:block;margin:8px 0;'
    const sizing = `${width ? `width:${width}px;` : ''}max-width:100%;height:auto;${layout}`
    const cleaned = tag
      .replace(/\s(?:class|style|width|height|loading)\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, '')
      .replace(/\s*\/?>$/, '')
    const dimensions = `${width ? ` width="${width}"` : ''}${height ? ` height="${height}"` : ''}`
    const markers = `${formula && !attrs.flag ? ' flag="tex"' : ''}${inline && !attrs['data-image-layout'] ? ' data-image-layout="inline"' : ''}`
    return `${cleaned}${dimensions}${markers} style="${sizing}">`
  })
}

/** 选项归一化：兼容 string[] 与 { key, value }[] 两种形态 */
function normalizeOptions(raw: UnifiedQuestion['options']): WrongImportOption[] {
  if (!Array.isArray(raw)) return []
  const normalized: { option_code: string; content: string }[] = []

  raw.forEach((item, index) => {
    if (typeof item === 'string') {
      const text = item.trim()
      if (text) {
        normalized.push({ option_code: OPTION_LETTERS[index] || String(index + 1), content: text })
      }
      return
    }
    if (item && typeof item === 'object') {
      const key = String((item as any).key ?? '').trim().toUpperCase()
      const value = String((item as any).value ?? '').trim()
      if (value) {
        normalized.push({ option_code: key || OPTION_LETTERS[index] || String(index + 1), content: value })
      }
    }
  })

  return normalized.map((option, index) => ({
    ...option,
    content: normalizeRichTextImages(option.content, 'option'),
    sort_order: index,
  }))
}

/** 答案解析：支持 "B" / "AB" / "A,B" / "A、B" 等写法 */
function splitAnswerCodes(answer?: string): string[] {
  const raw = String(answer ?? '').trim().toUpperCase()
  if (!raw) return []

  const tokens = raw.split(/[,，、\s;；/|]+/).map((item) => item.trim()).filter(Boolean)
  if (tokens.length === 1 && /^[A-H]{2,}$/.test(tokens[0])) {
    return tokens[0].split('')
  }
  return tokens
}

/** 考生作答转成后端快照：单选保留字符串，多选拆成数组 */
function buildWrongResponse(answer?: string): string | string[] | undefined {
  const tokens = String(answer ?? '')
    .split(/[,，、\s;；/|]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (tokens.length === 0) return undefined
  return tokens.length === 1 ? tokens[0] : tokens
}

/**
 * 题干不再拼装材料。
 * 材料走 materials 字段，由服务端建材料实体并关联，供多题共享、可版本化。
 */
function buildStem(question: UnifiedQuestion): string {
  return normalizeRichTextImages(String(question.stem || '').trim(), 'stem')
}

/**
 * 材料复用键：同一篇材料下的多道题会拿到完全相同的材料内容，
 * 用内容哈希作为 link_key，服务端据此只建一份材料实体。
 */
function materialLinkKey(content: string): string {
  let hash = 0x811c9dc5
  for (let i = 0; i < content.length; i += 1) {
    hash ^= content.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193)
  }
  return `m${(hash >>> 0).toString(36)}`
}

/** 构造材料数组：没有材料就返回空数组，由调用方决定是否带上该字段 */
function buildMaterials(question: UnifiedQuestion): WrongImportMaterial[] {
  const material = String(question.material || '').trim()
  if (!material) return []
  return [
    {
      link_key: materialLinkKey(material),
      title: '材料',
      content: normalizeRichTextImages(material, 'stem'),
      content_format: 'html',
      role: 'passage',
      sort_order: 0,
    },
  ]
}

/** 试卷唯一键：优先考试 ID，退化为标题，清洗掉非法字符 */
function buildPaperKey(paper: UnifiedPaper): string {
  const meta: any = paper.metadata || {}
  const seed = String(meta.exam_id || meta.examId || paper.title || 'paper')
  return seed.replace(/[\s:：/\\?#]+/g, '_').replace(/_+/g, '_').slice(0, 60) || 'paper'
}

/**
 * 把当前试卷中的错题映射成后端导入请求体。
 * 无题干或缺权威答案的题目会被跳过并记录原因。
 */
export function buildWrongImportItems(paper: UnifiedPaper): ImportBuildResult {
  const platform = String(paper?.source_platform || 'other')
  const sourceLabel = buildSourceLabel(paper)
  const paperKey = buildPaperKey(paper)

  const items: WrongImportItem[] = []
  const skipped: SkippedQuestion[] = []

  for (const { question, sectionName } of collectWrongQuestionsWithSection(paper)) {
    const order = question.order_num
    const stem = buildStem(question)
    if (!stem) {
      skipped.push({ order, reason: '题干为空' })
      continue
    }

    const options = normalizeOptions(question.options)
    const answerCodes = splitAnswerCodes(question.answer)
    if (answerCodes.length === 0) {
      // 后端 answer 必填：没有权威答案就无法判分，导入后也进不了刷题系统
      skipped.push({ order, reason: '缺少权威答案' })
      continue
    }

    const analysis = String(question.analysis || '').trim()
    const qid = Number(question.question_id ?? question.id)
    const externalKey = `${platform}:${paperKey}:${Number.isFinite(qid) && qid > 0 ? qid : `o${order ?? items.length + 1}`}`

    let questionType: WrongImportItem['question_type'] = 'fill_blank'
    let answerData: string | string[] = answerCodes[0]
    let gradingMethod: 'exact' | 'set' = 'exact'

    if (options.length > 0) {
      if (answerCodes.length > 1) {
        questionType = 'multiple_choice'
        answerData = answerCodes
        gradingMethod = 'set'
      } else {
        questionType = 'single_choice'
        answerData = answerCodes[0]
        gradingMethod = 'exact'
      }
    } else if (answerCodes.length > 1) {
      answerData = answerCodes
      gradingMethod = 'set'
    }

    const materials = buildMaterials(question)
    const wrongResponse = buildWrongResponse(question.user_answer)

    items.push({
      // 稳定幂等键：同一个页面同一道题重复导入时保持不变
      idempotency_key: `ext-${externalKey}`.slice(0, 128),
      entry_source: 'import',
      stem,
      content_format: 'html',
      question_type: questionType,
      options,
      answer: { answer_data: { correct: answerData }, grading_method: gradingMethod },
      ...(wrongResponse !== undefined ? { wrong_response: wrongResponse } : {}),
      explanations: analysis
        ? [{ content: normalizeRichTextImages(analysis, 'explanation'), is_default: true }]
        : [],
      ...(materials.length > 0 ? { materials } : {}),
      // 必填：后端校验「错题来源不能为空」；section_name 供答题卡按章节分组
      entry_metadata: {
        source: sourceLabel,
        ...(sectionName ? { section_name: sectionName } : {}),
      },
      source_system: platform,
      external_key: externalKey.slice(0, 255),
      order,
    })
  }

  return { items, skipped }
}
