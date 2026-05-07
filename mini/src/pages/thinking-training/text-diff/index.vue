<script lang="ts" setup>
import { ref, computed } from 'vue'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

type GameState = 'ready' | 'playing' | 'finished'

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

// 相似字组
const CHAR_GROUPS = [
  { base: '已', diff: '己' }, { base: '末', diff: '未' }, { base: '土', diff: '士' },
  { base: '日', diff: '曰' }, { base: '刀', diff: '力' }, { base: '人', diff: '入' },
  { base: '天', diff: '夫' }, { base: '干', diff: '千' }, { base: '午', diff: '牛' },
  { base: '大', diff: '太' }, { base: '王', diff: '玉' }, { base: '甲', diff: '由' },
  { base: '方', diff: '万' }, { base: '问', diff: '间' }, { base: '买', diff: '卖' },
  { base: '木', diff: '本' }, { base: '白', diff: '自' }, { base: '目', diff: '且' },
  { base: '乌', diff: '鸟' }, { base: '令', diff: '今' }, { base: '贝', diff: '见' },
  { base: '折', diff: '拆' }, { base: '拔', diff: '拨' }, { base: '侯', diff: '候' },
  { base: '沐', diff: '浴' }, { base: '辩', diff: '辨' }, { base: '晴', diff: '睛' },
  { base: '壁', diff: '璧' }, { base: '戍', diff: '戊' }, { base: '衰', diff: '哀' },
]

const TOTAL_ROUNDS = 15
const GRID_SIZE = [5, 6, 7] // 逐渐增大

const state = ref<GameState>('ready')
const round = ref(0)
const correct = ref(0)
const wrong = ref(0)
const startTime = ref(0)
const elapsed = ref(0)
const grid = ref<string[]>([])
const diffIndex = ref(0)
const currentGroup = ref({ base: '', diff: '' })
const currentGridCols = ref(5)
const feedback = ref<'correct' | 'wrong' | null>(null)
let timer: ReturnType<typeof setInterval> | null = null
let feedbackTimeout: ReturnType<typeof setTimeout> | null = null

const accuracy = computed(() => {
  const total = correct.value + wrong.value
  return total ? Math.round(correct.value / total * 100) : 0
})

function shuffle<T>(arr: T[]): T[] {
  const result = [...arr]
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
}

function generateGrid() {
  // 根据轮次选择方格大小
  const sizeIdx = Math.min(Math.floor(round.value / 5), GRID_SIZE.length - 1)
  const cols = GRID_SIZE[sizeIdx]
  currentGridCols.value = cols
  const totalCells = cols * cols

  // 随机选一组相似字
  const group = CHAR_GROUPS[Math.floor(Math.random() * CHAR_GROUPS.length)]
  currentGroup.value = group

  // 生成网格：全部填入 base，随机一个位置换成 diff
  const cells = Array(totalCells).fill(group.base)
  const diffPos = Math.floor(Math.random() * totalCells)
  cells[diffPos] = group.diff
  diffIndex.value = diffPos

  grid.value = cells
}

function startGame() {
  round.value = 0
  correct.value = 0
  wrong.value = 0
  elapsed.value = 0
  feedback.value = null
  state.value = 'playing'
  startTime.value = Date.now()

  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    elapsed.value = Date.now() - startTime.value
  }, 100)

  nextRound()
}

function nextRound() {
  round.value++
  if (round.value > TOTAL_ROUNDS) {
    finishGame()
    return
  }
  feedback.value = null
  generateGrid()
}

function handleCellClick(index: number) {
  if (state.value !== 'playing' || feedback.value) return

  if (index === diffIndex.value) {
    correct.value++
    feedback.value = 'correct'
  }
  else {
    wrong.value++
    feedback.value = 'wrong'
  }

  if (feedbackTimeout) clearTimeout(feedbackTimeout)
  feedbackTimeout = setTimeout(() => {
    nextRound()
  }, 500)
}

