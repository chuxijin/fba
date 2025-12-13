# 微信小程序开放能力使用规划

## 已实现的微信能力

### 1. 客服会话 (open-type="contact")
**位置**: `pages/mine/index.vue` - 更多服务 → 联系客服

**实现方式**:
```vue
<button
  open-type="contact"
  session-from="user-center"
>
  联系客服
</button>
```

**使用场景**: 用户遇到问题时，可以直接通过微信客服消息与客服沟通

---

## 待实现的微信能力

### 2. 获取用户信息 (open-type="getUserInfo")
**建议位置**:
- `pages/mine/index.vue` - 用户头像区域（未登录状态）
- `components/auth/LoginModal.vue` - 登录弹窗

**实现方式**:
```vue
<u-button
  text="微信授权登录"
  open-type="getUserInfo"
  @getuserinfo="handleGetUserInfo"
/>
```

**回调处理**:
```typescript
function handleGetUserInfo(e: any) {
  const userInfo = e.detail.userInfo
  if (userInfo) {
    // 发送到后端验证并创建用户
    console.log('用户信息:', userInfo)
  }
}
```

---

### 3. 获取手机号 (open-type="getPhoneNumber")
**建议位置**:
- `pages/mine/index.vue` - 快捷功能 → VIP会员
- 购买题库流程
- 需要实名认证的功能

**实现方式**:
```vue
<u-button
  text="绑定手机号"
  open-type="getPhoneNumber"
  @getphonenumber="handleGetPhoneNumber"
/>
```

**回调处理**:
```typescript
function handleGetPhoneNumber(e: any) {
  const { code, encryptedData, iv } = e.detail
  if (code) {
    // 发送到后端解密获取手机号
    // POST /api/user/bind-phone
    // { code, encryptedData, iv }
  }
}
```

---

### 4. 分享功能 (open-type="share")
**建议位置**:
- `pages/practice/bank-detail.vue` - 题库详情页（分享题库）
- `pages/practice/ResultSummary.vue` - 答题结果（分享成绩）
- `pages/mine/index.vue` - 快捷功能 → 种草、代理推广

**实现方式**:
```vue
<u-button
  text="分享给好友"
  open-type="share"
/>
```

**配置分享内容** (在页面的 `onShareAppMessage` 中):
```typescript
// pages/practice/bank-detail.vue
onShareAppMessage(() => {
  return {
    title: `${bank.value.name} - 一起来刷题吧！`,
    path: `/pages/practice/bank-detail?bankId=${bank.value.id}`,
    imageUrl: bank.value.cover_url || '/static/images/share-default.png'
  }
})
```

---

### 5. 转发到朋友圈 (open-type="shareTimeline")
**建议位置**:
- 学习成就分享
- 打卡记录分享

**实现方式**:
```vue
<u-button
  text="分享到朋友圈"
  open-type="shareTimeline"
/>
```

**配置分享内容** (在页面的 `onShareTimeline` 中):
```typescript
onShareTimeline(() => {
  return {
    title: '我已连续打卡7天，一起来学习吧！',
    query: 'inviteCode=xxx',
    imageUrl: '/static/images/share-achievement.png'
  }
})
```

---

### 6. 打开设置页 (open-type="openSetting")
**建议位置**:
- `pages/mine/index.vue` - 更多服务 → 设置
- 权限被拒绝后的引导页面

**实现方式**:
```vue
<u-button
  text="打开设置"
  open-type="openSetting"
  @opensetting="handleOpenSetting"
/>
```

**回调处理**:
```typescript
function handleOpenSetting(e: any) {
  const authSetting = e.detail.authSetting
  if (authSetting['scope.userInfo']) {
    console.log('用户已授权个人信息')
  }
}
```

---

### 7. 打开客服会话（按钮方式）
**建议位置**:
- `pages/practice/bank-detail.vue` - 题库详情（遇到问题）
- `components/business/MaterialCard.vue` - 资料卡片（下载问题）

