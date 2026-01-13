/**
 * 练习历史相关 API
 *
 * 包含：
 * - PracticeSession（练习会话）：记录一次完整的练习
 * - PracticeRecord（答题记录）：记录每道题的答题详情
 */

import { get, post, put, del } from '../request'

// ============ 类型定义 ============

/**
 * 练习类型
 */
export type SessionType = 'chapter' | 'bank' | 'random' | 'exam' | 'wrong' | 'favorite'

/**
 * 会话状态
 */
export type SessionStatus = 'in_progress' | 'completed' | 'abandoned'

/**
 * 创建练习会话参数
 */
export interface CreateSessionParams {
  session_type: SessionType
  bank_id?: number
  chapter_id?: number
  exam_id?: number
  question_ids?: number[]
  total_count?: number  // 可选，后端自动计算
  limit?: number  // 题目数量限制（用于随机出题）
  shuffle?: boolean  // 是否随机顺序
  exam_config?: {
    time_limit?: number
    show_answer?: boolean
    allow_review?: boolean
  }
}

/**
 * 练习会话详情
 */
export interface SessionDetail {
  id: number
  user_id: number
  session_type: SessionType
  bank_id?: number
  chapter_id?: number
  question_ids?: number[]
  total_count: number
  completed_count: number
  correct_count: number
  wrong_count: number
  accuracy_rate: number
  score?: number
  total_score?: number
  total_time: number
  start_time: string
  submit_time?: string
  status: SessionStatus
  exam_config?: Record<string, any>
  created_time: string
}

/**
 * 练习会话列表项
 */
export interface SessionListItem {
  id: number
  session_type: SessionType
  bank_id?: number
  practice_name?: string
  total_count: number
  completed_count: number
  correct_count: number
  wrong_count: number
  accuracy_rate: number
  total_time: number
  status: SessionStatus
  start_time: string
  updated_time: string
}

/**
 * 答题卡项
 */
export interface AnswerCardItem {
  index: number
  question_id: number
  status: 'correct' | 'wrong' | 'unanswered'
  answer_time: number
}

/**
 * 会话答题报告
 */
export interface SessionReport {
  session_id: number
  bank_id?: number
  practice_name?: string
  session_type: SessionType
  total_count: number
  completed_count: number
  correct_count: number
  wrong_count: number
  unanswered_count: number
  accuracy_rate: number
  total_time: number
  status: SessionStatus
  answer_items: AnswerCardItem[]
  wrong_question_ids: number[]
}

/**
 * 题目解析项
 */
export interface QuestionSolution {
  question_id: number
  content: string
  type: string
  options?: Record<string, any>[]
  correct_answer: string | string[]
  analysis?: string
  user_answer?: string | string[]
  is_correct?: boolean
  answer_time?: number  // 答题用时（秒）
}

/**
 * 会话答案解析
 */
export interface SessionSolution {
  session_id: number
  questions: QuestionSolution[]
}

/**
 * 更新会话统计参数
 */
export interface UpdateSessionParams {
  completed_count?: number
  correct_count?: number
  wrong_count?: number
  total_time?: number
}

/**
 * 提交会话参数
 */
export interface SubmitSessionParams {
  total_time: number
}

/**
 * 答题记录参数
 */
export interface RecordParams {
  question_id: number
  user_answer: string | string[]
  is_correct: boolean
  answer_time: number
}

/**
 * 批量创建答题记录参数
 */
export interface BatchCreateRecordsParams {
  session_id: number
  records: RecordParams[]
}

/**
 * 答题记录详情
 */
export interface RecordDetail {
  id: number
  user_id: number
  session_id: number
  question_id: number
  user_answer: string | string[]
  is_correct: boolean
  answer_time: number
  bank_id: number
  chapter_id?: number
  created_time: string
}

/**
 * 答题记录列表项
 */
export interface RecordListItem {
  id: number
  question_id: number
  is_correct: boolean
  answer_time: number
  created_time: string
}

/**
 * 分页结果
 */
export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  size: number
  total_pages: number
}

// ============ 练习会话 API ============

/**
 * 创建练习会话
 */
export function createSession(data: CreateSessionParams): Promise<SessionDetail> {
  return post('/qbank/sessions', data)
}

/**
 * 获取练习会话详情
 */
export function getSession(sessionId: number): Promise<SessionDetail> {
  return get(`/qbank/sessions/${sessionId}`)
}

/**
 * 获取练习会话列表
 */
export function getSessionList(params?: {
  page?: number
  size?: number
  session_type?: SessionType
  status?: SessionStatus
}): Promise<PageResult<SessionListItem>> {
  return get('/qbank/sessions', params)
}

/**
 * 获取最新的进行中会话
 */
export function getLatestSession(params?: {
  bank_id?: number
  chapter_id?: number
}): Promise<SessionDetail> {
  return get('/qbank/sessions/latest', params)
}

/**
 * 更新练习会话统计
 */
export function updateSession(sessionId: number, data: UpdateSessionParams): Promise<void> {
  return put(`/qbank/sessions/${sessionId}`, data)
}

/**
 * 提交练习会话
 */
export function submitSession(sessionId: number, data: SubmitSessionParams): Promise<void> {
  return post(`/qbank/sessions/${sessionId}/submit`, data)
}

