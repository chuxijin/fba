import {
  AUTH_MESSAGE_TIMEOUT, AUTH_REQUEST_TIMEOUT, BACKEND_BASE,
  getTokenExpiry, isQuotaInfo, isTokenExpired, withTimeout,
  type QuotaInfo, type TokenInfo, type UserInfo,
} from './auth-protocol'

export { getTokenExpiry, isTokenExpired, type QuotaInfo, type TokenInfo, type UserInfo } from './auth-protocol'

export interface ScanQrcodeResult {
  scene_id: string
  qrcode_data_url: string
  expires_in: number
}

export const STORAGE_KEY_TOKEN = 'fba_auth_token'
export const STORAGE_KEY_USER = 'fba_auth_user'
export const STORAGE_KEY_QUOTA_REVISION = 'fba_quota_revision'
export const STORAGE_KEY_ACCOUNT_CACHE = 'fba_account_cache'
export const STORAGE_KEY_SIGNED_OUT = 'fba_auth_signed_out'
export const STORAGE_KEY_SIGNED_OUT_TOKEN = 'fba_auth_signed_out_token'
export const STORAGE_KEY_SITE_SESSION = 'fba_auth_site_session'

export async function getSignOutState(): Promise<{ signedOut: boolean; fingerprint?: string }> {
  const data = await chrome.storage.local.get([STORAGE_KEY_SIGNED_OUT, STORAGE_KEY_SIGNED_OUT_TOKEN])
  const fingerprint = data[STORAGE_KEY_SIGNED_OUT_TOKEN]
  return { signedOut: !!data[STORAGE_KEY_SIGNED_OUT], fingerprint: typeof fingerprint === 'string' ? fingerprint : undefined }
}

/** 统一处理后台消息的失败、超时及失效扩展上下文。 */
export function sendAuthMessage<T>(message: { type: string; expectedToken?: string }, fallback: string, timeout = AUTH_MESSAGE_TIMEOUT): Promise<T> {
  const task = new Promise<T>((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      const error = chrome.runtime.lastError
      if (error || response?.success !== true) reject(new Error(error?.message || response?.error || fallback))
      else resolve(response as T)
    })
  })
  return withTimeout(task, timeout, fallback)
}

export class AuthApiError extends Error {
  constructor(message: string, public unauthorized = false) { super(message) }
}

/** 统一 HTTP/业务错误；只读一次响应，兼容代理返回的非 JSON 错误。 */
export async function requestAuthApi<T>(path: string, options: RequestInit = {}, serverBase = BACKEND_BASE): Promise<T> {
  const response = await fetch(`${serverBase.replace(/\/+$/, '')}/api/v1${path}`, {
    ...options, signal: options.signal || AbortSignal.timeout(AUTH_REQUEST_TIMEOUT),
    headers: { ...options.headers, 'X-Client-Type': 'extension' },
  })
  const result = await response.json().catch(() => null)
  if ([response.status, result?.code].some((code) => code === 401 || code === 403)) {
    throw new AuthApiError(result?.msg || '登录会话已失效，请重新登录', true)
  }
  if (!response.ok || result?.code !== 200) {
    throw new AuthApiError(result?.msg || `账户服务响应异常 (${response.status})`)
  }
  return result.data as T
}

interface AccountCache {
  version: 1
  sessionKey: string
  serverBase: string
  confirmedAt: number
  quota: QuotaInfo
}

interface AuthSession {
  token: TokenInfo | null
  user: UserInfo | null
  cache?: AccountCache
  quotaRevision?: string
  sourceSession?: string
}

