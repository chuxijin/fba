const REFRESH_COOKIE_NAME = 'fba_refresh_token'
const REFRESH_COOKIE_STORAGE_KEY = 'auth_refresh_cookie'
const REFRESH_COOKIE_EXPIRE_STORAGE_KEY = 'auth_refresh_cookie_expire_time'

type CookieHeaderValue = string | string[] | undefined

function normalizeCookieHeaderValue(value: CookieHeaderValue): string[] {
  if (!value) {
    return []
  }

  if (Array.isArray(value)) {
    return value.filter(Boolean)
  }

  return value
    .split('\n')
    .map(item => item.trim())
    .filter(Boolean)
}

function getHeaderValue(headers: Record<string, any> | undefined, key: string) {
  if (!headers) {
    return undefined
  }

  const matchedKey = Object.keys(headers).find(headerKey => headerKey.toLowerCase() === key.toLowerCase())
  return matchedKey ? headers[matchedKey] : undefined
}

function parseExpireTime(setCookie: string) {
  const segments = setCookie.split(';').map(item => item.trim()).filter(Boolean)
  const attributes = new Map<string, string>()

  for (const segment of segments.slice(1)) {
    const [rawKey, ...rest] = segment.split('=')
    const key = rawKey.trim().toLowerCase()
    const value = rest.join('=').trim()
    attributes.set(key, value)
  }

  const maxAge = Number(attributes.get('max-age') || '')
  if (Number.isFinite(maxAge)) {
    return maxAge <= 0 ? 0 : Date.now() + maxAge * 1000
  }

  const expires = attributes.get('expires')
  if (!expires) {
    return 0
  }

  const timestamp = Date.parse(expires)
  return Number.isFinite(timestamp) ? timestamp : 0
}

function parseRefreshCookie(setCookie: string) {
  const firstSegment = setCookie.split(';')[0]?.trim()
  if (!firstSegment) {
    return null
  }

  const separatorIndex = firstSegment.indexOf('=')
  if (separatorIndex <= 0) {
    return null
  }

  const name = firstSegment.slice(0, separatorIndex).trim()
  const value = firstSegment.slice(separatorIndex + 1).trim()

  if (name !== REFRESH_COOKIE_NAME) {
    return null
  }

  return {
    name,
    value,
    cookie: `${name}=${value}`,
    expireTime: parseExpireTime(setCookie),
  }
}

function getResponseCookieCandidates(response: any) {
  const cookies = normalizeCookieHeaderValue(response?.cookies)
  const headerCookies = normalizeCookieHeaderValue(
    getHeaderValue(response?.header, 'set-cookie') || getHeaderValue(response?.header, 'Set-Cookie'),
  )
  return [...cookies, ...headerCookies]
}

export function getStoredRefreshCookie() {
  return uni.getStorageSync(REFRESH_COOKIE_STORAGE_KEY) || ''
}

export function getStoredRefreshToken() {
  const cookie = getStoredRefreshCookie()
  if (!cookie) {
    return ''
  }

  const separatorIndex = cookie.indexOf('=')
  if (separatorIndex <= 0) {
    return ''
  }

  return cookie.slice(separatorIndex + 1)
}

export function getStoredRefreshExpireTime() {
  const expireTime = Number(uni.getStorageSync(REFRESH_COOKIE_EXPIRE_STORAGE_KEY) || 0)
  return Number.isFinite(expireTime) ? expireTime : 0
}

export function getStoredRefreshExpiresIn() {
  const expireTime = getStoredRefreshExpireTime()
  if (!expireTime) {
    return 0
  }

  return Math.max(0, Math.ceil((expireTime - Date.now()) / 1000))
}

export function hasStoredRefreshCookie() {
  return !!getStoredRefreshCookie()
}

export function clearStoredRefreshCookie() {
  uni.removeStorageSync(REFRESH_COOKIE_STORAGE_KEY)
  uni.removeStorageSync(REFRESH_COOKIE_EXPIRE_STORAGE_KEY)
}

export function saveRefreshCookie(setCookie: string) {
  const parsedCookie = parseRefreshCookie(setCookie)
  if (!parsedCookie) {
    return false
  }

  if (!parsedCookie.value || parsedCookie.expireTime === 0) {
    clearStoredRefreshCookie()
    return true
  }

  uni.setStorageSync(REFRESH_COOKIE_STORAGE_KEY, parsedCookie.cookie)
  uni.setStorageSync(REFRESH_COOKIE_EXPIRE_STORAGE_KEY, parsedCookie.expireTime)
  return true
}

export function syncRefreshCookieFromResponse(response: any) {
  const candidates = getResponseCookieCandidates(response)
  let handled = false

  for (const cookie of candidates) {
    handled = saveRefreshCookie(cookie) || handled
  }

  return handled
}

export function applyRefreshCookieHeader(header?: Record<string, any>) {
  const nextHeader = { ...(header || {}) }
  const refreshCookie = getStoredRefreshCookie()
  if (!refreshCookie) {
    return nextHeader
  }

  const currentCookie = String(getHeaderValue(nextHeader, 'Cookie') || '')
  if (!currentCookie.includes(`${REFRESH_COOKIE_NAME}=`)) {
    nextHeader.Cookie = currentCookie ? `${currentCookie}; ${refreshCookie}` : refreshCookie
  }

  return nextHeader
}
