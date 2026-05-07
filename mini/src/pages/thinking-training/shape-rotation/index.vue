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

const TOTAL_ROUNDS = 15

// 基础形状定义（用 5x5 点阵表示）
const SHAPES = [
  // L 形
  [[1, 0], [1, 1], [1, 2], [1, 3], [2, 3]],
  // T 形
  [[0, 1], [1, 0], [1, 1], [1, 2], [2, 1]],
  // Z 形
  [[0, 0], [0, 1], [1, 1], [1, 2], [2, 2]],
  // 十字
  [[0, 1], [1, 0], [1, 1], [1, 2], [2, 1]],
  // 倒 L
  [[0, 0], [1, 0], [2, 0], [2, 1], [2, 2]],
  // S 形
  [[0, 1], [0, 2], [1, 0], [1, 1], [2, 0]],
  // 阶梯
  [[0, 0], [1, 0], [1, 1], [2, 1], [2, 2]],
  // P 形
  [[0, 0], [0, 1], [1, 0], [1, 1], [2, 0]],
]

const state = ref<GameState>('ready')
const round = ref(0)
const correct = ref(0)
const wrong = ref(0)
const originalShape = ref<number[][]>([])
const optionShapes = ref<number[][][]>([])
const correctOptionIndex = ref(0)
const feedback = ref<'correct' | 'wrong' | null>(null)
const startTime = ref(0)
const elapsed = ref(0)
let timer: ReturnType<typeof setInterval> | null = null
let feedbackTimer: ReturnType<typeof setTimeout> | null = null

const accuracy = computed(() => {
  const total = correct.value + wrong.value
  return total ? Math.round(correct.value / total * 100) : 0
})

function rotateShape(shape: number[][], times: number): number[][] {
  let result = shape.map(p => [...p])
  for (let t = 0; t < times; t++) {
    result = result.map(p => [p[1], 4 - p[0]])
  }
  return normalizeShape(result)
}

function mirrorShape(shape: number[][]): number[][] {
  const result = shape.map(p => [p[0], 4 - p[1]])
  return normalizeShape(result)
}

function normalizeShape(shape: number[][]): number[][] {
  const minR = Math.min(...shape.map(p => p[0]))
  const minC = Math.min(...shape.map(p => p[1]))
  return shape.map(p => [p[0] - minR, p[1] - minC]).sort((a, b) => a[0] - b[0] || a[1] - b[1])
}

function shapesEqual(a: number[][], b: number[][]): boolean {
  if (a.length !== b.length) return false
  const an = normalizeShape(a)
  const bn = normalizeShape(b)
  return an.every((p, i) => p[0] === bn[i][0] && p[1] === bn[i][1])
}

function generateRound() {
  const baseShape = SHAPES[Math.floor(Math.random() * SHAPES.length)]
  const rotations = Math.floor(Math.random() * 3) + 1

  // 原始图形（可能先随机旋转一下）
  const origRotation = Math.floor(Math.random() * 4)
  originalShape.value = rotateShape(baseShape, origRotation)

  // 正确答案：旋转后的图形
  const correctShape = rotateShape(originalShape.value, rotations)

  // 干扰项：镜像 + 不同旋转
  const distractors: number[][][] = []
  // 镜像
  const mirrored = mirrorShape(originalShape.value)
  if (!shapesEqual(mirrored, correctShape)) {
    distractors.push(rotateShape(mirrored, Math.floor(Math.random() * 4)))
  }
  // 不同图形
  for (const s of SHAPES) {
    if (distractors.length >= 2) break
    const candidate = rotateShape(s, Math.floor(Math.random() * 4))
    if (!shapesEqual(candidate, correctShape) && !distractors.some(d => shapesEqual(d, candidate))) {
      distractors.push(candidate)
    }
  }

  // 确保有3个干扰项
  while (distractors.length < 3) {
    const s = SHAPES[Math.floor(Math.random() * SHAPES.length)]
    const candidate = rotateShape(s, Math.floor(Math.random() * 4))
    if (!shapesEqual(candidate, correctShape) && !distractors.some(d => shapesEqual(d, candidate))) {
      distractors.push(candidate)
    }
  }

  // 混合选项
  const allOptions = [correctShape, ...distractors.slice(0, 3)]
  const shuffled = shuffleArray(allOptions.map((s, i) => ({ shape: s, isCorrect: i === 0 })))
  optionShapes.value = shuffled.map(o => o.shape)
  correctOptionIndex.value = shuffled.findIndex(o => o.isCorrect)
}

