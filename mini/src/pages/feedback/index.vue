<script lang="ts" setup>
import type { FeedbackType } from '@fba/api-sdk'
import { onLoad } from '@dcloudio/uni-app'
import { ref } from 'vue'
import FeedbackPanel from '@/components/FeedbackPanel.vue'

defineOptions({
  name: 'FeedbackPage',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '意见反馈',
  },
})

interface FeedbackRouteContext {
  title?: string
  subtitle?: string
  feedbackType?: FeedbackType | null
  pagePath?: string | null
  targetType?: string | null
  targetId?: string | null
  targetText?: string | null
}

const routeContext = ref<FeedbackRouteContext>({
  title: '意见反馈',
  subtitle: '遇到题目问题、功能异常、体验建议，都可以在这里告诉我们',
  feedbackType: null,
  pagePath: null,
  targetType: null,
  targetId: null,
  targetText: null,
})

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

function decodeQueryValue(value: unknown): string | null {
  if (value === undefined || value === null) {
    return null
  }

  const text = String(value).trim()
  if (!text) {
    return null
  }

  try {
    return decodeURIComponent(text)
  }
  catch {
    return text
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

function handleSuccess() {
  setTimeout(() => {
    goBack()
  }, 450)
}

onLoad((query) => {
  const feedbackType = decodeQueryValue(query?.feedbackType) as FeedbackType | null

  routeContext.value = {
    title: decodeQueryValue(query?.title) || '意见反馈',
    subtitle: decodeQueryValue(query?.subtitle) || '遇到题目问题、功能异常、体验建议，都可以在这里告诉我们',
    feedbackType,
    pagePath: decodeQueryValue(query?.pagePath),
    targetType: decodeQueryValue(query?.targetType),
    targetId: decodeQueryValue(query?.targetId),
    targetText: decodeQueryValue(query?.targetText),
  }
})
</script>

<template>
  <view class="relative min-h-screen w-full overflow-x-hidden overflow-y-hidden from-[#F3E8FF] via-[#F8F5FB] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="pointer-events-none absolute h-80 w-80 rounded-full bg-[#E9D5FF]/40 blur-[40px] -right-8 -top-12" />
    <view class="pointer-events-none absolute top-24 h-60 w-60 rounded-full bg-[#FBCFE8]/20 blur-[40px] -left-16" />

    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center text-[#1E293B] active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">意见反馈</text>
      </view>
    </view>

    <scroll-view scroll-y class="box-border relative z-10 h-[calc(100vh-44px)] w-full px-4 pb-10 pt-4">
      <FeedbackPanel
        :title="routeContext.title"
        :subtitle="routeContext.subtitle"
        :feedback-type="routeContext.feedbackType"
        :page-path="routeContext.pagePath"
        :target-type="routeContext.targetType"
        :target-id="routeContext.targetId"
        :target-text="routeContext.targetText"
        @success="handleSuccess"
      />
      <view class="h-safe-area-bottom w-full" />
    </scroll-view>
  </view>
</template>
