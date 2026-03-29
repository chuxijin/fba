import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { fbaApi } from '@/api/sdk'
import {
  clearStoredRefreshCookie,
  getStoredRefreshExpiresIn,
  getStoredRefreshToken,
  hasStoredRefreshCookie,
} from '@/utils/auth-cookie'
import { clearCachedStudyPreference } from '@/utils/studyPreferenceCache'
import { isDoubleTokenMode } from '@/utils'
import { useUserStore } from './user'

export interface IAuthLoginRes {
  token?: string
  accessToken?: string
  expiresIn?: number
  accessExpiresIn?: number
  refreshToken?: string
  refreshExpiresIn?: number
}

export function isSingleTokenRes(val: any): val is { token: string, expiresIn: number } {
  return val && 'token' in val
}

export function isDoubleTokenRes(val: any): val is {
  accessToken: string
  accessExpiresIn: number
  refreshToken: string
  refreshExpiresIn: number
} {
  return val && 'accessToken' in val
}

function getExpireSeconds(expireTime?: string | null, fallbackSeconds = 0): number {
  if (!expireTime) {
    return fallbackSeconds
  }

  const timestamp = Date.parse(expireTime)
  if (!Number.isFinite(timestamp)) {
    return fallbackSeconds
  }

  return Math.max(1, Math.ceil((timestamp - Date.now()) / 1000))
}

function buildDoubleTokenInfo(res: any): IAuthLoginRes {
  return {
    accessToken: res?.access_token || '',
    accessExpiresIn: getExpireSeconds(res?.access_token_expire_time, 7200),
    refreshToken: getStoredRefreshToken(),
    refreshExpiresIn: getStoredRefreshExpiresIn(),
  }
}

function getWxCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    uni.login({
      provider: 'weixin',
      success: res => resolve(res.code),
      fail: reject,
    })
  })
}

const tokenInfoState: IAuthLoginRes = isDoubleTokenMode
  ? {
      accessToken: '',
      accessExpiresIn: 0,
      refreshToken: '',
      refreshExpiresIn: 0,
    }
  : {
      token: '',
      expiresIn: 0,
    }

