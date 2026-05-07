<script lang="ts" setup>
import { ref, computed } from 'vue'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

type GameState = 'ready' | 'showing' | 'playing' | 'result' | 'finished'

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const GRID_SIZE = 5 // 5×5 方格
const TOTAL_CELLS = GRID_SIZE * GRID_SIZE
const ROUNDS_PER_GAME = 10

interface DifficultyOption {
  label: string
  count: number // 闪现数字个数
  showTime: number // 展示时长 ms
}

const DIFFICULTIES: DifficultyOption[] = [
  { label: '入门', count: 3, showTime: 3000 },
  { label: '简单', count: 4, showTime: 3000 },
  { label: '一般', count: 5, showTime: 2500 },
  { label: '提高', count: 6, showTime: 2500 },
  { label: '困难', count: 7, showTime: 2000 },
  { label: '最强大脑', count: 8, showTime: 2000 },
  { label: 'yyds', count: 9, showTime: 1500 },
]

const state = ref<GameState>('ready')
const difficultyIndex = ref(1)
const round = ref(0)
const correct = ref(0)

// 当前轮数据
const numberCells = ref<Map<number, number>>(new Map()) // cellIndex -> number
const nextTarget = ref(1) // 下一个要点击的数字（从小到大）
const sortedNumbers = ref<number[]>([]) // 排序后的数字列表
const clickedCells = ref<Set<number>>(new Set()) // 已正确点击的格子
const wrongCell = ref<number | null>(null) // 点错的格子
const roundCorrect = ref(true) // 当前轮是否全对
let showTimer: ReturnType<typeof setTimeout> | null = null

const currentDifficulty = computed(() => DIFFICULTIES[difficultyIndex.value])
const currentTargetValue = computed(() => sortedNumbers.value[nextTarget.value - 1] ?? 0)

function shufflePositions(count: number): number[] {
  const positions = Array.from({ length: TOTAL_CELLS }, (_, i) => i)
  for (let i = positions.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[positions[i], positions[j]] = [positions[j], positions[i]]
  }
  return positions.slice(0, count)
}

function generateRound() {
  const count = currentDifficulty.value.count
  const positions = shufflePositions(count)

  // 生成不重复数字 (1-based, 范围适中)
  const maxNum = count + Math.floor(count * 0.5)
  const nums = new Set<number>()
  while (nums.size < count) {
    nums.add(Math.floor(Math.random() * maxNum) + 1)
  }
  const numArr = [...nums]

  // 映射 position -> number
  const map = new Map<number, number>()
  positions.forEach((pos, i) => {
    map.set(pos, numArr[i])
  })

  numberCells.value = map
  sortedNumbers.value = [...numArr].sort((a, b) => a - b)
  nextTarget.value = 1
  clickedCells.value = new Set()
  wrongCell.value = null
  roundCorrect.value = true
}

function startGame() {
  round.value = 0
  correct.value = 0
  state.value = 'ready'
  nextRound()
}

function nextRound() {
  round.value++
  if (round.value > ROUNDS_PER_GAME) {
    state.value = 'finished'
    return
  }

  generateRound()
  state.value = 'showing'

  if (showTimer) clearTimeout(showTimer)
  showTimer = setTimeout(() => {
    state.value = 'playing'
  }, currentDifficulty.value.showTime)
}

function handleCellClick(cellIndex: number) {
  if (state.value !== 'playing') return
  if (clickedCells.value.has(cellIndex)) return // 已点击过

  const expectedValue = currentTargetValue.value
  const cellValue = numberCells.value.get(cellIndex)

  if (cellValue === expectedValue) {
    // 正确
    clickedCells.value = new Set([...clickedCells.value, cellIndex])
    nextTarget.value++

    // 全部点完
    if (nextTarget.value > sortedNumbers.value.length) {
      if (roundCorrect.value) correct.value++
      state.value = 'result'
    }
  }
  else {
    // 错误
    wrongCell.value = cellIndex
    roundCorrect.value = false
    setTimeout(() => {
      wrongCell.value = null
    }, 400)
  }
}

function continueGame() {
  nextRound()
}

