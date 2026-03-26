<script lang="ts" setup>
import { computed } from 'vue'

defineOptions({
  name: 'PracticeStartModal',
})

const props = defineProps<{
  modelValue: boolean
  mode: PracticeMode
  target: PracticeStartTarget | null
  checkingLatest?: boolean
  starting?: boolean
  latestSession?: LatestSessionBrief | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'start': []
  'restart': []
  'continue': []
}>()

type PracticeMode = 'exam' | 'practice' | 'memorize'

interface PracticeStartTarget {
  id: number
  name: string
  questionCount: number
}

interface LatestSessionBrief {
  id: number
  status: string
  total_count: number
  completed_count: number
}

const modeOptions: Array<{
  value: PracticeMode
  title: string
  tip: string
  desc: string
}> = [
  {
    value: 'practice',
    title: '刷题模式',
    tip: '做完一题看一题解析',
    desc: '适合日常训练和查漏补缺。',
  },
  {
    value: 'exam',
    title: '考试模式',
    tip: '整套做完后统一交卷',
    desc: '更适合模拟正式考试节奏。',
  },
  {
    value: 'memorize',
    title: '背题模式',
    tip: '答案解析默认可见',
    desc: '适合快速过题和记忆知识点。',
  },
]

const currentModeOption = computed(() => modeOptions.find(item => item.value === props.mode) || modeOptions[0])

const hasLatestInProgress = computed(() => props.latestSession?.status === 'in_progress')

function closeModal() {
  emit('update:modelValue', false)
}
</script>

<template>
  <wd-popup
    :model-value="modelValue"
    position="bottom"
    custom-class="rounded-t-3xl overflow-hidden bg-[#FAFAFA]"
    safe-area-inset-bottom
    :z-index="999999"
    custom-style="height:auto;max-height:82vh;"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <view class="relative px-5 pb-4 pt-5">
      <view
        class="absolute right-4 top-4 z-20 h-8 w-8 flex items-center justify-center rounded-full bg-slate-100/60 text-slate-400 transition-transform active:scale-90"
        @click="closeModal"
      >
        <view class="i-carbon-close text-[18px]" />
      </view>

      <view class="flex items-start justify-between gap-3">
        <view class="min-w-0">
          <view class="text-[18px] text-[#14532D] font-black">
            开始刷题
          </view>
          <view class="mt-1 text-[12px] text-[#6B7280]">
            将按设置里的默认模式开始这套题
          </view>
        </view>
      </view>

      <view
        v-if="target"
        class="mt-4 rounded-[24px] from-[#10B981] to-[#047857] bg-gradient-to-br px-4 py-4 text-white shadow-[0_14px_30px_rgba(16,185,129,0.22)]"
      >
        <view class="text-[12px] text-white/75">
          当前题库
        </view>
        <view class="mt-1 break-all text-[18px] font-black leading-[1.35]">
          {{ target.name }}
        </view>
        <view class="mt-2 inline-flex items-center rounded-full bg-white/16 px-3 py-1 text-[11px] text-white/90">
          共 {{ target.questionCount }} 题
        </view>
      </view>

      <view class="mt-4 overflow-hidden border border-white/80 rounded-[24px] bg-white/88 shadow-[0_10px_28px_rgba(148,163,184,0.10)]">
        <view class="px-4 py-4">
          <view class="flex items-center justify-between gap-3">
            <view>
              <view class="text-[14px] text-[#1E293B] font-bold">
                默认刷题模式
              </view>
              <view class="mt-1 text-[11px] text-[#94A3B8]">
                前往设置页可修改默认模式
              </view>
            </view>
            <view class="shrink-0 rounded-full bg-[#ECFDF5] px-3 py-1.5 text-[12px] text-[#059669] font-bold">
              {{ currentModeOption.title }}
            </view>
          </view>

          <view class="mt-3 border border-[#ECFDF5] rounded-[20px] bg-[#F8FAFC] px-4 py-4">
            <view class="text-[14px] text-[#14532D] font-bold">
              {{ currentModeOption.tip }}
            </view>
            <view class="mt-1.5 text-[12px] text-[#64748B] leading-[1.7]">
              {{ currentModeOption.desc }}
            </view>
          </view>
        </view>
      </view>

      <view
        v-if="hasLatestInProgress && latestSession"
        class="mt-4 border border-[#FDE68A] rounded-[24px] bg-[#FFFBEB] px-4 py-4 shadow-[0_8px_20px_rgba(245,158,11,0.10)]"
      >
        <view class="text-[14px] text-[#92400E] font-bold">
          发现未完成进度
        </view>
        <view class="mt-1.5 text-[12px] text-[#B45309] leading-[1.7]">
          已完成 {{ latestSession.completed_count }} / {{ latestSession.total_count }} 题，可以继续上次，也可以重新开始。
        </view>

        <view class="mt-4 flex gap-3">
          <view
            class="h-11 flex flex-1 items-center justify-center border border-[#FCD34D] rounded-full bg-white text-[14px] text-[#B45309] font-bold active:scale-[0.98]"
            @click="emit('continue')"
          >
            继续上次
          </view>
          <view
            class="h-11 flex flex-1 items-center justify-center rounded-full bg-[#F59E0B] text-[14px] text-white font-bold active:scale-[0.98]"
            @click="emit('restart')"
          >
            {{ starting ? '创建中...' : '重新开始' }}
          </view>
        </view>
      </view>

      <view
        v-else
        class="mt-4 border border-white/70 rounded-[20px] bg-white/82 px-4 py-3 text-[12px] text-[#64748B] shadow-sm"
      >
        {{ checkingLatest ? '正在检查是否存在未完成练习...' : '将按当前模式创建新的练习会话。' }}
      </view>

      <view
        v-if="!hasLatestInProgress"
        class="mt-4 h-12 flex items-center justify-center rounded-full bg-[#059669] text-[15px] text-white font-black shadow-[0_16px_28px_rgba(5,150,105,0.22)] transition-transform active:scale-[0.98]"
        @click="emit('start')"
      >
        {{ starting ? '开始中...' : '开始刷题' }}
      </view>

      <view class="h-safe-area-bottom w-full" />
    </view>
  </wd-popup>
</template>
