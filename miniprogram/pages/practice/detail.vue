<template>
  <!-- 页面元数据：控制页面滚动 -->
  <page-meta :page-style="isSheetVisible || showConfirmDialog ? 'overflow: hidden' : ''"></page-meta>

  <view class="practice-page">
    <HeaderPanel
      :title="practiceName"
      :current="currentStep"
      :total="totalSteps"
      :time-text="timeText"
      :view-mode="viewMode"
      :is-paused="isPaused"
      @show-sheet="openAnswerSheet"
      @toggle-pause="timer.togglePause"
    />

    <!-- 原生 swiper -->
    <view
      class="swiper-container"
      @touchstart="handleTouchStart"
      @touchend="handleTouchEnd"
    >
      <swiper
        v-if="displayQuestions.length > 0"
        class="question-swiper"
        :style="{ height: swiperHeight }"
        :current="currentIndex"
        @change="handleSwiperChange"
      >
        <swiper-item v-for="(item, index) in displayQuestions" :key="item.question.id">
          <view class="swiper-item-content">
            <QuestionCard
              :question="item.question"
              :mode="mode"
              :value="getQuestionAnswer(item.originalIndex)"
              :analysis-visible="shouldShowAnalysis(item.originalIndex)"
              :is-collected="questionCollected.get(item.originalIndex) || false"
              :should-show-confirm="getShouldShowConfirm(item.question) && !shouldShowAnalysis(item.originalIndex)"
              :correct-answer="questionSolutions.get(item.originalIndex)?.correct_answer || item.question.answer"
              :loading="false"
              @select="(value: string) => handleSelect(item.originalIndex, value)"
              @confirm="handleConfirm"
              @toggle-collect="toggleCollect"
            />

            <!-- 解析面板 -->
            <!-- 🔥 性能优化：只渲染当前题和前后各2题的解析面板 -->
            <AnalysisPanel
              v-if="shouldShowAnalysis(item.originalIndex) && answerRecords.has(item.originalIndex) && Math.abs(index - (currentStep - 1)) <= 2"
              :question="item.question"
              :user-answer="getQuestionAnswer(item.originalIndex)"
              :is-correct="answerRecords.get(item.originalIndex)?.isCorrect || false"
              :answer-time="answerRecords.get(item.originalIndex)?.answerTime || 0"
              :total-attempts="0"
              :correct-rate="getCorrectRate(item.originalIndex)"
              :common-mistakes="getCommonMistakes(item.originalIndex)"
              :analysis="questionSolutions.get(item.originalIndex)?.analysis || item.question.analysis"
              :correct-answer="questionSolutions.get(item.originalIndex)?.correct_answer || item.question.answer"
              :similar-questions="[]"
              :is-collected="questionCollected.get(item.originalIndex) || false"
              :is-marked-wrong="questionMarkedWrong.get(item.originalIndex) || false"
              :note-text="questionNotes.get(item.originalIndex) || ''"
              :note-is-public="questionNoteIsPublic.get(item.originalIndex) || false"
              :public-notes="questionPublicNotes.get(item.originalIndex) || []"
              @toggle-collect="toggleCollect"
              @toggle-wrong-book="toggleWrongBook"
              @add-to-set="handleAddToSet"
              @update-note="handleUpdateNote"
              @go-to-question="handleGoToSimilarQuestion"
              @load-public-notes="handleLoadPublicNotes"
              @vote-note="handleVoteNote"
            />
          </view>
        </swiper-item>
      </swiper>

      <QuestionSkeleton v-else />
    </view>

    <!-- 答题卡 -->
    <AnswerSheet
      :visible="isSheetVisible"
      :items="answerSheetItems"
      :total-count="totalSteps"
      :is-dark="isDarkMode"
      :show-submit="mode !== 'memorize'"
      @close="closeAnswerSheet"
      @select-item="handleSelectSheetItem"
      @submit="handleSubmitAll"
    />

    <!-- 确认提交对话框 -->
    <up-modal
      :show="showConfirmDialog"
      title="提示"
      :content="confirmDialogMessage"
      show-cancel-button
      @confirm="handleConfirmSubmit"
      @cancel="handleCancelSubmit"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onHide } from '@dcloudio/uni-app'

import AnswerSheet from './modules/AnswerSheet.vue'
import HeaderPanel from '../../components/business/HeaderPanel.vue'
import QuestionCard from '../../components/business/QuestionCard.vue'
import AnalysisPanel from '../../components/business/AnalysisPanel.vue'
import QuestionSkeleton from '../../components/business/QuestionSkeleton.vue'
import type { BaseQuestion, PracticeMode } from '../../components/business/question-map'
import { adaptQuestionList, adaptListToComponentFormat } from '../../utils/question-adapter-v2'
import { questionApiV2, practiceApi, authApi, bankApi, chapterApi, favoriteApi, noteApi, setToken } from '@/api'
import type { QuestionSolution } from '@/api/types/question-v2'
import {
  useTimer,
  useAnswerSheet,
  usePracticeDetail,
  useSystemInfo,
  type AnswerSheetItem,
  type AnswerRecord
} from '@/composables'
import { formatDuration as formatDurationUtil } from '../../utils/format'
import { usePracticeStore } from '../../stores/practice'

declare const uni: any

declare const document: Document & {
  body?: HTMLElement & { getAttribute: (qualifiedName: string) => string | null }
}

// ============ Composables 初始化 ============
const timer = useTimer()
const answerSheet = useAnswerSheet()
const { calculateSwiperHeight } = useSystemInfo()
const practiceStore = usePracticeStore()

const practice = usePracticeDetail({
  onTimerReset: () => timer.reset(),
  getElapsedSeconds: () => timer.getElapsedSeconds(),
  getCurrentPausedDuration: () => timer.getCurrentPausedDuration(),
})

// 解构常用状态
const {
  practiceName,
  loading,
  allQuestions,
  currentBankId,
  currentSessionId,
  answerRecords,
  questionCollected,
  questionMarkedWrong,
  questionNotes,
  questionNoteIds,
  questionNoteIsPublic,
  questionStartTime,
  questionStartPausedDuration,
} = practice

const { timeText, isPaused, pausedDuration } = timer
const isSheetVisible = answerSheet.isVisible