function goBack() {
  if (showTimer) clearTimeout(showTimer)
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
        <text class="text-lg font-bold tracking-widest">瞬间记忆</text>
      </view>
    </view>

    <view class="px-4 pb-8 pt-3">
      <!-- 进度 -->
      <view v-if="state === 'showing' || state === 'playing' || state === 'result'" class="mb-3 flex items-center justify-between px-1">
        <text class="text-[14px] text-[#64748B] font-bold">第 {{ round }}/{{ ROUNDS_PER_GAME }} 轮</text>
        <text class="text-[14px] text-[#F59E0B] font-bold">{{ currentDifficulty.label }}</text>
      </view>

      <!-- 展示阶段 -->
      <view v-if="state === 'showing'">
        <view class="mb-3 text-center text-[13px] text-[#94A3B8]">
          记住数字的位置和数值
        </view>
        <view class="grid grid-cols-5 gap-1.5 mx-auto" style="max-width: 340px">
          <view
            v-for="i in TOTAL_CELLS"
            :key="i"
            class="aspect-square flex items-center justify-center rounded-lg"
            :class="numberCells.has(i - 1) ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-white/60'"
          >
            <text v-if="numberCells.has(i - 1)" class="text-[22px] font-black">
              {{ numberCells.get(i - 1) }}
            </text>
          </view>
        </view>
        <view class="mt-3 h-1.5 mx-8 overflow-hidden rounded-full bg-[#E2E8F0]">
          <view class="h-full rounded-full bg-[#F59E0B] animate-shrink" :style="{ animationDuration: `${currentDifficulty.showTime}ms` }" />
        </view>
      </view>

      <!-- 作答阶段 -->
      <view v-if="state === 'playing'">
        <view class="mb-3 text-center">
          <text class="text-[13px] text-[#94A3B8]">按从小到大的顺序点击位置，下一个: </text>
          <text class="text-[18px] text-[#F59E0B] font-black">{{ currentTargetValue }}</text>
        </view>
        <view class="grid grid-cols-5 gap-1.5 mx-auto" style="max-width: 340px">
          <view
            v-for="i in TOTAL_CELLS"
            :key="i"
            class="aspect-square flex items-center justify-center rounded-lg font-black transition-all active:scale-95"
            :class="[
              clickedCells.has(i - 1)
                ? 'bg-[#059669] text-white'
                : wrongCell === i - 1
                  ? 'bg-[#FEE2E2] text-[#EF4444]'
                  : 'bg-white text-[#1E293B] shadow-sm',
            ]"
            @click="handleCellClick(i - 1)"
          >
            <text v-if="clickedCells.has(i - 1)" class="text-[20px]">
              {{ numberCells.get(i - 1) }}
            </text>
            <text v-else-if="wrongCell === i - 1" class="text-[18px]">✕</text>
          </view>
        </view>
      </view>

      <!-- 单轮结果 -->
      <view v-if="state === 'result'" class="mt-4">
        <view class="mb-4 text-center text-[13px] text-[#94A3B8]">
          正确答案
        </view>
        <view class="grid grid-cols-5 gap-1.5 mx-auto mb-4" style="max-width: 340px">
          <view
            v-for="i in TOTAL_CELLS"
            :key="i"
            class="aspect-square flex items-center justify-center rounded-lg"
            :class="numberCells.has(i - 1) ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-white/40'"
          >
            <text v-if="numberCells.has(i - 1)" class="text-[22px] font-black">
              {{ numberCells.get(i - 1) }}
            </text>
          </view>
        </view>

        <view class="rounded-2xl bg-white/90 px-5 py-4 text-center shadow-sm">
          <text class="text-[18px]">{{ roundCorrect ? '✅' : '❌' }}</text>
          <text class="ml-2 text-[16px] font-black">{{ roundCorrect ? '全部正确！' : '有位置记错了' }}</text>
        </view>

        <view
          class="mt-4 mx-auto h-11 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[15px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="continueGame"
        >
          {{ round >= ROUNDS_PER_GAME ? '查看结果' : '下一轮' }}
        </view>
      </view>

      <!-- 准备 -->
      <view v-if="state === 'ready'" class="mt-4">
        <view class="text-center">
          <view class="mx-auto mb-5 text-[48px]">🧠</view>
          <view class="mb-4 text-[18px] font-black">瞬间记忆</view>
        </view>

        <view class="mx-auto mb-5 rounded-xl bg-white/80 px-5 py-4 text-left shadow-sm" style="max-width: 320px">
          <view class="mb-2 text-[14px] text-[#059669] font-bold">规则说明</view>
          <view class="mb-2 text-[13px] text-[#475569] leading-relaxed">
            屏幕上会闪现一组数字，记住它们的位置和数值
          </view>
          <view class="mb-2 text-[13px] text-[#475569] leading-relaxed">
            数字消失后，按照从小到大的顺序点击对应位置
          </view>
          <view class="text-[13px] text-[#475569] leading-relaxed">
            锻炼工作记忆和瞬间记忆能力
          </view>
        </view>

        <view class="mb-5">
          <view class="mb-3 text-[14px] text-[#059669] font-bold text-center">选择难度</view>
          <view class="grid grid-cols-3 gap-2 mx-auto" style="max-width: 320px">
            <view
              v-for="(opt, i) in DIFFICULTIES"
              :key="i"
              class="h-11 flex items-center justify-center rounded-lg text-[14px] font-black active:scale-95"
              :class="difficultyIndex === i ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-white text-[#475569]'"
              @click="difficultyIndex = i"
            >
              {{ opt.label }}
            </view>
          </view>
        </view>

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
          <text class="text-[18px] font-black">🧠 训练完成!</text>
          <view class="mt-4 grid grid-cols-2 gap-4">
            <view>
              <view class="text-[28px] text-[#059669] font-black">{{ correct }}</view>
              <view class="text-[12px] text-[#64748B]">全对轮数</view>
            </view>
            <view>
              <view class="text-[28px] text-[#F59E0B] font-black">{{ ROUNDS_PER_GAME }}</view>
              <view class="text-[12px] text-[#64748B]">总轮数</view>
            </view>
          </view>
          <view class="mt-3 text-[13px] text-[#94A3B8]">
            难度: {{ currentDifficulty.label }} ({{ currentDifficulty.count }}个数字)
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
  </view>
</template>

<style scoped>
@keyframes shrink {
  from { width: 100%; }
  to { width: 0%; }
}
.animate-shrink {
  animation: shrink linear forwards;
}
</style>
