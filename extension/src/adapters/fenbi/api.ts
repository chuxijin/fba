import { UnifiedPaper, RenderTypographySettings } from '../types'
import { fenbiSession } from './session'
import { extractFenbiPaperFromDom } from './dom'

/**
 * 粉笔试卷状态即时感知器 (严格遵循 100% 纯静默被动拦截原则，杜绝任何主动网络请求)
 * 职责：
 * 1. 优先从 FenbiSessionManager 会话中获取最新已聚合的试卷
 * 2. 若未就绪，向 MAIN 世界触发重播已拦截的网络缓存
 * 3. 兜底尝试从页面 DOM 视图结构中提取
 * 4. 严禁向粉笔官方接口发起任何主动 HTTP 请求
 */
export async function fetchFenbiPaperActively(settings: RenderTypographySettings): Promise<UnifiedPaper | null> {
  // 1. 优先读取已聚合好的试卷
  const existingPaper = fenbiSession.getPaper()
  if (existingPaper && existingPaper.total_questions > 0) {
    return existingPaper
  }

  // 2. 若已有静态题包，立即重新触发聚合
  const reAggregated = fenbiSession.buildAggregatedPaper(settings)
  if (reAggregated && reAggregated.total_questions > 0) {
    return reAggregated
  }

  // 3. 唤醒 injected.js 重播内存中已捕获的网络包缓存
  if (typeof window !== 'undefined') {
    window.postMessage({ source: 'GONGKAO_CONTENT_REQUEST_EXAM' }, '*')
  }

  // 短暂等待拦截消息分发
  await new Promise((resolve) => setTimeout(resolve, 80))

  const afterReplay = fenbiSession.getPaper() || fenbiSession.buildAggregatedPaper(settings)
  if (afterReplay && afterReplay.total_questions > 0) {
    return afterReplay
  }

  // 4. 纯净 DOM 兜底扫描 (不发任何网络请求)
  if (typeof document !== 'undefined') {
    const domPaper = extractFenbiPaperFromDom(settings)
    if (domPaper && domPaper.total_questions > 0) {
      return fenbiSession.enrichFromDom(domPaper)
    }
  }

  return null
}
