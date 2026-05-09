import type {
  RenderBookKind,
  RenderJobCreatePayload,
  RenderJobFile,
  RenderJobResult,
} from '@fba/api-sdk'
import { api } from '@/api/sdk'
import { getAppSettings } from '@/utils/appSettings'
import { getEnvBaseUrl } from '@/utils'

export type ExportSourceType = 'placement' | 'wrong' | 'favorite' | 'note'
export type RenderBookTemplateKey = 'exam_paper' | 'practice' | 'wrong_question'
type RenderContentMode = NonNullable<RenderJobCreatePayload['content_mode']>
type RenderAnswerLayout = NonNullable<RenderJobCreatePayload['answer_layout']>
type RenderDeliveryMode = NonNullable<RenderJobCreatePayload['delivery_mode']>
type RenderLayoutMode = 'compact' | 'standard' | 'loose' | 'single' | 'pad_landscape' | 'pad_portrait'
type RenderTheme = 'blue' | 'green' | 'orange' | 'purple' | 'teal' | 'crimson' | 'indigo' | 'amber'

export interface ExportScope {
  sourceType: ExportSourceType
  templateKey?: RenderBookTemplateKey
  bookKind?: RenderBookKind
  title: string
  bankId?: number | null
  chapterId?: number | null
  knowledgePoint?: string | string[] | null
  questionIds?: number[]
  questionCount?: number | null
  yearStart?: number | null
  yearEnd?: number | null
  settings?: RenderBookExportSettings
}

export interface RenderBookExportSettings {
  contentMode?: RenderContentMode
  answerLayout?: RenderAnswerLayout | null
  deliveryMode?: RenderDeliveryMode
  includeAnswer?: boolean
  includeAnalysis?: boolean
  layoutMode?: RenderLayoutMode
  theme?: RenderTheme
  darkMode?: boolean
  showSource?: boolean
  doubleSided?: boolean
  uploadToOss?: boolean
}

interface ResolvedRenderBookExportSettings {
  contentMode: RenderContentMode
  answerLayout: RenderAnswerLayout | null
  deliveryMode: RenderDeliveryMode
  includeAnswer: boolean
  includeAnalysis: boolean
  layoutMode: RenderLayoutMode
  theme: RenderTheme
  darkMode: boolean
  showSource: boolean
  doubleSided: boolean
  uploadToOss: boolean
}

interface RenderBookRuntimeOptions {
  include_answer: boolean
  include_analysis: boolean
  layout_mode: RenderLayoutMode
  theme: RenderTheme
  dark_mode: boolean
  show_source: boolean
  double_sided: boolean
}

export type RenderBookExportPresetKey
  = | 'questions_only'
    | 'questions_with_answers_single'
    | 'questions_with_analysis_single'
    | 'questions_with_analysis_split'

export interface RenderBookExportPresetOption {
  key: RenderBookExportPresetKey
  label: string
  description: string
  settings: Partial<RenderBookExportSettings>
}

export interface RenderBookExportSubmitPayload {
  settings: RenderBookExportSettings
  questionCount?: number | null
  yearStart?: number | null
  yearEnd?: number | null
}

const API_PREFIX = import.meta.env.VITE_API_PREFIX || '/api/v1'

function normalizeBaseUrl(rawUrl?: string | null) {
  return String(rawUrl || '')
    .replace(/\/api\/v1\/?$/i, '')
    .replace(/\/+$/, '')
}

function getStoredAccessToken(): string {
  const directToken = uni.getStorageSync('access_token')
  if (directToken) {
    return directToken
  }

  const tokenStoreCache = uni.getStorageSync('token')
  if (!tokenStoreCache) {
    return ''
  }

  try {
    if (typeof tokenStoreCache === 'string') {
      const parsed = JSON.parse(tokenStoreCache)
      return parsed?.tokenInfo?.token || parsed?.tokenInfo?.accessToken || ''
    }
    return tokenStoreCache?.tokenInfo?.token || tokenStoreCache?.tokenInfo?.accessToken || ''
  }
  catch {
    return ''
  }
}

function getApiBaseUrl() {
  return normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL || getEnvBaseUrl() || 'http://127.0.0.1:8000')
}

function toAbsoluteApiUrl(path: string) {
  return `${getApiBaseUrl()}${API_PREFIX}${path.startsWith('/') ? path : `/${path}`}`
}

