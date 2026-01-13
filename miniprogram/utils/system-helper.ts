/**
 * 系统信息辅助函数
 *
 * 基于 useSystemInfo 提供的系统信息，封装常用的判断逻辑
 */
import { useSystemInfo } from '@/composables/useSystemInfo'

declare const uni: any

/**
 * 比较版本号
 *
 * @param v1 - 版本号 1
 * @param v2 - 版本号 2
 * @return -1: v1 < v2, 0: v1 === v2, 1: v1 > v2
 */
export function compareVersion(v1: string, v2: string): number {
  const v1Arr = v1.split('.')
  const v2Arr = v2.split('.')
  const len = Math.max(v1Arr.length, v2Arr.length)

  for (let i = 0; i < len; i++) {
    const num1 = parseInt(v1Arr[i] || '0')
    const num2 = parseInt(v2Arr[i] || '0')
    if (num1 > num2) return 1
    if (num1 < num2) return -1
  }
  return 0
}

/**
 * 检查基础库版本是否满足要求
 *
 * @param minVersion - 最低版本要求
 * @return 是否满足
 */
export function checkSDKVersion(minVersion: string): boolean {
  const { appBaseInfo } = useSystemInfo()
  if (!appBaseInfo.value) return false

  const currentVersion = appBaseInfo.value.hostSDKVersion || '0.0.0'
  return compareVersion(currentVersion, minVersion) >= 0
}

/**
 * 检查是否为 iOS 设备
 */
export function isIOS(): boolean {
  const { deviceInfo } = useSystemInfo()
  return deviceInfo.value?.osName?.toLowerCase() === 'ios'
}

/**
 * 检查是否为 Android 设备
 */
export function isAndroid(): boolean {
  const { deviceInfo } = useSystemInfo()
  return deviceInfo.value?.osName?.toLowerCase() === 'android'
}

/**
 * 检查是否为开发工具
 */
export function isDevTools(): boolean {
  const { deviceInfo } = useSystemInfo()
  return deviceInfo.value?.platform === 'devtools'
}

/**
 * 获取状态栏高度（用于适配刘海屏）
 */
export function getStatusBarHeight(): number {
  const { windowInfo } = useSystemInfo()
  return windowInfo.value?.statusBarHeight || 0
}

/**
 * 获取底部安全区域高度（用于适配全面屏）
 */
export function getSafeAreaBottom(): number {
  const { windowInfo } = useSystemInfo()
  const safeAreaInsets = windowInfo.value?.safeAreaInsets
  return safeAreaInsets?.bottom || 0
}

/**
 * 检查权限并引导用户授权
 *
 * @param permissionType - 权限类型
 * @param tipMessage - 提示信息
 * @return 是否已授权
 */
export async function checkPermission(
  permissionType: 'camera' | 'album' | 'location' | 'microphone',
  tipMessage?: string
): Promise<boolean> {
  const { appAuthorizeSetting } = useSystemInfo()
  if (!appAuthorizeSetting.value) return false

  const authKey = `${permissionType}Authorized` as keyof typeof appAuthorizeSetting.value
  const authStatus = appAuthorizeSetting.value[authKey]

  if (authStatus === 'authorized') {
    return true
  }

  if (authStatus === 'denied') {
    // 已拒绝，引导用户去设置
    const permissionNames: Record<string, string> = {
      camera: '相机',
      album: '相册',
      location: '位置',
      microphone: '麦克风',
    }

    return new Promise((resolve) => {
      uni.showModal({
        title: '需要授权',
        content: tipMessage || `使用此功能需要${permissionNames[permissionType]}权限，请在设置中开启`,
        confirmText: '去设置',
        success: (res: any) => {
          if (res.confirm) {
            uni.openSetting({
              success: () => {
                // 用户可能已经授权，重新检查
                resolve(checkPermission(permissionType))
              },
            })
          } else {
            resolve(false)
          }
        },
      })
    })
  }

  // 'not determined' 或其他状态，返回 false，让业务代码自行调用授权 API
  return false
}

/**
 * 检查网络状态（需要用户授权）
 */
export async function getNetworkType(): Promise<string> {
  return new Promise((resolve) => {
    uni.getNetworkType({
      success: (res: any) => {
        resolve(res.networkType)
      },
      fail: () => {
        resolve('unknown')
      },
    })
  })
}

/**
 * 根据网络状态优化图片质量
 *
 * @param originalUrl - 原始图片 URL
 * @return 优化后的 URL
 */
export async function optimizeImageUrl(originalUrl: string): Promise<string> {
  const networkType = await getNetworkType()

  // WiFi 下加载原图
  if (networkType === 'wifi') {
    return originalUrl
  }

  // 2G/3G 下加载缩略图（假设服务端支持参数）
  if (networkType === '2g' || networkType === '3g') {
    return `${originalUrl}?x-oss-process=image/resize,w_400`
  }

  // 4G/5G 下加载中等质量
  return `${originalUrl}?x-oss-process=image/resize,w_800`
}

/**
 * 判断设备性能等级（简单判断）
 */
export function getDevicePerformance(): 'high' | 'medium' | 'low' {
  const { deviceInfo, windowInfo } = useSystemInfo()

  // 开发工具默认高性能
  if (isDevTools()) return 'high'

  const pixelRatio = windowInfo.value?.pixelRatio || 2
  const osName = deviceInfo.value?.osName?.toLowerCase() || ''

  // iOS 设备一般性能较好
  if (osName === 'ios') {
    return pixelRatio >= 3 ? 'high' : 'medium'
  }

  // Android 根据像素比简单判断
  if (pixelRatio >= 3) return 'high'
  if (pixelRatio >= 2) return 'medium'
  return 'low'
}
