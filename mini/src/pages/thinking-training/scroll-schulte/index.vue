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

const GRID_SIZE = 4
const TOTAL_CELLS = GRID_SIZE * GRID_SIZE
const GAME_DURATION = 60 // 秒

const state = ref<GameState>('ready')
const grid = ref<number[]>([])
const nextTarget = ref(1) // 下一个要点击的数字
const score = ref(0)
const mistakes = ref(0)
const remaining = ref(GAME_DURATION)
const feedback = ref<{ index: number, type: 'correct' | 'wrong' } | null>(null)
let timer: ReturnType<typeof setInterval> | null = null
let feedbackTimer: ReturnType<typeof setTimeout> | null = null

// 当前方格中的最小数字
const minInGrid = computed(() => Math.min(...grid.value))

function generateGrid(): number[] {
  // 生成 16 个不重复数字，包含 nextTarget
  const nums = new Set<number>()
  nums.add(nextTarget.value)

  while (nums.size < TOTAL_CELLS) {
    // 数字范围：从 nextTarget 附近，保证有挑战性
    const range = Math.max(30, nextTarget.value + 20)
    const n = Math.floor(Math.random() * range) + 1
    if (!nums.has(n)) {
      nums.add(n)
    }
  }

  // 打乱排列
  const arr = [...nums]
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

function refreshCell(index: number) {
  // 被点击的格子刷新为新数字
  const existing = new Set(grid.value)
  let newNum: number
  const range = Math.max(30, nextTarget.value + 25)
  let attempts = 0
  do {
    newNum = Math.floor(Math.random() * range) + 1
    attempts++
  } while ((existing.has(newNum) || newNum < nextTarget.value) && attempts < 100)

  grid.value[index] = newNum

  // 确保 nextTarget 在方格中存在
  if (!grid.value.includes(nextTarget.value)) {
    // 把一个随机非目标格替换成 nextTarget
    const candidates = grid.value
      .map((v, i) => ({ v, i }))
      .filter(({ i }) => i !== index)
    if (candidates.length > 0) {
      const pick = candidates[Math.floor(Math.random() * candidates.length)]
      grid.value[pick.i] = nextTarget.value
    }
  }

  grid.value = [...grid.value] // 触发响应
}

function startGame() {
  nextTarget.value = 1
  score.value = 0
  mistakes.value = 0
  remaining.value = GAME_DURATION
  feedback.value = null
  grid.value = generateGrid()
  state.value = 'playing'

  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    remaining.value--
    if (remaining.value <= 0) {
      finishGame()
    }
  }, 1000)
}

function handleCellClick(index: number) {
  if (state.value !== 'playing') return

  const clickedNum = grid.value[index]

  if (clickedNum === nextTarget.value) {
    // 正确
    score.value++
    feedback.value = { index, type: 'correct' }
    nextTarget.value++
    refreshCell(index)
  }
  else {
    // 错误
    mistakes.value++
    feedback.value = { index, type: 'wrong' }
  }

  if (feedbackTimer) clearTimeout(feedbackTimer)
  feedbackTimer = setTimeout(() => {
    feedback.value = null
  }, 300)
}

