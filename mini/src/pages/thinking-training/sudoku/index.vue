<script lang="ts" setup>
import { ref, computed } from 'vue'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

type GameState = 'ready' | 'playing' | 'finished'
type Difficulty = 'easy' | 'medium' | 'hard'

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const EMPTY = 0

const state = ref<GameState>('ready')
const difficulty = ref<Difficulty>('easy')
const board = ref<number[][]>([])       // 当前棋盘（含用户输入）
const solution = ref<number[][]>([])    // 完整解
const fixed = ref<boolean[][]>([])      // 是否固定格
const selected = ref<[number, number] | null>(null)
const mistakes = ref(0)
const startTime = ref(0)
const elapsed = ref(0)
const noteMode = ref(false)
const notes = ref<Set<number>[][]>([])  // 候选数标记
let timer: ReturnType<typeof setInterval> | null = null

const difficultyOptions: { label: string, value: Difficulty, blanks: number }[] = [
  { label: '简单', value: 'easy', blanks: 30 },
  { label: '中等', value: 'medium', blanks: 40 },
  { label: '困难', value: 'hard', blanks: 50 },
]

const currentBlanks = computed(() => difficultyOptions.find(d => d.value === difficulty.value)!.blanks)

const remainingCount = computed(() => {
  let count = 0
  for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      if (board.value[r][c] === EMPTY) count++
    }
  }
  return count
})

// ---- 数独生成算法 ----
function createEmptyBoard(): number[][] {
  return Array.from({ length: 9 }, () => Array(9).fill(EMPTY))
}

function isValid(b: number[][], row: number, col: number, num: number): boolean {
  for (let c = 0; c < 9; c++) {
    if (b[row][c] === num) return false
  }
  for (let r = 0; r < 9; r++) {
    if (b[r][col] === num) return false
  }
  const boxR = Math.floor(row / 3) * 3
  const boxC = Math.floor(col / 3) * 3
  for (let r = boxR; r < boxR + 3; r++) {
    for (let c = boxC; c < boxC + 3; c++) {
      if (b[r][c] === num) return false
    }
  }
  return true
}

function shuffleArray<T>(arr: T[]): T[] {
  const result = [...arr]
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
}

function solveSudoku(b: number[][]): boolean {
  for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      if (b[r][c] === EMPTY) {
        const nums = shuffleArray([1, 2, 3, 4, 5, 6, 7, 8, 9])
        for (const num of nums) {
          if (isValid(b, r, c, num)) {
            b[r][c] = num
            if (solveSudoku(b)) return true
            b[r][c] = EMPTY
          }
        }
        return false
      }
    }
  }
  return true
}

function generatePuzzle(blanks: number) {
  // 生成完整解
  const fullBoard = createEmptyBoard()
  solveSudoku(fullBoard)
  solution.value = fullBoard.map(row => [...row])

  // 挖空
  const puzzle = fullBoard.map(row => [...row])
  const positions = shuffleArray(
    Array.from({ length: 81 }, (_, i) => [Math.floor(i / 9), i % 9] as [number, number]),
  )
  let removed = 0
  for (const [r, c] of positions) {
    if (removed >= blanks) break
    puzzle[r][c] = EMPTY
    removed++
  }

  board.value = puzzle.map(row => [...row])
  fixed.value = puzzle.map(row => row.map(v => v !== EMPTY))
  notes.value = Array.from({ length: 9 }, () =>
    Array.from({ length: 9 }, () => new Set<number>()),
  )
}

function startGame() {
  mistakes.value = 0
  elapsed.value = 0
  selected.value = null
  noteMode.value = false
  state.value = 'playing'
  startTime.value = Date.now()

  generatePuzzle(currentBlanks.value)

  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    elapsed.value = Date.now() - startTime.value
  }, 1000)
}

function selectCell(row: number, col: number) {
  if (state.value !== 'playing') return
  if (fixed.value[row][col]) {
    selected.value = [row, col] // 允许选中固定格查看
    return
  }
  selected.value = [row, col]
}

