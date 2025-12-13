<template>
  <view class="profile-page">
    <!-- 头像和基本信息 -->
    <view class="header-section">
      <button class="avatar-button" open-type="chooseAvatar" @chooseavatar="onChooseAvatar">
        <image
          class="avatar"
          :src="userInfo.avatar || DEFAULT_AVATAR"
          mode="aspectFill"
        />
        <view class="avatar-edit-tip">
          <text class="edit-icon">✎</text>
        </view>
      </button>
    </view>

    <!-- 个人信息列表 -->
    <view class="info-section">
      <view class="info-item" @tap="handleEditNickname">
        <text class="info-label">昵称</text>
        <view class="info-value-row">
          <text class="info-value">{{ userInfo.nickname || '未设置' }}</text>
          <text class="arrow">›</text>
        </view>
      </view>

      <view class="info-item">
        <text class="info-label">用户名</text>
        <view class="info-value-row">
          <text class="info-value gray">{{ userInfo.username || '未设置' }}</text>
        </view>
      </view>

      <view class="info-item">
        <text class="info-label">微信绑定</text>
        <view class="info-value-row">
          <text class="info-value" :class="{ success: isWxBound }">
            {{ isWxBound ? '已绑定' : '未绑定' }}
          </text>
          <text v-if="!isWxBound" class="arrow">›</text>
        </view>
      </view>
    </view>

    <!-- 功能列表 -->
    <view class="function-section">
      <view class="function-item" @tap="handleChangePassword">
        <text class="function-label">修改密码</text>
        <text class="arrow">›</text>
      </view>

      <view class="function-item" @tap="handleManageAddress">
        <text class="function-label">收货地址</text>
        <text class="arrow">›</text>
      </view>
    </view>

    <!-- 底部按钮 -->
    <view class="bottom-actions">
      <button class="action-button secondary" @tap="handleSwitchAccount">
        切换账号
      </button>
      <button class="action-button danger" @tap="handleLogout">
        退出登录
      </button>
    </view>

    <!-- 昵称编辑弹窗 -->
    <view v-if="showNicknameModal" class="modal-overlay" @tap="showNicknameModal = false">
      <view class="modal-content" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">修改昵称</text>
          <text class="modal-close" @tap="showNicknameModal = false">✕</text>
        </view>
        <input
          v-model="editNickname"
          type="nickname"
          class="modal-input"
          placeholder="请输入昵称"
          maxlength="20"
        />
        <view class="modal-buttons">
          <button class="modal-button cancel" @tap="showNicknameModal = false">
            取消
          </button>
          <button class="modal-button confirm" @tap="handleSaveNickname">
            保存
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '../../stores/user'
import { API_BASE_URL, DEFAULT_AVATAR } from '../../config/api'

declare const uni: any

const userStore = useUserStore()

interface UserInfo {
  id?: number
  username?: string
  nickname?: string
  avatar?: string
  phone?: string
  open_id?: string
}

// 用户信息从 store 获取
const userInfo = computed(() => userStore.userInfo || {})
const isWxBound = computed(() => !!userInfo.value.open_id)

// 昵称编辑
const showNicknameModal = ref<boolean>(false)
const editNickname = ref<string>('')

/**
 * 页面加载
 */
onMounted(async () => {
  // 从 store 加载用户信息（如果 store 为空会自动从后端获取）
  await userStore.fetchUserInfo()
})

/**
 * 选择头像
 */
async function onChooseAvatar(e: any) {
  const { avatarUrl } = e.detail
  if (!avatarUrl) return

  try {
    console.log('开始上传头像:', avatarUrl)

    // 上传头像到服务器
    const uploadRes = await uni.uploadFile({
      url: `${API_BASE_URL}/qbank/upload/avatar`,
      filePath: avatarUrl,
      name: 'file',
      header: {
        Authorization: `Bearer ${uni.getStorageSync('access_token')}`
      }
    })

    const res = uploadRes[1] || uploadRes
    console.log('[个人资料页] 上传响应:', res)

    if (res.statusCode === 200) {
      const data = JSON.parse(res.data)
      console.log('[个人资料页] 上传返回数据:', data)

      if (data.code === 200 && data.data && data.data.url) {
        console.log('[个人资料页] 上传成功，新头像 URL:', data.data.url)
        console.log('[个人资料页] 开始刷新用户信息...')

        // ✅ 刷新 store 状态（强制从后端重新获取）
        await userStore.refreshUserInfo()

        console.log('[个人资料页] 刷新后的用户信息:', userStore.userInfo)
        console.log('[个人资料页] 刷新后的头像:', userStore.userInfo?.avatar)

        uni.showToast({
          title: '头像更新成功',
          icon: 'success'
        })
      } else {
        throw new Error(data.msg || '上传失败')
      }
    } else {
      throw new Error(`HTTP ${res.statusCode}`)
    }
  } catch (error: any) {
    console.error('头像上传失败:', error)
    uni.showToast({
      title: error.message || '头像上传失败',
      icon: 'none'
    })
  }
}

/**
 * 编辑昵称
 */
function handleEditNickname() {
  editNickname.value = userInfo.value.nickname || ''
  showNicknameModal.value = true
}

/**
 * 保存昵称
 */