/**
 * 放弃练习会话
 */
export function abandonSession(sessionId: number): Promise<void> {
  return post(`/qbank/sessions/${sessionId}/abandon`, {})
}

/**
 * 删除练习会话
 */
export function deleteSession(sessionId: number): Promise<void> {
  return del(`/qbank/sessions/${sessionId}`)
}

// ============ 答题记录 API ============

/**
 * 创建答题记录（支持单条或批量）
 */
export function createRecords(data: BatchCreateRecordsParams): Promise<void> {
  return post('/qbank/sessions/records', data)
}

/**
 * 获取答题记录详情
 */
export function getRecord(recordId: number): Promise<RecordDetail> {
  return get(`/qbank/sessions/records/${recordId}`)
}

/**
 * 获取答题记录列表
 */
export function getRecordList(params?: {
  page?: number
  size?: number
  session_id?: number
  question_id?: number
}): Promise<PageResult<RecordListItem>> {
  return get('/qbank/sessions/records', params)
}

/**
 * 获取会话的所有答题记录
 */
export function getSessionRecords(sessionId: number): Promise<RecordDetail[]> {
  return get(`/qbank/sessions/${sessionId}/records`)
}

/**
 * 获取会话答题报告（用于结算页面）
 */
export function getSessionReport(sessionId: number): Promise<SessionReport> {
  return get(`/qbank/sessions/${sessionId}/report`)
}

/**
 * 获取会话答案解析
 */
export function getSessionSolution(sessionId: number): Promise<SessionSolution> {
  return get(`/qbank/sessions/${sessionId}/solution`)
}

// ============ 用户学习统计（练习中心用）============

/**
 * 章节学习进度项
 */
export interface ChapterProgressItem {
  chapter_id: number
  chapter_name: string
  total_count: number
  practiced_count: number  // 已练习题数（包含未判题）
  completed_count: number  // 已判题题数（is_correct 不为空）
  correct_count: number
  accuracy_rate: number  // 正确率（基于已判题题目）
}

/**
 * 题库学习进度项
 */
export interface BankProgressItem {
  bank_id: number
  practiced_count: number  // 已练习题数（包含未判题，去重）
  completed_count: number  // 已判题题数（is_correct 不为空，去重）
  total_count: number
  correct_count: number
  accuracy_rate: number  // 正确率（基于已判题题目）
  total_time: number
  in_progress_session_id: number | null
  in_progress_count: number
  chapters: ChapterProgressItem[]
}

/**
 * 用户学习汇总
 */
export interface UserStatisticsSummary {
  total_practiced: number
  total_correct: number
  total_time: number
  bank_count: number
}

/**
 * 用户学习统计
 */
export interface UserStatistics {
  banks: BankProgressItem[]
  summary: UserStatisticsSummary
}

/**
 * 获取用户学习统计
 *
 * 用于练习中心页面显示各题库进度和判断是否有未完成会话
 * 支持按分类筛选，返回章节级别的学习进度
 */
export function getUserStatistics(params?: {
  cat_id?: number
}): Promise<UserStatistics> {
  return get('/qbank/sessions/user/statistics', params, {
    needToken: true,
    silent: true, // 静默失败，未登录时显示上锁状态
  })
}

// ============ 题库学习统计（题库详情页用）============

/**
 * 章节统计项（用于题库详情页）
 */
export interface ChapterStatisticsItem {
  chapter_id: number
  chapter_name: string
  total_questions: number
  practiced_count: number
  correct_count: number
  accuracy_rate: number
}

/**
 * 题库统计（用于题库详情页）
 */
export interface BankStatistics {
  bank_id: number
  total_questions: number
  practiced_count: number
  correct_count: number
  accuracy_rate: number
  total_time: number
  chapter_statistics: ChapterStatisticsItem[]
}

/**
 * 获取单个题库的学习统计
 *
 * 从 getUserStatistics 返回的数据中提取指定题库的统计
 * 如果未找到该题库的统计，返回空数据
 *
 * :param bankId: 题库 ID
 * :return: 题库统计数据
 */
export async function getBankStatistics(bankId: number): Promise<BankStatistics> {
  const userStats = await getUserStatistics()
  const bankProgress = userStats.banks.find(b => b.bank_id === bankId)

  if (!bankProgress) {
    // 返回空统计
    return {
      bank_id: bankId,
      total_questions: 0,
      practiced_count: 0,
      correct_count: 0,
      accuracy_rate: 0,
      total_time: 0,
      chapter_statistics: []
    }
  }

  // 转换 BankProgressItem -> BankStatistics
  return {
    bank_id: bankProgress.bank_id,
    total_questions: bankProgress.total_count,
    practiced_count: bankProgress.practiced_count,
    correct_count: bankProgress.correct_count,
    accuracy_rate: bankProgress.accuracy_rate,
    total_time: bankProgress.total_time,
    chapter_statistics: bankProgress.chapters.map(ch => ({
      chapter_id: ch.chapter_id,
      chapter_name: ch.chapter_name,
      total_questions: ch.total_count,
      practiced_count: ch.practiced_count,
      correct_count: ch.correct_count,
      accuracy_rate: ch.accuracy_rate
    }))
  }
}
