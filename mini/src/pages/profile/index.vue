<script lang="ts" setup>
import { computed, ref } from 'vue'
import { fbaApi } from '@/api/sdk'
import { useTokenStore, useUserStore } from '@/store'
import { toLoginPage } from '@/utils/toLoginPage'
import { getEnvBaseUrl } from '@/utils'

defineOptions({
  name: 'Profile',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '个人资料',
  },
})

const DEFAULT_AVATAR = 'https://api.dicebear.com/7.x/notionists/svg?seed=Felix'

const userStore = useUserStore()
const tokenStore = useTokenStore()

const updatingAvatar = ref(false)
const updatingNickname = ref(false)
const switchingAccount = ref(false)

const userInfo = computed(() => userStore.userInfo || {})
const displayAvatar = computed(() => userInfo.value.avatar || DEFAULT_AVATAR)
const displayNickname = computed(() => userInfo.value.nickname || '微信用户')
const displayUsername = computed(() => userInfo.value.username || '-')
const loginMethodLabel = computed(() => {
  const username = String(userInfo.value.username || '').trim()
  if (!username) {
    return '未识别'
  }

  return username.startsWith('wx_') ? '微信登录' : '账号密码登录'
})
const { statusBarHeight } = uni.getSystemInfoSync()

function ensureLogin() {
  if (tokenStore.updateNowTime().hasLogin) {
    return true
  }
  toLoginPage()
  return false
}

function updateLocalUser(patch: Record<string, any>) {
  userStore.setUserInfo({
    ...userInfo.value,
    ...patch,
  })
}

async function uploadAvatarToOss(filePath: string): Promise<string> {
  const token = await tokenStore.tryGetValidToken()
  if (!token) {
    throw new Error('未登录')
  }

  const baseUrl = getEnvBaseUrl().replace(/\/+$/, '')
  const uploadUrl = `${baseUrl}/api/v1/oss/upload`

  return await new Promise<string>((resolve, reject) => {
    uni.uploadFile({
      url: uploadUrl,
      filePath,
      name: 'file',
      formData: {
        path: 'avatar/profile',
        use_signed_url: 'false',
      },
      header: {
        Authorization: `Bearer ${token}`,
      },
      success: (response) => {
        if (response.statusCode >= 400) {
          reject(new Error(`上传失败，状态码：${response.statusCode}`))
          return
        }
        try {
          const payload = typeof response.data === 'string'
            ? JSON.parse(response.data || '{}')
            : (response.data as any)
          const url = payload?.data?.url
          if (!url) {
            reject(new Error(payload?.msg || '上传结果缺少 URL'))
            return
          }
          resolve(url)
        }
        catch (error) {
          reject(error)
        }
      },
      fail: (error) => {
        console.error('[avatar-upload] fail', error)
        reject(error)
      },
    })
  })
}

async function onChooseAvatar(event: any) {
  if (!ensureLogin() || updatingAvatar.value) {
    return
  }

  const localAvatar = event?.detail?.avatarUrl
  if (!localAvatar) {
    uni.showToast({ title: '获取头像失败', icon: 'none' })
    return
  }

  updatingAvatar.value = true
  try {
    const avatarUrl = await uploadAvatarToOss(localAvatar)
    await fbaApi.admin.sys.user.updateMyAvatar(avatarUrl)
    updateLocalUser({ avatar: avatarUrl })
    uni.showToast({ title: '头像已更新', icon: 'success' })
  }
  catch (error) {
    console.error('更新头像失败:', error)
    uni.showToast({ title: '更新头像失败', icon: 'none' })
  }
  finally {
    updatingAvatar.value = false
  }
}

function handleEditNickname() {
  if (!ensureLogin() || updatingNickname.value) {
    return
  }

  uni.showModal({
    title: '修改昵称',
    editable: true,
    placeholderText: '请输入昵称',
    content: displayNickname.value,
    success: async (result) => {
      if (!result.confirm) {
        return
      }

      const nickname = String(result.content || '').trim()
      if (!nickname) {
        uni.showToast({ title: '昵称不能为空', icon: 'none' })
        return
      }

      updatingNickname.value = true
      try {
        await fbaApi.admin.sys.user.updateMyNickname(nickname)
        updateLocalUser({ nickname })
        uni.showToast({ title: '昵称已更新', icon: 'success' })
      }
      catch (error) {
        console.error('更新昵称失败:', error)
        uni.showToast({ title: '更新昵称失败', icon: 'none' })
      }
      finally {
        updatingNickname.value = false
      }
    },
  })
}