function finishGame() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  elapsed.value = Date.now() - startTime.value
  state.value = 'finished'
}

function formatTime(ms: number): string {
  return (ms / 1000).toFixed(1)
}

function goBack() {
  if (timer) clearInterval(timer)
  if (feedbackTimeout) clearTimeout(feedbackTimeout)
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
        <text class="text-lg font-bold tracking-widest">文字找茬</text>
      </view>
    </view>

    <view class="px-4 pb-8 pt-3">
      <!-- 进度 -->
      <view v-if="state === 'playing'" class="mb-3 flex items-center justify-between px-1">
        <text class="text-[14px] text-[#64748B] font-bold">{{ round }}/{{ TOTAL_ROUNDS }}</text>
        <text class="text-[14px] text-[#64748B] font-bold tabular-nums">{{ formatTime(elapsed) }}s</text>
      </view>

      <view v-if="state === 'playing'" class="mb-2 h-1.5 overflow-hidden rounded-full bg-[#E2E8F0]">
        <view class="h-full rounded-full bg-[#F59E0B] transition-all duration-300" :style="{ width: `${round / TOTAL_ROUNDS * 100}%` }" />
      </view>

      <!-- 提示 -->
      <view v-if="state === 'playing'" class="mb-4 text-center text-[13px] text-[#94A3B8]">
        找出不同的那个字
      </view>

      <!-- 方格 -->
      <view
        v-if="state === 'playing'"
        class="grid gap-1.5 mx-auto"
        :style="{ gridTemplateColumns: `repeat(${currentGridCols}, 1fr)`, maxWidth: '380px' }"
      >
        <view
          v-for="(char, index) in grid"
          :key="index"
          class="aspect-square flex items-center justify-center rounded-lg font-black shadow-sm active:scale-95 transition-all"
          :class="[
            feedback && index === diffIndex
              ? 'bg-[#059669] text-white ring-2 ring-[#059669]'
              : feedback === 'wrong' ? 'bg-white/60 text-[#1F2937]' : 'bg-white text-[#1F2937]',
          ]"
          :style="{ fontSize: currentGridCols <= 5 ? '22px' : currentGridCols <= 6 ? '18px' : '16px' }"
          @click="handleCellClick(index)"
        >
          {{ char }}
        </view>
      </view>

      <!-- 准备 -->
      <view v-if="state === 'ready'" class="mt-8 text-center">
        <view class="mx-auto mb-6 text-[48px]">🔍</view>
        <view class="mb-2 text-[18px] font-black">文字找茬</view>
        <view class="mb-1 text-[14px] text-[#475569] leading-relaxed">在一堆相似的汉字中</view>
        <view class="mb-1 text-[14px] text-[#475569] leading-relaxed">快速找出那个不一样的字</view>
        <view class="mb-6 text-[13px] text-[#94A3B8]">例：从一堆「已」中找到「己」</view>
        <view
          class="mx-auto h-12 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[16px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="startGame"
        >
          开始挑战
        </view>
      </view>

      <!-- 结果 -->
      <view v-if="state === 'finished'" class="mt-6">
        <view class="rounded-2xl bg-white/90 px-5 py-6 text-center shadow-sm">
          <text class="text-[18px] font-black">🔍 挑战完成!</text>
          <view class="mt-4 grid grid-cols-3 gap-4">
            <view>
              <view class="text-[24px] text-[#059669] font-black">{{ correct }}</view>
              <view class="text-[12px] text-[#64748B]">正确</view>
            </view>
            <view>
              <view class="text-[24px] text-[#EF4444] font-black">{{ wrong }}</view>
              <view class="text-[12px] text-[#64748B]">错误</view>
            </view>
            <view>
              <view class="text-[24px] text-[#F59E0B] font-black">{{ accuracy }}%</view>
              <view class="text-[12px] text-[#64748B]">准确率</view>
            </view>
          </view>
          <view class="mt-3 text-[14px] text-[#64748B]">
            用时 {{ formatTime(elapsed) }}s
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
