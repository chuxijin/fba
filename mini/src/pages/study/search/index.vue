<script lang="ts" setup>
import type {
  CoulddriveResourceListItem,
  CoulddriveResourceListParams,
  CoulddriveResourceVectorSearchResultItem,
} from '@fba/api-sdk'
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'

defineOptions({
  name: 'StudySearch',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '资料搜索',
  },
})

type SearchMode = 'keyword' | 'vector'

interface SearchResultItem {
  resource: CoulddriveResourceListItem
  similarity?: number | null
}

const PAGE_SIZE = 20
const RESOURCE_TYPE_OPTIONS = [
  { label: '全部类型', value: '' },
  { label: '笔记', value: '笔记' },
  { label: '真题', value: '真题' },
  { label: '电子书', value: '电子书' },
]

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const loading = ref(false)
const loadingMore = ref(false)
const initialized = ref(false)
const keyword = ref('')
const categoryId = ref<number | undefined>(undefined)
const categoryName = ref('')
const resourceType = ref('')
const searchMode = ref<SearchMode>('keyword')
const results = ref<SearchResultItem[]>([])
const total = ref(0)
const page = ref(1)

const hasKeyword = computed(() => Boolean(normalizeKeyword(keyword.value)))
const hasMore = computed(() =>
  searchMode.value === 'keyword' && results.value.length < total.value,
)
const canTryVectorSearch = computed(() =>
  Boolean(tokenStore.hasLogin) && hasKeyword.value && searchMode.value === 'keyword' && initialized.value && !loading.value && !results.value.length,
)
const currentCategoryFilterLabel = computed(() =>
  categoryName.value || '全部分类',
)
const currentYearFilterLabel = computed(() => '年份')
const currentResourceTypeFilterLabel = computed(() =>
  resourceType.value || '资料类型',
)
const emptyMessage = computed(() => {
  if (!hasKeyword.value) {
    return '输入关键词开始搜索'
  }

  if (searchMode.value === 'vector') {
    return '强力搜索下也没有找到相关资料'
  }

  return '没有找到相关资料'
})

function normalizeKeyword(value: string) {
  return String(value || '').trim()
}

function decodeQueryValue(value: unknown) {
  const rawValue = String(value || '').trim()
  if (!rawValue) {
    return ''
  }

  try {
    return decodeURIComponent(rawValue)
  }
  catch {
    return rawValue
  }
}

function parseOptionalNumber(value: unknown) {
  const num = Number(value)
  return Number.isFinite(num) && num > 0 ? num : undefined
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }

  uni.switchTab({ url: '/pages/study/index' })
}

function getResourceName(item: CoulddriveResourceListItem) {
  return item.main_name || item.title || `资料 #${item.id}`
}

function getResourceRemark(item: CoulddriveResourceListItem) {
  return String(item.remark || item.description || item.category_name || '').trim()
}

function getSimilarityText(similarity?: number | null) {
  const score = Number(similarity)
  if (!Number.isFinite(score) || score <= 0) {
    return ''
  }

  return `匹配度 ${Math.round(score * 100)}%`
}

function openResourceDetail(item: SearchResultItem) {
  uni.navigateTo({
    url: `/pages/study/resource-detail/index?id=${item.resource.id}`,
  })
}

async function loadKeywordResults(targetPage: number, normalizedKeyword: string) {
  searchMode.value = 'keyword'

  const params: CoulddriveResourceListParams = {
    page: targetPage,
    size: PAGE_SIZE,
    status: 1,
    keyword: normalizedKeyword,
  }

  if (typeof categoryId.value === 'number') {
    params.category_id = categoryId.value
  }

  if (resourceType.value) {
    params.resource_type = resourceType.value
  }

  const data = await fbaApi.coulddrive.resource.getList(params)
  const items = Array.isArray(data.items) ? data.items : []
  const mappedItems = items.map(item => ({
    resource: item,
    similarity: null,
  }))

  results.value = targetPage === 1
    ? mappedItems
    : [...results.value, ...mappedItems]
  total.value = Number(data.total || 0)
  page.value = targetPage
}

async function loadVectorResults(normalizedKeyword: string) {
  searchMode.value = 'vector'

  const params: {
    query: string
    category_id?: number
    limit: number
  } = {
    query: normalizedKeyword,
    limit: PAGE_SIZE,
  }

  if (typeof categoryId.value === 'number') {
    params.category_id = categoryId.value
  }

  const data = await fbaApi.coulddrive.resource.vectorSearch(params)
  const items = Array.isArray(data) ? data : []
  const filteredItems = resourceType.value
    ? items.filter(item => item.resource.resource_type === resourceType.value)
    : items

  results.value = filteredItems.map((item: CoulddriveResourceVectorSearchResultItem) => ({
    resource: item.resource,
    similarity: item.similarity,
  }))
  total.value = results.value.length
  page.value = 1
}

