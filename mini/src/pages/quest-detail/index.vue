<script lang="ts" setup>
import { onLoad } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { api } from '@/api/sdk'
import LoginModal from '@/components/LoginModal.vue'
import { useTokenStore } from '@/store'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

interface QuestDetail {
  id: number
  code: string
  name: string
  brief: string
  info: string | null
  detail: string | null
  cover_image: string | null
  start_time: string | null
  end_time: string | null
  status: number
  total_quota: number
  claimed_count: number
  max_claims_per_user: number
  claim_expire_seconds: number
  submission_required: boolean
  review_required: boolean
  reward_type: string
  reward_data: Record<string, any> | null
  my_claim_count: number
  my_active_claim_id: number | null
  my_latest_claim_status: number | null
}

interface ClaimDetail {
  id: number
  quest_id: number
  claim_status: number
  claim_time: string | null
  expire_time: string | null
  submission_links: string[] | null
  submission_images: string[] | null
  submission_note: string | null
  submit_time: string | null
  review_remark: string | null
  reward_status: number
  granted_at: string | null
}

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const tokenStore = useTokenStore()
const loading = ref(false)
const claiming = ref(false)
const submitting = ref(false)
const quest = ref<QuestDetail | null>(null)
const questId = ref(0)
const showLoginModal = ref(false)

// 提交表单
const submissionNote = ref('')
const submissionLinks = ref('')

const hasLogin = computed(() => tokenStore.hasLogin)

// 状态信息
const statusMap: Record<number, { label: string, color: string }> = {
  0: { label: '未开始', color: 'bg-[#F1F5F9] text-[#64748B]' },
  1: { label: '进行中', color: 'bg-[#ECFDF5] text-[#059669]' },
  2: { label: '已暂停', color: 'bg-[#FFFBEB] text-[#B45309]' },
  3: { label: '已结束', color: 'bg-[#F1F5F9] text-[#94A3B8]' },
}

// 领取状态
const claimStatusMap: Record<number, { label: string, color: string, icon: string }> = {
  0: { label: '已领取', color: 'text-[#3B82F6]', icon: 'i-carbon-in-progress' },
  1: { label: '已提交', color: 'text-[#F59E0B]', icon: 'i-carbon-send-alt' },
  2: { label: '已通过', color: 'text-[#10B981]', icon: 'i-carbon-checkmark-filled' },
  3: { label: '已拒绝', color: 'text-[#EF4444]', icon: 'i-carbon-close-filled' },
  4: { label: '已放弃', color: 'text-[#94A3B8]', icon: 'i-carbon-subtract' },
  5: { label: '已过期', color: 'text-[#94A3B8]', icon: 'i-carbon-time' },
}

function statusLabel(s: number) {
  return statusMap[s]?.label ?? '未知'
}

function statusColor(s: number) {
  return statusMap[s]?.color ?? 'bg-[#F1F5F9] text-[#64748B]'
}

