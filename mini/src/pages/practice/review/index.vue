<script lang="ts" setup>
import { computed, reactive, ref } from 'vue'
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'
import { getAppSettings } from '@/utils/appSettings'
import { replaceHtmlWithCachedMedia } from '@/utils/questionMediaCache'

defineOptions({ name: 'PracticeReviewPage' })
definePage({ style: { navigationStyle: 'custom', navigationBarTextStyle: 'black' } })

type UserAnswerValue = string | string[]

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

// ============ 路由参数 ============
const source = ref<'wrong' | 'favorite' | 'note'>('wrong')
const groupBy = ref('')
const groupName = ref('')
const routeParams = ref<Record<string, string>>({})

// ============ 状态 ============
const loading = ref(true)
const questionIds = ref<number[]>([])
const currentIndex = ref(0)
const currentQuestion = ref<any>(null)
const currentSolution = ref<any>(null)
const userAnswer = ref<UserAnswerValue | undefined>(undefined)
const isAnswered = ref(false)
const isCorrect = ref<boolean | null>(null)
const showAnalysis = ref(false)
const removedIds = reactive<Set<number>>(new Set())
const correctStreakMap = reactive<Record<number, number>>({})

// 计算属性
const activeIds = computed(() => questionIds.value.filter(id => !removedIds.has(id)))
const totalCount = computed(() => activeIds.value.length)
const currentQid = computed(() => activeIds.value[currentIndex.value] || 0)
const isLastQuestion = computed(() => currentIndex.value >= totalCount.value - 1)
const isMultiple = computed(() => {
  const type = currentQuestion.value?.type
  return type === 'multiple_choice' || type === 'multi_select'
})
const options = computed(() => currentQuestion.value?.options || [])
const selectedCodes = computed<string[]>(() => {
  if (!userAnswer.value) return []
  return Array.isArray(userAnswer.value) ? userAnswer.value : [userAnswer.value]
})
const correctCodes = computed<string[]>(() => {
  const ans = currentSolution.value?.correct_answer
  if (!ans) return []
  return Array.isArray(ans) ? ans : [ans]
})
const masteryThreshold = computed(() => getAppSettings().wrongMasteryStreak || 3)

const sourceLabel = computed(() => {
  const labels: Record<string, string> = { wrong: '错题练习', favorite: '收藏练习', note: '笔记练习' }
  return labels[source.value] || '复习'
})

// ============ 生命周期 ============
onLoad((query: any) => {
  // uni-app onLoad 的 query 不会自动 decode encodeURIComponent 的值，统一解码
  const decoded: Record<string, string> = {}
  for (const [k, v] of Object.entries(query || {}))
    decoded[k] = decodeURIComponent(v as string)

  source.value = (decoded.source as any) || 'wrong'
  groupBy.value = decoded.group_by || 'bank'
  groupName.value = decoded.group_name || ''
  routeParams.value = decoded
  loadQuestionIds()
})

