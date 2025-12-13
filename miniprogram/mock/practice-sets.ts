import { QuestionType, QuestionTypeLabel } from '@/api/types/question'

/**
 * 刷题模式枚举
 */
export enum PracticeMode {
  Practice = 'practice',  // 刷题模式 - 提交后自动跳下一题
  Exercise = 'exercise',  // 练题模式 - 提交后不自动跳转，显示解析
  Memorize = 'memorize'   // 背题模式 - 直接展示题目+正确答案+核心解析
}

/**
 * 刷题模式标签
 */
export const PracticeModeLabel: Record<PracticeMode, string> = {
  [PracticeMode.Practice]: '刷题模式',
  [PracticeMode.Exercise]: '练题模式',
  [PracticeMode.Memorize]: '背题模式'
}

/**
 * 刷题模式描述
 */
export const PracticeModeDesc: Record<PracticeMode, string> = {
  [PracticeMode.Practice]: '连续作答，快速刷题',
  [PracticeMode.Exercise]: '查看解析，巩固知识',
  [PracticeMode.Memorize]: '直接背诵，高效记忆'
}

/**
 * 刷题模式图标
 */
export const PracticeModeIcon: Record<PracticeMode, string> = {
  [PracticeMode.Practice]: '⚡',
  [PracticeMode.Exercise]: '📝',
  [PracticeMode.Memorize]: '📚'
}

/**
 * 题型套题信息
 */
export interface QuestionTypeSet {
  id: string
  type_id: QuestionType
  name: string
  icon: string
  count: number
  color: string
  bgColor: string
  description: string
}

/**
 * 题型套题列表
 */
export const questionTypeSets: QuestionTypeSet[] = [
  {
    id: 'single',
    type_id: QuestionType.Single,
    name: QuestionTypeLabel[QuestionType.Single],
    icon: '🔘',
    count: 120,
    color: '#3b82f6',
    bgColor: 'rgba(59, 130, 246, 0.1)',
    description: '四选一，基础题型'
  },
  {
    id: 'multiple',
    type_id: QuestionType.Multiple,
    name: QuestionTypeLabel[QuestionType.Multiple],
    icon: '☑️',
    count: 80,
    color: '#8b5cf6',
    bgColor: 'rgba(139, 92, 246, 0.1)',
    description: '多个正确答案'
  },
  {
    id: 'judgement',
    type_id: QuestionType.Judgement,
    name: QuestionTypeLabel[QuestionType.Judgement],
    icon: '✓',
    count: 150,
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.1)',
    description: '判断对错'
  },
  {
    id: 'fill',
    type_id: QuestionType.Fill,
    name: QuestionTypeLabel[QuestionType.Fill],
    icon: '✏️',
    count: 60,
    color: '#f59e0b',
    bgColor: 'rgba(245, 158, 11, 0.1)',
    description: '填写关键词'
  },
  {
    id: 'material',
    type_id: QuestionType.Material,
    name: QuestionTypeLabel[QuestionType.Material],
    icon: '📄',
    count: 40,
    color: '#06b6d4',
    bgColor: 'rgba(6, 182, 212, 0.1)',
    description: '阅读材料作答'
  },
  {
    id: 'qa',
    type_id: QuestionType.QA,
    name: QuestionTypeLabel[QuestionType.QA],
    icon: '💬',
    count: 30,
    color: '#ec4899',
    bgColor: 'rgba(236, 72, 153, 0.1)',
    description: '简答或论述'
  }
]

/**
 * 获取题型套题信息
 */
export function getQuestionTypeSet(typeId: QuestionType): QuestionTypeSet | undefined {
  return questionTypeSets.find(set => set.type_id === typeId)
}

export default {
  PracticeMode,
  PracticeModeLabel,
  PracticeModeDesc,
  PracticeModeIcon,
  questionTypeSets,
  getQuestionTypeSet
}