function claimPercent(): number {
  if (!quest.value || !quest.value.total_quota) return 0
  return Math.min(Math.round(quest.value.claimed_count / quest.value.total_quota * 100), 100)
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

function dateRange(): string {
  if (!quest.value) return ''
  const start = formatDate(quest.value.start_time)
  const end = formatDate(quest.value.end_time)
  if (start && end) return `${start} - ${end}`
  if (start) return `${start} 起`
  if (end) return `${end} 截止`
  return '长期有效'
}

// 奖励描述
function rewardDesc(): string {
  if (!quest.value) return ''
  const typeMap: Record<string, string> = {
    points: '积分',
    vip: '会员时长',
    feature: '功能权限',
  }
  const label = typeMap[quest.value.reward_type] || quest.value.reward_type
  const data = quest.value.reward_data
  if (data?.amount) return `${label} +${data.amount}`
  if (data?.days) return `${label} +${data.days}天`
  return label
}

// 是否可以领取
const canClaim = computed(() => {
  if (!quest.value) return false
  if (quest.value.status !== 1) return false
  if (quest.value.total_quota > 0 && quest.value.claimed_count >= quest.value.total_quota) return false
  if (quest.value.my_claim_count >= quest.value.max_claims_per_user) return false
  if (quest.value.my_active_claim_id) return false
  return true
})

// 是否有进行中的领取（可提交）
const canSubmit = computed(() => {
  return quest.value?.my_active_claim_id && quest.value?.my_latest_claim_status === 0
})

// 底部按钮文字
const actionLabel = computed(() => {
  if (!quest.value) return ''
  if (quest.value.status !== 1) return '任务未开放'
  if (quest.value.my_active_claim_id && quest.value.my_latest_claim_status === 0) return '提交任务'
  if (quest.value.my_active_claim_id && quest.value.my_latest_claim_status === 1) return '等待审核中'
  if (quest.value.my_latest_claim_status === 2) return '已完成'
  if (canClaim.value) return '领取任务'
  if (quest.value.total_quota > 0 && quest.value.claimed_count >= quest.value.total_quota) return '名额已满'
  if (quest.value.my_claim_count >= quest.value.max_claims_per_user) return '已达领取上限'
  return '不可领取'
})

const actionDisabled = computed(() => {
  return !canClaim.value && !canSubmit.value
})

function goBack() {
  uni.navigateBack()
}

async function loadDetail() {
  loading.value = true
  try {
    const { data } = await api.getQuestDetail({ path: { pk: questId.value } }) as any
    quest.value = data as QuestDetail
  }
  catch (err) {
    console.error('加载任务详情失败:', err)
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

async function handleAction() {
  if (!hasLogin.value) {
    showLoginModal.value = true
    return
  }
  if (canSubmit.value) {
    handleSubmit()
    return
  }
  if (canClaim.value) {
    handleClaim()
  }
}

async function handleClaim() {
  claiming.value = true
  try {
    await api.claimQuest({ path: { pk: questId.value } })
    uni.showToast({ title: '领取成功', icon: 'success' })
    await loadDetail()
  }
  catch (err) {
    console.error('领取失败:', err)
    uni.showToast({ title: '领取失败', icon: 'none' })
  }
  finally {
    claiming.value = false
  }
}

async function handleSubmit() {
  if (!quest.value?.my_active_claim_id) return
  if (quest.value.submission_required && !submissionNote.value.trim() && !submissionLinks.value.trim()) {
    uni.showToast({ title: '请填写提交内容', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const links = submissionLinks.value.trim()
      ? submissionLinks.value.split('\n').map((l) => l.trim()).filter(Boolean)
      : null
    await api.submitClaim({
      path: { pk: quest.value.my_active_claim_id },
      body: {
        submission_note: submissionNote.value.trim() || null,
        submission_links: links,
      },
    })
    uni.showToast({ title: '提交成功', icon: 'success' })
    submissionNote.value = ''
    submissionLinks.value = ''
    await loadDetail()
  }
  catch (err) {
    console.error('提交失败:', err)
    uni.showToast({ title: '提交失败', icon: 'none' })
  }
  finally {
    submitting.value = false
  }
}

async function handleAbandon() {
  if (!quest.value?.my_active_claim_id) return
  uni.showModal({
    title: '确认放弃',
    content: '放弃后本次领取将作废，确定放弃吗？',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await api.abandonClaim({ path: { pk: quest.value!.my_active_claim_id } })
        uni.showToast({ title: '已放弃', icon: 'none' })
        await loadDetail()
      }
      catch (err) {
        console.error('放弃失败:', err)
        uni.showToast({ title: '操作失败', icon: 'none' })
      }
    },
  })
}

function handleLoginSuccess() {
  showLoginModal.value = false
  void loadDetail()
}

onLoad((query) => {
  questId.value = Number(query?.id || 0)
  if (questId.value) {
    void loadDetail()
  }
})
</script>

<template>
  <view class="relative min-h-screen bg-[#F8FAFC] text-[#334155]">
    <!-- 顶部导航 -->
    <view class="fixed left-0 right-0 top-0 z-50 bg-white/90 backdrop-blur-lg" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold">任务详情</text>
      </view>
    </view>

    <!-- 占位 -->
    <view :style="{ height: `${statusBarHeight + 44}px` }" />

    <!-- 加载中 -->
    <view v-if="loading" class="py-20 text-center text-[14px] text-[#94A3B8]">加载中...</view>

    <view v-else-if="quest" class="pb-24">
      <!-- 封面图 -->
      <image
        v-if="quest.cover_image"
        class="h-48 w-full bg-[#E2E8F0]"
        :src="quest.cover_image"
        mode="aspectFill"
      />

      <!-- 主卡片 -->
      <view class="mx-4 -mt-4 relative z-10 overflow-hidden rounded-2xl bg-white shadow-sm" :class="{ 'mt-4': !quest.cover_image }">
        <view class="p-5">
          <!-- 标题 + 状态 -->
          <view class="flex items-start justify-between gap-2">
            <text class="flex-1 text-[18px] text-[#0F172A] font-bold leading-snug">{{ quest.name }}</text>
            <view class="mt-0.5 shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-bold" :class="statusColor(quest.status)">
              {{ statusLabel(quest.status) }}
            </view>
          </view>

          <!-- 简介 -->
          <text class="mt-3 block text-[14px] text-[#475569] leading-relaxed">{{ quest.brief }}</text>

          <!-- 信息区 -->
          <view class="mt-4 flex flex-col gap-2.5">
            <!-- 日期 -->
            <view class="flex items-center gap-2">
              <view class="i-carbon-calendar text-[15px] text-[#94A3B8]" />
              <text class="text-[13px] text-[#64748B]">{{ dateRange() }}</text>
            </view>
            <!-- 奖励 -->
            <view class="flex items-center gap-2">
              <view class="i-carbon-gift text-[15px] text-[#F59E0B]" />
              <text class="text-[13px] text-[#64748B]">奖励：{{ rewardDesc() }}</text>
            </view>
            <!-- 名额 -->
            <view class="flex items-center gap-2">
              <view class="i-carbon-user-multiple text-[15px] text-[#94A3B8]" />
              <text class="text-[13px] text-[#64748B]">
                {{ quest.total_quota > 0 ? `名额 ${quest.claimed_count}/${quest.total_quota}` : `已有 ${quest.claimed_count} 人领取` }}
              </text>
            </view>
          </view>

          <!-- 进度条 -->
          <view v-if="quest.total_quota > 0" class="mt-4">
            <view class="h-2 overflow-hidden rounded-full bg-[#E2E8F0]">
              <view
                class="h-full rounded-full transition-all duration-500"
                :class="claimPercent() >= 100 ? 'bg-[#94A3B8]' : 'from-[#3B82F6] to-[#2563EB] bg-gradient-to-r'"
                :style="{ width: `${claimPercent()}%` }"
              />
            </view>
          </view>
        </view>
      </view>

      <!-- 我的参与状态 -->
      <view v-if="hasLogin && quest.my_latest_claim_status != null" class="mx-4 mt-3 overflow-hidden rounded-2xl bg-white shadow-sm">
        <view class="p-4">
          <view class="flex items-center gap-2">
            <view class="text-[16px]" :class="[claimStatusMap[quest.my_latest_claim_status]?.icon, claimStatusMap[quest.my_latest_claim_status]?.color]" />
            <text class="text-[14px] font-medium" :class="claimStatusMap[quest.my_latest_claim_status]?.color">
              {{ claimStatusMap[quest.my_latest_claim_status]?.label }}
            </text>
            <text v-if="quest.my_claim_count > 1" class="text-[12px] text-[#94A3B8]">
              (已领取 {{ quest.my_claim_count }} 次)
            </text>
          </view>
        </view>
      </view>

      <!-- 提交表单(已领取且未提交) -->
      <view v-if="canSubmit && quest.submission_required" class="mx-4 mt-3 overflow-hidden rounded-2xl bg-white shadow-sm">
        <view class="p-4">
          <text class="text-[15px] text-[#1E293B] font-bold">提交任务内容</text>

          <view class="mt-3">
            <text class="text-[13px] text-[#64748B]">说明</text>
            <textarea
              v-model="submissionNote"
              class="mt-1.5 w-full rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-3 text-[14px] text-[#334155]"
              placeholder="请描述完成情况..."
              :maxlength="500"
              :auto-height="true"
            />
          </view>

          <view class="mt-3">
            <text class="text-[13px] text-[#64748B]">相关链接（每行一个）</text>
            <textarea
              v-model="submissionLinks"
              class="mt-1.5 w-full rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-3 text-[14px] text-[#334155]"
              placeholder="https://..."
              :maxlength="2000"
              :auto-height="true"
            />
          </view>

          <!-- 放弃按钮 -->
          <view class="mt-4 text-center">
            <text class="text-[13px] text-[#EF4444] active:opacity-60" @click="handleAbandon">放弃任务</text>
          </view>
        </view>
      </view>

      <!-- 任务详情 -->
      <view v-if="quest.detail" class="mx-4 mt-3 overflow-hidden rounded-2xl bg-white shadow-sm">
        <view class="p-4">
          <text class="text-[15px] text-[#1E293B] font-bold">任务详情</text>
          <rich-text class="mt-3 block text-[14px] text-[#475569] leading-relaxed" :nodes="quest.detail" />
        </view>
      </view>

      <!-- 任务补充信息 -->
      <view v-if="quest.info" class="mx-4 mt-3 overflow-hidden rounded-2xl bg-white shadow-sm">
        <view class="p-4">
          <text class="text-[15px] text-[#1E293B] font-bold">补充说明</text>
          <text class="mt-2 block text-[14px] text-[#64748B] leading-relaxed">{{ quest.info }}</text>
        </view>
      </view>
    </view>

    <!-- 底部操作栏 -->
    <view v-if="quest" class="fixed bottom-0 left-0 right-0 z-50 border-t border-[#F1F5F9] bg-white/95 px-5 pb-[env(safe-area-inset-bottom)] pt-3 backdrop-blur-lg">
      <view
        class="h-12 flex items-center justify-center rounded-xl text-[16px] font-bold transition-all"
        :class="actionDisabled
          ? 'bg-[#E2E8F0] text-[#94A3B8]'
          : 'from-[#3B82F6] to-[#2563EB] bg-gradient-to-r text-white shadow-lg shadow-blue-500/25 active:scale-[0.98]'"
        @click="!actionDisabled && handleAction()"
      >
        <view v-if="claiming || submitting" class="i-carbon-circle-dash mr-2 animate-spin text-[18px]" />
        {{ claiming ? '领取中...' : submitting ? '提交中...' : actionLabel }}
      </view>
    </view>

    <LoginModal v-model="showLoginModal" @success="handleLoginSuccess" />
  </view>
</template>
