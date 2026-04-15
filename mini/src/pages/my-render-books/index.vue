<script lang="ts" setup>
import type { PageData, RenderJobResult, RenderJobFile } from '@fba/api-sdk'
import { computed, ref } from 'vue'
import { onPullDownRefresh, onReachBottom, onShow } from '@dcloudio/uni-app'
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'
import { getEnvBaseUrl } from '@/utils'
import { formatDateTime } from '@/utils/mine'
import { toLoginPage } from '@/utils/toLoginPage'

defineOptions({
  name: 'MyRenderBooks',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '我的题本',
  },
})

const PAGE_SIZE = 20

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const loading = ref(false)
const loadingMore = ref(false)
const previewingJobId = ref('')
const downloadingJobId = ref('')
const jobs = ref<RenderJobResult[]>([])
const total = ref(0)
const page = ref(1)

const hasMore = computed(() => jobs.value.length < total.value)

function ensureLogin() {
  tokenStore.updateNowTime()
  if (tokenStore.hasLogin) {
    return true
  }

  uni.showToast({ title: '请先登录后查看我的题本', icon: 'none' })
  setTimeout(() => {
    toLoginPage()
  }, 300)
  return false
}

async function loadJobs(targetPage = 1) {
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
    const data = await fbaApi.renderBook.listJobs({
      page: targetPage,
      size: PAGE_SIZE,
    } as any) as PageData<RenderJobResult>
    jobs.value = isFirstPage ? data.items : [...jobs.value, ...data.items]
    total.value = data.total
    page.value = targetPage
  }
  catch (error) {
    console.error('加载我的题本失败:', error)
    if (isFirstPage) {
      jobs.value = []
      total.value = 0
    }
    uni.showToast({ title: '加载我的题本失败', icon: 'none' })
  }
  finally {
    loading.value = false
    loadingMore.value = false
  }
}

function statusLabel(status: string) {
  const labelMap: Record<string, string> = {
    accepted: '排队中',
    running: '生成中',
    succeeded: '已完成',
    failed: '失败',
  }
  return labelMap[status] || '未知状态'
}

function templateLabel(templateKey: string) {
  const labelMap: Record<string, string> = {
    exam_paper: '试卷',
    practice: '练习',
    wrong_question: '错题',
  }
  return labelMap[templateKey] || templateKey
}

function clickPreviewImage(urls: string[], current: string) {
  uni.previewImage({
    urls,
    current
  })
}

function resolveDownloadFile(job: RenderJobResult): RenderJobFile | null {
  const preferredKinds: Array<RenderJobFile['file_kind']> = ['combined_pdf', 'question_pdf', 'solution_pdf']
  for (const kind of preferredKinds) {
    const match = job.files.find(file => file.file_kind === kind && file.status === 'available')
    if (match) {
      return match
    }
  }
  return null
}

function getStoredAccessToken(): string {
  const directToken = uni.getStorageSync('access_token')
  if (directToken) {
    return directToken
  }

  const tokenStoreCache = uni.getStorageSync('token')
  if (!tokenStoreCache) {
    return ''
  }

  try {
    if (typeof tokenStoreCache === 'string') {
      const parsed = JSON.parse(tokenStoreCache)
      return parsed?.tokenInfo?.token || parsed?.tokenInfo?.accessToken || ''
    }
    return tokenStoreCache?.tokenInfo?.token || tokenStoreCache?.tokenInfo?.accessToken || ''
  }
  catch {
    return ''
  }
}

function toAbsoluteApiUrl(path: string) {
  const baseURL = import.meta.env.VITE_API_BASE_URL || getEnvBaseUrl() || 'http://127.0.0.1:8000'
  const apiPrefix = import.meta.env.VITE_API_PREFIX || '/api/v1'
  const base = String(baseURL).replace(/\/+$/, '')
  const prefix = String(apiPrefix).startsWith('/') ? apiPrefix : `/${apiPrefix}`
  return `${base}${prefix}${path}`
}

function downloadFile(url: string, useAuth: boolean) {
  const token = getStoredAccessToken()
  return new Promise<UniApp.DownloadSuccessData>((resolve, reject) => {
    uni.downloadFile({
      url,
      header: useAuth && token
        ? { Authorization: `Bearer ${token}` }
        : undefined,
      success: (result) => {
        if (result.statusCode >= 200 && result.statusCode < 300) {
          resolve(result)
          return
        }
        reject(new Error(`下载失败(${result.statusCode})`))
      },
      fail: reject,
    })
  })
}

