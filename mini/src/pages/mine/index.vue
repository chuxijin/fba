<script lang="ts" setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import LoginModal from '@/components/LoginModal.vue'
import { useTokenStore, useUserStore } from '@/store'
import {
  clearLoginRedirect,
  consumeLoginAutoOpen,
  redirectAfterLogin,
  setLoginRedirect,
} from '@/utils/toLoginPage'

defineOptions({
  name: 'Mine',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '用户中心',
  },
})

const userStore = useUserStore()
const tokenStore = useTokenStore()
const showLoginModal = ref(false)
const { statusBarHeight } = uni.getSystemInfoSync()
const DEFAULT_AVATAR = 'https://api.dicebear.com/7.x/notionists/svg?seed=Felix'

const hasLogin = computed(() => tokenStore.hasLogin)

const displayAvatar = computed(() => {
  if (!hasLogin.value) {
    return DEFAULT_AVATAR
  }

  return userStore.userInfo.avatar || DEFAULT_AVATAR
})

const displayNickname = computed(() => {
  if (!hasLogin.value) {
    return '未登录学员'
  }

  return userStore.userInfo.nickname || userStore.userInfo.username || '微信用户'
})

async function syncLoginState() {
  tokenStore.updateNowTime()

  if (!tokenStore.hasLogin) {
    return
  }

  const userId = Number(userStore.userInfo?.id || userStore.userInfo?.userId || 0)
  if (userId > 0) {
    return
  }

  try {
    await userStore.fetchUserInfo()
  }
  catch (error) {
    console.error('Sync mine user info error:', error)
  }
}

function maybeOpenLoginModal() {
  if (hasLogin.value || showLoginModal.value) {
    consumeLoginAutoOpen()
    return
  }

  if (consumeLoginAutoOpen()) {
    showLoginModal.value = true
  }
}

function handleLogin() {
  tokenStore.updateNowTime()
  if (!hasLogin.value) {
    clearLoginRedirect()
    showLoginModal.value = true
    return
  }

  uni.navigateTo({ url: '/pages/profile/index' })
}

function openServicePage(url: string) {
  tokenStore.updateNowTime()
  if (!hasLogin.value) {
    setLoginRedirect(url)
    showLoginModal.value = true
    return
  }

  uni.navigateTo({ url })
}

function openFeedbackPage() {
  uni.navigateTo({ url: '/pages/feedback/index' })
}

async function handleLoginSuccess() {
  await syncLoginState()
  redirectAfterLogin()
}

onShow(() => {
  void syncLoginState().finally(() => {
    maybeOpenLoginModal()
  })
})
</script>

<template>
  <view class="relative min-h-screen overflow-hidden from-[#F3E8FF] via-[#F8F5FB] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="pointer-events-none absolute h-80 w-80 rounded-full bg-[#E9D5FF]/40 blur-[40px] -right-8 -top-12" />
    <view class="pointer-events-none absolute top-20 h-60 w-60 rounded-full bg-[#FBCFE8]/20 blur-[40px] -left-16" />

    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="h-11 flex items-center justify-between px-4">
        <view class="w-20" />
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">用户中心</text>
        <view class="w-20" />
      </view>
    </view>

    <view class="relative z-10 mt-6 px-4 pb-14">
      <view class="mb-7 ml-1 flex items-center transition-transform active:scale-[0.98]" @click="handleLogin">
        <image
          class="h-16 w-16 border-[3px] border-white rounded-full bg-white shadow-sm"
          :src="displayAvatar"
          mode="aspectFill"
        />
        <view class="ml-4 flex-1">
          <view class="text-xl text-[#1E293B] font-bold">
            {{ displayNickname }}
          </view>
          <view class="mt-1.5 inline-block border border-[#E9D5FF] rounded-md bg-[#F3E8FF] px-2.5 py-0.5 text-[11px] text-[#7E22CE] font-bold">
            完善目标院校，资料推荐更准
          </view>
        </view>
        <view class="h-8 w-8 flex items-center justify-center text-[#1E293B]">
          <view class="i-carbon-chevron-right text-xl" />
        </view>
      </view>

      <view class="relative mb-6 flex items-center justify-between overflow-hidden rounded-2xl from-[#C084FC] to-[#9333EA] bg-gradient-to-r p-4.5 text-white shadow-lg shadow-purple-200/50">
        <view class="pointer-events-none absolute bottom-0 right-0 text-8xl text-white/10 -mb-4 -mr-4">
          <view class="i-carbon-trophy" />
        </view>

        <view class="relative z-10">
          <view class="flex items-center text-lg font-bold tracking-wide">
            <view class="i-carbon-star-filled mr-1.5 text-2xl text-[#FDE047]" />
            升级铂金刷题会员
          </view>
          <view class="mt-1 text-[11px] text-white/85">
            解锁历年独家高分真题无限制下载
          </view>
        </view>
        <view class="relative z-10 rounded-full bg-white px-4.5 py-2.5 text-xs text-[#9333EA] font-black tracking-wider shadow-sm transition-transform active:scale-95">
          GO
        </view>
      </view>

      <view class="border border-white/60 rounded-2xl bg-white/80 p-5 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="mb-5 pl-1 text-[13px] text-[#475569] font-bold tracking-wide">
          我的服务
        </view>
        <view class="grid grid-cols-4 gap-y-7">
          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/practice-record/index')">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#F0FDF4] text-[#16A34A] shadow-inner">
              <view class="i-carbon-chart-line text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">刷题记录</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/my-wrong-questions/index')">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#FEF2F2] text-[#EF4444] shadow-inner">
              <view class="i-carbon-close-outline text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">我的错题</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/my-favorites/index')">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#FFFBEB] text-[#F59E0B] shadow-inner">
              <view class="i-carbon-star text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">我的收藏</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/my-notes/index')">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#EFF6FF] text-[#3B82F6] shadow-inner">
              <view class="i-carbon-notebook text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">我的笔记</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openFeedbackPage">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#F5F3FF] text-[#8B5CF6] shadow-inner">
              <view class="i-carbon-idea text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">意见反馈</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/settings/index')">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#F5F3FF] text-[#8B5CF6] shadow-inner">
              <view class="i-carbon-settings text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">设置</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#FFF7ED] text-[#EA580C] shadow-inner">
              <view class="i-carbon-trophy text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">刷题排行</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#FDF4FF] text-[#D946EF] shadow-inner">
              <view class="i-carbon-headset text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">专属客服</text>
          </view>
        </view>
      </view>
    </view>

    <LoginModal v-model="showLoginModal" @success="handleLoginSuccess" />
  </view>
</template>
