/**
 * 本地存储工具函数
 */

declare const uni: any

/**
 * 设置存储
 *
 * @param key 键名
 * @param value 值
 */
export function setStorage(key: string, value: any): void {
  try {
    uni.setStorageSync(key, value)
  } catch (error) {
    console.error(`[Storage] 设置失败:`, error)
  }
}

/**
 * 获取存储
 *
 * @param key 键名
 * @param defaultValue 默认值
 * @return 存储的值
 */
export function getStorage<T = any>(key: string, defaultValue?: T): T | undefined {
  try {
    const value = uni.getStorageSync(key)
    return value !== '' ? value : defaultValue
  } catch (error) {
    console.error(`[Storage] 获取失败:`, error)
    return defaultValue
  }
}

/**
 * 移除存储
 *
 * @param key 键名
 */
export function removeStorage(key: string): void {
  try {
    uni.removeStorageSync(key)
  } catch (error) {
    console.error(`[Storage] 移除失败:`, error)
  }
}

/**
 * 清空存储
 */
export function clearStorage(): void {
  try {
    uni.clearStorageSync()
  } catch (error) {
    console.error(`[Storage] 清空失败:`, error)
  }
}

/**
 * 获取存储信息
 *
 * @return 存储信息
 */
export function getStorageInfo(): {
  keys: string[]
  currentSize: number
  limitSize: number
} {
  try {
    return uni.getStorageInfoSync()
  } catch (error) {
    console.error(`[Storage] 获取信息失败:`, error)
    return { keys: [], currentSize: 0, limitSize: 0 }
  }
}
