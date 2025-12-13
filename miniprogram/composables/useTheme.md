# 主题管理 Composable 使用指南

## 功能介绍

`useTheme` 是一个全局主题管理的组合式函数（Composable），提供明暗主题切换功能。

## 特性

- ✅ 全局状态共享（所有组件使用同一个主题状态）
- ✅ 自动持久化（刷新后保持主题设置）
- ✅ DOM 同步（自动更新 `data-theme` 属性）
- ✅ 单例模式（只初始化一次）

## 基础用法

```typescript
import { useTheme } from '@/composables/useTheme'

// 在组件中使用
const { isDarkMode, toggleTheme, setTheme, getCurrentTheme } = useTheme()
```

## API

### isDarkMode
- 类型: `Ref<boolean>`
- 说明: 当前是否为深色模式（响应式）

### toggleTheme()
- 类型: `() => void`
- 说明: 切换主题（明暗互换）

### setTheme(theme)
- 类型: `(theme: 'light' | 'dark') => void`
- 说明: 设置指定主题

### getCurrentTheme()
- 类型: `() => 'light' | 'dark'`
- 说明: 获取当前主题

## 使用示例

### 示例 1：刷题页面头部（HeaderPanel.vue）

```vue
<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'

const { isDarkMode, toggleTheme } = useTheme()
</script>

<template>
  <view class="header" @tap="toggleTheme">
    <ThemeIcon :is-dark="isDarkMode" />
  </view>
</template>
```

### 示例 2：我的页面（mine/index.vue）

```vue
<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'

const { isDarkMode, toggleTheme } = useTheme()

function handleThemeToggle() {
  toggleTheme()
  uni.showToast({
    title: isDarkMode.value ? '已切换到深色模式' : '已切换到浅色模式',
    icon: 'none'
  })
}
</script>
```

### 示例 3：设置页面（带开关）

```vue
<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'

const { isDarkMode, setTheme } = useTheme()

function handleSwitchChange(enabled: boolean) {
  setTheme(enabled ? 'dark' : 'light')
}
</script>

<template>
  <view class="setting-item">
    <text>深色模式</text>
    <switch :checked="isDarkMode" @change="handleSwitchChange" />
  </view>
</template>
```

## 注意事项

1. **无需重复初始化**: `useTheme()` 内部自动初始化，多次调用不会重复初始化
2. **状态共享**: 所有使用 `useTheme()` 的组件共享同一个 `isDarkMode` 状态
3. **自动持久化**: 主题变更会自动保存到 `uni.storage`，刷新后保持
4. **DOM 同步**: 自动更新 `document.body` 的 `data-theme` 属性

## 技术原理

- 使用 Vue 3 的 `ref` 创建响应式状态
- 通过模块级变量实现单例模式
- 监听存储和 DOM 变化，确保状态一致性
