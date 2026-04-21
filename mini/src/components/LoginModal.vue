<script lang="ts" setup>
import { ref, watch } from 'vue'
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  'success': []
}>()

const tokenStore = useTokenStore()

const loginType = ref<'wechat' | 'account' | 'order'>('wechat')
const DEFAULT_AVATAR = '/static/images/default-avatar.png'

const loginForm = ref({
  avatar: DEFAULT_AVATAR,
  nickname: '',
})

const accountForm = ref({
  username: '',
  password: '',
  captcha: '',
})

const accountCaptchaEnabled = ref(false)
const accountCaptchaImage = ref('')
const accountCaptchaUuid = ref('')
const accountCaptchaLoading = ref(false)

const orderForm = ref({
  orderNo: '',
})

function onChooseAvatar(e: any) {
  loginForm.value.avatar = e.detail.avatarUrl
}

function closeModal() {
  emit('update:modelValue', false)
}

function getErrorMessage(error: any, fallback: string) {
  return (
    error?.response?.data?.msg
    || error?.response?.data?.message
    || error?.msg
    || error?.message
    || fallback
  )
}

function handleLoginSuccess() {
  tokenStore.updateNowTime()
  closeModal()
  emit('success')
}

function selectLoginType(type: 'wechat' | 'account' | 'order') {
  loginType.value = type
  if (type === 'account' && props.modelValue) {
    void refreshAccountCaptcha()
  }
}

async function refreshAccountCaptcha(showError = false) {
  if (accountCaptchaLoading.value) {
    return
  }

  accountCaptchaLoading.value = true
  try {
    const captcha = await fbaApi.admin.auth.getCaptcha()
    accountCaptchaEnabled.value = Boolean(captcha?.is_enabled)
    accountCaptchaUuid.value = accountCaptchaEnabled.value ? captcha?.uuid || '' : ''
    accountCaptchaImage.value = accountCaptchaEnabled.value && captcha?.image
      ? `data:image/png;base64,${captcha.image}`
      : ''
    accountForm.value.captcha = ''
  }
  catch (error) {
    console.error('Load Login Captcha Error:', error)
    if (showError) {
      uni.showToast({
        title: '验证码加载失败，请重试',
        icon: 'none',
      })
    }
  }
  finally {
    accountCaptchaLoading.value = false
  }
}

watch(
  () => props.modelValue,
  (value) => {
    if (value && loginType.value === 'account') {
      void refreshAccountCaptcha()
    }
  },
)

function getWechatProfile() {
  return new Promise<{ nickname?: string, avatar?: string }>((resolve) => {
    uni.getUserProfile({
      desc: '用于完善您的头像和昵称资料',
      success: (res: any) => {
        const userInfo = res?.userInfo || {}
        resolve({
          nickname: userInfo.nickName || '',
          avatar: userInfo.avatarUrl || '',
        })
      },
      fail: () => {
        resolve({})
      },
    })
  })
}

async function buildWechatIdentity(): Promise<{ nickname: string, avatar: string }> {
  const profile = await getWechatProfile()
  const nickname = loginForm.value.nickname.trim() || profile.nickname || '微信用户'

  const localAvatar = loginForm.value.avatar || ''
  const isRemoteAvatar = /^https?:\/\//.test(localAvatar) && localAvatar !== DEFAULT_AVATAR
  const avatar = isRemoteAvatar ? localAvatar : (profile.avatar || DEFAULT_AVATAR)

  return {
    nickname,
    avatar,
  }
}

async function confirmWxLogin() {
  uni.showLoading({
    title: '授权登录中...',
    mask: true,
  })

  try {
    const identity = await buildWechatIdentity()
    await tokenStore.wxLogin({
      nickname: identity.nickname,
      avatar: identity.avatar,
    })
    handleLoginSuccess()
  }
  catch (error) {
    console.error('Login Error:', error)
  }
  finally {
    uni.hideLoading()
  }
}

