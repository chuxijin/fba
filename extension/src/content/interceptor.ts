/**
 * 网页主环境通用网络请求嗅探器 (运行于宿主页面的 MAIN 世界)
 * 职责极度单一纯粹 (KISS 原则):
 * 1. 透明 Hook 原生 fetch 与 XMLHttpRequest，静默捕获题库/试卷/报告 JSON
 * 2. 劫持 History API 与 HashChange，实现无感 SPA 路由感知
 * 3. 绝不掺杂任何特定平台的业务逻辑与错题算法，100% 原始数据直接派发给 Content Script
 */
;(function () {

  // ==========================================
  // 1. Hook History API & SPA 路由感知
  // ==========================================
  const originalPushState = history.pushState
  history.pushState = function (...args) {
    const res = originalPushState.apply(this, args)
    dispatchRouteChange(window.location.href)
    return res
  }

  const originalReplaceState = history.replaceState
  history.replaceState = function (...args) {
    const res = originalReplaceState.apply(this, args)
    dispatchRouteChange(window.location.href)
    return res
  }

  window.addEventListener('popstate', () => dispatchRouteChange(window.location.href))
  window.addEventListener('hashchange', () => dispatchRouteChange(window.location.href))

  function dispatchRouteChange(newUrl: string) {
    window.postMessage(
      {
        source: 'GONGKAO_REFORMATTER_INTERCEPTOR',
        type: 'SPA_ROUTE_CHANGED',
        url: newUrl,
        timestamp: Date.now(),
      },
      '*'
    )
  }

  // ==========================================
  // 2. 目标公考 URL 白名单智能匹配
  // ==========================================
  function isTargetExamUrl(url: string): boolean {
    if (!url) return false
    const lower = url.toLowerCase()
    return (
      lower.includes('fenbi.com') ||
      lower.includes('fbstatic.cn') ||
      lower.includes('fenbike.cn') ||
      lower.includes('huatu.com') ||
      lower.includes('shikaobang.cn') ||
      lower.includes('/waapi/') ||
      lower.includes('/combine/') ||
      lower.includes('/static/exercise') ||
      lower.includes('/exam') ||
      lower.includes('/exercises') ||
      lower.includes('/mock') ||
      lower.includes('/paper') ||
      lower.includes('/error') ||
      lower.includes('/wrong') ||
      lower.includes('/practice') ||
      lower.includes('/solution') ||
      lower.includes('/report') ||
      lower.includes('/sheet') ||
      lower.includes('/tiku')
    )
  }

  // 缓存最近拦截到的网络数据流供重发
  const cachedPayloads: Array<{ url: string; data: any; pageUrl: string; timestamp: number }> = []

  function dispatchRawData(url: string, data: any, pageUrl: string) {
    if (!data) return
    const entry = { url, data, pageUrl, timestamp: Date.now() }
    const previous = cachedPayloads.findIndex(item => item.url === url && item.pageUrl === pageUrl)
    if (previous >= 0) cachedPayloads.splice(previous, 1)
    cachedPayloads.push(entry)
    if (cachedPayloads.length > 30) cachedPayloads.shift()

    // 动态嗅探粉笔题库前缀 (如 syzc, xingce)
    const prefixMatch = url.match(/tiku\.fenbi\.com\/api\/([a-zA-Z0-9_\-]+)\//)
    if (prefixMatch && prefixMatch[1] && prefixMatch[1] !== 'universal' && prefixMatch[1] !== 'auth') {
      ;(window as any).__FENBI_ACTIVE_TIKU_PREFIX__ = prefixMatch[1]
    }

    window.postMessage(
      {
        source: 'GONGKAO_REFORMATTER_INTERCEPTOR',
        type: 'RAW_API_INTERCEPTED',
        url,
        data,
        pageUrl,
        timestamp: entry.timestamp,
      },
      '*'
    )
  }

  // ==========================================
  // 3. Hook window.fetch
  // ==========================================
  const originalFetch = window.fetch
  window.fetch = async function (...args) {
    const pageUrl = window.location.href
    const response = await originalFetch.apply(this, args)
    try {
      const input = args[0]
      let url = ''
      if (typeof input === 'string') {
        url = input
      } else if (input instanceof URL) {
        url = input.href
      } else if (input && typeof (input as any).url === 'string') {
        url = (input as any).url
      }

      if (isTargetExamUrl(url)) {
        const clone = response.clone()
        clone
          .json()
          .then((data) => dispatchRawData(url, data, pageUrl))
          .catch(() => {})
      }
    } catch (e) {}
    return response
  }

  // ==========================================
  // 4. Hook XMLHttpRequest
  // ==========================================
  const originalXhrOpen = XMLHttpRequest.prototype.open
  const originalXhrSend = XMLHttpRequest.prototype.send

  XMLHttpRequest.prototype.open = function (...args: any[]) {
    ;(this as any)._url = String(args[1])
    return originalXhrOpen.apply(this, args as any)
  }

  XMLHttpRequest.prototype.send = function (body?: Document | XMLHttpRequestBodyInit | null) {
    const pageUrl = window.location.href
    this.addEventListener('load', function () {
      try {
        const url = (this as any)._url || ''
        if (!isTargetExamUrl(url)) return
        // responseType=json 时访问 responseText 会抛错，必须直接读取 response 对象。
        const data = this.responseType === 'json'
          ? this.response
          : (!this.responseType || this.responseType === 'text') && this.responseText
            ? JSON.parse(this.responseText) : null
        dispatchRawData(url, data, pageUrl)
      } catch (e) {}
    })
    return originalXhrSend.call(this, body)
  }

  // 只重播页面已收到的缓存，不替页面请求报告、解析或历史接口。
  window.addEventListener('message', (event) => {
    if (event.source !== window || event.origin !== location.origin) return
    if (event.data?.source === 'GONGKAO_CONTENT_REQUEST_EXAM') {
      for (const item of cachedPayloads) {
        window.postMessage(
          {
            source: 'GONGKAO_REFORMATTER_INTERCEPTOR',
            type: 'RAW_API_INTERCEPTED',
            url: item.url,
            data: item.data,
            pageUrl: item.pageUrl,
            timestamp: item.timestamp,
          },
          '*'
        )
      }
      const requestId = String(event.data.requestId || '')
      if (/^[a-zA-Z0-9-]{8,80}$/.test(requestId)) {
        window.postMessage({ source: 'GONGKAO_CONTENT_REPLAY_DONE', requestId, pageUrl: location.href }, location.origin)
      }
    }
  })
})()
