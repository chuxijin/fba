/**
 * 设备信息辅助工具
 */

declare const uni: any

export interface DeviceInfo {
  device_id: string
  device_model: string
  os_version: string
  app_version: string
  platform: string
}

/**
 * 获取或生成设备唯一标识
 */
export function getOrCreateDeviceId(): string {
  const DEVICE_ID_KEY = 'device_id'

  // 尝试从缓存读取
  let deviceId = uni.getStorageSync(DEVICE_ID_KEY)

  if (!deviceId) {
    const deviceInfo = uni.getDeviceInfo()
    // 使用微信提供的 deviceId（更稳定）
    deviceId = deviceInfo.deviceId || generateDeviceId(deviceInfo.platform)

    // 存储到本地
    uni.setStorageSync(DEVICE_ID_KEY, deviceId)
  }

  return deviceId
}

/**
 * 生成设备唯一标识
 */
function generateDeviceId(platform: string = 'unknown'): string {
  const timestamp = Date.now()
  const random = Math.random().toString(36).substring(2, 11)
  return `${platform}_${timestamp}_${random}`
}

/**
 * 收集完整的设备信息
 */
export function collectDeviceInfo(): DeviceInfo {
  const deviceId = getOrCreateDeviceId()
  const deviceInfo = uni.getDeviceInfo()
  const appInfo = uni.getAppBaseInfo()

  return {
    device_id: deviceId,
    device_model: deviceInfo.deviceModel || deviceInfo.model || 'Unknown',
    os_version: `${deviceInfo.osName || 'Unknown'} ${deviceInfo.osVersion || ''}`.trim(),
    app_version: appInfo.version || '1.0.0',
    platform: deviceInfo.platform || 'miniapp'
  }
}

/**
 * 获取详细的系统信息（用于调试）
 */
export function getDetailedSystemInfo() {
  return {
    deviceInfo: uni.getDeviceInfo(),
    appBaseInfo: uni.getAppBaseInfo(),
    windowInfo: uni.getWindowInfo(),
    systemSetting: uni.getSystemSetting(),
    appAuthorizeSetting: uni.getAppAuthorizeSetting()
  }
}

