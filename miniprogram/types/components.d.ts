/**
 * 组件相关类型定义
 */

/**
 * 组件尺寸
 */
export type ComponentSize = 'small' | 'medium' | 'large'

/**
 * 组件类型/主题
 */
export type ComponentType = 'primary' | 'success' | 'warning' | 'error' | 'info'

/**
 * 按钮类型
 */
export type ButtonType = ComponentType | 'default'

/**
 * 标签类型
 */
export type TagType = ComponentType | 'default'

/**
 * 加载状态
 */
export type LoadingState = 'idle' | 'loading' | 'success' | 'error'

/**
 * 排序方向
 */
export type SortOrder = 'asc' | 'desc' | null
