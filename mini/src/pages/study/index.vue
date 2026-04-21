<script lang="ts" setup>
import type { CoulddriveResourceListItem, CoulddriveResourceListParams, GetCategoryTree } from '@fba/api-sdk'
import { computed, nextTick, ref, watch } from 'vue'
import { onLoad, onPullDownRefresh, onReachBottom, onShow } from '@dcloudio/uni-app'
import { fbaApi } from '@/api/sdk'
import { getAppSettings } from '@/utils/appSettings'
import { getStudyDomainOption, type StudyDomainCode } from '@/utils/studyDomain'
import { getStudyDomainCategoryRoots } from '@/utils/studyDomainQuestionScope'

defineOptions({
  name: 'Study',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '资料大厅',
  },
})

const PAGE_SIZE = 20
const POPULAR_RESOURCE_TYPES = ['笔记', '真题', '电子书'] as const

interface StudyShortcutItem {
  id: number
  label: string
  icon: string
  iconClass: string
  bgClass: string
  ringClass: string
}

const STUDY_SHORTCUT_STYLE_LIST = [
  {
    icon: 'i-carbon-education',
    iconClass: 'text-[#F59E0B]',
    bgClass: 'from-[#FFF7ED] to-[#FFEDD5]',
    ringClass: 'shadow-[0_10px_24px_-16px_rgba(245,158,11,0.75)]',
  },
  {
    icon: 'i-carbon-document-add',
    iconClass: 'text-[#06B6D4]',
    bgClass: 'from-[#ECFEFF] to-[#CFFAFE]',
    ringClass: 'shadow-[0_10px_24px_-16px_rgba(6,182,212,0.75)]',
  },
  {
    icon: 'i-carbon-notebook-reference',
    iconClass: 'text-[#FB7185]',
    bgClass: 'from-[#FFF1F2] to-[#FFE4E6]',
    ringClass: 'shadow-[0_10px_24px_-16px_rgba(251,113,133,0.75)]',
  },
  {
    icon: 'i-carbon-result',
    iconClass: 'text-[#38BDF8]',
    bgClass: 'from-[#EFF6FF] to-[#DBEAFE]',
    ringClass: 'shadow-[0_10px_24px_-16px_rgba(56,189,248,0.75)]',
  },
] as const

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const currentDomain = ref<StudyDomainCode>(getAppSettings().currentDomain)
const lastLoadedDomain = ref<StudyDomainCode>(getAppSettings().currentDomain)
const popularLoading = ref(false)
const recentLoading = ref(false)
const loadingMore = ref(false)
const initialized = ref(false)
const keyword = ref('')
const selectedShortcut = ref<number | null>(null)
const activeResourceTabIndex = ref(0)
const recentResources = ref<CoulddriveResourceListItem[]>([])
const popularResources = ref<CoulddriveResourceListItem[]>([])
const studyCategoryTree = ref<GetCategoryTree[]>([])
const popularLoaded = ref(false)
const recentLoaded = ref(false)
const recentTotal = ref(0)
const page = ref(1)
const resourceSwiperHeight = ref(320)
const resourceTouchStartX = ref(0)
const resourceTouchStartY = ref(0)
const resourceTabs = [
  { key: 'popular', label: '热门榜单' },
  { key: 'recent', label: '最近更新' },
] as const

const hasMore = computed(() => recentResources.value.length < recentTotal.value)
const hasAnyResources = computed(() => recentResources.value.length > 0 || popularResources.value.length > 0)
const activeResourceTab = computed(() => resourceTabs[activeResourceTabIndex.value]?.key || 'recent')
const currentDomainLabel = computed(() => getStudyDomainOption(currentDomain.value).label)
const studyShortcutItems = computed<StudyShortcutItem[]>(() => {
  return studyCategoryTree.value.map((node, index) => {
    const style = STUDY_SHORTCUT_STYLE_LIST[index % STUDY_SHORTCUT_STYLE_LIST.length]
    return {
      id: Number(node.id),
      label: node.name,
      ...style,
    }
  })
})
const selectedShortcutLabel = computed(() => {
  return studyShortcutItems.value.find(item => item.id === selectedShortcutCategoryId.value)?.label || ''
})
const selectedShortcutCategoryId = computed(() => {
  if (typeof selectedShortcut.value === 'number' && selectedShortcut.value > 0) {
    return selectedShortcut.value
  }

  const firstItem = studyShortcutItems.value[0]
  return firstItem?.id
})
const selectedShortcutCategoryIds = computed(() => {
  const categoryId = selectedShortcutCategoryId.value
  if (!categoryId) {
    return []
  }

  return collectStudyCategoryIds(findStudyCategoryById(categoryId))
})