export async function getAuthSession(): Promise<AuthSession> {
  if (typeof chrome !== 'undefined' && chrome.storage?.local) {
    const data = await chrome.storage.local.get([
      STORAGE_KEY_TOKEN, STORAGE_KEY_USER, STORAGE_KEY_ACCOUNT_CACHE, STORAGE_KEY_QUOTA_REVISION,
      STORAGE_KEY_SITE_SESSION,
    ])
    return {
      token: data[STORAGE_KEY_TOKEN] || null,
      user: data[STORAGE_KEY_USER] || null,
      cache: data[STORAGE_KEY_ACCOUNT_CACHE],
      quotaRevision: data[STORAGE_KEY_QUOTA_REVISION],
      sourceSession: data[STORAGE_KEY_SITE_SESSION] || undefined,
    }
  }
  return {
    token: JSON.parse(localStorage.getItem(STORAGE_KEY_TOKEN) || 'null'),
    user: JSON.parse(localStorage.getItem(STORAGE_KEY_USER) || 'null'),
    cache: JSON.parse(localStorage.getItem(STORAGE_KEY_ACCOUNT_CACHE) || 'null'),
    sourceSession: localStorage.getItem(STORAGE_KEY_SITE_SESSION) || undefined,
  }
}

export async function getTokenFingerprint(accessToken: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(accessToken))
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

async function sessionKey(token: TokenInfo | null): Promise<string> {
  return token?.access_token ? getTokenFingerprint(token.access_token) : 'guest'
}

/** 仅复用同一服务端、同一凭据的已确认身份；额度由视图标记为待刷新。 */
export async function readCachedAccount(serverBase: string): Promise<{ quota: QuotaInfo; token: TokenInfo | null } | null> {
  const session = await getAuthSession()
  const cache = session.cache
  if (!cache || cache.version !== 1 || cache.serverBase !== serverBase.replace(/\/+$/, '')) return null
  const quota = cache.quota
  if (!isQuotaInfo(quota)) return null
  const expiry = getTokenExpiry(session.token)
  if (quota.is_logged_in && (!session.token?.access_token || expiry === null || expiry <= Date.now())) return null
  if (!quota.is_logged_in && session.token?.access_token) return null
  const age = Date.now() - cache.confirmedAt
  if (!Number.isFinite(age) || age < 0 || age > (quota.is_logged_in ? 86400000 : 300000)) return null
  if (cache.sessionKey !== await sessionKey(session.token)) return null
  return {
    quota: { ...quota, user: quota.is_logged_in ? quota.user || session.user || undefined : undefined },
    token: session.token,
  }
}

async function cacheConfirmedAccount(quota: QuotaInfo, session: AuthSession, serverBase: string): Promise<boolean> {
  const cache: AccountCache = {
    version: 1,
    sessionKey: await sessionKey(session.token),
    serverBase: serverBase.replace(/\/+$/, ''),
    confirmedAt: Date.now(),
    quota,
  }
  const current = await getAuthSession()
  if (current.token?.access_token !== session.token?.access_token || current.quotaRevision !== session.quotaRevision) return false
  if (typeof chrome !== 'undefined' && chrome.storage?.local) {
    await chrome.storage.local.set({ [STORAGE_KEY_ACCOUNT_CACHE]: cache })
  } else {
    localStorage.setItem(STORAGE_KEY_ACCOUNT_CACHE, JSON.stringify(cache))
  }
  return true
}

// 只清除本次请求使用的凭据，避免迟到的失败响应清掉刚登录的新账号。
export async function clearAuthSessionIfCurrent(accessToken: string): Promise<void> {
  const session = await getAuthSession()
  if (session.token?.access_token === accessToken) await clearAuthSession()
}

/**
 * 保存登录成功后的凭据与用户信息
 */
export async function saveAuthSession(token: TokenInfo, user?: UserInfo, sourceSession?: string): Promise<void> {
  if (typeof chrome !== 'undefined' && chrome.storage?.local) {
    await chrome.storage.local.set({
      [STORAGE_KEY_TOKEN]: token,
      [STORAGE_KEY_USER]: user || {},
      [STORAGE_KEY_ACCOUNT_CACHE]: null,
      [STORAGE_KEY_SIGNED_OUT]: false,
      [STORAGE_KEY_SIGNED_OUT_TOKEN]: null,
      [STORAGE_KEY_SITE_SESSION]: sourceSession || null,
    })
  } else {
    localStorage.setItem(STORAGE_KEY_TOKEN, JSON.stringify(token))
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user || {}))
    localStorage.removeItem(STORAGE_KEY_ACCOUNT_CACHE)
    if (sourceSession) localStorage.setItem(STORAGE_KEY_SITE_SESSION, sourceSession)
    else localStorage.removeItem(STORAGE_KEY_SITE_SESSION)
  }
}

