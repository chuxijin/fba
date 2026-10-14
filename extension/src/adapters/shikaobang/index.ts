import { UnifiedPaper, UnifiedSection, UnifiedQuestion, RenderTypographySettings } from '../types'
import { applyNegativeKeywordsBold } from '../common'

/**
 * 事考帮 (shikaobang.cn) 题库与试卷数据归一化适配器
 * 支持成套模拟试卷 (getPaperContent) 与智能练习/错题刷题 (get-question)
 */
export function adaptShikaobangPaper(raw: any, settings: RenderTypographySettings): UnifiedPaper {
  const data = raw.data || raw

  // 判断是否为成套模考试卷 (含 paper 与 groups 结构)
  if (data.paper || (Array.isArray(data.groups) && data.groups.length > 0)) {
    return adaptShikaobangExamPaper(data, settings)
  }

  // 否则作为智能练习/错题/专项刷题处理 (含 question_data 结构)
  return adaptShikaobangExercisePaper(data, settings)
}

/**
 * 适配成套试卷 (如全真模考、历年真题)
 */
function adaptShikaobangExamPaper(data: any, settings: RenderTypographySettings): UnifiedPaper {
  const paperInfo = data.paper || {}
  const paperTitle = paperInfo.name || data.name || data.title || '事业单位全真模拟考试'

  // 1. 建立大材料索引 (data.qd)
  const qdMap = new Map<string | number, string>()
  if (data.qd && typeof data.qd === 'object') {
    for (const [key, val] of Object.entries(data.qd)) {
      if (Array.isArray(val) && val.length > 0) {
        const matText = val[0]?.text || val[0]?.c || ''
        qdMap.set(key, parseQuillDelta(matText))
        qdMap.set(Number(key), parseQuillDelta(matText))
      }
    }
  }

  // 2. 解析大模块 (groups) 与其下题目 (questions: 二维数组)
  const sections: UnifiedSection[] = []
  const rawGroups: any[] = Array.isArray(data.groups) ? data.groups : []
  const rawQuestionsGroup: any[] = Array.isArray(data.questions) ? data.questions : []

  let globalOrder = 1

  for (let gIdx = 0; gIdx < rawGroups.length; gIdx++) {
    const grp = rawGroups[gIdx]
    const secName = grp.title || grp.name || `模块 ${gIdx + 1}`
    const rawList = Array.isArray(rawQuestionsGroup[gIdx]) ? rawQuestionsGroup[gIdx] : []

    const secQuestions: UnifiedQuestion[] = []
    for (const q of rawList) {
      if (!q) continue

      // 材料匹配 (通过 q.qd 字段)
      let materialHtml: string | undefined = undefined
      if (q.qd && qdMap.has(q.qd)) {
        materialHtml = qdMap.get(q.qd)
      }

      secQuestions.push(parseExamQuestionItem(q, globalOrder++, materialHtml, settings))
    }

    if (secQuestions.length > 0) {
      sections.push({
        name: secName,
        questions: secQuestions,
      })
    }
  }

  // 兜底：若 groups 未匹配到题目，尝试扁平展开
  if (sections.length === 0 && rawQuestionsGroup.length > 0) {
    const flatQuestions: UnifiedQuestion[] = []
    for (const item of rawQuestionsGroup.flat()) {
      if (item) {
        flatQuestions.push(parseExamQuestionItem(item, globalOrder++, undefined, settings))
      }
    }
    if (flatQuestions.length > 0) {
      sections.push({
        name: '职业能力倾向测验',
        questions: flatQuestions,
      })
    }
  }

  const totalQuestions = sections.reduce((sum, sec) => sum + sec.questions.length, 0)

  return {
    title: paperTitle,
    source_platform: 'shikaobang' as any,
    total_questions: totalQuestions,
    sections,
    metadata: {
      paper_id: paperInfo.id,
      qv_no: paperInfo.qv_no,
      created_at: new Date().toISOString(),
      hasAnswers: sections.some((s) => s.questions.some((q) => Boolean(q.answer))),
    },
  }
}

/**
 * 适配智能练习、错题刷题与专项练习 (get-question)
 */
function adaptShikaobangExercisePaper(data: any, settings: RenderTypographySettings): UnifiedPaper {
  let title = data.title || data.req_param?.name || '事业单位专项练习'
  if (data.req_param?.mode === 'wrong') {
    title = `${data.req_param?.name || '专项'}·错题重练`
  }

  // 1. 建立材料映射表 (qd_data)
  const qdMap = new Map<string | number, string>()
  if (data.qd_data && typeof data.qd_data === 'object') {
    for (const [key, val] of Object.entries(data.qd_data)) {
      if (val && typeof val === 'object') {
        const matText = (val as any).content || (val as any).text || ''
        qdMap.set(key, parseQuillDelta(matText))
        qdMap.set(Number(key), parseQuillDelta(matText))
      }
    }
  }

  // 2. 提取题目字典或列表
  let questionList: any[] = []
  if (data.question_data) {
    if (Array.isArray(data.question_data)) {
      questionList = data.question_data
    } else if (typeof data.question_data === 'object') {
      questionList = Object.values(data.question_data)
    }
  }

  const parsedQuestions: UnifiedQuestion[] = []
  let globalOrder = 1

  for (const q of questionList) {
    if (!q) continue

    // 关联材料
    let materialHtml: string | undefined = undefined
    if (q.qd_id && qdMap.has(q.qd_id)) {
      materialHtml = qdMap.get(q.qd_id)
    }

    parsedQuestions.push(parseExerciseQuestionItem(q, globalOrder++, materialHtml, settings))
  }

  return {
    title,
    source_platform: 'shikaobang' as any,
    total_questions: parsedQuestions.length,
    sections: [
      {
        name: '职业能力倾向测验',
        questions: parsedQuestions,
      },
    ],
    metadata: {
      exercise_history_type: data.exercise_history_type,
      history_id: data.history_id,
      created_at: new Date().toISOString(),
      hasAnswers: parsedQuestions.some((q) => Boolean(q.answer)),
    },
  }
}

