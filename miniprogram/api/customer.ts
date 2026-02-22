/**
 * 用户相关 API
 */

import { get } from './request'

/** ==================== 类型定义 ==================== */

/** 用户会员权益 */
export interface UserMembership {
  category: number // 0=全部, 1=题库, 2=词库...
  res_type: string // 'category'/'single'
  res_id: number | null // 资源ID
  end_time: string // 到期时间
  remaining_days: number // 剩余天数
}

/** 用户信息 */
export interface UserInfo {
  id: number
  username: string
  nickname: string
  avatar?: string
  memberships: UserMembership[]
}

/** ==================== API 方法 ==================== */

/**
 * 获取当前用户信息
 */
export function getCurrentUser() {
  return get<UserInfo>('/qbank/customer/me', undefined, {
    needToken: true,
  })
}

/** 导出为默认对象 */
export default {
  getCurrentUser,
}
