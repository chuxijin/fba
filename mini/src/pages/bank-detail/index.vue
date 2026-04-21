<script lang="ts" setup>
import { onLoad, onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { fbaApi } from '@/api/sdk'
import MembershipModal from '@/components/MembershipModal.vue'
import RenderBookExportPopup from '@/components/RenderBookExportPopup.vue'
import { useMembershipStore, useTokenStore } from '@/store'
import { exportMiniRenderBook } from '@/utils/renderBook'
import type { ExportScope, RenderBookExportSubmitPayload } from '@/utils/renderBook'
import { getAppSettings } from '@/utils/appSettings'
import { isMembershipAccessError } from '@/utils/membershipAccess'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

type PracticeMode = 'exam' | 'practice' | 'memorize'

interface ChapterNode {
  id: number
  name: string
  code: string | null
  level: number
  sort_order: number
  parent_id: number | null
  q_count_cache: number
  children: ChapterNode[]
}

interface BankDetail {
  id: number
  name: string
  desc: string | null
  q_count_cache: number
  bank_type: number
  cover_url: string | null
  difficulty: number | null
  access_entitlement_code?: string | null
  chapters: ChapterNode[]
}

interface ChapterProgressNode {
  chapter_id: number
  name: string
  question_count: number
  answer_count: number
  correct_count: number
  correct_ratio: number
  children: ChapterProgressNode[]
}

interface ChapterProgress {
  bank_id: number
  total_question_count: number
  total_answer_count: number
  total_correct_count: number
  chapters: ChapterProgressNode[]
}

interface BankExportTarget {
  scope: ExportScope
  state: 'bank' | 'chapter'
  chapterId?: number | null
}

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const tokenStore = useTokenStore()
const membershipStore = useMembershipStore()

const bankId = ref(0)
const loading = ref(false)
const bank = ref<BankDetail | null>(null)
const expandedChapters = ref<Set<number>>(new Set())
const progress = ref<ChapterProgress | null>(null)
const showMembershipModal = ref(false)
const requiresMembership = ref(false)
const initialized = ref(false)
const exportingBank = ref(false)
const exportingChapterId = ref<number | null>(null)
const showExportPopup = ref(false)
const exportTarget = ref<BankExportTarget | null>(null)

const totalQuestionCount = computed(() => progress.value?.total_question_count ?? bank.value?.q_count_cache ?? 0)
const totalAnswerCount = computed(() => progress.value?.total_answer_count ?? 0)
const totalCorrectRatio = computed(() => {
  if (!totalAnswerCount.value)
    return 0
  return Math.round((progress.value?.total_correct_count ?? 0) / totalAnswerCount.value * 100)
})
const actionButtonLabel = computed(() => {
  if (requiresMembership.value && !membershipStore.isVip) {
    return '开通会员后刷题'
  }

  return '开始刷题'
})

// 章节进度 map，方便 O(1) 查找
const progressMap = computed(() => {
  const map: Record<number, ChapterProgressNode> = {}
  if (!progress.value?.chapters)
    return map

  function walk(nodes: ChapterProgressNode[]) {
    for (const node of nodes) {
      map[node.chapter_id] = node
      if (node.children?.length)
        walk(node.children)
    }
  }
  walk(progress.value.chapters)
  return map
})

function goBack() {
  uni.navigateBack()
}

function toggleChapter(id: number) {
  if (expandedChapters.value.has(id))
    expandedChapters.value.delete(id)
  else
    expandedChapters.value.add(id)
}

function currentPracticeMode(): PracticeMode {
  return getAppSettings().practiceMode as PracticeMode
}

function navigateToPracticeSession(sessionId: number, mode: PracticeMode, displayTotalCount?: number) {
  if (!sessionId)
    return
  const params = [`sessionId=${sessionId}`, `mode=${mode}`]
  if (displayTotalCount && displayTotalCount > 0)
    params.push(`displayTotalCount=${displayTotalCount}`)
  uni.navigateTo({
    url: `/pages/practice/session/index?${params.join('&')}`,
  })
}

function openMembershipModalByGuard() {
  requiresMembership.value = true
  showMembershipModal.value = true
}

async function syncMembershipState() {
  if (!tokenStore.updateNowTime().hasLogin) {
    return
  }

  await membershipStore.fetchMembership()
}

async function startPracticeByBank() {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (!bank.value)
    return

  const mode = currentPracticeMode()
  try {
    const session = await fbaApi.qbank.session.create({
      session_type: mode === 'exam' ? 'exam' : 'bank',
      practice_name: bank.value.name,
      bank_id: bank.value.id,
      exam_config: {
        practice_mode: mode,
        entry: 'mini-bank-detail',
        display_total_count: totalQuestionCount.value,
      },
    } as any)
    navigateToPracticeSession(Number((session as any)?.id || 0), mode, totalQuestionCount.value)
  }
  catch (error) {
    if (isMembershipAccessError(error)) {
      openMembershipModalByGuard()
      return
    }

    console.error('创建刷题会话失败:', error)
    uni.showToast({ title: '创建刷题会话失败', icon: 'none' })
  }
}

async function startPracticeByChapter(chapter: ChapterNode) {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }

  const mode = currentPracticeMode()
  try {
    const session = await fbaApi.qbank.session.create({
      session_type: mode === 'exam' ? 'exam' : 'bank',
      practice_name: chapter.name,
      bank_id: bank.value?.id,
      chapter_id: chapter.id,
      exam_config: {
        practice_mode: mode,
        entry: 'mini-bank-detail',
        display_total_count: totalQuestionCount.value,
        chapter_question_count: chapter.q_count_cache,
      },
    } as any)
    navigateToPracticeSession(Number((session as any)?.id || 0), mode, totalQuestionCount.value)
  }
  catch (error) {
    if (isMembershipAccessError(error)) {
      openMembershipModalByGuard()
      return
    }

    console.error('创建刷题会话失败:', error)
    uni.showToast({ title: '创建刷题会话失败', icon: 'none' })
  }
}

