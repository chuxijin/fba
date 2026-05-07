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

const gridSize = ref(5)
const state = ref<GameState>('ready')
const grid = ref<number[]>([])
const nextTarget = ref(1)
const wrongClicks = ref(0)
const startTime = ref(0)
const elapsed = ref(0)
const bestRecord = ref<number | null>(loadBestRecord())
const clickedCells = ref<Set<number>>(new Set())
let timer: ReturnType<typeof setInterval> | null = null

const totalCells = computed(() => gridSize.value * gridSize.value)

function loadBestRecord(): number | null {
  const key = `schulte_best_5`
  const val = uni.getStorageSync(key)
  return val ? Number(val) : null
}

function saveBestRecord(time: number) {
  const key = `schulte_best_${gridSize.value}`
  if (!bestRecord.value || time < bestRecord.value) {
    bestRecord.value = time
    uni.setStorageSync(key, String(time))
  }
}

function shuffle(arr: number[]): number[] {
  const result = [...arr]
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
}

function initGrid() {
  const nums: number[] = []
  for (let i = 1; i <= totalCells.value; i++) {
    nums.push(i)
  }
  grid.value = shuffle(nums)
}

function startGame() {
  initGrid()
  nextTarget.value = 1
  wrongClicks.value = 0
  elapsed.value = 0
  clickedCells.value = new Set()
  state.value = 'playing'
  startTime.value = Date.now()

  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    elapsed.value = Date.now() - startTime.value
  }, 50)
}

function handleCellClick(num: number) {
  if (state.value !== 'playing') return

  if (num === nextTarget.value) {
    clickedCells.value.add(num)
    clickedCells.value = new Set(clickedCells.value)
    nextTarget.value++

    if (nextTarget.value > totalCells.value) {
      finishGame()
    }
  }
  else {
    wrongClicks.value++
  }
}

function finishGame() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  elapsed.value = Date.now() - startTime.value
  state.value = 'finished'
  saveBestRecord(elapsed.value)
}

function formatTime(ms: number): string {
  const seconds = ms / 1000
  return seconds.toFixed(2)
}

function getCellClass(num: number): string {
  if (clickedCells.value.has(num)) {
    return 'bg-[#059669] text-white'
  }
  if (state.value === 'playing' && num === nextTarget.value) {
    return 'bg-white text-[#1F2937]'
  }
  return 'bg-white text-[#1F2937]'
}

function goBack() {
  if (timer) clearInterval(timer)
  uni.navigateBack()
}

function changeSize(size: number) {
  if (state.value === 'playing') return
  gridSize.value = size
  bestRecord.value = loadBestRecord()
  state.value = 'ready'
}
</script>

<template>
  <view class="min-h-screen bg-[#F5F1EA] text-[#111827]">
    <view class="relative z-10 w-full bg-[#F5F1EA]" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white/90 text-[#475569] shadow-sm active:scale-95" @click="goBack">
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="text-lg font-bold tracking-widest">舒尔特方格</text>
      </view>
    </view>

    <view class="px-4 pb-8 pt-3">
      <!-- 规格选择 -->
      <view v-if="state !== 'playing'" class="mb-4 flex justify-center gap-2">
        <view
          v-for="s in [3, 4, 5, 6, 7]"
          :key="s"
          class="h-9 w-14 flex items-center justify-center rounded-lg text-[13px] font-black active:scale-95"
          :class="gridSize === s ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-white text-[#64748B]'"
          @click="changeSize(s)"
        >
          {{ s }}×{{ s }}
        </view>
      </view>

      <!-- 计时和状态 -->
      <view class="mb-4 flex items-center justify-between px-1">
        <view class="flex items-center gap-3">
          <text class="text-[28px] font-black tabular-nums">{{ formatTime(elapsed) }}s</text>
          <text v-if="state === 'playing'" class="text-[14px] text-[#64748B] font-bold">
            下一个: {{ nextTarget }}
          </text>
        </view>
        <view class="flex flex-col items-end">
          <text v-if="wrongClicks > 0" class="text-[12px] text-[#EF4444] font-bold">
            误点 {{ wrongClicks }} 次
          </text>
          <text v-if="bestRecord" class="text-[12px] text-[#059669] font-bold">
            最佳 {{ formatTime(bestRecord) }}s
          </text>
        </view>
      </view>

      <!-- 方格 -->
      <view
        v-if="state === 'playing'"
        class="grid gap-1.5 mx-auto"
        :style="{ gridTemplateColumns: `repeat(${gridSize}, 1fr)`, maxWidth: '400px' }"
      >
        <view
          v-for="(num, index) in grid"
          :key="index"
          class="aspect-square flex items-center justify-center rounded-lg font-black shadow-sm transition-all active:scale-95"
          :class="getCellClass(num)"
          :style="{ fontSize: gridSize <= 5 ? '20px' : gridSize <= 6 ? '16px' : '14px' }"
          @click="handleCellClick(num)"
        >
          {{ clickedCells.has(num) ? '✓' : num }}
        </view>
      </view>

      <!-- 准备/结果 -->
      <view v-if="state === 'ready'" class="mt-8 text-center">
        <view class="mb-4 text-[16px] text-[#475569] leading-relaxed">
          按顺序点击 1 到 {{ totalCells }} 的数字
          <view class="mt-1 text-[13px] text-[#94A3B8]">
            考察视觉搜索和注意力分配能力
          </view>
        </view>
        <view
          class="mx-auto h-12 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[16px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="startGame"
        >
          开始
        </view>
      </view>

      <view v-if="state === 'finished'" class="mt-6">
        <view class="rounded-2xl bg-white/90 px-5 py-6 text-center shadow-sm">
          <text class="text-[18px] font-black">🎉 完成!</text>
          <view class="mt-3 text-[36px] text-[#F59E0B] font-black tabular-nums">
            {{ formatTime(elapsed) }}s
          </view>
          <view v-if="wrongClicks > 0" class="mt-1 text-[13px] text-[#EF4444]">
            误点 {{ wrongClicks }} 次
          </view>
          <view v-if="bestRecord && elapsed <= bestRecord" class="mt-2 text-[14px] text-[#059669] font-bold">
            🏆 新纪录!
          </view>
        </view>
        <view class="mt-5 flex gap-3">
          <view
            class="flex-1 h-11 flex items-center justify-center rounded-xl bg-[#E8EDF5] text-[15px] font-black active:scale-95"
            @click="state = 'ready'"
          >
            返回
          </view>
          <view
            class="flex-1 h-11 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[15px] text-[#111827] font-black shadow-lg active:scale-95"
            @click="startGame"
          >
            再来一次
          </view>
        </view>
      </view>
    </view>
  </view>
</template>