async function quickWxLogin() {
  uni.showLoading({
    title: '一键登录中...',
    mask: true,
  })

  try {
    const identity = await buildWechatIdentity()
    await tokenStore.wxLogin({
      nickname: identity.nickname,
      avatar: identity.avatar,
    })
    handleLoginSuccess()
  }
  catch (error) {
    console.error('Quick Login Error:', error)
  }
  finally {
    uni.hideLoading()
  }
}

async function confirmAccountLogin() {
  const username = accountForm.value.username.trim()
  const password = accountForm.value.password
  const captcha = accountForm.value.captcha.trim()

  if (!username) {
    return uni.showToast({
      title: '请输入账号',
      icon: 'none',
    })
  }

  if (!password) {
    return uni.showToast({
      title: '请输入密码',
      icon: 'none',
    })
  }

  if (accountCaptchaEnabled.value && !captcha) {
    return uni.showToast({
      title: '请输入验证码',
      icon: 'none',
    })
  }

  uni.showLoading({
    title: '账号登录中...',
    mask: true,
  })

  try {
    await tokenStore.login({
      username,
      password,
      captcha: accountCaptchaEnabled.value ? captcha : undefined,
      uuid: accountCaptchaEnabled.value ? accountCaptchaUuid.value : undefined,
    })
    handleLoginSuccess()
  }
  catch (error) {
    console.error('Account Login Error:', error)
    if (accountCaptchaEnabled.value) {
      void refreshAccountCaptcha(true)
    }
  }
  finally {
    uni.hideLoading()
  }
}

async function confirmOrderLogin() {
  const orderNo = orderForm.value.orderNo.trim()

  if (!orderNo) {
    return uni.showToast({
      title: '请输入订单号',
      icon: 'none',
    })
  }

  uni.showLoading({
    title: '验证订单中...',
    mask: true,
  })

  try {
    await fbaApi.actcode.verifyAgisoOrder({
      order_input: orderNo,
    })
    await tokenStore.orderLogin(orderNo)
    orderForm.value.orderNo = ''
    handleLoginSuccess()
  }
  catch (error) {
    console.error('Order Login Error:', error)
    uni.showToast({
      title: getErrorMessage(error, '订单号登录失败，请重试'),
      icon: 'none',
    })
  }
  finally {
    uni.hideLoading()
  }
}

function cancelLogin() {
  closeModal()
}
</script>

