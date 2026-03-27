import type { CreateFeedbackParam, FeedbackType } from '@fba/api-sdk'
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'
import { getEnvBaseUrl } from '@/utils'

export interface FeedbackTypeOption {
  value: FeedbackType
  label: string
  hint: string
  tone: string
}

export interface FeedbackContext {
  feedbackType?: FeedbackType | null
  sourceApp?: string | null
  sourcePlatform?: string | null
  pagePath?: string | null
  targetType?: string | null
  targetId?: string | number | null
  targetText?: string | null
}

const DEFAULT_SOURCE_APP = 'question_bank_mini'
const DEFAULT_SOURCE_PLATFORM = 'mp-weixin'

export const FEEDBACK_MAX_IMAGES = 3
export const FEEDBACK_MAX_CONTENT_LENGTH = 500

export const FEEDBACK_TYPE_OPTIONS: FeedbackTypeOption[] = [
  { value: 'content_error', label: '题目内容', hint: '题干、答案、解析有误', tone: 'rose' },
  { value: 'bug', label: '功能异常', hint: '页面报错、按钮无效、闪退', tone: 'amber' },
  { value: 'feature_request', label: '功能需求', hint: '希望增加某个能力', tone: 'sky' },
  { value: 'product_suggestion', label: '产品建议', hint: '交互、流程、体验建议', tone: 'violet' },
  { value: 'experience', label: '使用体验', hint: '吐槽、表扬、感受反馈', tone: 'emerald' },
  { value: 'other', label: '其他', hint: '暂时归不到上面分类', tone: 'slate' },
]

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function buildQueryString(query: Record<string, unknown>): string {
  const params = Object.entries(query)
    .filter(([, value]) => value !== undefined && value !== null && String(value).length > 0)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)

  return params.join('&')
}

function normalizeOptionalString(value: unknown): string | undefined {
  if (value === undefined || value === null) {
    return undefined
  }

  const text = String(value).trim()
  return text || undefined
}

export function getDefaultFeedbackType(): FeedbackType {
  return 'other'
}

export function resolveFeedbackPagePath(explicitPath?: string | null): string | undefined {
  if (isNonEmptyString(explicitPath)) {
    return explicitPath.trim()
  }

  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const route = normalizeOptionalString(currentPage?.route)
  if (!route) {
    return undefined
  }

  const rawOptions = currentPage?.options || currentPage?.$page?.options || {}
  const queryString = buildQueryString(rawOptions)
  if (!queryString) {
    return `/${route}`
  }

  return `/${route}?${queryString}`
}

export function createFeedbackPayload(
  data: {
    feedbackType?: FeedbackType | null
    content: string
    contact?: string | null
    images?: string[] | null
  },
  context?: FeedbackContext,
): CreateFeedbackParam {
  return {
    feedback_type: data.feedbackType || context?.feedbackType || getDefaultFeedbackType(),
    content: data.content.trim(),
    contact: normalizeOptionalString(data.contact),
    images: data.images?.length ? data.images : undefined,
    source_app: normalizeOptionalString(context?.sourceApp) || DEFAULT_SOURCE_APP,
    source_platform: normalizeOptionalString(context?.sourcePlatform) || DEFAULT_SOURCE_PLATFORM,
    page_path: resolveFeedbackPagePath(context?.pagePath),
    target_type: normalizeOptionalString(context?.targetType),
    target_id: normalizeOptionalString(context?.targetId),
    target_text: normalizeOptionalString(context?.targetText),
  }
}

export async function submitFeedback(payload: CreateFeedbackParam): Promise<void> {
  await fbaApi.admin.feedback.create(payload)
}

export async function uploadFeedbackImage(filePath: string): Promise<string> {
  const tokenStore = useTokenStore()
  const token = await tokenStore.tryGetValidToken()
  if (!token) {
    throw new Error('FEEDBACK_UPLOAD_LOGIN_REQUIRED')
  }

  const baseUrl = getEnvBaseUrl().replace(/\/+$/, '')
  const uploadUrl = `${baseUrl}/api/v1/oss/upload`

  return await new Promise<string>((resolve, reject) => {
    uni.uploadFile({
      url: uploadUrl,
      filePath,
      name: 'file',
      formData: {
        path: 'feedback/screenshot',
        use_signed_url: 'false',
      },
      header: {
        Authorization: `Bearer ${token}`,
      },
      success: (response) => {
        if (response.statusCode >= 400) {
          reject(new Error(`UPLOAD_STATUS_${response.statusCode}`))
          return
        }

        try {
          const payload = typeof response.data === 'string'
            ? JSON.parse(response.data || '{}')
            : (response.data as any)
          const url = payload?.data?.url
          if (!url) {
            reject(new Error(payload?.msg || 'UPLOAD_URL_MISSING'))
            return
          }
          resolve(url)
        }
        catch (error) {
          reject(error)
        }
      },
      fail: reject,
    })
  })
}
