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
import { createMembershipModule } from './modules/membership';
import type { MembershipModule } from './modules/membership';
import { createRenderBookModule } from './modules/render-book';
import type { RenderBookModule } from './modules/render-book';
import { createContentModule } from './modules/content';
import type { ContentModule } from './modules/content';
import { createActcodeModule } from './modules/actcode';
import type { ActcodeModule } from './modules/actcode';
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
  membership: MembershipModule;
  renderBook: RenderBookModule;
  content: ContentModule;
  actcode: ActcodeModule;
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
  const membership = createMembershipModule(client);
  const renderBook = createRenderBookModule(client);
  const content = createContentModule(client);
  const actcode = createActcodeModule(client);

  return {
    admin,
    gongkao,
    qbank,
    coulddrive,
    oss,
    membership,
    renderBook,
    content,
    actcode,
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
export type { MembershipModule } from './modules/membership';
export type { RenderBookModule } from './modules/render-book';
export type { ContentModule } from './modules/content';
export type { ActcodeModule } from './modules/actcode';
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
  MembershipBrief,
  MembershipPlanBrief,
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
} from './types';