// ============ 页面状态 ============
const swiperHeight = ref('500px')
const currentStep = ref(1)
const totalSteps = computed(() => displayQuestions.value.length)
const currentCatId = ref<number | null>(null)  // 当前题库的分类 ID（用于刷新统计）

// ============ 笔记状态（公开笔记单独维护） ============
const currentUserId = ref<number | null>(null)  // 当前用户 ID
const questionPublicNotes = ref<Map<number, any[]>>(new Map())  // 公开笔记映射（questionIndex -> PublicNote[]）

// 当 loading 变为 false 时重新计算高度
watch(loading, (newVal) => {
  if (!newVal) {
    setTimeout(() => {
      calculateSwiperHeight('.swiper-container', (height) => {
        swiperHeight.value = height
      })
    }, 50)
  }
})

// ============ 模式相关 ============
const mode = ref<PracticeMode>('practice')
const currentAnswer = ref('')
const viewMode = ref<'all' | 'wrong' | null>(null)
const originalMode = ref<PracticeMode>('practice')

// 🔥 练题模式：存储每道题的 solution 数据（correct_answer + analysis）
const questionSolutions = ref<Map<number, QuestionSolution>>(new Map())

// 是否显示解析（改为函数，基于每个题目的状态判断）
function shouldShowAnalysis(questionIndex: number): boolean {
  // 背题模式：始终显示
  if (mode.value === 'memorize') return true

  // 查看模式：始终显示
  if (viewMode.value !== null) return true

  // 练题模式：检查该题是否已提交
  if (mode.value === 'exercise') {
    const record = answerRecords.value.get(questionIndex)
    return record ? (record.submitted ?? true) : false
  }

  return false
}

// 结果数据
const resultData = ref({
  score: 0,
  totalCount: 0,
  correctCount: 0,
  wrongCount: 0,
  wrongQuestions: [] as number[]
})

// ============ UI 状态 ============
const THEME_STORAGE_KEY = 'app-theme'
const isDarkMode = ref(false)
const showConfirmDialog = ref(false)
const confirmDialogMessage = ref('')
const unansweredCountForDialog = ref(0)

// 触摸事件状态
const touchStartX = ref(0)
const touchStartY = ref(0)
const touchStartStep = ref(0)

watch(isSheetVisible, (visible) => {
  if (typeof document === 'undefined') {
    return
  }
  if (visible) {
    document.body.classList.add('u-body--locked')
    return
  }
  document.body.classList.remove('u-body--locked')
})

// 显示的题目列表（根据 viewMode 过滤）
const displayQuestions = computed(() => {
  if (loading.value) {
    return []
  }

  if (viewMode.value === 'wrong') {
    return allQuestions.value
      .map((q, index) => ({ question: q, originalIndex: index + 1 }))
      .filter(item => {
        const record = answerRecords.value.get(item.originalIndex)
        return !record || !record.isCorrect
      })
  }
  return allQuestions.value.map((q, index) => ({ question: q, originalIndex: index + 1 }))
})

// 当前题目
const question = computed<BaseQuestion | undefined>(() => {
  if (displayQuestions.value.length === 0) {
    return undefined
  }
  const index = currentStep.value - 1
  const item = displayQuestions.value[index]
  return item?.question || displayQuestions.value[0]?.question
})

// 当前题目的原始索引（用于获取答案记录）
const currentOriginalIndex = computed(() => {
  if (displayQuestions.value.length === 0) {
    return 1
  }
  const index = currentStep.value - 1
  const item = displayQuestions.value[index]
  return item?.originalIndex || 1
})

// 获取指定题目的答案
function getQuestionAnswer(questionIndex: number): string {
  const answer = answerRecords.value.get(questionIndex)?.answer
  if (!answer) return ''
  // 🔥 如果是数组（多选题），转换为逗号分隔的字符串
  if (Array.isArray(answer)) {
    return answer.join(',')
  }
  return answer
}

// 判断指定题目是否应该显示确定按钮
function getShouldShowConfirm(question: BaseQuestion | undefined): boolean {
  if (!question) return false

  // 背题模式：不显示按钮
  if (mode.value === 'memorize') return false

  // 单选题和判断题：任何模式下都不显示按钮（自动提交）
  const isAutoSubmitType = question.type === 'single' || question.type === 'judgement'
  if (isAutoSubmitType) return false

  // 其他题型：练题模式和刷题模式都显示按钮
  return true
}

// ============ 解析面板数据 ============

/**
 * 获取指定题目的全站正确率
 */
function getCorrectRate(questionIndex: number): number {
  const solution = questionSolutions.value.get(questionIndex)
  return solution?.correct_rate ? Number(solution.correct_rate) : 0
}

/**
 * 获取指定题目的易错项（返回错选最多的选项，最多3个）
 */
