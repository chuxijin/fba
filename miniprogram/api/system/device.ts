/**
 * 设备信息相关 API
 */

import { post } from '../request'

/**
 * 更新设备信息参数
 */
export interface UpdateDeviceParams {
  device_id: string
  device_model?: string
  os_version?: string
  app_version?: string
  push_token?: string
}

/**
 * 更新设备信息（用于 App 启动/恢复时同步设备状态）
 */
export function updateDeviceInfo(params: UpdateDeviceParams) {
  return post('/qbank/device/update', params, {
    needToken: true,
    silent: true  // 静默更新，不显示 loading 和 toast
  })
}

export default {
  updateDeviceInfo
}