async function searchResources(targetPage = 1) {
  const normalizedKeyword = normalizeKeyword(keyword.value)
  keyword.value = normalizedKeyword
  searchMode.value = 'keyword'

  if (!normalizedKeyword) {
    results.value = []
    total.value = 0
    page.value = 1
    initialized.value = true
    return
  }

  if (targetPage === 1) {
    loading.value = true
  }
  else {
    loadingMore.value = true
  }

  try {
    await loadKeywordResults(targetPage, normalizedKeyword)
    initialized.value = true
  }
  catch (error) {
    console.error('搜索资料失败:', error)
    if (targetPage === 1) {
      results.value = []
      total.value = 0
      page.value = 1
    }
    uni.showToast({ title: '搜索失败，请稍后重试', icon: 'none' })
  }
  finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function triggerVectorSearch() {
  const normalizedKeyword = normalizeKeyword(keyword.value)
  keyword.value = normalizedKeyword

  if (!normalizedKeyword) {
    uni.showToast({ title: '请输入搜索关键词', icon: 'none' })
    return
  }

  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '登录后可使用强力搜索', icon: 'none' })
    return
  }

  loading.value = true
  loadingMore.value = false

  try {
    await loadVectorResults(normalizedKeyword)
    initialized.value = true
  }
  catch (error) {
    console.error('强力搜索失败:', error)
    searchMode.value = 'keyword'
    uni.showToast({ title: '强力搜索暂不可用', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

function submitSearch() {
  if (!normalizeKeyword(keyword.value)) {
    uni.showToast({ title: '请输入搜索关键词', icon: 'none' })
    return
  }

  void searchResources(1)
}

function clearKeyword() {
  if (!keyword.value) {
    return
  }

  keyword.value = ''
  searchMode.value = 'keyword'
  results.value = []
  total.value = 0
  page.value = 1
}

function showCategoryFilterHint() {
  uni.showToast({
    title: '分类跟随当前入口',
    icon: 'none',
  })
}

function showYearFilterHint() {
  uni.showToast({
    title: '年份筛选稍后开放',
    icon: 'none',
  })
}

function openResourceTypeFilter() {
  uni.showActionSheet({
    itemList: RESOURCE_TYPE_OPTIONS.map(item => item.label),
    success: (res) => {
      const selectedOption = RESOURCE_TYPE_OPTIONS[res.tapIndex]
      if (!selectedOption) {
        return
      }

      resourceType.value = selectedOption.value

      if (!hasKeyword.value) {
        return
      }

      void searchResources(1)
    },
  })
}

onLoad((options) => {
  keyword.value = decodeQueryValue(options?.keyword)
  categoryId.value = parseOptionalNumber(options?.categoryId)
  categoryName.value = decodeQueryValue(options?.categoryName)

  if (keyword.value) {
    void searchResources(1)
    return
  }

  initialized.value = true
})

onPullDownRefresh(async () => {
  if (searchMode.value === 'vector') {
    await triggerVectorSearch()
  }
  else {
    await searchResources(1)
  }
  uni.stopPullDownRefresh()
})

onReachBottom(() => {
  if (
    !hasKeyword.value
    || searchMode.value !== 'keyword'
    || loading.value
    || loadingMore.value
    || !hasMore.value
  ) {
    return
  }

  void searchResources(page.value + 1)
})
</script>

<template>
  <view class="relative min-h-screen overflow-hidden from-[#E1F0FF] via-[#F0F7FF] to-[#F8FAFC] bg-gradient-to-b text-[#334155]">
    <view class="pointer-events-none absolute h-72 w-72 rounded-full bg-[#BAE6FD]/40 blur-3xl -right-10 -top-10" />
    <view class="pointer-events-none absolute top-32 h-56 w-56 rounded-full bg-[#E0F2FE]/50 blur-3xl -left-12" />

    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center text-[#1E293B] active:opacity-60" @tap="goBack">
          <view class="i-carbon-chevron-left text-[24px]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">资料搜索</text>
      </view>
    </view>

    <view class="relative z-10 mt-4 px-4 pb-24">
      <view class="rounded-[26px] border border-white bg-white/82 px-4 py-3 shadow-[0_2px_10px_-4px_rgba(0,0,0,0.05)] backdrop-blur-md">
        <view class="flex items-center gap-2">
          <view class="i-carbon-search mr-2 text-xl text-[#94A3B8]" />
          <input
            v-model="keyword"
            class="h-6 flex-1 text-[15px] text-[#1E293B]"
            confirm-type="search"
            :maxlength="50"
            placeholder="搜索资料名称、简介、内容语义"
            placeholder-style="color: #94A3B8;"
            @confirm="submitSearch"
          >
          <view
            v-if="keyword"
            class="ml-2 h-6 w-6 flex items-center justify-center rounded-full bg-[#F1F5F9] text-[#94A3B8]"
            @tap="clearKeyword"
          >
            <view class="i-carbon-close text-sm" />
          </view>
          <view class="shrink-0 text-[13px] text-[#2563EB] font-bold" @tap="submitSearch">
            搜索
          </view>
        </view>
      </view>

      <view class="mt-4 flex items-center gap-6 overflow-x-auto px-1 whitespace-nowrap">
        <view
          class="flex shrink-0 items-center gap-1 text-[14px] font-medium"
          :class="categoryName ? 'text-[#F97316]' : 'text-[#475569]'"
          @tap="showCategoryFilterHint"
        >
          <text>{{ currentCategoryFilterLabel }}</text>
          <view class="i-carbon-chevron-down text-[12px]" />
        </view>

        <view
          class="flex shrink-0 items-center gap-1 text-[14px] text-[#475569] font-medium"
          @tap="showYearFilterHint"
        >
          <text>{{ currentYearFilterLabel }}</text>
          <view class="i-carbon-chevron-down text-[12px]" />
        </view>

        <view
          class="flex shrink-0 items-center gap-1 text-[14px] font-medium"
          :class="resourceType ? 'text-[#F97316]' : 'text-[#475569]'"
          @tap="openResourceTypeFilter"
        >
          <text>{{ currentResourceTypeFilterLabel }}</text>
          <view class="i-carbon-chevron-down text-[12px]" />
        </view>
      </view>

      <view class="mt-4 flex items-center justify-between px-1">
        <text class="text-[13px] text-[#475569] font-bold">搜索结果</text>
        <text v-if="hasKeyword" class="text-[11px] text-[#94A3B8]">{{ total }} 条</text>
      </view>

      <view v-if="loading && !results.length" class="py-18 text-center text-[13px] text-[#94A3B8]">
        搜索中...
      </view>

      <view
        v-else-if="results.length"
        class="mt-3 overflow-hidden border border-white/80 rounded-2xl bg-white/82 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md"
      >
        <view
          v-for="(item, index) in results"
          :key="`${searchMode}-${item.resource.id}-${index}`"
          class="flex items-start gap-3 px-4 py-3.5 transition-colors active:bg-[#F8FAFC]"
          :class="index < results.length - 1 ? 'border-b border-blue-50/70' : ''"
          @tap="openResourceDetail(item)"
        >
          <view class="mt-0.5 h-9 w-9 flex shrink-0 items-center justify-center rounded-2xl bg-[#EFF6FF] text-[#2563EB] shadow-inner">
            <view class="i-carbon-document text-[18px]" />
          </view>

          <view class="min-w-0 flex-1">
            <view class="line-clamp-1 text-[15px] text-[#1E293B] font-semibold leading-[1.45]">
              {{ getResourceName(item.resource) }}
            </view>

            <view
              v-if="getResourceRemark(item.resource)"
              class="mt-1 line-clamp-2 text-[12px] text-[#64748B] leading-[1.6]"
            >
              {{ getResourceRemark(item.resource) }}
            </view>

            <view class="mt-2 flex flex-wrap items-center gap-2">
              <view
                v-if="item.resource.category_name"
                class="rounded-full bg-[#F8FAFC] px-2.5 py-1 text-[11px] text-[#64748B]"
              >
                {{ item.resource.category_name }}
              </view>
              <view
                v-if="item.resource.resource_type"
                class="rounded-full bg-[#EFF6FF] px-2.5 py-1 text-[11px] text-[#2563EB]"
              >
                {{ item.resource.resource_type }}
              </view>
              <view
                v-if="getSimilarityText(item.similarity)"
                class="rounded-full bg-[#ECFDF5] px-2.5 py-1 text-[11px] text-[#059669]"
              >
                {{ getSimilarityText(item.similarity) }}
              </view>
            </view>
          </view>
        </view>

        <view v-if="loadingMore" class="px-4 py-4 text-center text-[12px] text-[#94A3B8]">
          正在加载更多结果...
        </view>
      </view>

      <view v-else-if="initialized" class="flex flex-col items-center justify-center py-24">
        <view class="i-carbon-search mb-4 text-6xl text-[#CBD5E1]" />
        <text class="text-[14px] text-[#94A3B8]">{{ emptyMessage }}</text>
        <view
          v-if="canTryVectorSearch"
          class="mt-4 rounded-full bg-[#1E293B] px-4 py-2 text-[13px] text-white font-semibold shadow-sm"
          @tap="triggerVectorSearch"
        >
          试试强力搜索
        </view>
      </view>
    </view>
  </view>
</template>
