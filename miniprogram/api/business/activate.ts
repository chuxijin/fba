/**
 * 激活码相关 API
 */

import { post } from '../request'

/**
 * 兑换结果
 */
export interface RedeemCodeResult {
  success: boolean
  reward_type: string
  reward_data: Record<string, any>
  message: string
}

/**
 * 查询激活码信息（不实际激活）
 *
 * :param code: 激活码
 * :return: 激活码信息
 */
export function queryActivationCode(code: string): Promise<RedeemCodeResult> {
  return post('/qbank/activation/query', { code }, {
    needToken: false,  // 不需要登录即可查询
    silent: false
  })
}

/**
 * 兑换激活码（题库系统专用接口）
 *
 * :param code: 激活码
 * :return: 兑换结果
 */
export function redeemActivationCode(code: string): Promise<RedeemCodeResult> {
  return post('/qbank/activation/redeem', { code }, {
    needToken: true,  // 需要登录
    silent: false
  })
}