let studyCategoryLoadTask: Promise<void> | null = null

function normalizeKeyword(value: string) {
  return String(value || '').trim()
}

function syncCurrentDomain() {
  currentDomain.value = getAppSettings().currentDomain
  return currentDomain.value
}

function flattenStudyCategories(nodes: GetCategoryTree[] | null | undefined): GetCategoryTree[] {
  const result: GetCategoryTree[] = []

  for (const node of nodes || []) {
    result.push(node)
    if (node.children?.length) {
      result.push(...flattenStudyCategories(node.children))
    }
  }

  return result
}

function collectStudyCategoryIds(node: GetCategoryTree | null | undefined): number[] {
  if (!node) {
    return []
  }

  const ids: number[] = []

  const walk = (currentNode: GetCategoryTree | null | undefined) => {
    if (!currentNode || typeof currentNode.id !== 'number') {
      return
    }

    ids.push(currentNode.id)
    for (const child of currentNode.children || []) {
      walk(child)
    }
  }

  walk(node)
  return ids
}

function findStudyCategoryById(categoryId: number) {
  return flattenStudyCategories(studyCategoryTree.value).find(node => Number(node.id) === categoryId) || null
}

async function ensureStudyCategoryTreeLoaded() {
  if (studyCategoryTree.value.length) {
    return
  }

  if (!studyCategoryLoadTask) {
    studyCategoryLoadTask = (async () => {
      try {
        studyCategoryTree.value = await getStudyDomainCategoryRoots(
          currentDomain.value,
          ['resource_exam'],
        ) as GetCategoryTree[]

        const selectedId = selectedShortcut.value
        const exists = typeof selectedId === 'number'
          ? studyCategoryTree.value.some(item => Number(item.id) === selectedId)
          : false

        if (!exists) {
          selectedShortcut.value = studyCategoryTree.value[0]?.id || null
        }
      }
      catch (error) {
        console.error('加载学习分类失败:', error)
        studyCategoryTree.value = []
        selectedShortcut.value = null
      }
      finally {
        studyCategoryLoadTask = null
      }
    })()
  }

  await studyCategoryLoadTask
}

function buildQuery(targetPage = 1) {
  const params: CoulddriveResourceListParams = {
    page: targetPage,
    size: PAGE_SIZE,
    status: 1,
  }

  const categoryId = selectedShortcutCategoryId.value
  if (typeof categoryId === 'number') {
    params.category_id = categoryId
  }

  return params
}

async function loadRecentResources(targetPage = 1) {
  const isFirstPage = targetPage === 1
  if (isFirstPage) {
    recentLoading.value = true
  }
  else {
    loadingMore.value = true
  }

  try {
    const data = await fbaApi.coulddrive.resource.getList(buildQuery(targetPage))
    const items = Array.isArray(data.items) ? data.items : []

    recentResources.value = isFirstPage ? items : [...recentResources.value, ...items]
    recentTotal.value = Number(data.total || 0)
    page.value = targetPage
    if (isFirstPage) {
      recentLoaded.value = true
    }
  }
  catch (error) {
    console.error('加载学习资料失败:', error)
    if (isFirstPage) {
      recentResources.value = []
      recentTotal.value = 0
      recentLoaded.value = false
    }
    uni.showToast({ title: '加载资料失败', icon: 'none' })
  }
  finally {
    recentLoading.value = false
    loadingMore.value = false
  }
}

