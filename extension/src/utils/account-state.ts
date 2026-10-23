import {
  fetchCurrentQuota, getAuthSession, getTokenExpiry, readCachedAccount, QuotaInfo,
  STORAGE_KEY_TOKEN, STORAGE_KEY_USER, STORAGE_KEY_QUOTA_REVISION,
} from './auth'
import { AUTH_RECHECK_INTERVAL, BACKEND_BASE } from './auth-protocol'

export type AccountState =
  | { status: 'loading' }
  | { status: 'ready'; quota: QuotaInfo; refreshing?: boolean; refreshError?: string }
  | { status: 'error'; message: string }

// 本地已确认身份先显示；网络刷新额度，storage 变化同步所有可见视图。
export function createAccountStore(serverBase = BACKEND_BASE) {
  let state: AccountState = { status: 'loading' }
  let generation = 0
  let pending: Promise<void> | null = null
  let expiryTimer: ReturnType<typeof setTimeout> | null = null
  let recheckTimer: ReturnType<typeof setInterval> | null = null
  let lastRefresh = 0
  const listeners = new Set<(state: AccountState) => void>()

  function publish(next: AccountState) {
    state = next
    listeners.forEach((listener) => listener(state))
  }

  function invalidate() {
    generation++
    pending = null
    if (expiryTimer) clearTimeout(expiryTimer)
    expiryTimer = null
    publish({ status: 'loading' })
  }

  function scheduleExpiry(quota: QuotaInfo, token: Awaited<ReturnType<typeof getAuthSession>>['token']) {
    if (expiryTimer) clearTimeout(expiryTimer)
    expiryTimer = null
    const expiry = quota.is_logged_in ? getTokenExpiry(token) : null
    if (expiry !== null && listeners.size) {
      expiryTimer = setTimeout(() => {
        invalidate()
        void refresh()
      }, Math.min(Math.max(0, expiry - Date.now()), 2147483647))
    }
  }

  function refresh(): Promise<void> {
    if (pending) return pending
    lastRefresh = Date.now()
    const version = generation
    publish(state.status === 'ready' ? { status: 'ready', quota: state.quota, refreshing: true } : { status: 'loading' })
    const task = (async () => {
      let settled = false
      // 本地读取与网络确认同时开始，不等待 Service Worker 唤醒或服务器响应。
      const hydrate = readCachedAccount(serverBase).then((cached) => {
        if (!cached || settled || version !== generation) return
        publish({ status: 'ready', quota: cached.quota, refreshing: true })
        scheduleExpiry(cached.quota, cached.token)
      }).catch(() => {})
      try {
        const quota = await fetchCurrentQuota(serverBase)
        const session = await getAuthSession()
        if (version !== generation) return
        settled = true
        publish({ status: 'ready', quota })
        scheduleExpiry(quota, session.token)
      } catch (error) {
        await hydrate
        settled = true
        if (version === generation) {
          const message = error instanceof Error ? error.message : '无法确认账户，请重试'
          if (state.status === 'ready') {
            publish({ status: 'ready', quota: state.quota, refreshError: message })
          } else {
            publish({ status: 'error', message })
          }
        }
      }
    })()
    pending = task
    void task.finally(() => { if (pending === task) pending = null })
    return task
  }

  function onStorageChange(changes: Record<string, chrome.storage.StorageChange>, area: string) {
    if (area !== 'local' || ![STORAGE_KEY_TOKEN, STORAGE_KEY_USER, STORAGE_KEY_QUOTA_REVISION]
      .some((key) => key in changes)) return
    if (STORAGE_KEY_TOKEN in changes || STORAGE_KEY_USER in changes) {
      invalidate()
    } else {
      generation++
      pending = null
    }
    if (listeners.size) void refresh()
  }

  function subscribe(listener: (state: AccountState) => void): () => void {
    if (!listeners.size) {
      if (typeof chrome !== 'undefined') chrome.storage?.onChanged?.addListener(onStorageChange)
      if (typeof window !== 'undefined') {
        window.addEventListener('focus', onFocus)
        document.addEventListener('visibilitychange', onFocus)
        recheckTimer = setInterval(onFocus, AUTH_RECHECK_INTERVAL)
      }
    }
    listeners.add(listener)
    listener(state)
    return () => {
      listeners.delete(listener)
      if (!listeners.size) {
        if (typeof chrome !== 'undefined') chrome.storage?.onChanged?.removeListener(onStorageChange)
        if (typeof window !== 'undefined') {
          window.removeEventListener('focus', onFocus)
          document.removeEventListener('visibilitychange', onFocus)
        }
        if (recheckTimer) clearInterval(recheckTimer)
        recheckTimer = null
        invalidate()
      }
    }
  }

  function onFocus() {
    if (!document.hidden && Date.now() - lastRefresh > 1000) void refresh()
  }

  return { refresh, subscribe }
}

export const accountStore = createAccountStore()
