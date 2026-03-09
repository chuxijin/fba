import { createApiClient } from './client/create-client';
import type { ApiClient, SdkOptions } from './client/types';
import { createBankModule } from './modules/bank';
import type { BankModule } from './modules/bank';
import { createMaterialModule } from './modules/material';
import type { MaterialModule } from './modules/material';
import { createPracticeModule } from './modules/practice';
import type { PracticeModule } from './modules/practice';
import { createQuestionModule } from './modules/question';
import type { QuestionModule } from './modules/question';

/** SDK 瀹炰緥锛屽寘鍚墍鏈夊彲鐢ㄦā鍧?*/
export interface FbaApiSdk {
  /** 棰樺簱妯″潡 */
  bank: BankModule;
  /** 鏉愭枡妯″潡 */
  material: MaterialModule;
  /** 棰樼洰妯″潡 */
  question: QuestionModule;
  /** 鍒烽/缁冧範妯″潡 */
  practice: PracticeModule;
  /** 搴曞眰 ApiClient锛堢敤浜庤嚜瀹氫箟璋冪敤锛?*/
  client: ApiClient;
}

/**
 * 鍒涘缓 FBA API SDK 瀹炰緥
 *
 * @example Web 绔紙Axios 閫傞厤鍣級
 * ```ts
 * import axios from 'axios';
 * import { createFbaApiSdk } from '@fba/api-sdk';
 *
 * const sdk = createFbaApiSdk({
 *   baseURL: 'http://127.0.0.1:8000',
 *   adapter: {
 *     request: (config) => axios(config).then(res => res.data),
 *   },
 *   getToken: () => localStorage.getItem('token') ?? undefined,
 * });
 *
 * const banks = await sdk.bank.getList();
 * ```
 *
 * @example 灏忕▼搴忕锛坵x.request 閫傞厤鍣級
 * ```ts
 * import { createFbaApiSdk } from '@fba/api-sdk';
 *
 * const sdk = createFbaApiSdk({
 *   baseURL: 'https://api.example.com',
 *   adapter: {
 *     request: (config) => new Promise((resolve, reject) => {
 *       wx.request({
 *         url: config.url,
 *         method: config.method,
 *         data: config.data || config.params,
 *         header: config.headers,
 *         timeout: config.timeout,
 *         success: (res) => resolve(res.data),
 *         fail: reject,
 *       });
 *     }),
 *   },
 *   getToken: () => wx.getStorageSync('token') || undefined,
 * });
 * ```
 */
export function createFbaApiSdk(options: SdkOptions): FbaApiSdk {
  const client = createApiClient(options);

  return {
    bank: createBankModule(client),
    material: createMaterialModule(client),
    question: createQuestionModule(client),
    practice: createPracticeModule(client),
    client,
  };
}

// 鈹€鈹€ 閲嶆柊瀵煎嚭 鈹€鈹€

// SDK 宸ュ巶
export { createApiClient } from './client/create-client';

// 閿欒绫?
export { ApiError, NetworkError, UnauthorizedError } from './client/errors';

// Client 绫诲瀷
export type { ApiClient, RequestAdapter, RequestConfig, SdkOptions } from './client/types';

// Module 绫诲瀷
export type { BankModule } from './modules/bank';
export type { MaterialModule } from './modules/material';
export type { PracticeModule } from './modules/practice';
export type { QuestionModule } from './modules/question';

// 鎵€鏈夋暟鎹被鍨?
export type {
  // Common
  DeleteParam,
  PageData,
  PaginationParams,
  ResponseModel,
  // Bank
  BankListParams,
  BankSchemaBase,
  BankScope,
  BankStatus,
  BankType,
  CreateBankParam,
  GetBankDetail,
  GetBankDetailWithChapters,
  GetBankQuestionsAllResult,
  GetChapterTree,
  UpdateBankParam,
  // Material
  ChapterBankBrief,
  CreateMaterialParam,
  GetMaterialDetail,
  GetMaterialListItem,
  GetMaterialWithRelationDetail,
  LinkQuestionParam,
  MaterialListParams,
  MaterialSchemaBase,
  UpdateMaterialParam,
  // Question
  AnalysisStatus,
  BatchImportParam,
  BatchImportResult,
  ContentStatus,
  CreateQuestionParam,
  Difficulty,
  GetQuestionDetail,
  GetQuestionListItem,
  GetQuestionNoteDetail,
  GetQuestionSolution,
  GetQuestionStatisticsDetail,
  GetQuestionWithAnswer,
  QuestionAnalysisItem,
  QuestionCoreBase,
  QuestionListParams,
  QuestionOptionItem,
  QuestionOptionStatsItem,
  QuestionPlacementItem,
  QuestionType,
  ReviewStatus,
  UpdateQuestionParam,
  UpsertQuestionAnalysisItem,
  UpsertQuestionOptionItem,
  UpsertQuestionPlacementItem,
  // Practice
  AnswerCardStatus,
  BatchUpsertPracticeRecordsParam,
  CreatePracticeSessionParam,
  GetPracticeRecordDetail,
  GetPracticeRecordListItem,
  GetPracticeSessionDetail,
  GetPracticeSessionListItem,
  PracticeQuestionParams,
  PracticeSessionQueryParam,
  SessionQuestionItem,
  SessionStatus,
  SessionType,
  SubmitPracticeSessionParam,
  SubmitPracticeSessionResult,
  UpsertPracticeRecordItem,
} from './types';

