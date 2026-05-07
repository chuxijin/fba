<script lang="ts" setup>
import { ref, computed } from 'vue'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

type GameState = 'ready' | 'playing' | 'won'

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const DIGITS = 4

const state = ref<GameState>('ready')
const secretNumber = ref<number[]>([])
const currentInput = ref('')
const guesses = ref<Array<{ digits: number[], bulls: number, cows: number }>>([])
const maxGuesses = 10

const isWon = computed(() => state.value === 'won')
const attemptsLeft = computed(() => maxGuesses - guesses.value.length)

function generateSecret(): number[] {
  const digits = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
  // 洗牌
  for (let i = digits.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[digits[i], digits[j]] = [digits[j], digits[i]]
  }
  // 首位不为0
  const result = digits.slice(0, DIGITS)
  if (result[0] === 0) {
    const nonZeroIdx = result.findIndex(d => d !== 0)
    ;[result[0], result[nonZeroIdx]] = [result[nonZeroIdx], result[0]]
  }
  return result
}

function evaluate(guess: number[], secret: number[]): { bulls: number, cows: number } {
  let bulls = 0
  let cows = 0
  for (let i = 0; i < DIGITS; i++) {
    if (guess[i] === secret[i]) {
      bulls++
    }
    else if (secret.includes(guess[i])) {
      cows++
    }
  }
  return { bulls, cows }
}

function startGame() {
  secretNumber.value = generateSecret()
  guesses.value = []
  currentInput.value = ''
  state.value = 'playing'
}

function handleKeyInput(key: string) {
  if (state.value !== 'playing') return
  if (key === 'del') {
    currentInput.value = currentInput.value.slice(0, -1)
    return
  }
  if (currentInput.value.length < DIGITS) {
    // 不允许重复数字
    if (currentInput.value.includes(key)) {
      uni.showToast({ title: '不能有重复数字', icon: 'none', duration: 1000 })
      return
    }
    // 首位不能为0
    if (currentInput.value.length === 0 && key === '0') {
      uni.showToast({ title: '首位不能为0', icon: 'none', duration: 1000 })
      return
    }
    currentInput.value += key
  }
}

function submitGuess() {
  if (state.value !== 'playing') return
  if (currentInput.value.length !== DIGITS) {
    uni.showToast({ title: `请输入${DIGITS}位数字`, icon: 'none' })
    return
  }

  const guessDigits = currentInput.value.split('').map(Number)
  const { bulls, cows } = evaluate(guessDigits, secretNumber.value)

  guesses.value.push({ digits: guessDigits, bulls, cows })
  currentInput.value = ''

  if (bulls === DIGITS) {
    state.value = 'won'
    return
  }

  if (guesses.value.length >= maxGuesses) {
    state.value = 'won' // 用完次数也结束
  }
}

