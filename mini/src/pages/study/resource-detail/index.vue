<script lang="ts" setup>
import type { CoulddriveResourceListItem } from '@fba/api-sdk'
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { fbaApi } from '@/api/sdk'

defineOptions({
  name: 'StudyResourceDetail',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '资料详情',
  },
})

interface ResourceDetail extends CoulddriveResourceListItem {
  extract_code?: string | null
  resource_image?: string | null
  path_info?: string | null
  content?: string | null
}

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const resourceId = ref(0)
const loading = ref(false)
const resource = ref<ResourceDetail | null>(null)

const summaryText = computed(() => {
  if (!resource.value) {
    return ''
  }

  return String(
    resource.value.resource_intro
      || resource.value.description
      || resource.value.remark
      || '',
  ).trim()
})

const detailRows = computed(() => {
  if (!resource.value) {
    return []
  }

  return [
    { label: '提取码', value: resource.value.extract_code || '无' },
    { label: '文件大小', value: formatFileSize(resource.value.file_size) },
    { label: '更新时间', value: formatDateTime(resource.value.updated_time || resource.value.created_time) },
  ]
})

function parsePositiveNumber(value: unknown) {
  const num = Number(value)
  return Number.isFinite(num) && num > 0 ? num : 0
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '-'
  }

  const normalizedValue = String(value).trim().replace(' ', 'T')
  const date = new Date(normalizedValue)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }

  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  const hour = `${date.getHours()}`.padStart(2, '0')
  const minute = `${date.getMinutes()}`.padStart(2, '0')

  return `${year}-${month}-${day} ${hour}:${minute}`
}

