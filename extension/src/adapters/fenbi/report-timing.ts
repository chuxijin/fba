import type { PracticeReportPayload } from './report'

export function applyReportTiming(draft: PracticeReportPayload, exclude: boolean, actualSeconds: string | number): PracticeReportPayload {
  const seconds = actualSeconds === '' ? null : Number(actualSeconds)
  if (exclude && seconds != null && (!Number.isSafeInteger(seconds) || seconds < 0)) {
    throw new Error('实际用时请填写非负整数秒，未知请留空')
  }
  // 原平台整卷、模块、逐题用时保持原样；不分摊手填的整卷计时。
  return { ...draft, exclude_source_timing: exclude, manual_duration_seconds: exclude ? seconds : null }
}
