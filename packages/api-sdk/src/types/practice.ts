import type { QuestionType } from './question';

/** 缁冧範浼氳瘽绫诲瀷 */
export type SessionType = 'chapter' | 'bank' | 'random' | 'exam' | 'wrong' | 'favorite';

/** 浼氳瘽鐘舵€?*/
export type SessionStatus = 'in_progress' | 'completed' | 'abandoned';

/** 绛旈鍗＄姸鎬?*/
export type AnswerCardStatus = 'correct' | 'wrong' | 'unanswered';

/** 鍒涘缓缁冧範浼氳瘽鍙傛暟 */
export interface CreatePracticeSessionParam {
  session_type: SessionType;
  practice_name?: string | null;
  bank_id?: number | null;
  chapter_id?: number | null;
  knowledge_point?: string[] | null;
  limit?: number | null;
  shuffle?: boolean;
  exam_config?: Record<string, unknown> | null;
}

/** 浼氳瘽棰樼洰蹇収 */
export interface SessionQuestionItem {
  id: number;
  session_id: number;
  seq_no: number;
  question_id: number;
  placement_id: number;
  question_type: QuestionType;
  full_score: number;
}

/** 鍗曟浣滅瓟璁板綍鍙傛暟 */
export interface UpsertPracticeRecordItem {
  seq_no: number;
  question_id: number;
  placement_id: number;
  user_answer: Record<string, unknown> | unknown[] | string;
  /** 绛旈鑰楁椂锛堢锛?-7200锛?*/
  answer_time: number;
}

/** 鎵归噺鎻愪氦浣滅瓟鍙傛暟 */
export interface BatchUpsertPracticeRecordsParam {
  session_id: number;
  records: UpsertPracticeRecordItem[];
  judge_now?: boolean;
}

/** 浣滅瓟璁板綍璇︽儏 */
export interface GetPracticeRecordDetail {
  id: number;
  session_id: number;
  user_id: number;
  seq_no: number;
  question_id: number;
  placement_id: number;
  user_answer: Record<string, unknown> | unknown[] | string;
  is_correct: boolean | null;
  score: number | null;
  full_score: number;
  answer_time: number;
  judged_at: string | null;
  judge_version: string | null;
  created_time: string;
  updated_time: string | null;
}

/** 浣滅瓟璁板綍鍒楄〃椤?*/
export interface GetPracticeRecordListItem {
  id: number;
  session_id: number;
  seq_no: number;
  question_id: number;
  placement_id: number;
  user_answer: Record<string, unknown> | unknown[] | string;
  is_correct: boolean | null;
  score: number | null;
  full_score: number;
  answer_time: number;
  judged_at: string | null;
}

/** 缁冧範浼氳瘽鍒楄〃椤?*/
export interface GetPracticeSessionListItem {
  id: number;
  user_id: number;
  session_type: SessionType;
  status: SessionStatus;
  bank_id: number | null;
  chapter_id: number | null;
  practice_name: string | null;
  total_count: number;
  completed_count: number;
  correct_count: number;
  wrong_count: number;
  accuracy_rate: number;
  score: number | null;
  total_score: number | null;
  total_time: number;
  start_time: string;
  submit_time: string | null;
  updated_time: string | null;
}

/** 缁冧範浼氳瘽璇︽儏锛堝惈棰樼洰涓庤褰曪級 */
export interface GetPracticeSessionDetail extends GetPracticeSessionListItem {
  session_questions: SessionQuestionItem[];
  records: GetPracticeRecordListItem[];
}

/** 缁冧範浼氳瘽鏌ヨ鍙傛暟 */
export interface PracticeSessionQueryParam {
  session_type?: SessionType;
  status?: SessionStatus;
  bank_id?: number;
  chapter_id?: number;
}

/** 鎻愪氦缁冧範浼氳瘽鍙傛暟 */
export interface SubmitPracticeSessionParam {
  total_time: number;
  judge_version?: string | null;
}

/** 鎻愪氦缁冧範浼氳瘽缁撴灉 */
export interface SubmitPracticeSessionResult {
  completed_count: number;
  correct_count: number;
  wrong_count: number;
  accuracy_rate: number;
  score: number | null;
  total_score: number | null;
}

/** 绛旈鍗￠」 */
export interface AnswerCardItem {
  seq_no: number;
  question_id: number;
  placement_id: number;
  status: AnswerCardStatus;
  answer_time: number;
}

/** 浼氳瘽鎶ュ憡 */
export interface SessionReport {
  session_id: number;
  session_type: SessionType;
  status: SessionStatus;
  bank_id: number | null;
  chapter_id: number | null;
  total_count: number;
  completed_count: number;
  correct_count: number;
  wrong_count: number;
  unanswered_count: number;
  accuracy_rate: number;
  total_time: number;
  answer_items: AnswerCardItem[];
  wrong_question_ids: number[];
}

/** 缁冧範棰樼洰鍒楄〃鏌ヨ鍙傛暟 */
export interface PracticeQuestionParams {
  bank_id?: number;
  chapter_id?: number;
  type?: QuestionType;
  difficulty?: string;
}




