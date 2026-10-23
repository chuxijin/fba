import { getAuthSession, getSignOutState } from './auth'
import { AUTH_BRIDGE_VERSION, BACKEND_BASE, isTokenExpired, isTrustedSite, LOCAL_SITE_ORIGINS, SITE_URL_PATTERNS, withTimeout } from './auth-protocol'

/** 用户主动检查时生成可复制报告，只输出状态，不输出 Cookie、Token 或用户资料。 */
export async function collectAuthDiagnostics(): Promise<string> {
  const session = await getAuthSession()
  const logout = await getSignOutState()
  const tabs = await chrome.tabs.query({ url: SITE_URL_PATTERNS })
  const accessToken = session.token?.access_token
  const backend = checkEndpoint(`${BACKEND_BASE}/api/v1/render-books/public/quota`, accessToken)
  const sites = await Promise.all(LOCAL_SITE_ORIGINS.map(async (origin) => {
    const allowed = await chrome.permissions.contains({ origins: [`${new URL(origin).protocol}//${new URL(origin).hostname}/*`] })
    if (!allowed) return [`官网 ${origin}`, '  站点访问权限未开启，请在扩展详情中允许访问此站点。']
    const result = await checkEndpoint(`${origin}/api/extension/session`)
    const lines = [`官网 ${origin}`, `  会话接口：${result}`]
    const siteTabs = tabs.filter((tab) => isTrustedSite(tab.url) && new URL(tab.url!).origin === origin)
    if (!siteTabs.length) lines.push('  未打开此官网标签页')
    for (const tab of siteTabs) {
      try {
        const state = await withTimeout(chrome.tabs.sendMessage(tab.id!, { type: 'SITE_AUTH_DIAGNOSE' }, { frameId: 0 }), 1500, '官网桥接未响应')
        if (state?.bridgeVersion !== AUTH_BRIDGE_VERSION) throw new Error('outdated bridge')
        lines.push(`  页面桥接：已注入 v${state.bridgeVersion}；官网脚本：${state.siteDetected ? '已握手' : '未握手，请刷新官网'}`)
        lines.push(`  页面 Cookie：${state.hasSiteToken ? '存在' : '不存在'}；最近同步：${syncLabels[state.lastSync] || '未知'}`)
      } catch {
        if (tab.discarded) {
          lines.push('  页面桥接：标签页已休眠，请先打开该官网标签页')
          continue
        }
        try {
          // permissions.contains 只反映清单授权，不能识别浏览器的“此站点不允许使用扩展”。
          // 运行无副作用的探针，以浏览器实际访问判定为准，不读取任何页面数据。
          await chrome.scripting.executeScript({ target: { tabId: tab.id!, frameIds: [0] }, func: () => true })
          lines.push('  页面桥接：站点访问正常，桥接未连接或版本过旧，请点击“从官网同步”')
        } catch (error) {
          const message = error instanceof Error ? error.message : ''
          if (/^Blocked\.?$/i.test(message.trim())) {
            lines.push(`  页面桥接：浏览器已暂停此网站上的扩展（Blocked）。打开 ${origin} 的 🧩 扩展菜单，开启“允许在此网站使用扩展”，再刷新官网`)
          } else if (/Cannot access|permission|not allowed|denied/i.test(message)) {
            lines.push('  页面桥接：浏览器拒绝站点访问。请检查该网站的总开关和扩展的站点访问权限')
          } else {
            lines.push('  页面桥接：访问探针未完成，请重新加载扩展并打开官网标签页后重试')
          }
        }
      }
    }
    return lines
  }))
  const unsupported = [...new Set(tabs.filter((tab) => tab.url && !isTrustedSite(tab.url)).map((tab) => new URL(tab.url!).origin))]
  return [
    `登录同步检查（扩展 ${chrome.runtime.getManifest().version} / 桥接 v${AUTH_BRIDGE_VERSION}）`,
    `扩展凭据：${accessToken ? isTokenExpired(session.token) ? '已过期，请重新登录' : '存在' : '不存在'}`,
    `退出保护：${logout.signedOut ? logout.fingerprint ? '仅屏蔽上次退出的凭据' : '旧版退出标记，保持已登录官网打开后点击“从官网同步”' : '未启用'}`,
    `后端 ${BACKEND_BASE}：${await backend}`,
    ...sites.flat(),
    ...unsupported.map((origin) => `本地页面 ${origin} 未接入登录桥接，请使用上列 3000 端口的官网`),
  ].join('\n')
}

const syncLabels: Record<string, string> = { idle: '尚未开始', pending: '进行中', success: '成功', error: '失败' }

async function checkEndpoint(url: string, accessToken?: string): Promise<string> {
  try {
    const response = await fetch(url, {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      credentials: 'include', cache: 'no-store', signal: AbortSignal.timeout(8000),
    })
    if (response.status === 401 || response.status === 403) return `凭据被拒绝（HTTP ${response.status}），请重新登录`
    if (!response.ok) return `接口异常（HTTP ${response.status}）`
    const result = await response.json()
    if (result.code !== 200) return `接口异常（业务码 ${Number(result.code) || '未知'}）`
    if (url.endsWith('/quota')) {
      if (typeof result.data?.is_logged_in !== 'boolean') return '接口格式异常'
      return result.data.is_logged_in ? '已确认登录' : '游客'
    }
    if (!result.data || !('token' in result.data)) return '接口格式异常'
    return result.data.token?.access_token ? '已有有效登录' : '未读到有效登录 Cookie'
  } catch (error) {
    if (error instanceof Error && ['AbortError', 'TimeoutError'].includes(error.name)) return '会话校验超时；可点击“从官网同步”通过已打开页面重连'
    return '连接失败（Failed to fetch）；也可能是浏览器暂停了此网站上的扩展，请结合下方页面桥接结果检查'
  }
}
