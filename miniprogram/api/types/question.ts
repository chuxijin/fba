/**
 * 后端数据类型定义（与后端保持一致）
 */

/** 题目选项 */
export interface QuestionOption {
  id: number
  question_id: number
  label: string                    // 选项标识 A, B, C, D
  content: string | null           // 选项内容
  content_html: string | null      // 选项富文本
  media_assets: Record<string, any> | null  // 媒体资源
  is_correct: boolean              // 是否正确
  sort_order: number               // 排序
}

/** 题目详情 */
export interface QuestionDetail {
  id: number
  bank_id: number                  // 题库ID
  chapter_id: number | null        // 章节ID
  type_id: number                  // 题型ID（1=选择题 2=判断题 3=填空题 4=问答题 5=材料题）
  choice_type: string | null       // 选择题类型：single/multiple/uncertain
  diff_id: number | null           // 难度ID
  stem: string                     // 题干
  answer_json: Record<string, any> | null   // 答案结构（JSON）
  answer_text: string | null       // 答案文本
  analysis: string | null          // 解析
  media_assets: Record<string, any> | null  // 媒体资源
  score: number                    // 分值
  keyword: string | null           // 关键字
  source: string | null            // 来源
  year: number | null              // 年份
  is_active: boolean               // 是否启用
  version: number                  // 版本号
  review_status: number            // 审核状态
  create_user: number              // 创建人ID
  update_user: number | null       // 更新人ID
  created_time: string             // 创建时间
  updated_time: string | null      // 更新时间
  options: QuestionOption[]        // 题目选项
}

/** 题型枚举（与后端保持一致） */
export enum QuestionType {
  Choice = 1,      // 选择题（单选/多选/不定项，通过 choice_type 区分）
  Judgement = 2,   // 判断题
  Fill = 3,        // 填空题
  QA = 4,          // 问答题
  Material = 5     // 材料题
}

/** 题型标签映射 */
export const QuestionTypeLabel: Record<number, string> = {
  [QuestionType.Choice]: '选择题',
  [QuestionType.Judgement]: '判断题',
  [QuestionType.Fill]: '填空题',
  [QuestionType.QA]: '问答题',
  [QuestionType.Material]: '材料分析题'
}

/** 题型组件映射（用于前端渲染） */
export const QuestionTypeComponent: Record<number, string> = {
  [QuestionType.Choice]: 'choice',       // 选择题（会根据 choice_type 进一步区分）
  [QuestionType.Judgement]: 'judgement',
  [QuestionType.Fill]: 'fill',
  [QuestionType.QA]: 'qa',
  [QuestionType.Material]: 'material'
}

/** 选择题类型（choice_type 字段） */
export enum ChoiceType {
  Single = 'single',        // 单选
  Multiple = 'multiple',    // 多选
  Uncertain = 'uncertain'   // 不定项选择
}
