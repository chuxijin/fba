import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'
import { getEnvBaseUrl } from '@/utils'

export interface PracticeAIEvaluationResultPayload {
  reference_answer?: string | null
  grading_summary?: string | null
  strengths?: string[]
  missing_points?: string[]
  improvement_suggestions?: string[]
  encouragement?: string | null
  knowledge_points?: string[]
  needs_manual_review?: boolean
  overview?: string | null
  high_frequency_issues?: string[]
  weak_knowledge_points?: Array<{ name?: string | null, reason?: string | null }>
  next_actions?: string[]
}

export interface PracticeAIEvaluation {
  id: number
  user_id: number
  session_id?: number | null
  practice_record_id?: number | null
  question_id?: number | null
  target_type: 'question_eval' | 'session_summary'
  trigger_source: 'auto' | 'manual'
  status: 'pending' | 'succeeded' | 'failed'
  provider_id?: number | null
  model_name?: string | null
  prompt_version?: string | null
  score?: number | null
  max_score?: number | null
  confidence?: number | null
  summary_text?: string | null
  request_payload?: Record<string, any> | null
  result_payload?: PracticeAIEvaluationResultPayload | null
  error_message?: string | null
  started_at?: string | null
  finished_at?: string | null
  is_latest: boolean
  created_time: string
  updated_time?: string | null
}

interface SubjectiveAnswerOCRResult {
  text: string
}

export function isSubjectiveQuestionType(type?: string | null) {
  return type === 'shortAnswer'
}

export function normalizeStringList(value: unknown) {
  if (!Array.isArray(value))
    return []
  return value.map(item => String(item || '').trim()).filter(Boolean)
}

export function formatEvaluationScore(score?: number | null, maxScore?: number | null) {
  if (score == null && maxScore == null)
    return '--'

  const left = score == null ? '--' : trimTrailingZero(score)
  const right = maxScore == null ? '--' : trimTrailingZero(maxScore)
  return `${left}/${right}`
}

function trimTrailingZero(value: number) {
  const fixed = Number(value)
  if (Number.isInteger(fixed))
    return String(fixed)
  return fixed.toFixed(2).replace(/\.?0+$/, '')
}

export async function getPracticeRecordAIEvaluation(recordId: number) {
  return await fbaApi.qbank.request.get<PracticeAIEvaluation>(`/ai-evaluations/records/${recordId}`)
}

export async function regeneratePracticeRecordAIEvaluation(recordId: number) {
  return await fbaApi.qbank.request.post<PracticeAIEvaluation>(`/ai-evaluations/records/${recordId}/judge`, {
    force_regenerate: true,
  })
}

export async function judgeSessionSubjectiveRecords(sessionId: number, forceRegenerate = false) {
  return await fbaApi.qbank.request.post<PracticeAIEvaluation[]>(
    `/ai-evaluations/sessions/${sessionId}/judge-subjective`,
    { force_regenerate: forceRegenerate },
  )
}

export async function getPracticeSessionAISummary(sessionId: number) {
  return await fbaApi.qbank.request.get<PracticeAIEvaluation>(`/ai-evaluations/sessions/${sessionId}/summary`)
}

export async function generatePracticeSessionAISummary(sessionId: number, forceRegenerate = false) {
  return await fbaApi.qbank.request.post<PracticeAIEvaluation>(
    `/ai-evaluations/sessions/${sessionId}/summary`,
    { force_regenerate: forceRegenerate },
  )
}

export async function recognizeSubjectiveAnswerImage(filePath: string) {
  const tokenStore = useTokenStore()
  const token = await tokenStore.tryGetValidToken()
  if (!token) {
    throw new Error('SUBJECTIVE_OCR_LOGIN_REQUIRED')
  }

  const baseUrl = getEnvBaseUrl().replace(/\/+$/, '')
  const uploadUrl = `${baseUrl}/api/v1/qbank/ai-evaluations/ocr`

  return await new Promise<SubjectiveAnswerOCRResult>((resolve, reject) => {
    uni.uploadFile({
      url: uploadUrl,
      filePath,
      name: 'files',
      header: {
        Authorization: `Bearer ${token}`,
      },
      success: (response) => {
        if (response.statusCode >= 400) {
          try {
            const payload = typeof response.data === 'string'
              ? JSON.parse(response.data || '{}')
              : (response.data as any)
            reject(new Error(payload?.msg || `SUBJECTIVE_OCR_STATUS_${response.statusCode}`))
          }
          catch {
            reject(new Error(`SUBJECTIVE_OCR_STATUS_${response.statusCode}`))
          }
          return
        }

        try {
          const payload = typeof response.data === 'string'
            ? JSON.parse(response.data || '{}')
            : (response.data as any)
          const text = String(payload?.data?.text || '').trim()
          if (!text) {
            reject(new Error(payload?.msg || 'SUBJECTIVE_OCR_EMPTY'))
            return
          }
          resolve({ text })
        }
        catch (error) {
          reject(error)
        }
      },
      fail: reject,
    })
  })
}
