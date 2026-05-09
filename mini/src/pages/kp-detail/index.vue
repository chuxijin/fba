<script lang="ts" setup>
import { onLoad, onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { api } from '@/api/sdk'
import MembershipModal from '@/components/MembershipModal.vue'
import RenderBookExportPopup from '@/components/RenderBookExportPopup.vue'
import { useMembershipStore, useTokenStore } from '@/store'
import { getAppSettings } from '@/utils/appSettings'
import { isMembershipAccessError } from '@/utils/membershipAccess'
import { exportMiniRenderBook } from '@/utils/renderBook'
import type { ExportScope, RenderBookExportSubmitPayload } from '@/utils/renderBook'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

type PracticeMode = 'exam' | 'practice' | 'memorize'

interface CategoryNode {
  id: number
  name: string
  app_code?: string
  type?: string
  code?: string | null
  description?: string | null
  children?: CategoryNode[] | null
}

interface KpProgressNode {
  name: string
  question_count: number
  answer_count: number
  correct_count: number
  correct_ratio: number
}

interface KpItem {
  id: number
  name: string
  question_count: number
  answer_count?: number
  correct_count?: number
  correct_ratio?: number
  children: KpItem[]
}

interface KpExportTarget {
  scope: ExportScope
  state: 'single' | 'all'
  itemId?: number | null
  totalQuestionCount: number
}

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const tokenStore = useTokenStore()
const membershipStore = useMembershipStore()

const categoryId = ref(0)
const categoryName = ref('')
const loading = ref(false)
const showMembershipModal = ref(false)
const initialized = ref(false)
const kpItems = ref<KpItem[]>([])
const kpProgressMap = ref<Record<string, KpProgressNode>>({})
const expandedIds = ref<Set<number>>(new Set())
const totalQuestionCount = ref(0)
const totalAnswerCount = ref(0)
const totalCorrectCount = ref(0)
const loadingItemId = ref<number | null>(null)
const exportingItemId = ref<number | null>(null)
const exportingAll = ref(false)
const showExportPopup = ref(false)
const exportTarget = ref<KpExportTarget | null>(null)

const hasKpItems = computed(() => kpItems.value.length > 0)

function goBack() {
  uni.navigateBack()
}

function toggleExpand(id: number) {
  if (expandedIds.value.has(id))
    expandedIds.value.delete(id)
  else
    expandedIds.value.add(id)
}

function currentPracticeMode(): PracticeMode {
  return getAppSettings().practiceMode as PracticeMode
}

function navigateToPracticeSession(sessionId: number, mode: PracticeMode) {
  if (!sessionId)
    return
  uni.navigateTo({
    url: `/pages/practice/session/index?sessionId=${sessionId}&mode=${mode}`,
  })
}

function patchProgressToTree(nodes: KpItem[]) {
  for (const node of nodes) {
    const progress = kpProgressMap.value[node.name]
    if (progress) {
      node.answer_count = progress.answer_count
      node.correct_count = progress.correct_count
      node.correct_ratio = progress.correct_ratio
    }
    if (node.children?.length) {
      patchProgressToTree(node.children)
    }
  }
}

async function loadKpProgress() {
  if (!categoryId.value || !tokenStore.hasLogin) return
  try {
    const { data: res } = await api.qbankGetKpProgress({ path: { pk: categoryId.value } }) as any
    totalAnswerCount.value = res.total_answer_count || 0
    totalCorrectCount.value = res.total_correct_count || 0
    
    const pMap: Record<string, KpProgressNode> = {}
    for (const item of res.items || []) {
      pMap[item.name] = item
    }
    kpProgressMap.value = pMap
    patchProgressToTree(kpItems.value)
  } catch (error) {
    console.error('加载知识点进度失败:', error)
  }
}

async function loadKpDetail() {
  if (!categoryId.value)
    return

  loading.value = true
  try {
    const { data: res } = await api.qbankGetKpDetail({ path: { pk: categoryId.value } }) as any
    
    categoryName.value = res.name
    kpItems.value = res.children || []
    totalQuestionCount.value = res.total_question_count || 0

    await loadKpProgress()
  }
  catch (error) {
    console.error('加载知识点详情失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

function findNodeById(nodes: CategoryNode[], targetId: number): CategoryNode | null {
  for (const node of nodes) {
    if (node.id === targetId)
      return node
    const child = findNodeById(node.children || [], targetId)
    if (child)
      return child
  }
  return null
}

async function startPracticeByKp(kpName: string, itemId: number) {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }

  loadingItemId.value = itemId
  const mode = currentPracticeMode()
  const settings = getAppSettings()
  const currentYear = new Date().getFullYear()
  const yearRange = settings.randomPracticeYearRange

  let yearStart: number | undefined
  let yearEnd: number | undefined
  if (yearRange === 'last_3_years') {
    yearStart = currentYear - 2
    yearEnd = currentYear
  } else if (yearRange === 'last_5_years') {
    yearStart = currentYear - 4
    yearEnd = currentYear
  }

  try {
    const { data: session } = await api.qbankPracticeCreateSession({
      body: {
        session_type: mode === 'exam' ? 'exam' : 'random',
        practice_name: kpName,
        knowledge_point: [kpName],
        shuffle: true,
        limit: settings.randomPracticeCount,
        year_start: yearStart,
        year_end: yearEnd,
        exam_config: {
          practice_mode: mode,
          entry: 'mini-kp-detail',
        },
      } as any,
    })
    navigateToPracticeSession(Number((session as any)?.id || 0), mode)
  }
  catch (error) {
    if (isMembershipAccessError(error)) {
      showMembershipModal.value = true
      return
    }
    console.error('创建练习会话失败:', error)
    uni.showToast({ title: '创建练习会话失败', icon: 'none' })
  }
  finally {
    loadingItemId.value = null
  }
}

async function startPracticeAll() {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }

  if (!totalQuestionCount.value) {
    uni.showToast({ title: '暂无可练习题目', icon: 'none' })
    return
  }

  loadingItemId.value = -1
  const mode = currentPracticeMode()
  const settings = getAppSettings()
  const currentYear = new Date().getFullYear()
  const yearRange = settings.randomPracticeYearRange
  const allKpNames = kpItems.value.flatMap(item => collectLeafNames(item))

  let yearStart: number | undefined
  let yearEnd: number | undefined
  if (yearRange === 'last_3_years') {
    yearStart = currentYear - 2
    yearEnd = currentYear
  } else if (yearRange === 'last_5_years') {
    yearStart = currentYear - 4
    yearEnd = currentYear
  }

  try {
    const { data: session } = await api.qbankPracticeCreateSession({
      body: {
        session_type: mode === 'exam' ? 'exam' : 'random',
        practice_name: categoryName.value,
        knowledge_point: allKpNames,
        shuffle: true,
        limit: settings.randomPracticeCount,
        year_start: yearStart,
        year_end: yearEnd,
        exam_config: {
          practice_mode: mode,
          entry: 'mini-kp-detail',
        },
      } as any,
    })
    navigateToPracticeSession(Number((session as any)?.id || 0), mode)
  }
  catch (error) {
    if (isMembershipAccessError(error)) {
      showMembershipModal.value = true
      return
    }
    console.error('创建练习会话失败:', error)
    uni.showToast({ title: '创建练习会话失败', icon: 'none' })
  }
  finally {
    loadingItemId.value = null
  }
}

function collectLeafNames(item: KpItem): string[] {
  if (!item.children || !item.children.length)
    return [item.name]
  return item.children.flatMap(child => collectLeafNames(child))
}

async function exportKpQuestions(item: KpItem) {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (exportingItemId.value === item.id || exportingAll.value) {
    return
  }

  if (!item.question_count) {
    uni.showToast({ title: '暂无可导出题目', icon: 'none' })
    return
  }

  exportTarget.value = {
    scope: {
      sourceType: 'placement',
      templateKey: 'practice',
      bookKind: 'custom',
      title: `${item.name}题本`,
      knowledgePoint: item.name,
    },
    state: 'single',
    itemId: item.id,
    totalQuestionCount: item.question_count,
  }
  showExportPopup.value = true
}

async function exportAllKpQuestions() {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (exportingAll.value || exportingItemId.value) {
    return
  }

  if (!totalQuestionCount.value) {
    uni.showToast({ title: '暂无可导出题目', icon: 'none' })
    return
  }

  const allKpNames = kpItems.value.flatMap(item => collectLeafNames(item))
  exportTarget.value = {
    scope: {
      sourceType: 'placement',
      templateKey: 'practice',
      bookKind: 'custom',
      title: `${categoryName.value}题本`,
      knowledgePoint: allKpNames,
    },
    state: 'all',
    totalQuestionCount: totalQuestionCount.value,
  }
  showExportPopup.value = true
}

async function submitExport(payload: RenderBookExportSubmitPayload) {
  const target = exportTarget.value
  if (!target) {
    return
  }

  if (target.state === 'all') {
    exportingAll.value = true
  } else {
    exportingItemId.value = target.itemId ?? null
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
      showMembershipModal.value = true
    }
  }
  finally {
    if (target.state === 'all') {
      exportingAll.value = false
    }
    if (target.state === 'single' && exportingItemId.value === target.itemId) {
      exportingItemId.value = null
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

async function syncMembershipState() {
  if (!tokenStore.updateNowTime().hasLogin)
    return
  await membershipStore.fetchMembership()
}

onLoad((query) => {
  categoryId.value = Number(query?.id || 0)
  if (categoryId.value) {
    void syncMembershipState().then(() => loadKpDetail()).finally(() => {
      initialized.value = true
    })
  }
})

onShow(() => {
  if (!categoryId.value || !initialized.value)
    return
  void syncMembershipState()
  void loadKpProgress()
})
</script>

<template>
  <view class="relative min-h-screen from-[#EFF6FF] via-[#F8FBFF] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">知识点详情</text>
      </view>
    </view>

    <!-- 加载中 -->
    <view v-if="loading" class="py-20 text-center text-[14px] text-[#94A3B8]">
      加载中...
    </view>

    <template v-else-if="hasKpItems">
      <!-- 知识点信息卡 -->
      <view class="mx-4 mt-4 overflow-hidden border border-white/60 rounded-3xl bg-white/90 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)] backdrop-blur-md">
        <view class="relative overflow-hidden px-5 pb-5 pt-6">
          <view class="text-[18px] text-[#1E293B] font-black leading-snug">
            {{ categoryName }}
          </view>
          <!-- 统计与进度 -->
          <view class="mt-5">
            <view class="flex items-center gap-4 mb-4">
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
                  <view class="i-carbon-tree-view-alt text-[14px] text-[#10B981]" />
                </view>
                <view class="text-[13px]">
                  <text class="text-[#1E293B] font-black">{{ kpItems.length }}</text>
                  <text class="ml-0.5 text-[#94A3B8]">个目录</text>
                </view>
              </view>
            </view>
            
            <view v-if="tokenStore.hasLogin">
              <view class="mb-2 flex items-center justify-between">
                <view class="text-[12px] text-[#64748B] font-medium">总练习进度</view>
                <view class="text-[12px] text-[#475569] font-bold">
                  {{ totalAnswerCount }} / {{ totalQuestionCount }}
                  <text class="ml-1 text-[11px] text-[#94A3B8] font-normal" v-if="totalAnswerCount > 0">
                    正确率 {{ Math.round(totalCorrectCount / totalAnswerCount * 100) }}%
                  </text>
                </view>
              </view>
              <view class="h-1.5 w-full overflow-hidden rounded-full bg-[#E2E8F0]">
                <view
                  class="h-full rounded-full bg-gradient-to-r from-[#3B82F6] to-[#60A5FA] transition-all duration-700 ease-out"
                  :style="{ width: `${totalQuestionCount > 0 ? Math.min(100, (totalAnswerCount / totalQuestionCount) * 100) : 0}%` }"
                />
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- 子知识点列表 -->
      <view class="mx-4 mt-4 pb-28">
        <view class="mb-3 flex items-center justify-between pl-1">
          <text class="text-[13px] text-[#475569] font-bold">知识点目录</text>
        </view>
        <view class="flex flex-col gap-2.5">
          <view
            v-for="item in kpItems"
            :key="item.id"
            class="overflow-hidden border border-white/60 rounded-2xl bg-white/90 shadow-sm backdrop-blur-sm"
          >
            <view
              class="flex items-center px-4 py-3.5"
              @click="item.children?.length ? toggleExpand(item.id) : startPracticeByKp(item.name, item.id)"
            >
              <view
                class="mr-3 h-9 w-9 flex shrink-0 items-center justify-center rounded-xl shadow-inner"
                :class="item.children?.length ? 'bg-[#ECFDF5]' : 'bg-[#EFF6FF]'"
              >
                <view :class="item.children?.length ? 'i-carbon-folder text-[18px] text-[#10B981]' : 'i-carbon-document text-[18px] text-[#3B82F6]'" />
              </view>
              <view class="min-w-0 flex-1">
                <view class="text-[15px] text-[#1E293B] font-bold">
                  {{ item.name }}
                </view>
                <view class="mt-0.5 flex items-center gap-2 text-[11px] text-[#94A3B8]">
                  <text>{{ item.question_count }} 题</text>
                  <template v-if="item.answer_count">
                    <view class="h-2 w-px bg-[#CBD5E1]" />
                    <text>已做 {{ item.answer_count }}</text>
                    <view class="h-2 w-px bg-[#CBD5E1]" />
                    <text :class="item.correct_ratio! >= 60 ? 'text-[#10B981]' : 'text-[#EF4444]'">
                      正确率 {{ item.correct_ratio }}%
                    </text>
                  </template>
                </view>
              </view>
              <view class="ml-2 flex items-center gap-2">
                  <view
                    class="rounded-full border border-[#DBEAFE] px-3 py-1 text-[11px] text-[#2563EB] font-semibold active:opacity-70"
                    :class="exportingItemId === item.id ? 'bg-[#EFF6FF] opacity-70' : 'bg-white'"
                    @click.stop="exportKpQuestions(item)"
                  >
                    {{ exportingItemId === item.id ? '导出中' : '导出题本' }}
                  </view>
                <view
                  v-if="item.children?.length"
                  class="i-carbon-chevron-down text-lg text-[#94A3B8] transition-transform duration-300"
                  :style="{ transform: expandedIds.has(item.id) ? 'rotate(180deg)' : 'rotate(0deg)' }"
                />
                <view v-else class="i-carbon-chevron-right text-lg text-[#CBD5E1]" />
              </view>
            </view>

            <!-- 子知识点 -->
            <template v-if="item.children?.length && expandedIds.has(item.id)">
              <view class="mx-4 h-px from-transparent via-[#E2E8F0] to-transparent bg-gradient-to-r" />
              <view
                v-for="sub in item.children"
                :key="sub.id"
                class="flex items-center px-4 py-3 pl-14 active:bg-gray-50"
                @click="startPracticeByKp(sub.name, sub.id)"
              >
                <view class="min-w-0 flex-1">
                  <view class="text-[14px] text-[#334155] font-medium">
                    {{ sub.name }}
                  </view>
                  <view class="mt-0.5 flex items-center gap-2 text-[11px] text-[#94A3B8]">
                    <text>{{ sub.question_count }} 题</text>
                    <template v-if="sub.answer_count">
                      <view class="h-2 w-px bg-[#E2E8F0]" />
                      <text :class="sub.correct_ratio! >= 60 ? 'text-[#10B981]' : 'text-[#EF4444]'">
                        对 {{ sub.correct_ratio }}%
                      </text>
                    </template>
                  </view>
                </view>
                <view class="ml-2 flex items-center gap-2">
                  <view
                    class="rounded-full border border-[#DBEAFE] px-3 py-1 text-[11px] text-[#2563EB] font-semibold active:opacity-70"
                    :class="exportingItemId === sub.id ? 'bg-[#EFF6FF] opacity-70' : 'bg-white'"
                    @click.stop="exportKpQuestions(sub)"
                  >
                    {{ exportingItemId === sub.id ? '导出中' : '导出题本' }}
                  </view>
                  <view
                    v-if="loadingItemId === sub.id"
                    class="text-[11px] text-[#94A3B8]"
                  >
                    加载中...
                  </view>
                  <view v-else class="i-carbon-chevron-right text-lg text-[#CBD5E1]" />
                </view>
              </view>
            </template>
          </view>
        </view>
      </view>

      <!-- 底部操作按钮 -->
      <view class="fixed bottom-0 left-0 right-0 z-30 border-t border-white/40 bg-white/95 px-5 pb-[env(safe-area-inset-bottom)] pt-3 backdrop-blur-md">
        <view class="flex items-center gap-3">
          <view
            class="h-12 flex flex-1 items-center justify-center rounded-2xl border border-[#DBEAFE] bg-white text-[15px] text-[#2563EB] font-bold active:scale-[0.98]"
            :class="exportingAll ? 'opacity-70' : ''"
            @click="exportAllKpQuestions"
          >
            <view v-if="exportingAll" class="i-carbon-circle-dash animate-spin text-lg mr-1.5" />
            <view v-else class="i-carbon-document-pdf text-lg mr-1.5" />
            {{ exportingAll ? '导出中...' : '导出全本' }}
          </view>
          <view
            class="h-12 flex-[2] flex items-center justify-center rounded-2xl text-[16px] text-white font-black from-[#3B82F6] to-[#2563EB] bg-gradient-to-r shadow-[0_4px_14px_rgba(59,130,246,0.35)] active:scale-[0.98]"
            @click="startPracticeAll"
          >
            <view class="i-carbon-play-filled-alt text-lg mr-1.5" />
            {{ loadingItemId === -1 ? '创建中...' : `开始练习 · ${totalQuestionCount} 题` }}
          </view>
        </view>
      </view>
    </template>

    <view v-else class="py-20 text-center text-[14px] text-[#94A3B8]">
      知识点分类不存在或暂无内容
    </view>

    <MembershipModal v-model="showMembershipModal" />
    <RenderBookExportPopup
      :model-value="showExportPopup"
      template-key="practice"
      :title="exportTarget?.scope.title || '导出题本'"
      :total-question-count="exportTarget?.totalQuestionCount || 0"
      @update:model-value="handleExportPopupChange"
      @confirm="submitExport"
    />
  </view>
</template>
