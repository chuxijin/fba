# 设计系统使用指南

基于**腾讯 CoDesign 小程序设计规范**打造的设计系统。

## 📁 文件结构

```
miniprogram/
├── styles/
│   ├── design-tokens.scss    # 设计 Token（颜色、间距、字号等变量）
│   ├── mixins.scss           # SCSS Mixin（可复用的样式逻辑）
│   ├── utilities.scss        # 工具类（快速开发的 CSS 类）
│   └── index.scss            # 主入口文件
├── App.vue                   # 全局样式 + 工具类
��── uni.scss                  # UniApp 变量（自动注入所有页面）
```

---

## 🎨 一、设计 Token

### 色彩系统

符合 WCAG 对比度标准（≥ 4.5:1）

```scss
// 主色（品牌色 - 绿色主题）
$color-primary: #22c55e;
$color-primary-light: #34d399;
$color-primary-dark: #16a34a;

// 文本色
$color-text-primary: #1f2937;    // 主要文本（对比度 13.8:1）
$color-text-secondary: #4b5563;  // 次要文本（对比度 7.3:1）
$color-text-muted: #94a3b8;      // 辅助文本

// 语义色
$color-success: #16a34a;
$color-warning: #f59e0b;
$color-error: #ef4444;
$color-info: #3b82f6;

// 渐变色
$gradient-primary: linear-gradient(90deg, #34d399 0%, #22c55e 100%);
```

### 字体系统

符合设计规范的字体大小标准：
- 标题：18-24px (36-48rpx)
- 正文：14-16px (28-32rpx)
- 辅助文本：12px (24rpx)

```scss
// 字体大小
$font-size-xs: 20rpx;     // 10px - 标签
$font-size-sm: 24rpx;     // 12px - 辅助文本
$font-size-base: 28rpx;   // 14px - 基础文本
$font-size-lg: 32rpx;     // 16px - 大文本
$font-size-xl: 36rpx;     // 18px - 小标题
$font-size-2xl: 40rpx;    // 20px - 标题
$font-size-3xl: 48rpx;    // 24px - 大标题

// 字体粗细
$font-weight-normal: 400;
$font-weight-medium: 500;
$font-weight-semibold: 600;
$font-weight-bold: 700;

// 行高（规范建议 1.5 倍）
$line-height-normal: 1.5;
```

### 间距系统

统一间距标准：8px、12px、16px

```scss
$spacing-xs: 8rpx;      // 4px
$spacing-sm: 16rpx;     // 8px  ✅ 符合规范
$spacing-base: 24rpx;   // 12px ✅ 符合规范
$spacing-md: 32rpx;     // 16px ✅ 符合规范
$spacing-lg: 48rpx;     // 24px
$spacing-xl: 64rpx;     // 32px
```

### 图标规范

符合设计规范：24px、32px、48px

```scss
$icon-size-sm: 48rpx;    // 24px ✅ 符合规范
$icon-size-base: 64rpx;  // 32px ✅ 符合规范
$icon-size-lg: 96rpx;    // 48px ✅ 符合规范

// 图标与文本间距
$icon-text-gap: 16rpx;   // 8px ✅ 符合规范
```

### 交互规范

```scss
// 最小点击区域（规范要求 44px × 44px）
$tap-area-min: 88rpx;    // 44px ✅ 符合规范

// 圆角（圆角矩形按钮）
$radius-sm: 16rpx;       // 8px  - 按钮、输入框
$radius-base: 24rpx;     // 12px - 卡片
$radius-lg: 32rpx;       // 16px - 大卡片
```

---

## 🛠️ 二、Mixins 使用

### 方式 1：在 `<script setup>` 中使用（推荐）

```vue
<style scoped lang="scss">
// 自动可用，无需导入（已在 uni.scss 中全局注入）

.my-card {
  @include card;  // 应用��片样式
}

.my-button {
  @include button-primary;  // 应用主按钮样式
}

.center-box {
  @include flex-center;  // 应用居中布局
}

.multi-line-text {
  @include text-line-clamp(2);  // 两行文本截断
}
</style>
```

### 方式 2：在独立 `.scss` 文件中使用