function handleChangePassword() {
  if (!ensureLogin()) {
    return
  }

  uni.showModal({
    title: '修改密码',
    editable: true,
    placeholderText: '请输入旧密码',
    success: async (res1) => {
      if (!res1.confirm)
        return
      const oldPassword = String(res1.content || '').trim()
      if (!oldPassword) {
        uni.showToast({ title: '旧密码不能为空', icon: 'none' })
        return
      }

      uni.showModal({
        title: '设置新密码',
        editable: true,
        placeholderText: '请输入新密码',
        success: async (res2) => {
          if (!res2.confirm)
            return
          const newPassword = String(res2.content || '').trim()
          if (!newPassword) {
            uni.showToast({ title: '新密码不能为空', icon: 'none' })
            return
          }

          uni.showModal({
            title: '确认新密码',
            editable: true,
            placeholderText: '请再次输入新密码',
            success: async (res3) => {
              if (!res3.confirm)
                return
              const confirmPassword = String(res3.content || '').trim()
              if (confirmPassword !== newPassword) {
                uni.showToast({ title: '两次密码不一致', icon: 'none' })
                return
              }

              try {
                await fbaApi.admin.sys.user.updateMyPassword({
                  old_password: oldPassword,
                  new_password: newPassword,
                  confirm_password: confirmPassword,
                })
                uni.showToast({ title: '密码已更新', icon: 'success' })
              }
              catch (error) {
                console.error('修改密码失败:', error)
                uni.showToast({ title: '修改密码失败，请检查旧密码', icon: 'none' })
              }
            },
          })
        },
      })
    },
  })
}

function handleBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.switchTab({ url: '/pages/mine/index' })
}

async function handleSwitchAccount() {
  if (switchingAccount.value) {
    return
  }

  switchingAccount.value = true
  try {
    await tokenStore.logout()
    uni.showToast({ title: '已退出登录', icon: 'success' })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/mine/index' })
    }, 300)
  }
  finally {
    switchingAccount.value = false
  }
}

onShow(() => {
  ensureLogin()
})
</script>

<template>
  <view class="relative min-h-screen overflow-hidden from-[#F3E8FF] via-[#F8F5FB] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="pointer-events-none absolute h-80 w-80 rounded-full bg-[#E9D5FF]/40 blur-[40px] -right-8 -top-12" />
    <view class="pointer-events-none absolute top-20 h-60 w-60 rounded-full bg-[#FBCFE8]/20 blur-[40px] -left-16" />

    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="h-11 flex items-center justify-between px-4">
        <view class="w-20 flex items-center" @click="handleBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">个人资料</text>
        <view class="w-20" />
      </view>
    </view>

    <view class="relative z-10 mt-6 px-4 pb-24 space-y-4">
      <view class="overflow-hidden border border-white/60 rounded-2xl bg-white/80 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <button open-type="chooseAvatar" class="profile-row-btn w-full" hover-class="none" @chooseavatar="onChooseAvatar">
          <view class="h-16 flex items-center justify-between px-4">
            <text class="text-[15px] text-[#1E293B] font-bold">头像</text>
            <view class="flex items-center">
              <text v-if="updatingAvatar" class="mr-2 text-[12px] text-[#7E22CE]">上传中...</text>
              <image class="h-12 w-12 border-2 border-white rounded-full bg-white shadow-sm" :src="displayAvatar" mode="aspectFill" />
            </view>
          </view>
        </button>

        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4" @click="handleEditNickname">
          <text class="text-[15px] text-[#1E293B] font-bold">昵称</text>
          <view class="flex items-center text-[#64748B]">
            <text class="text-[14px]">{{ displayNickname }}</text>
            <view class="i-carbon-chevron-right ml-1 text-lg" />
          </view>
        </view>
      </view>

      <view class="overflow-hidden border border-white/60 rounded-2xl bg-white/80 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="h-14 flex items-center justify-between px-4">
          <text class="text-[15px] text-[#1E293B] font-bold">用户名</text>
          <text class="text-[14px] text-[#64748B]">{{ displayUsername }}</text>
        </view>

        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4">
          <text class="text-[15px] text-[#1E293B] font-bold">登录方式</text>
          <view class="flex items-center text-[#64748B]">
            <text class="text-[14px]">{{ loginMethodLabel }}</text>
          </view>
        </view>

        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4" @click="handleChangePassword">
          <text class="text-[15px] text-[#1E293B] font-bold">修改密码</text>
          <view class="i-carbon-chevron-right text-lg text-[#64748B]" />
        </view>
      </view>

      <view
        class="h-14 flex items-center justify-center border border-white/60 rounded-2xl bg-white/80 text-[15px] text-[#7E22CE] font-bold shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md transition-transform active:scale-[0.99]"
        @click="handleSwitchAccount"
      >
        切换账号
      </view>
    </view>
  </view>
</template>

<style scoped>
.profile-row-btn {
  padding: 0;
  margin: 0;
  border: none;
  border-radius: 0;
  text-align: left;
  line-height: inherit;
  background: transparent;
}

.profile-row-btn::after {
  border: none;
}
</style>
