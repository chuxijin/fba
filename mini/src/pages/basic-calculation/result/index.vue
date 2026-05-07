<script lang="ts" setup>
import { onLoad } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import {
  encodeBasicCalculationCustomConfig,
  type BasicCalculationCustomConfig,
} from '@/utils/basicCalculation'

defineOptions({
  name: 'BasicCalculationResult',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '练习结算',
  },
})

interface ResultRecord {
  seq: number
  expression: string
  answer: string
  correctAnswer: number
  correct: boolean
  usedSeconds: number
}

interface CalculationResult {
  id: string
  typeIndex: number
  typeTitle: string
  totalCount: number
  correctCount: number
  wrongCount: number
  totalSeconds: number
  keyboardOrder: string
  penEnabled: boolean
  customConfig?: BasicCalculationCustomConfig | null
  records: ResultRecord[]
}

const RESULT_STORAGE_KEY = 'basic_calculation_latest_result'
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const result = ref<CalculationResult | null>(null)

const accuracy = computed(() => {
  if (!result.value?.totalCount) {
    return 0
  }
  return Math.round((result.value.correctCount / result.value.totalCount) * 100)
})

const averageSeconds = computed(() => {
  if (!result.value?.totalCount) {
    return 0
  }
  return Math.round(result.value.totalSeconds / result.value.totalCount)
})

const performanceText = computed(() => {
  if (averageSeconds.value <= 18) {
    return '优秀'
  }
  if (averageSeconds.value <= 22) {
    return '良好'
  }
  if (averageSeconds.value <= 28) {
    return '合格'
  }
  return '继续练习'
})

function formatSeconds(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${minutes}:${String(rest).padStart(2, '0')}`
}

function goBack() {
  uni.redirectTo({ url: '/pages/basic-calculation/index' })
}

function restartPractice() {
  if (!result.value) {
    goBack()
    return
  }

  const params = [
    `typeIndex=${result.value.typeIndex}`,
    `count=${result.value.totalCount}`,
    `order=${result.value.keyboardOrder}`,
    `pen=${result.value.penEnabled ? 1 : 0}`,
  ]
  if (result.value.customConfig) {
    params.push('custom=1')
    params.push(`customConfig=${encodeBasicCalculationCustomConfig(result.value.customConfig)}`)
  }
  uni.redirectTo({ url: `/pages/basic-calculation/session/index?${params.join('&')}` })
}

onLoad((query) => {
  const cached = uni.getStorageSync(RESULT_STORAGE_KEY) as CalculationResult | null
  if (!cached || String(cached.id) !== String(query?.id || '')) {
    uni.showToast({ title: '结算数据已失效', icon: 'none' })
    setTimeout(goBack, 600)
    return
  }

  result.value = cached
})
</script>

<template>
  <view class="min-h-screen bg-[#F5F1EA] text-[#111827]">
    <view class="relative z-10 w-full bg-[#F5F1EA]" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white/90 text-[#475569] shadow-sm active:scale-95" @click="goBack">
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="text-lg font-bold tracking-widest">
          练习结算
        </text>
      </view>
    </view>

    <view v-if="result" class="px-4 pb-28 pt-3">
      <view class="rounded-xl bg-[#1F2937] px-5 py-5 text-[#F8FAFC] shadow-[0_16px_40px_-28px_rgba(31,41,55,0.7)]">
        <view class="text-[13px] text-[#FDE68A] font-bold">
          {{ result.typeTitle }}
        </view>
        <view class="mt-3 flex items-end justify-between">
          <view>
            <view class="text-[42px] font-black leading-none">
              {{ accuracy }}%
            </view>
            <view class="mt-2 text-[12px] text-[#CBD5E1]">
              正确率 · {{ performanceText }}
            </view>
          </view>
          <view class="rounded-md bg-white/10 px-3 py-2 text-right">
            <view class="text-[12px] text-[#CBD5E1]">
              总用时
            </view>
            <view class="mt-1 text-[18px] text-[#FDE68A] font-black">
              {{ formatSeconds(result.totalSeconds) }}
            </view>
          </view>
        </view>
      </view>

      <view class="mt-3 grid grid-cols-3 gap-2">
        <view class="rounded-md bg-white/80 px-3 py-3 text-center">
          <view class="text-[11px] text-[#94A3B8]">
            答对
          </view>
          <view class="mt-1 text-[18px] text-[#1F2937] font-black">
            {{ result.correctCount }}
          </view>
        </view>
        <view class="rounded-md bg-white/80 px-3 py-3 text-center">
          <view class="text-[11px] text-[#94A3B8]">
            答错
          </view>
          <view class="mt-1 text-[18px] text-[#B45309] font-black">
            {{ result.wrongCount }}
          </view>
        </view>
        <view class="rounded-md bg-white/80 px-3 py-3 text-center">
          <view class="text-[11px] text-[#94A3B8]">
            平均
          </view>
          <view class="mt-1 text-[18px] text-[#1F2937] font-black">
            {{ averageSeconds }}s
          </view>
        </view>
      </view>

      <view class="mt-5">
        <view class="mb-2 text-[15px] font-black">
          答题明细
        </view>
        <view class="flex flex-col gap-2">
          <view
            v-for="record in result.records"
            :key="record.seq"
            class="rounded-md bg-white/86 px-4 py-3 shadow-[0_2px_12px_-10px_rgba(31,41,55,0.22)]"
          >
            <view class="flex items-center justify-between gap-3">
              <view class="min-w-0 flex-1">
                <view class="text-[15px] font-black">
                  {{ record.seq }}. {{ record.expression }}
                </view>
                <view class="mt-1 text-[12px] text-[#64748B]">
                  你的答案：{{ record.answer }} · 正确答案：{{ record.correctAnswer }}
                </view>
              </view>
              <view class="shrink-0 text-right">
                <view class="rounded-full px-2.5 py-1 text-[11px] font-black" :class="record.correct ? 'bg-[#DBEAFE] text-[#1D4ED8]' : 'bg-[#FEF3C7] text-[#B45309]'">
                  {{ record.correct ? '正确' : '错误' }}
                </view>
                <view class="mt-1 text-[11px] text-[#94A3B8]">
                  {{ record.usedSeconds }}s
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>

    <view v-if="result" class="fixed bottom-0 left-0 right-0 bg-[#F5F1EA]/96 px-4 pb-[calc(env(safe-area-inset-bottom)+12px)] pt-3 shadow-[0_-10px_24px_-22px_rgba(31,41,55,0.55)]">
      <view class="grid grid-cols-2 gap-3">
        <view class="h-11 flex items-center justify-center rounded-md bg-[#E8EDF5] text-[15px] font-black active:scale-[0.99]" @click="goBack">
          返回配置
        </view>
        <view class="h-11 flex items-center justify-center rounded-md bg-[#F59E0B] text-[15px] text-[#111827] font-black active:scale-[0.99]" @click="restartPractice">
          再练一次
        </view>
      </view>
    </view>
  </view>
</template>
