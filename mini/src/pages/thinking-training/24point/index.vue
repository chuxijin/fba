<script lang="ts" setup>
import { ref, computed } from 'vue'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

type GameState = 'ready' | 'playing' | 'solved' | 'skipped'

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const state = ref<GameState>('ready')
const cards = ref<number[]>([])
const expression = ref('')
const round = ref(0)
const solved = ref(0)
const skipped = ref(0)
const startTime = ref(0)
const elapsed = ref(0)
const feedback = ref<string | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

// 预生成有解的题目
function hasSolution(nums: number[]): boolean {
  return solve24(nums).length > 0
}

function solve24(nums: number[]): string[] {
  const results: string[] = []
  const eps = 1e-6

  function dfs(arr: number[], exprs: string[]) {
    if (arr.length === 1) {
      if (Math.abs(arr[0] - 24) < eps) {
        results.push(exprs[0])
      }
      return
    }
    if (results.length > 0) return // 找到一个解即可

    for (let i = 0; i < arr.length; i++) {
      for (let j = 0; j < arr.length; j++) {
        if (i === j) continue
        const nextArr: number[] = []
        const nextExprs: string[] = []
        for (let k = 0; k < arr.length; k++) {
          if (k !== i && k !== j) {
            nextArr.push(arr[k])
            nextExprs.push(exprs[k])
          }
        }

        const ops: Array<{ op: string, val: number, expr: string }> = [
          { op: '+', val: arr[i] + arr[j], expr: `(${exprs[i]}+${exprs[j]})` },
          { op: '-', val: arr[i] - arr[j], expr: `(${exprs[i]}-${exprs[j]})` },
          { op: '×', val: arr[i] * arr[j], expr: `(${exprs[i]}×${exprs[j]})` },
        ]
        if (Math.abs(arr[j]) > eps) {
          ops.push({ op: '÷', val: arr[i] / arr[j], expr: `(${exprs[i]}÷${exprs[j]})` })
        }

        for (const { val, expr } of ops) {
          dfs([...nextArr, val], [...nextExprs, expr])
          if (results.length > 0) return
        }
      }
    }
  }

  dfs(nums, nums.map(String))
  return results
}

function generateCards(): number[] {
  let attempt = 0
  while (attempt < 200) {
    const nums = Array.from({ length: 4 }, () => Math.floor(Math.random() * 13) + 1)
    if (hasSolution(nums)) return nums
    attempt++
  }
  return [1, 2, 3, 4] // fallback
}

function startGame() {
  round.value = 0
  solved.value = 0
  skipped.value = 0
  elapsed.value = 0
  startTime.value = Date.now()

  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    elapsed.value = Date.now() - startTime.value
  }, 100)

  nextRound()
}

function nextRound() {
  round.value++
  cards.value = generateCards()
  expression.value = ''
  feedback.value = null
  state.value = 'playing'
}

function handleOperator(op: string) {
  if (state.value !== 'playing') return
  expression.value += op
}

function handleNumber(num: number) {
  if (state.value !== 'playing') return
  expression.value += String(num)
}

function handleClear() {
  expression.value = ''
}

function handleBackspace() {
  expression.value = expression.value.slice(0, -1)
}

function evaluateExpression(expr: string): number | null {
  try {
    // 把 × → *, ÷ → /
    const sanitized = expr.replace(/×/g, '*').replace(/÷/g, '/')
    // 安全检查：只允许数字和运算符
    if (!/^[\d+\-*/().]+$/.test(sanitized)) return null
    // eslint-disable-next-line no-eval
    const result = Function(`"use strict"; return (${sanitized})`)()
    return typeof result === 'number' && isFinite(result) ? result : null
  }
  catch {
    return null
  }
}

function checkUsedNumbers(expr: string): boolean {
  const usedNums = expr.match(/\d+/g)?.map(Number) || []
  if (usedNums.length !== 4) return false
  const sortedUsed = [...usedNums].sort((a, b) => a - b)
  const sortedCards = [...cards.value].sort((a, b) => a - b)
  return sortedUsed.every((n, i) => n === sortedCards[i])
}

function submitExpression() {
  if (state.value !== 'playing' || !expression.value.trim()) return

  if (!checkUsedNumbers(expression.value)) {
    feedback.value = '请恰好使用这4个数字各一次'
    setTimeout(() => { feedback.value = null }, 2000)
    return
  }

  const result = evaluateExpression(expression.value)
  if (result === null) {
    feedback.value = '表达式有误，请检查'
    setTimeout(() => { feedback.value = null }, 2000)
    return
  }

  if (Math.abs(result - 24) < 1e-6) {
    solved.value++
    state.value = 'solved'
  }
  else {
    feedback.value = `= ${result}，不等于24`
    setTimeout(() => { feedback.value = null }, 2000)
  }
}

function skipCard() {
  skipped.value++
  const solutions = solve24(cards.value)
  state.value = 'skipped'
  feedback.value = solutions.length ? `参考解: ${solutions[0]}` : '无解'
}

function formatTime(ms: number): string {
  return (ms / 1000).toFixed(1)
}