/**
 * 解析试卷单题 (getPaperContent)
 */
function parseExamQuestionItem(
  q: any,
  orderNum: number,
  materialHtml: string | undefined,
  settings: RenderTypographySettings
): UnifiedQuestion {
  // 1. 题干解码 (q.c)
  let stemRaw = q.c?.c || q.c?.text || q.c || ''
  let stemHtml = parseQuillDelta(stemRaw)
  if (settings.boldNegativeQuestion) {
    stemHtml = applyNegativeKeywordsBold(stemHtml)
  }

  // 2. 选项解码 (q.a.opt: [{ k: 'A', c: '...' }])
  const optionsList: string[] = []
  const opts = q.a?.opt || q.options || []
  if (Array.isArray(opts)) {
    for (const opt of opts) {
      if (typeof opt === 'string') {
        optionsList.push(opt)
      } else if (opt && typeof opt === 'object') {
        const optText = parseQuillDelta(opt.c || opt.text || '')
        optionsList.push(optText)
      }
    }
  }

  // 3. 答案提取 (q.a.a: 'B')
  let answer = ''
  if (q.a?.a) {
    answer = String(q.a.a).trim().toUpperCase()
  } else if (q.answer) {
    answer = Array.isArray(q.answer) ? q.answer.join('') : String(q.answer)
  }

  // 4. 解析解码 (q.p.c)
  let analysisRaw = q.p?.c || q.p?.text || q.analyze || q.analysis || ''
  const analysisHtml = parseQuillDelta(analysisRaw)

  return {
    id: q.id || orderNum,
    question_id: q.qbcenter_id || q.id,
    order_num: orderNum,
    type: q.t === 'single' || q.type === 1 ? 'single_choice' : String(q.t || q.type || 'single_choice'),
    stem: stemHtml,
    options: optionsList,
    answer,
    analysis: analysisHtml,
    material: materialHtml,
    source: q.source || undefined,
  }
}

/**
 * 解析练习单题 (get-question)
 */
function parseExerciseQuestionItem(
  q: any,
  orderNum: number,
  materialHtml: string | undefined,
  settings: RenderTypographySettings
): UnifiedQuestion {
  // 1. 题干解码 (q.content)
  let stemRaw = q.content || q.stem || ''
  let stemHtml = parseQuillDelta(stemRaw)
  if (settings.boldNegativeQuestion) {
    stemHtml = applyNegativeKeywordsBold(stemHtml)
  }

  // 2. 选项解码 (q.options: [{ k: 'A', c: '...' }])
  const optionsList: string[] = []
  const opts = q.options || q.a?.opt || []
  if (Array.isArray(opts)) {
    for (const opt of opts) {
      if (typeof opt === 'string') {
        optionsList.push(opt)
      } else if (opt && typeof opt === 'object') {
        const optText = parseQuillDelta(opt.c || opt.text || '')
        optionsList.push(optText)
      }
    }
  }

  // 3. 答案提取 (q.answer: ["A"])
  let answer = ''
  if (Array.isArray(q.answer)) {
    answer = q.answer.join('').trim().toUpperCase()
  } else if (q.answer) {
    answer = String(q.answer).trim().toUpperCase()
  }

  // 4. 解析解码 (q.analyze)
  let analysisRaw = q.analyze || q.analysis || q.p?.c || ''
  const analysisHtml = parseQuillDelta(analysisRaw)

  return {
    id: q.id || orderNum,
    question_id: q.qbcenter_id || q.id,
    order_num: orderNum,
    type: q.type === 1 ? 'single_choice' : String(q.type || 'single_choice'),
    stem: stemHtml,
    options: optionsList,
    answer,
    analysis: analysisHtml,
    material: materialHtml,
    source: q.source || undefined,
  }
}

/**
 * 核心富文本与图文混排解码器 (Quill Delta -> 标准干净 HTML)
 * 完美还原文字、换行符、空格以及嵌入图片 (如图形推理图、资料分析统计图)
 */
export function parseQuillDelta(raw: any): string {
  if (!raw) return ''

  let deltaObj = raw

  // 兼容嵌套对象
  if (typeof raw === 'object' && raw.c) {
    raw = raw.c
  }

  if (typeof raw === 'string') {
    const trimmed = raw.trim()
    // 若不是 JSON 结构，直接作为普通文本/HTML 返回
    if (!trimmed.includes('ops') && !trimmed.startsWith('{')) {
      return trimmed
    }
    try {
      deltaObj = JSON.parse(trimmed)
    } catch {
      return trimmed
    }
  }

  if (deltaObj && Array.isArray(deltaObj.ops)) {
    let html = ''
    for (const op of deltaObj.ops) {
      if (typeof op.insert === 'string') {
        // 将普通换行符替换为段落换行，避免被浏览器折叠
        const txt = op.insert.replace(/\n/g, '<br/>')
        html += txt
      } else if (op.insert && typeof op.insert === 'object') {
        if (op.insert.image) {
          html += `<img src="${op.insert.image}" style="max-width:100%; display:inline-block; margin: 4px 0;" />`
        }
      }
    }
    return html.trim()
  }

  return typeof raw === 'string' ? raw : String(raw)
}

export * from './api'
export * from './dom'
export * from './mistake'