async function handleSaveNickname() {
  if (!editNickname.value.trim()) {
    uni.showToast({
      title: '昵称不能为空',
      icon: 'none'
    })
    return
  }

  try {
    // ✅ 调用后端接口更新昵称
    const res = await uni.request({
      url: `${API_BASE_URL}/qbank/customer/profile`,
      method: 'PUT',
      header: {
        Authorization: `Bearer ${uni.getStorageSync('access_token')}`
      },
      data: {
        nickname: editNickname.value
      }
    })

    const response = res[1] || res
    if (response.statusCode === 200 && response.data.code === 200) {
      // ✅ 刷新 store 状态
      await userStore.refreshUserInfo()

      showNicknameModal.value = false
      uni.showToast({
        title: '昵称修改成功',
        icon: 'success'
      })

      console.log('[个人资料页] 昵称更新成功，已刷新 store')
    } else {
      throw new Error(response.data?.msg || '更新失败')
    }
  } catch (error: any) {
    console.error('保存昵称失败:', error)
    uni.showToast({
      title: error.message || '保存失败',
      icon: 'none'
    })
  }
}

/**
 * 修改密码
 */
function handleChangePassword() {
  uni.showToast({
    title: '功能开发中',
    icon: 'none'
  })
}

/**
 * 管理收货地址
 */
function handleManageAddress() {
  uni.showToast({
    title: '功能开发中',
    icon: 'none'
  })
}

/**
 * 切换账号
 */
function handleSwitchAccount() {
  uni.showModal({
    title: '切换账号',
    content: '确定要切换账号吗？',
    success: (res: any) => {
      if (res.confirm) {
        // ✅ 调用 store 的 logout 方法
        userStore.logout()

        uni.showToast({
          title: '已退出当前账号',
          icon: 'success',
          duration: 1500
        })

        // 返回上一页（个人中心）
        setTimeout(() => {
          uni.navigateBack()
        }, 1500)

        console.log('[个人资料页] 已切换账号')
      }
    }
  })
}

/**
 * 退出登录
 */
function handleLogout() {
  uni.showModal({
    title: '退出登录',
    content: '确定要退出登录吗？',
    success: (res: any) => {
      if (res.confirm) {
        // ✅ 调用 store 的 logout 方法
        userStore.logout()

        uni.showToast({
          title: '已退出登录',
          icon: 'success',
          duration: 1500
        })

        // 返回上一页（个人中心）
        setTimeout(() => {
          uni.navigateBack()
        }, 1500)

        console.log('[个人资料页] 已退出登录')
      }
    }
  })
}
</script>

<style scoped lang="scss">
.profile-page {
  min-height: 100vh;
  background-color: #f5f7fa;
  padding-bottom: 40rpx;
}

/* ==================== 头像区域 ==================== */
.header-section {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 60rpx 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.avatar-button {
  position: relative;
  padding: 0;
  background: none;
  border: none;

  &::after {
    border: none;
  }
}

.avatar {
  width: 160rpx;
  height: 160rpx;
  border-radius: 50%;
  border: 6rpx solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.2);
}

.avatar-edit-tip {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 48rpx;
  height: 48rpx;
  background-color: #667eea;
  border-radius: 50%;
  border: 4rpx solid #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.edit-icon {
  font-size: 24rpx;
  color: #ffffff;
}

/* ==================== 信息列表 ==================== */
.info-section,
.function-section {
  margin: 24rpx 28rpx;
  background-color: #ffffff;
  border-radius: 16rpx;
  overflow: hidden;
}

.info-item,
.function-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 32rpx;
  border-bottom: 1rpx solid #f0f0f0;

  &:last-child {
    border-bottom: none;
  }

  &:active {
    background-color: #f8f8f8;
  }
}

.info-label,
.function-label {
  font-size: 28rpx;
  color: #333333;
}

.info-value-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.info-value {
  font-size: 28rpx;
  color: #666666;

  &.gray {
    color: #999999;
  }

  &.success {
    color: #52c41a;
  }
}

.arrow {
  font-size: 40rpx;
  color: #cccccc;
  font-weight: 300;
}

/* ==================== 底部按钮 ==================== */
.bottom-actions {
  margin: 24rpx 28rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.action-button {
  width: 100%;
  height: 88rpx;
  border-radius: 44rpx;
  font-size: 32rpx;
  font-weight: 600;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;

  &::after {
    border: none;
  }

  &.secondary {
    background-color: #ffffff;
    color: #667eea;
    border: 2rpx solid #667eea;
  }

  &.danger {
    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
    color: #ffffff;
    box-shadow: 0 8rpx 24rpx rgba(255, 107, 107, 0.3);
  }

  &:active {
    opacity: 0.8;
    transform: scale(0.98);
  }
}

/* ==================== 昵称编辑弹窗 ==================== */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-content {
  width: 600rpx;
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32rpx;
}

.modal-title {
  font-size: 36rpx;
  font-weight: 600;
  color: #333333;
}

.modal-close {
  font-size: 40rpx;
  color: #999999;
  cursor: pointer;
}

.modal-input {
  width: 100%;
  height: 88rpx;
  background-color: #f5f5f5;
  border-radius: 16rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
  color: #333333;
  margin-bottom: 32rpx;
  box-sizing: border-box;
}

.modal-buttons {
  display: flex;
  gap: 20rpx;
}

.modal-button {
  flex: 1;
  height: 80rpx;
  border-radius: 40rpx;
  font-size: 30rpx;
  border: none;

  &::after {
    border: none;
  }

  &.cancel {
    background-color: #f0f0f0;
    color: #666666;
  }

  &.confirm {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #ffffff;
  }

  &:active {
    opacity: 0.8;
  }
}
</style>
