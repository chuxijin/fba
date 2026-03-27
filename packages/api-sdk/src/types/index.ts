// Common
export type { DeleteParam, PageData, PaginationParams, ResponseModel } from './common';

// Bank
export type {
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
} from './bank';

// Material
export type {
  ChapterBankBrief,
  CreateMaterialParam,
  GetMaterialDetail,
  GetMaterialListItem,
  GetMaterialWithRelationDetail,
  LinkQuestionParam,
  MaterialListParams,
  MaterialSchemaBase,
  UpdateMaterialParam,
} from './material';

// Question
export type {
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
} from './question';

// Practice
export type {
  AnswerCardItem,
  AnswerCardStatus,
  BatchUpsertPracticeRecordsParam,
  ChapterDistributionItem,
  CreatePracticeSessionParam,
  GetPracticeRecordDetail,
  GetPracticeRecordListItem,
  GetPracticeRecordSessionItem,
  GetPracticeSessionDetail,
  GetPracticeSessionListItem,
  GetSessionQuestionsResponse,
  KnowledgePointValue,
  PracticeQuestionParams,
  PracticeSessionQueryParam,
  SessionChapterBrief,
  SessionMaterialItem,
  SessionQuestionContentItem,
  SessionQuestionItem,
  SessionQuestionOption,
  SessionReport,
  SessionStatus,
  SessionType,
  SubmitPracticeSessionParam,
  SubmitPracticeSessionResult,
  UpsertPracticeRecordItem,
} from './practice';

// Gongkao
export type {
  GongkaoEntity,
  GongkaoListParams,
  GkContentParams,
  GkContentResult,
  GkCiyuParams,
  GkCiyuResult,
  GkGangweiParams,
  GkGangweiResult,
  GkGuanmeiParams,
  GkGuanmeiResult,
  GkMaterialParams,
  GkMaterialResult,
  GkQuestionAnswerResult,
  GkQuestionOptionResult,
  GkQuestionParams,
  GkQuestionResult,
  GkShipingParams,
  GkShipingResult,
  GkShizhenParams,
  GkShizhenResult,
} from './gongkao';

// Admin
export type {
  AdminCaptchaResult,
  AdminCurrentUser,
  AdminEntity,
  AdminListParams,
  AdminLoginParams,
  AdminLoginToken,
  AdminRefreshTokenResult,
  AdminRoleExpiry,
  AdminSwaggerToken,
  AdminUserInfo,
  CategoryListParams,
  CategorySchemaBase,
  CreateCategoryParam,
  CreateFeedbackParam,
  DeleteCategoryParam,
  DeleteFeedbackParam,
  FeedbackListParams,
  FeedbackStatus,
  FeedbackType,
  GetCategoryDetail,
  GetCategoryTree,
  GetFeedbackDetail,
  UpdateFeedbackParam,
  UpdateCategoryParam,
} from './admin';

// Qbank extra
export type {
  QbankCheckInParam,
  QbankEntity,
  QbankRoleExpiry,
  QbankUserAccountDetail,
  QbankWxLoginParam,
  QbankWxLoginResponse,
} from './qbank';

// Coulddrive
export type {
  CoulddriveDriveType,
  CoulddriveResourceKnowledgeItem,
  CoulddriveResourceListItem,
  CoulddriveResourceListParams,
  CoulddriveResourceVectorSearchKnowledgeResultItem,
  CoulddriveResourceVectorSearchParams,
  CoulddriveResourceVectorSearchResultItem,
  CoulddriveResourceVectorizeParams,
  CoulddriveResourceVectorizeResult,
} from './coulddrive';

// Oss
export type { OssUploadParams, OssUploadResult } from './oss';
