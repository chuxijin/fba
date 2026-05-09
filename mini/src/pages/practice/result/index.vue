<script lang="ts" setup>
import { onLoad } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import type { AnswerSheetGroup, AnswerSheetItem } from '@/components/AnswerSheet.vue'
import { api } from '@/api/sdk'
import { useResultStore } from '@/store/result'
import {
  generatePracticeSessionAISummary,
  getPracticeSessionAISummary,
  normalizeStringList,
  type PracticeAIEvaluation,
} from '@/utils/aiEvaluation'

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

interface SubmitResultData {
  reward_exp?: number
  practice_reward_exp?: number
  check_in_reward_exp?: number
  is_auto_checked_in?: boolean
  check_in_streak?: number | null
  family_code?: string | null
  tier_grade?: number | null
  exp?: number | null
  available_exp?: number | null
}

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const resultStore = useResultStore()

const loading = ref(true)
const sessionId = ref(0)
const report = ref<ReportData | null>(null)
const aiSummary = ref<PracticeAIEvaluation | null>(null)
const aiSummaryLoading = ref(false)
const aiSummaryGenerating = ref(false)
const aiSummaryError = ref('')
const aiSummaryCollapsed = ref(true)
const answerCardFilter = ref<'all' | 'wrong'>('all')
const submitResult = computed<SubmitResultData | null>(() => {
  if (resultStore.state.sessionId !== sessionId.value) {
    return null
  }
  return resultStore.state.submitResult || null
})
const rewardExp = computed(() => Number(submitResult.value?.reward_exp || 0))
const practiceRewardExp = computed(() => Number(submitResult.value?.practice_reward_exp || 0))
const checkInRewardExp = computed(() => Number(submitResult.value?.check_in_reward_exp || 0))
const rewardSubtitle = computed(() => {
  if (practiceRewardExp.value > 0 && checkInRewardExp.value > 0)
    return '答题奖励和自动签到已计入会员成长经验'
  if (checkInRewardExp.value > 0)
    return '达到今日条件，已自动完成签到'
  return '答对题目已计入会员成长经验'
})

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
const wrongQuestionIdSet = computed(() => {
  return new Set((report.value?.wrong_question_ids || []).map(item => Number(item)))
})

const wrongQuestionIdsParam = computed(() => {
  return Array.from(wrongQuestionIdSet.value).join(',')
})

const answerCardItems = computed(() => {
  const items = report.value?.answer_items || []
  if (answerCardFilter.value === 'wrong')
    return items.filter(item => wrongQuestionIdSet.value.has(Number(item.question_id)))
  return items
})

const answerGroups = computed<AnswerSheetGroup[]>(() => {
  const items = answerCardItems.value
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

function summaryPayload() {
  return aiSummary.value?.result_payload || null
}

function summaryStrengths() {
  return normalizeStringList(summaryPayload()?.strengths)
}

function summaryIssues() {
  return normalizeStringList(summaryPayload()?.high_frequency_issues)
}

function summaryNextActions() {
  return normalizeStringList(summaryPayload()?.next_actions)
}

function summaryWeakPoints() {
  const raw = summaryPayload()?.weak_knowledge_points
  if (!Array.isArray(raw))
    return []
  return raw
    .map((item) => ({
      name: String(item?.name || '').trim(),
      reason: String(item?.reason || '').trim(),
    }))
    .filter(item => item.name || item.reason)
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
    url: `/pages/practice/session/index?sessionId=${sessionId.value}&mode=review&viewMode=wrong&wrongOnly=1&wrongQuestionIds=${wrongQuestionIdsParam.value}`,
  })
}

function handleSelectItem(item: AnswerSheetItem) {
  if (!sessionId.value)
    return
  const viewMode = answerCardFilter.value === 'wrong' ? 'wrong' : 'all'
  const wrongQuery = viewMode === 'wrong' ? `&wrongOnly=1&wrongQuestionIds=${wrongQuestionIdsParam.value}` : ''
  uni.navigateTo({
    url: `/pages/practice/session/index?sessionId=${sessionId.value}&mode=review&viewMode=${viewMode}&gotoQuestionId=${item.id}${wrongQuery}`,
  })
}