function goBack() {
  if (timer) clearInterval(timer)
  uni.navigateBack()
}

function cardDisplay(n: number): string {
  if (n === 1) return 'A'
  if (n === 11) return 'J'
  if (n === 12) return 'Q'
  if (n === 13) return 'K'
  return String(n)
}
</script>

<template>
  <view class="min-h-screen bg-[#F5F1EA] text-[#111827]">
    <view class="relative z-10 w-full bg-[#F5F1EA]" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white/90 text-[#475569] shadow-sm active:scale-95" @click="goBack">
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="text-lg font-bold tracking-widest">24点</text>
      </view>
    </view>

    <view class="px-4 pb-[220px] pt-3">
      <!-- 统计 -->
      <view v-if="state !== 'ready'" class="mb-4 flex items-center justify-between px-1">
        <text class="text-[14px] text-[#64748B] font-bold">第 {{ round }} 题</text>
        <view class="flex gap-3">
          <text class="text-[13px] text-[#059669] font-bold">解出 {{ solved }}</text>
          <text class="text-[13px] text-[#94A3B8] font-bold">跳过 {{ skipped }}</text>
        </view>
      </view>

      <!-- 卡牌展示 -->
      <view v-if="state !== 'ready'" class="mb-5 flex justify-center gap-3">
        <view
          v-for="(card, i) in cards"
          :key="i"
          class="h-20 w-14 flex items-center justify-center rounded-xl bg-white text-[28px] text-[#1E293B] font-black shadow-md active:scale-95"
          @click="handleNumber(card)"
        >
          {{ cardDisplay(card) }}
        </view>
      </view>

      <!-- 表达式输入 -->
      <view v-if="state === 'playing'" class="mb-4">
        <view class="min-h-[52px] flex items-center rounded-xl bg-white/90 px-4 py-3 shadow-sm">
          <text class="flex-1 text-[20px] font-black tabular-nums" :class="expression ? 'text-[#1E293B]' : 'text-[#CBD5E1]'">
            {{ expression || '点击数字和运算符组合' }}
          </text>
          <view v-if="expression" class="i-carbon-close ml-2 text-[18px] text-[#94A3B8]" @click="handleClear" />
        </view>
        <view v-if="feedback" class="mt-2 text-center text-[13px] text-[#EF4444] font-bold">
          {{ feedback }}
        </view>
      </view>

      <!-- 解出 -->
      <view v-if="state === 'solved'" class="mt-4 rounded-2xl bg-white/90 px-5 py-5 text-center shadow-sm">
        <text class="text-[20px]">🎉</text>
        <view class="mt-1 text-[16px] font-black">答对了！</view>
        <view class="mt-2 text-[14px] text-[#64748B]">{{ expression }} = 24</view>
        <view
          class="mt-4 mx-auto h-11 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[15px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="nextRound"
        >
          下一题
        </view>
      </view>

      <!-- 跳过 -->
      <view v-if="state === 'skipped'" class="mt-4 rounded-2xl bg-white/90 px-5 py-5 text-center shadow-sm">
        <view class="text-[14px] text-[#64748B]">{{ feedback }}</view>
        <view
          class="mt-4 mx-auto h-11 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[15px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="nextRound"
        >
          下一题
        </view>
      </view>

      <!-- 准备 -->
      <view v-if="state === 'ready'" class="mt-8 text-center">
        <view class="mx-auto mb-6 text-[48px]">🃏</view>
        <view class="mb-2 text-[18px] font-black">24点游戏</view>
        <view class="mb-1 text-[14px] text-[#475569] leading-relaxed">用 + - × ÷ 和括号</view>
        <view class="mb-6 text-[14px] text-[#475569] leading-relaxed">让4个数字运算结果等于24</view>
        <view
          class="mx-auto h-12 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[16px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="startGame"
        >
          开始挑战
        </view>
      </view>
    </view>

    <!-- 固定底部操作键盘 -->
    <view v-if="state === 'playing'" class="fixed bottom-0 left-0 right-0 bg-[#D9D3C8]/96 px-4 pb-[calc(env(safe-area-inset-bottom)+8px)] pt-3 shadow-[0_-10px_28px_-22px_rgba(31,41,55,0.55)]">
      <view class="grid grid-cols-6 gap-1 mb-1">
        <view
          v-for="op in ['+', '-', '×', '÷', '(', ')']"
          :key="op"
          class="h-[52px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[22px] font-black active:scale-[0.98]"
          @click="handleOperator(op)"
        >
          {{ op }}
        </view>
      </view>
      <view class="grid grid-cols-3 gap-1">
        <view class="h-[52px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[20px] font-black active:scale-[0.98]" @click="handleBackspace">
          退格
        </view>
        <view class="h-[52px] flex items-center justify-center rounded-md bg-[#F59E0B] text-[20px] text-[#111827] font-black active:scale-[0.98]" @click="submitExpression">
          = 24?
        </view>
        <view class="h-[52px] flex items-center justify-center rounded-md bg-white/80 text-[20px] text-[#94A3B8] font-black active:scale-[0.98]" @click="skipCard">
          跳过
        </view>
      </view>
    </view>
  </view>
</template>