function inputNumber(num: number) {
  if (state.value !== 'playing' || !selected.value) return
  const [r, c] = selected.value
  if (fixed.value[r][c]) return

  if (noteMode.value) {
    // 候选数模式
    const noteSet = notes.value[r][c]
    if (noteSet.has(num)) {
      noteSet.delete(num)
    }
    else {
      noteSet.add(num)
    }
    notes.value = [...notes.value] // 触发响应
    return
  }

  // 正常输入
  if (num === solution.value[r][c]) {
    board.value[r][c] = num
    board.value = [...board.value] // 触发响应
    notes.value[r][c] = new Set() // 清除候选数

    // 检查是否完成
    if (remainingCount.value === 0) {
      finishGame()
    }
  }
  else {
    mistakes.value++
    // 三次错误提示
    if (mistakes.value >= 3) {
      uni.showToast({ title: '错误太多了，加油！', icon: 'none' })
    }
  }
}

function clearCell() {
  if (state.value !== 'playing' || !selected.value) return
  const [r, c] = selected.value
  if (fixed.value[r][c]) return
  board.value[r][c] = EMPTY
  board.value = [...board.value]
  notes.value[r][c] = new Set()
  notes.value = [...notes.value]
}

function finishGame() {
  if (timer) { clearInterval(timer); timer = null }
  elapsed.value = Date.now() - startTime.value
  state.value = 'finished'
}

function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function getCellClass(row: number, col: number): string {
  const isSelected = selected.value && selected.value[0] === row && selected.value[1] === col
  const isFixed = fixed.value[row]?.[col]
  const val = board.value[row]?.[col]
  const selectedVal = selected.value ? board.value[selected.value[0]]?.[selected.value[1]] : 0
  const isSameNumber = val && val !== EMPTY && val === selectedVal
  const isSameRowCol = selected.value && (selected.value[0] === row || selected.value[1] === col)
  const isSameBox = selected.value
    && Math.floor(selected.value[0] / 3) === Math.floor(row / 3)
    && Math.floor(selected.value[1] / 3) === Math.floor(col / 3)

  if (isSelected) return 'bg-[#BFDBFE] text-[#1E293B]'
  if (isSameNumber) return 'bg-[#DBEAFE] text-[#1E293B]'
  if (isSameRowCol || isSameBox) return 'bg-[#F1F5F9] text-[#1E293B]'
  if (isFixed) return 'bg-white text-[#1E293B]'
  return 'bg-white text-[#2563EB]'
}

