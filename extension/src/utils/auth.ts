/**
 * 用户认证与 Token 存储管理模块
 * 支持与后端微信小程序扫码登录闭环对接，Token 持久化存储于 chrome.storage.local
 */

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

export interface ScanQrcodeResult {
  scene_id: string
  qrcode_data_url: string
  expires_in: number
}

const STORAGE_KEY_TOKEN = 'fba_auth_token'
const STORAGE_KEY_USER = 'fba_auth_user'

/**
 * 获取本地存储的 Token 信息
 */
export async function getStoredToken(): Promise<TokenInfo | null> {
  try {
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      const res = await chrome.storage.local.get([STORAGE_KEY_TOKEN])
      return res[STORAGE_KEY_TOKEN] || null
    }
    const raw = localStorage.getItem(STORAGE_KEY_TOKEN)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    console.warn('读取本地 Token 失败:', e)
    return null
  }
}

/**
 * 获取本地存储的用户信息
 */
export async function getStoredUser(): Promise<UserInfo | null> {
  try {
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      const res = await chrome.storage.local.get([STORAGE_KEY_USER])
      return res[STORAGE_KEY_USER] || null
    }
    const raw = localStorage.getItem(STORAGE_KEY_USER)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    console.warn('读取本地用户信息失败:', e)
    return null
  }
}

/**
 * 保存登录成功后的凭据与用户信息
 */
export async function saveAuthSession(token: TokenInfo, user?: UserInfo): Promise<void> {
  try {
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      await chrome.storage.local.set({
        [STORAGE_KEY_TOKEN]: token,
        [STORAGE_KEY_USER]: user || {},
      })
    } else {
      localStorage.setItem(STORAGE_KEY_TOKEN, JSON.stringify(token))
      if (user) localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user))
    }
  } catch (e) {
    console.error('保存登录凭据失败:', e)
  }
}

/**
 * 清除登录凭据（登出）
 */
export async function clearAuthSession(): Promise<void> {
  try {
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      await chrome.storage.local.remove([STORAGE_KEY_TOKEN, STORAGE_KEY_USER])
    } else {
      localStorage.removeItem(STORAGE_KEY_TOKEN)
      localStorage.removeItem(STORAGE_KEY_USER)
    }
  } catch (e) {
    console.error('清除登录凭据失败:', e)
  }
}

/**
 * 请求后端生成小程序登录二维码
 */
export async function fetchScanQrcode(serverBase: string = 'http://127.0.0.1:8000'): Promise<ScanQrcodeResult> {
  const url = `${serverBase.replace(/\/+$/, '')}/api/v1/oauth2/wechat/scan/qrcode`
  const res = await fetch(url)
  const json = await res.json()
  if (json.code !== 200 || !json.data?.scene_id) {
    throw new Error(json.msg || '获取微信扫码登录二维码失败')
  }
  return json.data
}

/**
 * 轮询检查扫码登录状态
 */
export async function pollScanStatus(
  sceneId: string,
  serverBase: string = 'http://127.0.0.1:8000'
): Promise<{ status: 'PENDING' | 'CONFIRMED' | 'EXPIRED'; token?: TokenInfo; user?: UserInfo; msg?: string }> {
  const url = `${serverBase.replace(/\/+$/, '')}/api/v1/oauth2/wechat/scan/status?scene_id=${encodeURIComponent(sceneId)}`
  const res = await fetch(url)
  const json = await res.json()
  if (json.code !== 200) {
    return { status: 'EXPIRED', msg: json.msg || '轮询状态异常' }
  }
  return json.data
}

/**
 * 模拟手机确认扫码（开发与测试环境专属）
 */
