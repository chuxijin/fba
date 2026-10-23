import {
  AuthApiError, getAuthSession, saveAuthSession, clearAuthSessionIfCurrent, getTokenFingerprint,
  getSignOutState, requestAuthApi, STORAGE_KEY_SIGNED_OUT, STORAGE_KEY_SIGNED_OUT_TOKEN,
} from './auth'
import {
  AUTH_BRIDGE_VERSION, getTokenExpiry, isAccessToken, isSiteAuthMessage, isTrustedSite,
  LOCAL_SITE_ORIGINS, SITE_URL_PATTERNS, withTimeout, type SiteAuthMessage, type TokenInfo, type UserInfo,
} from './auth-protocol'

let authRevision = 0
const pendingLogins = new Map<string, { revision: number; task: ReturnType<typeof applySiteAuth> }>()

function pendingLoginToken(): string | undefined {
  return [...pendingLogins.entries()].find(([, entry]) => entry.revision === authRevision)?.[0]
}

async function validateSiteToken(accessToken: string): Promise<UserInfo> {
  const user = await requestAuthApi<UserInfo>('/sys/users/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!user?.id) throw new Error('登录会话不可用')
  const { id, username, nickname, avatar } = user
  return { id, username, nickname, avatar }
}

export function handleSiteAuth(message: SiteAuthMessage) {
  if (!isSiteAuthMessage(message)) return Promise.reject(new Error('无效的登录同步消息'))
  if (message.type !== 'SITE_AUTH_LOGIN') return applySiteAuth(message)
  const accessToken = message.accessToken
  const existing = pendingLogins.get(accessToken)
  if (existing?.revision === authRevision) return existing.task
  // 页面握手与 Popup 自动重连可能同时提交同一会话，共用校验，避免互相判为过期响应。
  const entry = { task: applySiteAuth(message), revision: authRevision }
  pendingLogins.set(accessToken, entry)
  void entry.task.finally(() => {
    if (pendingLogins.get(accessToken) === entry) pendingLogins.delete(accessToken)
  }).catch(() => {})
  return entry.task
}

async function applySiteAuth(message: SiteAuthMessage) {
  const revision = message.type === 'SITE_AUTH_LOGIN' ? ++authRevision : authRevision
  const session = await getAuthSession()
  const before = session.token?.access_token
  if (message.type === 'SITE_AUTH_LOGOUT') {
    const pendingToken = pendingLoginToken()
    // 不相关的迟到退出不能取消正在校验的新登录。
    if (pendingToken && pendingToken !== message.expectedToken) return session
    if (message.expectedToken !== before && !pendingToken) {
      if (!before && bootstrapRequest && message.expectedToken) authRevision++
      return session
    }
    authRevision++
    if (before && message.expectedToken === before) {
      await endSession(before)
    }
    return getAuthSession()
  }
  const accessToken = message.type === 'SITE_AUTH_LOGIN' ? message.accessToken : before
  if (!accessToken) return session
  if (message.type === 'SITE_AUTH_LOGIN') {
    const logout = await getSignOutState()
    if (logout.signedOut && logout.fingerprint === await getTokenFingerprint(accessToken)) {
      return { ...await getAuthSession(), rejectedToken: accessToken }
    }
  }
  try {
    const user = await validateSiteToken(accessToken)
    const current = await getAuthSession()
    if (revision !== authRevision || current.token?.access_token !== before) return current
    const expiry = getTokenExpiry({ access_token: accessToken })
    if (before !== accessToken || JSON.stringify(current.user) !== JSON.stringify(user)) {
      await saveAuthSession({ access_token: accessToken,
        access_token_expire_time: expiry === null ? undefined : new Date(expiry).toISOString() }, user)
    }
    return getAuthSession()
  } catch (error) {
    if (revision !== authRevision) return getAuthSession()
    if (error instanceof AuthApiError && error.unauthorized) {
      if (before === accessToken) await clearAuthSessionIfCurrent(accessToken)
      return { ...await getAuthSession(), rejectedToken: accessToken }
    }
    throw error
  }
}

export async function logoutExtension(expectedToken: string): Promise<void> {
  const current = await getAuthSession()
  const pendingToken = pendingLoginToken()
  if (current.token?.access_token !== expectedToken || (pendingToken && pendingToken !== expectedToken)) return
  authRevision++
  await endSession(expectedToken)
}

async function endSession(accessToken: string): Promise<void> {
  const fingerprint = await getTokenFingerprint(accessToken)
  if ((await getAuthSession()).token?.access_token !== accessToken) return
  // 先清本地并同步官网，再撤销后端；断网时也不会恢复刚退出的会话。
  await chrome.storage.local.set({ [STORAGE_KEY_SIGNED_OUT]: true, [STORAGE_KEY_SIGNED_OUT_TOKEN]: fingerprint })
  await clearAuthSessionIfCurrent(accessToken)
  try {
    await requestAuthApi('/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${accessToken}` } })
  } catch (error) {
    // 官网可能已经撤销同一会话；重复退出视为成功，网络失败仍通知调用方。
    if (!(error instanceof AuthApiError && error.unauthorized)) throw error
  }
}

interface SitePageSession {
  bridgeVersion: number
  origin: string
  accessToken: string | null
}

async function readSitePageSession(tab: chrome.tabs.Tab): Promise<SitePageSession | null> {
  if (tab.id === undefined || !isTrustedSite(tab.url) || tab.discarded) return null
  const tabId = tab.id
  async function read(): Promise<SitePageSession> {
    const response = await withTimeout(
      chrome.tabs.sendMessage(tabId, { type: 'SITE_AUTH_READ_SESSION' }, { frameId: 0 }), 1500, '官网桥接未响应')
    if (response?.bridgeVersion !== AUTH_BRIDGE_VERSION || response.origin !== new URL(tab.url!).origin ||
        (response.accessToken !== null && !isAccessToken(response.accessToken))) {
      throw new Error('官网桥接需要更新')
    }
    return response
  }
  try {
    try { return await read() } catch {
      // 扩展重载不会为已打开的标签页补注入 content script；在准确的官网顶层页面恢复桥接。
      await chrome.scripting.executeScript({ target: { tabId, frameIds: [0] }, files: ['site-auth.js'] })
      return await read()
    }
  } catch { return null }
}

let bootstrapRequest: Promise<void> | null = null
export function bootstrapSiteSession(): Promise<void> {
  if (bootstrapRequest) return bootstrapRequest
  const task = (async () => {
    let revision = authRevision
    const tabs = await chrome.tabs.query({ url: SITE_URL_PATTERNS })
    tabs.sort((a, b) => Number(!!b.active) - Number(!!a.active))
    const pages = await Promise.all(tabs.map(readSitePageSession))
    // 重连注入可能已触发官网自身的登录握手，等待该次校验完成再请求额度。
    await Promise.all([...pendingLogins.values()].filter((entry) => entry.revision === authRevision).map((entry) => entry.task))
    if (revision !== authRevision || (await getAuthSession()).token?.access_token) return
    const logout = await getSignOutState()
    async function adopt(accessToken: string): Promise<boolean> {
      if (revision !== authRevision || (await getAuthSession()).token?.access_token) return true
      const expectedRevision = authRevision + 1
      const session = await handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken })
      if (authRevision !== expectedRevision) return true
      revision = expectedRevision
      return !!session.token?.access_token
    }
    for (const page of pages) {
      if (!page?.accessToken) continue
      if (revision !== authRevision) return
      // 优先读取当前已登录官网的 Cookie，再由后端验证；不依赖官网 BFF 的冷启动或跨域 Cookie 请求。
      if (await adopt(page.accessToken)) return
    }
    // 旧退出标记只能由上面的官网实际会话校验迁移，不能直接删除后恢复残留 Cookie。
    if (logout.signedOut && !logout.fingerprint) return
    for (const origin of LOCAL_SITE_ORIGINS) {
      try {
        // host_permissions 允许扩展请求本地官网，credentials 携带其现有 Cookie。
        const response = await fetch(`${origin}/api/extension/session`, {
          credentials: 'include', cache: 'no-store', signal: AbortSignal.timeout(2000),
        })
        if (!response.ok) continue
        const result = await response.json()
        if (result.code !== 200 || !result.data?.token?.access_token) continue
        if (revision !== authRevision) return
        const accessToken = result.data.token.access_token
        if (await adopt(accessToken)) return
      } catch { /* 官网未启动时继续扩展自身的游客流程 */ }
    }
  })()
  bootstrapRequest = task
  void task.finally(() => { if (bootstrapRequest === task) bootstrapRequest = null }).catch(() => {})
  return task
}

export function publicSession(session: Awaited<ReturnType<typeof getAuthSession>> & { rejectedToken?: string }) {
  return { token: session.token ? { access_token: session.token.access_token } as TokenInfo : null,
    user: session.user, rejectedToken: session.rejectedToken }
}
