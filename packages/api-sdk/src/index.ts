import { createApiClient } from './client/create-client';
import type { ApiClient, SdkOptions } from './client/types';
import { createAdminModule } from './modules/admin';
import type { AdminModule } from './modules/admin';
import { createGongkaoModule } from './modules/gongkao';
import type { GongkaoModule } from './modules/gongkao';
import { createQbankModule } from './modules/qbank';
import type { QbankModule } from './modules/qbank';
import { createCoulddriveModule } from './modules/coulddrive';
import type { CoulddriveModule } from './modules/coulddrive';
import { createOssModule } from './modules/oss';
import type { OssModule } from './modules/oss';
import { createRenderBookModule } from './modules/render-book';
import type { RenderBookModule } from './modules/render-book';
import { createContentModule } from './modules/content';
import type { ContentModule } from './modules/content';
import { createActcodeModule } from './modules/actcode';
import type { ActcodeModule } from './modules/actcode';
import { createCmsModule } from './modules/cms';
import type { CmsModule } from './modules/cms';
import { createQuestModule } from './modules/quest';
import type { QuestModule } from './modules/quest';
import type { BankModule } from './modules/bank';
import type { MaterialModule } from './modules/material';
import type { PracticeModule } from './modules/practice';
import type { QuestionModule } from './modules/question';

export interface FbaApiSdk {
  admin: AdminModule;
  gongkao: GongkaoModule;
  qbank: QbankModule;
  coulddrive: CoulddriveModule;
  oss: OssModule;
  renderBook: RenderBookModule;
  content: ContentModule;
  actcode: ActcodeModule;
  cms: CmsModule;
  quest: QuestModule;
  bank: BankModule;
  material: MaterialModule;
  question: QuestionModule;
  practice: PracticeModule;
  client: ApiClient;
}

export function createFbaApiSdk(options: SdkOptions): FbaApiSdk {
  const client = createApiClient(options);
  const admin = createAdminModule(client);
  const gongkao = createGongkaoModule(client);
  const qbank = createQbankModule(client);
  const coulddrive = createCoulddriveModule(client);
  const oss = createOssModule(client);
  const renderBook = createRenderBookModule(client);
  const content = createContentModule(client);
  const actcode = createActcodeModule(client);
  const cms = createCmsModule(client);
  const quest = createQuestModule(client);

  return {
    admin,
    gongkao,
    qbank,
    coulddrive,
    oss,
    renderBook,
    content,
    actcode,
    cms,
    quest,
    bank: qbank.bank,
    material: qbank.material,
    question: qbank.question,
    practice: qbank.practice,
    client,
  };
}