function formatFileSize(value?: number | null) {
  const size = Number(value)
  if (!Number.isFinite(size) || size <= 0) {
    return '未知'
  }

  if (size < 1024) {
    return `${size} B`
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }

  if (size < 1024 * 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`
  }

  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function getDriveTypeLabel(value?: string | null) {
  const driveType = String(value || '').trim()
  if (!driveType) {
    return '-'
  }

  if (driveType === 'BaiduDrive') {
    return '百度网盘'
  }

  if (driveType === 'QuarkDrive') {
    return '夸克网盘'
  }

  if (driveType === 'AlistDrive') {
    return 'AList 网盘'
  }

  if (driveType === 'LocalFile') {
    return '本地文件'
  }

  return driveType
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }

  uni.switchTab({ url: '/pages/study/index' })
}

function getResourceName(item: ResourceDetail) {
  return item.title || `资料 #${item.id}`
}

function buildCopyContent(includeExtractCode = true) {
  if (!resource.value) {
    return ''
  }

  return [
    getResourceName(resource.value),
    resource.value.url,
    includeExtractCode && resource.value.extract_code ? `提取码：${resource.value.extract_code}` : '',
  ].filter(Boolean).join('\n')
}

function copyText(data: string, successTitle: string) {
  if (!data) {
    uni.showToast({ title: '暂无可复制内容', icon: 'none' })
    return
  }

  uni.setClipboardData({
    data,
    success: () => {
      uni.showToast({
        title: successTitle,
        icon: 'none',
      })
    },
  })
}

function copyResourceLink() {
  copyText(
    buildCopyContent(true),
    resource.value?.extract_code ? '链接和提取码已复制' : '资料链接已复制',
  )
}

function copyExtractCode() {
  copyText(resource.value?.extract_code || '', '提取码已复制')
}

function previewResourceImage() {
  if (!resource.value?.resource_image) {
    return
  }

  uni.previewImage({
    urls: [resource.value.resource_image],
    current: resource.value.resource_image,
  })
}

async function loadResourceDetail() {
  if (!resourceId.value) {
    return
  }

  loading.value = true

  try {
    const data = await fbaApi.coulddrive.resource.getDetail(resourceId.value) as unknown as ResourceDetail
    resource.value = data
  }
  catch (error) {
    console.error('加载资料详情失败:', error)
    uni.showToast({ title: '加载资料详情失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

function recordResourceClick() {
  if (!resourceId.value) {
    return
  }

  void fbaApi.coulddrive.resource.recordClick(resourceId.value).catch((error) => {
    console.warn('记录资源点击失败:', error)
  })
}

onLoad((query) => {
  resourceId.value = parsePositiveNumber(query?.id)

  if (!resourceId.value) {
    uni.showToast({ title: '资料不存在', icon: 'none' })
    return
  }

  void loadResourceDetail()
  recordResourceClick()
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
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">资料详情</text>
      </view>
    </view>

    <view v-if="loading" class="relative z-10 px-4 py-20 text-center text-[14px] text-[#94A3B8]">
      资料加载中...
    </view>

    <view v-else-if="resource" class="relative z-10 px-4 pb-36 pt-4">
      <view class="overflow-hidden border border-white/80 rounded-[28px] bg-white/84 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.05)] backdrop-blur-md">
        <image
          v-if="resource.resource_image"
          :src="resource.resource_image"
          class="h-44 w-full bg-[#F8FAFC]"
          mode="aspectFill"
          @tap="previewResourceImage"
        />

        <view class="px-5 pb-5 pt-5">
          <view class="text-[20px] text-[#1E293B] font-black leading-[1.45]">
            {{ getResourceName(resource) }}
          </view>

          <view class="mt-4 flex flex-wrap items-center gap-2">
            <view
              v-if="resource.category_name"
              class="rounded-full bg-[#F8FAFC] px-3 py-1 text-[12px] text-[#64748B]"
            >
              {{ resource.category_name }}
            </view>
            <view
              v-if="resource.resource_type"
              class="rounded-full bg-[#EFF6FF] px-3 py-1 text-[12px] text-[#2563EB]"
            >
              {{ resource.resource_type }}
            </view>
            <view class="rounded-full bg-[#ECFDF5] px-3 py-1 text-[12px] text-[#059669]">
              {{ getDriveTypeLabel(resource.url_type) }}
            </view>
          </view>

        </view>
      </view>

      <view class="mt-4 border border-white/80 rounded-[24px] bg-white/82 p-5 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="text-[15px] text-[#1E293B] font-bold">
          资料简介
        </view>
        <view class="mt-3 text-[13px] text-[#64748B] leading-[1.8] whitespace-pre-wrap">
          {{ summaryText || '暂无资料简介' }}
        </view>
      </view>

      <view class="mt-4 border border-white/80 rounded-[24px] bg-white/82 p-5 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="text-[15px] text-[#1E293B] font-bold">
          分享信息
        </view>

        <view class="mt-4 flex flex-col gap-3">
          <view
            v-for="row in detailRows"
            :key="row.label"
            class="flex items-start justify-between gap-4"
          >
            <text class="shrink-0 text-[12px] text-[#94A3B8]">
              {{ row.label }}
            </text>
            <text class="min-w-0 text-right text-[13px] text-[#334155] leading-[1.6] break-all">
              {{ row.value }}
            </text>
          </view>
        </view>
      </view>

      <view class="mt-4 border border-white/80 rounded-[24px] bg-white/82 p-5 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="flex items-center justify-between">
          <view class="text-[15px] text-[#1E293B] font-bold">
            资料链接
          </view>
          <view class="text-[12px] text-[#2563EB] font-medium" @tap="copyResourceLink">
            复制
          </view>
        </view>

        <view class="mt-3 rounded-2xl bg-[#F8FAFC] px-4 py-3 text-[12px] text-[#64748B] leading-[1.7] break-all">
          {{ resource.url }}
        </view>
      </view>
    </view>

    <view v-else class="relative z-10 flex flex-col items-center justify-center px-4 py-24">
      <view class="i-carbon-document-unknown mb-4 text-6xl text-[#CBD5E1]" />
      <text class="text-[14px] text-[#94A3B8]">
        暂时没有找到这份资料
      </text>
      <view
        class="mt-5 rounded-full bg-[#1E293B] px-5 py-2 text-[13px] text-white font-semibold"
        @tap="goBack"
      >
        返回上一页
      </view>
    </view>

    <view
      v-if="resource"
      class="fixed inset-x-0 bottom-0 z-20 border-t border-white/70 bg-white/92 px-4 pt-3 backdrop-blur-md"
      :style="{ paddingBottom: 'calc(16px + env(safe-area-inset-bottom))' }"
    >
      <view class="flex items-center gap-3">
        <view
          v-if="resource.extract_code"
          class="h-11 flex flex-1 items-center justify-center rounded-2xl bg-[#F8FAFC] text-[13px] text-[#334155] font-semibold"
          @tap="copyExtractCode"
        >
          复制提取码
        </view>
        <view
          class="h-11 flex flex-1 items-center justify-center rounded-2xl bg-[#DBEAFE] text-[13px] text-[#1D4ED8] font-semibold"
          @tap="copyResourceLink"
        >
          复制链接
        </view>
      </view>
    </view>
  </view>
</template>