export function resolveTemplateKey(sourceType: ExportSourceType): RenderBookTemplateKey {
  if (sourceType === 'wrong') {
    return 'wrong_question'
  }
  if (sourceType === 'favorite' || sourceType === 'note') {
    return 'wrong_question'
  }
  return 'exam_paper'
}

function resolveBookKind(sourceType: ExportSourceType): RenderBookKind {
  if (sourceType === 'wrong' || sourceType === 'favorite' || sourceType === 'note') {
    return 'wrong'
  }
  return 'exam'
}

function resolveTheme(sourceType: ExportSourceType): RenderJobCreatePayload['options']['theme'] {
  if (sourceType === 'wrong') {
    return 'orange'
  }
  if (sourceType === 'favorite') {
    return 'green'
  }
  if (sourceType === 'note') {
    return 'blue'
  }
  return 'blue'
}

export const MINI_RENDER_BOOK_EXPORT_PRESETS: RenderBookExportPresetOption[] = [
  {
    key: 'questions_only',
    label: '仅题目（默认）',
    description: '只导出题干和选项，适合直接打印练习。',
    settings: {
      contentMode: 'questions_only',
      includeAnswer: false,
      includeAnalysis: false,
    },
  },
  {
    key: 'questions_with_answers_single',
    label: '题目+答案（合卷）',
    description: '题目在前，答案统一附在后面，便于自测。',
    settings: {
      contentMode: 'questions_with_answers',
      answerLayout: 'appendix',
      deliveryMode: 'single_pdf',
      includeAnswer: true,
      includeAnalysis: false,
    },
  },
  {
    key: 'questions_with_analysis_single',
    label: '题目+答案+解析（合卷）',
    description: '导出完整题本和解析，适合复盘学习。',
    settings: {
      contentMode: 'questions_with_answers',
      answerLayout: 'appendix',
      deliveryMode: 'single_pdf',
      includeAnswer: true,
      includeAnalysis: true,
    },
  },
  {
    key: 'questions_with_analysis_split',
    label: '题目与解析（分卷）',
    description: '题本与解析分开导出，打印更清爽。',
    settings: {
      contentMode: 'questions_with_answers',
      answerLayout: 'appendix',
      deliveryMode: 'split_pdf',
      includeAnswer: true,
      includeAnalysis: true,
    },
  },
]

export function resolveMiniRenderBookPreset(key: RenderBookExportPresetKey): Partial<RenderBookExportSettings> {
  return MINI_RENDER_BOOK_EXPORT_PRESETS.find(item => item.key === key)?.settings || {}
}

function resolveSolutionMode(settings: ResolvedRenderBookExportSettings): RenderJobCreatePayload['solution_mode'] {
  if (settings.contentMode === 'questions_only') {
    return 'none'
  }
  if (settings.answerLayout === 'inline') {
    return 'inline'
  }
  if (settings.deliveryMode === 'split_pdf') {
    return 'separate'
  }
  return 'appendix'
}

function buildDefaultSettings(scope: ExportScope): RenderBookExportSettings {
  return {
    contentMode: 'questions_only',
    answerLayout: null,
    deliveryMode: 'single_pdf',
    includeAnswer: false,
    includeAnalysis: false,
    layoutMode: 'standard',
    theme: resolveTheme(scope.sourceType),
    darkMode: false,
    showSource: scope.sourceType !== 'placement',
    doubleSided: false,
    uploadToOss: true,
  }
}

function normalizePositiveInteger(value?: number | null) {
  if (!Number.isFinite(value)) {
    return null
  }

  const normalized = Math.trunc(Number(value))
  if (normalized <= 0) {
    return null
  }

  return normalized
}

function resolveScopeFilters(scope: ExportScope) {
  let yearStart = normalizePositiveInteger(scope.yearStart)
  let yearEnd = normalizePositiveInteger(scope.yearEnd)
  if (yearStart && yearEnd && yearStart > yearEnd) {
    const nextStart = yearEnd
    yearEnd = yearStart
    yearStart = nextStart
  }

  return {
    questionCount: normalizePositiveInteger(scope.questionCount),
    yearStart,
    yearEnd,
  }
}

