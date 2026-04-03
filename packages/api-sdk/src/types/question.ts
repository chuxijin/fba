/** 题目类型 */
export type QuestionType = 'single' | 'multiple' | 'judgement' | 'fill' | 'shortAnswer';

/** 难度 */
export type Difficulty = 'easy' | 'medium' | 'hard';

/** 内容状态：0=草稿, 10=已完�? 20=待修�?*/
export type ContentStatus = 0 | 10 | 20;

/** 审核状态：0=待审�? 10=已通过, 20=已驳�?*/
export type ReviewStatus = 0 | 10 | 20;

/** 解析状态：0=未编�? 10=已编�? 20=待修�?*/
export type AnalysisStatus = 0 | 10 | 20;

/** 题目挂载信息 */
export interface QuestionPlacementItem {
  id: number;
  question_id: number;
  bank_id: number;
  chapter_id: number | null;
  sort_order: number;
  is_active: boolean;
  score: number | null;
  review_status: ReviewStatus;
  scene_mask: number | null;
  bank_name: string | null;
  chapter_name: string | null;
}

/** 选项 */
export interface QuestionOptionItem {
  id: number;
  question_id: number;
  option_code: string;
  content_id: number;
  content: string;
  sort_order: number;
  is_active: boolean;
}

/** 解析 */
export interface QuestionAnalysisItem {
  id: number;
  question_id: number;
  type: string;
  version_no: number;
  is_default: boolean;
  answer_data: Record<string, unknown>;
  content: string;
  status: AnalysisStatus;
  view_count: number;
  helpful_count: number;
  unhelpful_count: number;
  created_time: string;
  updated_time: string | null;
}

/** 题目统计 */
export interface GetQuestionStatisticsDetail {
  question_id: number;
  attempt_count: number;
  correct_count: number;
  correct_rate: number;
  avg_answer_time: number | null;
  option_select_stats: Record<string, unknown> | null;
  collect_count: number;
  note_count: number;
  report_count: number;
}

/** 题目列表�?*/
export interface GetQuestionListItem {
  id: number;
  type: QuestionType;
  stem: string;
  difficulty: Difficulty;
  default_score: number;
  knowledge_point: string[] | null;
  content_status: ContentStatus;
  created_time: string;
  updated_time: string | null;
  placement: QuestionPlacementItem | null;
  option_count: number;
  analysis_count: number;
}

/** 题目详情（不含答案） */
export interface GetQuestionDetail {
  id: number;
  type: QuestionType;
  stem: string;
  difficulty: Difficulty;
  default_score: number;
  knowledge_point: string[] | null;
  content_status: ContentStatus;
  created_time: string;
  updated_time: string | null;
  options: QuestionOptionItem[];
  placements: QuestionPlacementItem[];
  analyses: QuestionAnalysisItem[];
  material_ids: number[];
  statistics: GetQuestionStatisticsDetail | null;
}

/** 题目含答案（导出格式�?*/
export interface GetQuestionWithAnswer {
  id: number;
  type: QuestionType;
  stem: string;
  difficulty: Difficulty;
  default_score: number;
  knowledge_point: string[] | null;
  content_status: ContentStatus;
  created_time: string;
  updated_time: string | null;
  options: QuestionOptionItem[];
  placement: QuestionPlacementItem | null;
  answer_data: Record<string, unknown> | null;
  analysis_content: string | null;
  analyses: QuestionAnalysisItem[];
  material_ids: number[];
}

/** 题目答案与解析（练题模式�?*/
export interface GetQuestionSolution {
  correct_answer: string | string[];
  analysis: string;
  is_correct: boolean | null;
  correct_rate: number;
  option_select_stats: Record<string, unknown> | null;
}

/** 选项统计�?*/
export interface QuestionOptionStatsItem {
  option_code: string;
  count: number;
  rate: number;
}

/** 题目笔记详情 */
export interface GetQuestionNoteDetail {
  id: number;
  question_id: number;
  content: string;
  created_time: string;
  updated_time: string | null;
}

// ── 写入参数 ──

/** 创建/更新选项参数 */
export interface UpsertQuestionOptionItem {
  id?: number;
  option_code: string;
  content: string;
  sort_order?: number;
  is_active?: boolean;
}

/** 创建/更新挂载参数 */
export interface UpsertQuestionPlacementItem {
  id?: number;
  bank_id: number;
  chapter_id?: number | null;
  sort_order?: number;
  is_active?: boolean;
  score?: number | null;
  review_status?: ReviewStatus;
  scene_mask?: number | null;
}

/** 创建/更新解析参数 */
export interface UpsertQuestionAnalysisItem {
  id?: number;
  type?: string;
  version_no?: number;
  is_default?: boolean;
  answer_data: Record<string, unknown>;
  content: string;
  status?: AnalysisStatus;
}

/** 题目核心字段 */
export interface QuestionCoreBase {
  type: QuestionType;
  stem: string;
  difficulty?: Difficulty;
  default_score?: number;
  knowledge_point?: string[] | null;
  content_status?: ContentStatus;
}

/** 创建题目参数 */
export interface CreateQuestionParam {
  core: QuestionCoreBase;
  options?: UpsertQuestionOptionItem[];
  placements: UpsertQuestionPlacementItem[];
  analyses: UpsertQuestionAnalysisItem[];
  material_ids?: number[] | null;
}

/** 更新题目参数 */
export interface UpdateQuestionParam {
  core?: QuestionCoreBase;
  options?: UpsertQuestionOptionItem[];
  placements?: UpsertQuestionPlacementItem[];
  analyses?: UpsertQuestionAnalysisItem[];
  material_ids?: number[] | null;
}

/** 题目列表查询参数 */
export interface QuestionListParams {
  ids?: string;
  bank_id?: number;
  chapter_id?: number;
  type?: QuestionType;
  difficulty?: Difficulty;
  content_status?: ContentStatus;
  is_active?: boolean;
  review_status?: ReviewStatus;
  keyword?: string;
  page?: number;
  size?: number;
  include_answer?: boolean;
}

/** 批量导入参数 */
export interface BatchImportParam {
  bank_id: number;
  chapter_id?: number;
  items: Record<string, unknown>[];
}

/** 批量导入结果 */
export interface BatchImportResult {
  total: number;
  success: number;
  failed: number;
  errors: Record<string, unknown>[];
}

