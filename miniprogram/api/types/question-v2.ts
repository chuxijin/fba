/**
 * 题目相关类型定义（与重构后的后端保持一致）
 */

/** ==================== 基础枚举 ==================== */

/** 题型（字符串枚举，与后端保持一致） */
export type QuestionType = 'single' | 'multiple' | 'judgement' | 'fill' | 'shortAnswer'

/** 难度（字符串枚举，与后端保持一致） */
export type DifficultyType = 'easy' | 'medium' | 'hard'

/** 题型标签映射 */
export const QuestionTypeLabel: Record<QuestionType, string> = {
  single: '单选题',
  multiple: '多选题',
  judgement: '判断题',
  fill: '填空题',
  shortAnswer: '简答题',
}

/** 难度标签映射 */
export const DifficultyLabel: Record<DifficultyType, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

/** ==================== 后端数据结构 ==================== */

/** 题目选项数据（options_data 对象中的项） */
export interface QuestionOptionData {
  /** 选项代码 (A, B, C, D, ...) */
  code: string
  /** 选项内容（富文本） */
  content: string
}

/** 题目解析数据（analysis 对象） */
export interface QuestionAnalysisData {
  /** 正确答案数据 */
  answer_data: {
    /** 正确答案 */
    correct: string | string[] | { keywords?: string[] }
  }
  /** 解析内容（富文本） */
  content: string
}

/** 题目列表项（不含答案） */
export interface QuestionListItem {
  /** 题目 ID */
  id: number
  /** 题库 ID */
  bank_id: number
  /** 章节 ID */
  chapter_id: number | null
  /** 题型 */
  type: QuestionType
  /** 题干（富文本） */
  stem: string
  /** 选项数据（选择题专用，刷题时必需） */
  options_data: Record<string, QuestionOptionData> | null
  /** 难度 */
  difficulty: DifficultyType
  /** 分值 */
  score: number | string
  /** 考点 */
  knowledge_point: string | null
  /** 是否启用 */
  is_active: boolean
  /** 审核状态 */
  review_status: number
  /** 创建时间 */
  created_time: string
  /** 题库名称 */
  bank_name?: string | null
  /** 章节名称 */
  chapter_name?: string | null
}

/** 题目列表项（含答案和解析） - 用于查看历史记录 */
export interface QuestionWithAnswer extends QuestionListItem {
  /** 答案数据 */
  answer_data: {
    /** 正确答案 */
    correct: string | string[]
  } | null
  /** 解析内容 */
  analysis_content: string | null
}

/** 题目详情（管理员接口，包含答案） */
export interface QuestionDetail {
  /** 题目 ID */
  id: number
  /** 题库 ID */
  bank_id: number
  /** 章节 ID */
  chapter_id: number | null
  /** 题型 */
  type: QuestionType
  /** 题干（富文本） */
  stem: string
  /** 选项数据（选择题专用） */
  options_data: Record<string, QuestionOptionData> | null
  /** 难度 */
  difficulty: DifficultyType
  /** 分值 */
  score: number
  /** 考点 */
  knowledge_point: string | null
  /** 来源 */
  source: string | null
  /** 年份 */
  year: number | null
  /** 用途 */
  usage: string
  /** 是否启用 */
  is_active: boolean
  /** 审核状态 */
  review_status: number
  /** 创建人 ID */
  created_by: number
  /** 更新人 ID */
  updated_by: number | null
  /** 创建时间 */
  created_time: string
  /** 更新时间 */
  updated_time: string | null
  /** 解析数据（包含答案） */
  analysis: QuestionAnalysisData | null
  /** 题库信息 */
  bank?: { id: number; name: string } | null
  /** 章节信息 */
  chapter?: { id: number; name: string } | null
}

/** 题目解析详情 */
export interface QuestionAnalysisDetail {
  /** 解析 ID */
  id: number
  /** 题目 ID */
  question_id: number
  /** 答案数据 */
  answer_data: {
    correct: string | string[] | { keywords?: string[] }
  }
  /** 解析内容（富文本） */
  content: string
  /** 查看次数 */
  view_count: number
  /** 有帮助次数 */
  helpful_count: number
  /** 无帮助次数 */
  unhelpful_count: number
  /** 创建时间 */
  created_time: string
  /** 更新时间 */
  updated_time: string | null
}

/** 题目答案和解析（练题模式专用） */
export interface QuestionSolution {
  /** 正确答案 */
  correct_answer: string | string[]
  /** 解析内容（富文本） */
  analysis: string
  /** 是否正确（传入 user_answer 时返回） */
  is_correct?: boolean
  /** 全站正确率（百分比） */
  correct_rate?: number
  /** 错误选项统计 */
  wrong_option_stats?: Record<string, number>
}

/** 题目答案项（批量提交） */
export interface QuestionAnswerItem {
  /** 题目 ID */
  question_id: number
  /** 用户答案 */
  user_answer: string | string[]
  /** 答题时间（秒） */
  answer_time?: number
}

/** 批量提交答案参数 */
export interface BatchSubmitAnswerParam {
  /** 题目答案列表 */
  answers: QuestionAnswerItem[]
  /** 是否包含解析内容（默认 false） */
  include_analysis?: boolean
}

/** 题目结果项（批量提交返回） */
export interface QuestionResultItem {
  /** 题目 ID */
  question_id: number
  /** 是否正确 */
  is_correct: boolean
  /** 用户答案 */
  user_answer: string | string[]
  /** 正确答案 */
  correct_answer: Record<string, any>
  /** 得分 */
  score: number
  /** 满分 */
  full_score: number
  /** 解析内容（可选） */
  analysis_content?: string | null
}

/** 批量提交答案结果 */
export interface BatchSubmitAnswerResult {
  /** 总题目数 */
  total_questions: number
  /** 答对题目数 */
  correct_count: number
  /** 答错题目数 */
  wrong_count: number
  /** 总得分 */
  total_score: number
  /** 总满分 */
  full_score: number
  /** 正确率（百分比） */
  accuracy_rate: number
  /** 得分率（百分比） */
  score_rate: number
  /** 每道题的结果详情 */
  results: QuestionResultItem[]
}

/** ==================== 前端专用类型 ==================== */

/** 前端题目选项格式（便于渲染） */
export interface FrontendQuestionOption {
  /** 选项标识 (A, B, C, D, ...) */
  label: string
  /** 选项内容 */
  content: string
  /** 是否正确答案（仅在查看解析时使用） */
  is_correct?: boolean
}

/** 前端题目格式（适配后的数据） */
export interface FrontendQuestion {
  /** 题目 ID */
  id: number
  /** 题型 */
  type: QuestionType
  /** 题干 */
  stem: string
  /** 选项列表（选择题/判断题） */
  options?: FrontendQuestionOption[]
  /** 难度 */
  difficulty: DifficultyType
  /** 分值 */
  score: number
  /** 考点 */
  knowledge_point?: string
  /** 解析（查看解析时加载） */
  analysis?: {
    /** 正确答案 */
    correct_answer: string | string[]
    /** 解析内容 */
    content: string
    /** 关键词（简答题） */
    keywords?: string[]
  }
}

/** 题目查询参数 */
export interface QuestionQueryParams {
  /** 题库 ID */
  bank_id?: number
  /** 章节 ID */
  chapter_id?: number
  /** 题型 */
  type?: QuestionType
  /** 难度 */
  difficulty?: DifficultyType
  /** 是否启用 */
  is_active?: boolean
  /** 审核状态 */
  review_status?: number
  /** 关键字搜索 */
  keyword?: string
  /** 页码 */
  page?: number
  /** 每页数量 */
  size?: number
}