async function loadPopularResources() {
  popularLoading.value = true
  try {
    const allowedCategoryIds = new Set(selectedShortcutCategoryIds.value)
    if (!allowedCategoryIds.size) {
      popularResources.value = []
      popularLoaded.value = true
      return
    }

    const hotList = await fbaApi.coulddrive.resource.getHot(
      selectedShortcutCategoryId.value,
      10,
      [...POPULAR_RESOURCE_TYPES],
    )

    popularResources.value = hotList.filter((item) => {
      const categoryId = Number(item.category_id || 0)
      return allowedCategoryIds.has(categoryId)
    })
    popularLoaded.value = true
  }
  catch (error) {
    console.error('加载热门资料失败:', error)
    popularResources.value = []
    popularLoaded.value = false
  }
  finally {
    popularLoading.value = false
  }
}

function resetPopularResources() {
  popularResources.value = []
  popularLoaded.value = false
}

function resetRecentResources() {
  recentResources.value = []
  recentTotal.value = 0
  page.value = 1
  recentLoaded.value = false
  loadingMore.value = false
}

async function loadActiveTabResources(force = false) {
  await ensureStudyCategoryTreeLoaded()

  if (activeResourceTab.value === 'popular') {
    if (!force && (popularLoaded.value || popularLoading.value)) {
      initialized.value = true
      return
    }

    await loadPopularResources()
    initialized.value = true
    return
  }

  if (!force && (recentLoaded.value || recentLoading.value || loadingMore.value)) {
    initialized.value = true
    return
  }

  await loadRecentResources(1)
  initialized.value = true
}

function openSearchPage() {
  const query: string[] = []
  const normalizedKeyword = normalizeKeyword(keyword.value)

  if (normalizedKeyword) {
    query.push(`keyword=${encodeURIComponent(normalizedKeyword)}`)
  }

  if (typeof selectedShortcutCategoryId.value === 'number') {
    query.push(`categoryId=${selectedShortcutCategoryId.value}`)
  }

  if (selectedShortcutLabel.value) {
    query.push(`categoryName=${encodeURIComponent(selectedShortcutLabel.value)}`)
  }

  const queryString = query.length ? `?${query.join('&')}` : ''
  uni.navigateTo({
    url: `/pages/study/search/index${queryString}`,
  })
}

function triggerSearch() {
  keyword.value = normalizeKeyword(keyword.value)
  openSearchPage()
}

function handleKeywordConfirm(event: { detail?: { value?: string } }) {
  keyword.value = normalizeKeyword(event?.detail?.value || keyword.value)
  triggerSearch()
}

function clearKeyword() {
  if (!keyword.value) {
    return
  }

  keyword.value = ''
}

function selectShortcut(categoryId: number) {
  if (selectedShortcut.value === categoryId) {
    return
  }

  selectedShortcut.value = categoryId
  resetPopularResources()
  resetRecentResources()
  activeResourceTabIndex.value = 0
  void loadActiveTabResources(true)
}

function switchResourceTab(tab: 'popular' | 'recent') {
  const nextIndex = resourceTabs.findIndex(item => item.key === tab)
  if (nextIndex < 0 || nextIndex === activeResourceTabIndex.value) {
    return
  }

  activeResourceTabIndex.value = nextIndex
  void loadActiveTabResources()
}

function onResourceSwiperChange(event: any) {
  activeResourceTabIndex.value = Number(event?.detail?.current || 0)
  void loadActiveTabResources()
}

function handleResourceTouchStart(event: any) {
  const touch = event?.changedTouches?.[0] || event?.touches?.[0]
  if (!touch) {
    return
  }

  resourceTouchStartX.value = Number(touch.clientX || 0)
  resourceTouchStartY.value = Number(touch.clientY || 0)
}

function handleResourceTouchEnd(event: any) {
  const touch = event?.changedTouches?.[0]
  if (!touch) {
    return
  }

  const deltaX = Number(touch.clientX || 0) - resourceTouchStartX.value
  const deltaY = Number(touch.clientY || 0) - resourceTouchStartY.value

  if (Math.abs(deltaX) < 42 || Math.abs(deltaX) <= Math.abs(deltaY)) {
    return
  }

  if (deltaX < 0 && activeResourceTabIndex.value < resourceTabs.length - 1) {
    activeResourceTabIndex.value += 1
    return
  }

  if (deltaX > 0 && activeResourceTabIndex.value > 0) {
    activeResourceTabIndex.value -= 1
  }
}

