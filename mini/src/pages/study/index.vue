<script lang="ts" setup>
import type { CoulddriveResourceListItem } from '@fba/api-sdk'
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import { fbaApi } from '@/api/sdk'

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

const { statusBarHeight } = uni.getSystemInfoSync()

const loading = ref(false)
const loadingMore = ref(false)
const initialized = ref(false)
const keyword = ref('')
const selectedResourceType = ref('all')
const resources = ref<CoulddriveResourceListItem[]>([])
const total = ref(0)
const page = ref(1)

const hasMore = computed(() => resources.value.length < total.value)
const resourceTypeOptions = computed(() => {
  const typeSet = new Set<string>()
  const options = [{ label: '全部', value: 'all' }]

  resources.value.forEach((item) => {
    const value = String(item.resource_type || '').trim()
    if (!value || typeSet.has(value)) {
      return
    }

    typeSet.add(value)
    options.push({
      label: value,
      value,
    })
  })

  if (
    selectedResourceType.value !== 'all'
    && !options.some(item => item.value === selectedResourceType.value)
  ) {
    options.unshift({
      label: selectedResourceType.value,
      value: selectedResourceType.value,
    })
  }

  return options
})

function normalizeKeyword(value: string) {
  return String(value || '').trim()
}

function buildQuery(targetPage = 1) {
  return {
    page: targetPage,
    size: PAGE_SIZE,
    status: 1,
    keyword: normalizeKeyword(keyword.value) || undefined,
    resource_type: selectedResourceType.value === 'all' ? undefined : selectedResourceType.value,
  }
}

async function loadResources(targetPage = 1) {
  const isFirstPage = targetPage === 1
  if (isFirstPage) {
    loading.value = true
  }
  else {
    loadingMore.value = true
  }

  try {
    const data = await fbaApi.coulddrive.resource.getList(buildQuery(targetPage))
    const items = Array.isArray(data.items) ? data.items : []

    resources.value = isFirstPage ? items : [...resources.value, ...items]
    total.value = Number(data.total || 0)
    page.value = targetPage
    initialized.value = true
  }
  catch (error) {
    console.error('加载学习资料失败:', error)
    if (isFirstPage) {
      resources.value = []
      total.value = 0
    }
    uni.showToast({ title: '加载资料失败', icon: 'none' })
  }
  finally {
    loading.value = false
    loadingMore.value = false
  }
}

function triggerSearch() {
  loadResources(1)
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
  triggerSearch()
}

function selectResourceType(value: string) {
  if (selectedResourceType.value === value) {
    return
  }

  selectedResourceType.value = value
  loadResources(1)
}

function formatFileSize(size?: number | null) {
  const value = Number(size || 0)
  if (!value) {
    return ''
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1).replace(/\.0$/, '')} KB`
  }
  if (value < 1024 * 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(1).replace(/\.0$/, '')} MB`
  }
  return `${(value / 1024 / 1024 / 1024).toFixed(1).replace(/\.0$/, '')} GB`
}

function formatRelativeTime(value?: string | null) {
  if (!value) {
    return ''
  }

  const target = new Date(value.replace(' ', 'T')).getTime()
  if (!target) {
    return value
  }

  const diff = Date.now() - target
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour

  if (diff < hour) {
    return `${Math.max(1, Math.floor(diff / minute))}分钟前`
  }
  if (diff < day) {
    return `${Math.max(1, Math.floor(diff / hour))}小时前`
  }
  if (diff < day * 30) {
    return `${Math.max(1, Math.floor(diff / day))}天前`
  }

  return value.slice(0, 10)
}

function getResourceName(item: CoulddriveResourceListItem) {
  return item.main_name || item.title || `资料 #${item.id}`
}

function getResourceSubtitle(item: CoulddriveResourceListItem) {
  return item.resource_intro || item.description || item.category_name || '暂无资料简介'
}

function getResourceMeta(item: CoulddriveResourceListItem) {
  const parts = [
    item.category_name || '',
    formatFileSize(item.file_size),
    item.view_count ? `${item.view_count} 浏览` : '',
    formatRelativeTime(item.created_time),
  ].filter(Boolean)
  return parts.join(' · ')
}

