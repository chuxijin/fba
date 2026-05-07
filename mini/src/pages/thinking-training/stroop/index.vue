<script lang="ts" setup>
import { ref, computed } from 'vue'

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

type GameState = 'ready' | 'playing' | 'result' | 'finished'

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const TOTAL_ROUNDS = 20

const COLOR_MAP: Record<string, string> = {
  红: '#EF4444',
  橙: '#F97316',
  黄: '#EAB308',
  绿: '#22C55E',
  蓝: '#3B82F6',
  紫: '#A855F7',
}
const COLOR_NAMES = Object.keys(COLOR_MAP)

interface DifficultyOption {
  label: string
  desc: string
}

const DIFFICULTIES: DifficultyOption[] = [
  { label: '难度1', desc: '颜色一致性判断' },
  { label: '难度2', desc: '颜色与含义判断' },
  { label: '难度3', desc: '双文字关系判断' },
  { label: '难度4', desc: '三重关系判断' },
  { label: '难度5', desc: '带框颜色选择' },
]

const state = ref<GameState>('ready')
const difficultyIndex = ref(0)
const round = ref(0)
const correct = ref(0)
const wrong = ref(0)
const startTime = ref(0)
const elapsed = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

// 当前题目数据
const questionWord = ref('')      // 显示的文字
const questionColor = ref('')     // 文字的显示颜色
const questionWord2 = ref('')     // 第二个文字（难度3+）
const questionColor2 = ref('')    // 第二个文字颜色
const questionBorderColor = ref('') // 框的颜色（难度5+）
const options = ref<Array<{ label: string, value: string }>>([])
const correctAnswer = ref('')
const feedback = ref<'correct' | 'wrong' | null>(null)

const accuracy = computed(() => {
  const total = correct.value + wrong.value
  return total ? Math.round(correct.value / total * 100) : 0
})

function randomPick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

function randomPickExcept<T>(arr: T[], except: T): T {
  const filtered = arr.filter(x => x !== except)
  return filtered[Math.floor(Math.random() * filtered.length)]
}

function shuffleArray<T>(arr: T[]): T[] {
  const result = [...arr]
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
}

