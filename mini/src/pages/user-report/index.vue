<script lang="ts" setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { api } from '@/api/sdk'
import { useTokenStore, useUserStore } from '@/store'
import { formatDuration } from '@/utils/mine'

defineOptions({
  name: 'UserReportPage',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '用户报告',
  },
})

interface ReportMetric {
  label: string
  value: string
  tone: string
}

const tokenStore = useTokenStore()
const userStore = useUserStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const loading = ref(false)
const dashboard = ref<any>(null)

const displayNickname = computed(() => userStore.userInfo?.nickname || '我的')
const reportData = computed(() => dashboard.value?.report || null)
const summaryTitle = computed(() => `${displayNickname.value}的刷题报告`)

const todayAccuracy = computed(() => {
  const dailyBreakdown = dashboard.value?.week_stats?.daily_breakdown
  if (!Array.isArray(dailyBreakdown) || !dailyBreakdown.length)
    return 0

  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  const todayData = dailyBreakdown.find((d: any) => String(d.date) === todayStr)
  if (!todayData || !todayData.count)
    return 0

  return Math.round((todayData.correct_count / todayData.count) * 100)
})

const metricCards = computed<ReportMetric[]>(() => {
  const report = reportData.value || {}
  return [
    {
      label: '全站最高答题量',
      value: String(Number(report.site_max_answer_count || 0)),
      tone: 'from-[#FFF7ED] to-[#FFFBF5] text-[#EA580C]',
    },
    {
      label: '答题量排名',
      value: formatRank(report.answer_count_rank),
      tone: 'from-[#F5F3FF] to-[#FAF5FF] text-[#7C3AED]',
    },
    {
      label: '总答题量',
      value: String(Number(report.total_answer_count || dashboard.value?.total_questions || 0)),
      tone: 'from-[#ECFDF5] to-[#F0FDF4] text-[#059669]',
    },
    {
      label: '正确率',
      value: formatPercent(report.accuracy_rate ?? dashboard.value?.overall_accuracy ?? 0),
      tone: 'from-[#EFF6FF] to-[#F8FBFF] text-[#2563EB]',
    },
    {
      label: '练习天数',
      value: `${Number(report.practice_days || 0)}天`,
      tone: 'from-[#FDF2F8] to-[#FFF7FB] text-[#DB2777]',
    },
    {
      label: '答题时长',
      value: formatDuration(Number(report.total_answer_duration || 0)),
      tone: 'from-[#FEFCE8] to-[#FFFEF4] text-[#CA8A04]',
    },
    {
      label: '创建练习数',
      value: String(Number(report.created_session_count || 0)),
      tone: 'from-[#F0FDFA] to-[#F4FFFD] text-[#0F766E]',
    },
  ]
})

function formatPercent(value: unknown) {
  const num = Number(value || 0)
  if (!Number.isFinite(num))
    return '0%'
  if (Number.isInteger(num))
    return `${num}%`
  return `${num.toFixed(2).replace(/\.?0+$/, '')}%`
}

function formatRank(value: unknown) {
  const rank = Number(value || 0)
  return rank > 0 ? `第${rank}名` : '--'
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }

  uni.switchTab({ url: '/pages/practice/index' })
}

function openRankList() {
  uni.navigateTo({ url: '/pages/rank-list/index' })
}

async function loadDashboard() {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    uni.switchTab({ url: '/pages/mine/index' })
    return
  }

  loading.value = true
  try {
    const { data: dashData } = await api.homeDashboard() as any
    dashboard.value = dashData
  }
  catch (error) {
    console.error('加载用户报告失败:', error)
    uni.showToast({ title: '加载用户报告失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

onShow(() => {
  loadDashboard()
})
</script>

<template>
  <view class="relative min-h-screen overflow-hidden from-[#DAF0E4] via-[#F4FBF7] to-[#FAFCFB] bg-gradient-to-b text-[#334155]">
    <view class="pointer-events-none absolute h-80 w-80 rounded-full bg-[#BBF7D0]/50 blur-[40px] -right-10 -top-12" />
    <view class="pointer-events-none absolute top-28 h-64 w-64 rounded-full bg-[#DCFCE7]/70 blur-[50px] -left-16" />

    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="h-11 flex items-center justify-between px-4">
        <view class="w-20 flex items-center active:opacity-60" @tap="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">用户报告</text>
        <view class="w-20" />
      </view>
    </view>

    <view class="relative z-10 px-4 pb-16 pt-6">
      <view class="overflow-hidden rounded-[28px] from-[#10B981] to-[#047857] bg-gradient-to-br px-5 py-5 text-white shadow-[0_18px_44px_rgba(16,185,129,0.24)]">
        <view class="flex items-start justify-between">
          <view class="flex-1">
            <view class="text-[12px] text-white/72">
              统计总览
            </view>
            <view class="mt-2 text-[24px] font-black leading-tight">
              {{ summaryTitle }}
            </view>
          </view>
          <view
            class="ml-3 mt-1 h-9 w-9 flex shrink-0 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm transition-transform active:scale-90"
            @tap="openRankList"
          >
            <view class="i-carbon-trophy text-[20px] text-white" />
          </view>
        </view>
        <view class="mt-2 text-[12px] text-white/80">
          {{ loading ? '正在同步你的最新练习表现' : '这里会集中展示你的累计刷题表现和站内排名' }}
        </view>
      </view>

      <view class="mt-4 grid grid-cols-2 gap-4">
        <view
          v-for="(item, index) in metricCards"
          :key="item.label"
          class="rounded-[24px] border border-white/70 bg-gradient-to-br px-4 py-4 shadow-[0_10px_26px_rgba(148,163,184,0.10)] backdrop-blur-sm"
          :class="[item.tone, { 'col-span-2': metricCards.length % 2 !== 0 && index === metricCards.length - 1 }]"
        >
          <view class="text-[12px] opacity-70">
            {{ item.label }}
          </view>
          <view class="mt-3 break-all text-[22px] font-black leading-tight">
            {{ loading ? '--' : item.value }}
          </view>
        </view>
      </view>

      <view class="mt-4 rounded-[24px] border border-white/70 bg-white/88 px-4 py-4 shadow-[0_10px_26px_rgba(148,163,184,0.10)] backdrop-blur-sm">
        <view class="text-[15px] text-[#14532D] font-bold">
          今日表现
        </view>
        <view class="mt-3 flex items-center justify-between">
          <view>
            <view class="text-[12px] text-[#94A3B8]">
              今日答题
            </view>
            <view class="mt-1 text-[24px] text-[#059669] font-black">
              {{ loading ? '--' : Number(dashboard?.check_in?.today_practice_count || 0) }}
            </view>
          </view>
          <view class="h-12 w-px bg-[#E2E8F0]" />
          <view class="text-right">
            <view class="text-[12px] text-[#94A3B8]">
              今日正确率
            </view>
            <view class="mt-1 text-[24px] text-[#2563EB] font-black">
              {{ loading ? '--' : `${todayAccuracy}%` }}
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>
