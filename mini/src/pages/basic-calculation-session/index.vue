<script lang="ts" setup>
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { computed, nextTick, ref } from 'vue'
import {
  BASIC_CALCULATION_TYPES,
  BASIC_CALCULATION_CUSTOM_CONFIG_KEY,
  createBasicCalculationQuestions,
  decodeBasicCalculationCustomConfig,
  getKeyboardKeys,
  type BasicCalculationOrder,
  type BasicCalculationCustomConfig,
  type BasicCalculationQuestion,
} from '@/utils/basicCalculation'

defineOptions({
  name: 'BasicCalculationSession',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '计算练习',
  },
})

interface AnswerRecord {
  seq: number
  expression: string
  answer: string
  correctAnswer: number
  correct: boolean
  usedSeconds: number
}

const RESULT_STORAGE_KEY = 'basic_calculation_latest_result'

const windowInfo = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const statusBarHeight = windowInfo.statusBarHeight || 0

const typeIndex = ref(0)
const totalCount = ref(10)
const keyboardOrder = ref<BasicCalculationOrder>('asc')
const penEnabled = ref(false)
const customConfig = ref<BasicCalculationCustomConfig | null>(null)
const questions = ref<BasicCalculationQuestion[]>([])
const currentIndex = ref(0)
const answerInput = ref('')
const startedAt = ref(Date.now())
const questionStartedAt = ref(Date.now())
const nowTick = ref(Date.now())
const records = ref<AnswerRecord[]>([])
const answerInputFocused = ref(false)
const keyboardInputEnabled = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const currentType = computed(() => BASIC_CALCULATION_TYPES[typeIndex.value] || BASIC_CALCULATION_TYPES[0])
const currentQuestion = computed(() => questions.value[currentIndex.value])
const progressText = computed(() => `${Math.min(currentIndex.value + 1, totalCount.value)}/${totalCount.value}`)
const elapsedSeconds = computed(() => Math.max(0, Math.floor((nowTick.value - startedAt.value) / 1000)))
const questionSeconds = computed(() => Math.max(0, Math.floor((nowTick.value - questionStartedAt.value) / 1000)))
const numberKeys = computed(() => getKeyboardKeys(keyboardOrder.value))
const answeredCount = computed(() => records.value.length)
const correctCount = computed(() => records.value.filter(item => item.correct).length)

