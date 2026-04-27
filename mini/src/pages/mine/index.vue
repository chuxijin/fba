<script lang="ts" setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { fbaApi } from '@/api/sdk'
import LoginModal from '@/components/LoginModal.vue'
import { useCachedAvatar } from '@/hooks/useCachedAvatar'
import { useMembershipStore, useTokenStore, useUserStore } from '@/store'
import { getAppSettings, saveAppSettings } from '@/utils/appSettings'
import { STUDY_DOMAIN_OPTIONS, getStudyDomainOption, type StudyDomainCode } from '@/utils/studyDomain'
import { mergeCachedStudyPreference } from '@/utils/studyPreferenceCache'
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
const membershipStore = useMembershipStore()
const showLoginModal = ref(false)
const currentDomain = ref<StudyDomainCode>(getAppSettings().currentDomain)
const unreadMessageCount = ref(0)
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const DEFAULT_AVATAR = '/static/images/default-avatar.png'

const hasLogin = computed(() => tokenStore.hasLogin)
const isVip = computed(() => membershipStore.isVip)
const tierName = computed(() => membershipStore.tierName)
const isSvip = computed(() => {
  const familyCode = membershipStore.activeMembership?.family_code?.toUpperCase() || ''
  if (familyCode) {
    return familyCode === 'SVIP'
  }
  return /^SVIP/i.test(tierName.value)
})
const currentDomainLabel = computed(() => getStudyDomainOption(currentDomain.value).label)

const avatarSource = computed(() => {
  if (!hasLogin.value) {
    return DEFAULT_AVATAR
  }

  return userStore.userInfo.avatar || DEFAULT_AVATAR
})
const displayAvatar = useCachedAvatar(avatarSource, DEFAULT_AVATAR)

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
    // 用户信息已有，仅静默刷新会员状态
    void membershipStore.fetchMembership()
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

async function loadUnreadMessageCount() {
  tokenStore.updateNowTime()
  if (!hasLogin.value) {
    unreadMessageCount.value = 0
    return
  }

  try {
    const data = await fbaApi.qbank.request.get<{ count: number }>('/messages/unread-count')
    unreadMessageCount.value = Number(data?.count || 0)
  }
  catch (error) {
    console.error('加载未读消息数失败:', error)
    unreadMessageCount.value = 0
  }
}

async function handleLoginSuccess() {
  tokenStore.updateNowTime()
  showLoginModal.value = false
  await syncLoginState()
  await loadUnreadMessageCount()
  redirectAfterLogin()
}

function openMembershipCenter() {
  tokenStore.updateNowTime()
  if (!hasLogin.value) {
    setLoginRedirect('/pages/membership-center/index')
    showLoginModal.value = true
    return
  }

  uni.navigateTo({ url: '/pages/membership-center/index' })
}

function chooseStudyDomain() {
  uni.showActionSheet({
    itemList: STUDY_DOMAIN_OPTIONS.map(item => item.label),
    success: async (res) => {
      const nextDomain = STUDY_DOMAIN_OPTIONS[Number(res.tapIndex)]?.code
      if (!nextDomain || nextDomain === currentDomain.value) {
        return
      }

      currentDomain.value = nextDomain
      saveAppSettings({ currentDomain: nextDomain })

      if (tokenStore.updateNowTime().hasLogin) {
        try {
          await fbaApi.qbank.settings.updateStudyPreference({
            current_domain: nextDomain,
          } as any)
          mergeCachedStudyPreference(Number(userStore.userInfo?.id || 0), {
            current_domain: nextDomain,
          })
        }
        catch (error) {
          console.error('保存当前领域失败:', error)
        }
      }

      uni.showToast({ title: `已切换到${getStudyDomainOption(nextDomain).shortLabel}`, icon: 'none' })
    },
  })
}

onShow(() => {
  currentDomain.value = getAppSettings().currentDomain
  void syncLoginState().finally(() => {
    void loadUnreadMessageCount()
    maybeOpenLoginModal()
  })
})
</script>