function syncResourceSwiperHeight() {
  nextTick(() => {
    const panelClass = activeResourceTab.value === 'popular'
      ? '.study-resource-panel-popular'
      : '.study-resource-panel-recent'

    uni.createSelectorQuery()
      .select(panelClass)
      .boundingClientRect((rect: any) => {
        const nextHeight = Number(rect?.height || 0)
        if (nextHeight > 0) {
          resourceSwiperHeight.value = nextHeight
        }
      })
      .exec()
  })
}

function getResourceTitle(item: CoulddriveResourceListItem) {
  const value = (item as CoulddriveResourceListItem & { remark?: string | null }).remark
  const title = String(value || '').trim()
  if (title) {
    return title
  }

  return item.title || item.resource_intro || `资料 #${item.id}`
}

function getResourceSubtitle(item: CoulddriveResourceListItem) {
  return String(item.resource_intro || item.description || '').trim()
}

function getRankBadgeClass(index: number) {
  if (index === 0) {
    return 'from-[#FFF7ED] to-[#FED7AA] text-[#F97316] shadow-[0_10px_22px_-16px_rgba(249,115,22,0.9)]'
  }
  if (index === 1) {
    return 'from-[#F8FAFC] to-[#E2E8F0] text-[#94A3B8] shadow-[0_10px_22px_-18px_rgba(148,163,184,0.8)]'
  }
  if (index === 2) {
    return 'from-[#FFF1F2] to-[#FFE4E6] text-[#FB923C] shadow-[0_10px_22px_-18px_rgba(251,146,60,0.75)]'
  }
  return 'bg-[#F8FAFC] text-[#94A3B8]'
}

function getResourceListTag(tab: 'popular' | 'recent', item: CoulddriveResourceListItem, index: number) {
  if (item.hot || (tab === 'popular' && index < 3)) {
    return '热'
  }

  if (tab === 'recent' && index < 3) {
    return '新'
  }

  if (tab === 'popular' && index < 6) {
    return '新'
  }

  return ''
}

function getResourceListTagClass(tag: string) {
  if (tag === '热') {
    return 'bg-[#FFF1F2] text-[#F43F5E]'
  }
  if (tag === '新') {
    return 'bg-[#FFF7ED] text-[#F97316]'
  }
  return ''
}

function openResourceDetail(item: CoulddriveResourceListItem) {
  uni.navigateTo({
    url: `/pages/study/resource-detail/index?id=${item.id}`,
  })
}

onLoad(() => {
  syncCurrentDomain()
  void loadActiveTabResources(true)
})

onShow(() => {
  const nextDomain = syncCurrentDomain()
  if (nextDomain === lastLoadedDomain.value) {
    return
  }

  lastLoadedDomain.value = nextDomain
  selectedShortcut.value = null
  studyCategoryTree.value = []
  studyCategoryLoadTask = null
  resetPopularResources()
  resetRecentResources()
  void loadActiveTabResources(true)
})

onPullDownRefresh(async () => {
  if (activeResourceTab.value === 'popular') {
    resetPopularResources()
  }
  else {
    resetRecentResources()
  }

  await loadActiveTabResources(true)
  uni.stopPullDownRefresh()
})

onReachBottom(() => {
  if (
    activeResourceTab.value !== 'recent'
    || recentLoading.value
    || loadingMore.value
    || !initialized.value
    || !hasMore.value
  ) {
    return
  }

  loadRecentResources(page.value + 1)
})

watch(
  () => [
    activeResourceTabIndex.value,
    recentResources.value.length,
    popularResources.value.length,
    popularLoading.value,
    recentLoading.value,
    loadingMore.value,
  ],
  () => {
    syncResourceSwiperHeight()
  },
)
</script>

