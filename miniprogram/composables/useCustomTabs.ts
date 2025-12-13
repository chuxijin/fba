import { ref, computed } from 'vue'

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

/**
 * 初始化自定义 Tab
 */
function initCustomTabs() {
  if (initialized) return

  try {
    if (typeof uni !== 'undefined') {
      const stored = uni.getStorageSync(STORAGE_KEY)
      if (stored && Array.isArray(stored)) {
        customTabs.value = stored
      } else {
        customTabs.value = [...DEFAULT_TABS]
        saveCustomTabs()
      }
    } else {
      customTabs.value = [...DEFAULT_TABS]
    }
  } catch (error) {
    console.error('初始化自定义 Tab 失败:', error)
    customTabs.value = [...DEFAULT_TABS]
  }

  initialized = true
}

/**
 * 保存自定义 Tab 到存储
 */
function saveCustomTabs() {
  try {
    if (typeof uni !== 'undefined') {
      uni.setStorageSync(STORAGE_KEY, customTabs.value)
    }
  } catch (error) {
    console.error('保存自定义 Tab 失败:', error)
  }
}

/**
 * 自定义 Tab 管理 Composable
 */
export function useCustomTabs() {
  initCustomTabs()

  const sortedTabs = computed(() => {
    return [...customTabs.value].sort((a, b) => a.order - b.order)
  })

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
      console.warn('不能删除固定 Tab')
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

  return {
    tabs: sortedTabs,
    addTab,
    removeTab,
    updateTabOrder,
    hasTab,
    resetTabs,
    getTab
  }
}