let refreshPending: Promise<AuthSession> | null = null

/** 后台统一续期插件自己的会话；旧请求不覆盖后来登录的账号。 */
export async function getRequestAuthSession(serverBase = BACKEND_BASE): Promise<AuthSession> {
  const session = await getAuthSession()
  if (!session.token || !isTokenExpired(session.token)) return session
  if (!session.token.refresh_token) {
    await clearAuthSessionIfCurrent(session.token.access_token)
    return getAuthSession()
  }
  if (refreshPending) return refreshPending
  const task = (async () => {
    try {
      const token = await requestAuthApi<TokenInfo>('/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.token!.access_token}` },
        body: JSON.stringify({ refresh_token: session.token!.refresh_token }),
      }, serverBase)
      if (!token.access_token || !token.refresh_token || token.client_type !== 'extension') {
        throw new Error('插件刷新响应无效')
      }
      if ((await getAuthSession()).token?.access_token === session.token!.access_token) {
        await saveAuthSession(token, session.user || undefined, session.sourceSession)
      }
    } catch (error) {
      if (!(error instanceof AuthApiError && error.unauthorized)) throw error
      await clearAuthSessionIfCurrent(session.token!.access_token)
    }
    return getAuthSession()
  })()
  refreshPending = task
  try { return await task } finally { if (refreshPending === task) refreshPending = null }
}

/**
 * 清除登录凭据（登出）
 */
export async function clearAuthSession(): Promise<void> {
  if (typeof chrome !== 'undefined' && chrome.storage?.local) {
    await chrome.storage.local.remove([STORAGE_KEY_TOKEN, STORAGE_KEY_USER, STORAGE_KEY_ACCOUNT_CACHE])
  } else {
    localStorage.removeItem(STORAGE_KEY_TOKEN)
    localStorage.removeItem(STORAGE_KEY_USER)
    localStorage.removeItem(STORAGE_KEY_ACCOUNT_CACHE)
  }
}

/** 用户主动退出时，由后台撤销服务端会话并同步官网。 */
export async function logoutAuthSession(): Promise<void> {
  const session = await getAuthSession()
  if (!session.token?.access_token) return clearAuthSession()
  await sendAuthMessage({ type: 'LOGOUT_AUTH', expectedToken: session.token.access_token }, '服务端退出失败')
}

/**
 * 请求后端生成小程序登录二维码
 */
export async function fetchScanQrcode(serverBase = BACKEND_BASE): Promise<ScanQrcodeResult> {
  const data = await requestAuthApi<ScanQrcodeResult>('/oauth2/wechat/scan/qrcode', {}, serverBase)
  if (!data?.scene_id) throw new Error('获取微信扫码登录二维码失败')
  return data
}

/**
 * 轮询检查扫码登录状态
 */
export async function pollScanStatus(
  sceneId: string,
  serverBase = BACKEND_BASE
): Promise<{ status: 'PENDING' | 'CONFIRMED' | 'EXPIRED'; token?: TokenInfo; user?: UserInfo; msg?: string }> {
  return requestAuthApi(`/oauth2/wechat/scan/status?scene_id=${encodeURIComponent(sceneId)}`, {}, serverBase)
}

/**
 * 模拟手机确认扫码（开发与测试环境专属）
 */
export async function mockConfirmScan(
  sceneId: string,
  serverBase = BACKEND_BASE
): Promise<boolean> {
  await requestAuthApi('/oauth2/wechat/scan/mock_confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scene_id: sceneId }),
  }, serverBase)
  return true
}

export interface CaptchaResult {
  is_enabled: boolean
  uuid: string
  image: string
  expire_seconds?: number
}

export interface PasswordLoginParams {
  username: string
  password: string
  uuid?: string
  captcha?: string
}

/**
 * 获取图形验证码 (若系统启用)
 */