export const useTokenStore = defineStore(
  'token',
  () => {
    const tokenInfo = ref<IAuthLoginRes>({ ...tokenInfoState })
    const nowTime = ref(Date.now())

    const updateNowTime = () => {
      nowTime.value = Date.now()
      return useTokenStore()
    }

    const setTokenInfo = (val: IAuthLoginRes) => {
      updateNowTime()
      tokenInfo.value = val

      const now = Date.now()
      if (isSingleTokenRes(val)) {
        uni.setStorageSync('accessTokenExpireTime', now + val.expiresIn * 1000)
        uni.removeStorageSync('refreshTokenExpireTime')
        uni.setStorageSync('access_token', val.token || '')
        uni.removeStorageSync('refresh_token')
        return
      }

      if (isDoubleTokenRes(val)) {
        uni.setStorageSync('accessTokenExpireTime', now + val.accessExpiresIn * 1000)

        if (val.refreshExpiresIn > 0) {
          uni.setStorageSync('refreshTokenExpireTime', now + val.refreshExpiresIn * 1000)
        }
        else {
          uni.removeStorageSync('refreshTokenExpireTime')
        }

        uni.setStorageSync('access_token', val.accessToken || '')

        if (val.refreshToken) {
          uni.setStorageSync('refresh_token', val.refreshToken)
        }
        else {
          uni.removeStorageSync('refresh_token')
        }
      }
    }

    const isTokenExpired = computed(() => {
      const expireTime = Number(uni.getStorageSync('accessTokenExpireTime') || 0)
      if (!expireTime) {
        return true
      }

      return nowTime.value >= expireTime
    })

    const isRefreshTokenExpired = computed(() => {
      if (!isDoubleTokenMode) {
        return true
      }

      const refreshExpireTime = Number(uni.getStorageSync('refreshTokenExpireTime') || 0)
      if (!refreshExpireTime) {
        return true
      }

      return nowTime.value >= refreshExpireTime
    })

    async function finishLogin(authInfo: IAuthLoginRes) {
      setTokenInfo(authInfo)

      const userStore = useUserStore()
      try {
        await userStore.fetchUserInfo()
      }
      catch (error) {
        await logout()
        throw error
      }
    }

    const login = async (loginForm: any) => {
      try {
        const res = await fbaApi.admin.auth.login(loginForm)
        const authInfo: IAuthLoginRes = isDoubleTokenMode
          ? buildDoubleTokenInfo(res)
          : {
              token: (res as any).access_token || '',
              expiresIn: getExpireSeconds((res as any).access_token_expire_time, 7200),
            }

        await finishLogin(authInfo)
        uni.showToast({
          title: '登录成功',
          icon: 'success',
        })
        return res
      }
      catch (error) {
        console.error('登录失败:', error)
        uni.showToast({
          title: '登录失败，请重试',
          icon: 'error',
        })
        throw error
      }
      finally {
        updateNowTime()
      }
    }

    const wxLogin = async (userInfo?: { nickname?: string, avatar?: string }) => {
      try {
        const code = await getWxCode()
        const res = await fbaApi.qbank.auth.wxLogin({
          code,
          platform: 'miniapp',
          ...userInfo,
        })

        const authInfo: IAuthLoginRes = isDoubleTokenMode
          ? buildDoubleTokenInfo(res)
          : {
              token: (res as any).access_token || '',
              expiresIn: getExpireSeconds((res as any).access_token_expire_time, 7200),
            }

        await finishLogin(authInfo)
        uni.showToast({
          title: '登录成功',
          icon: 'success',
        })
        return res
      }
      catch (error) {
        console.error('微信登录失败:', error)
        uni.showToast({
          title: '微信登录失败，请重试',
          icon: 'error',
        })
        throw error
      }
      finally {
        updateNowTime()
      }
    }

    const orderLogin = async (orderInput: string) => {
      try {
        const res = await fbaApi.client.post('/actcode/agiso/login', {
          order_input: orderInput,
        })

        const authInfo: IAuthLoginRes = isDoubleTokenMode
          ? buildDoubleTokenInfo(res)
          : {
              token: (res as any).access_token || '',
              expiresIn: getExpireSeconds((res as any).access_token_expire_time, 7200),
            }

        await finishLogin(authInfo)
        uni.showToast({
          title: '登录成功',
          icon: 'success',
        })
        return res
      }
      catch (error) {
        console.error('订单号登录失败:', error)
        throw error
      }
      finally {
        updateNowTime()
      }
    }

    const logout = async () => {
      const userStore = useUserStore()
      const userId = Number(userStore.userInfo?.id || 0)

      try {
        await fbaApi.admin.auth.logout()
      }
      catch (error) {
        console.error('退出登录失败:', error)
      }
      finally {
        updateNowTime()
        tokenInfo.value = { ...tokenInfoState }

        uni.removeStorageSync('token')
        uni.removeStorageSync('access_token')
        uni.removeStorageSync('refresh_token')
        uni.removeStorageSync('accessTokenExpireTime')
        uni.removeStorageSync('refreshTokenExpireTime')

        clearStoredRefreshCookie()
        clearCachedStudyPreference(userId)
        userStore.clearUserInfo()
      }
    }

    const refreshToken = async () => {
      if (!isDoubleTokenMode) {
        throw new Error('单 token 模式不支持刷新 token')
      }

      try {
        if (!hasStoredRefreshCookie()) {
          throw new Error('无效的 refresh token')
        }

        const res = await fbaApi.admin.auth.refresh()
        setTokenInfo(buildDoubleTokenInfo(res))
        return res
      }
      catch (error) {
        console.error('刷新 token 失败:', error)
        throw error
      }
      finally {
        updateNowTime()
      }
    }

    const getValidToken = computed(() => {
      if (isTokenExpired.value) {
        return ''
      }

      const storedAccessToken = uni.getStorageSync('access_token') || ''
      if (!isDoubleTokenMode) {
        if (isSingleTokenRes(tokenInfo.value)) {
          return tokenInfo.value.token || storedAccessToken
        }
        return storedAccessToken
      }

      if (isDoubleTokenRes(tokenInfo.value)) {
        return tokenInfo.value.accessToken || storedAccessToken
      }

      return storedAccessToken
    })

    const hasLoginInfo = computed(() => {
      const storedAccessToken = uni.getStorageSync('access_token') || ''
      if (isDoubleTokenMode) {
        const currentAccessToken = isDoubleTokenRes(tokenInfo.value)
          ? tokenInfo.value.accessToken || ''
          : ''
        const currentRefreshToken = isDoubleTokenRes(tokenInfo.value)
          ? tokenInfo.value.refreshToken || ''
          : ''

        return Boolean(currentAccessToken || storedAccessToken || currentRefreshToken || getStoredRefreshToken())
      }

      if (isSingleTokenRes(tokenInfo.value)) {
        return Boolean(tokenInfo.value.token) || Boolean(storedAccessToken)
      }

      return Boolean(storedAccessToken)
    })

    const hasValidLogin = computed(() => {
      const canRefreshSession = isDoubleTokenMode && hasStoredRefreshCookie() && !isRefreshTokenExpired.value
      return hasLoginInfo.value && (!isTokenExpired.value || canRefreshSession)
    })

    const tryGetValidToken = async (): Promise<string> => {
      updateNowTime()

      if (!getValidToken.value && isDoubleTokenMode && !isRefreshTokenExpired.value) {
        try {
          await refreshToken()
          return getValidToken.value
        }
        catch (error) {
          console.error('尝试刷新 token 失败:', error)
          return ''
        }
      }

      return getValidToken.value
    }

    return {
      login,
      wxLogin,
      orderLogin,
      logout,
      hasLogin: hasValidLogin,
      refreshToken,
      tryGetValidToken,
      validToken: getValidToken,
      tokenInfo,
      setTokenInfo,
      updateNowTime,
    }
  },
  {
    persist: true,
  },
)
