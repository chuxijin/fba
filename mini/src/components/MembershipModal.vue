<script lang="ts" setup>
import { computed, ref } from 'vue'
import { api } from '@/api/sdk'
import { useMembershipStore, useTokenStore } from '@/store'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  'success': []
}>()

const tokenStore = useTokenStore()
const membershipStore = useMembershipStore()

const activating = ref(false)
const orderInput = ref('')

const isVip = computed(() => membershipStore.isVip)
const tierName = computed(() => membershipStore.tierName)

const vipExpireLabel = computed(() => {
  const validTo = membershipStore.validTo
  if (!validTo) return ''
  const d = new Date(validTo.replace(/-/g, '/'))
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
})

function getErrorMessage(error: any, fallback: string) {
  return (
    error?.response?.data?.msg
    || error?.response?.data?.message
    || error?.msg
    || error?.message
    || fallback
  )
}

async function handleActivateOrder() {
  const normalizedOrderInput = orderInput.value.trim()
  if (!normalizedOrderInput || activating.value) {
    if (!normalizedOrderInput) {
      uni.showToast({ title: '请输入订单号', icon: 'none' })
    }
    return
  }

  if (!tokenStore.hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }

  activating.value = true
  uni.showLoading({ title: '激活中...', mask: true })
  try {
    const { data: result } = await api.activateAgisoOrderForCurrentUser({ body: { order_input: normalizedOrderInput } }) as any

    await membershipStore.fetchMembership()
    orderInput.value = ''
    uni.showToast({ title: result?.message || '激活成功', icon: 'success' })
    closeModal()
    emit('success')
  }
  catch (error: any) {
    console.error('订单号激活失败:', error)
    uni.showToast({
      title: getErrorMessage(error, '订单号激活失败，请重试'),
      icon: 'none',
    })
  }
  finally {
    activating.value = false
    uni.hideLoading()
  }
}

function closeModal() {
  emit('update:modelValue', false)
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
      <!-- 关闭按钮 -->
      <view
        class="absolute right-4 top-4 z-20 h-8 w-8 flex items-center justify-center rounded-full bg-slate-100/50 transition-transform active:scale-90"
        @click="closeModal"
      >
        <view class="i-carbon-close text-lg text-slate-400" />
      </view>

      <!-- 标题区 -->
      <view class="relative mb-6 mt-3 text-center">
        <view class="mb-2 flex items-center justify-center gap-2">
          <view class="i-carbon-trophy text-2xl text-[#F59E0B]" />
          <text class="from-[#F59E0B] to-[#B45309] bg-gradient-to-r bg-clip-text text-xl text-transparent font-bold tracking-wide">
            {{ isVip ? '续期会员' : '激活会员' }}
          </text>
        </view>
        <view class="text-[13px] text-[#64748B]">
          <template v-if="isVip">
            当前 {{ tierName }}，有效期至 {{ vipExpireLabel }}
          </template>
          <template v-else>
            解锁全部高级权益，畅享无限制刷题与资料下载
          </template>
        </view>
      </view>

      <!-- 权益列表 -->
      <view class="mb-5 flex items-center justify-center gap-4">
        <view class="flex items-center gap-1">
          <view class="i-carbon-checkmark-filled text-sm text-[#F59E0B]" />
          <text class="text-[12px] text-[#475569]">无限下载</text>
        </view>
        <view class="flex items-center gap-1">
          <view class="i-carbon-checkmark-filled text-sm text-[#F59E0B]" />
          <text class="text-[12px] text-[#475569]">全部题库</text>
        </view>
        <view class="flex items-center gap-1">
          <view class="i-carbon-checkmark-filled text-sm text-[#F59E0B]" />
          <text class="text-[12px] text-[#475569]">AI 智能解析</text>
        </view>
        <view class="flex items-center gap-1">
          <view class="i-carbon-checkmark-filled text-sm text-[#F59E0B]" />
          <text class="text-[12px] text-[#475569]">专属客服</text>
        </view>
      </view>

      <view class="mt-4 border border-[#E2E8F0] rounded-2xl bg-white/90 px-3.5 py-3">
        <view class="mb-2 text-[12px] text-[#64748B] font-bold">
          已有订单号？
        </view>
        <view class="flex items-center gap-2">
          <view class="h-10 flex flex-1 items-center border border-[#E2E8F0] rounded-xl bg-[#F8FAFC] px-3">
            <view class="i-carbon-document mr-2 text-[16px] text-[#94A3B8]" />
            <input
              v-model="orderInput"
              type="text"
              class="min-w-0 flex-1 bg-transparent text-[14px] text-[#1E293B]"
              placeholder="输入订单号激活会员"
              placeholder-class="text-[#CBD5E1] text-[13px]"
            >
          </view>
          <button
            class="custom-btn-no-border m-0 h-10 shrink-0 rounded-xl from-[#1E293B] to-[#334155] bg-gradient-to-r px-3 text-[13px] text-white font-bold leading-[40px] active:scale-95"
            :disabled="activating"
            :class="activating ? 'opacity-70' : ''"
            @click="handleActivateOrder"
          >
            {{ activating ? '激活中' : '立即激活' }}
          </button>
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
