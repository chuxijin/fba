import type { QuestionType } from './question';

/** 练习会话类型 */
export type SessionType = 'chapter' | 'bank' | 'random' | 'exam' | 'wrong' | 'favorite';

/** 会话状态 */
export type SessionStatus = 'in_progress' | 'completed' | 'abandoned';

/** 答题卡状态 */
export type AnswerCardStatus = 'correct' | 'wrong' | 'unanswered';

/** 创建练习会话参数 */
export interface CreatePracticeSessionParam {
  session_type: SessionType;
  practice_name?: string | null;
  bank_id?: number | null;
  chapter_id?: number | null;
  placement_ids?: number[] | null;
  limit?: number | null;
  shuffle?: boolean;
  exam_config?: Record<string, unknown> | null;
}

/** 会话题目快照 */
export interface SessionQuestionItem {
  id: number;
  session_id: number;
  seq_no: number;
  question_id: number;
  placement_id: number;
  question_type: QuestionType;
  full_score: number;
}

/** 单次作答记录参数 */
export interface UpsertPracticeRecordItem {
  seq_no: number;
  question_id: number;
  placement_id: number;
  user_answer: Record<string, unknown> | unknown[] | string;
  /** 答题耗时（秒，0-7200） */
  answer_time: number;
}

/** 批量提交作答参数 */
export interface BatchUpsertPracticeRecordsParam {
  session_id: number;
  records: UpsertPracticeRecordItem[];
  judge_now?: boolean;
}

/** 作答记录详情 */
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

/** 作答记录列表项 */
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

/** 练习会话列表项 */
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

/** 练习会话详情（含题目与记录） */
export interface GetPracticeSessionDetail extends GetPracticeSessionListItem {
  session_questions: SessionQuestionItem[];
  records: GetPracticeRecordListItem[];
}

/** 练习会话查询参数 */
export interface PracticeSessionQueryParam {
  session_type?: SessionType;
  status?: SessionStatus;
  bank_id?: number;
  chapter_id?: number;
}

/** 提交练习会话参数 */
export interface SubmitPracticeSessionParam {
  total_time: number;
  judge_version?: string | null;
}

/** 提交练习会话结果 */
export interface SubmitPracticeSessionResult {
  completed_count: number;
  correct_count: number;
  wrong_count: number;
  accuracy_rate: number;
  score: number | null;
  total_score: number | null;
}

/** 练习题目列表查询参数 */
export interface PracticeQuestionParams {
  bank_id?: number;
  chapter_id?: number;
  type?: QuestionType;
  difficulty?: string;
}
