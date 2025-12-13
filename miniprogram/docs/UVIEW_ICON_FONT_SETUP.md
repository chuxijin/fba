# UView Plus 图标字体离线配置指南

## 问题说明

微信小程序开发工具中可能出现字体加载失败的警告：
```
Failed to load font https://at.alicdn.com/t/font_2225171_8kdcwk4po24.ttf
```

这是因为：
1. 网络请求失败
2. 开发环境跨域限制
3. CDN 访问受限

## 解决方案

### 方案一：配置仅加载一次（已配置✅��

在 `main.js` 中已配置：
```javascript
app.use(uviewPlus, {
  config: {
    loadFontOnce: true  // 只在全局加载一次
  }
})
```

**优点**：无需下载文件，减少重复请求
**缺点**：仍需网络，首次加载可能失败

---

### 方案二：���用本地字体文件（完全离线）

#### 步骤 1：下载字体文件

**方式 A - 直接下载**：
1. 访问：https://at.alicdn.com/t/font_2225171_8kdcwk4po24.ttf
2. 保存到：`miniprogram/static/fonts/uview-icon.ttf`

**方式 B - 使用 curl（推荐）**：
```bash
# 创建字体目录
mkdir -p miniprogram/static/fonts

# 下载字体文件
curl -o miniprogram/static/fonts/uview-icon.ttf \
  https://at.alicdn.com/t/font_2225171_8kdcwk4po24.ttf
```

#### 步骤 2：配置使用本地字体

修改 `main.js`：
```javascript
// #ifdef VUE3
import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import uviewPlus from 'uview-plus'

export function createApp() {
  const app = createSSRApp(App)
  const pinia = createPinia()

  app.use(pinia)

  // ✅ 配置使用本地字体
  app.use(uviewPlus, {
    config: {
      loadFontOnce: true,
      // 使用本地字体文件路径
      iconUrl: '/static/fonts/uview-icon.ttf'
    }
  })

  return {
    app
  }
}
// #endif
```

#### 步骤 3：验证配置

重新编译小程序，字体加载失败的警告应该消失。

---

### 方��三：使用自己的 CDN（生产环境推荐）

如果您有自己的服务器或 OSS：

#### 步骤 1：上传字体文件到服务器
```bash
# 上传到阿里��� OSS / 腾讯云 COS / 自有服务器
# 示例路径：https://your-cdn.com/fonts/uview-icon.ttf
```

#### 步骤 2：配置 CDN 地址
```javascript
app.use(uviewPlus, {
  config: {
    loadFontOnce: true,
    iconUrl: 'https://your-cdn.com/fonts/uview-icon.ttf'
  }
})
```

**注意事项**：
- ✅ 必须使用 HTTPS
- ✅ 必须配置 CORS（允许小程序域名访问）
- ✅ 推荐使用 CDN 加速

---

## manifest.json 配置（可选）

如果使用在线字体，需要在 `manifest.json` 中配置合法域名：

```json
{
  "mp-weixin": {
    "permission": {
      "scope.userLocation": {
        "desc": "您的位置信息将用于小程序位置接口的效果展示"
      }
    },
    "requiredPrivateInfos": [],
    "downloadFile": {
      "timeout": 30000
    },
    // ✅ 配置字体文件合法域名
    "embeddedFonts": {
      "scope": "global",
      "urls": [
        "https://at.alicdn.com/t/font_2225171_8kdcwk4po24.ttf"
      ]
    }
  }
}
```

---

## 常见问题

### Q1：字体文件很大，会影响性能吗？
**A**：UView Plus 图标字体约 50-100KB���采用 woff/ttf 压缩格式，影响很小。配置 `loadFontOnce: true` 后只加载一次。

### Q2：开发环境加载失败，生产环境会有问题吗？
**A**：不会。开发环境的警告不影响功能，图标可能显示为乱码但不影响开发。生产环境配置好合法域名即可。

### Q3：可以使用自定义图标字体吗？
**A**：可以。配置 `customIcon`：
```javascript
config: {
  customIcon: {
    family: 'my-icon',
    url: '/static/fonts/my-icon.ttf'
  }
}
```

使用：
```vue
<u-icon customPrefix="my-icon" name="icon-name"></u-icon>
```

---

## 推荐配置（总结）

### 开发环境
```javascript
app.use(uviewPlus, {
  config: {
    loadFontOnce: true  // 减少网络请求即可
  }
})
```

### 生产环境
```javascript
app.use(uviewPlus, {
  config: {
    loadFontOnce: true,
    iconUrl: '/static/fonts/uview-icon.ttf'  // 使用本地字体
  }
})
```

或者使用 CDN：
```javascript
app.use(uviewPlus, {
  config: {
    loadFontOnce: true,
    iconUrl: 'https://your-cdn.com/fonts/uview-icon.ttf'
  }
})
```

---

**文档更新时间**：2025-12-09
**参考文档**：https://uview-plus.jiangruyi.com/components/icon.html
