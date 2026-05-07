<script lang="ts" setup>
import { ref, computed } from 'vue'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

type GameState = 'ready' | 'flashing' | 'inputting' | 'result' | 'finished'

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const TOTAL_ROUNDS = 10

const state = ref<GameState>('ready')
const level = ref(3) // 起始：3个数相加
const numbers = ref<number[]>([])
const correctAnswer = ref(0)
const userInput = ref('')
const currentFlashIndex = ref(-1)
const round = ref(0)
const correct = ref(0)
const maxLevel = ref(3)
const roundResult = ref<'correct' | 'wrong' | null>(null)
let flashTimer: ReturnType<typeof setInterval> | null = null

const flashSpeed = computed(() => Math.max(400, 1000 - level.value * 50)) // 速度随级别加快

function generateNumbers(count: number): number[] {
  const result: number[] = []
  for (let i = 0; i < count; i++) {
    // 数值范围随级别增大
    const maxVal = level.value <= 4 ? 9 : level.value <= 6 ? 19 : 49
    result.push(Math.floor(Math.random() * maxVal) + 1)
  }
  return result
}

function startGame() {
  level.value = 3
  round.value = 0
  correct.value = 0
  maxLevel.value = 3
  roundResult.value = null
  nextRound()
}

function nextRound() {
  round.value++
  if (round.value > TOTAL_ROUNDS) {
    state.value = 'finished'
    return
  }

  userInput.value = ''
  roundResult.value = null
  numbers.value = generateNumbers(level.value)
  correctAnswer.value = numbers.value.reduce((sum, n) => sum + n, 0)
  currentFlashIndex.value = -1
  state.value = 'flashing'

  // 开始逐个闪现
  let idx = 0
  if (flashTimer) clearInterval(flashTimer)
  flashTimer = setInterval(() => {
    if (idx < numbers.value.length) {
      currentFlashIndex.value = idx
      idx++
    }
    else {
      if (flashTimer) clearInterval(flashTimer)
      flashTimer = null
      currentFlashIndex.value = -1
      state.value = 'inputting'
    }
  }, flashSpeed.value)
}

function submitAnswer() {
  if (state.value !== 'inputting') return

  const answer = parseInt(userInput.value, 10)
  const isCorrect = answer === correctAnswer.value

  if (isCorrect) {
    correct.value++
    roundResult.value = 'correct'
    level.value = Math.min(level.value + 1, 15)
    maxLevel.value = Math.max(maxLevel.value, level.value)
  }
  else {
    roundResult.value = 'wrong'
    level.value = Math.max(level.value - 1, 2)
  }

  state.value = 'result'
}

function continueGame() {
  nextRound()
}

function handleKeyInput(key: string) {
  if (state.value !== 'inputting') return
  if (key === 'del') {
    userInput.value = userInput.value.slice(0, -1)
    return
  }
  if (userInput.value.length < 6) {
    userInput.value += key
  }
}

function goBack() {
  if (flashTimer) clearInterval(flashTimer)
  uni.navigateBack()
}
</script>

