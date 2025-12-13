import { ref } from 'vue'

declare const uni: any

declare const document: Document & {
  body?: HTMLElement & {
    getAttribute: (qualifiedName: string) => string | null
    setAttribute: (qualifiedName: string, value: string) => void
  }
}

const THEME_STORAGE_KEY = 'app-theme'
type Theme = 'light' | 'dark'

// 全局共享的主题状态
const isDarkMode = ref<boolean>(false)
let initialized = false

/**
 * 应用主题到 DOM 和存储
 */
function applyTheme(theme: Theme) {
  if (typeof document !== 'undefined' && document.body) {
    document.body.setAttribute('data-theme', theme)
  }

  if (typeof uni !== 'undefined') {
    uni.setStorageSync(THEME_STORAGE_KEY, theme)
  }
}

/**
 * 初始化主题
 */
function initTheme() {
  if (initialized) return

  let initialTheme: Theme = 'light'

  // 优先从 DOM 获取
  if (typeof document !== 'undefined' && document.body) {
    const bodyTheme = document.body.getAttribute('data-theme')
    if (bodyTheme === 'dark' || bodyTheme === 'light') {
      initialTheme = bodyTheme
    }
  }

  // 其次从存储获取
  if (typeof uni !== 'undefined') {
    const storedTheme = uni.getStorageSync(THEME_STORAGE_KEY)
    if (storedTheme === 'dark' || storedTheme === 'light') {
      initialTheme = storedTheme
    }
  }

  isDarkMode.value = initialTheme === 'dark'
  applyTheme(initialTheme)
  initialized = true
}

/**
 * 主题管理 Composable
 */
export function useTheme() {
  // 确保初始化
  initTheme()

  /**
   * 切换主题
   */
  function toggleTheme() {
    const nextTheme: Theme = isDarkMode.value ? 'light' : 'dark'
    isDarkMode.value = !isDarkMode.value
    applyTheme(nextTheme)
  }

  /**
   * 设置指定主题
   */
  function setTheme(theme: Theme) {
    isDarkMode.value = theme === 'dark'
    applyTheme(theme)
  }

  /**
   * 获取当前主题
   */
  function getCurrentTheme(): Theme {
    return isDarkMode.value ? 'dark' : 'light'
  }

  return {
    isDarkMode,
    toggleTheme,
    setTheme,
    getCurrentTheme
  }
}