<template>
  <view class="relative min-h-[calc(100vh-50px-env(safe-area-inset-bottom))] overflow-hidden from-[#F3E8FF] via-[#F8F5FB] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="pointer-events-none absolute h-80 w-80 rounded-full bg-[#E9D5FF]/40 blur-[40px] -right-8 -top-12" />
    <view class="pointer-events-none absolute top-20 h-60 w-60 rounded-full bg-[#FBCFE8]/20 blur-[40px] -left-16" />

    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="h-11 flex items-center justify-between px-4">
        <view class="w-20" />
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">用户中心</text>
        <view class="w-20" />
      </view>
    </view>

    <view class="relative z-10 mt-6 px-4 pb-6">
      <view class="mb-7 ml-1 flex items-center transition-transform active:scale-[0.98]" @click="handleLogin">
        <view class="relative">
          <image
            class="h-16 w-16 border-[3px] rounded-full bg-white shadow-sm"
            :class="isVip ? 'border-[#FDE047]' : 'border-white'"
            :src="displayAvatar"
            mode="aspectFill"
          />
        </view>
        <view class="ml-4 flex-1">
          <view class="flex items-center">
            <text class="text-xl text-[#1E293B] font-bold">
              {{ displayNickname }}
            </text>
            <view
              v-if="isVip"
              class="ml-2 inline-flex items-center rounded-full px-2.5 py-0.5 shadow-sm transition-transform active:scale-95"
              :class="isSvip ? 'bg-[#1E1B4B]' : 'bg-[#0F3B82]'"
              @click.stop="openMembershipCenter"
            >
              <text
                class="text-[10px] font-semibold tracking-[0.3px] italic"
                :class="isSvip ? 'text-[#FDE68A]' : 'text-[#DBEAFE]'"
              >
                {{ tierName }}
              </text>
            </view>
          </view>
          <view class="mt-1.5 flex flex-wrap items-center gap-2">
            <view
              class="inline-flex items-center rounded-md border border-[#BFDBFE] bg-[#EFF6FF] px-2.5 py-0.5 text-[11px] text-[#1D4ED8] font-bold"
              @click.stop="chooseStudyDomain"
            >
              当前领域：{{ currentDomainLabel }}
            </view>
            <view
              class="inline-block rounded-md px-2.5 py-0.5 text-[11px] font-bold"
              :class="isVip
                ? 'border border-[#FDE68A] bg-[#FFFBEB] text-[#B45309]'
                : 'border border-[#E9D5FF] bg-[#F3E8FF] text-[#7E22CE]'"
              @click.stop="openMembershipCenter"
            >
              {{ isVip ? '查看会员权益' : '完善目标院校，资料推荐更准' }}
            </view>
          </view>
        </view>
        <view class="h-8 w-8 flex items-center justify-center text-[#1E293B]">
          <view class="i-carbon-chevron-right text-xl" />
        </view>
      </view>

      <view class="border border-white/60 rounded-2xl bg-white/80 p-5 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="mb-5 pl-1 text-[13px] text-[#475569] font-bold tracking-wide">
          学习资产
        </view>
        <view class="grid grid-cols-5 gap-y-6">
          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/practice-record/index')">
            <view class="mb-1.5 h-10 w-10 flex items-center justify-center rounded-2xl bg-[#F0FDF4] text-[#16A34A] shadow-inner">
              <view class="i-carbon-chart-line text-[20px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">刷题记录</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/my-wrong-questions/index')">
            <view class="mb-1.5 h-10 w-10 flex items-center justify-center rounded-2xl bg-[#FEF2F2] text-[#EF4444] shadow-inner">
              <view class="i-carbon-close-outline text-[20px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">我的错题</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/my-favorites/index')">
            <view class="mb-1.5 h-10 w-10 flex items-center justify-center rounded-2xl bg-[#FFFBEB] text-[#F59E0B] shadow-inner">
              <view class="i-carbon-star text-[20px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">我的收藏</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/my-notes/index')">
            <view class="mb-1.5 h-10 w-10 flex items-center justify-center rounded-2xl bg-[#EFF6FF] text-[#3B82F6] shadow-inner">
              <view class="i-carbon-notebook text-[20px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">我的笔记</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/my-render-books/index')">
            <view class="mb-1.5 h-10 w-10 flex items-center justify-center rounded-2xl bg-[#FFF7ED] text-[#EA580C] shadow-inner">
              <view class="i-carbon-book text-[20px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">我的题本</text>
          </view>
        </view>
      </view>

      <view class="mt-4 border border-white/60 rounded-2xl bg-white/80 p-5 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="mb-5 pl-1 text-[13px] text-[#475569] font-bold tracking-wide">
          账户服务
        </view>
        <view class="grid grid-cols-4 gap-y-7">
          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/my-messages/index')">
            <view class="relative mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#EEF2FF] text-[#4F46E5] shadow-inner">
              <view class="i-carbon-notification text-[22px]" />
              <view
                v-if="unreadMessageCount > 0"
                class="absolute min-w-[17px] h-[17px] flex items-center justify-center rounded-full bg-[#EF4444] px-1 text-[9px] text-white font-black shadow-sm -right-1 -top-1"
              >
                {{ unreadMessageCount > 99 ? '99+' : unreadMessageCount }}
              </view>
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">我的消息</text>
          </view>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openFeedbackPage">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#F5F3FF] text-[#8B5CF6] shadow-inner">
              <view class="i-carbon-idea text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">意见反馈</text>
          </view>

          <button open-type="contact" class="m-0 flex flex-col items-center bg-transparent p-0 leading-normal transition-transform active:scale-95 after:border-0">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#FDF4FF] text-[#D946EF] shadow-inner">
              <view class="i-carbon-headset text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">专属客服</text>
          </button>

          <view class="flex flex-col items-center transition-transform active:scale-95" @click="openServicePage('/pages/settings/index')">
            <view class="mb-1.5 h-11 w-11 flex items-center justify-center rounded-2xl bg-[#F5F3FF] text-[#8B5CF6] shadow-inner">
              <view class="i-carbon-settings text-[22px]" />
            </view>
            <text class="text-[11px] text-[#64748B] font-medium">设置</text>
          </view>
        </view>
      </view>
    </view>

    <LoginModal v-model="showLoginModal" @success="handleLoginSuccess" />
  </view>
</template>