<template>
  <view class="min-h-screen bg-[#F5F1EA] text-[#111827]">
    <view class="relative z-10 w-full bg-[#F5F1EA]" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white/90 text-[#475569] shadow-sm active:scale-95" @click="goBack">
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="text-lg font-bold tracking-widest">闪电心算</text>
      </view>
    </view>

    <view class="px-4 pb-[280px] pt-3">
      <!-- 进度 -->
      <view v-if="state !== 'ready' && state !== 'finished'" class="mb-4 flex items-center justify-between px-1">
        <text class="text-[14px] text-[#64748B] font-bold">第 {{ round }}/{{ TOTAL_ROUNDS }} 轮</text>
        <text class="text-[14px] text-[#F59E0B] font-bold">{{ level }} 个数相加</text>
      </view>

      <!-- 闪现数字 -->
      <view v-if="state === 'flashing'" class="mt-12 text-center">
        <view class="mb-4 text-[13px] text-[#94A3B8]">心算以下数字之和</view>
        <view class="mx-auto h-40 w-40 flex items-center justify-center rounded-2xl bg-white/90 shadow-lg">
          <text v-if="currentFlashIndex >= 0" class="text-[56px] font-black text-[#1E293B] tabular-nums">
            {{ numbers[currentFlashIndex] }}
          </text>
        </view>
        <view class="mt-4 flex justify-center gap-1.5">
          <view
            v-for="(_, i) in numbers"
            :key="i"
            class="h-2 w-2 rounded-full transition-all"
            :class="i <= currentFlashIndex ? 'bg-[#F59E0B]' : 'bg-[#E2E8F0]'"
          />
        </view>
      </view>

      <!-- 输入区显示 -->
      <view v-if="state === 'inputting'" class="mt-6 text-center">
        <view class="mb-4 text-[13px] text-[#94A3B8]">请输入所有数字的总和</view>
        <view class="mx-auto min-h-[64px] flex items-center justify-center rounded-2xl bg-white/90 px-6 py-4 shadow-sm">
          <text class="text-[36px] font-black tabular-nums" :class="userInput ? 'text-[#1E293B]' : 'text-[#CBD5E1]'">
            {{ userInput || '?' }}
          </text>
        </view>
      </view>

      <!-- 单轮结果 -->
      <view v-if="state === 'result'" class="mt-8 text-center">
        <view class="mx-auto rounded-2xl bg-white/90 px-6 py-6 shadow-sm">
          <text class="text-[24px]">{{ roundResult === 'correct' ? '⚡' : '❌' }}</text>
          <view class="mt-2 text-[16px] font-black">
            {{ roundResult === 'correct' ? '算对了！' : '算错了' }}
          </view>
          <view class="mt-3 text-[14px] text-[#64748B]">
            {{ numbers.join(' + ') }} = <text class="text-[#1E293B] font-bold">{{ correctAnswer }}</text>
          </view>
          <view v-if="roundResult === 'wrong'" class="mt-1 text-[14px] text-[#EF4444]">
            你的答案: <text class="font-bold">{{ userInput || '(未输入)' }}</text>
          </view>
        </view>
        <view
          class="mt-5 mx-auto h-11 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[15px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="continueGame"
        >
          {{ round >= TOTAL_ROUNDS ? '查看结果' : '下一轮' }}
        </view>
      </view>

      <!-- 准备 -->
      <view v-if="state === 'ready'" class="mt-8 text-center">
        <view class="mx-auto mb-6 text-[48px]">⚡</view>
        <view class="mb-2 text-[18px] font-black">闪电心算</view>
        <view class="mb-1 text-[14px] text-[#475569] leading-relaxed">数字会逐个闪现在屏幕上</view>
        <view class="mb-6 text-[14px] text-[#475569] leading-relaxed">在心中累加，最后输入总和</view>
        <view
          class="mx-auto h-12 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[16px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="startGame"
        >
          开始训练
        </view>
      </view>

      <!-- 最终结果 -->
      <view v-if="state === 'finished'" class="mt-6">
        <view class="rounded-2xl bg-white/90 px-5 py-6 text-center shadow-sm">
          <text class="text-[18px] font-black">⚡ 训练完成!</text>
          <view class="mt-4 grid grid-cols-3 gap-4">
            <view>
              <view class="text-[24px] text-[#059669] font-black">{{ correct }}</view>
              <view class="text-[12px] text-[#64748B]">正确</view>
            </view>
            <view>
              <view class="text-[24px] text-[#EF4444] font-black">{{ TOTAL_ROUNDS - correct }}</view>
              <view class="text-[12px] text-[#64748B]">错误</view>
            </view>
            <view>
              <view class="text-[24px] text-[#F59E0B] font-black">{{ maxLevel }}</view>
              <view class="text-[12px] text-[#64748B]">最多累加</view>
            </view>
          </view>
        </view>
        <view class="mt-5 flex gap-3">
          <view class="flex-1 h-11 flex items-center justify-center rounded-xl bg-[#E8EDF5] text-[15px] font-black active:scale-95" @click="state = 'ready'">
            返回
          </view>
          <view class="flex-1 h-11 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[15px] text-[#111827] font-black shadow-lg active:scale-95" @click="startGame">
            再来一次
          </view>
        </view>
      </view>
    </view>

    <!-- 固定底部键盘 -->
    <view v-if="state === 'inputting'" class="fixed bottom-0 left-0 right-0 bg-[#D9D3C8]/96 px-4 pb-[calc(env(safe-area-inset-bottom)+8px)] pt-3 shadow-[0_-10px_28px_-22px_rgba(31,41,55,0.55)]">
      <view class="grid grid-cols-3 gap-1">
        <view
          v-for="n in [1, 2, 3, 4, 5, 6, 7, 8, 9]"
          :key="n"
          class="h-[62px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[24px] text-[#334155] font-medium active:scale-[0.98]"
          @click="handleKeyInput(String(n))"
        >
          {{ n }}
        </view>
        <view class="h-[62px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[22px] font-black active:scale-[0.98]" @click="handleKeyInput('del')">
          退格
        </view>
        <view class="h-[62px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[24px] text-[#334155] font-medium active:scale-[0.98]" @click="handleKeyInput('0')">
          0
        </view>
        <view class="h-[62px] flex items-center justify-center rounded-md bg-[#F59E0B] text-[22px] text-[#111827] font-black active:scale-[0.98]" @click="submitAnswer">
          确定
        </view>
      </view>
    </view>
  </view>
</template>