function generateQuestion() {
  const d = difficultyIndex.value

  if (d === 0) {
    // 难度1：颜色一致性判断 — 文字和颜色是否一致？
    const word = randomPick(COLOR_NAMES)
    const isMatch = Math.random() > 0.5
    const color = isMatch ? word : randomPickExcept(COLOR_NAMES, word)

    questionWord.value = word
    questionColor.value = COLOR_MAP[color]
    correctAnswer.value = isMatch ? '一致' : '不一致'
    options.value = [
      { label: '一致', value: '一致' },
      { label: '不一致', value: '不一致' },
    ]
  }
  else if (d === 1) {
    // 难度2：颜色与含义判断 — 文字用什么颜色显示的？选颜色
    const word = randomPick(COLOR_NAMES)
    const color = randomPickExcept(COLOR_NAMES, word) // 确保不一致增加难度
    questionWord.value = word
    questionColor.value = COLOR_MAP[color]
    correctAnswer.value = color

    const wrongOptions = shuffleArray(COLOR_NAMES.filter(c => c !== color)).slice(0, 2)
    options.value = shuffleArray([
      { label: color, value: color },
      ...wrongOptions.map(c => ({ label: c, value: c })),
    ])
  }
  else if (d === 2) {
    // 难度3：双文字关系判断 — 两个色字，它们的"显示颜色"是否相同？
    const word1 = randomPick(COLOR_NAMES)
    const word2 = randomPick(COLOR_NAMES)
    const isSame = Math.random() > 0.5
    const color1 = randomPickExcept(COLOR_NAMES, word1)
    const color2 = isSame ? color1 : randomPickExcept(COLOR_NAMES.filter(c => c !== color1 && c !== word2), word2) || randomPickExcept(COLOR_NAMES, color1)

    questionWord.value = word1
    questionColor.value = COLOR_MAP[color1]
    questionWord2.value = word2
    questionColor2.value = COLOR_MAP[color2]
    correctAnswer.value = isSame ? '相同' : '不同'
    options.value = [
      { label: '相同', value: '相同' },
      { label: '不同', value: '不同' },
    ]
  }
  else if (d === 3) {
    // 难度4：三重关系判断 — 左边文字的"含义"与右边文字的"颜色"是否一致？
    const word1 = randomPick(COLOR_NAMES)
    const color1 = randomPickExcept(COLOR_NAMES, word1) // 左边干扰色
    const isMatch = Math.random() > 0.5
    const word2 = randomPick(COLOR_NAMES)
    // 右边文字的显示颜色 = 左边文字的含义(word1) 或不等
    const color2 = isMatch ? word1 : randomPickExcept(COLOR_NAMES, word1)

    questionWord.value = word1
    questionColor.value = COLOR_MAP[color1]
    questionWord2.value = word2
    questionColor2.value = COLOR_MAP[color2]
    correctAnswer.value = isMatch ? '一致' : '不一致'
    options.value = [
      { label: '一致', value: '一致' },
      { label: '不一致', value: '不一致' },
    ]
  }
  else if (d === 4) {
    // 难度5：带框颜色选择 — 文字在彩色框中，选框的颜色
    const word = randomPick(COLOR_NAMES)
    const textColor = randomPickExcept(COLOR_NAMES, word)
    const borderColor = randomPickExcept(COLOR_NAMES.filter(c => c !== word && c !== textColor), word) || randomPickExcept(COLOR_NAMES, word)

    questionWord.value = word
    questionColor.value = COLOR_MAP[textColor]
    questionBorderColor.value = COLOR_MAP[borderColor]
    correctAnswer.value = borderColor

    const wrongOptions = shuffleArray(COLOR_NAMES.filter(c => c !== borderColor)).slice(0, 2)
    options.value = shuffleArray([
      { label: borderColor, value: borderColor },
      ...wrongOptions.map(c => ({ label: c, value: c })),
    ])
  }

  feedback.value = null
}

function getQuestionHint(): string {
  const d = difficultyIndex.value
  if (d === 0) return '文字含义与显示颜色是否一致？'
  if (d === 1) return '文字用什么颜色显示的？'
  if (d === 2) return '两个字的显示颜色是否相同？'
  if (d === 3) return '左边文字含义与右边文字颜色是否一致？'
  if (d === 4) return '边框是什么颜色？'
  return ''
}

function startGame() {
  round.value = 0
  correct.value = 0
  wrong.value = 0
  elapsed.value = 0
  startTime.value = Date.now()
  state.value = 'playing'

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
  generateQuestion()
}

function handleAnswer(value: string) {
  if (state.value !== 'playing' || feedback.value) return

  if (value === correctAnswer.value) {
    correct.value++
    feedback.value = 'correct'
  }
  else {
    wrong.value++
    feedback.value = 'wrong'
  }

  setTimeout(() => {
    nextRound()
  }, 400)
}

function finishGame() {
  if (timer) { clearInterval(timer); timer = null }
  elapsed.value = Date.now() - startTime.value
  state.value = 'finished'
}

