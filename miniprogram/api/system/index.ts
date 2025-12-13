/**
 * 系统 API 统一导出
 */

export * from './auth'
export * from './customer'

// 默认导出
import * as authApi from './auth'
import * as customerApi from './customer'

export default {
  auth: authApi,
  customer: customerApi,
}