export { createApiClient } from './client/create-client';
export { ApiError, NetworkError, UnauthorizedError } from './client/errors';
export type { ApiClient, FormDataLike, RequestAdapter, RequestConfig, SdkOptions } from './client/types';
export type { AdminModule } from './modules/admin';
export type { GongkaoModule } from './modules/gongkao';
export type { QbankModule } from './modules/qbank';
export type { CoulddriveModule } from './modules/coulddrive';
export type { OssModule } from './modules/oss';
export type { RenderBookModule } from './modules/render-book';
export type { ContentModule } from './modules/content';
export type { ActcodeModule } from './modules/actcode';
export type { CmsAdminModule, CmsModule } from './modules/cms';
export type { QuestAdminModule, QuestModule } from './modules/quest';
export type { BankModule } from './modules/bank';
export type { MaterialModule } from './modules/material';
export type { PracticeModule } from './modules/practice';
export type { QuestionModule } from './modules/question';
export type {
  DeleteParam,
  PageData,
  PaginationParams,
  ResponseModel,
  ContentResult,
  ContentParams,
  ContentListDetail,
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
  ChapterBankBrief,
  CreateMaterialParam,
  GetMaterialDetail,
  GetMaterialListItem,
  GetMaterialWithRelationDetail,
  LinkQuestionParam,
  MaterialListParams,
  MaterialSchemaBase,
  UpdateMaterialParam,
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
  AnswerCardStatus,
  BatchUpsertPracticeRecordsParam,
  BatchUpsertPracticeRecordsResult,
  CreatePracticeSessionParam,
  GetPracticeRecordDetail,
  GetPracticeRecordListItem,
  GetPracticeSessionDetail,
  GetPracticeSessionListItem,
  PracticeJudgeResultItem,
  PracticeQuestionParams,
  PracticeSessionQueryParam,
  SessionQuestionItem,
  SessionStatus,
  SessionType,
  SubmitPracticeSessionParam,
  SubmitPracticeSessionResult,
  UpsertPracticeRecordItem,
  GongkaoEntity,
  GongkaoListParams,
  GkContentParams,
  GkContentResult,
  GkCiyuParams,
  GkCiyuResult,
  GkGangweiParams,
  GkGangweiResult,
  GkMaterialParams,
  GkMaterialResult,
  GkQuestionAnswerResult,
  GkQuestionOptionResult,
  GkQuestionParams,
  GkQuestionResult,
  GkShizhenParams,
  GkShizhenResult,
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
  UpdateCategoryParam,
  UpdateFeedbackParam,
  QbankCheckInParam,
  QbankEntity,
  QbankKnowledgePointChild,
  QbankKnowledgePointDetail,
  QbankKnowledgePointProgress,
  QbankKnowledgePointProgressItem,
  QbankRoleExpiry,
  QbankStatisticsParams,
  QbankUserAccountDetail,
  QbankWxLoginParam,
  QbankWxLoginResponse,
  CoulddriveDriveType,
  CoulddriveResourceListItem,
  CoulddriveResourceListParams,
  CoulddriveResourceKnowledgeItem,
  CoulddriveResourceVectorSearchKnowledgeResultItem,
  CoulddriveResourceVectorSearchParams,
  CoulddriveResourceVectorSearchResultItem,
  CoulddriveResourceVectorizeParams,
  CoulddriveResourceVectorizeResult,
  OssUploadParams,
  OssUploadResult,
  RenderAnswerLayout,
  RenderBookKind,
  RenderBookMode,
  RenderBookStatus,
  RenderContentMode,
  RenderDeliveryMode,
  RenderFileKind,
  RenderFileStatus,
  RenderJobCreatePayload,
  RenderJobFile,
  RenderJobListParams,
  RenderJobPageData,
  RenderJobResult,
  RenderOptions,
  RenderOutputTargets,
  RenderStorageType,
  RenderTemplatePreviewRequest,
  RenderTemplatePreviewResult,
  RenderTemplateSummary,
  RenderVariant,
  SolutionMode,
  ActcodeOrderActivateResult,
  ActcodeOrderLoginResult,
  ActcodeOrderPayload,
  ActcodeOrderVerifyResult,
  CmsJumpType,
  CmsSlotAction,
  CmsSlotDeletedResult,
  CmsSlotStatus,
  CmsSlotType,
  CmsSlotUpdatedResult,
  CreateSlotParam,
  GetActiveSlot,
  GetSlotDetail,
  ReportSlotActionParam,
  SlotListParams,
  SlotStatsResult,
  UpdateSlotParam,
  AdminClaimListParams,
  CreateQuestParam,
  GetClaimDetail,
  GetQuestDetail,
  GetQuestWithUserDetail,
  MyClaimListParams,
  QuestAbandonResult,
  QuestClaimStatus,
  QuestDeletedResult,
  QuestListParams,
  QuestRetryGrantResult,
  QuestReviewDecision,
  QuestRewardStatus,
  QuestRewardType,
  QuestStatus,
  QuestUpdatedResult,
  ReviewClaimParam,
  ReviewClaimResult,
  RevokeClaimParam,
  RevokeClaimResult,
  SubmitClaimParam,
  UpdateQuestParam,
} from './types';

// === Generated SDK runtime (hey-api/openapi-ts) ===
// 新业务推荐用法: setupSdk + 直接 import 生成方法
//   import { setupSdk } from '@fba/api-sdk';
//   import { getQuestList } from '@fba/api-sdk/generated';
export { setupSdk, getSdkInstance, createClientConfig } from './runtime/axios';
export type { SetupSdkOptions, ApiResponseError } from './runtime/axios';
