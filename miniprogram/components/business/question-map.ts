import type { DefineComponent } from 'vue'

import SingleChoiceQuestion from './questions/SingleChoiceQuestion.vue'
import MultipleChoiceQuestion from './questions/MultipleChoiceQuestion.vue'
import JudgementQuestion from './questions/JudgementQuestion.vue'
import FillBlankQuestion from './questions/FillBlankQuestion.vue'
import MaterialQuestion from './questions/MaterialQuestion.vue'
import QaQuestion from './questions/QaQuestion.vue'

export type QuestionType =
  | 'single'
  | 'multiple'
  | 'judgement'
  | 'fill'
  | 'material'
  | 'qa'

/**
 * 刷题模式
 * - practice: 刷题模式 - 提交后自动跳转下一题，不显示解析，最后反馈总分及错题题号
 * - exercise: 练题模式 - 提交后不自动跳转，显示解析
 * - memorize: 背题模式 - 直接展示题目+正确答案+核心解析
 */
export type PracticeMode = 'practice' | 'exercise' | 'memorize'

export interface OptionItem {
  value: string
  text: string
}

export interface BaseQuestion {
  id: string
  type: QuestionType
  stem: string
  typeLabel?: string
  analysis?: string
  answer?: string | string[]
}

export interface ChoiceQuestion extends BaseQuestion {
  options: OptionItem[]
}

export interface FillQuestion extends BaseQuestion {
  answers?: string[]
  placeholder?: string
}

export interface MaterialQuestion extends BaseQuestion {
  materials: string[]
  subQuestions: BaseQuestion[]
}

export interface QaQuestion extends BaseQuestion {
  reference?: string
}

export type QuestionComponentMap = {
  [K in QuestionType]: DefineComponent<any, any, any>
}

export const questionComponentMap: QuestionComponentMap = {
  single: SingleChoiceQuestion,
  multiple: MultipleChoiceQuestion,
  judgement: JudgementQuestion,
  fill: FillBlankQuestion,
  material: MaterialQuestion,
  qa: QaQuestion
}

/** 模式名称映射 */
export const ModeNameMap: Record<PracticeMode, string> = {
  practice: '刷题模式',
  exercise: '练题模式',
  memorize: '背题模式'
}

