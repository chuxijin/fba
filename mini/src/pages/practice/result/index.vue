<script lang="ts" setup>
import { onLoad } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import type { AnswerSheetGroup, AnswerSheetItem } from '@/components/AnswerSheet.vue'
import { fbaApi } from '@/api/sdk'
import { useResultStore } from '@/store/result'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

interface AnswerCardItem {
  seq_no: number
  question_id: number
  placement_id: number
  status: 'correct' | 'wrong' | 'unanswered'
  answer_time: number
  chapter_name: string | null
}

interface ReportData {
  session_id: number
  session_type: string
  practice_name: string
  status: string
  bank_id: number | null
  chapter_id: number | null
  total_count: number
  completed_count: number
  correct_count: number
  wrong_count: number
  unanswered_count: number
  accuracy_rate: number
  total_time: number
  answer_items: AnswerCardItem[]
  wrong_question_ids: number[]
}

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const resultStore = useResultStore()

const loading = ref(true)
const sessionId = ref(0)
const report = ref<ReportData | null>(null)

const accuracy = computed(() => {
  if (!report.value || report.value.total_count === 0)
    return 0
  return Math.round((report.value.correct_count / report.value.total_count) * 100)
})

const formattedDuration = computed(() => {
  const seconds = report.value?.total_time || 0
  if (seconds < 60)
    return `${seconds}秒`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m < 60)
    return s > 0 ? `${m}分${s}秒` : `${m}分钟`
  const h = Math.floor(m / 60)
  const rm = m % 60
  return rm > 0 ? `${h}小时${rm}分` : `${h}小时`
})

// 按章节分组答题卡
const answerGroups = computed<AnswerSheetGroup[]>(() => {
  const items = report.value?.answer_items || []
  if (!items.length)
    return []

  const groups: AnswerSheetGroup[] = []
  let lastChapter = '\x00'
  for (const item of items) {
    const chapterName = item.chapter_name || ''
    if (chapterName !== lastChapter) {
      groups.push({ title: chapterName, items: [] })
      lastChapter = chapterName
    }
    groups[groups.length - 1].items.push({
      id: item.question_id,
      seq_no: item.seq_no,
      status: item.status,
    })
  }
  return groups
})

// 进度环 SVG 参数
const circleRadius = 44
const circleCircumference = 2 * Math.PI * circleRadius
const strokeDashoffset = computed(() => {
  return circleCircumference - (accuracy.value / 100) * circleCircumference
})

function accuracyColor() {
  const v = accuracy.value
  if (v >= 80)
    return '#10B981'
  if (v >= 60)
    return '#3B82F6'
  if (v >= 40)
    return '#F59E0B'
  return '#EF4444'
}

function goBack() {
  uni.navigateBack()
}

function handleViewAll() {
  if (!sessionId.value)
    return
  uni.navigateTo({
    url: `/pages/practice/session/index?sessionId=${sessionId.value}&mode=review&viewMode=all`,
  })
}

function handleViewWrong() {
  if (!sessionId.value)
    return

  const wrongIds = report.value?.wrong_question_ids || []
  if (wrongIds.length === 0) {
    uni.showToast({ title: '没有错题', icon: 'none' })
    return
  }

  uni.navigateTo({
    url: `/pages/practice/session/index?sessionId=${sessionId.value}&mode=review&viewMode=wrong`,
  })
}

function handleSelectItem(item: AnswerSheetItem) {
  if (!sessionId.value)
    return
  // seq_no 从 1 开始，gotoIndex 从 0 开始
  uni.navigateTo({
    url: `/pages/practice/session/index?sessionId=${sessionId.value}&mode=review&viewMode=all&gotoIndex=${item.seq_no - 1}`,
  })
}

