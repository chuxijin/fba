import { ref, computed } from 'vue'
import * as userSettingsApi from '@/api/business/user-settings'

declare const uni: any

/**
 * 自定义 Tab 数据结构
 */
export interface CustomTab {
  id: string
  name: string
  categoryId: number
  categoryName: string
  bankId: number | null
  bankName: string | null
  isFixed: boolean
  order: number
}

const STORAGE_KEY = 'practice-custom-tabs'

// 默认 Tab 配置
const DEFAULT_TABS: CustomTab[] = [
  {
    id: 'all',
    name: '全部',
    categoryId: 0,
    categoryName: '全部',
    bankId: null,
    bankName: null,
    isFixed: true,
    order: 0
  }
]

// 全局 Tab 列表
const customTabs = ref<CustomTab[]>([])
let initialized = false

// 🔥 全局单例 computed（确保所有组件共享同一个响应式引用）
const sortedTabs = computed(() => {
  return [...customTabs.value].sort((a, b) => a.order - b.order)
})

/**
 * 从后端加载 Tab 配置
 */
async function loadFromBackend(): Promise<CustomTab[]> {
  try {
    const token = uni.getStorageSync('access_token')
    if (!token) {
      return []
    }

    const response = await userSettingsApi.getStudyPreference()

    // 🔥 后端返回 snake_case，前端使用 camelCase，需要转换
    const backendTabs = response.custom_tabs || []
    return backendTabs.map(tab => ({
      id: tab.id,
      name: tab.name,
      categoryId: tab.category_id,
      categoryName: tab.category_name,
      bankId: tab.bank_id,
      bankName: tab.bank_name,
      isFixed: tab.is_fixed,
      order: tab.order
    }))
  } catch (error) {
    console.error('[Custom Tabs] 从后端加载失败:', error)
    return []
  }
}

/**
 * 同步到后端
 */
async function syncToBackend(tabs: CustomTab[]): Promise<void> {
  try {
    const token = uni.getStorageSync('access_token')
    if (!token) {
      return
    }

    // 🔥 前端 camelCase 转换为后端 snake_case
    const backendTabs = tabs.map(tab => ({
      id: tab.id,
      name: tab.name,
      category_id: tab.categoryId,
      category_name: tab.categoryName,
      bank_id: tab.bankId,
      bank_name: tab.bankName,
      is_fixed: tab.isFixed,
      order: tab.order
    }))

    await userSettingsApi.updateStudyPreference({
      custom_tabs: backendTabs as any
    })

    console.log('[Custom Tabs] 已同步到后端:', tabs.length, '个 Tab')
  } catch (error) {
    console.error('[Custom Tabs] 同步到后端失败:', error)
  }
}

/**
 * 初始化自定义 Tab
 */
async function initCustomTabs() {
  if (initialized) return

  // 🔥 立即标记为已初始化，防止重复调用
  initialized = true

  try {
    if (typeof uni !== 'undefined') {
      // 🔥 第一步：先同步加载本地数据（立即可用）
      const stored = uni.getStorageSync(STORAGE_KEY)
      if (stored && Array.isArray(stored) && stored.length > 0) {
        // ✅ 本地有数据，直接使用（不从后端加载，避免覆盖）
        customTabs.value = stored
        console.log('[Custom Tabs] 使用本地缓存:', stored.length, '个 Tab')
      } else {
        // ✅ 本地没有数据，从后端加载
        console.log('[Custom Tabs] 本地无数据，尝试从后端加载')
        const backendTabs = await loadFromBackend()

        if (backendTabs.length > 0) {
          customTabs.value = backendTabs
          uni.setStorageSync(STORAGE_KEY, backendTabs)
          console.log('[Custom Tabs] 从后端加载:', backendTabs.length, '个 Tab')
        } else {
          customTabs.value = [...DEFAULT_TABS]
          saveCustomTabs()
          console.log('[Custom Tabs] 使用默认配置')
        }
      }
    } else {
      customTabs.value = [...DEFAULT_TABS]
    }
  } catch (error) {
    console.error('[Custom Tabs] 初始化失败:', error)
    // 如果已经有本地数据，保持不变；否则使用默认
    if (customTabs.value.length === 0) {
      customTabs.value = [...DEFAULT_TABS]
    }
  }
}

/**
 * 保存自定义 Tab 到存储
 */
function saveCustomTabs() {
  try {
    if (typeof uni !== 'undefined') {
      // 保存到本地存储
      uni.setStorageSync(STORAGE_KEY, customTabs.value)

      // 🔥 异步同步到后端（不阻塞UI）
      syncToBackend(customTabs.value).catch(err => {
        console.error('[Custom Tabs] 后台同步失败:', err)
      })
    }
  } catch (error) {
    console.error('[Custom Tabs] 保存失败:', error)
  }
}

/**
 * 自定义 Tab 管理 Composable
 */
export function useCustomTabs() {
  // 🔥 确保初始化（异步，不阻塞）
  if (!initialized) {
    initCustomTabs().catch(err => {
      console.error('[Custom Tabs] 初始化失败:', err)
    })
  }

  /**
   * 添加自定义 Tab
   */
  function addTab(tab: Omit<CustomTab, 'id' | 'isFixed' | 'order'>) {
    const newTab: CustomTab = {
      ...tab,
      id: `custom-${Date.now()}`,
      isFixed: false,
      order: customTabs.value.length
    }

    customTabs.value.push(newTab)
    saveCustomTabs()

    return newTab
  }

  /**
   * 删除自定义 Tab
   */
  function removeTab(tabId: string) {
    const index = customTabs.value.findIndex(t => t.id === tabId)
    if (index === -1) return false

    const tab = customTabs.value[index]
    if (tab.isFixed) {
      console.warn('[Custom Tabs] 不能删除固定 Tab')
      return false
    }

    customTabs.value.splice(index, 1)
    saveCustomTabs()

    return true
  }

  /**
   * 更新 Tab 顺序
   */
  function updateTabOrder(tabId: string, newOrder: number) {
    const tab = customTabs.value.find(t => t.id === tabId)
    if (!tab) return false

    tab.order = newOrder
    saveCustomTabs()

    return true
  }

  /**
   * 检查 Tab 是否已存在
   */
  function hasTab(categoryId: number, bankId: number | null): boolean {
    return customTabs.value.some(
      t => t.categoryId === categoryId && t.bankId === bankId
    )
  }

  /**
   * 重置为默认 Tab
   */
  function resetTabs() {
    customTabs.value = [...DEFAULT_TABS]
    saveCustomTabs()
  }

  /**
   * 获取指定 Tab
   */
  function getTab(tabId: string): CustomTab | undefined {
    return customTabs.value.find(t => t.id === tabId)
  }

  /**
   * 手动从后端重新加载配置
   */
  async function reloadFromBackend() {
    const backendTabs = await loadFromBackend()
    if (backendTabs.length > 0) {
      customTabs.value = backendTabs
      uni.setStorageSync(STORAGE_KEY, backendTabs)
    }
  }

  // 🔥 返回全局单例 computed，确保响应式
  return {
    tabs: sortedTabs,
    addTab,
    removeTab,
    updateTabOrder,
    hasTab,
    resetTabs,
    getTab,
    reloadFromBackend
  }
}