async function loadReport() {
  if (!sessionId.value)
    return

  // 优先从内存 store 取（提交时已预取）
  const sameResultSession = resultStore.state.sessionId === sessionId.value
  if (resultStore.state.reportData && sameResultSession) {
    report.value = resultStore.state.reportData
    loading.value = false
    return
  }

  // 降级：从 API 请求
  loading.value = true
  try {
    const { data } = await api.qbankPracticeGetSessionReport({ path: { pk: sessionId.value } }) as any
    report.value = data
    const currentSameResultSession = resultStore.state.sessionId === sessionId.value
    resultStore.setResult(
      sessionId.value,
      data,
      currentSameResultSession ? resultStore.state.solutionData : null,
      currentSameResultSession ? resultStore.state.submitResult : null,
    )
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

async function loadSessionSolution() {
  if (!sessionId.value)
    return

  const sameResultSession = resultStore.state.sessionId === sessionId.value
  if (sameResultSession && Array.isArray(resultStore.state.solutionData))
    return

  try {
    const { data } = await api.qbankPracticeGetSessionSolution({ path: { pk: sessionId.value } }) as any
    const currentSameResultSession = resultStore.state.sessionId === sessionId.value
    resultStore.setResult(
      sessionId.value,
      currentSameResultSession ? resultStore.state.reportData : report.value,
      data,
      currentSameResultSession ? resultStore.state.submitResult : null,
    )
  }
  catch (error) {
    console.error('加载整套解析失败:', error)
  }
}

async function loadAISummary() {
  if (!sessionId.value)
    return

  aiSummaryLoading.value = true
  aiSummaryError.value = ''
  try {
    aiSummary.value = await getPracticeSessionAISummary(sessionId.value)
    aiSummaryCollapsed.value = Boolean(aiSummary.value)
  }
  catch (error: any) {
    const status = Number(error?.response?.status || error?.statusCode || 0)
    if (status !== 404) {
      aiSummaryError.value = String(error?.response?.data?.msg || error?.message || 'AI 总结加载失败').trim()
    }
    aiSummary.value = null
  }
  finally {
    aiSummaryLoading.value = false
  }
}

async function generateAISummary(forceRegenerate = false) {
  if (!sessionId.value || aiSummaryGenerating.value)
    return

  aiSummaryGenerating.value = true
  aiSummaryError.value = ''
  try {
    aiSummary.value = await generatePracticeSessionAISummary(sessionId.value, forceRegenerate)
    aiSummaryCollapsed.value = false
    uni.showToast({ title: forceRegenerate ? 'AI 总结已更新' : 'AI 总结已生成', icon: 'success' })
  }
  catch (error: any) {
    aiSummaryError.value = String(error?.response?.data?.msg || error?.message || 'AI 总结生成失败').trim()
    uni.showToast({ title: 'AI 总结生成失败', icon: 'none' })
  }
  finally {
    aiSummaryGenerating.value = false
  }
}

onLoad((query) => {
  sessionId.value = Number(query?.sessionId || resultStore.state.sessionId || 0)
  if (!sessionId.value) {
    uni.showToast({ title: '缺少会话参数', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 1500)
    return
  }
  Promise.all([loadReport(), loadSessionSolution(), loadAISummary()])
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

        <view v-if="rewardExp > 0" class="mt-4 overflow-hidden rounded-2xl border border-[#FDE68A] from-[#FFFBEB] to-[#EFF6FF] bg-gradient-to-br px-4 py-4 shadow-sm">
          <view class="flex items-center justify-between">
            <view class="flex items-center gap-3">
              <view class="h-11 w-11 flex items-center justify-center rounded-2xl bg-[#0F172A] text-[#FDE68A]">
                <view class="i-carbon-trophy text-[22px]" />
              </view>
              <view>
                <view class="text-[14px] text-[#0F172A] font-black">
                  本次练习奖励
                </view>
                <view class="mt-1 text-[11px] text-[#64748B]">
                  {{ rewardSubtitle }}
                </view>
              </view>
            </view>
            <view class="text-right">
              <view class="text-[24px] text-[#B45309] font-black">
                +{{ rewardExp }}
              </view>
              <view class="text-[11px] text-[#92400E]">
                经验
              </view>
            </view>
          </view>
          <view v-if="practiceRewardExp > 0 || checkInRewardExp > 0" class="mt-3 flex flex-wrap gap-2">
            <view v-if="practiceRewardExp > 0" class="rounded-full bg-white/80 px-3 py-1 text-[11px] text-[#92400E] font-bold">
              答题 +{{ practiceRewardExp }}
            </view>
            <view v-if="checkInRewardExp > 0" class="rounded-full bg-[#ECFDF5] px-3 py-1 text-[11px] text-[#047857] font-bold">
              自动签到 +{{ checkInRewardExp }}
            </view>
          </view>
          <view v-if="submitResult?.available_exp !== null && submitResult?.available_exp !== undefined" class="mt-3 rounded-xl bg-white/70 px-3 py-2 text-[11px] text-[#64748B]">
            当前可用经验 {{ submitResult.available_exp }}，累计经验 {{ submitResult.exp || 0 }}
          </view>
        </view>

        <view class="box-border mt-4 overflow-hidden border border-white/60 rounded-2xl bg-white/90 shadow-sm backdrop-blur-sm">
          <view class="flex items-center justify-between px-4 pb-1 pt-3.5" @click="aiSummary && (aiSummaryCollapsed = !aiSummaryCollapsed)">
            <view class="flex items-center gap-2">
              <view class="i-carbon-ai-generate text-[16px] text-[#0F766E]" />
              <text class="text-[13px] text-[#0F766E] font-bold">AI 练习总结</text>
            </view>
            <view class="flex items-center gap-2">
              <view
                class="rounded-full px-3 py-1 text-[11px] font-bold"
                :class="aiSummaryGenerating
                  ? 'bg-[#EFF6FF] text-[#2563EB]'
                  : aiSummary
                    ? 'bg-[#ECFDF5] text-[#059669]'
                    : 'bg-[#F8FAFC] text-[#64748B]'"
              >
                {{ aiSummaryGenerating ? '生成中' : aiSummary ? '已生成' : '未生成' }}
              </view>
              <view v-if="aiSummary" class="h-7 w-7 flex items-center justify-center rounded-full bg-[#F1F5F9] text-[#64748B]">
                <view :class="aiSummaryCollapsed ? 'i-carbon-chevron-down' : 'i-carbon-chevron-up'" class="text-[15px]" />
              </view>
            </view>
          </view>

          <view v-if="aiSummary && aiSummaryCollapsed" class="px-4 pb-4 pt-2">
            <view class="rounded-2xl bg-[#F8FAFC] px-4 py-3 text-[13px] text-[#64748B] leading-[1.7]">
              AI 总结已收起，点击标题栏展开查看。
            </view>
          </view>

          <view v-else-if="aiSummaryLoading" class="px-4 pb-4 pt-2 text-[13px] text-[#64748B]">
            正在加载 AI 总结...
          </view>

          <view v-else-if="aiSummary" class="px-4 pb-4 pt-2">
            <view v-if="aiSummary.summary_text" class="rounded-2xl bg-[#F8FAFC] px-4 py-4 text-[14px] text-[#334155]">
              <AiRichContent :content="aiSummary.summary_text" />
            </view>

            <view v-if="summaryStrengths().length" class="mt-3 rounded-2xl bg-[#ECFDF5] px-4 py-4">
              <view class="text-[12px] text-[#15803D] font-bold">
                本次表现亮点
              </view>
              <view class="mt-2 flex flex-col gap-2 text-[13px] text-[#166534]">
                <view v-for="(line, lineIndex) in summaryStrengths()" :key="`strength-${lineIndex}`">
                  {{ line }}
                </view>
              </view>
            </view>

            <view v-if="summaryIssues().length" class="mt-3 rounded-2xl bg-[#FFF7ED] px-4 py-4">
              <view class="text-[12px] text-[#C2410C] font-bold">
                高频问题
              </view>
              <view class="mt-2 flex flex-col gap-2 text-[13px] text-[#9A3412]">
                <view v-for="(line, lineIndex) in summaryIssues()" :key="`issue-${lineIndex}`">
                  {{ line }}
                </view>
              </view>
            </view>

            <view v-if="summaryWeakPoints().length" class="mt-3 rounded-2xl bg-[#EFF6FF] px-4 py-4">
              <view class="text-[12px] text-[#1D4ED8] font-bold">
                薄弱知识点
              </view>
              <view class="mt-2 flex flex-col gap-3 text-[13px] text-[#1E3A8A]">
                <view v-for="(item, index) in summaryWeakPoints()" :key="`weak-${index}`">
                  <view class="font-bold">
                    {{ item.name || '待补强' }}
                  </view>
                  <view v-if="item.reason" class="mt-1 leading-[1.7]">
                    {{ item.reason }}
                  </view>
                </view>
              </view>
            </view>

            <view v-if="summaryNextActions().length" class="mt-3 rounded-2xl bg-[#F5F3FF] px-4 py-4">
              <view class="text-[12px] text-[#6D28D9] font-bold">
                下一步建议
              </view>
              <view class="mt-2 flex flex-col gap-2 text-[13px] text-[#6D28D9]">
                <view v-for="(line, lineIndex) in summaryNextActions()" :key="`action-${lineIndex}`">
                  {{ line }}
                </view>
              </view>
            </view>

            <view v-if="summaryPayload()?.encouragement" class="mt-3 rounded-2xl bg-[#FDF4FF] px-4 py-4 text-[13px] text-[#A21CAF]">
              <AiRichContent :content="summaryPayload()?.encouragement || ''" />
            </view>

            <view class="mt-4 flex justify-end">
              <view
                class="inline-flex items-center gap-1 rounded-full bg-[#0F766E] px-3 py-1.5 text-[12px] text-white font-bold active:scale-95"
                @click="generateAISummary(true)"
              >
                <view class="i-carbon-renew text-[13px]" />
                <text>{{ aiSummaryGenerating ? '生成中...' : '重新生成' }}</text>
              </view>
            </view>
          </view>

          <view v-else class="px-4 pb-4 pt-2">
            <view class="rounded-2xl bg-[#F8FAFC] px-4 py-4 text-[13px] text-[#64748B] leading-[1.8]">
              {{ aiSummaryError || '这次练习还没有 AI 总结。你可以手动生成一份，看看整体表现、薄弱点和下一步建议。' }}
            </view>
            <view class="mt-4 flex justify-end">
              <view
                class="inline-flex items-center gap-1 rounded-full bg-[#0F766E] px-3 py-1.5 text-[12px] text-white font-bold active:scale-95"
                @click="generateAISummary()"
              >
                <view class="i-carbon-ai-generate text-[13px]" />
                <text>{{ aiSummaryGenerating ? '生成中...' : '生成 AI 总结' }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 答题卡（按章节分组） -->
        <view v-if="report.answer_items?.length" class="box-border mt-4 overflow-hidden border border-white/60 rounded-2xl bg-white/90 shadow-sm backdrop-blur-sm">
          <view class="flex items-center justify-between px-4 pb-1 pt-3.5">
            <text class="text-[13px] text-[#475569] font-bold">答题卡</text>
            <view class="flex items-center rounded-full bg-[#F1F5F9] p-0.5">
              <view
                class="rounded-full px-3 py-1 text-[11px] font-bold"
                :class="answerCardFilter === 'all' ? 'bg-white text-[#2563EB] shadow-sm' : 'text-[#64748B]'"
                @click="answerCardFilter = 'all'"
              >
                全部
              </view>
              <view
                class="rounded-full px-3 py-1 text-[11px] font-bold"
                :class="answerCardFilter === 'wrong' ? 'bg-white text-[#EF4444] shadow-sm' : 'text-[#64748B]'"
                @click="answerCardFilter = 'wrong'"
              >
                错题
              </view>
            </view>
          </view>
          <view class="px-4">
            <AnswerSheet :groups="answerGroups" @select="handleSelectItem" />
            <view v-if="!answerGroups.length" class="py-8 text-center text-[13px] text-[#94A3B8]">
              当前没有错题，继续保持。
            </view>
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