async function loadReport() {
  if (!sessionId.value)
    return

  // 优先从内存 store 取（提交时已预取）
  if (resultStore.state.reportData && resultStore.state.sessionId === sessionId.value) {
    report.value = resultStore.state.reportData
    loading.value = false
    return
  }

  // 降级：从 API 请求
  loading.value = true
  try {
    const data = await fbaApi.qbank.session.getReport(sessionId.value) as any
    report.value = data
  }
  catch (error) {
    console.error('加载报告失败:', error)
    uni.showToast({ title: '加载报告失败', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 1500)
  }
  finally {
    loading.value = false
  }
}

onLoad((query) => {
  sessionId.value = Number(query?.sessionId || resultStore.state.sessionId || 0)
  if (!sessionId.value) {
    uni.showToast({ title: '缺少会话参数', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 1500)
    return
  }
  loadReport()
})
</script>

<template>
  <view class="relative min-h-screen overflow-x-hidden from-[#EFF6FF] via-[#F8FBFF] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <!-- 顶部导航 -->
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">练习报告</text>
      </view>
    </view>

    <!-- 加载中 -->
    <view v-if="loading" class="py-20 text-center text-[14px] text-[#94A3B8]">
      加载中...
    </view>

    <template v-else-if="report">
      <scroll-view scroll-y class="box-border px-4 pb-28" :style="{ height: `calc(100vh - ${statusBarHeight! + 44}px)` }">
        <!-- 正确率环形卡 -->
        <view class="mt-4 overflow-hidden border border-white/60 rounded-2xl bg-white/90 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)] backdrop-blur-md">
          <view class="box-border flex flex-col items-center px-5 pb-6 pt-8">
            <!-- SVG 环形进度 -->
            <view class="relative h-32 w-32 flex items-center justify-center">
              <svg width="128" height="128" viewBox="0 0 100 100" class="absolute inset-0">
                <circle
                  cx="50" cy="50" :r="circleRadius"
                  fill="none" stroke="#E2E8F0" stroke-width="8"
                />
                <circle
                  cx="50" cy="50" :r="circleRadius"
                  fill="none" :stroke="accuracyColor()" stroke-width="8"
                  stroke-linecap="round"
                  :stroke-dasharray="circleCircumference"
                  :stroke-dashoffset="strokeDashoffset"
                  transform="rotate(-90 50 50)"
                  style="transition: stroke-dashoffset 1s ease"
                />
              </svg>
              <view class="z-10 flex flex-col items-center">
                <text class="text-3xl font-black" :style="{ color: accuracyColor() }">{{ accuracy }}%</text>
                <text class="mt-0.5 text-[12px] text-[#94A3B8]">正确率</text>
              </view>
            </view>

            <!-- 练习名称 + 用时 -->
            <view class="mt-5 flex flex-wrap items-center justify-center gap-3">
              <view class="flex items-center gap-1.5 rounded-lg bg-[#F1F5F9] px-3 py-1.5">
                <view class="i-carbon-document text-[13px] text-[#64748B]" />
                <text class="text-[12px] text-[#475569]">{{ report.practice_name || '练习' }}</text>
              </view>
              <view class="flex items-center gap-1.5 rounded-lg bg-[#F1F5F9] px-3 py-1.5">
                <view class="i-carbon-time text-[13px] text-[#64748B]" />
                <text class="text-[12px] text-[#475569]">{{ formattedDuration }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 四格统计 -->
        <view class="box-border mt-4 flex gap-2.5">
          <view class="flex flex-1 flex-col items-center gap-1 rounded-xl bg-white/90 py-4 shadow-sm backdrop-blur-sm">
            <text class="text-2xl text-[#3B82F6] font-black">{{ report.total_count }}</text>
            <text class="text-[11px] text-[#94A3B8]">总题数</text>
          </view>
          <view class="flex flex-1 flex-col items-center gap-1 rounded-xl bg-white/90 py-4 shadow-sm backdrop-blur-sm">
            <text class="text-2xl text-[#10B981] font-black">{{ report.correct_count }}</text>
            <text class="text-[11px] text-[#94A3B8]">答对</text>
          </view>
          <view class="flex flex-1 flex-col items-center gap-1 rounded-xl bg-white/90 py-4 shadow-sm backdrop-blur-sm">
            <text class="text-2xl text-[#EF4444] font-black">{{ report.wrong_count }}</text>
            <text class="text-[11px] text-[#94A3B8]">答错</text>
          </view>
          <view class="flex flex-1 flex-col items-center gap-1 rounded-xl bg-white/90 py-4 shadow-sm backdrop-blur-sm">
            <text class="text-2xl text-[#94A3B8] font-black">{{ report.unanswered_count }}</text>
            <text class="text-[11px] text-[#94A3B8]">未答</text>
          </view>
        </view>

        <!-- 答题卡（按章节分组） -->
        <view v-if="answerGroups.length" class="box-border mt-4 overflow-hidden border border-white/60 rounded-2xl bg-white/90 shadow-sm backdrop-blur-sm">
          <view class="px-4 pb-1 pt-3.5">
            <text class="text-[13px] text-[#475569] font-bold">答题卡</text>
          </view>
          <view class="px-4">
            <AnswerSheet :groups="answerGroups" @select="handleSelectItem" />
          </view>
        </view>
      </scroll-view>

      <!-- 底部操作按钮 -->
      <view class="box-border fixed bottom-0 left-0 right-0 z-30 border-t border-white/40 bg-white/95 px-5 pb-[env(safe-area-inset-bottom)] pt-3 backdrop-blur-md">
        <view class="flex gap-3">
          <view
            class="h-12 flex flex-1 items-center justify-center rounded-full border-2 border-[#3B82F6] bg-white text-[15px] text-[#3B82F6] font-bold active:scale-[0.98]"
            @click="handleViewAll"
          >
            查看全部解析
          </view>
          <view
            class="h-12 flex flex-1 items-center justify-center rounded-full from-[#3B82F6] to-[#2563EB] bg-gradient-to-r text-[15px] text-white font-bold shadow-[0_4px_14px_rgba(59,130,246,0.35)] active:scale-[0.98]"
            @click="handleViewWrong"
          >
            仅看错题
          </view>
        </view>
      </view>
    </template>

    <view v-else class="py-20 text-center text-[14px] text-[#94A3B8]">
      报告不存在
    </view>
  </view>
</template>