function goBack() {
  if (timer) clearInterval(timer)
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
        <text class="text-lg font-bold tracking-widest">数独</text>
      </view>
    </view>

    <view class="px-3 pb-[160px] pt-2">
      <!-- 准备 -->
      <view v-if="state === 'ready'" class="mt-6 px-2">
        <view class="text-center">
          <view class="mx-auto mb-5 text-[48px]">🧩</view>
          <view class="mb-4 text-[18px] font-black">数独</view>
        </view>

        <view class="mb-5">
          <view class="mb-3 text-[14px] text-[#475569] font-bold text-center">选择难度</view>
          <view class="flex justify-center gap-2">
            <view
              v-for="opt in difficultyOptions"
              :key="opt.value"
              class="h-10 w-20 flex items-center justify-center rounded-lg text-[14px] font-black active:scale-95"
              :class="difficulty === opt.value ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-white text-[#64748B]'"
              @click="difficulty = opt.value"
            >
              {{ opt.label }}
            </view>
          </view>
        </view>

        <view
          class="mx-auto h-12 w-48 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[16px] text-[#111827] font-black shadow-lg active:scale-95"
          @click="startGame"
        >
          开始游戏
        </view>
      </view>

      <!-- 游戏中 -->
      <view v-if="state === 'playing'">
        <!-- 顶部状态 -->
        <view class="mb-2 flex items-center justify-between px-1">
          <text class="text-[14px] text-[#64748B] font-bold tabular-nums">⏱ {{ formatTime(elapsed) }}</text>
          <text class="text-[14px] font-bold" :class="mistakes > 0 ? 'text-[#EF4444]' : 'text-[#64748B]'">
            错误 {{ mistakes }}
          </text>
          <text class="text-[14px] text-[#64748B] font-bold">剩余 {{ remainingCount }}</text>
        </view>

        <!-- 数独棋盘 -->
        <view class="mx-auto rounded-lg border-2 border-[#1F2937] overflow-hidden" style="width: fit-content">
          <view v-for="(row, r) in board" :key="r" class="flex">
            <view
              v-for="(cell, c) in row"
              :key="c"
              class="relative h-9 w-9 flex items-center justify-center font-black active:scale-95"
              :class="[
                getCellClass(r, c),
                c % 3 === 2 && c < 8 ? 'border-r-2 border-r-[#1F2937]' : 'border-r border-r-[#CBD5E1]',
                r % 3 === 2 && r < 8 ? 'border-b-2 border-b-[#1F2937]' : 'border-b border-b-[#CBD5E1]',
              ]"
              @click="selectCell(r, c)"
            >
              <!-- 数字 -->
              <text v-if="cell !== EMPTY" class="text-[16px]" :class="fixed[r][c] ? 'font-black' : 'font-bold'">
                {{ cell }}
              </text>
              <!-- 候选数 -->
              <view v-else-if="notes[r][c].size > 0" class="grid grid-cols-3 w-full h-full p-px">
                <text
                  v-for="n in 9"
                  :key="n"
                  class="flex items-center justify-center text-[7px] text-[#94A3B8]"
                >
                  {{ notes[r][c].has(n) ? n : '' }}
                </text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- 完成 -->
      <view v-if="state === 'finished'" class="mt-6">
        <view class="rounded-2xl bg-white/90 px-5 py-6 text-center shadow-sm">
          <text class="text-[18px] font-black">🎉 数独完成!</text>
          <view class="mt-4 grid grid-cols-2 gap-4">
            <view>
              <view class="text-[24px] text-[#F59E0B] font-black tabular-nums">{{ formatTime(elapsed) }}</view>
              <view class="text-[12px] text-[#64748B]">用时</view>
            </view>
            <view>
              <view class="text-[24px] font-black" :class="mistakes === 0 ? 'text-[#059669]' : 'text-[#EF4444]'">{{ mistakes }}</view>
              <view class="text-[12px] text-[#64748B]">错误</view>
            </view>
          </view>
        </view>
        <view class="mt-5 flex gap-3">
          <view class="flex-1 h-11 flex items-center justify-center rounded-xl bg-[#E8EDF5] text-[15px] font-black active:scale-95" @click="state = 'ready'">
            返回
          </view>
          <view class="flex-1 h-11 flex items-center justify-center rounded-xl bg-[#F59E0B] text-[15px] text-[#111827] font-black shadow-lg active:scale-95" @click="startGame">
            再来一局
          </view>
        </view>
      </view>
    </view>

    <!-- 固定底部操作键盘 -->
    <view v-if="state === 'playing'" class="fixed bottom-0 left-0 right-0 bg-[#D9D3C8]/96 px-4 pb-[calc(env(safe-area-inset-bottom)+8px)] pt-3 shadow-[0_-10px_28px_-22px_rgba(31,41,55,0.55)]">
      <view class="flex justify-center gap-2 mb-2">
        <view
          class="h-9 flex-1 flex items-center justify-center rounded-lg text-[13px] font-black active:scale-95"
          :class="noteMode ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-[#E8EDF5] text-[#475569]'"
          @click="noteMode = !noteMode"
        >
          {{ noteMode ? '📝 标注中' : '📝 标注' }}
        </view>
        <view class="h-9 flex-1 flex items-center justify-center rounded-lg bg-[#E8EDF5] text-[13px] text-[#475569] font-black active:scale-95" @click="clearCell">
          清除
        </view>
      </view>
      <view class="grid grid-cols-9 gap-1">
        <view
          v-for="n in 9"
          :key="n"
          class="h-[52px] flex items-center justify-center rounded-md bg-[#E8EDF5] text-[20px] text-[#334155] font-black active:scale-[0.98]"
          @click="inputNumber(n)"
        >
          {{ n }}
        </view>
      </view>
    </view>
  </view>
</template>
