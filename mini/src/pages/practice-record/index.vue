<script lang="ts" setup>
import type { GetPracticeSessionListItem, PageData } from '@fba/api-sdk'
import { computed, ref } from 'vue'
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'
import { useResultStore } from '@/store/result'
import { getAppSettings } from '@/utils/appSettings'
import { formatDateTime, formatDuration, getSessionStatusLabel, getSessionTypeLabel } from '@/utils/mine'
import { getStudyDomainOption } from '@/utils/studyDomain'
import { toLoginPage } from '@/utils/toLoginPage'

defineOptions({
  name: 'PracticeRecord',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '刷题记录',
  },
})

const PAGE_SIZE = 20

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const loading = ref(false)
const loadingMore = ref(false)
const deletingId = ref(0)
const records = ref<GetPracticeSessionListItem[]>([])
const total = ref(0)
const page = ref(1)
const currentDomainLabel = ref(getStudyDomainOption(getAppSettings().currentDomain).label)

const hasMore = computed(() => records.value.length < total.value)

const summary = computed(() => {
  const completedCount = records.value.reduce((sum, item) => sum + Number(item.completed_count || 0), 0)
  const correctCount = records.value.reduce((sum, item) => sum + Number(item.correct_count || 0), 0)
  const accuracy = completedCount > 0 ? Math.round((correctCount / completedCount) * 100) : 0

  return {
    completedCount,
    correctCount,
    accuracy,
  }
})

function ensureLogin() {
  if (tokenStore.updateNowTime().hasLogin) {
    return true
  }

  uni.showToast({ title: '请先登录后查看刷题记录', icon: 'none' })
  setTimeout(() => {
    toLoginPage()
  }, 300)
  return false
}

async function loadRecords(targetPage = 1) {
  if (!ensureLogin()) {
    return
  }

  const isFirstPage = targetPage === 1
  if (isFirstPage) {
    loading.value = true
  }
  else {
    loadingMore.value = true
  }

  try {
    const currentDomain = getAppSettings().currentDomain
    currentDomainLabel.value = getStudyDomainOption(currentDomain).label

    const data = await fbaApi.qbank.request.get<PageData<GetPracticeSessionListItem>>('/sessions', {
      params: {
        page: targetPage,
        size: PAGE_SIZE,
        study_domain: currentDomain,
      },
    })

    records.value = isFirstPage ? data.items : [...records.value, ...data.items]
    total.value = data.total
    page.value = targetPage
  }
  catch (error) {
    console.error('加载刷题记录失败:', error)
    if (isFirstPage) {
      records.value = []
      total.value = 0
    }
    uni.showToast({ title: '加载刷题记录失败', icon: 'none' })
  }
  finally {
    loading.value = false
    loadingMore.value = false
  }
}

function practiceModeOf(record: GetPracticeSessionListItem) {
  return record.session_type === 'exam' ? 'exam' : 'practice'
}

async function openSession(record: GetPracticeSessionListItem) {
  if (record.status === 'completed') {
    uni.showLoading({ title: '加载中...', mask: true })
    try {
      const [reportData, solutionData] = await Promise.all([
        fbaApi.qbank.session.getReport(record.id).catch(() => null),
        fbaApi.qbank.session.getSolution(record.id).catch(() => null),
      ])
      const resultStore = useResultStore()
      resultStore.setResult(record.id, reportData, solutionData)
      uni.navigateTo({
        url: `/pages/practice/result/index?sessionId=${record.id}`,
      })
    }
    catch (error) {
      console.error('加载失败:', error)
      uni.showToast({ title: '加载失败', icon: 'none' })
    }
    finally {
      uni.hideLoading()
    }
    return
  }

  // 进行中：直接进刷题页
  uni.navigateTo({
    url: `/pages/practice/session/index?sessionId=${record.id}&mode=${practiceModeOf(record)}`,
  })
}

function actionLabel(record: GetPracticeSessionListItem) {
  return record.status === 'in_progress' ? '继续刷题' : '查看数据'
}

async function handleDelete(record: GetPracticeSessionListItem) {
  if (deletingId.value)
    return

  const confirmed = await new Promise<boolean>((resolve) => {
    uni.showModal({
      title: '删除记录',
      content: `确认删除“${record.practice_name || getSessionTypeLabel(record.session_type)}”这条刷题记录吗？`,
      confirmText: '删除',
      confirmColor: '#DC2626',
      cancelText: '取消',
      success: res => resolve(Boolean(res.confirm)),
      fail: () => resolve(false),
    })
  })

  if (!confirmed)
    return

  deletingId.value = record.id
  try {
    await fbaApi.qbank.session.remove(record.id)
    records.value = records.value.filter(item => item.id !== record.id)
    total.value = Math.max(0, total.value - 1)
    uni.showToast({ title: '删除成功', icon: 'success' })
  }
  catch (error) {
    console.error('删除刷题记录失败:', error)
    uni.showToast({ title: '删除刷题记录失败', icon: 'none' })
  }
  finally {
    deletingId.value = 0
  }
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }

  uni.switchTab({ url: '/pages/mine/index' })
}

