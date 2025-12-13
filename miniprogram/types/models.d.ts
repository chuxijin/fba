/**
 * 业务模型类型定义
 * 导出所有业务相关的公共类型
 */

/**
 * 题库范围
 */
export type BankScope = 1 | 2 // 1=免费 2=付费

/**
 * 题目类型
 */
export type QuestionType = 'single' | 'multiple' | 'judge' | 'fill' | 'essay'

/**
 * 题目难度
 */
export type QuestionDifficulty = 'easy' | 'medium' | 'hard'

/**
 * 练习模式
 */
export type PracticeMode = 'practice' | 'exercise' | 'memorize' | 'exam'

/**
 * 查看模式
 */
export type ViewMode = 'all' | 'wrong' | null

/**
 * 会员类别
 */
export type MembershipCategory = 0 | 1 | 2 // 0=全部 1=题库 2=词库

/**
 * 资源类型
 */
export type ResourceType = 'category' | 'single'

/**
 * 权限原因
 */
export type AccessReason = 'free' | 'vip_all' | 'vip_category' | 'purchased' | 'need_login' | 'need_purchase'

/**
 * 题库状态
 */
export type BankStatus = 'not-started' | 'in-progress' | 'completed'