function formatTime(ms: number): string {
  return (ms / 1000).toFixed(1)
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
        <text class="text-lg font-bold tracking-widest">斯特鲁普测试</text>
      </view>
    </view>

    <view class="px-4 pb-8 pt-3">
      <!-- 游戏中 -->
      <view v-if="state === 'playing'">
        <!-- 进度 -->
        <view class="mb-2 flex items-center justify-between px-1">
          <text class="text-[14px] text-[#64748B] font-bold">{{ round }}/{{ TOTAL_ROUNDS }}</text>
          <text class="text-[14px] text-[#64748B] font-bold tabular-nums">{{ formatTime(elapsed) }}s</text>
        </view>
        <view class="mb-4 h-1.5 overflow-hidden rounded-full bg-[#E2E8F0]">
          <view class="h-full rounded-full bg-[#F59E0B] transition-all duration-300" :style="{ width: `${round / TOTAL_ROUNDS * 100}%` }" />
        </view>

        <!-- 提示 -->
        <view class="mb-4 text-center text-[13px] text-[#94A3B8]">
          {{ getQuestionHint() }}
        </view>

        <!-- 题面区域 -->
        <view class="mb-6 flex items-center justify-center gap-5 min-h-[120px]">
          <!-- 主文字 -->
          <view
            class="flex items-center justify-center rounded-2xl px-6 py-5"
            :class="difficultyIndex === 4 ? '' : 'bg-white/90 shadow-sm'"
            :style="difficultyIndex === 4 ? `border: 5px solid ${questionBorderColor}; background: rgba(255,255,255,0.9); box-shadow: 0 2px 10px -4px rgba(0,0,0,0.06);` : ''"
          >
            <text class="text-[48px] font-black" :style="{ color: questionColor }">
              {{ questionWord }}
            </text>
          </view>

          <!-- 第二个文字（难度3/4） -->
          <view
            v-if="difficultyIndex >= 2 && difficultyIndex <= 3"
            class="flex items-center justify-center rounded-2xl bg-white/90 px-6 py-5 shadow-sm"
          >
            <text class="text-[48px] font-black" :style="{ color: questionColor2 }">
              {{ questionWord2 }}
            </text>
          </view>
        </view>

        <!-- 选项 -->
        <view class="grid gap-2" :class="options.length <= 2 ? 'grid-cols-2' : 'grid-cols-3'">
          <view
            v-for="opt in options"
            :key="opt.value"
            class="h-14 flex items-center justify-center rounded-xl text-[18px] font-black shadow-sm transition-all active:scale-95"
            :class="[
              feedback && opt.value === correctAnswer
                ? 'bg-[#059669] text-white'
                : feedback === 'wrong' && opt.value !== correctAnswer
                  ? 'opacity-50 bg-white text-[#1E293B]'
                  : 'bg-white text-[#1E293B]',
            ]"
            @click="handleAnswer(opt.value)"
          >
            {{ opt.label }}
          </view>
        </view>
      </view>

      <!-- 准备 -->
      <view v-if="state === 'ready'" class="mt-2">
        <view class="text-center">
          <view class="mx-auto mb-4 text-[48px]">🎨</view>
          <view class="mb-4 text-[18px] font-black">斯特鲁普测试</view>
        </view>

        <view class="mx-auto mb-5 rounded-xl bg-white/80 px-5 py-4 text-left shadow-sm" style="max-width: 320px">
          <view class="mb-2 text-[14px] text-[#059669] font-bold">规则说明</view>
          <view class="mb-2 text-[13px] text-[#475569] leading-relaxed">
            屏幕上会显示带有颜色的文字
          </view>
          <view class="mb-2 text-[13px] text-[#475569] leading-relaxed">
            需要忽略文字含义，根据文字颜色做出判断
          </view>
          <view class="text-[13px] text-[#475569] leading-relaxed">
            锻炼抑制干扰信息的能力和注意力控制
          </view>
        </view>

        <view class="mb-5">
          <view class="mb-3 text-[14px] text-[#059669] font-bold text-center">选择难度</view>
          <view class="grid grid-cols-3 gap-2 mx-auto" style="max-width: 320px">
            <view
              v-for="(opt, i) in DIFFICULTIES"
              :key="i"
              class="rounded-lg px-2 py-3 text-center active:scale-95"
              :class="difficultyIndex === i ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-white text-[#475569]'"
              @click="difficultyIndex = i"
            >
              <view class="text-[14px] font-black">{{ opt.label }}</view>
              <view class="mt-0.5 text-[11px]" :class="difficultyIndex === i ? 'text-[#FDE68A]/70' : 'text-[#94A3B8]'">
                {{ opt.desc }}
              </view>
            </view>
          </view>
        </view>

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
          <text class="text-[18px] font-black">🎨 测试完成!</text>
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
            用时 {{ formatTime(elapsed) }}s · {{ DIFFICULTIES[difficultyIndex].desc }}
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