function toNumber(value: unknown, fallback: number) {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

function formatSeconds(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${minutes}:${String(rest).padStart(2, '0')}`
}

function resetQuestionTimer() {
  questionStartedAt.value = Date.now()
}

function focusAnswerInput() {
  keyboardInputEnabled.value = true
  answerInputFocused.value = false
  nextTick(() => {
    answerInputFocused.value = true
  })
}

function keepAnswerInputFocus() {
  if (!keyboardInputEnabled.value) {
    return
  }

  setTimeout(focusAnswerInput, 80)
}

function restartPractice() {
  questions.value = createBasicCalculationQuestions(typeIndex.value, totalCount.value, customConfig.value)
  currentIndex.value = 0
  answerInput.value = ''
  records.value = []
  startedAt.value = Date.now()
  resetQuestionTimer()
  keepAnswerInputFocus()
}

function goBack() {
  uni.navigateBack()
}

function appendKey(key: string) {
  if (answerInput.value.length >= 12) {
    return
  }
  if (key === '.' && answerInput.value.includes('.')) {
    return
  }
  if (key === '-' && answerInput.value.startsWith('-')) {
    return
  }
  if (key === '-' && answerInput.value.length > 0) {
    answerInput.value = `-${answerInput.value}`
    keepAnswerInputFocus()
    return
  }
  answerInput.value = `${answerInput.value}${key}`
  keepAnswerInputFocus()
}

function toggleSign() {
  if (!answerInput.value) {
    answerInput.value = '-'
    keepAnswerInputFocus()
    return
  }
  if (answerInput.value.startsWith('-')) {
    answerInput.value = answerInput.value.slice(1)
    keepAnswerInputFocus()
    return
  }
  answerInput.value = `-${answerInput.value}`
  keepAnswerInputFocus()
}

function clearAnswer() {
  answerInput.value = ''
  keepAnswerInputFocus()
}

function backspaceAnswer() {
  answerInput.value = answerInput.value.slice(0, -1)
  keepAnswerInputFocus()
}

function sanitizeAnswerInput(value: string) {
  let nextValue = ''
  let hasDot = false

  for (const char of value) {
    if (/\d/.test(char)) {
      nextValue = `${nextValue}${char}`
      continue
    }
    if (char === '.' && !hasDot) {
      hasDot = true
      nextValue = `${nextValue}${char}`
      continue
    }
    if (char === '-' && !nextValue) {
      nextValue = '-'
    }
  }

  return nextValue.slice(0, 12)
}

function handleAnswerInput(event: { detail?: { value?: string } }) {
  answerInput.value = sanitizeAnswerInput(String(event.detail?.value || ''))
  return answerInput.value
}

function handleAnswerFocus() {
  keyboardInputEnabled.value = true
  answerInputFocused.value = true
}

function handleAnswerBlur() {
  answerInputFocused.value = false
}

function isCorrectAnswer() {
  const userAnswer = Number(answerInput.value)
  const answer = Number(currentQuestion.value?.answer)
  if (!Number.isFinite(userAnswer)) {
    return false
  }
  return Math.abs(userAnswer - answer) < 0.01
}

function finishPractice() {
  const resultId = `${Date.now()}`
  uni.setStorageSync(RESULT_STORAGE_KEY, {
    id: resultId,
    typeIndex: typeIndex.value,
    typeTitle: currentType.value.title,
    totalCount: totalCount.value,
    correctCount: correctCount.value,
    wrongCount: Math.max(0, totalCount.value - correctCount.value),
    totalSeconds: elapsedSeconds.value,
    keyboardOrder: keyboardOrder.value,
    penEnabled: penEnabled.value,
    customConfig: customConfig.value,
    records: records.value,
  })
  uni.redirectTo({
    url: `/pages/basic-calculation-result/index?id=${resultId}`,
  })
}

function confirmAnswer() {
  if (!answerInput.value || answerInput.value === '-') {
    uni.showToast({ title: '请输入答案', icon: 'none' })
    return
  }

  const correct = isCorrectAnswer()
  const question = currentQuestion.value
  if (!question) {
    return
  }

  records.value = [
    ...records.value,
    {
      seq: currentIndex.value + 1,
      expression: question.expression,
      answer: answerInput.value,
      correctAnswer: question.answer,
      correct,
      usedSeconds: questionSeconds.value,
    },
  ]

  if (!correct) {
    uni.showToast({ title: `正确答案：${currentQuestion.value.answer}`, icon: 'none' })
  }

  if (currentIndex.value >= totalCount.value - 1) {
    setTimeout(finishPractice, correct ? 120 : 650)
    return
  }

  currentIndex.value += 1
  answerInput.value = ''
  resetQuestionTimer()
  keepAnswerInputFocus()
}

onLoad((query) => {
  typeIndex.value = Math.max(0, Math.min(BASIC_CALCULATION_TYPES.length - 1, toNumber(query?.typeIndex, 0)))
  totalCount.value = Math.max(1, Math.min(100, toNumber(query?.count, 10)))
  keyboardOrder.value = query?.order === 'desc' || query?.order === 'random' ? query.order : 'asc'
  penEnabled.value = String(query?.pen || '') === '1'
  if (String(query?.custom || '') === '1') {
    customConfig.value = decodeBasicCalculationCustomConfig(String(query?.customConfig || ''))
    uni.setStorageSync(BASIC_CALCULATION_CUSTOM_CONFIG_KEY, customConfig.value)
  }
  restartPractice()
  timer = setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
})

onUnload(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<template>
  <view class="min-h-screen bg-[#F5F1EA] text-[#111827]">
    <view class="relative z-10 w-full bg-[#F5F1EA]" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white/90 text-[#475569] shadow-sm active:scale-95" @click="goBack">
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="max-w-[220px] truncate text-lg font-bold tracking-widest">
          {{ currentType.title }}
        </text>
      </view>
    </view>

    <view class="px-4 pb-[320px] pt-2">
      <view class="flex items-center justify-between text-[15px] text-[#0F172A]">
        <text>{{ progressText }}</text>
        <view class="flex items-center gap-2">
          <text v-if="penEnabled" class="text-[24px] leading-none">🖊</text>
          <text>{{ formatSeconds(elapsedSeconds) }}</text>
        </view>
      </view>

      <view class="pt-12 text-center">
        <view class="text-[40px] text-[#020617] font-medium leading-tight">
          {{ currentQuestion?.expression }}
        </view>
        <view class="mt-6 text-[13px] text-[#334155]">
          合格：28s 良好：22s 优秀：18s
        </view>

        <view class="mt-5 flex items-center justify-between gap-4">
          <view class="h-[74px] w-[74px] flex items-center justify-center rounded-full bg-white/86 text-[14px] font-bold shadow-[0_8px_24px_-18px_rgba(31,41,55,0.5)] active:scale-95" @click="restartPractice">
            重开
          </view>
          <view
            class="min-w-0 flex-1 rounded-md border bg-white/70 px-3 py-3 text-center"
            :class="answerInputFocused ? 'border-[#F59E0B]' : 'border-[#E7E2D8]'"
            @click="focusAnswerInput"
          >
            <input
              class="h-8 w-full text-center text-[26px] text-[#111827] font-black"
              confirm-type="done"
              :adjust-position="false"
              :focus="answerInputFocused"
              :maxlength="12"
              placeholder="点这里可键盘输入"
              placeholder-style="color: #94A3B8; font-size: 15px; font-weight: 400;"
              type="text"
              :value="answerInput"
              @blur="handleAnswerBlur"
              @confirm="confirmAnswer"
              @focus="handleAnswerFocus"
              @input="handleAnswerInput"
            >
          </view>
          <view class="relative h-[74px] w-[74px] flex items-center justify-center rounded-full bg-white/86 text-[14px] font-bold shadow-[0_8px_24px_-18px_rgba(31,41,55,0.5)] active:scale-95" @click="confirmAnswer">
            <view class="absolute right-0 top-0 rounded-full bg-[#F59E0B] px-1.5 py-0.5 text-[10px] text-white">
              提
            </view>
            确定
          </view>
        </view>
      </view>
    </view>

    <view class="fixed bottom-0 left-0 right-0 bg-[#D9D3C8]/96 px-4 pb-[calc(env(safe-area-inset-bottom)+8px)] pt-3 shadow-[0_-10px_28px_-22px_rgba(31,41,55,0.55)]">
      <view class="grid grid-cols-3 gap-1">
        <view class="h-[62px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[22px] font-black active:scale-[0.98]" @click="toggleSign">
          ±
        </view>
        <view class="h-[62px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[22px] font-black active:scale-[0.98]" @click="clearAnswer">
          清空
        </view>
        <view class="h-[62px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[22px] font-black active:scale-[0.98]" @click="backspaceAnswer">
          退格
        </view>

        <view
          v-for="key in numberKeys"
          :key="key"
          class="h-[62px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[24px] text-[#334155] font-medium active:scale-[0.98]"
          @click="appendKey(key)"
        >
          {{ key }}
        </view>

        <view class="h-[62px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[24px] text-[#334155] font-medium active:scale-[0.98]" @click="appendKey('.')">
          .
        </view>
        <view class="h-[62px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[24px] text-[#334155] font-medium active:scale-[0.98]" @click="appendKey('0')">
          0
        </view>
        <view class="h-[62px] flex items-center justify-center rounded-md bg-[#F59E0B] text-[22px] text-[#111827] font-black active:scale-[0.98]" @click="confirmAnswer">
          确定
        </view>
      </view>
    </view>
  </view>
</template>
