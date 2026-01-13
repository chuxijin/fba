/**
 * 系统信息 Composable
 *
 * 统一管理小程序系统信息，避免到处调用 deprecated API
 */
import { ref, computed } from 'vue'

declare const uni: any

// 系统信息缓存（全局单例）
let systemInfoCache: SystemInfoData | null = null

interface SystemInfoData {
  windowInfo: UniNamespace.GetWindowInfoResult
  deviceInfo: UniNamespace.GetDeviceInfoResult
  appBaseInfo: UniNamespace.GetAppBaseInfoResult
  systemSetting: UniNamespace.GetSystemSettingResult
  appAuthorizeSetting: UniNamespace.GetAppAuthorizeSettingResult
}

export function useSystemInfo() {
  const systemInfo = ref<SystemInfoData | null>(systemInfoCache)

  /**
   * 初始化系统信息（App.vue 启动时调用）
   */
  function initSystemInfo() {
    if (systemInfoCache) return systemInfoCache

    try {
      const windowInfo = uni.getWindowInfo()
      const deviceInfo = uni.getDeviceInfo()
      const appBaseInfo = uni.getAppBaseInfo()
      const systemSetting = uni.getSystemSetting()
      const appAuthorizeSetting = uni.getAppAuthorizeSetting()

      systemInfoCache = {
        windowInfo,
        deviceInfo,
        appBaseInfo,
        systemSetting,
        appAuthorizeSetting,
      }

      systemInfo.value = systemInfoCache
      return systemInfoCache
    } catch (error) {
      console.error('[系统信息] 初始化失败:', error)
      return null
    }
  }

  /**
   * 获取窗口信息
   */
  const windowInfo = computed(() => systemInfo.value?.windowInfo)

  /**
   * 获取设备信息
   */
  const deviceInfo = computed(() => systemInfo.value?.deviceInfo)

  /**
   * 获取应用基础信息
   */
  const appBaseInfo = computed(() => systemInfo.value?.appBaseInfo)

  /**
   * 获取系统设置
   */
  const systemSetting = computed(() => systemInfo.value?.systemSetting)

  /**
   * 获取应用授权设置
   */
  const appAuthorizeSetting = computed(() => systemInfo.value?.appAuthorizeSetting)

  /**
   * 计算 Swiper 容器高度
   *
   * @param selector - 选择器（如 '.content-swiper'）
   * @param callback - 回调函数，接收计算后的高度（px 字符串）
   */
  function calculateSwiperHeight(selector: string, callback: (height: string) => void) {
    if (!windowInfo.value) {
      console.warn('[系统信息] windowInfo 未初始化，无法计算高度')
      return
    }

    const query = uni.createSelectorQuery()
    query.select(selector).boundingClientRect()
    query.exec((result: any) => {
      if (result && result[0]) {
        const calculatedHeight = windowInfo.value!.windowHeight - result[0].top
        callback(`${calculatedHeight}px`)
      }
    })
  }

  /**
   * 计算元素距顶部的剩余高度
   *
   * @param selector - 选择器
   * @return Promise<string> - 高度字符串（如 '500px'）
   */
  async function calculateRemainingHeight(selector: string): Promise<string> {
    return new Promise((resolve) => {
      calculateSwiperHeight(selector, (height) => resolve(height))
    })
  }

  return {
    // 初始化
    initSystemInfo,

    // 系统信息
    systemInfo,
    windowInfo,
    deviceInfo,
    appBaseInfo,
    systemSetting,
    appAuthorizeSetting,

    // 工具函数
    calculateSwiperHeight,
    calculateRemainingHeight,
  }
}
