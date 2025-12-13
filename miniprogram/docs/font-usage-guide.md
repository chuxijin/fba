# 全局字体使用指南

## 📝 配置说明

全局字体已在以下文件中配置：
- **App.vue**: 全局样式和 CSS 变量
- **uni.scss**: SCSS 变量（可在任何 .scss 文件中使用）

---

## 🎯 使用方法

### 1. 在普通 CSS/SCSS 中使用 CSS 变量

```vue
<style scoped lang="scss">
.title {
  font-size: var(--font-size-xl);      // 36rpx
  font-weight: var(--font-weight-bold); // 700
}

.text {
  font-size: var(--font-size-base);    // 28rpx
  font-weight: var(--font-weight-normal); // 400
}
</style>
```

### 2. 在 SCSS 文件中使用 SCSS 变量

```vue
<style scoped lang="scss">
.title {
  font-size: $uni-font-size-xl;         // 36rpx
  font-weight: $uni-font-weight-bold;   // 700
  font-family: $uni-font-family-base;   // 系统字体
}

.code {
  font-family: $uni-font-family-mono;   // 等宽字体
}
</style>
```

---

## 📏 可用字体大小

| 变量名 | CSS 变量 | SCSS 变量 | 值 |
|--------|---------|----------|-----|
| 超小号 | `var(--font-size-xs)` | `$uni-font-size-xs` | 20rpx |
| 小号 | `var(--font-size-sm)` | `$uni-font-size-sm-rpx` | 24rpx |
| 基础 | `var(--font-size-base)` | `$uni-font-size-base-rpx` | 28rpx |
| 大号 | `var(--font-size-lg)` | `$uni-font-size-lg-rpx` | 32rpx |
| 超大号 | `var(--font-size-xl)` | `$uni-font-size-xl` | 36rpx |
| 2倍大 | `var(--font-size-2xl)` | `$uni-font-size-2xl` | 40rpx |
| 3倍大 | `var(--font-size-3xl)` | `$uni-font-size-3xl` | 48rpx |

---

## ⚖️ 可用字体粗细

| 名称 | CSS 变量 | SCSS 变量 | 值 |
|------|---------|----------|-----|
| 细体 | `var(--font-weight-light)` | `$uni-font-weight-light` | 300 |
| 常规 | `var(--font-weight-normal)` | `$uni-font-weight-normal` | 400 |
| 中等 | `var(--font-weight-medium)` | `$uni-font-weight-medium` | 500 |
| 半粗 | `var(--font-weight-semibold)` | `$uni-font-weight-semibold` | 600 |
| 粗体 | `var(--font-weight-bold)` | `$uni-font-weight-bold` | 700 |

---

## 🔤 字体家族

```scss
// 默认系统字体（推荐）
font-family: $uni-font-family-base;

// 衬线字体（适合正式文档）
font-family: $uni-font-family-serif;

// 等宽字体（适合代码显示）
font-family: $uni-font-family-mono;
```

---

## 📐 行高

| 名称 | SCSS 变量 | 值 |
|------|----------|-----|
| 紧凑 | `$uni-line-height-tight` | 1.25 |
| 正常 | `$uni-line-height-normal` | 1.5 |
| 宽松 | `$uni-line-height-relaxed` | 1.75 |
| 超宽松 | `$uni-line-height-loose` | 2 |

---

## 🎨 完整示例

```vue
<template>
  <view class="demo-page">
    <text class="title">标题文字</text>
    <text class="subtitle">副标题文字</text>
    <text class="body">正文内容</text>
    <text class="caption">说明文字</text>
  </view>
</template>

<style scoped lang="scss">
.demo-page {
  padding: 32rpx;
}

.title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: #1f2937;
  margin-bottom: 16rpx;
}

.subtitle {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: #4b5563;
  margin-bottom: 12rpx;
}

.body {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-normal);
  line-height: 1.6;
  color: #6b7280;
  margin-bottom: 8rpx;
}

.caption {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-light);
  color: #9ca3af;
}
</style>
```

---

## 🌟 自定义字体（高级）

### 方法一：使用在线字体

```vue
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

page {
  font-family: 'Noto Sans SC', -apple-system, sans-serif;
}
</style>
```

### 方法二：使用本地字体

1. 将字体文件放在 `static/fonts/` 目录
2. 在 App.vue 中引入：

```vue
<style>
@font-face {
  font-family: 'CustomFont';
  src: url('/static/fonts/CustomFont.ttf') format('truetype');
  font-weight: normal;
  font-style: normal;
}

page {
  font-family: 'CustomFont', -apple-system, sans-serif;
}
</style>
```

---

## ⚠️ 注意事项

1. **小程序字体限制**：
   - 微信小程序限制字体文件大小（建议 < 2MB）
   - 字体加载会影响首屏渲染速度
   - 推荐使用系统默认字体

2. **性能优化**：
   - 优先使用系统字体
   - 如需自定义字体，使用 font-display: swap
   - 考虑字体子集化（只包含需要的文字）

3. **兼容性**：
   - iOS 优先使用 "PingFang SC"
   - Android 优先使用 "Microsoft YaHei"
   - 始终提供降级方案

---

## 📱 平台差异

不同平台的默认字体：

| 平台 | 默认字体 |
|------|---------|
| iOS | PingFang SC（苹方） |
| Android | Microsoft YaHei（微软雅黑）或 Roboto |
| 微信小程序 | 根据系统自动选择 |
| H5 | 根据浏览器自动选择 |

当前配置的 font-family 已自动适配各平台！