function getCommonMistakes(questionIndex: number): Array<{ option: string; description: string }> {
  const solution = questionSolutions.value.get(questionIndex)
  if (!solution?.wrong_option_stats) return []

  // 将对象转换为数组并按错误次数排序，取前3个
  const mistakes = Object.entries(solution.wrong_option_stats)
    .map(([option, count]) => ({ option, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 3)  // 最多显示前3个错选最多的选项

  // 🔥 只返回选项字母，不显示人数
  return mistakes.map(m => ({
    option: m.option,
    description: ''
  }))
}

// ============ 答题卡相关 ============
// 答题卡状态完全由 answerRecords 计算得出，无需单独维护
const answerSheetItems = computed<AnswerSheetItem[]>(() => {
  // 🔥 修复：遍历 displayQuestions，使用 originalIndex 查询记录
  return displayQuestions.value.map((item, idx) => {
    const originalIndex = item.originalIndex
    const record = answerRecords.value.get(originalIndex)
    let status: AnswerSheetStatus = 'unselected'

    if (record) {
      // 刷题模式 + 未提交（viewMode === null）：显示 selected
      if (mode.value === 'practice' && viewMode.value === null) {
        status = 'selected'
      } else {
        // 其他模式或已提交：显示 correct/wrong
        status = record.isCorrect ? 'correct' : 'wrong'
      }
    }

    return {
      index: originalIndex,  // 使用原始索引
      status,
      isCurrent: (idx + 1) === currentStep.value  // 当前步骤基于显示列表
    }
  })
})

// ============ 辅助函数 ============
// 计算时长文本（毫秒转为可读格式）
function formatDuration(milliseconds: number): string {
  const seconds = Math.floor(milliseconds / 1000)
  return formatDurationUtil(seconds)
}

// 构建答题结果项
function buildAnswerItems(questionCount: number) {
  return Array.from({ length: questionCount }, (_, idx) => {
    const index = idx + 1
    const record = answerRecords.value.get(index)
    const question = allQuestions.value[idx]

    let status: 'correct' | 'wrong' | 'unanswered' = 'unanswered'
    if (record) {
      status = record.isCorrect ? 'correct' : 'wrong'
    }

    return {
      index,
      questionId: question?.id ? parseInt(question.id) : 0,  // 添加 questionId
      status
    }
  })
}

// 准备结算数据
function prepareResultData(useOriginalMode = false) {
  const questionCount = allQuestions.value.length
  const durationText = formatDuration(timer.getElapsedMs())
  const answerItems = buildAnswerItems(questionCount)
  const unanswered = questionCount - answerRecords.value.size

  return {
    practiceName: practiceName.value,
    totalCount: questionCount,
    correctCount: resultData.value.correctCount,
    wrongCount: resultData.value.wrongCount,
    unansweredCount: unanswered,
    duration: durationText,
    answerItems,
    bankId: currentBankId.value,
    mode: useOriginalMode ? originalMode.value : mode.value,
    wrongQuestions: resultData.value.wrongQuestions
  }
}

// 进入查看模式
function enterViewMode(viewModeType: 'all' | 'wrong', title: string) {
  originalMode.value = mode.value
  viewMode.value = viewModeType
  mode.value = 'exercise'
  currentStep.value = 1
}

// 同步题目切换后的状态
function syncQuestionState() {
  currentAnswer.value = answerRecords.value.get(currentOriginalIndex.value)?.answer || ''
}

// ============ 答题逻辑 ============
function handleSelect(questionIndex: number, value: string) {
  // 更新指定题目的答案记录
  const existingRecord = answerRecords.value.get(questionIndex)
  if (existingRecord) {
    existingRecord.answer = value
  } else {
    answerRecords.value.set(questionIndex, {
      questionId: allQuestions.value[questionIndex - 1]?.id || '',
      answer: value,
      isCorrect: false,
      score: 0,
      submitted: false  // 标记为未提交（输入中状态）
    })
  }

  // 同步 currentAnswer（用于实时显示）
  if (questionIndex === currentOriginalIndex.value) {
    currentAnswer.value = value
  }

  // 背题模式：不自动提交
  if (mode.value === 'memorize') return

  // 单选题和判断题：选中后立即提交（刷题和练题模式）
  const currentQuestion = allQuestions.value[questionIndex - 1]
  const isAutoSubmitType = currentQuestion?.type === 'single' || currentQuestion?.type === 'judgement'

  if (questionIndex === currentOriginalIndex.value && isAutoSubmitType) {
    handleConfirm()
  }
}

function handleConfirm() {
  if (!currentAnswer.value || !question.value) {
    uni.showToast({
      title: '请先作答',
      icon: 'none'
    })
    return
  }

  // 🔥 修改：不判题，只记录答案和答题时长
  const questionScore = 1

  // 计算答题时长（扣除暂停时间）
  const questionStartTimeValue = questionStartTime.value.get(currentOriginalIndex.value) || Date.now()
  const questionStartPausedValue = questionStartPausedDuration.value.get(currentOriginalIndex.value) || 0
  const currentPausedTotal = timer.getCurrentPausedDuration()
  const actualElapsed = Date.now() - questionStartTimeValue - (currentPausedTotal - questionStartPausedValue)
  const answerTime = Math.floor(actualElapsed / 1000)

  // 🔥 根据题型格式化答案（多选题需要转换为数组）
  let formattedAnswer: string | string[]
  if (question.value.type === 'multiple') {
    // 多选题：将逗号分隔的字符串转换为数组
    formattedAnswer = currentAnswer.value.split(',').filter(v => v.trim())
  } else {
    // 其他题型：保持字符串格式
    formattedAnswer = currentAnswer.value
  }

  // 🔥 练题模式：先设置 submitted=false，等获取 solution 后再设置为 true
  const record: AnswerRecord = {
    questionId: question.value.id,
    answer: formattedAnswer,
    isCorrect: false,  // 临时值，submit 时后端会判题
    score: 0,  // 临时值
    answerTime,
    submitted: mode.value !== 'exercise'  // 练题模式先设为 false
  }
  answerRecords.value.set(currentOriginalIndex.value, record)

  // 🔥 实时保存答题记录到后端（不传 is_correct）
  practice.saveAnswerRecord(record, viewMode.value)

  // 🔥 练题模式：调用 solution API 获取解析
  if (mode.value === 'exercise') {
    fetchQuestionSolution(parseInt(question.value.id))
  }

  if (mode.value === 'practice') {
    setTimeout(() => {
      if (currentStep.value < totalSteps.value) {
        handleNextQuestion()
      } else {
        // 最后一题答完后，弹出答题卡
        openAnswerSheet()
      }
    }, 300)
  }
}

/**
 * 获取题目答案和解析（练题模式专用）
 *
 * :param questionId: 题目 ID
 */
async function fetchQuestionSolution(questionId: number) {
  try {
    const record = answerRecords.value.get(currentOriginalIndex.value)
    if (!record) return

    // 🔥 将用户答案转换为字符串格式（传给后端）
    const userAnswerStr = Array.isArray(record.answer)
      ? JSON.stringify(record.answer)
      : record.answer

    // 🔥 调用 solution API，传入用户答案，后端判题并返回结果
    const solution = await questionApiV2.getQuestionSolution(questionId, userAnswerStr)

    // 存储 solution 数据到 Map 中（使用题号索引，与 answerRecords 保持一致）
    questionSolutions.value.set(currentOriginalIndex.value, solution)

    // 🔥 使用后端判题结果，更新 answerRecord（创建新对象以触发 Vue 响应式）
    if (solution.is_correct !== undefined && solution.is_correct !== null) {
      answerRecords.value.set(currentOriginalIndex.value, {
        ...record,
        isCorrect: solution.is_correct,
        score: solution.is_correct ? 1 : 0,
        submitted: true  // 🔥 获取到 solution 后才设置为已提交
      })
    }
  } catch (error) {
    console.error('[练题模式] 获取 solution 失败:', error)
    // 🔥 获取失败时也要设置为已提交，否则解析面板不会显示
    const record = answerRecords.value.get(currentOriginalIndex.value)
    if (record) {
      answerRecords.value.set(currentOriginalIndex.value, {
        ...record,
        submitted: true
      })
    }
  }
}

function calculateResult() {
  let totalScore = 0
  let correctCount = 0
  let wrongCount = 0
  const wrongQuestions: number[] = []

  answerRecords.value.forEach((record, questionIndex) => {
    totalScore += record.score
    if (record.isCorrect) {
      correctCount++
    } else {
      wrongCount++
      wrongQuestions.push(questionIndex)
    }
  })

  resultData.value = {
    score: totalScore,
    totalCount: allQuestions.value.length,
    correctCount,
    wrongCount,
    wrongQuestions: wrongQuestions.sort((a, b) => a - b)
  }
}

function handleGoToQuestion(index: number) {
  currentStep.value = index + 1
  syncQuestionState()
}

// ============ 用户登录 ============
async function ensureLoggedIn(): Promise<boolean> {
  try {
    await authApi.getCurrentUser()
    return true
  } catch (error) {
    try {
      const res = await authApi.testLogin({
        username: 'test_user',
        nickname: '测试用户'
      })
      setToken(res.access_token)
      return true
    } catch (loginError) {
      console.error('自动登录失败:', loginError)
      uni.showToast({
        title: '登录失败，请稍后重试',
        icon: 'none'
      })
      return false
    }
  }
}

// ============ 用户信息加载 ============
async function loadCurrentUser(): Promise<void> {
  try {
    const userInfo = await authApi.getCurrentUser()
    // UserInfo.id 是 string，需要转换为 number
    currentUserId.value = parseInt(userInfo.id)
  } catch (error) {
    console.error('[加载用户信息失败]:', error)
  }
}

// ============ 公开笔记加载 ============

/**
 * 🔥 加载公开笔记（用户点击公开笔记 tab 时调用）
 */
async function handleLoadPublicNotes(): Promise<void> {
  const currentQuestion = allQuestions.value[currentOriginalIndex.value - 1]
  if (!currentQuestion?.id) {
    console.error('[加载公开笔记] 题目ID不存在')
    return
  }

  const questionId = parseInt(currentQuestion.id)

  try {
    // 加载公开笔记（包含精选和非精选）
    const publicNotes = await noteApi.getPublicNotes(questionId, undefined)
    if (publicNotes && publicNotes.length > 0) {
      // 转换为 AnalysisPanel 需要的格式（包含 id 和 avatar）
      const formattedNotes = publicNotes.map(note => ({
        id: note.id,  // 🔥 笔记 ID（用于点赞）
        author: note.user_nickname || '匿名用户',
        avatar: note.user_avatar || undefined,  // 🔥 用户头像
        time: new Date(note.updated_time).toLocaleDateString(),
        content: note.content,
        likes: note.like_count,
        userVoted: undefined  // 🔥 TODO: 加载用户投票状态
      }))
      questionPublicNotes.value.set(currentOriginalIndex.value, formattedNotes)
    } else {
      // 清空公开笔记（避免显示旧数据）
      questionPublicNotes.value.set(currentOriginalIndex.value, [])
    }
  } catch (error) {
    console.error('[加载公开笔记失败]:', error)
    uni.showToast({
      title: '加载公开笔记失败',
      icon: 'none',
      duration: 2000
    })
  }
}

/**
 * 🔥 处理笔记点赞
 *
 * :param noteId: 笔记 ID
 * :param voteValue: 投票值（1=点赞，null=取消点赞）
 */
async function handleVoteNote(noteId: number, voteValue: 1 | -1 | null): Promise<void> {
  try {
    if (voteValue === null) {
      // 取消点赞
      await noteApi.cancelVote(noteId)
      uni.showToast({
        title: '已取消点赞',
        icon: 'none',
        duration: 1500
      })
    } else {
      // 点赞
      await noteApi.voteNote(noteId, voteValue)
      uni.showToast({
        title: '点赞成功',
        icon: 'success',
        duration: 1500
      })
    }

    // 🔥 刷新公开笔记列表（更新点赞数）
    await handleLoadPublicNotes()
  } catch (error) {
    console.error('[笔记点赞失败]:', error)
    uni.showToast({
      title: '操作失败，请重试',
      icon: 'none',
      duration: 2000
    })
  }
}

// ============ 加载题目 ============
async function loadQuestions(bankId: number, chapterId?: number) {
  // 🔥 背题模式：不创建会话，直接加载带答案的题目
  if (mode.value === 'memorize') {
    const success = await practice.loadMemorizeQuestions({
      bank_id: bankId,
      chapter_id: chapterId
    })
    if (success) {
      currentStep.value = 1
      // 🔥 背题模式也需要启动计时器
      timer.start()
    }
    return
  }

  // 🔥 刷题/练题模式：创建会话
  const success = await practice.startPractice({
    session_type: chapterId ? 'chapter' : 'bank',
    bank_id: bankId,
    chapter_id: chapterId
  })

  if (success) {
    // 重置当前步骤为 1，确保 swiper 从第一题开始
    currentStep.value = 1
    // 🔥 新练习：启动计时器（从 0 开始）
    timer.start()
  }
}

/**
 * 将 solution 数据的选项列表转换为 session 数据的选项字典
 *
 * @param optionsList solution 格式：[{code: 'A', content: '...'}, ...]
 * @return session 格式：{A: {code: 'A', content: '...'}, ...}
 */
function convertOptionsListToDict(optionsList: any[]): Record<string, any> {
  const dict: Record<string, any> = {}
  optionsList.forEach((option) => {
    if (option.code) {
      dict[option.code] = option
    }
  })
  return dict
}

/**
 * 加载历史会话（查看历史记录时使用）
 *
 * :param sessionId: 会话 ID
 * :param viewModeParam: 查看模式
 * :param gotoIndex: 跳转到的题目索引
 */
async function loadHistorySession(sessionId: number, viewModeParam?: string, gotoIndex?: string) {
  try {
    loading.value = true
    currentSessionId.value = sessionId

    // 🔥 优先使用缓存的解析数据（从 ResultSummary 页面缓存）
    let cachedSolution = uni.getStorageSync('practice-solution')
    let solutionData: any = null

    if (cachedSolution && cachedSolution.session_id === sessionId) {
      // 使用缓存的解析数据
      console.log('[查看历史] 使用缓存的解析数据')
      solutionData = cachedSolution
      // 清除缓存（一次性使用）
      uni.removeStorageSync('practice-solution')
    } else {
      // 没有缓存，调用 getSolution API 获取
      console.log('[查看历史] 调用 getSolution API 获取解析数据')
      solutionData = await practiceApi.getSessionSolution(sessionId)
    }

    const questions = solutionData.questions || []

    // 检查题目数据
    if (!questions.length) {
      uni.showToast({ title: '该会话没有题目数据', icon: 'none', duration: 2000 })
      setTimeout(() => uni.navigateBack(), 2000)
      return
    }

    // 🔥 将 solution 格式转换为内部标准格式（QuestionWithAnswer）
    const adaptedQuestions = questions.map((q: any) => ({
      id: q.question_id,
      stem: q.content,  // solution 用 content
      type: q.type,
      options_data: q.options ? convertOptionsListToDict(q.options) : null,  // list → dict
      answer_data: q.correct_answer ? { correct: q.correct_answer } : null,
      analysis_content: q.analysis,
      // 保留用户答案信息
      user_answer: q.user_answer,
      is_correct: q.is_correct,
      answer_time: q.answer_time || 0
    }))

    // 转换为前端格式
    const frontendQuestions = adaptQuestionList(adaptedQuestions as any, true)
    allQuestions.value = adaptListToComponentFormat(frontendQuestions)
    if (!practiceName.value || practiceName.value === '加载中...') {
      practiceName.value = '练习'
    }

    // 🔥 从 solution 数据恢复答题记录
    answerRecords.value.clear()
    questions.forEach((q: any, index: number) => {
      if (q.user_answer !== null && q.user_answer !== undefined) {
        answerRecords.value.set(index + 1, {
          questionId: String(q.question_id),
          answer: typeof q.user_answer === 'string' ? q.user_answer : q.user_answer.join(','),
          isCorrect: q.is_correct ?? false,
          score: q.is_correct ? 1 : 0,
          answerTime: q.answer_time || 0
        })
      }
    })

    // 设置查看模式
    originalMode.value = mode.value
    mode.value = 'exercise'

    if (viewModeParam === 'wrong') {
      viewMode.value = 'wrong'
    } else {
      viewMode.value = 'all'
    }

    // 设置当前题目索引
    if (gotoIndex) {
      currentStep.value = Number(gotoIndex)  // gotoIndex 已经是 1-based（题号），直接使用
    } else {
      currentStep.value = 1
    }

    // 批量查询收藏状态
    await practice.initializeFavoriteStatus()
  } catch (error) {
    console.error('[查看历史] 加载失败:', error)
    uni.showToast({ title: '加载历史失败', icon: 'none', duration: 2000 })
    setTimeout(() => uni.navigateBack(), 2000)
  } finally {
    loading.value = false
  }
}

/**
 * 恢复未完成的练习会话（继续答题）
 */
async function resumeInProgressSession(sessionId: number) {
  try {
    loading.value = true
    currentSessionId.value = sessionId

    // 🔥 获取会话详情（包含题目和答案解析）
    const session = await practiceApi.getSession(sessionId)
    currentBankId.value = session.bank_id || null
    const questionIds = session.question_ids || []
    const questions = (session as any).questions || []

    if (!questions.length) {
      uni.showToast({ title: '该会话没有题目数据', icon: 'none', duration: 2000 })
      setTimeout(() => uni.navigateBack(), 2000)
      return
    }

    // 🔥 直接使用会话返回的题目列表（已按 question_ids 顺序排列，含答案解析）
    const frontendQuestions = adaptQuestionList(questions as any, true)
    allQuestions.value = adaptListToComponentFormat(frontendQuestions)
    practiceName.value = session.practice_name || '练习'

    // 获取已有的答题记录
    const records = await practiceApi.getSessionRecords(sessionId)

    // 构建 question_id -> record 的映射
    const recordMap = new Map<number, any>()
    records.forEach(record => {
      recordMap.set(record.question_id, record)
    })

    // 恢复答题记录到 answerRecords
    answerRecords.value.clear()
    questionIds.forEach((questionId, index) => {
      const record = recordMap.get(questionId)
      if (record) {
        answerRecords.value.set(index + 1, {
          questionId: String(questionId),
          answer: typeof record.user_answer === 'string' ? record.user_answer : record.user_answer.join(','),
          isCorrect: record.is_correct,
          score: record.is_correct ? 1 : 0,
          answerTime: record.answer_time || 0
        })
      }
    })

    // 🔥 保持用户设置的做题模式（不强制设置为 practice）
    // mode.value 已经在 onMounted 初期根据 URL 参数或本地存储设置过了
    viewMode.value = null

    // 跳转到第一道未答题目
    let firstUnansweredIndex = 1
    for (let i = 1; i <= questionIds.length; i++) {
      if (!answerRecords.value.has(i)) {
        firstUnansweredIndex = i
        break
      }
    }
    currentStep.value = firstUnansweredIndex

    // 恢复计时器（从上次累计时间继续）
    const previousTotalTime = session.total_time || 0
    timer.reset(previousTotalTime)

    // 🔥 重要：恢复时间后立即启动计时器
    timer.start()

    // 记录当前题目的开始时间
    questionStartTime.value.clear()
    questionStartPausedDuration.value.clear()
    questionStartTime.value.set(firstUnansweredIndex, Date.now())
    questionStartPausedDuration.value.set(firstUnansweredIndex, 0)

    // 8. 批量查询收藏状态
    await practice.initializeFavoriteStatus()
  } catch (error) {
    console.error('[继续答题] 恢复失败:', error)
    uni.showToast({
      title: '恢复练习失败',
      icon: 'none',
      duration: 2000
    })
    setTimeout(() => {
      uni.navigateBack()
    }, 2000)
  } finally {
    loading.value = false
  }
}

/**
 * 加载收藏的题目
 *
 * 从收藏页面进入时调用，根据题目ID列表加载题目详情
 */
async function loadFavoriteQuestions(questionIds: number[], bankName?: string) {
  try {
    loading.value = true

    const loggedIn = await ensureLoggedIn()
    if (!loggedIn) {
      return
    }

    // 设置题库名称
    practiceName.value = decodeURIComponent(bankName || '我的收藏')

    // 批量获取题目详情（包含解析）
    const questionPromises = questionIds.map(id =>
      questionApiV2.getQuestionDetail(id)
    )

    const questionList = await Promise.all(questionPromises)

    if (!questionList || questionList.length === 0) {
      uni.showToast({
        title: '没有找到收藏的题目',
        icon: 'none',
        duration: 2000
      })
      setTimeout(() => {
        uni.navigateBack()
      }, 2000)
      return
    }

    try {
      // 两步转换：后端数据 → FrontendQuestion → BaseQuestion（组件格式）
      const frontendQuestions = adaptQuestionList(questionList as any, true) // 包含解析
      allQuestions.value = adaptListToComponentFormat(frontendQuestions)

      // 重置当前步骤为 1
      currentStep.value = 1
    } catch (adaptError) {
      console.error('❌ 题目数据适配失败:', adaptError)
      uni.showToast({
        title: '题目数据格式错误',
        icon: 'none',
        duration: 2000
      })
      setTimeout(() => {
        uni.navigateBack()
      }, 2000)
      return
    }

    // 重置开始时间和计时器状态
    timer.reset()

    // 🔥 收藏模式：启动计时器
    timer.start()

    // 记录第一题的开始时间
    questionStartTime.value.clear()
    questionStartPausedDuration.value.clear()
    questionStartTime.value.set(1, Date.now())
    questionStartPausedDuration.value.set(1, 0)

    // 批量查询收藏状态并初始化（从收藏页面进入，所有题目都已收藏）
    // 直接标记所有题目为已收藏，无需再次查询
    questionCollected.value.clear()
    allQuestions.value.forEach((q, index) => {
      questionCollected.value.set(index + 1, true)
    })

    // 注意：收藏模式不创建练习会话（用户可能反复练习收藏题）
  } catch (error) {
    console.error('[收藏模式] 加载题目失败:', error)
    uni.showToast({
      title: '加载收藏题目失败',
      icon: 'none',
      duration: 2000
    })
    setTimeout(() => {
      uni.navigateBack()
    }, 2000)
  } finally {
    loading.value = false
  }
}

// ============ 题目切换 ============
const currentIndex = computed(() => currentStep.value - 1)

// 触摸开始事件
function handleTouchStart(e: any) {
  const touch = e.touches[0]
  touchStartX.value = touch.pageX
  touchStartY.value = touch.pageY
  touchStartStep.value = currentStep.value
}

// 触摸结束事件
function handleTouchEnd(e: any) {
  const touch = e.changedTouches[0]
  const touchEndX = touch.pageX
  const touchEndY = touch.pageY
  const deltaX = touchEndX - touchStartX.value
  const deltaY = touchEndY - touchStartY.value

  // 判断是否为左滑手势（水平滑动距离大于垂直滑动距离，且向左滑动）
  const isLeftSwipe = Math.abs(deltaX) > Math.abs(deltaY) && deltaX < -50

  // 只有在"触摸开始时就在最后一题 且 swiper 未发生切换"时才触发答题卡
  // 这样可以避免从倒数第二题滑到最后一题时误触发
  const isAtLastQuestion = touchStartStep.value === totalSteps.value && currentStep.value === totalSteps.value

  // 非查看模式下，在最后一题左滑弹出答题卡
  if (viewMode.value === null && isLeftSwipe && isAtLastQuestion) {
    openAnswerSheet()
  }
}

function handleSwiperChange(e: any) {
  const newIndex = e.detail?.current ?? 0
  currentStep.value = newIndex + 1

  // 同步题目状态
  syncQuestionState()

  // 记录题目开始时间和暂停累计时长（如果还没记录）
  if (!questionStartTime.value.has(currentOriginalIndex.value)) {
    questionStartTime.value.set(currentOriginalIndex.value, Date.now())
    questionStartPausedDuration.value.set(currentOriginalIndex.value, pausedDuration.value)
  }
}

function handleNextQuestion() {
  if (currentStep.value < totalSteps.value) {
    currentStep.value++
    syncQuestionState()
  }
}

async function toggleCollect() {
  if (!question.value?.id) {
    uni.showToast({ title: '题目信息不完整', icon: 'none' })
    return
  }
  await practice.toggleCollect(currentOriginalIndex.value, question.value.id)
}

function toggleWrongBook() {
  const currentMarked = questionMarkedWrong.value.get(currentOriginalIndex.value) || false
  questionMarkedWrong.value.set(currentOriginalIndex.value, !currentMarked)

  uni.showToast({
    title: !currentMarked ? '已加入错题本' : '已移出错题本',
    icon: 'none'
  })
}

function handleAddToSet() {
  uni.showToast({
    title: '题集功能开发中...',
    icon: 'none'
  })
}

async function handleUpdateNote(data: { note: string; isPublic: boolean }) {
  // 先更新本地状态
  questionNotes.value.set(currentOriginalIndex.value, data.note)

  // 如果笔记为空，不保存到后端
  if (!data.note.trim()) {
    return
  }

  // 获取当前题目ID
  const currentQuestion = allQuestions.value[currentOriginalIndex.value - 1]
  if (!currentQuestion?.id) {
    console.error('[保存笔记] 题目ID不存在')
    return
  }

  const questionId = parseInt(currentQuestion.id)

  try {
    // 调用 API 创建或更新笔记（不需要传 userId，后端会自动从 token 中获取）
    const savedNote = await noteApi.createOrUpdateMyNote(
      questionId,
      data.note,
      data.isPublic
    )

    // 保存笔记ID，方便后续更新
    questionNoteIds.value.set(currentOriginalIndex.value, savedNote.id)

    uni.showToast({
      title: '笔记已保存',
      icon: 'success',
      duration: 1500
    })
  } catch (error) {
    console.error('[保存笔记失败]:', error)
    uni.showToast({
      title: '保存失败，请重试',
      icon: 'none',
      duration: 2000
    })
  }
}

function handleGoToSimilarQuestion(questionId: string) {
  uni.showToast({
    title: '跳转到题目: ' + questionId,
    icon: 'none'
  })
  // TODO: 实现跳转逻辑
}

function handleSelectSheetItem(originalIndex: number) {
  // 🔥 修复：根据原始题号找到在显示列表中的位置
  const displayIndex = displayQuestions.value.findIndex(item => item.originalIndex === originalIndex)

  if (displayIndex !== -1) {
    // 先关闭答题卡
    closeAnswerSheet()

    // 等待 DOM 更新后再切换题目（避免 swiper 组件的时序问题）
    setTimeout(() => {
      currentStep.value = displayIndex + 1
      syncQuestionState()
    }, 50)
  } else {
    closeAnswerSheet()
  }
}

function handleSubmitAll() {
  // 检查是否所有题目都已作答
  const unansweredCount = answerSheetItems.value.filter(item => item.status === 'unselected').length

  if (unansweredCount > 0) {
    // 先关闭答题卡，避免对话框被遮挡
    closeAnswerSheet()

    // 显示自定义确认对话框
    unansweredCountForDialog.value = unansweredCount
    confirmDialogMessage.value = `还有 ${unansweredCount} 道题未作答，确定要提交吗？`
    showConfirmDialog.value = true
  } else {
    submitAnswers()
  }
}

// 确认对话框 - 确认提交
function handleConfirmSubmit() {
  showConfirmDialog.value = false
  submitAnswers()
}

// 确认对话框 - 取消提交
function handleCancelSubmit() {
  showConfirmDialog.value = false
  // 用户点击取消，重新打开答题卡
  openAnswerSheet()
}

async function submitAnswers() {
  closeAnswerSheet()

  if (!currentSessionId.value) {
    uni.showToast({ title: '会话不存在', icon: 'none' })
    return
  }

  try {
    uni.showLoading({ title: '提交中...', mask: true })

    // 🔥 并行提交会话 + 预取 solution 数据（用于结算页和查看解析）
    const [_, solutionData] = await Promise.all([
      practiceApi.submitSession(currentSessionId.value, {
        total_time: timer.getElapsedSeconds()
      }),
      practiceApi.getSessionSolution(currentSessionId.value)
    ])

    // 🔥 缓存 solution 数据，供 ResultSummary 和后续的查看解析使用
    uni.setStorageSync('practice-solution', solutionData)

    // 🔥 提交成功后，刷新练习中心的统计数据（静默刷新，不阻塞跳转）
    if (currentCatId.value !== null) {
      practiceStore.refreshStatistics(currentCatId.value).catch(err => {
        console.warn('[答题页] 刷新统计失败（不影响跳转）:', err)
      })
    }

    uni.hideLoading()

    // 跳转到结算页面（传递 sessionId，结算页通过 API 获取数据）
    uni.redirectTo({
      url: `/pages/practice/ResultSummary?sessionId=${currentSessionId.value}`
    })
  } catch (error) {
    uni.hideLoading()
    console.error('提交答案失败:', error)
    uni.showToast({ title: '提交失败，请重试', icon: 'none', duration: 2000 })
  }
}

// 使用 composable 方法
const openAnswerSheet = answerSheet.open
const closeAnswerSheet = answerSheet.close

function handleBackFromView() {
  if (!currentBankId.value) {
    uni.showToast({
      title: '无法返回',
      icon: 'none'
    })
    return
  }

  // 保存数据到存储并跳转回结算页面
  uni.setStorageSync('practice-result', prepareResultData(true))

  uni.redirectTo({
    url: '/pages/practice/ResultSummary'
  })
}

// ============ 动态高度计算 ============
// 使用 composable 统一管理系统信息
// calculateSwiperHeight 已在上方从 useSystemInfo 导入

// ============ 主题相关 ============
function syncTheme() {
  const bodyTheme = document?.body?.getAttribute('data-theme')
  if (bodyTheme) {
    isDarkMode.value = bodyTheme === 'dark'
    return
  }
  const storedTheme = typeof uni !== 'undefined' ? uni.getStorageSync(THEME_STORAGE_KEY) : ''
  if (storedTheme) {
    isDarkMode.value = storedTheme === 'dark'
  }
}

let themeObserver: MutationObserver | null = null

onMounted(async () => {
  // 🔥 不要在这里启动计时器，应该在各个场景加载完成后再启动

  // 🔥 加载当前用户信息（用于笔记功能）
  loadCurrentUser().catch(err => {
    console.warn('[页面加载时获取用户信息失败]:', err)
  })

  // 计算 swiper 高度
  setTimeout(() => {
    calculateSwiperHeight('.swiper-container', (height) => {
      swiperHeight.value = height
    })
  }, 100)

  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const bankId = currentPage?.options?.bankId
  const chapterId = currentPage?.options?.chapterId
  const modeParam = currentPage?.options?.mode
  const viewModeParam = currentPage?.options?.viewMode
  const gotoIndex = currentPage?.options?.gotoIndex
  const urlSessionId = currentPage?.options?.sessionId  // 获取 sessionId 参数
  const resumeParam = currentPage?.options?.resume  // 获取 resume 参数
  const catId = currentPage?.options?.catId  // 获取分类 ID 参数

  // 🔥 保存分类 ID（用于答题完成后刷新统计）
  if (catId) {
    currentCatId.value = Number(catId)
  }

  if (modeParam && ['practice', 'exercise', 'memorize'].includes(modeParam)) {
    mode.value = modeParam as PracticeMode
    console.log('[做题页面] 使用 URL 参数指定的做题模式:', modeParam)
  } else {
    // 如果 URL 没有指定模式，从本地存储读取用户设置的默认模式
    const savedMode = uni.getStorageSync('practice_mode') as PracticeMode
    console.log('[做题页面] 从本地存储读取到的模式:', savedMode)
    if (savedMode && ['practice', 'exercise', 'memorize'].includes(savedMode)) {
      mode.value = savedMode
      console.log('[做题页面] ✅ 使用用户设置的默认做题模式:', savedMode)
    } else {
      console.log('[做题页面] ⚠️ 本地存储没有有效模式，使用默认值: practice')
    }
  }
  console.log('[做题页面] 最终使用的做题模式:', mode.value)

  // 🔥 如果有 sessionId，根据 resume 参数决定是继续答题还是查看历史
  if (urlSessionId) {
    if (resumeParam === 'true') {
      // 继续答题模式
      await resumeInProgressSession(Number(urlSessionId))
    } else {
      // 查看历史模式
      await loadHistorySession(Number(urlSessionId), viewModeParam, gotoIndex)
    }
    loading.value = false
    return  // 直接返回，不执行后续的正常流程
  }

  if (bankId) {
    // 保存 bankId
    currentBankId.value = Number(bankId)

    // 检查是否从结算页返回（查看模式）
    const isFromResult = viewModeParam || gotoIndex

    if (isFromResult) {
      // 从结算页返回：直接设置模式和恢复数据即可
      // 所有派生状态（答题卡、解析显示）会自动更新

      // 1. 设置查看模式
      if (viewModeParam === 'all' || gotoIndex) {
        originalMode.value = mode.value
        viewMode.value = 'all'
        mode.value = 'exercise'
      } else if (viewModeParam === 'wrong') {
        // 从结算页查看本次练习的错题
        originalMode.value = mode.value
        viewMode.value = 'wrong'
        mode.value = 'exercise'
      } else if (viewModeParam === 'favorite') {
        // 从收藏页面进入：使用练题模式（答题后立即显示解析）
        mode.value = 'exercise'

        // 从 storage 读取收藏的题目ID列表
        const favoriteQuestionIds = uni.getStorageSync('favorite-question-ids')
        if (favoriteQuestionIds && favoriteQuestionIds.length > 0) {
          await practice.loadFavoriteQuestions(favoriteQuestionIds, currentPage?.options?.bankName)
          loading.value = false
          return
        }
      } else if (viewModeParam === 'wrong-practice') {
        // 从错题本页面进入：使用练题模式（答题后立即显示解析）
        mode.value = 'exercise'

        // 从 storage 读取错题的题目ID列表
        const wrongQuestionIds = uni.getStorageSync('wrong-question-ids')
        if (wrongQuestionIds && wrongQuestionIds.length > 0) {
          await practice.loadWrongQuestions(wrongQuestionIds, currentPage?.options?.bankName)
          loading.value = false
          return
        }
      }

      // 2. 恢复题目数据
      const savedQuestions = uni.getStorageSync('practice-questions')
      if (savedQuestions && Array.isArray(savedQuestions)) {
        allQuestions.value = savedQuestions
        practiceName.value = uni.getStorageSync('practice-bank-name') || '加载中...'

        // 3. 恢复答题记录
        const savedAnswers = uni.getStorageSync('practice-answers')
        if (savedAnswers && Array.isArray(savedAnswers)) {
          answerRecords.value.clear()
          savedAnswers.forEach((item: any) => {
            answerRecords.value.set(item.index, {
              questionId: item.questionId,
              answer: item.answer,
              isCorrect: item.isCorrect,
              score: item.score,
              answerTime: item.answerTime,
              submitted: item.submitted ?? true  // 兼容旧数据，默认为已提交
            })
          })
        }

        // 4. 设置当前题目索引（所有状态会自动更新）
        if (gotoIndex) {
          currentStep.value = Number(gotoIndex)
        } else {
          currentStep.value = 1
        }

        // 重要：恢复完成后，设置 loading 为 false
        loading.value = false
      } else {
        // 如果没有缓存数据，还是要加载（会在loadQuestions中设置loading=false）
        await loadQuestions(Number(bankId), chapterId ? Number(chapterId) : undefined)
      }
    } else {
      // 正常进入刷题：加载题目数据
      await loadQuestions(Number(bankId), chapterId ? Number(chapterId) : undefined)
    }
  } else {
    uni.showToast({
      title: '缺少题库参数',
      icon: 'none'
    })
    setTimeout(() => {
      uni.navigateBack()
    }, 1500)
  }

  syncTheme()
  if (typeof document !== 'undefined' && typeof MutationObserver !== 'undefined' && document.body) {
    themeObserver = new MutationObserver(syncTheme)
    themeObserver.observe(document.body, { attributes: true, attributeFilter: ['data-theme'] })
  }
})

// 🔥 页面隐藏时保存当前进度（用户返回时触发）
onHide(() => {
  // 只在练习模式且有会话时保存
  if (currentSessionId.value && viewMode.value === null) {
    practice.saveCurrentProgress()
  }
})

onBeforeUnmount(() => {
  // 计时器由 useTimer composable 自动清理

  if (themeObserver) {
    themeObserver.disconnect()
    themeObserver = null
  }
  if (typeof document !== 'undefined') {
    document.body.classList.remove('u-body--locked')
  }
})

// 拦截返回事件（uni-app 页面生命周期）
const onBackPress = () => {
  // 只在查看模式下拦截返回
  if (viewMode.value) {
    handleBackFromView()
    return true  // 返回 true 阻止默认返回行为
  }
  return false  // 返回 false 允许默认返回
}
</script>

<style scoped lang="scss">
page {
  height: 100%;
  overflow: hidden;
}

.practice-page {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
  margin: 0;
  box-sizing: border-box;
  background: var(--color-bg-card);
  overflow: hidden;
}

.practice-page :deep(.header-panel) {
  flex-shrink: 0;
  width: 100%;
  border-radius: 0 0 32rpx 32rpx;
}

/* 原生 swiper 容器 - 动态高度由 JS 计算 */
.swiper-container {
  flex: 1;
  width: 100%;
  overflow: hidden;
  /* 高度由 JS 动态计算设置到 swiper 上 */
}

.question-swiper {
  width: 100%;
  height: 100%;
}

.swiper-item-content {
  width: 100%;
  height: 100%;
  min-height: 100%;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 24rpx 28rpx 48rpx;
  box-sizing: border-box;
  /* 只允许垂直滚动，水平滑动交给 swiper */
  touch-action: pan-y;
}

/* 让内容撑满可滚动区域 */
.swiper-item-content > .question-card {
  min-height: 100%;
}
</style>
