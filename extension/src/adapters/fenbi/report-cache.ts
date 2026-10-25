import { fenbiReportRoute } from './report'
import type { FenbiHistoryItem, ReportDetailModule } from './report'

function numberValue(value: unknown): number | undefined {
  if (value === null || value === undefined || value === '') return undefined
  const number = Number(value)
  return Number.isFinite(number) ? number : undefined
}

const MAX_CACHED_REPORTS = 20

function setBounded<K, V>(map: Map<K, V>, key: K, value: V, limit: number): void {
  map.set(key, value)
  while (map.size > limit) map.delete(map.keys().next().value!)
}

/** 只保存页面已经收到的报告数据；按报告编号和逐题 key 关联，不发起网络请求。 */
export class FenbiReportCache {
  private solutions = new Map<string, any>()
  private reports = new Map<string, any>()
  private staticSolutions = new Map<string, any>()
  private history = new Map<string, FenbiHistoryItem>()

  capture(url: string, raw: any, pageUrl: string): void {
    const data = raw?.data && typeof raw.data === 'object' && !Array.isArray(raw.data) ? raw.data : raw
    if (!data || typeof data !== 'object') return
    const lowerUrl = url.toLowerCase()
    let requestKey = ''
    try { requestKey = new URL(url, pageUrl).searchParams.get('key') || '' } catch {}
    const exerciseKey = String(data.exerciseId || requestKey || fenbiReportRoute(pageUrl)?.key || '')

    if (lowerUrl.includes('/combine/exercise/getsolution') && exerciseKey && data.userAnswers) {
      setBounded(this.solutions, exerciseKey, { ...data, exerciseId: exerciseKey }, MAX_CACHED_REPORTS)
    }
    if (lowerUrl.includes('/combine/exercise/getreport') && exerciseKey) {
      setBounded(this.reports, exerciseKey, data, MAX_CACHED_REPORTS)
    }
    if (Array.isArray(data.solutions) && data.solutions.length) {
      this.staticSolutions.delete(url)
      setBounded(this.staticSolutions, url, data, MAX_CACHED_REPORTS)
    }
    if (lowerUrl.includes('/getexercisebriefhistory')) {
      for (const item of data.historyItems || []) {
        if (!item.exerciseKey) continue
        this.history.set(String(item.exerciseKey), {
          exerciseKey: String(item.exerciseKey),
          updatedTime: numberValue(item.updatedTime),
          score: numberValue(item.score),
          fullScore: numberValue(item.fullScore),
        })
      }
      while (this.history.size > 200) this.history.delete(this.history.keys().next().value!)
    }
  }

  read(href: string): {
    solution: any
    staticSolution: any
    details: ReportDetailModule[]
    moduleNodes: any[]
    history: FenbiHistoryItem | null
  } {
    const route = fenbiReportRoute(href)
    const solution = route ? this.solutions.get(route.key) : null
    const report = route ? this.reports.get(route.key) : null
    const subReports: any[] = Array.isArray(report?.subReports) ? report.subReports : []
    const details: ReportDetailModule[] = subReports
      .flatMap(sub => Array.isArray(sub?.courseReports) ? sub.courseReports : [])
      .find(course => Array.isArray(course?.details) && course.details.length)?.details || []
    const tree = subReports.find(sub => Array.isArray(sub?.children) && sub.nodeType !== undefined)
    const moduleNodes = details.length ? details : tree?.children || []
    const meta = subReports.find(sub => sub?.paperId != null && sub?.fullmark != null)
    const cachedHistory = route ? this.history.get(route.key) : null
    const history = route ? {
      exerciseKey: route.key,
      updatedTime: numberValue(meta?.submitTime) ?? cachedHistory?.updatedTime,
      score: numberValue(meta?.score) ?? cachedHistory?.score,
      fullScore: numberValue(meta?.fullmark) ?? cachedHistory?.fullScore,
    } : null

    // 静态解析包没有报告编号，必须和本报告的作答 key 完全对应，不能复用上一张卷子。
    const answerKeys = Object.keys(solution?.userAnswers || {})
    const answerKeySet = new Set(answerKeys)
    const staticSolution = answerKeys.length ? [...this.staticSolutions.values()].reverse().find(data => {
      const keys = data.solutions.map((item: any) => String(item?.globalId || ''))
      return keys.length === answerKeys.length && new Set(keys).size === keys.length
        && keys.every((key: string) => answerKeySet.has(key))
    }) : null
    return { solution, staticSolution, details, moduleNodes, history }
  }
}
