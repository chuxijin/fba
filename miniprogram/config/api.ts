/**
 * API 配置
 *
 * 配置说明：
 * - 开发环境：统一使用 localhost（仅限开发者工具）
 * - 生产环境：使用线上域名（真机调试时使用）
 */

// 开发环境配置（开发者工具专用）
const DEV_CONFIG = {
  baseUrl: 'http://localhost:8000'
}

// 生产环境配置（真机调试和正式发布）
const PROD_CONFIG = {
  baseUrl: 'https://your-domain.com'  // TODO: 替换为生产环境域名
}

/**
 * 获取 API 基础 URL
 */
export function getApiBaseUrl(): string {
  // @ts-ignore
  if (process.env.NODE_ENV === 'production') {
    return PROD_CONFIG.baseUrl
  }

  // 开发环境统一使用 localhost
  return DEV_CONFIG.baseUrl
}

/**
 * 完整的 API 路径
 */
export const API_BASE_URL = `${getApiBaseUrl()}/api/v1`

/**
 * 默认头像（Base64 SVG）
 */
export const DEFAULT_AVATAR = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2VlZSIvPjxjaXJjbGUgY3g9IjEwMCIgY3k9IjgwIiByPSIzMCIgZmlsbD0iI2NjYyIvPjxwYXRoIGQ9Ik02MCAxNTBDNjAgMTMwIDgwIDEyMCAxMDAgMTIwczQwIDEwIDQwIDMwIiBmaWxsPSIjY2NjIi8+PC9zdmc+'

console.log('=== API 配置 ===')
console.log('运行环境:', process.env.NODE_ENV)
console.log('API 地址:', API_BASE_URL)
console.log('================')