**实现方式**:
```vue
<u-button
  text="遇到问题？联系客服"
  size="small"
  plain
  open-type="contact"
  session-from="bank-detail"
  send-message-title="题库相关问题"
  :send-message-path="`/pages/practice/bank-detail?bankId=${bankId}`"
/>
```

---

### 8. 订阅消息 (open-type="subscribe")
**建议位置**:
- 每日刷题提醒
- 学习计划提醒
- VIP到期提醒

**实现方式**:
```vue
<u-button
  text="开启每日提醒"
  open-type="subscribe"
  :template-id="['模板ID1', '模板ID2']"
  @subscribeMessage="handleSubscribe"
/>
```

**回调处理**:
```typescript
function handleSubscribe(e: any) {
  const { errMsg, templateId } = e.detail
  if (errMsg === 'subscribeMessage:ok') {
    console.log('订阅成功:', templateId)
  }
}
```

---

## 功能与微信能力对应表

| 功能模块 | 微信能力 | 优先级 | 位置 |
|---------|---------|-------|------|
| 用户登录 | getUserInfo | ⭐⭐⭐ 高 | LoginModal.vue |
| 手机号绑定 | getPhoneNumber | ⭐⭐⭐ 高 | VIP购买流程 |
| 联系客服 | contact | ⭐⭐⭐ 高 | mine/index.vue ✅ |
| 分享题库 | share | ⭐⭐ 中 | bank-detail.vue |
| 分享成绩 | share | ⭐⭐ 中 | ResultSummary.vue |
| 邀请好友 | share | ⭐⭐ 中 | mine/index.vue |
| 每日提醒 | subscribe | ⭐ 低 | 设置页面 |
| 打开设置 | openSetting | ⭐ 低 | 权限引导页 |

---

## 后端配置要求

### 1. 客服消息配置
- 微信公众平台 → 功能 → 客服消息
- 添加客服账号
- 配置客服消息推送URL

### 2. 订阅消息模板
- 微信公众平台 → 功能 → 订阅消息
- 申请模板：
  - 每日刷题提醒
  - 学习计划提醒
  - VIP到期提醒

### 3. 隐私协议
需要在小程序中配置用户隐私保护指引，说明：
- 收集手机号的用途
- 用户信息的使用范围
- 数据安全措施

---

## 开发建议

1. **渐进式实现**: 先实现高优先级功能（登录、客服、手机号）
2. **统一封装**: 创建 `composables/useWechatOpenAPI.ts` 统一管理微信能力调用
3. **错误处理**: 用户拒绝授权时的友好提示
4. **降级方案**: 部分功能在用户拒绝授权时提供替代方案

---

## 示例：统一封装微信能力

```typescript
// composables/useWechatOpenAPI.ts
export function useWechatOpenAPI() {
  /**
   * 获取用户信息
   */
  const getUserInfo = async () => {
    return new Promise((resolve, reject) => {
      uni.getUserProfile({
        desc: '用于完善用户资料',
        success: (res) => resolve(res.userInfo),
        fail: (err) => reject(err)
      })
    })
  }

  /**
   * 获取手机号
   */
  const getPhoneNumber = async (code: string) => {
    // 调用后端接口解密
    return await fetch('/api/user/decrypt-phone', {
      method: 'POST',
      body: JSON.stringify({ code })
    })
  }

  /**
   * 订阅消息
   */
  const subscribeMessage = async (templateIds: string[]) => {
    return new Promise((resolve, reject) => {
      uni.requestSubscribeMessage({
        tmplIds: templateIds,
        success: (res) => resolve(res),
        fail: (err) => reject(err)
      })
    })
  }

  return {
    getUserInfo,
    getPhoneNumber,
    subscribeMessage
  }
}
```

---

**最后更新**: 2025-12-09
**维护者**: 开发团队
