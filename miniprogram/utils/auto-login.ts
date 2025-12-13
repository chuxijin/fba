/**
 * 开发环境自动登录工具
 *
 * 功能：
 * - 检测开发环境，自动使用测试账号登录
 * - 避免每次启动都需要手动登录
 * - 生产环境不生效
 */

import { API_BASE_URL } from '@/config/api'

/**
 * 自动登录配置
 */
interface AutoLoginConfig {
  enabled: boolean
  username: string
  nickname: string
  showToast: boolean
}

/**
 * 默认配置
 */
const DEFAULT_CONFIG: AutoLoginConfig = {
  enabled: true,
  username: 'dev_test_user',
  nickname: '开发测试用户',
  showToast: false
}

/**
 * 检查是否已登录
 */
function isLoggedIn(): boolean {
  const token = uni.getStorageSync('access_token')
  return !!token
}

/**
 * 检查是否为开发环境
 */
function isDevelopment(): boolean {
  // @ts-ignore
  return process.env.NODE_ENV === 'development'
}

/**
 * 执行测试登录
 *
 * :param config: 登录配置
 * :return: 是否登录成功
 */
async function performTestLogin(config: AutoLoginConfig): Promise<boolean> {
  try {
    console.log(`[自动登录] 开始自动登录，用户: ${config.username}`)

    const res = await uni.request({
      url: `${API_BASE_URL}/qbank/auth/test-login`,
      method: 'POST',
      data: {
        username: config.username,
        nickname: config.nickname
      },
      timeout: 10000
    })

    if (res.data.code === 200) {
      const { access_token, user_info } = res.data.data

      // 保存 token 和用户信息
      uni.setStorageSync('access_token', access_token)
      uni.setStorageSync('user_info', user_info)

      console.log(`[自动登录] 登录成功，用户 ID: ${user_info.id}`)

      if (config.showToast) {
        uni.showToast({
          title: `自动登录成功`,
          icon: 'success',
          duration: 1500
        })
      }

      return true
    } else {
      console.error(`[自动登录] 登录失败:`, res.data.msg)
      return false
    }
  } catch (error: any) {
    console.error('[自动登录] 登录异常:', error)
    return false
  }
}

/**
 * 自动登录主函数
 *
 * :param customConfig: 自定义配置（可选）
 * :return: 是否登录成功
 */
export async function autoLogin(customConfig?: Partial<AutoLoginConfig>): Promise<boolean> {
  const config: AutoLoginConfig = { ...DEFAULT_CONFIG, ...customConfig }

  // 1. 检查是否启用自动登录
  if (!config.enabled) {
    console.log('[自动登录] 自动登录已禁用')
    return false
  }

  // 2. 检查是否为开发环境
  if (!isDevelopment()) {
    console.log('[自动登录] 非开发环境，跳过自动登录')
    return false
  }

  // 3. 检查是否已登录
  if (isLoggedIn()) {
    console.log('[自动登录] 已登录，跳过自动登录')
    return true
  }

  // 4. 执行自动登录
  console.log('[自动登录] 条件满足，执行自动登录...')
  return await performTestLogin(config)
}

/**
 * 手动测试登录（供调试页面使用）
 *
 * :param username: 用户名
 * :param nickname: 昵称
 * :return: 是否登录成功
 */
export async function manualTestLogin(username: string, nickname?: string): Promise<boolean> {
  if (!username.trim()) {
    uni.showToast({
      title: '请输入用户名',
      icon: 'none'
    })
    return false
  }

  return await performTestLogin({
    enabled: true,
    username,
    nickname: nickname || `测试用户_${username}`,
    showToast: true
  })
}

/**
 * 退出登录
 */
export function logout(): void {
  uni.removeStorageSync('access_token')
  uni.removeStorageSync('user_info')
  console.log('[自动登录] 已退出登录')
}

/**
 * 获取当前登录状态
 */
export function getLoginStatus(): {
  isLoggedIn: boolean
  userInfo: any | null
  token: string | null
} {
  const token = uni.getStorageSync('access_token')
  const userInfo = uni.getStorageSync('user_info')

  return {
    isLoggedIn: !!token,
    userInfo: userInfo || null,
    token: token || null
  }
}