<template>
  <wd-popup
    :model-value="modelValue"
    position="bottom"
    custom-class="rounded-t-3xl overflow-hidden bg-[#FAFAFA]"
    :safe-area-inset-bottom="true"
    :z-index="999999"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <view class="relative p-6 transition-all duration-300">
      <view
        class="absolute right-4 top-4 z-20 h-8 w-8 flex items-center justify-center rounded-full bg-slate-100/50 transition-transform active:scale-90"
        @click="cancelLogin"
      >
        <view class="i-carbon-close text-lg text-slate-400" />
      </view>

      <view class="relative mb-6 mt-3 text-center">
        <view class="mb-2 from-[#A855F7] to-[#7E22CE] bg-gradient-to-r bg-clip-text text-xl text-[#1E293B] text-transparent font-bold tracking-wide">
          {{ loginType === 'wechat' ? '获取您的专属身份' : (loginType === 'account' ? '安全身份验证' : '订单凭证登录') }}
        </view>
        <view class="text-[13px] text-[#64748B]">
          {{ loginType === 'wechat' ? '提供头像和昵称，让我们记住优秀的您' : (loginType === 'account' ? '请输入您注册时绑定的账号与密码' : '请输入系统签发的订单凭证') }}
        </view>
      </view>

      <view v-if="loginType === 'wechat'">
        <view class="mx-auto mb-6 h-24 w-24 flex justify-center rounded-full shadow-[0px_10px_30px_rgba(168,85,247,0.1)]">
          <button
            open-type="chooseAvatar"
            class="custom-btn-no-border m-0 h-full w-full overflow-hidden border-[4px] border-[#F3E8FF] rounded-full bg-white p-0 shadow-inner transition-transform active:scale-95"
            @chooseavatar="onChooseAvatar"
          >
            <image class="h-full w-full bg-slate-100" :src="loginForm.avatar" mode="aspectFill" />
          </button>
        </view>

        <view class="mb-7 text-center text-xs text-[#94A3B8] opacity-80 -mt-5">
          点击更换自定义头像
        </view>

        <view class="group relative mb-8 overflow-hidden border border-gray-100/80 rounded-2xl bg-white p-4 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)]">
          <view class="absolute left-0 top-0 h-full w-1 from-[#A855F7] to-[#C084FC] bg-gradient-to-b opacity-40" />
          <view class="flex items-center pl-2">
            <text class="w-14 text-[13px] text-[#475569] font-bold">昵称</text>
            <input
              v-model="loginForm.nickname"
              type="nickname"
              class="ml-2 flex-1 bg-transparent text-base text-[#1E293B]"
              placeholder="自定义专属名称（可选）"
              placeholder-class="text-[#CBD5E1] text-[15px]"
            >
            <view class="i-carbon-keyboard text-lg text-[#CBD5E1] opacity-50" />
          </view>
        </view>

        <view class="flex space-x-4">
          <button
            class="custom-btn-no-border m-0 h-[52px] flex-1 border-2 border-[#E9D5FF] rounded-2xl bg-[#F1F5F9] text-[16px] text-[#8B5CF6] font-bold leading-[48px] transition-transform active:scale-95"
            @click="confirmWxLogin"
          >
            授权登录
          </button>
          <button
            class="custom-btn-no-border m-0 h-[52px] flex-[1.4] rounded-2xl from-[#C084FC] to-[#9333EA] bg-gradient-to-r text-[17px] text-white font-bold leading-[52px] tracking-wider shadow-lg shadow-purple-200 transition-transform active:scale-95"
            @click="quickWxLogin"
          >
            <view class="flex items-center justify-center">
              <view class="i-carbon-flash mr-1.5 text-xl text-[#FDE047]" />
              一键登录
            </view>
          </button>
        </view>
      </view>

      <view v-else-if="loginType === 'account'">
        <view class="mb-8 space-y-4">
          <view class="relative flex items-center overflow-hidden border border-gray-100/80 rounded-2xl bg-white p-4 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)]">
            <view class="absolute left-0 top-0 h-full w-1 bg-[#E2E8F0]" />
            <view class="i-carbon-user ml-2 text-[22px] text-[#94A3B8]" />
            <input
              v-model="accountForm.username"
              type="text"
              class="ml-4 flex-1 bg-transparent text-base text-[#1E293B]"
              placeholder="请输入账号"
              placeholder-class="text-[#CBD5E1] text-[15px]"
            >
          </view>

          <view class="relative flex items-center overflow-hidden border border-gray-100/80 rounded-2xl bg-white p-4 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)]">
            <view class="absolute left-0 top-0 h-full w-1 bg-[#E2E8F0]" />
            <view class="i-carbon-locked ml-2 text-[22px] text-[#94A3B8]" />
            <input
              v-model="accountForm.password"
              type="text"
              password
              class="ml-4 flex-1 bg-transparent text-base text-[#1E293B]"
              placeholder="请输入密码"
              placeholder-class="text-[#CBD5E1] text-[15px]"
            >
          </view>

          <view v-if="accountCaptchaEnabled" class="flex items-stretch">
            <view class="relative flex flex-1 items-center overflow-hidden border border-gray-100/80 rounded-2xl bg-white p-4 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)]">
              <view class="absolute left-0 top-0 h-full w-1 bg-[#E2E8F0]" />
              <view class="i-carbon-password ml-2 text-[22px] text-[#94A3B8]" />
              <input
                v-model="accountForm.captcha"
                type="text"
                class="ml-4 flex-1 bg-transparent text-base text-[#1E293B]"
                placeholder="请输入验证码"
                placeholder-class="text-[#CBD5E1] text-[15px]"
              >
            </view>

            <view
              class="ml-3 h-[56px] w-[120px] overflow-hidden border border-gray-100/80 rounded-2xl bg-white shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)]"
              @click="refreshAccountCaptcha(true)"
            >
              <image
                v-if="accountCaptchaImage"
                class="h-full w-full"
                :src="accountCaptchaImage"
                mode="scaleToFill"
              />
              <view v-else class="h-full w-full flex items-center justify-center text-xs text-[#64748B]">
                {{ accountCaptchaLoading ? '加载中...' : '刷新验证码' }}
              </view>
            </view>
          </view>
        </view>

        <view class="flex">
          <button
            class="custom-btn-no-border m-0 h-[52px] w-full rounded-2xl from-[#1E293B] to-[#334155] bg-gradient-to-r text-[17px] text-white font-bold leading-[52px] tracking-wider shadow-slate-200 shadow-xl transition-transform active:scale-95"
            @click="confirmAccountLogin"
          >
            <view class="flex items-center justify-center">
              立即登录
              <view class="i-carbon-arrow-right ml-1.5 text-lg" />
            </view>
          </button>
        </view>
      </view>

      <view v-else-if="loginType === 'order'">
        <view class="mb-8 space-y-4">
          <view class="relative flex items-center overflow-hidden border border-gray-100/80 rounded-2xl bg-white p-4 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)]">
            <view class="absolute left-0 top-0 h-full w-1 from-[#F59E0B] to-[#D97706] bg-gradient-to-b opacity-60" />
            <view class="i-carbon-document ml-2 text-[22px] text-[#94A3B8]" />
            <input
              v-model="orderForm.orderNo"
              type="text"
              class="ml-4 flex-1 bg-transparent text-base text-[#1E293B]"
              placeholder="请输入订单号或授权码"
              placeholder-class="text-[#CBD5E1] text-[15px]"
            >
          </view>
        </view>

        <view class="flex">
          <button
            class="custom-btn-no-border m-0 h-[52px] w-full rounded-2xl from-[#F59E0B] to-[#B45309] bg-gradient-to-r text-[17px] text-white font-bold leading-[52px] tracking-wider shadow-orange-200/50 shadow-xl transition-transform active:scale-95"
            @click="confirmOrderLogin"
          >
            <view class="flex items-center justify-center">
              使用订单凭证进入
              <view class="i-carbon-rocket ml-1.5 text-lg" />
            </view>
          </button>
        </view>
      </view>

      <view class="mt-5 flex justify-center pb-2">
        <view class="flex items-center border border-slate-100 rounded-full bg-[#F8FAFC] p-1.5 shadow-inner">
          <view
            class="flex items-center whitespace-nowrap rounded-full px-3 py-1.5 text-[12px] transition-all"
            :class="loginType === 'wechat' ? 'bg-white text-[#A855F7] font-bold shadow-sm border border-slate-100/50' : 'text-[#64748B] active:bg-white/50'"
            @click="selectLoginType('wechat')"
          >
            <view class="i-carbon-logo-wechat mr-1 text-[14px]" />
            微信通行
          </view>

          <view
            class="flex items-center whitespace-nowrap rounded-full px-3 py-1.5 text-[12px] transition-all"
            :class="loginType === 'account' ? 'bg-white text-[#1E293B] font-bold shadow-sm border border-slate-100/50' : 'text-[#64748B] active:bg-white/50'"
            @click="selectLoginType('account')"
          >
            <view class="i-carbon-user mr-1 text-[14px]" />
            账号密码
          </view>

          <view
            class="flex items-center whitespace-nowrap rounded-full px-3 py-1.5 text-[12px] transition-all"
            :class="loginType === 'order' ? 'bg-white text-[#F59E0B] font-bold shadow-sm border border-slate-100/50' : 'text-[#64748B] active:bg-white/50'"
            @click="selectLoginType('order')"
          >
            <view class="i-carbon-document mr-1 text-[14px]" />
            订单凭证
          </view>
        </view>
      </view>

      <view class="h-safe-area-bottom w-full" />
    </view>
  </wd-popup>
</template>

<style scoped>
.custom-btn-no-border::after {
  border: none !important;
}

.custom-btn-no-border {
  overflow: visible;
}
</style>