<template>
  <view class="relative min-h-[calc(100vh-50px-env(safe-area-inset-bottom))] overflow-hidden from-[#E1F0FF] via-[#F0F7FF] to-[#F8FAFC] bg-gradient-to-b text-[#334155]">
    <view class="pointer-events-none absolute h-72 w-72 rounded-full bg-[#BAE6FD]/40 blur-3xl -right-10 -top-10" />
    <view class="pointer-events-none absolute top-32 h-56 w-56 rounded-full bg-[#E0F2FE]/50 blur-3xl -left-12" />

    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="h-11 flex items-center justify-between px-4">
        <view class="w-20" />
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">{{ currentDomainLabel }}资料</text>
        <view class="w-20" />
      </view>
    </view>

    <view class="relative z-10 mt-4 px-4 pb-6">
      <view class="mb-5 rounded-[26px] border border-white bg-white/78 px-4 py-3 shadow-[0_2px_10px_-4px_rgba(0,0,0,0.05)] backdrop-blur-md">
        <view class="flex items-center gap-2">
          <view class="i-carbon-search mr-2 text-xl text-[#94A3B8]" />
          <input
            v-model="keyword"
            class="h-6 flex-1 text-[15px] text-[#1E293B]"
            confirm-type="search"
            :maxlength="50"
            placeholder="搜索资料名称、分类、简介"
            placeholder-style="color: #94A3B8;"
            @confirm="handleKeywordConfirm"
          >
          <view
            v-if="keyword"
            class="ml-2 h-6 w-6 flex items-center justify-center rounded-full bg-[#F1F5F9] text-[#94A3B8]"
            @tap="clearKeyword"
          >
            <view class="i-carbon-close text-sm" />
          </view>
          <view
            class="shrink-0 text-[13px] text-[#2563EB] font-bold"
            @tap="triggerSearch"
          >
            搜索
          </view>
        </view>
      </view>

      <view v-if="studyShortcutItems.length" class="mb-4 overflow-hidden rounded-[28px] border border-white/70 bg-white/78 px-3 py-3 shadow-[0_12px_30px_-20px_rgba(37,99,235,0.28)] backdrop-blur-md">
        <view class="grid grid-cols-4 gap-1.5">
          <view
            v-for="item in studyShortcutItems"
            :key="item.id"
            class="flex flex-col items-center justify-start rounded-2xl px-1 py-1.5 transition-all duration-200"
            :class="selectedShortcutCategoryId === item.id ? 'bg-[#F8FBFF]' : 'bg-transparent'"
            @tap="selectShortcut(item.id)"
          >
            <view
              class="mb-2.5 h-12 w-12 flex items-center justify-center rounded-2xl bg-gradient-to-br"
              :class="[item.bgClass, item.ringClass]"
            >
              <view :class="[item.icon, item.iconClass, 'text-[24px]']" />
            </view>
            <text
              class="text-center text-[12px] leading-[1.35]"
              :class="selectedShortcutCategoryId === item.id ? 'text-[#1E293B] font-bold' : 'text-[#334155]'"
            >
              {{ item.label }}
            </text>
          </view>
        </view>
      </view>

      <view class="mb-3">
        <view class="relative flex w-full items-center rounded-[18px] bg-white/78 p-1.5 shadow-[0_10px_28px_-18px_rgba(15,23,42,0.35)]">
          <view
            class="absolute bottom-1.5 top-1.5 rounded-[14px] bg-[#1E293B] shadow-sm transition-all duration-300"
            :style="{
              width: 'calc(50% - 6px)',
              left: activeResourceTab === 'popular' ? '6px' : 'calc(50% + 0px)',
            }"
          />
          <view
            v-for="tab in resourceTabs"
            :key="tab.key"
            class="relative z-10 flex-1 text-center rounded-[14px] px-4 py-2 text-[13px] transition-all duration-200"
            :class="activeResourceTab === tab.key
              ? 'text-white font-bold'
              : 'text-[#64748B]'"
            @tap="switchResourceTab(tab.key)"
          >
            {{ tab.label }}
          </view>
        </view>
      </view>

      <view
        v-if="((activeResourceTab === 'popular' && popularLoading) || (activeResourceTab === 'recent' && recentLoading)) && !hasAnyResources"
        class="py-18 text-center text-[13px] text-[#94A3B8]"
      >
        资料加载中...
      </view>

      <swiper
        v-else-if="hasAnyResources"
        class="study-resource-swiper"
        :style="{ height: `${resourceSwiperHeight}px` }"
        :current="activeResourceTabIndex"
        :duration="280"
        :disable-touch="false"
        @change="onResourceSwiperChange"
        @touchstart="handleResourceTouchStart"
        @touchend="handleResourceTouchEnd"
      >
        <swiper-item>
          <view class="study-resource-panel study-resource-panel-popular border border-white/80 rounded-2xl bg-white/80 p-3 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
            <view v-if="popularLoading && !popularLoaded" class="flex items-center justify-center py-14 text-[13px] text-[#94A3B8]">
              热门资料加载中...
            </view>
            <template v-else-if="popularResources.length">
              <view
                v-for="(item, index) in popularResources"
                :key="`popular-${item.id}`"
                class="flex items-center rounded-2xl px-2 py-2.5 transition-colors active:bg-[#F8FAFC]"
                :class="index < popularResources.length - 1 ? 'border-b border-blue-50/70' : ''"
                @tap="openResourceDetail(item)"
              >
                <view
                  class="mr-3 h-7 w-7 flex shrink-0 items-center justify-center rounded-full text-[15px] font-black"
                  :class="getRankBadgeClass(index)"
                >
                  {{ index + 1 }}
                </view>

                <view class="min-w-0 flex-1 pr-3">
                  <view class="line-clamp-1 text-[15px] text-[#1E293B] leading-[1.45]">
                    {{ getResourceTitle(item) }}
                  </view>
                  <view
                    v-if="getResourceSubtitle(item)"
                    class="mt-1 line-clamp-1 text-[12px] text-[#94A3B8] leading-[1.45]"
                  >
                    {{ getResourceSubtitle(item) }}
                  </view>
                </view>

                <view
                  v-if="getResourceListTag('popular', item, index)"
                  class="shrink-0 rounded-full px-1.5 py-0.5 text-[11px] font-bold"
                  :class="getResourceListTagClass(getResourceListTag('popular', item, index))"
                >
                  {{ getResourceListTag('popular', item, index) }}
                </view>
              </view>
            </template>
            <view v-else class="flex items-center justify-center py-14 text-[13px] text-[#94A3B8]">
              当前筛选下暂无热门资料
            </view>
          </view>
        </swiper-item>

        <swiper-item>
          <view class="study-resource-panel study-resource-panel-recent border border-white/80 rounded-2xl bg-white/80 p-3 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
            <view v-if="recentLoading && !recentLoaded" class="flex items-center justify-center py-14 text-[13px] text-[#94A3B8]">
              最近更新加载中...
            </view>
            <template v-else-if="recentResources.length">
              <view
                v-for="(item, index) in recentResources"
                :key="`recent-${item.id}`"
                class="flex items-center rounded-2xl px-2 py-2.5 transition-colors active:bg-[#F8FAFC]"
                :class="index < recentResources.length - 1 ? 'border-b border-blue-50/70' : ''"
                @tap="openResourceDetail(item)"
              >
                <view
                  class="mr-3 h-7 w-7 flex shrink-0 items-center justify-center rounded-full text-[15px] font-black"
                  :class="getRankBadgeClass(index)"
                >
                  {{ index + 1 }}
                </view>

                <view class="min-w-0 flex-1 pr-3">
                  <view class="line-clamp-1 text-[15px] text-[#1E293B] leading-[1.45]">
                    {{ getResourceTitle(item) }}
                  </view>
                  <view
                    v-if="getResourceSubtitle(item)"
                    class="mt-1 line-clamp-1 text-[12px] text-[#94A3B8] leading-[1.45]"
                  >
                    {{ getResourceSubtitle(item) }}
                  </view>
                </view>

                <view
                  v-if="getResourceListTag('recent', item, index)"
                  class="shrink-0 rounded-full px-1.5 py-0.5 text-[11px] font-bold"
                  :class="getResourceListTagClass(getResourceListTag('recent', item, index))"
                >
                  {{ getResourceListTag('recent', item, index) }}
                </view>
              </view>
            </template>
            <view v-else class="flex items-center justify-center py-14 text-[13px] text-[#94A3B8]">
              当前筛选下暂无更新资料
            </view>

            <view v-if="loadingMore" class="pt-4 text-center text-[12px] text-[#94A3B8]">
              正在加载更多资料...
            </view>
          </view>
        </swiper-item>
      </swiper>

      <view v-else class="flex flex-col items-center justify-center py-20">
        <view class="i-carbon-book mb-4 text-6xl text-[#CBD5E1]" />
        <text class="text-[14px] text-[#94A3B8]">当前筛选下暂时没有相关资料</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.study-resource-swiper {
  width: 100%;
}
</style>
