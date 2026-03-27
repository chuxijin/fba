import { getLastPage } from '@/utils'
import { debounce } from '@/utils/debounce'
import { tabBar } from '@/pages.json'

interface ToLoginPageOptions {
  /**
   * 跳转模式, uni.switchTab | uni.reLaunch
   * @default 'switchTab'
   */
  mode?: 'navigateTo' | 'reLaunch' | 'switchTab'
  /**
   * 查询参数
   * @example '?redirect=/pages/home/index'
   */
  queryString?: string
  /**
   * 登录成功后回跳地址
   */
  redirectUrl?: string
  /**
   * 是否自动拉起登录弹窗
   * @default true
   */
  openModal?: boolean
}

const LOGIN_PAGE = '/pages/mine/index'
const LOGIN_REDIRECT_STORAGE_KEY = 'login_redirect_url'
const LOGIN_AUTO_OPEN_STORAGE_KEY = 'login_auto_open'
const TAB_BAR_PAGE_SET = new Set((tabBar?.list || []).map(item => `/${item.pagePath}`))

function normalizeUrl(url?: string | null): string {
  if (!url) {
    return ''
  }

  const text = String(url).trim()
  if (!text) {
    return ''
  }

  return text.startsWith('/') ? text : `/${text}`
}

function buildCurrentPageUrl(): string {
  const currentPage = getLastPage() as any
  if (!currentPage?.route) {
    return ''
  }

  const route = normalizeUrl(currentPage.route)
  const rawOptions = currentPage?.options || currentPage?.$page?.options || {}
  const queryString = Object.entries(rawOptions)
    .filter(([, value]) => value !== undefined && value !== null && String(value).length > 0)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')

  if (!queryString) {
    return route
  }

  return `${route}?${queryString}`
}

function getRedirectPath(url: string): string {
  return normalizeUrl(url.split('?')[0] || '')
}

export function setLoginRedirect(url?: string | null): void {
  const normalizedUrl = normalizeUrl(url)
  if (!normalizedUrl || getRedirectPath(normalizedUrl) === LOGIN_PAGE) {
    uni.removeStorageSync(LOGIN_REDIRECT_STORAGE_KEY)
    return
  }

  uni.setStorageSync(LOGIN_REDIRECT_STORAGE_KEY, normalizedUrl)
}

export function getLoginRedirect(): string {
  return normalizeUrl(uni.getStorageSync(LOGIN_REDIRECT_STORAGE_KEY) || '')
}

export function clearLoginRedirect(): void {
  uni.removeStorageSync(LOGIN_REDIRECT_STORAGE_KEY)
}

export function markLoginAutoOpen(enabled = true): void {
  if (enabled) {
    uni.setStorageSync(LOGIN_AUTO_OPEN_STORAGE_KEY, '1')
    return
  }

  uni.removeStorageSync(LOGIN_AUTO_OPEN_STORAGE_KEY)
}

export function consumeLoginAutoOpen(): boolean {
  const shouldOpen = uni.getStorageSync(LOGIN_AUTO_OPEN_STORAGE_KEY) === '1'
  uni.removeStorageSync(LOGIN_AUTO_OPEN_STORAGE_KEY)
  return shouldOpen
}

export function redirectAfterLogin(): boolean {
  const redirectUrl = getLoginRedirect()
  clearLoginRedirect()

  if (!redirectUrl) {
    return false
  }

  const redirectPath = getRedirectPath(redirectUrl)
  if (!redirectPath || redirectPath === LOGIN_PAGE) {
    return false
  }

  if (TAB_BAR_PAGE_SET.has(redirectPath)) {
    uni.switchTab({ url: redirectPath })
    return true
  }

  uni.navigateTo({ url: redirectUrl })
  return true
}

/**
 * 跳转到登录页, 带防抖处理
 *
 * 如果要立即跳转，不做延时，可以使用 `toLoginPage.flush()` 方法
 */
export const toLoginPage = debounce((options: ToLoginPageOptions = {}) => {
  const {
    mode = 'switchTab',
    queryString = '',
    redirectUrl,
    openModal = true,
  } = options

  const currentPath = buildCurrentPageUrl()
  setLoginRedirect(redirectUrl || currentPath)
  markLoginAutoOpen(openModal)

  if (currentPath === LOGIN_PAGE) {
    return
  }

  if (mode === 'reLaunch') {
    uni.reLaunch({ url: `${LOGIN_PAGE}${queryString}` })
    return
  }

  uni.switchTab({ url: LOGIN_PAGE })
}, 500)