function getResourceIconClass(item: CoulddriveResourceListItem) {
  const fileType = String(item.file_type || '').toLowerCase()
  const resourceType = String(item.resource_type || '').toLowerCase()

  if (fileType === 'pdf') {
    return 'i-carbon-document-pdf'
  }
  if (fileType.includes('doc') || fileType.includes('txt') || fileType.includes('md')) {
    return 'i-carbon-document'
  }
  if (fileType.includes('ppt')) {
    return 'i-carbon-document'
  }
  if (fileType.includes('xls')) {
    return 'i-carbon-table'
  }
  if (fileType.includes('zip') || fileType.includes('rar') || fileType.includes('7z')) {
    return 'i-carbon-folder'
  }
  if (fileType.includes('mp4') || resourceType.includes('视频')) {
    return 'i-carbon-video'
  }
  if (fileType.includes('mp3') || resourceType.includes('音频')) {
    return 'i-carbon-volume-up'
  }
  if (fileType.includes('jpg') || fileType.includes('png') || fileType.includes('jpeg')) {
    return 'i-carbon-image'
  }
  return 'i-carbon-document'
}

function getResourceIconStyle(item: CoulddriveResourceListItem) {
  const fileType = String(item.file_type || '').toLowerCase()
  const resourceType = String(item.resource_type || '').toLowerCase()

  if (fileType === 'pdf') {
    return {
      wrapper: 'from-[#FEF2F2] to-[#FEE2E2] text-[#DC2626]',
      action: 'bg-[#FEF2F2] text-[#DC2626]',
    }
  }
  if (fileType.includes('mp4') || resourceType.includes('视频')) {
    return {
      wrapper: 'from-[#EEF2FF] to-[#E0E7FF] text-[#4F46E5]',
      action: 'bg-[#EEF2FF] text-[#4F46E5]',
    }
  }
  if (fileType.includes('jpg') || fileType.includes('png') || fileType.includes('jpeg')) {
    return {
      wrapper: 'from-[#ECFDF5] to-[#D1FAE5] text-[#059669]',
      action: 'bg-[#ECFDF5] text-[#059669]',
    }
  }
  return {
    wrapper: 'from-[#EFF6FF] to-[#DBEAFE] text-[#2563EB]',
    action: 'bg-[#EFF6FF] text-[#2563EB]',
  }
}

function copyResourceInfo(item: CoulddriveResourceListItem) {
  const content = [
    getResourceName(item),
    item.url,
    item.extract_code ? `提取码：${item.extract_code}` : '',
  ].filter(Boolean).join('\n')

  uni.setClipboardData({
    data: content,
    success: () => {
      uni.showToast({
        title: item.extract_code ? '链接和提取码已复制' : '资料链接已复制',
        icon: 'none',
      })
    },
  })
}

function handleResourceAction(item: CoulddriveResourceListItem) {
  const itemList = ['复制资料链接']
  if (item.extract_code) {
    itemList.push('仅复制提取码')
  }

  uni.showActionSheet({
    itemList,
    success: (res) => {
      if (res.tapIndex === 0) {
        copyResourceInfo(item)
        return
      }

      if (item.extract_code && res.tapIndex === 1) {
        uni.setClipboardData({
          data: item.extract_code,
          success: () => uni.showToast({ title: '提取码已复制', icon: 'none' }),
        })
      }
    },
  })
}

onLoad(() => {
  loadResources(1)
})

onPullDownRefresh(async () => {
  await loadResources(1)
  uni.stopPullDownRefresh()
})

onReachBottom(() => {
  if (loading.value || loadingMore.value || !initialized.value || !hasMore.value) {
    return
  }

  loadResources(page.value + 1)
})
</script>