export async function mockConfirmScan(
  sceneId: string,
  serverBase: string = 'http://127.0.0.1:8000'
): Promise<boolean> {
  const url = `${serverBase.replace(/\/+$/, '')}/api/v1/oauth2/wechat/scan/mock_confirm`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scene_id: sceneId }),
  })
  const json = await res.json()
  return json.code === 200
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
export async function fetchCaptcha(serverBase: string = 'http://127.0.0.1:8000'): Promise<CaptchaResult> {
  const url = `${serverBase.replace(/\/+$/, '')}/api/v1/auth/captcha`
  const res = await fetch(url)
  const json = await res.json()
  if (json.code !== 200 || !json.data) {
    throw new Error(json.msg || '获取图形验证码失败')
  }
  const data = json.data
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
  serverBase: string = 'http://127.0.0.1:8000'
): Promise<{ token: TokenInfo; user: UserInfo }> {
  const url = `${serverBase.replace(/\/+$/, '')}/api/v1/auth/login`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  const json = await res.json()
  if (json.code !== 200 || !json.data?.access_token) {
    throw new Error(json.msg || '账号或密码错误')
  }
  const token: TokenInfo = {
    access_token: json.data.access_token,
    access_token_expire_time: json.data.access_token_expire_time,
  }
  const rawUser = json.data.user || {}
  const user: UserInfo = {
    id: rawUser.id,
    username: rawUser.username,
    nickname: rawUser.nickname,
    avatar: rawUser.avatar,
    is_vip: rawUser.is_vip,
  }
  return { token, user }
}

export interface QuotaInfo {
  is_logged_in: boolean
  remaining_quota: number
  daily_limit: number
  used_count: number
  user?: UserInfo
}

/**
 * 统一获取当前环境的可用额度（自动结合已存储的 Token 或游客 IP 限额）
 */
export async function fetchCurrentQuota(serverBase: string = 'http://127.0.0.1:8000'): Promise<QuotaInfo> {
  const token = await getStoredToken()
  const user = await getStoredUser()

  // 1. 在 Chrome 扩展环境中，优先通过 background 转发，规避网页 CSP/CORS 限制
  if (typeof chrome !== 'undefined' && chrome.runtime?.sendMessage) {
    try {
      const bgRes = await new Promise<any>((resolve) => {
        chrome.runtime.sendMessage({ type: 'GET_QUOTA' }, (resp) => {
          if (chrome.runtime.lastError || !resp?.success) {
            resolve(null)
          } else {
            resolve(resp.data)
          }
        })
      })

      if (bgRes) {
        return {
          is_logged_in: Boolean(token?.access_token || bgRes.is_logged_in),
          remaining_quota: typeof bgRes.remaining_quota === 'number' ? bgRes.remaining_quota : 5,
          daily_limit: typeof bgRes.daily_limit === 'number' ? bgRes.daily_limit : 5,
          used_count: typeof bgRes.used_count === 'number' ? bgRes.used_count : 0,
          user: user || undefined,
        }
      }
    } catch {
      // 忽略 background 通信异常，fallback 到直接 fetch
    }
  }

  const headers: Record<string, string> = {}
  if (token?.access_token) {
    headers['Authorization'] = `Bearer ${token.access_token}`
  }

  try {
    const url = `${serverBase.replace(/\/+$/, '')}/api/v1/render-books/public/quota`
    const res = await fetch(url, { headers })
    const json = await res.json()

    if (json.code === 200 && json.data) {
      const data = json.data
      return {
        is_logged_in: Boolean(token?.access_token || data.is_logged_in),
        remaining_quota: typeof data.remaining_quota === 'number' ? data.remaining_quota : 5,
        daily_limit: typeof data.daily_limit === 'number' ? data.daily_limit : 5,
        used_count: typeof data.used_count === 'number' ? data.used_count : 0,
        user: user || undefined,
      }
    }
  } catch (e) {
    console.warn('获取额度失败:', e)
  }

  return {
    is_logged_in: Boolean(token?.access_token),
    remaining_quota: 5,
    daily_limit: 5,
    used_count: 0,
    user: user || undefined,
  }
}