// ============ 数据加载 ============
async function loadQuestionIds() {
  loading.value = true
  try {
    const collectPayload: Record<string, any> = {
      source_type: source.value,
    }

    if (routeParams.value.bank_id)
      collectPayload.bank_id = Number(routeParams.value.bank_id)
    if (routeParams.value.chapter_id)
      collectPayload.chapter_id = Number(routeParams.value.chapter_id)
    if (routeParams.value.knowledge_point) {
      collectPayload.knowledge_point = String(routeParams.value.knowledge_point)
        .split(',')
        .map(item => item.trim())
        .filter(Boolean)
    }

    const result = await fbaApi.qbank.question.collect(collectPayload as any)

    questionIds.value = Array.isArray(result?.question_ids) ? result.question_ids : []
    currentIndex.value = 0

    if (questionIds.value.length > 0)
      await loadCurrentQuestion()
    else
      loading.value = false
  }
  catch (error) {
    console.error('加载题目列表失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
    loading.value = false
  }
}

async function loadCurrentQuestion() {
  if (!currentQid.value) {
    loading.value = false
    return
  }

  loading.value = true
  resetAnswerState()
  try {
    currentQuestion.value = await fbaApi.qbank.practice.getQuestionDetail(currentQid.value)
  }
  catch (error) {
    console.error('加载题目失败:', error)
    uni.showToast({ title: '加载题目失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

async function loadSolution() {
  if (!currentQid.value || currentSolution.value)
    return
  try {
    currentSolution.value = await fbaApi.qbank.practice.getQuestionAnalysis(currentQid.value)
  }
  catch (error) {
    console.error('加载解析失败:', error)
  }
}

// ============ 答题逻辑 ============
function resetAnswerState() {
  userAnswer.value = undefined
  isAnswered.value = false
  isCorrect.value = null
  showAnalysis.value = false
  currentSolution.value = null
}

function onSelectOption(code: string) {
  if (isAnswered.value)
    return

  if (isMultiple.value) {
    const codes = selectedCodes.value.includes(code)
      ? selectedCodes.value.filter(c => c !== code)
      : [...selectedCodes.value, code]
    userAnswer.value = codes.sort()
  }
  else {
    userAnswer.value = code
    // 单选自动提交
    submitAnswer()
  }
}

async function submitAnswer() {
  if (isAnswered.value || !userAnswer.value)
    return

  isAnswered.value = true
  await loadSolution()

  // 判对错
  const userCodes = selectedCodes.value.sort()
  const correctAnswerCodes = correctCodes.value.sort()
  isCorrect.value = userCodes.length === correctAnswerCodes.length
    && userCodes.every((c, i) => c === correctAnswerCodes[i])

  showAnalysis.value = true

  // 错题模式：答对后调 increment_correct
  if (source.value === 'wrong' && isCorrect.value) {
    await handleWrongQuestionCorrect()
  }
}

async function handleWrongQuestionCorrect() {
  const qid = currentQid.value
  const streak = (correctStreakMap[qid] || 0) + 1
  correctStreakMap[qid] = streak

  try {
    await fbaApi.qbank.wrongQuestion.answerCorrect(qid, { mastery_threshold: masteryThreshold.value })

    if (streak >= masteryThreshold.value) {
      removedIds.add(qid)
      uni.showToast({ title: '已掌握，自动移除', icon: 'success', duration: 1500 })
    }
  }
  catch (error) {
    console.error('更新错题状态失败:', error)
  }
}

function goNext() {
  if (currentIndex.value < totalCount.value - 1) {
    currentIndex.value++
    loadCurrentQuestion()
  }
  else {
    // 全部做完
    uni.showToast({ title: '已全部做完！', icon: 'success' })
    setTimeout(() => goBack(), 1500)
  }
}

function goPrev() {
  if (currentIndex.value > 0) {
    currentIndex.value--
    loadCurrentQuestion()
  }
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.switchTab({ url: '/pages/mine/index' })
}

function getOptionClass(code: string) {
  if (!isAnswered.value) {
    return selectedCodes.value.includes(code)
      ? 'border-[#3B82F6] bg-[#EFF6FF]'
      : 'border-[#E2E8F0] bg-white'
  }
  const isSelected = selectedCodes.value.includes(code)
  const isCorrectOption = correctCodes.value.includes(code)

  if (isCorrectOption)
    return 'border-[#16A34A] bg-[#ECFDF5]'
  if (isSelected && !isCorrectOption)
    return 'border-[#DC2626] bg-[#FEF2F2]'
  return 'border-[#E2E8F0] bg-white/60 opacity-60'
}

function getOptionIcon(code: string) {
  if (!isAnswered.value) {
    return selectedCodes.value.includes(code) ? 'i-carbon-checkbox-checked text-[#3B82F6]' : 'i-carbon-checkbox text-[#94A3B8]'
  }
  const isSelected = selectedCodes.value.includes(code)
  const isCorrectOption = correctCodes.value.includes(code)

  if (isCorrectOption) return 'i-carbon-checkmark-filled text-[#16A34A]'
  if (isSelected && !isCorrectOption) return 'i-carbon-close-filled text-[#DC2626]'
  return 'i-carbon-checkbox text-[#94A3B8]/40'
}

function stripHtml(html: string) {
  return html?.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim() || ''
}
</script>

<template>
  <view class="relative min-h-screen bg-[#F8FAFC] text-[#334155]">
    <!-- 顶部导航 -->
    <view class="fixed left-0 right-0 top-0 z-50 bg-white/95 shadow-sm backdrop-blur-md" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-[15px] text-[#1E293B] font-bold">{{ groupName || sourceLabel }}</text>
        <text class="absolute right-4 text-[13px] text-[#94A3B8]">
          {{ totalCount > 0 ? `${currentIndex + 1}/${totalCount}` : '' }}
        </text>
      </view>
    </view>

    <!-- 内容区域 -->
    <view class="px-4 pb-28" :style="{ paddingTop: `${(statusBarHeight || 20) + 56}px` }">
      <!-- loading -->
      <view v-if="loading && !currentQuestion" class="flex flex-col items-center justify-center py-32">
        <text class="text-[14px] text-[#94A3B8]">加载中...</text>
      </view>

      <!-- 空状态 -->
      <view v-else-if="totalCount === 0" class="flex flex-col items-center justify-center py-32">
        <view class="i-carbon-checkmark-outline mb-4 text-6xl text-[#16A34A]" />
        <text class="text-[16px] text-[#1E293B] font-bold">全部完成！</text>
        <text class="mt-2 text-[13px] text-[#94A3B8]">当前分组下已没有更多题目</text>
      </view>

      <!-- 题目卡片 -->
      <view v-else-if="currentQuestion" class="flex flex-col gap-4">
        <!-- 题干 -->
        <view class="rounded-2xl bg-white p-5 shadow-sm">
          <view class="mb-3 flex items-center gap-2">
            <text class="rounded-full bg-[#EFF6FF] px-2.5 py-0.5 text-[11px] text-[#3B82F6] font-bold">
              {{ currentQuestion.type_label || currentQuestion.type || '单选' }}
            </text>
            <text v-if="currentQuestion.difficulty" class="rounded-full bg-[#F8FAFC] px-2.5 py-0.5 text-[11px] text-[#64748B]">
              {{ currentQuestion.difficulty_label || currentQuestion.difficulty }}
            </text>
          </view>
          <rich-text class="text-[15px] text-[#1E293B] font-medium leading-[1.8]" :nodes="replaceHtmlWithCachedMedia(currentQuestion.stem)" />
        </view>

        <!-- 选项列表 -->
        <view class="flex flex-col gap-2.5">
          <view
            v-for="opt in options"
            :key="opt.code"
            class="flex items-start gap-3 rounded-xl border-2 px-4 py-3.5 transition-all"
            :class="getOptionClass(opt.code)"
            @click="onSelectOption(opt.code)"
          >
            <view class="mt-0.5 text-[18px]" :class="getOptionIcon(opt.code)" />
            <view class="min-w-0 flex-1">
              <text class="text-[14px] text-[#1E293B] font-medium leading-[1.6]">
                {{ opt.code }}. {{ stripHtml(opt.content) }}
              </text>
            </view>
          </view>
        </view>

        <!-- 多选确认按钮 -->
        <view v-if="isMultiple && !isAnswered && selectedCodes.length > 0" class="mt-2">
          <view
            class="flex items-center justify-center rounded-xl bg-[#3B82F6] py-3 text-[15px] text-white font-bold shadow-md active:opacity-80"
            @click="submitAnswer"
          >
            确认提交
          </view>
        </view>

        <!-- 答题结果 -->
        <view v-if="isAnswered" class="rounded-2xl p-4" :class="isCorrect ? 'bg-[#ECFDF5]' : 'bg-[#FEF2F2]'">
          <view class="flex items-center gap-2">
            <view :class="isCorrect ? 'i-carbon-checkmark-filled text-[20px] text-[#16A34A]' : 'i-carbon-close-filled text-[20px] text-[#DC2626]'" />
            <text class="text-[15px] font-bold" :class="isCorrect ? 'text-[#16A34A]' : 'text-[#DC2626]'">
              {{ isCorrect ? '回答正确' : '回答错误' }}
            </text>
            <text class="ml-auto text-[12px] text-[#94A3B8]">
              正确答案：{{ correctCodes.join(', ') }}
            </text>
          </view>
        </view>

        <!-- 解析区域 -->
        <view v-if="showAnalysis && currentSolution" class="rounded-2xl bg-white p-5 shadow-sm">
          <text class="mb-3 block text-[14px] text-[#3B82F6] font-bold">解析</text>
          <rich-text class="text-[13px] text-[#475569] leading-[1.8]" :nodes="replaceHtmlWithCachedMedia(currentSolution.analysis || currentSolution.explanation || '暂无解析')" />
        </view>
      </view>
    </view>

    <!-- 底部操作栏 -->
    <view v-if="totalCount > 0" class="fixed bottom-0 left-0 right-0 z-50 border-t border-[#F1F5F9] bg-white/95 px-6 pb-[env(safe-area-inset-bottom)] backdrop-blur-md">
      <view class="flex items-center justify-between py-3">
        <view
          class="h-10 w-10 flex items-center justify-center rounded-full active:opacity-60"
          :class="currentIndex > 0 ? 'bg-[#F1F5F9]' : 'opacity-30'"
          @click="goPrev"
        >
          <view class="i-carbon-chevron-left text-[18px] text-[#475569]" />
        </view>

        <view class="flex items-center gap-2">
          <text class="text-[13px] text-[#94A3B8]">
            {{ currentIndex + 1 }} / {{ totalCount }}
          </text>
        </view>

        <view v-if="isAnswered">
          <view
            class="rounded-full bg-[#3B82F6] px-6 py-2 text-[14px] text-white font-bold shadow-md active:opacity-80"
            @click="goNext"
          >
            {{ isLastQuestion ? '完成' : '下一题' }}
          </view>
        </view>
        <view v-else class="h-10 w-10" />
      </view>
    </view>
  </view>
</template>