async function exportBankQuestions() {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (!bank.value || exportingBank.value) {
    return
  }

  exportTarget.value = {
    scope: {
      sourceType: 'placement',
      templateKey: 'exam_paper',
      title: `${bank.value.name}题本`,
      bankId: bank.value.id,
    },
    state: 'bank',
  }
  showExportPopup.value = true
}

async function exportChapterQuestions(chapter: ChapterNode) {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (!bank.value || exportingChapterId.value === chapter.id) {
    return
  }

  exportTarget.value = {
    scope: {
      sourceType: 'placement',
      templateKey: 'exam_paper',
      title: `${chapter.name}题本`,
      bankId: bank.value.id,
      chapterId: chapter.id,
    },
    state: 'chapter',
    chapterId: chapter.id,
  }
  showExportPopup.value = true
}

async function submitExport(payload: RenderBookExportSubmitPayload) {
  const target = exportTarget.value
  if (!target) {
    return
  }

  if (target.state === 'bank') {
    exportingBank.value = true
  } else {
    exportingChapterId.value = target.chapterId ?? null
  }

  try {
    await exportMiniRenderBook({
      ...target.scope,
      settings: payload.settings,
      questionCount: payload.questionCount,
      yearStart: payload.yearStart,
      yearEnd: payload.yearEnd,
    })
  }
  catch (error) {
    if (isMembershipAccessError(error)) {
      openMembershipModalByGuard()
    }
  }
  finally {
    if (target.state === 'bank') {
      exportingBank.value = false
    }
    if (target.state === 'chapter' && exportingChapterId.value === target.chapterId) {
      exportingChapterId.value = null
    }
    exportTarget.value = null
  }
}

function handleExportPopupChange(value: boolean) {
  showExportPopup.value = value
  if (!value) {
    exportTarget.value = null
  }
}