function finishGame() {
  if (timer) { clearInterval(timer); timer = null }
  state.value = 'finished'
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function goBack() {
  if (timer) clearInterval(timer)
  if (feedbackTimer) clearTimeout(feedbackTimer)
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
        <text class="text-lg font-bold tracking-widest">滚动舒尔特</text>
      </view>
    </view>

    <view class="px-4 pb-8 pt-3">
      <!-- 游戏中 -->
      <view v-if="state === 'playing'">
        <!-- 状态栏 -->
        <view class="mb-3 flex items-center justify-between px-1">
          <view class="flex items-center gap-1">
            <text class="text-[13px] text-[#94A3B8]">下一个</text>
            <text class="text-[20px] text-[#F59E0B] font-black tabular-nums">{{ nextTarget }}</text>
          </view>
          <view class="flex items-center gap-3">
            <text class="text-[14px] text-[#059669] font-bold">得分 {{ score }}</text>
            <text class="text-[14px] font-bold tabular-nums" :class="remaining <= 10 ? 'text-[#EF4444]' : 'text-[#64748B]'">
              {{ formatTime(remaining) }}
            </text>
          </view>
        </view>

        <!-- 进度条 -->
        <view class="mb-4 h-1.5 overflow-hidden rounded-full bg-[#E2E8F0]">
          <view
            class="h-full rounded-full transition-all duration-1000"
            :class="remaining <= 10 ? 'bg-[#EF4444]' : 'bg-[#F59E0B]'"
            :style="{ width: `${remaining / GAME_DURATION * 100}%` }"
          />
        </view>

        <!-- 4×4 方格 -->
        <view class="grid grid-cols-4 gap-2 mx-auto" style="max-width: 340px">
          <view
            v-for="(num, index) in grid"
            :key="index"
            class="aspect-square flex items-center justify-center rounded-xl text-[26px] font-black shadow-sm transition-all active:scale-95"
            :class="[
              feedback && feedback.index === index && feedback.type === 'correct'
                ? 'bg-[#059669] text-white scale-95'
                : feedback && feedback.index === index && feedback.type === 'wrong'
                  ? 'bg-[#FEE2E2] text-[#EF4444]'
                  : num === nextTarget
                    ? 'bg-white text-[#1E293B]'
                    : 'bg-white text-[#1E293B]',
            ]"
            @click="handleCellClick(index)"
          >
            {{ num }}
          </view>
        </view>

        <!-- 提示 -->
        <view class="mt-4 text-center text-[13px] text-[#94A3B8]">
          从小到大依次点击，点中后自动刷新
        </view>
      </view>

      <!-- 准备 -->
      <view v-if="state === 'ready'" class="mt-8 text-center">
        <view class="mx-auto mb-6 text-[48px]">🔢</view>
        <view class="mb-4 text-[18px] font-black">滚动舒尔特</view>

        <view class="mx-auto mb-6 rounded-xl bg-white/80 px-5 py-4 text-left shadow-sm" style="max-width: 320px">
          <view class="mb-2 text-[14px] text-[#059669] font-bold">规则说明</view>
          <view class="mb-2 text-[13px] text-[#475569] leading-relaxed">
            以 4×4 舒尔特方格训练为基础，从小到大点击数字方格
          </view>
          <view class="mb-2 text-[13px] text-[#475569] leading-relaxed">
            点击后的方格会自动刷新数字，在有限时间内尽可能点击更多数字
          </view>
          <view class="text-[13px] text-[#475569] leading-relaxed">
            与舒尔特方格一样，能够锻炼和提高注意力
          </view>
        </view>

        <view
          class="mx-auto h-12 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[16px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="startGame"
        >
          开始训练
        </view>
      </view>

      <!-- 结果 -->
      <view v-if="state === 'finished'" class="mt-6">
        <view class="rounded-2xl bg-white/90 px-5 py-6 text-center shadow-sm">
          <text class="text-[18px] font-black">🔢 训练完成!</text>
          <view class="mt-4 grid grid-cols-3 gap-4">
            <view>
              <view class="text-[28px] text-[#F59E0B] font-black">{{ score }}</view>
              <view class="text-[12px] text-[#64748B]">得分</view>
            </view>
            <view>
              <view class="text-[28px] text-[#EF4444] font-black">{{ mistakes }}</view>
              <view class="text-[12px] text-[#64748B]">误点</view>
            </view>
            <view>
              <view class="text-[28px] text-[#059669] font-black">{{ nextTarget - 1 }}</view>
              <view class="text-[12px] text-[#64748B]">最大数</view>
            </view>
          </view>
          <view class="mt-3 text-[13px] text-[#94A3B8]">
            {{ GAME_DURATION }}秒内连续点击了 {{ score }} 个数字
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
