/**
 * 题目数据适配器
 * 将后端数据格式转换为前端组件所需格式
 */

import type { QuestionDetail, QuestionOption } from '@/api/types/question'
import { QuestionType, QuestionTypeLabel, ChoiceType } from '@/api/types/question'
import type { BaseQuestion, ChoiceQuestion, FillQuestion, MaterialQuestion, QaQuestion, OptionItem } from '@/components/practice/question-map'

/**
 * 转换选项格式
 * 防御性处理：确保即使输入为 null/undefined/非数组也不会崩溃
 */
function adaptOptions(options: QuestionOption[] | undefined | null): OptionItem[] {
  // 多重检查确保安全
  if (!options) {
    console.warn('[adaptOptions] options is null or undefined')
    return []
  }

  if (!Array.isArray(options)) {
    console.warn('[adaptOptions] options is not an array:', typeof options)
    return []
  }

  if (options.length === 0) {
    console.warn('[adaptOptions] options array is empty')
    return []
  }

  try {
    return options
      .sort((a, b) => (a?.sort_order || 0) - (b?.sort_order || 0))
      .map(opt => ({
        value: opt?.label || '',
        text: opt?.content || ''
      }))
  } catch (error) {
    console.error('[adaptOptions] Error processing options:', error)
    return []
  }
}

/**
 * 根据 choice_type 确定前端组件类型
 */
function getChoiceComponentType(choiceType: string | null): 'single' | 'multiple' | 'judgement' {
  switch (choiceType) {
    case ChoiceType.Single:
    case ChoiceType.Uncertain:  // 不定项也用单选组件，但允许多选
      return 'single'
    case ChoiceType.Multiple:
      return 'multiple'
    default:
      return 'single'
  }
}

/**
 * 转换选择题（包括单选/多选/不定项）
 */
function adaptChoiceQuestion(question: QuestionDetail): ChoiceQuestion {
  const componentType = getChoiceComponentType(question.choice_type)

  return {
    id: String(question.id),
    type: componentType,
    typeLabel: question.choice_type === ChoiceType.Multiple ? '多选题' :
               question.choice_type === ChoiceType.Uncertain ? '不定项选择' : '单选题',
    stem: question.stem,
    options: adaptOptions(question.options),
    answer: question.answer_json?.correct || [],
    analysis: question.analysis || undefined
  }
}

/**
 * 转换判断题
 */
function adaptJudgementQuestion(question: QuestionDetail): ChoiceQuestion {
  return {
    id: String(question.id),
    type: 'judgement',
    typeLabel: QuestionTypeLabel[question.type_id],
    stem: question.stem,
    options: adaptOptions(question.options),
    answer: question.answer_json?.correct || [],
    analysis: question.analysis || undefined
  }
}

/**
 * 转换填空题
 */
function adaptFillQuestion(question: QuestionDetail): FillQuestion {
  const blanks = question.answer_json?.blanks || []
  const answers = blanks.length > 0 ? blanks[0].answers : []

  return {
    id: String(question.id),
    type: 'fill',
    typeLabel: QuestionTypeLabel[question.type_id],
    stem: question.stem,
    answers: answers,
    placeholder: '请输入答案',
    answer: answers,
    analysis: question.analysis || undefined
  }
}

/**
 * 转换材料题
 */
function adaptMaterialQuestion(question: QuestionDetail, allQuestions: QuestionDetail[]): MaterialQuestion {
  const materials = question.answer_json?.materials || []
  const subQuestionIds = question.answer_json?.sub_questions || []

  // 查找子题
  const subQuestions = subQuestionIds
    .map((id: number) => allQuestions.find(q => q.id === id))
    .filter((q): q is QuestionDetail => q !== undefined)
    .map(subQ => adaptQuestion(subQ, allQuestions))

  return {
    id: String(question.id),
    type: 'material',
    typeLabel: QuestionTypeLabel[question.type_id],
    stem: question.stem,
    materials: materials,
    subQuestions: subQuestions,
    analysis: question.analysis || undefined
  }
}

/**
 * 转换问答题
 */
function adaptQaQuestion(question: QuestionDetail): QaQuestion {
  return {
    id: String(question.id),
    type: 'qa',
    typeLabel: QuestionTypeLabel[question.type_id],
    stem: question.stem,
    reference: question.answer_text || undefined,
    analysis: question.analysis || undefined
  }
}

/**
 * 转换单个题目
 */
export function adaptQuestion(question: QuestionDetail, allQuestions: QuestionDetail[] = []): BaseQuestion {
  switch (question.type_id) {
    case QuestionType.Choice:
      return adaptChoiceQuestion(question)

    case QuestionType.Judgement:
      return adaptJudgementQuestion(question)

    case QuestionType.Fill:
      return adaptFillQuestion(question)

    case QuestionType.Material:
      return adaptMaterialQuestion(question, allQuestions)

    case QuestionType.QA:
      return adaptQaQuestion(question)

    default:
      throw new Error(`未知题型: ${question.type_id}`)
  }
}

/**
 * 批量转换题目列表
 */
export function adaptQuestions(questions: QuestionDetail[]): BaseQuestion[] {
  // 过滤掉材料题的子题（它们会被包含在材料题中）
  const mainQuestions = questions.filter(q => {
    // 如果 answer_json 中有 parent_id，说明是子题
    return !q.answer_json?.parent_id
  })

  return mainQuestions.map(q => adaptQuestion(q, questions))
}

/**
 * 获取题目的正确答案（用于判题）
 */
export function getCorrectAnswer(question: QuestionDetail): string[] | string | null {
  if (question.answer_json?.correct) {
    return question.answer_json.correct
  }

  if (question.answer_text) {
    return question.answer_text
  }

  // 从选项中提取正确答案
  const correctOptions = question.options
    .filter(opt => opt.is_correct)
    .map(opt => opt.label)

  return correctOptions.length > 0 ? correctOptions : null
}

/**
 * 检查用户答案是否正确
 */
export function checkAnswer(question: QuestionDetail, userAnswer: string | string[]): boolean {
  const correctAnswer = getCorrectAnswer(question)

  if (!correctAnswer) {
    return false
  }

  // 数组答案（多选题）
  if (Array.isArray(correctAnswer) && Array.isArray(userAnswer)) {
    if (correctAnswer.length !== userAnswer.length) {
      return false
    }
    const sortedCorrect = [...correctAnswer].sort()
    const sortedUser = [...userAnswer].sort()
    return sortedCorrect.every((ans, idx) => ans === sortedUser[idx])
  }

  // 字符串答案（单选、判断、填空）
  if (typeof correctAnswer === 'string' && typeof userAnswer === 'string') {
    return correctAnswer.trim() === userAnswer.trim()
  }

  return false
}