function goBack() {
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
        <text class="text-lg font-bold tracking-widest">猜数字</text>
      </view>
    </view>

    <view class="px-4 pb-[240px] pt-3">
      <!-- 准备 -->
      <view v-if="state === 'ready'" class="mt-8 text-center">
        <view class="mx-auto mb-6 text-[48px]">🎯</view>
        <view class="mb-2 text-[18px] font-black">猜数字 (Bulls & Cows)</view>
        <view class="mb-1 text-[14px] text-[#475569] leading-relaxed">
          系统随机生成一个 {{ DIGITS }} 位不重复数字
        </view>
        <view class="mb-1 text-[14px] text-[#475569] leading-relaxed">
          <text class="text-[#059669] font-bold">A</text> = 数字和位置都对
        </view>
        <view class="mb-6 text-[14px] text-[#475569] leading-relaxed">
          <text class="text-[#F59E0B] font-bold">B</text> = 数字对但位置不对
        </view>
        <view
          class="mx-auto h-12 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[16px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="startGame"
        >
          开始猜
        </view>
      </view>

      <!-- 游戏中 -->
      <view v-if="state === 'playing' || state === 'won'">
        <!-- 猜测历史 -->
        <view class="mb-4">
          <view v-if="!guesses.length" class="text-center text-[13px] text-[#94A3B8] py-4">
            请输入你的第一次猜测
          </view>
          <view
            v-for="(guess, i) in guesses"
            :key="i"
            class="mb-2 flex items-center rounded-xl bg-white/90 px-4 py-3 shadow-sm"
          >
            <text class="mr-2 text-[12px] text-[#94A3B8] font-bold w-6">{{ i + 1 }}</text>
            <view class="flex flex-1 gap-2">
              <view
                v-for="(d, j) in guess.digits"
                :key="j"
                class="h-9 w-9 flex items-center justify-center rounded-lg bg-[#F1F5F9] text-[18px] font-black"
              >
                {{ d }}
              </view>
            </view>
            <view class="flex items-center gap-3 ml-3">
              <view class="flex items-center gap-1">
                <text class="text-[18px] text-[#059669] font-black">{{ guess.bulls }}</text>
                <text class="text-[12px] text-[#059669] font-bold">A</text>
              </view>
              <view class="flex items-center gap-1">
                <text class="text-[18px] text-[#F59E0B] font-black">{{ guess.cows }}</text>
                <text class="text-[12px] text-[#F59E0B] font-bold">B</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 结果 -->
        <view v-if="state === 'won'" class="mb-4 rounded-2xl bg-white/90 px-5 py-5 text-center shadow-sm">
          <view v-if="guesses.length && guesses[guesses.length - 1].bulls === DIGITS">
            <text class="text-[18px] font-black">🎉 猜对了！</text>
            <view class="mt-2 text-[14px] text-[#64748B]">
              用了 {{ guesses.length }} 次猜中
            </view>
          </view>
          <view v-else>
            <text class="text-[18px] font-black">😅 次数用完了</text>
            <view class="mt-2 text-[14px] text-[#64748B]">
              答案是 <text class="text-[#1E293B] font-black text-[18px] tracking-widest">{{ secretNumber.join('') }}</text>
            </view>
          </view>
          <view class="mt-4 flex gap-3">
            <view class="flex-1 h-11 flex items-center justify-center rounded-xl bg-[#E8EDF5] text-[15px] font-black active:scale-95" @click="state = 'ready'">
              返回
            </view>
            <view class="flex-1 h-11 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[15px] text-[#111827] font-black shadow-lg active:scale-95" @click="startGame">
              再来一局
            </view>
          </view>
        </view>

        <!-- 输入显示 -->
        <view v-if="state === 'playing'">
          <view class="mb-2 flex items-center justify-between px-1">
            <text class="text-[13px] text-[#94A3B8]">剩余 {{ attemptsLeft }} 次机会</text>
          </view>
          <view class="flex justify-center gap-3">
            <view
              v-for="i in DIGITS"
              :key="i"
              class="h-14 w-14 flex items-center justify-center rounded-xl text-[24px] font-black"
              :class="currentInput[i - 1] ? 'bg-white shadow-sm text-[#1E293B]' : 'bg-[#E2E8F0] text-[#CBD5E1]'"
            >
              {{ currentInput[i - 1] || '_' }}
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 固定底部键盘 -->
    <view v-if="state === 'playing'" class="fixed bottom-0 left-0 right-0 bg-[#D9D3C8]/96 px-4 pb-[calc(env(safe-area-inset-bottom)+8px)] pt-3 shadow-[0_-10px_28px_-22px_rgba(31,41,55,0.55)]">
      <view class="grid grid-cols-5 gap-1">
        <view
          v-for="n in [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]"
          :key="n"
          class="h-[62px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[24px] text-[#334155] font-medium active:scale-[0.98]"
          :class="currentInput.includes(String(n)) ? 'opacity-30' : ''"
          @click="handleKeyInput(String(n))"
        >
          {{ n }}
        </view>
      </view>
      <view class="mt-1 grid grid-cols-2 gap-1">
        <view class="h-[52px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[22px] font-black active:scale-[0.98]" @click="handleKeyInput('del')">
          退格
        </view>
        <view class="h-[52px] flex items-center justify-center rounded-md bg-[#F59E0B] text-[22px] text-[#111827] font-black active:scale-[0.98]" @click="submitGuess">
          确定
        </view>
      </view>
    </view>
  </view>
</template>