function normalizeSettings(raw: RenderBookExportSettings): ResolvedRenderBookExportSettings {
  const contentMode = raw.contentMode || 'questions_only'
  let answerLayout: RenderAnswerLayout | null = raw.answerLayout ?? 'appendix'
  let includeAnswer = raw.includeAnswer ?? (contentMode === 'questions_with_answers')
  let includeAnalysis = raw.includeAnalysis ?? false
  const deliveryMode = raw.deliveryMode || 'single_pdf'

  if (contentMode === 'questions_only') {
    answerLayout = null
    includeAnswer = false
    includeAnalysis = false
  } else {
    if (!answerLayout) {
      answerLayout = 'appendix'
    }
    includeAnswer = true
  }

  if (!includeAnswer) {
    includeAnalysis = false
  }

  return {
    contentMode,
    answerLayout,
    deliveryMode,
    includeAnswer,
    includeAnalysis,
    layoutMode: raw.layoutMode || 'standard',
    theme: raw.theme || 'blue',
    darkMode: raw.darkMode ?? false,
    showSource: raw.showSource ?? false,
    doubleSided: raw.doubleSided ?? false,
    uploadToOss: raw.uploadToOss ?? true,
  }
}

function chooseMiniExportPreset(defaultSettings: RenderBookExportSettings): Promise<RenderBookExportSettings> {
  return new Promise((resolve, reject) => {
    uni.showActionSheet({
      title: '选择题本导出模式',
      itemList: MINI_RENDER_BOOK_EXPORT_PRESETS.map(item => item.label),
      success: (result) => {
        const picked = MINI_RENDER_BOOK_EXPORT_PRESETS[result.tapIndex]
        resolve({
          ...defaultSettings,
          ...(picked?.settings || {}),
        })
      },
      fail: () => {
        reject(new Error('cancelled'))
      },
    })
  })
}

function buildCollectPayload(scope: ExportScope) {
  const filters = resolveScopeFilters(scope)
  const payload: Record<string, unknown> = {
    source_type: scope.sourceType,
  }

  if (scope.bankId) {
    payload.bank_id = scope.bankId
  }
  if (scope.chapterId) {
    payload.chapter_id = scope.chapterId
  }
  if (scope.knowledgePoint) {
    payload.knowledge_point = Array.isArray(scope.knowledgePoint)
      ? scope.knowledgePoint
      : [scope.knowledgePoint]
  }
  if (filters.questionCount) {
    payload.limit = filters.questionCount
  }
  if (filters.yearStart) {
    payload.year_start = filters.yearStart
  }
  if (filters.yearEnd) {
    payload.year_end = filters.yearEnd
  }

  return payload
}

function resolveDownloadFile(job: RenderJobResult): RenderJobFile | null {
  const preferredKinds: Array<RenderJobFile['file_kind']> = ['question_pdf', 'combined_pdf', 'solution_pdf']
  for (const kind of preferredKinds) {
    const match = job.files.find(file => file.file_kind === kind && file.status === 'available')
    if (match) {
      return match
    }
  }
  return null
}

function resolveErrorMessage(error: any) {
  return error?.message || error?.response?.data?.msg || error?.response?.data?.detail || '题本生成失败'
}

async function collectQuestionIds(scope: ExportScope) {
  if (scope.questionIds?.length) {
    return scope.questionIds
  }

  const { data: collected } = await api.qbankCollectQuestions({ body: buildCollectPayload(scope) as any }) as any
  const questionIds = Array.isArray((collected as any)?.question_ids) ? (collected as any).question_ids : []
  return questionIds
}

