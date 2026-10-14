/**
 * 网页主环境通用网络请求嗅探器 (运行于宿主页面的 MAIN 世界)
 * 职责极度单一纯粹 (KISS 原则):
 * 1. 透明 Hook 原生 fetch 与 XMLHttpRequest，静默捕获题库/试卷/报告 JSON
 * 2. 劫持 History API 与 HashChange，实现无感 SPA 路由感知
 * 3. 绝不掺杂任何特定平台的业务逻辑与错题算法，100% 原始数据直接派发给 Content Script
 */
;(function () {
  const SCRIPT_TAG = '[公考网络嗅探引擎]'
  console.log(`${SCRIPT_TAG} 网络请求拦截与 SPA 路由感知系统已就绪`)

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
  const cachedPayloads: Array<{ url: string; data: any; timestamp: number }> = []

  function dispatchRawData(url: string, data: any) {
    if (!data) return
    const entry = { url, data, timestamp: Date.now() }
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
        pageUrl: window.location.href,
        timestamp: Date.now(),
      },
      '*'
    )
  }

  // ==========================================
  // 3. Hook window.fetch
  // ==========================================
  const originalFetch = window.fetch
  window.fetch = async function (...args) {
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
          .then((data) => dispatchRawData(url, data))
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
    ;(this as any)._url = args[1]
    return originalXhrOpen.apply(this, args as any)
  }

  XMLHttpRequest.prototype.send = function (body?: Document | XMLHttpRequestBodyInit | null) {
    this.addEventListener('load', function () {
      try {
        const url = (this as any)._url || ''
        if (isTargetExamUrl(url) && this.responseText) {
          const data = JSON.parse(this.responseText)
          dispatchRawData(url, data)
        }
      } catch (e) {}
    })
    return originalXhrSend.call(this, body)
  }

  // 监听来自 Content Script 的主动试卷包重发请求
  window.addEventListener('message', (event) => {
    if (event.data?.source === 'GONGKAO_CONTENT_REQUEST_EXAM') {
      for (const item of cachedPayloads) {
        window.postMessage(
          {
            source: 'GONGKAO_REFORMATTER_INTERCEPTOR',
            type: 'RAW_API_INTERCEPTED',
            url: item.url,
            data: item.data,
            pageUrl: window.location.href,
            timestamp: item.timestamp,
          },
          '*'
        )
      }
    }
  })
})()
