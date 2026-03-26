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
export function isDoubleTokenRes(val: any): val is { accessToken: string, accessExpiresIn: number, refreshToken: string, refreshExpiresIn: number } {
  return val && 'accessToken' in val
}

function getExpireSeconds(expireTime?: string | null, fallbackSeconds = 0) {
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

function getWxCode() {
  return new Promise<string>((resolve, reject) => {
    uni.login({
      provider: 'weixin',
      success: res => resolve(res.code),
      fail: reject,
    })
  })
}

// 初始化状态
const tokenInfoState = isDoubleTokenMode
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
    // 定义用户信息
    const tokenInfo = ref<IAuthLoginRes>({ ...tokenInfoState })

    // 添加一个时间戳 ref 作为响应式依赖
    const nowTime = ref(Date.now())
    /**
     * 更新响应式数据:now
     * 确保isTokenExpired/isRefreshTokenExpired重新计算,而不是用错误过期缓存值
     * 可useTokenStore内部适时调用;也可链式调用:tokenStore.updateNowTime().hasLogin
     * @returns 最新的tokenStore实例
     */
    const updateNowTime = () => {
      nowTime.value = Date.now()
      return useTokenStore()
    }

    // 设置用户信息
    const setTokenInfo = (val: IAuthLoginRes) => {
      updateNowTime()
      tokenInfo.value = val

      // 计算并存储过期时间
      const now = Date.now()
      if (isSingleTokenRes(val)) {
        // 单token模式
        const expireTime = now + val.expiresIn * 1000
        uni.setStorageSync('accessTokenExpireTime', expireTime)
        uni.setStorageSync('access_token', val.token || '')
        uni.removeStorageSync('refresh_token')
      }
      else if (isDoubleTokenRes(val)) {
        // 双token模式
        const accessExpireTime = now + val.accessExpiresIn * 1000
        const refreshExpireTime = val.refreshExpiresIn > 0 ? now + val.refreshExpiresIn * 1000 : 0
        uni.setStorageSync('accessTokenExpireTime', accessExpireTime)
        if (refreshExpireTime > 0) {
          uni.setStorageSync('refreshTokenExpireTime', refreshExpireTime)
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

    /**
     * 判断token是否过期
     */
    const isTokenExpired = computed(() => {
      if (!tokenInfo.value) {
        return true
      }

      const now = nowTime.value
      const expireTime = uni.getStorageSync('accessTokenExpireTime')

      if (!expireTime)
        return true
      return now >= expireTime
    })

    /**
     * 判断refreshToken是否过期
     */
    const isRefreshTokenExpired = computed(() => {
      if (!isDoubleTokenMode)
        return true

      const now = nowTime.value
      const refreshExpireTime = uni.getStorageSync('refreshTokenExpireTime')

      if (!refreshExpireTime)
        return true
      return now >= refreshExpireTime
    })

    /**
     * 登录成功后处理逻辑
     * @param tokenInfo 登录返回的token信息
     */
    async function _postLogin(tokenInfo: IAuthLoginRes, loginUser?: any) {
      setTokenInfo(tokenInfo)
      const userStore = useUserStore()
      if (loginUser) {
        userStore.setUserInfo(loginUser)
        return
      }
      await userStore.fetchUserInfo()
    }

    /**
     * 用户登录
     * 有的时候后端会用一个接口返回token和用户信息，有的时候会分开2个接口，一个获取token，一个获取用户信息
     * （各有利弊，看业务场景和系统复杂度），这里使用2个接口返回的来模拟
     * @param loginForm 登录参数
     * @returns 登录结果
     */
    const login = async (loginForm: any) => {
      try {
        const res = await fbaApi.qbank.auth.testLogin(loginForm)
        console.log('普通登录-res: ', res)

        const tokenRes: IAuthLoginRes = isDoubleTokenMode
          ? buildDoubleTokenInfo(res)
          : {
              token: (res as any).access_token || '',
              expiresIn: getExpireSeconds((res as any).access_token_expire_time, 7200),
            }
        await _postLogin(tokenRes, (res as any).user)
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

    /**
     * 微信登录
     * 有的时候后端会用一个接口返回token和用户信息，有的时候会分开2个接口，一个获取token，一个获取用户信息
     * （各有利弊，看业务场景和系统复杂度），这里使用2个接口返回的来模拟
     * @returns 登录结果
     */
    const wxLogin = async (userInfo?: { nickname?: string, avatar?: string }) => {
      try {
        // 获取微信小程序登录的code
        const code = await getWxCode()
        console.log('微信登录-code: ', code)
        const res = await fbaApi.qbank.auth.wxLogin({ code, platform: 'miniapp', ...userInfo })
        console.log('微信登录-res: ', res)

        const tokenRes: IAuthLoginRes = isDoubleTokenMode
          ? buildDoubleTokenInfo(res)
          : {
              token: (res as any).access_token || '',
              expiresIn: getExpireSeconds((res as any).access_token_expire_time, 7200),
            }
        await _postLogin(tokenRes, (res as any).user)
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

    /**
     * 退出登录 并 删除用户信息
     */
    const logout = async () => {
      try {
        // TODO 实现自己的退出登录逻辑
        // 暂无实际服务端 logout API, 如有请替换下方逻辑
        // await fbaApi.qbank.auth.logout()
      }
      catch (error) {
        console.error('退出登录失败:', error)
      }
      finally {
        updateNowTime()
        const userStore = useUserStore()
        const userId = Number(userStore.userInfo?.userId || 0)

        // 无论成功失败，都需要清除本地token信息
        // 清除存储的过期时间
        uni.removeStorageSync('accessTokenExpireTime')
        uni.removeStorageSync('refreshTokenExpireTime')
        console.log('退出登录-清除用户信息')
        tokenInfo.value = { ...tokenInfoState }
        uni.removeStorageSync('token')
        uni.removeStorageSync('access_token')
        uni.removeStorageSync('refresh_token')
        clearStoredRefreshCookie()
        clearCachedStudyPreference(userId)
        userStore.clearUserInfo()
      }
    }

    /**
     * 刷新token
     * @returns 刷新结果
     */
    const refreshToken = async () => {
      if (!isDoubleTokenMode) {
        console.error('单token模式不支持刷新token')
        throw new Error('单token模式不支持刷新token')
      }

      try {
        if (!hasStoredRefreshCookie()) {
          throw new Error('无效的refreshToken')
        }

        const res = await fbaApi.admin.auth.refresh()
        console.log('刷新token-res: ', res)
        setTokenInfo(buildDoubleTokenInfo(res))
        return res
      }
      catch (error) {
        console.error('刷新token失败:', error)
        throw error
      }
      finally {
        updateNowTime()
      }
    }

    /**
     * 获取有效的token
     * 注意：在computed中不直接调用异步函数，只做状态判断
     * 实际的刷新操作应由调用方处理
     * 建议这样使用 tokenStore.updateNowTime().validToken
     */
    const getValidToken = computed(() => {
      // token已过期，返回空
      if (isTokenExpired.value) {
        return ''
      }

      if (!isDoubleTokenMode) {
        return isSingleTokenRes(tokenInfo.value) ? tokenInfo.value.token : ''
      }
      else {
        return isDoubleTokenRes(tokenInfo.value) ? tokenInfo.value.accessToken : ''
      }
    })

    /**
     * 检查是否有登录信息（不考虑token是否过期）
     */
    const hasLoginInfo = computed(() => {
      if (!tokenInfo.value) {
        return false
      }
      if (isDoubleTokenMode) {
        return !!uni.getStorageSync('access_token') || hasStoredRefreshCookie()
      }
      else {
        return isSingleTokenRes(tokenInfo.value) && !!tokenInfo.value.token
      }
    })

    /**
     * 检查是否已登录且token有效
     * 建议这样使用tokenStore.updateNowTime().hasLogin
     */
    const hasValidLogin = computed(() => {
      const canRefreshSession = isDoubleTokenMode && hasStoredRefreshCookie() && !isRefreshTokenExpired.value
      const valid = hasLoginInfo.value && (!isTokenExpired.value || canRefreshSession)
      console.log('hasValidLogin', hasLoginInfo.value, valid)
      return valid
    })

    /**
     * 尝试获取有效的token，如果过期且可刷新，则刷新token
     * @returns 有效的token或空字符串
     */
    const tryGetValidToken = async (): Promise<string> => {
      updateNowTime()
      if (!getValidToken.value && isDoubleTokenMode && !isRefreshTokenExpired.value) {
        try {
          await refreshToken()
          return getValidToken.value
        }
        catch (error) {
          console.error('尝试刷新token失败:', error)
          return ''
        }
      }
      return getValidToken.value
    }

    return {
      // 核心API方法
      login,
      wxLogin,
      logout,

      // 认证状态判断（最常用的）
      hasLogin: hasValidLogin,

      // 内部系统使用的方法
      refreshToken,
      tryGetValidToken,
      validToken: getValidToken,

      // 调试或特殊场景可能需要直接访问的信息
      tokenInfo,
      setTokenInfo,
      updateNowTime,
    }
  },
  {
    // 添加持久化配置，确保刷新页面后token信息不丢失
    persist: true,
  },
)
