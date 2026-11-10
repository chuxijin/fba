import type { ImportBuildResult } from '../importer'
import { formatUserAnswerChoice } from './normalize'
import { fenbiReportRoute } from './report'
import type { FenbiHistoryItem } from './report'

/** 只读当前报告缓存；同一条真实作答提供答案和用时，不按卷名或题序猜测。 */
export function attachFenbiWrongOccurrences(
  built: ImportBuildResult, href: string,
  cached: { solution: any; history: FenbiHistoryItem | null },
): ImportBuildResult {
  const route = fenbiReportRoute(href)
  const solution = cached.solution?.data || cached.solution
  if (!route || solution?.exerciseId !== route.key) return built
  const timestamp = cached.history?.exerciseKey === route.key ? cached.history.updatedTime : undefined
  const date = typeof timestamp === 'number' && timestamp > 0 ? new Date(timestamp) : null
  const submittedTime = date && Number.isFinite(date.getTime()) ? date.toISOString() : null
  return {
    ...built,
    items: built.items.map(item => {
      if (item.source_system !== 'fenbi' || !item.entry_metadata.source_question_key) return item
      const user = solution.userAnswers?.[item.entry_metadata.source_question_key]
      const answer = formatUserAnswerChoice(user?.answer)
      if (Number(user?.status) !== -1 || !answer) return item
      const tokens = answer.split(',')
      const rawTime = user.time
      const duration = typeof rawTime === 'number' || (typeof rawTime === 'string' && rawTime.trim())
        ? Number(rawTime) : NaN
      const externalKey = `fenbi:${route.key}:${item.entry_metadata.source_question_key}`
      return {
        ...item,
        external_key: externalKey,
        idempotency_key: `ext-${externalKey}`.slice(0, 128),
        wrong_response: tokens.length === 1 ? tokens[0] : tokens,
        wrong_occurrence: {
          source_key: route.key,
          submitted_time: submittedTime,
          duration_seconds: Number.isFinite(duration) && duration >= 0 ? Math.round(duration) : null,
        },
      }
    }),
  }
}
