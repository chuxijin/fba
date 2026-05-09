<script lang="ts" setup>
import type { PageData, RenderJobResult, RenderJobFile } from '@fba/api-sdk'
import { computed, ref } from 'vue'
import { onPullDownRefresh, onReachBottom, onShow } from '@dcloudio/uni-app'
import { api, buildRenderBookFileUrl } from '@/api/sdk'
import { useTokenStore } from '@/store'
import { getEnvBaseUrl } from '@/utils'
import { getAppSettings } from '@/utils/appSettings'
import { formatDateTime } from '@/utils/mine'
import { getStudyDomainOption } from '@/utils/studyDomain'
import { toLoginPage } from '@/utils/toLoginPage'

defineOptions({
  name: 'MyRenderBooks',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '我的题本',
    enablePullDownRefresh: true,
  },
})

const PAGE_SIZE = 20

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const loading = ref(false)
const loadingMore = ref(false)
const previewingJobId = ref('')
const downloadingJobId = ref('')
const retryingJobId = ref('')
const jobs = ref<RenderJobResult[]>([])
const total = ref(0)
const page = ref(1)
const currentDomainCode = ref(getAppSettings().currentDomain)
const currentDomainLabel = ref(getStudyDomainOption(currentDomainCode.value).label)

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

  const nextDomainCode = getAppSettings().currentDomain
  const domainChanged = currentDomainCode.value !== nextDomainCode
  currentDomainCode.value = nextDomainCode
  currentDomainLabel.value = getStudyDomainOption(nextDomainCode).label

  if (targetPage === 1) {
    loading.value = true
  }
  else {
    loadingMore.value = true
  }

  try {
    const { data } = await api.listRenderJobs({
      query: {
        page: targetPage,
        size: PAGE_SIZE,
        study_domain: currentDomainCode.value,
      } as any,
    }) as any as { data: PageData<RenderJobResult> }

    const pageItems = data.items || []
    total.value = Number(data.total || 0)
    page.value = targetPage
    if (targetPage === 1 || domainChanged) {
      jobs.value = pageItems
      return
    }

    jobs.value = [...jobs.value, ...pageItems]
  }
  catch (error) {
    console.error('加载我的题本失败:', error)
    jobs.value = []
    total.value = 0
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
    failed: '生成失败',
  }
  return labelMap[status] || '未知状态'
}

function statusBadgeClass(status: string) {
  const classMap: Record<string, string> = {
    accepted: 'bg-[#EFF6FF] text-[#2563EB]',
    running: 'bg-[#FFF7ED] text-[#EA580C]',
    succeeded: 'bg-[#ECFDF5] text-[#16A34A]',
    failed: 'bg-[#FEF2F2] text-[#DC2626]',
  }
  return classMap[status] || 'bg-[#F8FAFC] text-[#64748B]'
}

function templateLabel(templateKey: string) {
  const labelMap: Record<string, string> = {
    basic_calculation: '基础计算',
    exam_paper: '整卷题本',
    practice: '练习题本',
    wrong_question: '错题本',
  }
  return labelMap[templateKey] || templateKey
}

function templateBadgeClass(templateKey: string) {
  const classMap: Record<string, string> = {
    basic_calculation: 'bg-[#FFF7ED] text-[#C2410C]',
    exam_paper: 'bg-[#EFF6FF] text-[#2563EB]',
    practice: 'bg-[#F0FDF4] text-[#16A34A]',
    wrong_question: 'bg-[#FEF2F2] text-[#DC2626]',
  }
  return classMap[templateKey] || 'bg-[#F8FAFC] text-[#64748B]'
}

function friendlyErrorMessage(message?: string | null) {
  if (!message) {
    return '生成过程中出现异常，请稍后重试。'
  }

  const normalized = message.toLowerCase()
  if (
    normalized.includes('all connection attempts failed')
    || normalized.includes('connection refused')
    || normalized.includes('connection reset')
    || normalized.includes('timeout')
  ) {
    return '渲染服务连接失败，请稍后重试。'
  }
  if (normalized.includes('latex') || normalized.includes('pdf')) {
    return 'PDF 生成失败，请检查题目内容后重试。'
  }

  if (message.length > 48) {
    return `${message.slice(0, 48)}...`
  }
  return message
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
      buildRenderBookFileUrl(job.job_id, file.file_kind, { prefer_url: true }),
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
      buildRenderBookFileUrl(job.job_id, file.file_kind, { prefer_url: true }),
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

async function retryJob(job: RenderJobResult) {
  if (retryingJobId.value) {
    return
  }

  if (job.status !== 'failed') {
    uni.showToast({ title: '当前任务不需要重试', icon: 'none' })
    return
  }

  retryingJobId.value = job.job_id
  try {
    await api.dispatchRenderJob({
      path: { job_id: job.job_id },
      query: { upload_to_oss: true },
    })
    jobs.value = jobs.value.map(item => item.job_id === job.job_id
      ? { ...item, status: 'running', error_message: null }
      : item)
    uni.showToast({ title: '已重新提交生成', icon: 'none' })
    setTimeout(() => {
      void loadJobs()
    }, 800)
  }
  catch (error) {
    console.error('重试生成题本失败:', error)
    uni.showToast({ title: (error as any)?.message || '重试失败', icon: 'none' })
  }
  finally {
    retryingJobId.value = ''
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
        <view class="flex items-center gap-2">
          <text class="text-[13px] text-[#475569] font-bold">导出记录</text>
          <text class="rounded-full bg-[#F8FAFC] px-2.5 py-1 text-[10px] text-[#475569] font-semibold">当前领域：{{ currentDomainLabel }}</text>
        </view>
        <text class="text-[11px] text-[#94A3B8]">共 {{ total }} 条</text>
      </view>

      <view v-if="loading && jobs.length === 0" class="py-18 text-center text-[13px] text-[#94A3B8]">
        题本记录加载中...
      </view>

      <view v-else-if="jobs.length === 0" class="py-18 text-center text-[13px] text-[#94A3B8]">
        {{ currentDomainLabel }}领域下暂无题本记录，先去刷题页导出一份吧。
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
                  :class="statusBadgeClass(job.status)"
                >
                  {{ statusLabel(job.status) }}
                </text>
                <text
                  class="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold"
                  :class="templateBadgeClass(job.template_key)"
                >
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

              <view
                v-if="job.status === 'failed'"
                class="mt-2 inline-flex max-w-full items-start gap-1.5 rounded-lg bg-[#FEF2F2] px-2.5 py-2 text-[12px] text-[#B91C1C] leading-5"
              >
                <view class="i-carbon-warning-alt-filled mt-0.5 shrink-0 text-[13px]" />
                <text class="min-w-0">
                  {{ friendlyErrorMessage(job.error_message) }}
                </text>
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
                  v-if="job.status === 'failed'"
                  class="m-0 h-8 rounded-full border border-[#FECACA] bg-[#FEF2F2] px-4 text-[12px] text-[#DC2626] font-bold leading-[32px] w-full active:bg-[#FEE2E2]"
                  :disabled="retryingJobId === job.job_id"
                  @click="retryJob(job)"
                >
                  {{ retryingJobId === job.job_id ? '提交中' : '重试' }}
                </button>
                <button
                  v-else
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
                  v-if="job.status !== 'failed'"
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
