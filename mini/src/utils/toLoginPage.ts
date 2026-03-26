import { getLastPage } from '@/utils'
import { debounce } from '@/utils/debounce'

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
}

// 当前项目没有独立登录页，统一回到“我的”页触发登录流程
const LOGIN_PAGE = '/pages/mine/index'

/**
 * 跳转到登录页, 带防抖处理
 *
 * 如果要立即跳转，不做延时，可以使用 `toLoginPage.flush()` 方法
 */
export const toLoginPage = debounce((options: ToLoginPageOptions = {}) => {
  const { mode = 'switchTab', queryString = '' } = options
  const loginUrl = `${LOGIN_PAGE}${queryString}`

  // 获取当前页面路径
  const currentPage = getLastPage()
  const currentPath = `/${currentPage.route}`
  // 如果已经在登录页，则不跳转
  if (currentPath === LOGIN_PAGE) {
    return
  }

  if (mode === 'reLaunch') {
    uni.reLaunch({ url: loginUrl })
    return
  }

  uni.switchTab({ url: LOGIN_PAGE })
}, 500)