```scss
// 需要手动导入
@import '@/styles/mixins.scss';

.custom-component {
  @include card($padding: 48rpx, $radius: 48rpx);
}
```

### 常用 Mixins

#### 布局类

```scss
// Flex 居中
@include flex-center;

// Flex 两端对齐
@include flex-between;

// Flex 垂直布局
@include flex-column;

// Grid 等宽列
@include grid-equal(3, 24rpx);  // 3 列，间距 24rpx

// 绝对定位居中
@include absolute-center;
```

#### 文本类

```scss
// 单行截断
@include text-ellipsis;

// 多行截断
@include text-line-clamp(2);  // 显示 2 行

// 快速文本样式
@include text($font-size-lg, $font-weight-bold, $color-primary);
```

#### 外观类

```scss
// 卡片样式
@include card;  // 默认参数
@include card($padding: 48rpx, $radius: 48rpx, $shadow: false);  // 自定义参数

// 按钮样式
@include button-primary;   // 主按钮
@include button-secondary; // 次要按钮

// 圆形头像
@include avatar(96rpx);  // 96rpx 尺寸的头像
```

#### 交互类

```scss
// 点击反馈
@include tap-feedback;  // 默认 0.98 缩放
@include tap-feedback(0.95);  // 自定义缩放比例

// 悬停效果（仅 H5）
@include hover-lift;

// 渐变文字
@include gradient-text($gradient-primary);
```

---

## 🎯 三、工具类使用

工具类已全局注入到 `App.vue`，无需导入，直接在模板中使用。

### 布局类

```vue
<!-- Flex 布局 -->
<view class="flex-center">居中内容</view>
<view class="flex-between">两端对齐</view>
<view class="flex-column gap-base">垂直布局 + 24rpx 间距</view>

<!-- 对齐 -->
<view class="flex items-start justify-end">上对齐 + 右对齐</view>
```

### 间距类

```vue
<!-- Padding -->
<view class="p-lg">所有方向 48rpx 内边距</view>
<view class="pt-md pb-lg">上 32rpx，下 48rpx</view>

<!-- Margin -->
<view class="mt-lg mb-base">上 48rpx，下 24rpx</view>

<!-- Gap -->
<view class="flex gap-lg">子元素间距 48rpx</view>
```

### 文本类

```vue
<!-- 字体大小 -->
<text class="text-2xl font-bold">大标题</text>
<text class="text-base font-normal">正文</text>
<text class="text-sm text-muted">辅助文字</text>

<!-- 文本颜色 -->
<text class="text-primary">主要文本</text>
<text class="text-success">成功提示</text>
<text class="text-error">错误提示</text>

<!-- 文本截断 -->
<text class="ellipsis">单行截断...</text>
<text class="line-clamp-2">两行截断...</text>
```

### 颜色类

```vue
<!-- 背景色 -->
<view class="bg-card">卡片背景</view>
<view class="bg-gradient-primary">渐变背景</view>

<!-- 边框 -->
<view class="border rounded-lg">带边框圆角</view>
<view class="border-primary rounded-full">主色边框 + 圆形</view>
```

### 自定义组件类

```vue
<!-- 卡片 -->
<view class="card p-lg">
  卡片内容
</view>

<!-- 按钮 -->
<button class="btn btn-primary">主按钮</button>
<button class="btn btn-secondary">次要按钮</button>

<!-- 徽章 -->
<view class="badge badge-free">🆓</view>
<view class="badge badge-vip">💎</view>

<!-- 分隔线 -->
<view class="divider"></view>

<!-- 安全区域 -->
<view class="safe-area-bottom">底部安全区域</view>
```

---

## 📝 四、在页面中使用

### 示例 1：使用工具类（快速开发）

```vue
<template>
  <view class="page">
    <!-- 卡片 -->
    <view class="card p-lg mb-base">
      <view class="flex-between mb-base">
        <text class="text-xl font-bold">标题</text>
        <text class="text-sm text-muted">副标题</text>
      </view>
      <text class="text-base line-clamp-2">这是内容...</text>
    </view>

    <!-- 按钮 -->
    <button class="btn btn-primary">确定</button>
  </view>
</template>

<style scoped lang="scss">
.page {
  padding: 48rpx 32rpx;
  background: $gradient-page-bg;
  min-height: 100vh;
}
</style>
```

