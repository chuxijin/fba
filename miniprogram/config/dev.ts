/**
 * 开发环境配置
 *
 * 这个文件包含开发环境专用的配置，包括：
 * - 自动登录配置
 * - 调试选项
 * - 测试账号列表
 */

/**
 * 自动登录配置
 */
export const autoLoginConfig = {
  // 是否启用自动登录
  enabled: true,

  // 默认测试账号
  defaultAccount: {
    username: 'dev_test_user',
    nickname: '开发测试用户'
  },

  // 是否显示登录成功提示
  showToast: false
}

/**
 * 预设测试账号列表（用于快速切换）
 */
export const testAccounts = [
  {
    username: 'test_admin',
    nickname: '测试管理员',
    description: '模拟管理员账号'
  },
  {
    username: 'test_vip',
    nickname: '测试 VIP 用户',
    description: '模拟 VIP 会员'
  },
  {
    username: 'test_newbie',
    nickname: '测试新手',
    description: '模拟新注册用户'
  },
  {
    username: 'test_student',
    nickname: '测试学生',
    description: '模拟学生用户'
  }
]

/**
 * 调试选项
 */
export const debugOptions = {
  // 是否显示详细日志
  verbose: true,

  // 是否显示 API 请求日志
  logApiRequests: true,

  // 是否模拟网络延迟（毫秒）
  mockNetworkDelay: 0
}

/**
 * 开发环境特性开关
 */
export const devFeatures = {
  // 是否启用调试面板
  enableDebugPanel: true,

  // 是否跳过某些验证
  skipValidation: false,

  // 是否允许访问所有题库（忽略权限）
  unlockAllBanks: false
}

/**
 * 快捷操作配置
 */
export const shortcuts = {
  // 是否启用摇一摇切换账号
  shakeToSwitchAccount: false,

  // 是否启用长按标题栏显示调试菜单
  longPressForDebugMenu: true
}
