<script lang="ts" setup>
import { onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { fbaApi } from '@/api/sdk'
import LoginModal from '@/components/LoginModal.vue'
import { useTokenStore, useUserStore } from '@/store'
import { getAppSettings, saveAppSettings } from '@/utils/appSettings'
import { getCachedStudyPreference, setCachedStudyPreference } from '@/utils/studyPreferenceCache'
import CategoryConfigModal from './components/CategoryConfigModal.vue'

defineOptions({
  name: 'Practice',
})

definePage({
  type: 'home',
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

interface CategoryNode {
  id: number
  name: string
  app_code?: string
  type?: string
  code?: string | null
  description?: string | null
  color?: string | null
  sort_order?: number
  children?: CategoryNode[] | null
}

interface BankNode {
  id: number
  cat_id: number
  name: string
  bank_type: number
  q_count_cache?: number
  children?: BankNode[] | null
}

interface CategoryMeta {
  name: string
  path: number[]
  order: number
}

interface PracticeListItem {
  id: number
  name: string
  type: 'collection' | 'bank'
  desc: string
  count: number
  expanded: boolean
  children?: PracticeListItem[]
}

interface PracticeTab {
  id: number
  name: string
  items: PracticeListItem[]
  bankCount: number
  questionCount: number
}

interface SelectedPracticeTab {
  id: number
  name: string
  appCode: 'gongkao' | '考研'
}

interface StudyPreferenceCustomTab {
  id: string
  name: string
  category_id: number
  category_name: string
  bank_id?: number | null
  bank_name?: string | null
  is_fixed: boolean
  order: number
}

type PracticeMode = 'exam' | 'practice' | 'memorize'

interface LatestSessionBrief {
  id: number
  bank_id: number
  practice_name: string
  status: string
  total_count: number
  completed_count: number
  practice_mode: PracticeMode
}

type VisiblePracticeListItem = PracticeListItem & {
  node: PracticeListItem
  depth: number
}

interface DashboardState {
  todayPracticeCount: number
  overallAccuracy: string
}

const tokenStore = useTokenStore()
const userStore = useUserStore()
const showLoginModal = ref(false)
const showCategoryConfigModal = ref(false)
const loading = ref(false)
const refreshing = ref(false)
const dashboardLoading = ref(false)
const savingPreference = ref(false)
const activeIndex = ref(0)
const practiceMode = ref<PracticeMode>(getAppSettings().practiceMode as PracticeMode)
const recentSessionsLoading = ref(false)
const allTabs = ref<PracticeTab[]>([])
const tabs = ref<PracticeTab[]>([])
const bankTree = ref<BankNode[]>([])
const categoryTree = ref<CategoryNode[]>([])
const selectedPracticeTabs = ref<SelectedPracticeTab[]>([])
const recentSessions = ref<LatestSessionBrief[]>([])
const dashboard = ref<DashboardState>({
  todayPracticeCount: 0,
  overallAccuracy: '0%',
})

const { statusBarHeight } = uni.getSystemInfoSync()
const navBarHeight = (statusBarHeight || 20) + 44

const currentTab = computed(() => tabs.value[activeIndex.value] || null)
const latestRecentSession = computed(() => recentSessions.value[0] || null)

function rebuildDisplayedTabs() {
  if (!selectedPracticeTabs.value.length) {
    tabs.value = allTabs.value
  }
  else {
    tabs.value = selectedPracticeTabs.value
      .map(item => buildPracticeTabByCategoryId(item.id, item.name, categoryTree.value, bankTree.value))
      .filter((tab): tab is PracticeTab => Boolean(tab))
  }

  if (activeIndex.value >= tabs.value.length)
    activeIndex.value = 0
}

function toNumber(value: unknown) {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

function formatPercent(value: unknown) {
  const num = toNumber(value)
  if (Number.isInteger(num))
    return `${num}%`
  return `${num.toFixed(2).replace(/\.?0+$/, '')}%`
}

function flattenBankTree(nodes: BankNode[] | null | undefined): BankNode[] {
  const result: BankNode[] = []
  for (const node of nodes || []) {
    result.push(node)
    if (node.children?.length)
      result.push(...flattenBankTree(node.children))
  }
  return result
}

function buildCategoryMetaMap(nodes: CategoryNode[] | null | undefined) {
  const metaMap = new Map<number, CategoryMeta>()
  let order = 0

  const walk = (list: CategoryNode[] | null | undefined, path: number[] = []) => {
    for (const node of list || []) {
      const nextPath = [...path, node.id]
      metaMap.set(node.id, {
        name: node.name,
        path: nextPath,
        order: order++,
      })
      if (node.children?.length)
        walk(node.children, nextPath)
    }
  }

  walk(nodes)
  return metaMap
}

function resolveTabDepth(banks: BankNode[], categoryMetaMap: Map<number, CategoryMeta>) {
  const paths = flattenBankTree(banks)
    .map(bank => categoryMetaMap.get(bank.cat_id)?.path || [])
    .filter(path => path.length > 0)

  if (!paths.length)
    return 0

  const maxDepth = Math.max(...paths.map(path => path.length - 1))

  for (let depth = 0; depth <= maxDepth; depth += 1) {
    const ids = new Set<number>()
    for (const path of paths) {
      ids.add(path[Math.min(depth, path.length - 1)])
    }
    if (ids.size > 1)
      return depth
  }

  return Math.max(paths[0].length - 1, 0)
}

function resolveTabCategoryId(
  bank: BankNode,
  depth: number,
  categoryMetaMap: Map<number, CategoryMeta>,
): number | null {
  const meta = categoryMetaMap.get(bank.cat_id)
  if (meta)
    return meta.path[Math.min(depth, meta.path.length - 1)]

  for (const child of bank.children || []) {
    const childCategoryId = resolveTabCategoryId(child, depth, categoryMetaMap)
    if (childCategoryId)
      return childCategoryId
  }

  return null
}

function sumQuestionCount(nodes: BankNode[] | null | undefined): number {
  let total = 0
  for (const node of nodes || []) {
    if (node.children?.length)
      total += sumQuestionCount(node.children)
    else
      total += toNumber(node.q_count_cache)
  }
  return total
}

function countLeafBanks(nodes: BankNode[] | null | undefined): number {
  let total = 0
  for (const node of nodes || []) {
    if (node.children?.length)
      total += countLeafBanks(node.children)
    else
      total += 1
  }
  return total
}

function mapBankToListItem(bank: BankNode): PracticeListItem {
  const childItems = (bank.children || []).map(mapBankToListItem)

  if (bank.bank_type === 3 || childItems.length > 0) {
    const childCount = childItems.length
    return {
      id: bank.id,
      name: bank.name,
      type: 'collection',
      desc: `${childCount} ` + '\u4E2A\u9898\u5E93',
      count: childCount,
      expanded: false,
      children: childItems,
    }
  }

  const questionCount = toNumber(bank.q_count_cache)
  return {
    id: bank.id,
    name: bank.name,
    type: 'bank',
    desc: `${questionCount} ` + '\u9898',
    count: questionCount,
    expanded: false,
  }
}

function getVisibleItems(items: PracticeListItem[], depth = 0): VisiblePracticeListItem[] {
  const result: VisiblePracticeListItem[] = []

  for (const item of items) {
    result.push({
      node: item,
      ...item,
      depth,
    })

    if (item.type === 'collection' && item.expanded && item.children?.length) {
      result.push(...getVisibleItems(item.children, depth + 1))
    }
  }

  return result
}

function cloneFilteredBanksByCategoryId(
  nodes: BankNode[] | null | undefined,
  categoryId: number,
  categoryMetaMap: Map<number, CategoryMeta>,
): BankNode[] {
  const result: BankNode[] = []

  for (const node of nodes || []) {
    const children = cloneFilteredBanksByCategoryId(node.children, categoryId, categoryMetaMap)
    const path = categoryMetaMap.get(node.cat_id)?.path || []
    const selfMatched = path.includes(categoryId)

    if (selfMatched || children.length) {
      result.push({
        ...node,
        children,
      })
    }
  }

  return result
}

function buildPracticeTabs(categories: CategoryNode[], banks: BankNode[]) {
  const categoryMetaMap = buildCategoryMetaMap(categories)
  const tabDepth = resolveTabDepth(banks, categoryMetaMap)
  const groupedBanks = new Map<number, BankNode[]>()

  for (const bank of banks) {
    const tabCategoryId = resolveTabCategoryId(bank, tabDepth, categoryMetaMap)
    if (!tabCategoryId)
      continue

    const current = groupedBanks.get(tabCategoryId) || []
    current.push(bank)
    groupedBanks.set(tabCategoryId, current)
  }

  const practiceTabs = Array.from(groupedBanks.entries())
    .map(([categoryId, bankList]) => {
      const meta = categoryMetaMap.get(categoryId)
      if (!meta)
        return null

      return {
        id: categoryId,
        name: meta.name,
        items: bankList.map(mapBankToListItem),
        bankCount: countLeafBanks(bankList),
        questionCount: sumQuestionCount(bankList),
        order: meta.order,
      }
    })
    .filter((tab): tab is PracticeTab & { order: number } => Boolean(tab))
    .sort((a, b) => a.order - b.order)
    .map(({ order, ...tab }) => tab)

  if (practiceTabs.length)
    return practiceTabs

  if (!banks.length)
    return []

  return [{
    id: 0,
    name: '全部',
    items: banks.map(mapBankToListItem),
    bankCount: countLeafBanks(banks),
    questionCount: sumQuestionCount(banks),
  }]
}

function buildPracticeTabByCategoryId(
  categoryId: number,
  categoryName: string,
  categories: CategoryNode[],
  banks: BankNode[],
) {
  const categoryMetaMap = buildCategoryMetaMap(categories)
  const filteredBanks = cloneFilteredBanksByCategoryId(banks, categoryId, categoryMetaMap)

  return {
    id: categoryId,
    name: categoryName,
    items: filteredBanks.map(mapBankToListItem),
    bankCount: countLeafBanks(filteredBanks),
    questionCount: sumQuestionCount(filteredBanks),
  }
}

function resolveCategoryAppCodeById(nodes: CategoryNode[] | null | undefined, targetId: number): 'gongkao' | '考研' | null {
  for (const node of nodes || []) {
    if (node.id === targetId) {
      if (node.app_code === 'gongkao' || node.app_code === '考研')
        return node.app_code
      return null
    }

    const childResult = resolveCategoryAppCodeById(node.children, targetId)
    if (childResult)
      return childResult
  }

  return null
}

function mapPreferenceToSelectedTabs(customTabs: StudyPreferenceCustomTab[] | null | undefined) {
  return (customTabs || [])
    .slice()
    .sort((a, b) => toNumber(a.order) - toNumber(b.order))
    .map((item) => {
      const categoryId = toNumber(item.category_id)
      const appCode = resolveCategoryAppCodeById(categoryTree.value, categoryId)
      if (!categoryId || !appCode)
        return null

      return {
        id: categoryId,
        name: item.category_name || item.name,
        appCode,
      }
    })
    .filter((item): item is SelectedPracticeTab => Boolean(item))
}

function buildPreferencePayload() {
  return selectedPracticeTabs.value.map((item, index) => ({
    id: String(item.id),
    name: item.name,
    category_id: item.id,
    category_name: item.name,
    bank_id: null,
    bank_name: null,
    is_fixed: false,
    order: index,
  }))
}

function ensureLogin() {
  if (!tokenStore.updateNowTime().hasLogin) {
    showLoginModal.value = true
    return false
  }
  return true
}

function selectSubject(index: number) {
  activeIndex.value = index
}

function onSwiperChange(e: any) {
  activeIndex.value = e.detail.current || 0
}

function toggleCollection(item: PracticeListItem) {
  item.expanded = !item.expanded
}

function openSubjectSettings() {
  if (!ensureLogin())
    return

  showCategoryConfigModal.value = true
}

function handleSelectedTabsUpdate(value: SelectedPracticeTab[]) {
  selectedPracticeTabs.value = value
  rebuildDisplayedTabs()
  saveStudyPreference()
}

function startQuickPractice() {
  if (!currentTab.value) {
    uni.showToast({ title: '当前分类下暂无可练习内容', icon: 'none' })
    return
  }

  if (!ensureLogin())
    return

  uni.showToast({ title: '刷题会话页下一步接入，当前先完成首页真实数据', icon: 'none' })
}

function openBank(item: Pick<PracticeListItem, 'name'>) {
  if (!ensureLogin())
    return

  uni.showToast({ title: `${item.name} 已接入真实数据，做题页下一步继续`, icon: 'none' })
}

function normalizeLatestSession(session: any): LatestSessionBrief | null {
  if (!session)
    return null

  const savedPracticeMode = String(session?.exam_config?.practice_mode || '')
  const sessionType = String(session?.session_type || '')
  const sessionPracticeMode: PracticeMode = savedPracticeMode === 'exam' || savedPracticeMode === 'memorize'
    ? savedPracticeMode
    : sessionType === 'exam'
      ? 'exam'
    : 'practice'

  return {
    id: toNumber(session.id),
    bank_id: toNumber(session.bank_id),
    practice_name: String(session.practice_name || ''),
    status: String(session.status || ''),
    total_count: toNumber(session.total_count ?? session.session_questions?.length),
    completed_count: toNumber(session.completed_count ?? session.records?.length),
    practice_mode: sessionPracticeMode,
  }
}

async function fetchRecentSessionsSafe() {
  recentSessionsLoading.value = true

  try {
    const pageData = await fbaApi.qbank.session.getList({
      status: 'in_progress' as any,
      page: 1,
      size: 20,
    } as any)
    recentSessions.value = (pageData?.items || [])
      .map(normalizeLatestSession)
      .filter((item): item is LatestSessionBrief => Boolean(item))
  }
  catch (error) {
    const name = String((error as any)?.name || '')
    const message = String((error as any)?.message || '')
    const isNetworkError = name === 'NetworkError' || message.includes('Network request failed')

    if (!isNetworkError)
      console.error('加载最近未完成会话失败:', error)

    recentSessions.value = []
  }
  finally {
    recentSessionsLoading.value = false
  }

  return recentSessions.value
}

function getLatestSessionByBankId(bankId: number) {
  const currentMode = currentPracticeMode()
  return recentSessions.value.find(
    item => item.bank_id === bankId && item.practice_mode === currentMode,
  ) || null
}

function hasLatestSession(bankId: number) {
  return getLatestSessionByBankId(bankId)?.status === 'in_progress'
}

function currentPracticeMode() {
  return getAppSettings().practiceMode as PracticeMode
}

function navigateToPracticeSession(sessionId: number, modeOverride?: PracticeMode) {
  if (!sessionId)
    return

  uni.navigateTo({
    url: `/pages/practice/session/index?sessionId=${sessionId}&mode=${modeOverride || currentPracticeMode()}`,
  })
}

async function createPracticeSessionByBank(item: PracticeListItem) {
  if (item.type !== 'bank')
    return

  const nextPracticeMode = currentPracticeMode()
  practiceMode.value = nextPracticeMode

  try {
    const session = await fbaApi.qbank.session.create({
      session_type: nextPracticeMode === 'exam' ? 'exam' : 'bank',
      practice_name: item.name,
      bank_id: item.id,
      exam_config: {
        practice_mode: nextPracticeMode,
        entry: 'mini-home',
      },
      cat_id: currentTab.value?.id,
    } as any)

    navigateToPracticeSession(Number((session as any)?.id || 0), nextPracticeMode)
  }
  catch (error) {
    console.error('创建刷题会话失败:', error)
    uni.showToast({ title: '创建刷题会话失败', icon: 'none' })
  }
}

async function continueLatestSessionByBank(item: PracticeListItem) {
  if (item.type !== 'bank')
    return

  const latestSession = getLatestSessionByBankId(item.id)
  if (!latestSession)
    return

  practiceMode.value = latestSession.practice_mode
  navigateToPracticeSession(latestSession.id, latestSession.practice_mode)
}

function handleStartQuickPractice() {
  if (!ensureLogin())
    return

  if (!latestRecentSession.value) {
    uni.showToast({ title: '暂无未完成练习', icon: 'none' })
    return
  }

  navigateToPracticeSession(latestRecentSession.value.id, latestRecentSession.value.practice_mode)
}

function handleOpenBank(item: PracticeListItem) {
  if (item.type !== 'bank')
    return

  if (!ensureLogin())
    return

  uni.navigateTo({
    url: `/pages/bank-detail/index?id=${item.id}`,
  })
}

function handleContinueLatestSession(item: PracticeListItem, event?: any) {
  event?.stopPropagation?.()

  if (!ensureLogin())
    return

  void continueLatestSessionByBank(item)
}

function openUserReport() {
  if (!ensureLogin())
    return

  uni.navigateTo({ url: '/pages/user-report/index' })
}

async function refreshVisibleLatestSessions() {
  if (!tokenStore.updateNowTime().hasLogin) {
    recentSessions.value = []
    return
  }

  if (recentSessionsLoading.value)
    return

  await fetchRecentSessionsSafe()
}

async function loadDashboard() {
  if (!tokenStore.updateNowTime().hasLogin) {
    dashboard.value = {
      todayPracticeCount: 0,
      overallAccuracy: '0%',
    }
    return
  }

  dashboardLoading.value = true
  try {
    const data = await fbaApi.qbank.home.getDashboard() as any
    dashboard.value = {
      todayPracticeCount: toNumber(data?.check_in?.today_practice_count),
      overallAccuracy: formatPercent(data?.overall_accuracy),
    }
  }
  catch (error) {
    console.error('加载首页统计失败:', error)
    dashboard.value = {
      todayPracticeCount: 0,
      overallAccuracy: '0%',
    }
  }
  finally {
    dashboardLoading.value = false
  }
}

function applyStudyPreference(data: any) {
  const nextPracticeMode: PracticeMode = data?.practice_mode === 'exam' || data?.practice_mode === 'memorize'
    ? data.practice_mode
    : 'practice'

  practiceMode.value = nextPracticeMode
  saveAppSettings({ practiceMode: nextPracticeMode })
  selectedPracticeTabs.value = mapPreferenceToSelectedTabs(data?.custom_tabs)
  rebuildDisplayedTabs()
}

async function loadStudyPreference() {
  if (!tokenStore.updateNowTime().hasLogin) {
    selectedPracticeTabs.value = []
    practiceMode.value = getAppSettings().practiceMode as PracticeMode
    recentSessions.value = []
    return
  }

  try {
    const userId = Number(userStore.userInfo?.userId || 0)
    const cached = getCachedStudyPreference(userId)
    if (cached) {
      applyStudyPreference(cached)
      return
    }

    const data = await fbaApi.qbank.settings.getStudyPreference() as any
    setCachedStudyPreference(userId, data)
    applyStudyPreference(data)
  }
  catch (error) {
    console.error('加载学习偏好失败:', error)
    selectedPracticeTabs.value = []
    practiceMode.value = getAppSettings().practiceMode as PracticeMode
    rebuildDisplayedTabs()
  }
}

async function saveStudyPreference() {
  if (!tokenStore.updateNowTime().hasLogin || savingPreference.value)
    return

  savingPreference.value = true
  try {
    const payload = {
      practice_mode: practiceMode.value,
      custom_tabs: buildPreferencePayload(),
    } as any
    await fbaApi.qbank.settings.updateStudyPreference(payload)
    setCachedStudyPreference(Number(userStore.userInfo?.userId || 0), payload)
  }
  catch (error) {
    console.error('保存学习偏好失败:', error)
    uni.showToast({ title: '保存首页Tab失败', icon: 'none' })
  }
  finally {
    savingPreference.value = false
  }
}

async function loadPracticeTabs() {
  loading.value = true
  try {
    const [bankTreeData, categoryTreeData] = await Promise.all([
      fbaApi.qbank.bank.getList({ status: 1 }) as Promise<BankNode[]>,
      fbaApi.admin.sys.category.getTree({ status: true }) as Promise<CategoryNode[]>,
    ])

    bankTree.value = bankTreeData || []
    categoryTree.value = categoryTreeData || []
    allTabs.value = buildPracticeTabs(categoryTree.value, bankTree.value)
    rebuildDisplayedTabs()
  }
  catch (error) {
    console.error('加载刷题首页失败:', error)
    bankTree.value = []
    categoryTree.value = []
    allTabs.value = []
    tabs.value = []
    uni.showToast({ title: '加载刷题首页失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

function handleLoginSuccess() {
  refreshPracticePage()
}

async function refreshPracticePage() {
  await loadPracticeTabs()
  loadDashboard()
  await loadStudyPreference()
  await refreshVisibleLatestSessions()
}

async function onScrollRefresh() {
  refreshing.value = true
  try {
    await refreshPracticePage()
  }
  finally {
    refreshing.value = false
  }
}

const initialized = ref(false)

onShow(() => {
  if (!initialized.value) {
    // 首次进入：完整加载
    initialized.value = true
    refreshPracticePage()
  }
  else {
    // 从子页面返回：只刷新统计和进度，不重建 tabs
    loadDashboard()
    refreshVisibleLatestSessions()
  }
})
</script>

<template>
  <view class="relative h-screen flex flex-col overflow-hidden from-[#DAF0E4] via-[#F0F8F4] to-[#F8FCF9] bg-gradient-to-b text-[#334155]">
    <view class="relative z-20 w-full shrink-0" :style="{ paddingTop: `${navBarHeight}px` }">
      <!-- 标题栏 -->
      <view class="absolute left-0 right-0 flex items-center justify-center" :style="{ top: `${statusBarHeight}px`, height: '44px' }">
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">有岸上刷题</text>
      </view>
      <view class="relative w-full flex items-center border-b border-white/40 pb-2 pt-1">
        <scroll-view
          scroll-x
          class="flex-1 whitespace-nowrap px-4"
          style="width: calc(100% - 48px);"
          :show-scrollbar="false"
          :scroll-into-view="`tab-${activeIndex}`"
          scroll-with-animation
        >
          <template v-if="tabs.length">
            <view
              v-for="(tab, index) in tabs"
              :id="`tab-${index}`"
              :key="tab.id"
              class="relative mr-6 inline-block text-[17px] transition-all"
              :class="activeIndex === index ? 'font-black text-[#059669]' : 'font-medium text-[#64748B]'"
              @click="selectSubject(index)"
            >
              {{ tab.name }}
              <view
                v-if="activeIndex === index"
                class="absolute left-1/2 h-1 w-4 rounded-full bg-[#10B981] shadow-[0_2px_8px_rgba(16,185,129,0.5)] -bottom-2.5 -translate-x-1/2"
              />
            </view>
          </template>

          <view v-else class="inline-block text-[15px] text-[#94A3B8] font-medium">
            {{ loading ? '分类加载中...' : '暂无分类' }}
          </view>

          <view class="inline-block w-8" />
        </scroll-view>

        <view class="absolute bottom-0 right-0 top-0 w-20 flex items-center justify-end from-[#E4F4EC] via-[#E4F4EC]/90 to-transparent bg-gradient-to-l pr-3">
          <view class="h-8 w-8 flex items-center justify-center rounded-full bg-white/80 text-[#475569] shadow-sm backdrop-blur-sm transition-transform active:scale-95" @click="openSubjectSettings">
            <view class="i-carbon-menu text-lg" />
          </view>
        </view>
      </view>
    </view>

    <swiper
      class="relative z-10 w-full flex-1"
      :current="activeIndex"
      :duration="300"
      @change="onSwiperChange"
    >
      <template v-if="tabs.length">
        <swiper-item v-for="tab in tabs" :key="tab.id">
          <scroll-view scroll-y class="border-box h-full w-full pb-14" :show-scrollbar="false" refresher-enabled :refresher-triggered="refreshing" @refresherrefresh="onScrollRefresh">
            <view class="mb-5 mt-5 flex gap-3 px-5">
              <view
                hover-class="scale-95 opacity-90"
                :hover-stay-time="150"
                class="relative flex flex-1 flex-col justify-between overflow-hidden rounded-2xl from-[#10B981] to-[#047857] bg-gradient-to-br px-4 py-4 text-white"
                @click="handleStartQuickPractice"
              >
                <view class="i-carbon-rocket pointer-events-none absolute rotate-12 text-7xl text-white/10 -bottom-4 -right-4" />
                <view class="text-[11px] text-white/75">
                  {{ tab.name }}
                </view>
                <view class="mt-2 flex items-center text-[20px] font-black leading-none">
                  继续上次
                  <view class="i-carbon-arrow-right ml-1.5 text-base" />
                </view>
                <view class="mt-1.5 text-[10px] text-white/65">
                  {{ latestRecentSession?.practice_name || '暂无未完成练习' }}
                </view>
              </view>

              <view class="flex flex-1 flex-col justify-between rounded-2xl bg-white/90 px-4 py-4 shadow-sm backdrop-blur-sm transition-transform active:scale-[0.98]" @click="openUserReport">
                <view class="text-[11px] text-[#94A3B8]">
                  今日数据
                </view>
                <view class="mt-2 flex items-baseline gap-1">
                  <text class="text-[28px] text-[#059669] font-black leading-none">
                    {{ dashboardLoading ? '--' : dashboard.todayPracticeCount }}
                  </text>
                  <text class="text-[11px] text-[#94A3B8]">题</text>
                </view>
                <view class="mt-1.5 flex items-center gap-1">
                  <view class="h-1.5 w-1.5 shrink-0 rounded-full bg-[#10B981]" />
                  <text class="text-[11px] text-[#64748B]">累计正确率 {{ dashboard.overallAccuracy }}</text>
                </view>
              </view>
            </view>

            <view class="flex flex-col gap-3 px-5">
              <template v-if="tab.items.length">
                <transition-group name="practice-tree" tag="view" class="flex flex-col gap-3">
                  <view
                    v-for="item in getVisibleItems(tab.items)"
                    :key="`${item.id}-${item.depth}-${item.type}`"
                    class="relative"
                    :style="{
                      marginLeft: `${item.depth * 14}px`,
                      transitionDelay: item.depth > 0 ? `${Math.min(item.depth * 24, 72)}ms` : '0ms',
                    }"
                  >
                    <view
                      v-if="item.depth > 0"
                      class="absolute bottom-4 left-[-9px] top-4 w-[2px] rounded-full from-[#BBF7D0] via-[#D1FAE5] to-[#E2E8F0] bg-gradient-to-b"
                    />

                    <view
                      v-if="item.type === 'collection'"
                      class="overflow-hidden border border-white/70 rounded-2xl backdrop-blur-sm transition-all duration-300"
                      :class="item.expanded ? 'bg-[#F7FFFA] shadow-[0_14px_32px_rgba(16,185,129,0.12)] ring-1 ring-[#D1FAE5]' : 'bg-white/90 shadow-sm active:scale-[0.99]'"
                      @click="toggleCollection(item.node)"
                    >
                      <view class="flex items-center px-4 py-3.5">
                        <view class="mr-3 h-9 w-9 flex shrink-0 items-center justify-center rounded-xl bg-[#ECFDF5] shadow-inner">
                          <view class="i-carbon-folder text-[18px] text-[#10B981]" />
                        </view>
                        <view class="min-w-0 flex-1">
                          <view class="text-[15px] text-[#1E293B] font-bold">
                            {{ item.name }}
                          </view>
                          <view class="mt-0.5 text-[11px] text-[#94A3B8]">
                            {{ item.desc }}
                          </view>
                        </view>
                        <view
                          class="i-carbon-chevron-down text-lg text-[#94A3B8] transition-transform duration-300"
                          :style="{ transform: item.expanded ? 'rotate(180deg)' : 'rotate(0deg)' }"
                        />
                      </view>
                      <view
                        v-if="item.expanded && item.children?.length"
                        class="mx-4 h-px from-transparent via-[#D1FAE5] to-transparent bg-gradient-to-r"
                      />
                    </view>

                    <view
                      v-else
                      class="flex items-center border border-white/70 rounded-2xl bg-white/90 px-4 py-3.5 shadow-sm backdrop-blur-sm transition-all duration-200 active:scale-[0.99] active:bg-gray-50"
                      :class="item.depth > 0 ? 'shadow-[0_10px_24px_rgba(148,163,184,0.08)]' : ''"
                      @click="handleOpenBank(item.node)"
                    >
                      <view class="mr-3 h-9 w-9 flex shrink-0 items-center justify-center rounded-xl bg-[#EFF6FF] shadow-inner">
                        <view class="i-carbon-document text-[18px] text-[#3B82F6]" />
                      </view>
                      <view class="min-w-0 flex-1">
                        <view class="text-[15px] text-[#1E293B] font-bold">
                          {{ item.name }}
                        </view>
                        <view v-if="!hasLatestSession(item.id)" class="mt-0.5 text-[11px] text-[#94A3B8]">
                          {{ item.desc }}
                        </view>
                        <view
                          v-if="hasLatestSession(item.id)"
                          class="mt-2"
                          @click.stop="handleContinueLatestSession(item.node, $event)"
                        >
                          <view class="flex items-center justify-between">
                            <view class="flex items-center gap-1.5 text-[11px] text-[#059669] font-bold">
                              <view class="i-carbon-in-progress text-[12px]" />
                              <text>{{ getLatestSessionByBankId(item.id)!.completed_count }}/{{ getLatestSessionByBankId(item.id)!.total_count }}</text>
                            </view>
                            <view class="rounded-full bg-[#ECFDF5] px-2.5 py-0.5 text-[10px] text-[#059669] font-bold">
                              继续上次
                            </view>
                          </view>
                          <view class="mt-1.5 h-[4px] overflow-hidden rounded-full bg-[#E2E8F0]">
                            <view
                              class="h-full rounded-full from-[#34D399] to-[#10B981] bg-gradient-to-r transition-all duration-500"
                              :style="{ width: `${Math.min(100, Math.round((getLatestSessionByBankId(item.id)!.completed_count / Math.max(1, getLatestSessionByBankId(item.id)!.total_count)) * 100))}%` }"
                            />
                          </view>
                        </view>
                      </view>
                      <view class="i-carbon-chevron-right text-lg text-[#CBD5E1]" />
                    </view>
                  </view>
                </transition-group>
              </template>

              <view v-else class="rounded-2xl bg-white/80 px-5 py-10 text-center shadow-sm">
                <text class="text-[14px] text-[#94A3B8]">这个分类下暂时还没有题库。</text>
              </view>
            </view>
          </scroll-view>
        </swiper-item>
      </template>

      <swiper-item v-else>
        <view class="h-full px-5 pt-10">
          <view class="rounded-3xl bg-white/85 px-6 py-12 text-center shadow-sm">
            <view class="mb-2 text-[16px] text-[#1E293B] font-bold">
              {{ loading ? '刷题内容加载中...' : '暂时没有可展示的题库' }}
            </view>
            <view class="text-[13px] text-[#94A3B8]">
              {{ loading ? '正在从真实后端读取分类和题库数据' : '请先在后台配置分类并关联题库' }}
            </view>
          </view>
        </view>
      </swiper-item>
    </swiper>

    <LoginModal v-model="showLoginModal" @success="handleLoginSuccess" />
    <CategoryConfigModal
      v-model="showCategoryConfigModal"
      :categories="categoryTree"
      :selected-tabs="selectedPracticeTabs"
      :loading="loading"
      @update:selected-tabs="handleSelectedTabsUpdate"
    />
  </view>
</template>

<style lang="scss" scoped>
.practice-tree-enter-active,
.practice-tree-leave-active {
  transition:
    opacity 0.28s ease,
    transform 0.28s ease;
}

.practice-tree-enter-from,
.practice-tree-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.985);
}

.practice-tree-move {
  transition: transform 0.3s ease;
}
</style>
