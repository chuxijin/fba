/** 官网、content script 和后台共用的认证契约，不依赖存储或网络。 */
export const BACKEND_BASE = 'http://127.0.0.1:8000'
export const LOCAL_SITE_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']
export const SITE_URL_PATTERNS = LOCAL_SITE_ORIGINS.map((origin) => {
  const { protocol, hostname } = new URL(origin)
  return `${protocol}//${hostname}/*`
})
export const SITE_AUTH_CHANNEL = 'fba-site-auth-v1'
export const AUTH_BRIDGE_VERSION = 3
export const AUTH_REQUEST_TIMEOUT = 10000
export const AUTH_MESSAGE_TIMEOUT = 30000
export const AUTH_RECHECK_INTERVAL = 60000

export interface UserInfo {
  id?: number | string
  username?: string
  nickname?: string
  avatar?: string
  is_vip?: boolean
  quota?: number
}

export interface TokenInfo {
  access_token: string
  access_token_expire_time?: string
  refresh_token?: string
  refresh_token_expire_time?: string
  token_type?: string
}

export interface QuotaInfo {
  is_logged_in: boolean
  remaining_quota: number
  daily_limit: number
  used_count: number
  user?: UserInfo
}

export type SiteAuthMessage =
  | { type: 'SITE_AUTH_GET' }
  | { type: 'SITE_AUTH_LOGIN'; accessToken: string }
  | { type: 'SITE_AUTH_LOGOUT'; expectedToken?: string }

export function isAccessToken(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= 16384
}

export function readSiteToken(cookies: string): string | null {
  const raw = cookies.split(';').map((cookie) => cookie.trim()).find((cookie) => cookie.startsWith('web_token='))
  if (!raw) return null
  try {
    const value = decodeURIComponent(raw.slice('web_token='.length))
    const token = value.startsWith('"') ? JSON.parse(value) : value
    return isAccessToken(token) ? token : null
  } catch { return null }
}

export function isSiteAuthMessage(value: unknown): value is SiteAuthMessage {
  if (!value || typeof value !== 'object') return false
  const message = value as Record<string, unknown>
  return message.type === 'SITE_AUTH_GET' ||
    (message.type === 'SITE_AUTH_LOGIN' && isAccessToken(message.accessToken)) ||
    (message.type === 'SITE_AUTH_LOGOUT' && (message.expectedToken === undefined || isAccessToken(message.expectedToken)))
}

export function isTrustedSite(url?: string): boolean {
  try { return !!url && LOCAL_SITE_ORIGINS.includes(new URL(url).origin) } catch { return false }
}

export function isQuotaInfo(value: unknown): value is QuotaInfo {
  if (!value || typeof value !== 'object') return false
  const data = value as Record<string, unknown>
  return typeof data.is_logged_in === 'boolean' &&
    [data.remaining_quota, data.daily_limit, data.used_count].every((count) =>
      typeof count === 'number' && Number.isFinite(count) && count >= 0)
}

/** JWT exp 优先；只接受携带时区的旧版有效期字段。 */
export function getTokenExpiry(token: TokenInfo | null): number | null {
  if (!token?.access_token) return null
  try {
    const part = token.access_token.split('.')[1]!.replace(/-/g, '+').replace(/_/g, '/')
    const { exp } = JSON.parse(atob(part))
    if (typeof exp === 'number' && Number.isFinite(exp * 1000)) return exp * 1000
  } catch { /* 兼容旧凭据 */ }
  const expiry = token.access_token_expire_time
  if (!expiry || !/(Z|[+-]\d{2}:?\d{2})$/i.test(expiry)) return null
  const parsed = Date.parse(expiry)
  return Number.isFinite(parsed) ? parsed : null
}

export function isTokenExpired(token: TokenInfo | null, now = Date.now()): boolean {
  const expiry = getTokenExpiry(token)
  return expiry !== null && expiry <= now
}

export async function withTimeout<T>(task: Promise<T>, timeout: number, message: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    return await Promise.race([task, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error(message)), timeout)
    })])
  } finally { clearTimeout(timer) }
}
