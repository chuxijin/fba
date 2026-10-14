/**
 * 考场排版用户设置模型（极致精简，去伪存真）
 */
export interface RenderTypographySettings {
  includeAnswer: boolean       // 导出内容模式：false: 仅试卷题本; true: 包含答案解析
  answerPlacement?: 'merged' | 'separate' | 'none' // 答案排布: merged=合在一本卷末, separate=分为另外一个独立PDF, none=不含答案
  outputFormat: 'pdf' | 'docx' // 格式选择：pdf | docx
  questionLimit?: number       // 题目抽取上限 (错题专项集训专用，如 10/20/30/50/全部)
  exportScope?: 'all' | 'mistake_only' // 导出范围：all=全卷, mistake_only=仅做错题目

  // 系统底层固定保证的官方考场标准 (无需用户手动开关)
  boldNegativeQuestion?: boolean
  generateSectionPrompt?: boolean
  evenPagePadding?: boolean
}

/** 错题知识点页面专属元数据 */
export interface MistakePageMeta {
  keypointId?: string | number
  keypointName?: string
  total: number
  currentPage?: number
  pageSize?: number
  order?: string
  timeRange?: number | string
  platform?: string
}

/** 默认推荐考场配置 */
export const DEFAULT_TYPOGRAPHY_SETTINGS: RenderTypographySettings = {
  includeAnswer: true,
  answerPlacement: 'merged',
  outputFormat: 'pdf',
  exportScope: 'all',
  boldNegativeQuestion: true,
  generateSectionPrompt: true,
  evenPagePadding: true,
}

/** 单道题目的统一数据结构 */
export interface UnifiedQuestion {
  id?: string | number
  question_id?: number
  order_num?: number
  type?: string
  stem: string                       // 题干内容 (支持 HTML/纯文本)
  options?: string[] | { key: string; value: string }[] // 选项 A/B/C/D
  answer?: string                    // 正确答案
  analysis?: string                  // 解析
  material?: string                  // 材料 (如资料分析或言语长篇材料)
  source?: string                    // 来源 (如 2025国考行政职业能力测验)
  user_answer?: string               // 考生个人选择 (如 'A', 'B')
  is_wrong?: boolean                 // 是否为做错的题
}

/** 大模块/章节结构 (如常识判断、言语理解与表达) */
export interface UnifiedSection {
  name: string                       // 模块名称
  description?: string               // 模块说明 (如：本部分包括表达与理解两方面的内容...)
  questions: UnifiedQuestion[]
}

/** 整张试卷的统一数据结构 */
export interface UnifiedPaper {
  title: string                      // 试卷名称 (如: 2026年国家公务员录用考试行政职业能力测验试题)
  source_platform: 'fenbi' | 'huatu' | 'shikaobang' | 'other'
  total_questions: number
  sections: UnifiedSection[]
  metadata?: Record<string, any>
}

/** 扩展内部通信消息规范 */
export interface ExtensionMessage<T = any> {
  type: string
  payload?: T
}
