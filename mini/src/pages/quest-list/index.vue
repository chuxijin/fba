<script lang="ts" setup>
import { onLoad } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { httpGet } from '@/http/http'
import LoginModal from '@/components/LoginModal.vue'
import { useTokenStore } from '@/store'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

interface QuestItem {
  id: number
  code: string
  name: string
  brief: string
  info: string | null
  cover_image: string | null
  start_time: string | null
  end_time: string | null
  status: number
  total_quota: number
  claimed_count: number
  reward_type: string
  reward_data: Record<string, any> | null
  my_claim_count?: number
  my_active_claim_id?: number | null
  my_latest_claim_status?: number | null
}

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const tokenStore = useTokenStore()
const loading = ref(false)
const quests = ref<QuestItem[]>([])
const showLoginModal = ref(false)

const hasLogin = computed(() => tokenStore.hasLogin)

// 状态标签
function statusLabel(quest: QuestItem): string {
  const map: Record<number, string> = { 0: '未开始', 1: '进行中', 2: '已暂停', 3: '已结束' }
  return map[quest.status] ?? '未知'
}

function statusColor(quest: QuestItem): string {
  const map: Record<number, string> = {
    0: 'bg-[#F1F5F9] text-[#64748B]',
    1: 'bg-[#ECFDF5] text-[#059669]',
    2: 'bg-[#FFFBEB] text-[#B45309]',
    3: 'bg-[#F1F5F9] text-[#94A3B8]',
  }
  return map[quest.status] ?? 'bg-[#F1F5F9] text-[#64748B]'
}

// 进度百分比
function claimPercent(quest: QuestItem): number {
  if (!quest.total_quota) return 0
  return Math.min(Math.round(quest.claimed_count / quest.total_quota * 100), 100)
}

// 格式化日期
function formatDate(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}.${m}.${day}`
}

function dateRange(quest: QuestItem): string {
  const start = formatDate(quest.start_time)
  const end = formatDate(quest.end_time)
  if (start && end) return `${start} - ${end}`
  if (start) return `${start} 起`
  if (end) return `${end} 截止`
  return '长期有效'
}

function goBack() {
  uni.navigateBack()
}

function goToQuestDetail(quest: QuestItem) {
  uni.navigateTo({ url: `/pages/quest-detail/index?id=${quest.id}` })
}

async function loadQuests() {
  loading.value = true
  try {
    const data = await httpGet<any>('/api/v1/quest/quests', {
      only_active: true, page: 1, size: 50,
    })
    quests.value = data?.items || data || []
  }
  catch (error) {
    console.error('加载任务列表失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

function handleLoginSuccess() {
  showLoginModal.value = false
  void loadQuests()
}

onLoad(() => {
  tokenStore.updateNowTime()
  void loadQuests()
})
</script>

<template>
  <view class="relative min-h-screen from-[#FFF7ED] via-[#FFFBF5] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <!-- 顶部导航 -->
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">活动任务</text>
      </view>
    </view>

    <!-- 加载中 -->
    <view v-if="loading" class="py-20 text-center text-[14px] text-[#94A3B8]">
      加载中...
    </view>

    <!-- 空状态 -->
    <view v-else-if="!quests.length" class="mx-4 mt-8">
      <view class="rounded-2xl bg-white/80 px-5 py-12 text-center shadow-sm">
        <view class="i-carbon-task mx-auto text-[48px] text-[#CBD5E1]" />
        <text class="mt-3 block text-[14px] text-[#94A3B8]">暂无进行中的任务</text>
      </view>
    </view>

    <!-- 任务列表 -->
    <view v-else class="mx-4 mt-4 flex flex-col gap-3 pb-8">
      <view
        v-for="quest in quests"
        :key="quest.id"
        class="overflow-hidden border border-white/60 rounded-2xl bg-white/90 shadow-sm backdrop-blur-sm active:scale-[0.99]"
        @click="goToQuestDetail(quest)"
      >
        <view class="px-4 pt-4">
          <!-- 第一行：任务名称 + 状态 -->
          <view class="flex items-center justify-between">
            <text class="flex-1 text-[16px] text-[#1E293B] font-bold leading-snug truncate">
              {{ quest.name }}
            </text>
            <view class="ml-2 shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-bold" :class="statusColor(quest)">
              {{ statusLabel(quest) }}
            </view>
          </view>

          <!-- 简介 -->
          <text class="mt-2 block text-[13px] text-[#64748B] leading-relaxed line-clamp-2">
            {{ quest.brief }}
          </text>
        </view>

        <!-- 封面图 -->
        <image
          v-if="quest.cover_image"
          class="mx-4 mt-3 h-36 w-[calc(100%-32px)] rounded-xl bg-[#F1F5F9]"
          :src="quest.cover_image"
          mode="aspectFill"
        />

        <view class="px-4 pb-4" :class="quest.cover_image ? 'pt-3' : 'pt-4'">
          <!-- 进度条 -->
          <view v-if="quest.total_quota > 0" class="rounded-xl bg-[#F8FAFC] px-3.5 py-3">
            <view class="flex items-center justify-between">
              <text class="text-[13px] text-[#475569] font-medium">已领取</text>
              <text class="text-[13px] text-[#1E293B] font-bold">{{ quest.claimed_count }}/{{ quest.total_quota }}</text>
            </view>
            <view class="mt-2 h-2 overflow-hidden rounded-full bg-[#E2E8F0]">
              <view
                class="h-full rounded-full transition-all duration-500"
                :class="claimPercent(quest) >= 100 ? 'bg-[#94A3B8]' : 'from-[#3B82F6] to-[#2563EB] bg-gradient-to-r'"
                :style="{ width: `${claimPercent(quest)}%` }"
              />
            </view>
          </view>

          <!-- 不限名额 -->
          <view v-else class="rounded-xl bg-[#F8FAFC] px-3.5 py-3">
            <view class="flex items-center justify-between">
              <text class="text-[13px] text-[#475569] font-medium">已领取</text>
              <text class="text-[13px] text-[#1E293B] font-bold">{{ quest.claimed_count }} 人</text>
            </view>
          </view>

          <!-- 活动日期 -->
          <view class="mt-3 flex items-center gap-1.5">
            <view class="i-carbon-calendar text-[13px] text-[#94A3B8]" />
            <text class="text-[12px] text-[#94A3B8]">{{ dateRange(quest) }}</text>
          </view>
        </view>
      </view>
    </view>

    <LoginModal v-model="showLoginModal" @success="handleLoginSuccess" />
  </view>
</template>