export async function fetchCaptcha(serverBase = BACKEND_BASE): Promise<CaptchaResult> {
  const data = await requestAuthApi<CaptchaResult>('/auth/captcha', {}, serverBase)
  if (!data) throw new Error('获取图形验证码失败')
  let image = data.image || ''
  if (image && !image.startsWith('data:image/')) {
    image = `data:image/jpeg;base64,${image}`
  }
  return {
    is_enabled: !!data.is_enabled,
    uuid: data.uuid,
    image,
    expire_seconds: data.expire_seconds,
  }
}

/**
 * 用户账号密码登录
 */
export async function loginWithPassword(
  params: PasswordLoginParams,
  serverBase = BACKEND_BASE
): Promise<{ token: TokenInfo; user: UserInfo }> {
  const data = await requestAuthApi<TokenInfo & { user?: UserInfo }>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  }, serverBase)
  if (!data?.access_token) throw new Error('账号或密码错误')
  const token: TokenInfo = {
    access_token: data.access_token,
    access_token_expire_time: data.access_token_expire_time,
    refresh_token: data.refresh_token,
    session_uuid: data.session_uuid,
    client_type: data.client_type,
  }
  const rawUser = data.user || {}
  const user: UserInfo = {
    id: rawUser.id,
    username: rawUser.username,
    nickname: rawUser.nickname,
    avatar: rawUser.avatar,
    is_vip: rawUser.is_vip,
  }
  return { token, user }
}

/** Popup/网页只发消息，由 background 读取凭据并请求，不在失败后重复直连。 */
export async function fetchCurrentQuota(serverBase = BACKEND_BASE): Promise<QuotaInfo> {
  if (typeof chrome !== 'undefined' && typeof chrome.runtime?.sendMessage === 'function') {
    const response = await sendAuthMessage<{ data: QuotaInfo }>({ type: 'GET_QUOTA' }, '无法确认账户，请重试')
    if (!isQuotaInfo(response.data)) throw new Error('账户服务返回了无效额度，请重试')
    return response.data
  }
  return requestCurrentQuota(serverBase)
}

/** 仅由 background（或无扩展 API 的预览环境）调用。 */
export async function requestCurrentQuota(serverBase = BACKEND_BASE): Promise<QuotaInfo> {
  for (let attempt = 0; attempt < 3; attempt++) {
    const session = await getRequestAuthSession(serverBase)
    const accessToken = session.token?.access_token
    if (accessToken && isTokenExpired(session.token)) {
      await clearAuthSessionIfCurrent(accessToken)
      continue
    }
    const headers: Record<string, string> = {}
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`
    let data: QuotaInfo
    try {
      data = await requestAuthApi('/render-books/public/quota', { headers }, serverBase)
    } catch (error) {
      if (error instanceof AuthApiError && error.unauthorized && accessToken) {
        await clearAuthSessionIfCurrent(accessToken)
        continue
      }
      throw error
    }
    const current = await getAuthSession()
    if (current.token?.access_token !== accessToken || current.quotaRevision !== session.quotaRevision) continue
    if (!isQuotaInfo(data)) {
      throw new Error('账户服务返回了无效额度，请重试')
    }
    if (accessToken && !data.is_logged_in) {
      await clearAuthSessionIfCurrent(accessToken)
      // 清理期间若有新登录，重新确认新账号，不返回旧请求的游客结论。
      if ((await getAuthSession()).token?.access_token) continue
    }
    const quota: QuotaInfo = {
      is_logged_in: data.is_logged_in,
      remaining_quota: data.remaining_quota,
      daily_limit: data.daily_limit,
      used_count: data.used_count,
      user: data.is_logged_in ? data.user || current.user || undefined : undefined,
    }
    const confirmed = await getAuthSession()
    if (confirmed.token?.access_token !== (data.is_logged_in ? accessToken : undefined) ||
        confirmed.quotaRevision !== session.quotaRevision) continue
    try {
      if (!await cacheConfirmedAccount(quota, confirmed, serverBase)) continue
    } catch (error) {
      // 缓存持久化失败不影响已经取得的真实响应。
      console.warn('缓存账户信息失败:', error)
    }
    return quota
  }
  throw new Error('账户发生变化，请重试')
}
