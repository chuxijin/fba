<script lang="ts" setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getAppSettings } from '@/utils/appSettings'
import { getStudyDomainOption, type StudyDomainCode } from '@/utils/studyDomain'

defineOptions({
  name: 'AbilityPractice',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '能力练习',
  },
})

interface AbilityPracticeItem {
  title: string
  desc: string
  icon: string
  url?: string
}

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const currentDomain = ref<StudyDomainCode>(getAppSettings().currentDomain)

const abilityPracticeMap: Partial<Record<StudyDomainCode, AbilityPracticeItem[]>> = {
  kaoyan: [],
  gongkao: [
    {
      title: '基础计算练习',
      desc: '训练最基本的加减乘除，打好数资基础',
      icon: 'i-carbon-calculator',
      url: '/pages/basic-calculation/index',
    },
    {
      title: '资料分析专项',
      desc: '提供实际做题中常用公式的专项练习',
      icon: 'i-carbon-analytics',
    },
    {
      title: '思维能力训练',
      desc: '在潜移默化中提升思维能力或反应能力',
      icon: 'i-carbon-growth',
      url: '/pages/thinking-training/index',
    },
    {
      title: '数字推理训练',
      desc: '通过大量训练提高数字推理的敏感性',
      icon: 'i-carbon-number-small-0',
    },
  ],
}

const currentDomainOption = computed(() => getStudyDomainOption(currentDomain.value))
const practiceItems = computed(() => abilityPracticeMap[currentDomain.value] || [])
const emptyTitle = computed(() => {
  if (currentDomain.value === 'kaoyan') {
    return '考研能力练习暂未配置'
  }
  return `${currentDomainOption.value.label}能力练习暂未配置`
})
const emptyDesc = computed(() => {
  if (currentDomain.value === 'kaoyan') {
    return '当前先保留入口，等想清楚训练内容后再接入。'
  }
  return '后续会按当前领域展示专项练习入口。'
})

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.switchTab({ url: '/pages/mine/index' })
}

function openAbilityItem(item: AbilityPracticeItem) {
  if (item.url) {
    uni.navigateTo({ url: item.url })
    return
  }

  uni.showToast({ title: `${item.title} 正在接入中`, icon: 'none' })
}

onShow(() => {
  currentDomain.value = getAppSettings().currentDomain
})
</script>

<template>
  <view class="min-h-screen bg-[#F6F8FA] text-[#111827]">
    <view class="relative z-10 w-full bg-[#F6F8FA]" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white text-[#475569] shadow-sm active:scale-95" @click="goBack">
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="text-lg font-bold tracking-widest">
          能力练习
        </text>
        <view class="absolute right-4 rounded-full bg-[#ECFDF5] px-3 py-1 text-[12px] text-[#059669] font-bold">
          {{ currentDomainOption.shortLabel }}
        </view>
      </view>
    </view>

    <view class="px-4 pb-8 pt-4">
      <view v-if="practiceItems.length" class="flex flex-col gap-3">
        <view
          v-for="item in practiceItems"
          :key="item.title"
          class="flex items-center rounded-md bg-white px-4 py-4 shadow-[0_2px_12px_-8px_rgba(15,23,42,0.18)] active:scale-[0.99]"
          @click="openAbilityItem(item)"
        >
          <view class="mr-3 h-10 w-10 flex shrink-0 items-center justify-center rounded-md bg-[#ECFDF5] text-[#059669]">
            <view :class="item.icon" class="text-[22px]" />
          </view>
          <view class="min-w-0 flex-1">
            <view class="text-[16px] font-black leading-snug">
              {{ item.title }}
            </view>
            <view class="mt-1 text-[12px] text-[#6B7280] leading-snug">
              {{ item.desc }}
            </view>
          </view>
          <view class="i-carbon-chevron-right ml-3 shrink-0 text-[20px] text-[#9CA3AF]" />
        </view>
      </view>

      <view v-else class="rounded-md bg-white px-5 py-12 text-center shadow-[0_2px_12px_-8px_rgba(15,23,42,0.18)]">
        <view class="mx-auto mb-3 h-12 w-12 flex items-center justify-center rounded-md bg-[#F1F5F9] text-[#94A3B8]">
          <view class="i-carbon-rocket text-[24px]" />
        </view>
        <view class="text-[15px] text-[#1E293B] font-black">
          {{ emptyTitle }}
        </view>
        <view class="mt-1 text-[12px] text-[#94A3B8]">
          {{ emptyDesc }}
        </view>
      </view>
    </view>
  </view>
</template>