async function loadBankDetail() {
  if (!bankId.value)
    return

  loading.value = true
  try {
    const data = await fbaApi.qbank.bank.getDetail(bankId.value) as any
    bank.value = data
    requiresMembership.value = Boolean(data?.access_entitlement_code) && !membershipStore.isVip
  }
  catch (error) {
    console.error('加载题库详情失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

async function loadProgress() {
  if (!bankId.value || !tokenStore.updateNowTime().hasLogin)
    return

  try {
    progress.value = await fbaApi.qbank.bank.getChapterProgress(bankId.value) as any
    requiresMembership.value = Boolean(bank.value?.access_entitlement_code) && !membershipStore.isVip
  }
  catch (error) {
    if (isMembershipAccessError(error)) {
      requiresMembership.value = true
      return
    }

    // 未登录或接口异常时不影响页面展示
  }
}

function getChapterProgress(chapterId: number) {
  return progressMap.value[chapterId]
}

function progressPercent(chapterId: number): number {
  const p = getChapterProgress(chapterId)
  if (!p || !p.question_count)
    return 0
  return Math.round(p.answer_count / p.question_count * 100)
}

async function refreshPageData() {
  await syncMembershipState()
  await loadBankDetail()
  await loadProgress()
}

onLoad((query) => {
  bankId.value = Number(query?.id || 0)
  if (bankId.value) {
    void refreshPageData().finally(() => {
      initialized.value = true
    })
  }
})

onShow(() => {
  // 从刷题页返回时刷新进度
  if (!bankId.value || !initialized.value)
    return

  void syncMembershipState().finally(() => {
    if (!bank.value) {
      void loadBankDetail()
      void loadProgress()
      return
    }

    requiresMembership.value = Boolean(bank.value.access_entitlement_code) && !membershipStore.isVip
    void loadProgress()
  })
})
</script>

<template>
  <view class="relative min-h-screen from-[#EFF6FF] via-[#F8FBFF] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">题库详情</text>
      </view>
    </view>

    <!-- 加载中 -->
    <view v-if="loading" class="py-20 text-center text-[14px] text-[#94A3B8]">
      加载中...
    </view>

    <template v-else-if="bank">
      <!-- 题库信息卡 -->
      <view class="mx-4 mt-4 overflow-hidden border border-white/60 rounded-3xl bg-white/90 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)] backdrop-blur-md">
        <view class="relative overflow-hidden px-5 pb-5 pt-6">
          <view class="text-[18px] text-[#1E293B] font-black leading-snug">
            {{ bank.name }}
          </view>

          <!-- 统计条 -->
          <view class="mt-4 flex items-center gap-4">
            <view class="flex items-center gap-1.5">
              <view class="h-7 w-7 flex items-center justify-center rounded-lg bg-[#EFF6FF]">
                <view class="i-carbon-document text-[14px] text-[#3B82F6]" />
              </view>
              <view class="text-[13px]">
                <text class="text-[#1E293B] font-black">{{ totalQuestionCount }}</text>
                <text class="ml-0.5 text-[#94A3B8]">题</text>
              </view>
            </view>
            <view class="flex items-center gap-1.5">
              <view class="h-7 w-7 flex items-center justify-center rounded-lg bg-[#F0FDF4]">
                <view class="i-carbon-checkmark text-[14px] text-[#10B981]" />
              </view>
              <view class="text-[13px]">
                <text class="text-[#1E293B] font-black">{{ totalAnswerCount }}</text>
                <text class="ml-0.5 text-[#94A3B8]">已做</text>
              </view>
            </view>
            <view class="flex items-center gap-1.5">
              <view class="h-7 w-7 flex items-center justify-center rounded-lg bg-[#F5F3FF]">
                <view class="i-carbon-analytics text-[14px] text-[#7C3AED]" />
              </view>
              <view class="text-[13px]">
                <text class="text-[#1E293B] font-black">{{ totalCorrectRatio }}%</text>
                <text class="ml-0.5 text-[#94A3B8]">正确率</text>
              </view>
            </view>
          </view>
          <!-- 总进度条 -->
          <view v-if="totalAnswerCount > 0" class="mt-3">
            <view class="h-2 overflow-hidden rounded-full bg-[#E2E8F0]">
              <view
                class="h-full rounded-full from-[#3B82F6] to-[#2563EB] bg-gradient-to-r transition-all duration-500"
                :style="{ width: `${Math.min(Math.round(totalAnswerCount / totalQuestionCount * 100), 100)}%` }"
              />
            </view>
            <view class="mt-1 text-right text-[11px] text-[#94A3B8]">
              {{ totalAnswerCount }}/{{ totalQuestionCount }}
            </view>
          </view>
        </view>
      </view>

      <!-- 章节列表 -->
      <view v-if="bank.chapters?.length" class="mx-4 mt-4 pb-28">
        <view class="mb-3 flex items-center justify-between pl-1">
          <text class="text-[13px] text-[#475569] font-bold">章节目录</text>
        </view>
        <view class="flex flex-col gap-2.5">
          <view
            v-for="chapter in bank.chapters"
            :key="chapter.id"
            class="overflow-hidden border border-white/60 rounded-2xl bg-white/90 shadow-sm backdrop-blur-sm"
          >
            <view class="flex items-center px-4 py-3.5" @click="chapter.children?.length ? toggleChapter(chapter.id) : startPracticeByChapter(chapter)">
              <view class="mr-3 h-9 w-9 flex shrink-0 items-center justify-center rounded-xl shadow-inner" :class="chapter.children?.length ? 'bg-[#ECFDF5]' : 'bg-[#EFF6FF]'">
                <view :class="chapter.children?.length ? 'i-carbon-folder text-[18px] text-[#10B981]' : 'i-carbon-document text-[18px] text-[#3B82F6]'" />
              </view>
              <view class="min-w-0 flex-1">
                <view class="text-[15px] text-[#1E293B] font-bold">
                  {{ chapter.name }}
                </view>
                <view class="mt-0.5 flex items-center gap-2 text-[11px] text-[#94A3B8]">
                  <text>{{ (getChapterProgress(chapter.id)?.question_count ?? chapter.q_count_cache) || 0 }} 题</text>
                  <template v-if="getChapterProgress(chapter.id)?.answer_count">
                    <text>·</text>
                    <text class="text-[#3B82F6]">已做 {{ getChapterProgress(chapter.id)!.answer_count }}</text>
                    <text v-if="getChapterProgress(chapter.id)!.correct_ratio > 0" class="text-[#10B981]">
                      {{ getChapterProgress(chapter.id)!.correct_ratio }}%
                    </text>
                  </template>
                </view>
                <!-- 章节进度条 -->
                <view v-if="progressPercent(chapter.id) > 0" class="mt-1.5">
                  <view class="h-1.5 overflow-hidden rounded-full bg-[#E2E8F0]">
                    <view
                      class="h-full rounded-full from-[#3B82F6] to-[#60A5FA] bg-gradient-to-r transition-all duration-500"
                      :style="{ width: `${Math.min(progressPercent(chapter.id), 100)}%` }"
                    />
                  </view>
                </view>
              </view>
              <view class="ml-2 flex items-center gap-2">
                <view
                  class="rounded-full border border-[#DBEAFE] px-3 py-1 text-[11px] text-[#2563EB] font-semibold"
                  :class="exportingChapterId === chapter.id ? 'bg-[#EFF6FF] opacity-70' : 'bg-white'"
                  @click.stop="exportChapterQuestions(chapter)"
                >
                  {{ exportingChapterId === chapter.id ? '导出中' : '导出题本' }}
                </view>
                <view
                  v-if="chapter.children?.length"
                  class="i-carbon-chevron-down text-lg text-[#94A3B8] transition-transform duration-300"
                  :style="{ transform: expandedChapters.has(chapter.id) ? 'rotate(180deg)' : 'rotate(0deg)' }"
                />
                <view v-else class="i-carbon-chevron-right text-lg text-[#CBD5E1]" />
              </view>
            </view>

            <!-- 子章节 -->
            <template v-if="chapter.children?.length && expandedChapters.has(chapter.id)">
              <view class="mx-4 h-px from-transparent via-[#E2E8F0] to-transparent bg-gradient-to-r" />
              <view
                v-for="sub in chapter.children"
                :key="sub.id"
                class="flex items-center px-4 py-3 pl-14 active:bg-gray-50"
                @click="startPracticeByChapter(sub)"
              >
                <view class="min-w-0 flex-1">
                  <view class="text-[14px] text-[#334155] font-medium">
                    {{ sub.name }}
                  </view>
                  <view class="mt-0.5 flex items-center gap-2 text-[11px] text-[#94A3B8]">
                    <text>{{ (getChapterProgress(sub.id)?.question_count ?? sub.q_count_cache) || 0 }} 题</text>
                    <template v-if="getChapterProgress(sub.id)?.answer_count">
                      <text>·</text>
                      <text class="text-[#3B82F6]">已做 {{ getChapterProgress(sub.id)!.answer_count }}</text>
                      <text v-if="getChapterProgress(sub.id)!.correct_ratio > 0" class="text-[#10B981]">
                        {{ getChapterProgress(sub.id)!.correct_ratio }}%
                      </text>
                    </template>
                  </view>
                  <!-- 子章节进度条 -->
                  <view v-if="progressPercent(sub.id) > 0" class="mt-1.5">
                    <view class="h-1 overflow-hidden rounded-full bg-[#E2E8F0]">
                      <view
                        class="h-full rounded-full from-[#3B82F6] to-[#60A5FA] bg-gradient-to-r transition-all duration-500"
                        :style="{ width: `${Math.min(progressPercent(sub.id), 100)}%` }"
                      />
                    </view>
                  </view>
                </view>
                <view class="ml-2 flex items-center gap-2">
                  <view
                    class="rounded-full border border-[#DBEAFE] px-3 py-1 text-[11px] text-[#2563EB] font-semibold"
                    :class="exportingChapterId === sub.id ? 'bg-[#EFF6FF] opacity-70' : 'bg-white'"
                    @click.stop="exportChapterQuestions(sub)"
                  >
                    {{ exportingChapterId === sub.id ? '导出中' : '导出题本' }}
                  </view>
                  <view class="i-carbon-chevron-right text-lg text-[#CBD5E1]" />
                </view>
              </view>
            </template>
          </view>
        </view>
      </view>

      <!-- 无章节 -->
      <view v-else class="mx-4 mt-4 pb-28">
        <view class="rounded-2xl bg-white/80 px-5 py-8 text-center shadow-sm">
          <text class="text-[14px] text-[#94A3B8]">该题库暂无章节划分</text>
        </view>
      </view>

      <!-- 底部开始练习按钮 -->
      <view class="fixed bottom-0 left-0 right-0 z-30 border-t border-white/40 bg-white/95 px-5 pb-[env(safe-area-inset-bottom)] pt-3 backdrop-blur-md">
        <view class="flex items-center gap-3">
          <view
            class="h-12 flex flex-1 items-center justify-center rounded-2xl border border-[#DBEAFE] bg-white text-[15px] text-[#2563EB] font-bold active:scale-[0.98]"
            :class="exportingBank ? 'opacity-70' : ''"
            @click="exportBankQuestions"
          >
            <view v-if="exportingBank" class="i-carbon-circle-dash animate-spin text-lg mr-1.5" />
            <view v-else class="i-carbon-document-pdf text-lg mr-1.5" />
            {{ exportingBank ? '导出中...' : '导出题本' }}
          </view>
          <view
            class="h-12 flex flex-[1.35] items-center justify-center rounded-2xl text-[16px] text-white font-black active:scale-[0.98]"
            :class="requiresMembership && !membershipStore.isVip
              ? 'from-[#F59E0B] to-[#B45309] bg-gradient-to-r shadow-[0_4px_14px_rgba(245,158,11,0.35)]'
              : 'from-[#3B82F6] to-[#2563EB] bg-gradient-to-r shadow-[0_4px_14px_rgba(59,130,246,0.35)]'"
            @click="startPracticeByBank"
          >
            {{ actionButtonLabel }}
          </view>
        </view>
      </view>
    </template>

    <view v-else class="py-20 text-center text-[14px] text-[#94A3B8]">
      题库不存在或已下架
    </view>

    <MembershipModal v-model="showMembershipModal" />
    <RenderBookExportPopup
      :model-value="showExportPopup"
      template-key="exam_paper"
      :title="exportTarget?.scope.title || '导出题本'"
      @update:model-value="handleExportPopupChange"
      @confirm="submitExport"
    />
  </view>
</template>
