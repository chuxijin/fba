/** 只提取已验证的字段；不保存请求key，不把空值转成0。 */
export interface PlatformReferenceBase {
  version: 'fenbi-global-v1'
  captured_at: string
  population: 'platform_unspecified'
}
export interface PlatformQuestionReference extends PlatformReferenceBase {
  correct_ratio_percent: number | null
  total_count_raw: number | null
  wrong_count_raw: number | null
  most_wrong_choice: string | null
}
export interface PlatformReportReference extends PlatformReferenceBase {
  difficulty_raw: number | null
  average_score: number | null
  beat_rate_percent: number | null
  highest_score: number | null
  sigma_raw: number | null
  total_user_raw: number | null
}
function numeric(value: unknown, max = Number.MAX_VALUE): number | null {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
  if (typeof value !== 'number' && typeof value !== 'string') return null
  if (typeof value === 'string' && !value.trim()) return null
  const n = Number(value)
  return Number.isFinite(n) && n >= 0 && n <= max ? n : null
}
function count(value: unknown): number | null {
  const n = numeric(value, 1e12)
  return n !== null && Number.isSafeInteger(n) ? n : null
}
function base(timestamp: number): PlatformReferenceBase {
  return { version: 'fenbi-global-v1', captured_at: new Date(timestamp).toISOString(), population: 'platform_unspecified' }
}
export function questionReference(raw: any, timestamp: number): PlatformQuestionReference {
  return {
    ...base(timestamp), correct_ratio_percent: numeric(raw?.correctRatio, 100),
    total_count_raw: count(raw?.totalCount), wrong_count_raw: count(raw?.wrongCount),
    most_wrong_choice: typeof raw?.mostWrongAnswer?.choice === 'string' ? raw.mostWrongAnswer.choice.slice(0, 100) : null,
  }
}
export function reportReference(raw: any, timestamp: number): PlatformReportReference | null {
  const reports = Array.isArray(raw?.subReports) ? raw.subReports : []
  const basic = reports.find((s: any) => s?.type === 0)
  const overall = reports.find((s: any) => s?.type === 3)
  if (!basic && !overall) return null
  return {
    ...base(timestamp), difficulty_raw: numeric(basic?.difficulty), average_score: numeric(overall?.average),
    beat_rate_percent: numeric(overall?.beatRate, 100), highest_score: numeric(overall?.highest),
    sigma_raw: numeric(overall?.sigma), total_user_raw: count(overall?.totalUser),
  }
}
