import { UnifiedPaper, UnifiedSection, UnifiedQuestion, RenderTypographySettings } from '../types'
import { applyNegativeKeywordsBold } from '../common'

/**
 * 华图在线 (huatu.com / v.huatu.com / ns.huatu.com) 真实试卷与题库数据精准归一化适配器
 * 支持真题、模考大赛、专项练习以及错题做题页面
 */
export function adaptHuatuPaper(raw: any, settings: RenderTypographySettings): UnifiedPaper {
  // 1. 提取试卷名称
  let paperTitle =
    raw.name ||
    raw.title ||
    raw.practice?.name ||
    raw.paper?.name ||
    raw.examName ||
    '华图全真模拟考卷'

  // 清洗试卷标题末尾可能存在的冗余时间戳
  paperTitle = paperTitle.replace(/-\d{12,}$/, '').trim()

  // 2. 提取题目列表与复合题材料
  let singleQuestions: any[] = []
  let compositeQuestions: any[] = []

  if (Array.isArray(raw.singleQuestions)) {
    singleQuestions = raw.singleQuestions
  } else if (raw.data && Array.isArray(raw.data.singleQuestions)) {
    singleQuestions = raw.data.singleQuestions
  } else if (Array.isArray(raw.questions)) {
    singleQuestions = raw.questions
  } else if (raw.data && Array.isArray(raw.data.questions)) {
    singleQuestions = raw.data.questions
  }

  if (Array.isArray(raw.compositeQuestions)) {
    compositeQuestions = raw.compositeQuestions
  } else if (raw.data && Array.isArray(raw.data.compositeQuestions)) {
    compositeQuestions = raw.data.compositeQuestions
  }

  // 3. 建立复合材料快速索引 (compositeId -> materialHtml)
  const compositeMap = new Map<number | string, string>()
  for (const comp of compositeQuestions) {
    if (!comp) continue
    const compId = comp.id || comp.questionId
    const matHtml = comp.material || comp.content || comp.stem || ''
    if (compId) {
      compositeMap.set(Number(compId), matHtml)
      compositeMap.set(String(compId), matHtml)
    }
  }

  // 4. 提取试卷大模块信息 (paper.modules)
  const modules: any[] =
    raw.modules ||
    raw.paper?.modules ||
    raw.practice?.paper?.modules ||
    raw.practice?.modules ||
    []

  // 5. 逐题精准解析并关联复合材料
  const allParsedQuestions: UnifiedQuestion[] = []
  let globalOrder = 1

  for (const q of singleQuestions) {
    if (!q) continue

    // 查找关联的大材料 (如资料分析长篇图表或言语长篇材料)
    let materialHtml: string | undefined = undefined
    if (q.parent && compositeMap.has(q.parent)) {
      materialHtml = compositeMap.get(q.parent)
    } else if (q.material) {
      materialHtml = q.material
    }

    allParsedQuestions.push(parseHuatuQuestionDetail(q, globalOrder++, materialHtml, settings))
  }

  // 6. 根据 modules 结构切分大章节 (国考 1:1 六大模块划分)
  const sections: UnifiedSection[] = []

  if (Array.isArray(modules) && modules.length > 0) {
    let qIndex = 0
    for (const mod of modules) {
      const modName = mod.name || mod.title || '专项模块'
      const qCount = Number(mod.qcount || mod.count || 0)
      const secQuestions: UnifiedQuestion[] = []

      if (qCount > 0) {
        const slice = allParsedQuestions.slice(qIndex, qIndex + qCount)
        secQuestions.push(...slice)
        qIndex += qCount
      }

      if (secQuestions.length > 0) {
        sections.push({
          name: modName,
          questions: secQuestions,
        })
      }
    }

    // 若模块切分后仍有剩余题目未归入，追加到最后一个模块或兜底模块
    if (qIndex < allParsedQuestions.length) {
      const rest = allParsedQuestions.slice(qIndex)
      if (sections.length > 0) {
        sections[sections.length - 1].questions.push(...rest)
      } else {
        sections.push({
          name: '行政职业能力测验',
          questions: rest,
        })
      }
    }
  } else {
    // 无模块信息时整体归整为一个标准模块
    sections.push({
      name: '行政职业能力测验',
      questions: allParsedQuestions,
    })
  }

  const totalQuestions = sections.reduce((sum, sec) => sum + sec.questions.length, 0)

  return {
    title: paperTitle,
    source_platform: 'huatu',
    total_questions: totalQuestions,
    sections,
    metadata: {
      practice_id: raw.id || raw.practiceId || raw.practice?.id,
      paper_id: raw.paper?.id,
      created_at: new Date().toISOString(),
      hasAnswers: allParsedQuestions.some((q) => Boolean(q.answer && q.answer.trim())),
    },
  }
}

/**
 * 精准解析单道华图题目
 */
export function parseHuatuQuestionDetail(
  q: any,
  orderNum: number,
  materialHtml: string | undefined,
  settings: RenderTypographySettings
): UnifiedQuestion {
  // 1. 题干解析与反向设问陷阱词加粗
  let stem = q.stem || q.content || ''
  if (settings.boldNegativeQuestion) {
    stem = applyNegativeKeywordsBold(stem)
  }

  // 2. 提取并清洗选项 (华图存储在 choices 数组中)
  let optionsList: string[] = []
  const rawChoices = q.choices || q.options
  if (Array.isArray(rawChoices)) {
    optionsList = rawChoices.map((choice: any) => {
      if (typeof choice === 'string') return choice
      return choice?.content || choice?.text || String(choice || '')
    })
  }

  // 3. 映射参考答案 (华图答案为数字 1~4，分别对应 A~D)
  let answer = ''
  if (typeof q.answer === 'number') {
    const letterMap = ['A', 'B', 'C', 'D', 'E']
    answer = letterMap[q.answer - 1] || String(q.answer)
  } else if (typeof q.answer === 'string') {
    const num = parseInt(q.answer, 10)
    if (!isNaN(num) && num >= 1 && num <= 5) {
      const letterMap = ['A', 'B', 'C', 'D', 'E']
      answer = letterMap[num - 1]
    } else {
      answer = q.answer.trim().toUpperCase()
    }
  }

  // 4. 逐题深度解析
  const analysis = q.analysis || q.explanation || q.solution || ''

  // 5. 题目出处来源
  const source = q.from || q.source || undefined

  return {
    id: q.id || orderNum,
    question_id: q.id,
    order_num: orderNum,
    type: q.type === 99 || q.type === 1 ? 'single_choice' : String(q.type || 'single_choice'),
    stem,
    options: optionsList,
    answer,
    analysis,
    material: materialHtml,
    source,
  }
}

export * from './api'
export * from './dom'
export * from './mistake'