function openPdf(filePath: string) {
  return new Promise<void>((resolve, reject) => {
    uni.openDocument({
      filePath,
      fileType: 'pdf',
      showMenu: true,
      success: () => resolve(),
      fail: reject,
    })
  })
}

async function openJob(job: RenderJobResult) {
  if (previewingJobId.value) {
    return
  }

  if (job.status !== 'succeeded') {
    uni.showToast({ title: '当前题本尚未生成完成', icon: 'none' })
    return
  }

  const file = resolveDownloadFile(job)
  if (!file) {
    uni.showToast({ title: '当前题本暂无可打开的 PDF 文件', icon: 'none' })
    return
  }

  previewingJobId.value = job.job_id
  uni.showLoading({ title: '预览中...', mask: true })
  try {
    const downloadUrl = file.url || toAbsoluteApiUrl(
      fbaApi.renderBook.buildJobFileUrl(job.job_id, file.file_kind, { prefer_url: true }),
    )
    const result = await downloadFile(downloadUrl, !file.url)
    await openPdf(result.tempFilePath)
  }
  catch (error) {
    console.error('打开题本失败:', error)
    uni.showToast({ title: (error as any)?.message || '打开题本失败', icon: 'none' })
  }
  finally {
    uni.hideLoading()
    previewingJobId.value = ''
  }
}

function saveFile(tempFilePath: string) {
  return new Promise<UniApp.SaveFileSuccess>((resolve, reject) => {
    uni.saveFile({
      tempFilePath,
      success: res => resolve(res),
      fail: reject,
    })
  })
}

async function downloadJob(job: RenderJobResult) {
  if (downloadingJobId.value) {
    return
  }

  if (job.status !== 'succeeded') {
    uni.showToast({ title: '当前题本尚未生成完成', icon: 'none' })
    return
  }

  const file = resolveDownloadFile(job)
  if (!file) {
    uni.showToast({ title: '当前题本暂无可下载的 PDF 文件', icon: 'none' })
    return
  }

  downloadingJobId.value = job.job_id
  uni.showLoading({ title: '下载中...', mask: true })
  try {
    const downloadUrl = file.url || toAbsoluteApiUrl(
      fbaApi.renderBook.buildJobFileUrl(job.job_id, file.file_kind, { prefer_url: true }),
    )
    const result = await downloadFile(downloadUrl, !file.url)
    await saveFile(result.tempFilePath)

    uni.showModal({
      title: '下载完成',
      content: '已保存到小程序本地文件。你可以点击「预览」，在打开的 PDF 页面右上角菜单里进行转发或另存。',
      confirmText: '去预览',
      cancelText: '知道了',
      success: (res) => {
        if (res.confirm) {
          void openJob(job)
        }
      },
    })
  }
  catch (error) {
    console.error('下载题本失败:', error)
    uni.showToast({ title: (error as any)?.message || '下载题本失败', icon: 'none' })
  }
  finally {
    uni.hideLoading()
    downloadingJobId.value = ''
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
  loadJobs()
})

onPullDownRefresh(async () => {
  await loadJobs()
  uni.stopPullDownRefresh()
})

onReachBottom(() => {
  if (loading.value || loadingMore.value || !hasMore.value) {
    return
  }
  loadJobs(page.value + 1)
})
</script>

