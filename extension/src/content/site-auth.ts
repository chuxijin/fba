import { AUTH_BRIDGE_VERSION, isSiteAuthMessage, isTrustedSite, readSiteToken, SITE_AUTH_CHANNEL as CHANNEL } from '../utils/auth-protocol'

if (isTrustedSite(location.href) && window === window.top) {
  const bridgeScope = globalThis as typeof globalThis & { __fbaSiteAuthDispose?: () => void }
  bridgeScope.__fbaSiteAuthDispose?.()
  let revision = 0
  let siteDetected = false
  let lastSync = 'idle'
  function post(payload: unknown) { window.postMessage(payload, location.origin) }
  function onSiteMessage(event: MessageEvent) {
    const data = event.data
    const id = data?.id
    if (event.source !== window || event.origin !== location.origin || data?.channel !== CHANNEL ||
        data.direction !== 'site-to-extension' || typeof id !== 'string' || id.length > 100 ||
        !isSiteAuthMessage(data)) return
    if (!chrome.runtime?.id) {
      window.removeEventListener('message', onSiteMessage, { capture: true })
      return
    }
    // 优先于旧版残留监听器接收请求，防止失效上下文的错误响应抢先覆盖重连后的成功响应。
    event.stopImmediatePropagation()
    const version = ++revision
    siteDetected = true
    lastSync = 'pending'
    try {
      chrome.runtime.sendMessage(data, (response) => {
        const error = chrome.runtime.lastError
        if (version === revision) lastSync = !error && response?.success ? 'success' : 'error'
        post({ channel: CHANNEL, direction: 'extension-to-site', id,
          success: !error && response?.success, state: response?.state, error: error?.message || response?.error,
          stale: version !== revision })
      })
    } catch {
      lastSync = 'error'
      post({ channel: CHANNEL, direction: 'extension-to-site', id,
        success: false, error: '扩展已更新，请刷新官网页面后重试' })
    }
  }
  function onExtensionMessage(message: { type: string }, _sender: chrome.runtime.MessageSender, sendResponse: (response: unknown) => void) {
    if (message.type === 'SITE_AUTH_READ_SESSION') {
      sendResponse({ bridgeVersion: AUTH_BRIDGE_VERSION, origin: location.origin, accessToken: readSiteToken(document.cookie) })
      return false
    }
    if (message.type === 'SITE_AUTH_DIAGNOSE') {
      sendResponse({ bridgeVersion: AUTH_BRIDGE_VERSION, siteDetected, lastSync,
        hasSiteToken: !!readSiteToken(document.cookie) })
      return false
    }
    if (message.type === 'SITE_AUTH_CHANGED') {
      revision++
      post({ channel: CHANNEL, direction: 'extension-to-site', type: 'changed' })
    }
    return false
  }
  window.addEventListener('message', onSiteMessage, { capture: true })
  chrome.runtime.onMessage.addListener(onExtensionMessage)
  bridgeScope.__fbaSiteAuthDispose = () => {
    window.removeEventListener('message', onSiteMessage, { capture: true })
    try { chrome.runtime.onMessage.removeListener(onExtensionMessage) } catch { /* 兼容已被重载的扩展上下文 */ }
  }
  post({ channel: CHANNEL, direction: 'extension-to-site', type: 'available' })
}
