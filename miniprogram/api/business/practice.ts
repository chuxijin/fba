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
  question_ids?: number[]
  total_count: number
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
}

/**
 * 会话结算数据
 */
export interface SessionSummaryData {
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
  score?: number
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
 * 创建单条答题记录
 */
export function createRecord(data: RecordParams & {
  session_id: number
  bank_id: number
  chapter_id?: number
}): Promise<RecordDetail> {
  return post('/qbank/sessions/records', data)
}

/**
 * 批量创建答题记录
 */
export function batchCreateRecords(data: BatchCreateRecordsParams): Promise<void> {
  return post('/qbank/sessions/records/batch', data)
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
 * 获取会话结算数据（用于结算页面）
 */
export function getSessionSummary(sessionId: number): Promise<SessionSummaryData> {
  return get(`/qbank/sessions/${sessionId}/summary`)
}
