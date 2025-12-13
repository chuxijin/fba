/**
 * 题目数据适配器
 * 将后端数据格式转换为前端组件需要的格式
 */

import type {
  QuestionDetail,
  QuestionListItem,
  FrontendQuestion,
  FrontendQuestionOption,
  QuestionType,
} from '@/api/types/question-v2'

/**
 * 将后端的 options_data 转换为前端的 options 数组
 *
 * @param optionsData 后端的选项数据对象
 * @param correctAnswer 正确答案（可选，用于标记正确选项）
 * @return 前端选项数组
 */
function convertOptionsData(
  optionsData: Record<string, { code: string; content: string }> | null,
  correctAnswer?: string | string[]
): FrontendQuestionOption[] {
  if (!optionsData) {
    return []
  }

  const correctAnswerSet = new Set(
    Array.isArray(correctAnswer) ? correctAnswer : correctAnswer ? [correctAnswer] : []
  )

  return Object.values(optionsData).map((opt) => ({
    label: opt.code,
    content: opt.content,
    is_correct: correctAnswerSet.has(opt.code),
  }))
}

/**
 * 将后端题目详情转换为前端格式
 *
 * @param backendQuestion 后端题目数据
 * @param includeAnswer 是否包含答案（默认 false）
 * @return 前端题目格式
 */
export function adaptQuestionDetail(
  backendQuestion: QuestionDetail,
  includeAnswer = false
): FrontendQuestion {
  const frontendQuestion: FrontendQuestion = {
    id: backendQuestion.id,
    type: backendQuestion.type,
    stem: backendQuestion.stem,
    difficulty: backendQuestion.difficulty,
    score: typeof backendQuestion.score === 'string' ? parseFloat(backendQuestion.score) : backendQuestion.score,
    knowledge_point: backendQuestion.knowledge_point || undefined,
  }

  // 处理选择题和判断题的选项
  if (backendQuestion.type === 'single' || backendQuestion.type === 'multiple') {
    const correctAnswer = includeAnswer && backendQuestion.analysis
      ? backendQuestion.analysis.answer_data.correct
      : undefined

    frontendQuestion.options = convertOptionsData(
      backendQuestion.options_data,
      correctAnswer as string | string[]
    )
  } else if (backendQuestion.type === 'judgement') {
    // 判断题固定选项
    const correctAnswer = includeAnswer && backendQuestion.analysis
      ? backendQuestion.analysis.answer_data.correct
      : undefined

    frontendQuestion.options = [
      {
        label: 'A',
        content: '正确',
        is_correct: correctAnswer === 'A',
      },
      {
        label: 'B',
        content: '错误',
        is_correct: correctAnswer === 'B',
      },
    ]
  }

  // 包含答案和解析
  if (includeAnswer && backendQuestion.analysis) {
    const answerData = backendQuestion.analysis.answer_data

    frontendQuestion.analysis = {
      correct_answer: answerData.correct as string | string[],
      content: backendQuestion.analysis.content,
    }

    // 简答题的关键词
    if (backendQuestion.type === 'shortAnswer' && typeof answerData.correct === 'object') {
      frontendQuestion.analysis.keywords = (answerData.correct as any).keywords
    }
  }

  return frontendQuestion
}

/**
 * 批量转换题目列表
 *
 * @param backendQuestions 后端题目列表
 * @param includeAnswer 是否包含答案
 * @return 前端题目列表
 */
export function adaptQuestionList(
  backendQuestions: QuestionDetail[],
  includeAnswer = false
): FrontendQuestion[] {
  return backendQuestions.map((q) => adaptQuestionDetail(q, includeAnswer))
}

/**
 * 将题目列表项转换为题目详情格式（用于预加载）
 *
 * @param listItem 题目列表项
 * @return 简化的题目详情格式
 */
export function adaptListItemToDetail(listItem: QuestionListItem): Partial<QuestionDetail> {
  return {
    id: listItem.id,
    bank_id: listItem.bank_id,
    chapter_id: listItem.chapter_id,
    type: listItem.type,
    stem: listItem.stem,
    difficulty: listItem.difficulty,
    score: listItem.score,
    knowledge_point: listItem.knowledge_point,
    is_active: listItem.is_active,
    review_status: listItem.review_status,
    created_time: listItem.created_time,
    options_data: null, // 需要后续加载
    analysis: null, // 需要后续加载
  } as Partial<QuestionDetail>
}

/**
 * 判断题型是否有选项
 *
 * @param type 题型
 * @return 是否有选项
 */
export function hasOptions(type: QuestionType): boolean {
  return type === 'single' || type === 'multiple' || type === 'judgement'
}

/**
 * 格式化答案为显示文本
 *
 * @param answer 答案
 * @param type 题型
 * @return 答案文本
 */
export function formatAnswerText(
  answer: string | string[] | { keywords?: string[] },
  type: QuestionType
): string {
  if (type === 'single' || type === 'judgement') {
    return answer as string
  }

  if (type === 'multiple') {
    return Array.isArray(answer) ? answer.join(', ') : String(answer)
  }

  if (type === 'fill') {
    return Array.isArray(answer)
      ? answer.map((a, i) => `${i + 1}. ${a}`).join('；')
      : String(answer)
  }

  if (type === 'shortAnswer') {
    if (typeof answer === 'object' && (answer as any).keywords) {
      return (answer as any).keywords.join('、')
    }
    return String(answer)
  }

  return String(answer)
}

/**
 * 获取题型中文标签
 *
 * @param type 题型
 * @return 中文标签
 */
export function getTypeLabel(type: QuestionType): string {
  const labels: Record<QuestionType, string> = {
    single: '单选题',
    multiple: '多选题',
    judgement: '判断题',
    fill: '填空题',
    shortAnswer: '简答题',
  }
  return labels[type] || '未知题型'
}

/**
 * 将 FrontendQuestion 转换为前端组件期望的 BaseQuestion 格式
 * 用于兼容现有的刷题组件
 *
 * @param frontendQuestion v2 适配器返回的题目
 * @return 组件期望的题目格式
 */
export function adaptToComponentFormat(frontendQuestion: FrontendQuestion): any {
  const baseQuestion: any = {
    id: String(frontendQuestion.id),
    type: frontendQuestion.type,
    stem: frontendQuestion.stem,
    typeLabel: getTypeLabel(frontendQuestion.type),
  }

  // 转换选项格式：{label, content} → {value, text}
  if (frontendQuestion.options && frontendQuestion.options.length > 0) {
    baseQuestion.options = frontendQuestion.options.map((opt) => ({
      value: opt.label,
      text: opt.content,
    }))
  }

  // 转换答案格式
  if (frontendQuestion.analysis) {
    baseQuestion.answer = frontendQuestion.analysis.correct_answer
    // 将解析对象转换为字符串
    baseQuestion.analysis = frontendQuestion.analysis.content
  }

  return baseQuestion
}

/**
 * 批量转换为组件格式
 *
 * @param frontendQuestions v2 适配器返回的题目列表
 * @return 组件期望的题目列表
 */
export function adaptListToComponentFormat(frontendQuestions: FrontendQuestion[]): any[] {
  return frontendQuestions.map(adaptToComponentFormat)
}

/** 导出所有适配函数 */
export default {
  adaptQuestionDetail,
  adaptQuestionList,
  adaptListItemToDetail,
  hasOptions,
  formatAnswerText,
  getTypeLabel,
  adaptToComponentFormat,
  adaptListToComponentFormat,
}