<template>
  <view class="relative min-h-screen overflow-hidden from-[#E1F0FF] via-[#F0F7FF] to-[#F8FAFC] bg-gradient-to-b text-[#334155]">
    <view class="pointer-events-none absolute h-72 w-72 rounded-full bg-[#BAE6FD]/40 blur-3xl -right-10 -top-10" />
    <view class="pointer-events-none absolute top-32 h-56 w-56 rounded-full bg-[#E0F2FE]/50 blur-3xl -left-12" />

    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="h-11 flex items-center justify-between px-4">
        <view class="w-20" />
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">资料大厅</text>
        <view class="w-20" />
      </view>
    </view>

    <view class="relative z-10 mt-4 px-4 pb-24">
      <view class="mb-5 flex items-center border border-white rounded-full bg-white/78 px-4 py-2.5 shadow-[0_2px_10px_-4px_rgba(0,0,0,0.05)] backdrop-blur-md">
        <view class="i-carbon-search mr-2 text-xl text-[#94A3B8]" />
        <input
          v-model="keyword"
          class="h-6 flex-1 text-[15px] text-[#1E293B]"
          confirm-type="search"
          maxlength="50"
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
        <view class="ml-3 text-[13px] text-[#2563EB] font-bold" @tap="triggerSearch">
          搜索
        </view>
      </view>

      <scroll-view scroll-x class="mb-5 whitespace-nowrap">
        <view class="flex items-center gap-3 pl-1">
          <view
            v-for="item in resourceTypeOptions"
            :key="item.value"
            class="shrink-0 border rounded-full px-3.5 py-1.5 text-xs font-bold transition-colors"
            :class="selectedResourceType === item.value
              ? 'border-[#DBEAFE] bg-[#EFF6FF] text-[#2563EB] shadow-sm'
              : 'border-[#E2E8F0] bg-white/65 text-[#475569]'"
            @tap="selectResourceType(item.value)"
          >
            {{ item.label }}
          </view>
        </view>
      </scroll-view>

      <view class="mb-3 flex items-center justify-between pl-1">
        <text class="text-sm text-[#64748B] font-bold">最近更新资料</text>
        <text class="text-[11px] text-[#94A3B8]">共 {{ total }} 条</text>
      </view>

      <view v-if="loading && resources.length === 0" class="py-18 text-center text-[13px] text-[#94A3B8]">
        资料加载中...
      </view>

      <view
        v-else-if="resources.length > 0"
        class="border border-white/80 rounded-2xl bg-white/80 p-4 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md"
      >
        <view
          v-for="(item, index) in resources"
          :key="item.id"
          class="flex items-start"
          :class="index < resources.length - 1 ? 'mb-4 border-b border-blue-50/60 pb-4' : ''"
          @tap="handleResourceAction(item)"
        >
          <view
            class="mr-4 h-11 w-11 flex items-center justify-center rounded-xl bg-gradient-to-br shadow-inner"
            :class="getResourceIconStyle(item).wrapper"
          >
            <view :class="[getResourceIconClass(item), 'text-2xl']" />
          </view>

          <view class="min-w-0 flex-1">
            <view class="flex items-start justify-between gap-3">
              <view class="min-w-0 flex-1">
                <view class="line-clamp-2 text-[15px] text-[#1E293B] font-bold leading-[1.45]">
                  {{ getResourceName(item) }}
                </view>
                <view class="mt-1 line-clamp-2 text-[12px] text-[#64748B] leading-[1.6]">
                  {{ getResourceSubtitle(item) }}
                </view>
              </view>

              <view
                v-if="item.hot"
                class="shrink-0 rounded-full bg-[#FFF7ED] px-2 py-0.5 text-[10px] text-[#EA580C] font-bold"
              >
                HOT
              </view>
            </view>

            <view class="mt-2 flex items-center justify-between gap-3">
              <view class="min-w-0 flex-1 text-[11px] text-[#94A3B8] leading-[1.5]">
                {{ getResourceMeta(item) }}
              </view>
              <view
                class="h-8 w-8 flex shrink-0 items-center justify-center rounded-full transition-transform active:scale-90"
                :class="getResourceIconStyle(item).action"
              >
                <view class="i-carbon-copy text-lg" />
              </view>
            </view>

            <view v-if="item.extract_code" class="mt-2 inline-flex items-center rounded-full bg-[#F8FAFC] px-2.5 py-1 text-[10px] text-[#64748B]">
              提取码 {{ item.extract_code }}
            </view>
          </view>
        </view>

        <view v-if="loadingMore" class="pt-4 text-center text-[12px] text-[#94A3B8]">
          正在加载更多资料...
        </view>
      </view>

      <view v-else class="flex flex-col items-center justify-center py-20">
        <view class="i-carbon-book mb-4 text-6xl text-[#CBD5E1]" />
        <text class="text-[14px] text-[#94A3B8]">暂时没有找到相关资料，换个关键词试试</text>
      </view>
    </view>
  </view>
</template>