onShow(() => {
  loadRecords()
})

onPullDownRefresh(async () => {
  await loadRecords()
  uni.stopPullDownRefresh()
})

onReachBottom(() => {
  if (loading.value || loadingMore.value || !hasMore.value) {
    return
  }

  loadRecords(page.value + 1)
})
</script>

<template>
  <view class="relative min-h-screen from-[#F0FDF4] via-[#F8FCF9] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">刷题记录</text>
      </view>
    </view>

    <view class="mt-4 px-4 pb-24">
      <view class="mb-5 border border-white/60 rounded-2xl bg-white/80 p-5 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)] backdrop-blur-md">
        <view class="grid grid-cols-3 gap-3">
          <view class="flex flex-col items-center rounded-xl bg-[#F0FDF4] py-3">
            <text class="text-[22px] text-[#16A34A] font-black">{{ summary.completedCount }}</text>
            <text class="mt-1 text-[11px] text-[#94A3B8]">累计刷题</text>
          </view>
          <view class="flex flex-col items-center rounded-xl bg-[#F5F3FF] py-3">
            <text class="text-[22px] text-[#7C3AED] font-black">{{ summary.correctCount }}</text>
            <text class="mt-1 text-[11px] text-[#94A3B8]">答对题数</text>
          </view>
          <view class="flex flex-col items-center rounded-xl bg-[#FFF7ED] py-3">
            <text class="text-[22px] text-[#EA580C] font-black">{{ summary.accuracy }}%</text>
            <text class="mt-1 text-[11px] text-[#94A3B8]">综合正确率</text>
          </view>
        </view>
      </view>

      <view class="mb-3 flex items-center justify-between pl-1">
        <view class="flex items-center gap-2">
          <text class="text-[13px] text-[#475569] font-bold">练习历史</text>
          <text class="rounded-full bg-[#F8FAFC] px-2.5 py-1 text-[10px] text-[#475569] font-semibold">当前领域：{{ currentDomainLabel }}</text>
        </view>
        <text class="text-[11px] text-[#94A3B8]">共 {{ total }} 条</text>
      </view>

      <view v-if="loading && records.length === 0" class="py-18 text-center text-[13px] text-[#94A3B8]">
        刷题记录加载中...
      </view>

      <view v-else-if="records.length > 0" class="flex flex-col gap-3">
        <wd-swipe-action
          v-for="record in records"
          :key="record.id"
        >
          <view class="border border-white/60 rounded-2xl bg-white/80 px-4 py-4 shadow-[0_2px_12px_-6px_rgba(0,0,0,0.06)] backdrop-blur-md">
            <view class="min-w-0">
              <view class="flex items-center gap-2">
                <text
                  class="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold"
                  :class="record.status === 'in_progress' ? 'bg-[#ECFDF5] text-[#16A34A]' : 'bg-[#EFF6FF] text-[#2563EB]'"
                >
                  {{ getSessionStatusLabel(record.status) }}
                </text>
                <text class="truncate text-[14px] text-[#1E293B] font-bold">
                  {{ record.practice_name || getSessionTypeLabel(record.session_type) }}
                </text>
              </view>

              <view class="mt-3 flex items-end justify-between gap-4">
                <view class="min-w-0 flex-1">
                  <view class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-[#475569] font-medium">
                    <text v-if="record.total_time > 0">{{ formatDuration(record.total_time) }}</text>
                    <text v-if="record.status === 'in_progress'">{{ record.completed_count }}/{{ record.total_count }} 进度</text>
                    <text v-else>{{ record.correct_count }}/{{ record.total_count }} 答对</text>
                  </view>
                  <view class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-[#94A3B8]">
                    <text>{{ formatDateTime(record.start_time) }}</text>
                  </view>
                </view>

                <view class="shrink-0 h-9 flex items-center justify-center rounded-full px-4 text-[13px] text-white font-bold active:scale-[0.98]" :class="record.status === 'in_progress' ? 'bg-[#16A34A]' : 'bg-[#2563EB]'" @click="openSession(record)">
                  {{ actionLabel(record) }}
                </view>
              </view>
            </view>
          </view>

          <template #right>
            <view class="h-full flex items-stretch">
              <view class="h-full min-w-[72px] flex items-center justify-center rounded-r-2xl bg-[#EF4444] px-5 text-[14px] text-white font-bold" @click="handleDelete(record)">
                {{ deletingId === record.id ? '删除中' : '删除' }}
              </view>
            </view>
          </template>
        </wd-swipe-action>

        <view v-if="loadingMore" class="py-4 text-center text-[12px] text-[#94A3B8]">
          正在加载更多记录...
        </view>
      </view>

      <view v-else class="flex flex-col items-center justify-center py-20">
        <view class="i-carbon-document mb-4 text-6xl text-[#CBD5E1]" />
        <text class="text-[14px] text-[#94A3B8]">{{ currentDomainLabel }}领域下暂无刷题记录，快去练习吧！</text>
      </view>
    </view>
  </view>
</template>