<template>
  <view class="relative min-h-screen from-[#FFF7ED] via-[#F8FCF9] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">我的题本</text>
      </view>
    </view>

    <view class="mt-4 px-4 pb-24">
      <view class="mb-3 flex items-center justify-between pl-1">
        <text class="text-[13px] text-[#475569] font-bold">导出记录</text>
        <text class="text-[11px] text-[#94A3B8]">共 {{ total }} 条</text>
      </view>

      <view v-if="loading && jobs.length === 0" class="py-18 text-center text-[13px] text-[#94A3B8]">
        题本记录加载中...
      </view>

      <view v-else-if="jobs.length === 0" class="py-18 text-center text-[13px] text-[#94A3B8]">
        暂无题本记录，先去刷题页导出一份吧。
      </view>

      <view v-else class="flex flex-col gap-3">
        <view
          v-for="job in jobs"
          :key="job.job_id"
          class="border border-white/60 rounded-2xl bg-white/80 px-4 py-4 shadow-[0_2px_12px_-6px_rgba(0,0,0,0.06)] backdrop-blur-md"
        >
          <view class="flex items-start justify-between gap-3">
            <view class="min-w-0 flex-1">
              <view class="flex flex-wrap items-center gap-2">
                <text
                  class="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold"
                  :class="job.status === 'succeeded'
                    ? 'bg-[#ECFDF5] text-[#16A34A]'
                    : job.status === 'failed'
                      ? 'bg-[#FEF2F2] text-[#DC2626]'
                      : 'bg-[#EFF6FF] text-[#2563EB]'"
                >
                  {{ statusLabel(job.status) }}
                </text>
                <text class="shrink-0 rounded-full bg-[#FFF7ED] px-2.5 py-1 text-[10px] text-[#EA580C] font-bold">
                  {{ templateLabel(job.template_key) }}
                </text>
              </view>

              <view class="mt-2 text-[14px] text-[#1E293B] font-bold">
                {{ job.title }}
              </view>

              <view class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-[#64748B]">
                <text>时间 {{ formatDateTime(job.created_at, 'MM-DD HH:mm') }}</text>
                <text v-if="job.question_count">题量 {{ job.question_count }}</text>
              </view>

              <view v-if="job.status === 'failed' && job.error_message" class="mt-2 text-[12px] text-[#DC2626] leading-5">
                {{ job.error_message }}
              </view>

              <!-- 新增的高清导览大图预览流 -->
              <view v-if="(job as any).metadata?.preview_urls?.length > 0" class="mt-4">
                <scroll-view scroll-x class="whitespace-nowrap w-full" :show-scrollbar="false">
                  <view class="inline-flex gap-2">
                    <image
                      v-for="(imgUrl, index) in (job as any).metadata.preview_urls"
                      :key="index"
                      :src="imgUrl"
                      mode="heightFix"
                      class="h-32 rounded-lg border border-gray-100 shadow-sm shrink-0 bg-gray-50 active:opacity-80 transition-opacity"
                      @click.stop="clickPreviewImage((job as any).metadata.preview_urls, imgUrl)"
                    />
                  </view>
                </scroll-view>
                <view class="text-[10px] text-[#94A3B8] mt-2 flex items-center">
                  <view class="i-carbon-view mr-1"></view>点击查看高清排版试读 (共 {{ (job as any).metadata.preview_urls.length }} 页)
                </view>
              </view>
            </view>

            <view class="shrink-0 pt-2">
              <view class="flex flex-col gap-2">
                <button
                  class="m-0 h-8 rounded-full px-4 text-[12px] text-white font-bold leading-[32px] w-full"
                  :class="job.status === 'succeeded'
                    ? 'bg-gradient-to-r from-[#EA580C] to-[#F97316] shadow-sm'
                    : 'bg-[#CBD5E1]'"
                  :disabled="job.status !== 'succeeded' || previewingJobId === job.job_id"
                  @click="openJob(job)"
                >
                  {{ previewingJobId === job.job_id ? '打开中' : '全本PDF' }}
                </button>
                <button
                  class="m-0 h-8 rounded-full px-4 text-[12px] text-[#C2410C] border border-[#FED7AA] bg-[#FFF7ED] font-bold leading-[32px] w-full"
                  :class="job.status === 'succeeded'
                    ? 'active:bg-[#FFEDD5]'
                    : 'bg-[#F8FAFC] border-[#E2E8F0] text-[#94A3B8]'"
                  :disabled="job.status !== 'succeeded' || downloadingJobId === job.job_id"
                  @click="downloadJob(job)"
                >
                  {{ downloadingJobId === job.job_id ? '下载中' : '下载' }}
                </button>
              </view>
            </view>
          </view>
        </view>
      </view>

      <view v-if="loadingMore" class="py-6 text-center text-[12px] text-[#94A3B8]">
        加载更多中...
      </view>
      <view v-else-if="jobs.length > 0 && !hasMore" class="py-6 text-center text-[12px] text-[#CBD5E1]">
        没有更多了
      </view>
    </view>
  </view>
</template>