function buildRenderPayload(
  scope: ExportScope,
  questionIds: number[],
  settings: ResolvedRenderBookExportSettings,
): RenderJobCreatePayload {
  const filters = resolveScopeFilters(scope)
  const outputTargets = {
    question_pdf: true,
    solution_pdf: settings.contentMode === 'questions_with_answers' && settings.deliveryMode === 'split_pdf',
  }

  const bookKind = scope.bookKind || resolveBookKind(scope.sourceType)
  const isExam = bookKind === 'exam'

  const options: RenderBookRuntimeOptions = {
    include_answer: settings.includeAnswer,
    include_analysis: settings.includeAnalysis,
    layout_mode: settings.layoutMode,
    theme: settings.theme,
    dark_mode: settings.darkMode,
    show_source: settings.showSource,
    double_sided: settings.doubleSided,
  }

  return {
    template_key: scope.templateKey || resolveTemplateKey(scope.sourceType),
    mode: 'final',
    title: scope.title,
    book_kind: bookKind,
    content_mode: settings.contentMode,
    answer_layout: settings.answerLayout,
    delivery_mode: settings.deliveryMode,
    solution_mode: resolveSolutionMode(settings),
    filters: {
      question_ids: questionIds,
      bank_id: scope.bankId ?? null,
      chapter_id: scope.chapterId ?? null,
      knowledge_points: scope.knowledgePoint
        ? (Array.isArray(scope.knowledgePoint) ? scope.knowledgePoint : [scope.knowledgePoint])
        : null,
      question_count: filters.questionCount,
      year_start: filters.yearStart,
      year_end: filters.yearEnd,
    },
    options: options as unknown as RenderJobCreatePayload['options'],
    output_targets: outputTargets,
    metadata: {
      client: 'mini',
      source_type: scope.sourceType,
      study_domain: getAppSettings().currentDomain,
      paper_size: isExam ? 'B5' : 'A4',
      cover_style: isExam ? 'exam' : 'practice',
      bank_id: scope.bankId ?? null,
      chapter_id: scope.chapterId ?? null,
      knowledge_point: scope.knowledgePoint ?? null,
      question_count: filters.questionCount,
      year_start: filters.yearStart,
      year_end: filters.yearEnd,
      question_ids: questionIds,
      export_settings: {
        content_mode: settings.contentMode,
        answer_layout: settings.answerLayout,
        delivery_mode: settings.deliveryMode,
        include_answer: settings.includeAnswer,
        include_analysis: settings.includeAnalysis,
        layout_mode: settings.layoutMode,
        theme: settings.theme,
        dark_mode: settings.darkMode,
        show_source: settings.showSource,
      },
    },
  }
}

function downloadFile(url: string, useAuth: boolean) {
  const token = getStoredAccessToken()
  return new Promise<UniApp.DownloadSuccessData>((resolve, reject) => {
    uni.downloadFile({
      url,
      header: useAuth && token
        ? {
            Authorization: `Bearer ${token}`,
          }
        : undefined,
      success: (result) => {
        if (result.statusCode >= 200 && result.statusCode < 300) {
          resolve(result)
          return
        }
        reject(new Error(`下载失败(${result.statusCode})`))
      },
      fail: reject,
    })
  })
}

function openPdf(filePath: string) {
  return new Promise<void>((resolve, reject) => {
    uni.openDocument({
      filePath,
      fileType: 'pdf',
      showMenu: true,
      success: () => resolve(),
      fail: reject,
    })
  })
}

export async function exportMiniRenderBook(scope: ExportScope) {
  const defaultSettings = buildDefaultSettings(scope)
  let mergedSettings: RenderBookExportSettings
  if (scope.settings) {
    mergedSettings = { ...defaultSettings, ...scope.settings }
  } else {
    try {
      mergedSettings = await chooseMiniExportPreset(defaultSettings)
      
      // Prompt for double-sided printing
      const isDoubleSided = await new Promise<boolean>((resolve) => {
        uni.showModal({
          title: '排版优化选项',
          content: '是否为您优化【双面打印】排版？\n(开启后自动调整交替页码及封底空白页)',
          confirmText: '双面打印',
          cancelText: '电子版/单面',
          success: (res) => {
            resolve(res.confirm)
          },
          fail: () => {
            resolve(false)
          }
        })
      })
      mergedSettings.doubleSided = isDoubleSided
    } catch {
      return
    }
  }
  const resolvedSettings = normalizeSettings(mergedSettings)

  // 最佳实践：提交导出任务后允许用户继续操作，不要在页面里“硬控”等待生成完毕。
  // 用户可去「我的 - 我的题本」查看任务状态并下载。
  uni.showLoading({ title: '提交任务中...' })

  try {
    const questionIds = await collectQuestionIds(scope)
    if (!questionIds.length) {
      throw new Error('当前范围内暂无可导出的题目')
    }

    const { data: job } = await api.createRenderJob({
      body: buildRenderPayload(scope, questionIds, resolvedSettings),
    }) as any
    await api.dispatchRenderJob({
      path: { job_id: job.job_id },
      query: { upload_to_oss: resolvedSettings.uploadToOss },
    })

    uni.showModal({
      title: '已提交导出任务',
      content: '题本正在后台生成，你可以继续刷题。稍后到「我的 - 我的题本」查看并下载。',
      confirmText: '去查看',
      cancelText: '知道了',
      success: (res) => {
        if (res.confirm) {
          uni.navigateTo({ url: '/pages/mine/render-books/index' })
        }
      },
    })

    return job
  }
  catch (error) {
    console.error('导出题本失败:', error)
    uni.showToast({
      title: resolveErrorMessage(error),
      icon: 'none',
    })
    throw error
  }
  finally {
    uni.hideLoading()
  }
}