### 示例 2：使用 Mixins（自定义样式）

```vue
<template>
  <view class="custom-card">
    <view class="title">自定义卡片</view>
    <view class="content">内容...</view>
  </view>
</template>

<style scoped lang="scss">
.custom-card {
  @include card($padding: 48rpx);
  margin-bottom: $spacing-lg;

  .title {
    @include text($font-size-2xl, $font-weight-bold, $color-primary);
    margin-bottom: $spacing-base;
  }

  .content {
    @include text-line-clamp(3);
    color: $color-text-secondary;
  }
}
</style>
```

### 示例 3：混合使用

```vue
<template>
  <!-- 工具类 + 自定义样式 -->
  <view class="flex-column gap-base custom-page">
    <view class="card p-lg">卡片 1</view>
    <view class="card p-lg">卡片 2</view>
  </view>
</template>

<style scoped lang="scss">
.custom-page {
  padding: $spacing-lg;
  background: $gradient-page-bg;

  // 自定义卡片悬停效果
  .card {
    @include tap-feedback;
  }
}
</style>
```

---

## 🎨 五、设计规范对照表

| 项目 | 设计规范要求 | 本项目实现 | 状态 |
|------|------------|----------|------|
| **色彩** |
| 文本对比度 | ≥ 4.5:1 | 主文本 13.8:1 | ✅ |
| 主色用途 | 导航栏、按钮、重要信息 | `$color-primary` | ✅ |
| **字体** |
| 标题 | 18-24px | 36-48rpx | ✅ |
| 正文 | 14-16px | 28-32rpx | ✅ |
| 辅助文本 | 12px | 24rpx | ✅ |
| 行高 | 字号的 1.5 倍 | `$line-height-normal: 1.5` | ✅ |
| **图标** |
| 尺寸 | 24px、32px、48px | 48rpx、64rpx、96rpx | ✅ |
| 与文本间距 | 8px | 16rpx (8px) | ✅ |
| **组件** |
| 最小点击区域 | 44px × 44px | 88rpx × 88rpx | ✅ |
| 间距 | 8px、12px、16px | 16rpx、24rpx、32rpx | ✅ |
| 按钮样式 | 圆角矩形 | `border-radius: 28rpx` | ✅ |
| **TabBar** |
| 导航项数量 | 3-5 个 | 4 个（首页/练习/学习/我的） | ✅ |
| 图标文本 | 清晰易懂 | 待实现 | ⏸️ |

---

## 💡 最佳实践

### 1. 优先使用工具类

```vue
<!-- ✅ 推荐：快速开发 -->
<view class="card p-lg mb-base">

<!-- ❌ 不推荐：重复写样式 -->
<view style="background: #fff; padding: 48rpx; margin-bottom: 24rpx;">
```

### 2. 复杂样式使用 Mixins

```vue
<style scoped lang="scss">
/* ✅ 推荐：可维护 */
.custom-card {
  @include card;
  @include tap-feedback;
}

/* ❌ 不推荐：难维护 */
.custom-card {
  background: #fff;
  border-radius: 32rpx;
  box-shadow: 0 20rpx 48rpx rgba(34, 197, 94, 0.12);
  transition: transform 0.2s ease;
  &:active {
    transform: scale(0.98);
  }
}
</style>
```

### 3. 保持设计一致性

```vue
<!-- ✅ 推荐：使用统一的间距变量 -->
<view :style="{ padding: $spacing-lg + 'rpx' }">

<!-- ❌ 不推荐：随意使用数值 -->
<view style="padding: 50rpx;">
```

---

## 📚 参考资料

- [腾讯 CoDesign 小程序设计规范](https://codesign.qq.com/hc/article/design-system-mini-program/)
- [微信小程序设计指南](https://developers.weixin.qq.com/miniprogram/design/)
- [UniApp 样式文档](https://uniapp.dcloud.net.cn/tutorial/syntax-css.html)