function shuffleArray<T>(arr: T[]): T[] {
  const result = [...arr]
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
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
  generateRound()
}

function handleAnswer(index: number) {
  if (state.value !== 'playing' || feedback.value) return

  if (index === correctOptionIndex.value) {
    correct.value++
    feedback.value = 'correct'
  }
  else {
    wrong.value++
    feedback.value = 'wrong'
  }

  if (feedbackTimer) clearTimeout(feedbackTimer)
  feedbackTimer = setTimeout(() => {
    nextRound()
  }, 500)
}

function finishGame() {
  if (timer) { clearInterval(timer); timer = null }
  elapsed.value = Date.now() - startTime.value
  state.value = 'finished'
}

function isShapeCell(shape: number[][], row: number, col: number): boolean {
  return shape.some(p => p[0] === row && p[1] === col)
}

function formatTime(ms: number): string {
  return (ms / 1000).toFixed(1)
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
        <text class="text-lg font-bold tracking-widest">图形旋转</text>
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

      <!-- 游戏区 -->
      <view v-if="state === 'playing'">
        <view class="mb-3 text-center text-[13px] text-[#94A3B8]">
          哪个选项是原图旋转后的结果？
        </view>

        <!-- 原始图形 -->
        <view class="mb-5 flex justify-center">
          <view class="rounded-2xl bg-white/90 p-4 shadow-sm">
            <view class="text-center text-[12px] text-[#94A3B8] mb-2 font-bold">原图</view>
            <view class="grid gap-0.5" style="grid-template-columns: repeat(5, 1fr)">
              <view
                v-for="r in 5"
                :key="`orig-${r}`"
              >
                <view
                  v-for="c in 5"
                  :key="`orig-${r}-${c}`"
                  class="h-7 w-7 rounded-sm"
                  :class="isShapeCell(originalShape, r - 1, c - 1) ? 'bg-[#1F2937]' : 'bg-[#F1F5F9]'"
                />
              </view>
            </view>
          </view>
        </view>

        <!-- 选项 -->
        <view class="grid grid-cols-2 gap-3">
          <view
            v-for="(shape, idx) in optionShapes"
            :key="idx"
            class="rounded-2xl p-3 shadow-sm active:scale-95"
            :class="[
              feedback && idx === correctOptionIndex ? 'bg-[#ECFDF5] ring-2 ring-[#059669]' : 'bg-white/90',
              feedback === 'wrong' && idx !== correctOptionIndex ? 'opacity-50' : '',
            ]"
            @click="handleAnswer(idx)"
          >
            <view class="text-center text-[12px] text-[#94A3B8] mb-1 font-bold">{{ ['A', 'B', 'C', 'D'][idx] }}</view>
            <view class="grid gap-0.5 mx-auto" style="grid-template-columns: repeat(5, 1fr); width: fit-content">
              <template v-for="r in 5" :key="`opt-${idx}-${r}`">
                <view
                  v-for="c in 5"
                  :key="`opt-${idx}-${r}-${c}`"
                  class="h-5 w-5 rounded-sm"
                  :class="isShapeCell(shape, r - 1, c - 1) ? 'bg-[#475569]' : 'bg-[#F1F5F9]'"
                />
              </template>
            </view>
          </view>
        </view>
      </view>

      <!-- 准备 -->
      <view v-if="state === 'ready'" class="mt-8 text-center">
        <view class="mx-auto mb-6 text-[48px]">🔄</view>
        <view class="mb-2 text-[18px] font-black">图形旋转</view>
        <view class="mb-1 text-[14px] text-[#475569] leading-relaxed">给出一个原始图形</view>
        <view class="mb-6 text-[14px] text-[#475569] leading-relaxed">从4个选项中找出旋转后的正确图形</view>
        <view
          class="mx-auto h-12 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[16px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="startGame"
        >
          开始测试
        </view>
      </view>

      <!-- 结果 -->
      <view v-if="state === 'finished'" class="mt-6">
        <view class="rounded-2xl bg-white/90 px-5 py-6 text-center shadow-sm">
          <text class="text-[18px] font-black">🔄 测试完成!</text>
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
