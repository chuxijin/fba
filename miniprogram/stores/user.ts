import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import customerApi, { type UserInfo, type UserMembership } from '../api/system/customer'

declare const uni: any

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<UserInfo | null>(null)
  const memberships = ref<UserMembership[]>([])
  const lastFetchTime = ref<number>(0)

  const isLoggedIn = computed(() => !!userInfo.value)

  // 缓存策略：30分钟内不重复请求
  const CACHE_DURATION = 30 * 60 * 1000

  /**
   * 获取用户信息（带缓存）
   */
  async function fetchUserInfo(force = false) {
    const now = Date.now()

    // 未登录
    const token = uni.getStorageSync('access_token')
    if (!token) {
      userInfo.value = null
      memberships.value = []
      lastFetchTime.value = 0
      return
    }

    // 缓存有效（30分钟内）
    if (!force && userInfo.value && (now - lastFetchTime.value < CACHE_DURATION)) {
      console.log('[用户Store] 使用缓存数据')
      return
    }

    try {
      console.log('[用户Store] 请求用户信息')
      const data = await customerApi.getCurrentUser()
      userInfo.value = data
      memberships.value = data.memberships || []
      lastFetchTime.value = now
    } catch (error: any) {
      console.error('[用户Store] 获取用户信息失败:', error)
      // 401 token过期，清除登录态
      if (error.code === 401 || error.statusCode === 401) {
        logout()
      }
    }
  }

  /**
   * ✅ 核心方法：前端计算题库权限（0次API）
   */
  function checkBankAccess(
    bankId: number,
    catId: number,
    scope: number
  ): {
    hasAccess: boolean
    reason: 'free' | 'vip_all' | 'vip_category' | 'purchased' | 'need_login' | 'need_purchase'
    endTime?: string
    remainingDays?: number
  } {
    // 免费题库
    if (scope === 1) {
      return { hasAccess: true, reason: 'free' }
    }

    // 未登录
    if (!userInfo.value) {
      return { hasAccess: false, reason: 'need_login' }
    }

    const now = new Date()

    // 检查全站会员 (category=0)
    const vipAll = memberships.value.find(
      m => m.category === 0 && new Date(m.end_time) > now
    )
    if (vipAll) {
      return {
        hasAccess: true,
        reason: 'vip_all',
        endTime: vipAll.end_time,
        remainingDays: vipAll.remaining_days
      }
    }

    // 检查分类会员 (category=1, res_type='category', res_id=catId)
    const vipCategory = memberships.value.find(
      m =>
        m.category === 1 &&
        m.res_type === 'category' &&
        m.res_id === catId &&
        new Date(m.end_time) > now
    )
    if (vipCategory) {
      return {
        hasAccess: true,
        reason: 'vip_category',
        endTime: vipCategory.end_time,
        remainingDays: vipCategory.remaining_days
      }
    }

    // 检查单题库 (category=1, res_type='single', res_id=bankId)
    const purchased = memberships.value.find(
      m =>
        m.category === 1 &&
        m.res_type === 'single' &&
        m.res_id === bankId &&
        new Date(m.end_time) > now
    )
    if (purchased) {
      return {
        hasAccess: true,
        reason: 'purchased',
        endTime: purchased.end_time,
        remainingDays: purchased.remaining_days
      }
    }

    return { hasAccess: false, reason: 'need_purchase' }
  }

  /**
   * 强制刷新用户信息（支付成功后调用）
   */
  async function refreshUserInfo() {
    await fetchUserInfo(true)
  }

  /**
   * 登出
   */
  function logout() {
    console.log('[用户Store] 开始清除登录状态...')
    console.log('[用户Store] 清除前 - userInfo:', userInfo.value, 'isLoggedIn:', isLoggedIn.value)

    // 清除 store 状态
    userInfo.value = null
    memberships.value = []
    lastFetchTime.value = 0

    // 清除本地存储
    uni.removeStorageSync('access_token')
    uni.removeStorageSync('user_info')
    uni.removeStorageSync('token')  // 兼容旧版本

    console.log('[用户Store] 清除后 - userInfo:', userInfo.value, 'isLoggedIn:', isLoggedIn.value)
    console.log('[用户Store] Token已清除:', !uni.getStorageSync('access_token'))
  }

  return {
    userInfo,
    isLoggedIn,
    memberships,
    fetchUserInfo,
    checkBankAccess,
    refreshUserInfo,
    logout
  }
})
