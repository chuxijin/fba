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
              :analysis-visible="showAnalysis"
              :is-collected="questionCollected.get(item.originalIndex) || false"
              :should-show-confirm="getShouldShowConfirm(item.question) && !showAnalysis"
              :loading="false"
              @select="(value: string) => handleSelect(item.originalIndex, value)"
              @confirm="handleConfirm"
              @toggle-collect="toggleCollect"
            />

            <!-- 解析面板 -->
            <AnalysisPanel
              v-if="showAnalysis && (viewMode !== null || answerRecords.has(item.originalIndex))"
              :question="item.question"
              :user-answer="getQuestionAnswer(item.originalIndex)"
              :is-correct="answerRecords.get(item.originalIndex)?.isCorrect || false"
              :answer-time="answerRecords.get(item.originalIndex)?.answerTime || 0"
              :total-attempts="0"
              :correct-rate="0"
              :common-mistakes="[]"
              :analysis="item.question.analysis"
              :similar-questions="[]"
              :is-collected="questionCollected.get(item.originalIndex) || false"
              :is-marked-wrong="questionMarkedWrong.get(item.originalIndex) || false"
              :note-text="questionNotes.get(item.originalIndex) || ''"
              @toggle-collect="toggleCollect"
              @toggle-wrong-book="toggleWrongBook"
              @add-to-set="handleAddToSet"
              @update-note="handleUpdateNote"
              @go-to-question="handleGoToSimilarQuestion"
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
      :show-submit="mode === 'practice'"
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
import { questionApiV2, practiceApi, authApi, bankApi, favoriteApi, setToken } from '@/api'
import {
  useTimer,
  useAnswerSheet,
  usePracticeDetail,
  type AnswerSheetItem,
  type AnswerRecord
} from '@/composables'

declare const uni: any

declare const document: Document & {
  body?: HTMLElement & { getAttribute: (qualifiedName: string) => string | null }
}

// ============ Composables 初始化 ============
const timer = useTimer()
const answerSheet = useAnswerSheet()

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
  questionStartTime,
  questionStartPausedDuration,
} = practice

const { timeText, isPaused, pausedDuration } = timer
const isSheetVisible = answerSheet.isVisible

// ============ 页面状态 ============
const swiperHeight = ref('500px')
const currentStep = ref(1)
const totalSteps = computed(() => displayQuestions.value.length)

// 当 loading 变为 false 时重新计算高度
watch(loading, (newVal) => {
  if (!newVal) {
    setTimeout(() => calculateSwiperHeight(), 50)
  }
})

// ============ 模式相关 ============
const mode = ref<PracticeMode>('practice')
const currentAnswer = ref('')
const viewMode = ref<'all' | 'wrong' | null>(null)
const originalMode = ref<PracticeMode>('practice')

// 是否显示解析
const showAnalysis = computed(() => {
  if (mode.value === 'memorize') return true
  if (viewMode.value !== null) return true
  if (mode.value === 'exercise') return hasAnswered.value
  return false
})

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
  return answerRecords.value.get(questionIndex)?.answer || ''
}

// 判断指定题目是否应该显示确定按钮
function getShouldShowConfirm(question: BaseQuestion | undefined): boolean {
  if (!question) return false

  // 背题模式：不显示按钮
  if (mode.value === 'memorize') return false

  // 练题模式：始终显示按钮（所有题型）
  if (mode.value === 'exercise') return true

  // 刷题模式：只有多选题和填空题显示按钮（单选和判断题自动提交）
  if (mode.value === 'practice') {
    const isAutoSubmitType = question.type === 'single' || question.type === 'judgement'
    return !isAutoSubmitType
  }

  return true
}

// ============ 解析面板数据 ============
// 当前题目是否已答题（用于练题模式判断是否显示解析）
const hasAnswered = computed(() => {
  return answerRecords.value.has(currentOriginalIndex.value)
})

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
// 计算时长文本
function formatDuration(milliseconds: number): string {
  const totalSeconds = Math.floor(milliseconds / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}分${seconds}秒`
}

// 构建答题结果项
function buildAnswerItems(questionCount: number) {
  return Array.from({ length: questionCount }, (_, idx) => {
    const index = idx + 1
    const record = answerRecords.value.get(index)

    let status: 'correct' | 'wrong' | 'unanswered' = 'unanswered'
    if (record) {
      status = record.isCorrect ? 'correct' : 'wrong'
    }

    return { index, status }
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
      score: 0
    })
  }

  // 同步 currentAnswer（用于实时显示）
  if (questionIndex === currentOriginalIndex.value) {
    currentAnswer.value = value
  }

  if (mode.value === 'memorize') return

  // 刷题模式下，单选题和判断题选中后立即提交
  const currentQuestion = allQuestions.value[questionIndex - 1]
  const isAutoSubmitType = currentQuestion?.type === 'single' || currentQuestion?.type === 'judgement'

  if (mode.value === 'practice' && questionIndex === currentOriginalIndex.value && isAutoSubmitType) {
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

  const isCorrect = practice.checkAnswer(currentAnswer.value, question.value.answer)
  const questionScore = 1

  // 计算答题时长（扣除暂停时间）
  const questionStartTimeValue = questionStartTime.value.get(currentOriginalIndex.value) || Date.now()
  const questionStartPausedValue = questionStartPausedDuration.value.get(currentOriginalIndex.value) || 0
  const currentPausedTotal = timer.getCurrentPausedDuration()
  const actualElapsed = Date.now() - questionStartTimeValue - (currentPausedTotal - questionStartPausedValue)
  const answerTime = Math.floor(actualElapsed / 1000)

  const record: AnswerRecord = {
    questionId: question.value.id,
    answer: currentAnswer.value,
    isCorrect,
    score: isCorrect ? questionScore : 0,
    answerTime
  }
  answerRecords.value.set(currentOriginalIndex.value, record)

  // 🔥 实时保存答题记录到后端
  practice.saveAnswerRecord(record, viewMode.value)

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

// ============ 加载题目 ============
async function loadQuestions(bankId: number) {
  try {
    loading.value = true

    const loggedIn = await ensureLoggedIn()
    if (!loggedIn) {
      return
    }

    const bankInfo = await bankApi.getBankDetail(bankId)
    practiceName.value = bankInfo.name

    // 使用新的 v2 API 获取刷题题目列表（不含答案）
    const questionList = await questionApiV2.getBankPracticeQuestions(bankId)

    if (!questionList || questionList.length === 0) {
      uni.showToast({
        title: '该题库暂无题目',
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
      const frontendQuestions = adaptQuestionList(questionList as any, false)
      allQuestions.value = adaptListToComponentFormat(frontendQuestions)

      // 重要：重置当前步骤为 1，确保 swiper 从第一题开始
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

    // 记录第一题的开始时间和暂停累计时长
    questionStartTime.value.clear()
    questionStartPausedDuration.value.clear()
    questionStartTime.value.set(1, Date.now())
    questionStartPausedDuration.value.set(1, 0)

    // 创建练习会话（记录本次练习）
    await practice.createPracticeSession(bankId, null, 'bank', allQuestions.value.length)

    // 批量查询收藏状态并初始化
    await practice.initializeFavoriteStatus()
  } catch (error) {
    console.error('加载题目失败:', error)
    uni.showToast({
      title: '加载题目失败',
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
 * 加载历史会话（查看历史记录时使用）
 *
 * @param sessionId 会话 ID
 * @param viewModeParam 查看模式
 * @param gotoIndex 跳转到的题目索引
 */
async function loadHistorySession(sessionId: number, viewModeParam?: string, gotoIndex?: string) {
  try {
    loading.value = true
    currentSessionId.value = sessionId

    // 优化：尝试从 storage 读取缓存数据
    const cachedSummary = uni.getStorageSync('history-session-summary')
    const CACHE_TTL = 5 * 60 * 1000  // 5分钟缓存

    let session: any
    let questionIds: number[]
    let practiceNameStr: string | null = null
    let answerItemsFromCache: any[] = []

    if (cachedSummary
        && cachedSummary.sessionId === sessionId
        && (Date.now() - cachedSummary.timestamp) < CACHE_TTL) {
      // 使用缓存数据
      questionIds = cachedSummary.questionIds
      practiceNameStr = cachedSummary.practiceName
      currentBankId.value = cachedSummary.bankId || null
      answerItemsFromCache = cachedSummary.answerItems || []

      session = {
        id: sessionId,
        bank_id: cachedSummary.bankId,
        question_ids: questionIds
      }
    } else {
      // 从 API 加载
      session = await practiceApi.getSession(sessionId)
      currentBankId.value = session.bank_id || null
      questionIds = session.question_ids || []
      practiceNameStr = session.practice_name || '练习'
    }

    // 检查 question_ids
    if (!questionIds || questionIds.length === 0) {
      uni.showToast({ title: '该会话没有题目数据', icon: 'none', duration: 2000 })
      setTimeout(() => uni.navigateBack(), 2000)
      return
    }

    // 优先从 storage 读取题目数据（包含答案和解析）
    const savedQuestions = uni.getStorageSync('practice-questions')
    const savedBankName = uni.getStorageSync('practice-bank-name')

    if (savedQuestions && Array.isArray(savedQuestions) && savedQuestions.length > 0) {
      // 使用缓存的题目数据（已包含答案和解析）
      allQuestions.value = savedQuestions
      practiceName.value = savedBankName || practiceNameStr || '练习'
    } else {
      // 🔥 缓存不可用，从 API 获取题目（含答案和解析）
      const questionList = await questionApiV2.getQuestions({
        ids: questionIds.join(','),
        include_answer: true  // ✅ 关键：请求包含答案和解析
      })

      console.log('[查看历史] API返回的题目数据（前3题）:', questionList.slice(0, 3).map(q => ({
        id: q.id,
        has_answer_data: !!q.answer_data,
        has_analysis_content: !!q.analysis_content,
        answer_data: q.answer_data,
        analysis_content: q.analysis_content ? q.analysis_content.substring(0, 50) + '...' : null
      })))

      // 🔥 重要：API 返回的题目顺序可能与 questionIds 不一致，需要重新排序
      const questionMap = new Map()
      questionList.forEach(q => {
        questionMap.set(q.id, q)
      })

      const orderedQuestionList = questionIds.map(id => questionMap.get(id)).filter(Boolean)

      // 转换题目格式（API已返回答案，标记为包含解析）
      const frontendQuestions = adaptQuestionList(orderedQuestionList as any, true)

      console.log('[查看历史] 适配后的题目数据（前3题）:', frontendQuestions.slice(0, 3).map(q => ({
        id: q.id,
        has_answer: !!q.answer,
        has_analysis: !!q.analysis,
        answer: q.answer,
        analysis: q.analysis ? q.analysis.substring(0, 50) + '...' : null
      })))

      allQuestions.value = adaptListToComponentFormat(frontendQuestions)

      console.log('[查看历史] 最终题目数据（前3题）:', allQuestions.value.slice(0, 3).map(q => ({
        id: q.id,
        has_answer: !!q.answer,
        has_analysis: !!q.analysis,
        answer: q.answer,
        analysis: typeof q.analysis === 'string' ? q.analysis.substring(0, 50) + '...' : q.analysis
      })))

      practiceName.value = practiceNameStr || '练习'
    }

    // 获取答题记录（直接从 API 获取，不使用缓存）
    // 缓存中的 user_answer 字段不完整，必须从 API 获取完整数据
    const records = await practiceApi.getSessionRecords(sessionId)

    // 构建 question_id -> record 的映射
    const recordMap = new Map()
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

    // 获取会话详情
    const session = await practiceApi.getSession(sessionId)
    currentBankId.value = session.bank_id || null
    const questionIds = session.question_ids || []
    const completedCount = session.completed_count || 0

    if (!questionIds || questionIds.length === 0) {
      uni.showToast({ title: '该会话没有题目数据', icon: 'none', duration: 2000 })
      setTimeout(() => uni.navigateBack(), 2000)
      return
    }

    // 批量查询题目详情
    const questionList = await questionApiV2.getQuestions({ ids: questionIds.join(',') })

    // 🔥 重要：API 返回的题目顺序可能与 questionIds 不一致，需要重新排序
    // 创建 question_id -> question 的映射
    const questionMap = new Map()
    questionList.forEach(q => {
      questionMap.set(q.id, q)
    })

    // 按照 questionIds 的顺序重新排列题目
    const orderedQuestionList = questionIds.map(id => questionMap.get(id)).filter(Boolean)

    // 转换题目格式（继续答题时需要包含答案和解析，用于已答题目的展示）
    const frontendQuestions = adaptQuestionList(orderedQuestionList as any, true)
    allQuestions.value = adaptListToComponentFormat(frontendQuestions)

    // 设置题库名称
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

    // 设置为练习模式（可以继续答题）
    mode.value = 'practice'
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

function handleUpdateNote(note: string) {
  questionNotes.value.set(currentOriginalIndex.value, note)
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

  try {
    uni.showLoading({
      title: '提交中...',
      mask: true
    })

    // 构建提交参数（符合新后端格式）
    const answerItems = Array.from(answerRecords.value.entries()).map(([index, record]) => ({
      question_id: Number(record.questionId),
      user_answer: record.answer,
      answer_time: record.answerTime || 0
    }))

    // 调用新的批量提交 API（请求包含解析内容）
    const result = await questionApiV2.submitAnswers({
      answers: answerItems,
      include_analysis: true
    })

    uni.hideLoading()

    // 更新答题记录（使用服务器判分结果）
    result.results.forEach((item) => {
      // 找到对应的题目索引
      const questionIndex = allQuestions.value.findIndex(q => String(q.id) === String(item.question_id))
      if (questionIndex !== -1) {
        const index = questionIndex + 1
        const existingRecord = answerRecords.value.get(index)
        if (existingRecord) {
          existingRecord.isCorrect = item.is_correct
          existingRecord.score = item.score
        }

        // 将解析数据添加到题目中（转换为字符串格式）
        const question = allQuestions.value[questionIndex] as any
        if (item.analysis_content) {
          question.analysis = item.analysis_content  // 直接使用字符串
          // 提取正确答案（从 dict 中提取 correct 字段）
          if (!question.answer) {
            // correct_answer 格式为 {correct: "A"} 或 {correct: ["A", "C"]}
            if (typeof item.correct_answer === 'object' && item.correct_answer !== null) {
              question.answer = (item.correct_answer as any).correct
            } else {
              question.answer = item.correct_answer
            }
          }
        }
      }
    })

    // 更新结果数据（使用服务器统计结果）
    resultData.value = {
      score: result.total_score,
      totalCount: result.total_questions,
      correctCount: result.correct_count,
      wrongCount: result.wrong_count,
      wrongQuestions: result.results
        .map((item, idx) => (!item.is_correct ? idx + 1 : -1))
        .filter(idx => idx !== -1)
    }

    // 保存练习记录到后端（降级处理：失败不影响查看结算页）
    if (currentSessionId.value) {
      try {
        // 构建答题记录列表（使用更新后的判分结果）
        const records = Array.from(answerRecords.value.entries()).map(([index, record]) => ({
          question_id: Number(record.questionId),
          user_answer: record.answer,
          is_correct: record.isCorrect,
          answer_time: record.answerTime || 0
        }))

        // 批量创建答题记录
        await practiceApi.batchCreateRecords({
          session_id: currentSessionId.value,
          records
        })

        // 🔥 更新会话统计数据（正确数、错误数等）
        await practiceApi.updateSession(currentSessionId.value, {
          completed_count: result.total_questions,
          correct_count: result.correct_count,
          wrong_count: result.wrong_count,
          total_time: timer.getElapsedSeconds()
        })

        // 提交练习会话（标记为已完成）
        await practiceApi.submitSession(currentSessionId.value, {
          score: result.total_score
        })
      } catch (error) {
        console.error('[练习会话] 保存记录失败:', error)
        // 不阻断用户流程，继续跳转到结算页
      }
    }

    // 保存答题记录到 storage（用于返回时恢复）
    const answersArray = Array.from(answerRecords.value.entries()).map(([index, record]) => ({
      index,
      ...record
    }))
    uni.setStorageSync('practice-answers', answersArray)

    // 保存题目数据到 storage（避免查看解析时重新请求）
    uni.setStorageSync('practice-questions', allQuestions.value)
    uni.setStorageSync('practice-bank-name', practiceName.value)

    // 保存数据到存储
    uni.setStorageSync('practice-result', prepareResultData())

    // 跳转到结算页面（使用 redirectTo 替换当前页面）
    uni.redirectTo({
      url: '/pages/practice/ResultSummary'
    })
  } catch (error) {
    uni.hideLoading()
    console.error('提交答案失败:', error)
    uni.showToast({
      title: '提交失败，请重试',
      icon: 'none',
      duration: 2000
    })
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
function calculateSwiperHeight() {
  uni.getSystemInfo({
    success: (res) => {
      const query = uni.createSelectorQuery()
      query.select('.swiper-container').boundingClientRect((rect: any) => {
        if (rect) {
          const calculatedHeight = res.windowHeight - rect.top
          swiperHeight.value = `${calculatedHeight}px`
        }
      }).exec()
    }
  })
}

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
  // 启动计时器
  timer.start()

  // 计算 swiper 高度
  setTimeout(() => {
    calculateSwiperHeight()
  }, 100)

  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const bankId = currentPage?.options?.bankId
  const modeParam = currentPage?.options?.mode
  const viewModeParam = currentPage?.options?.viewMode
  const gotoIndex = currentPage?.options?.gotoIndex
  const urlSessionId = currentPage?.options?.sessionId  // 获取 sessionId 参数
  const resumeParam = currentPage?.options?.resume  // 获取 resume 参数

  if (modeParam && ['practice', 'exercise', 'memorize'].includes(modeParam)) {
    mode.value = modeParam as PracticeMode
  }

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
        originalMode.value = mode.value
        viewMode.value = 'wrong'
        mode.value = 'exercise'
      } else if (viewModeParam === 'favorite') {
        // 从收藏页面进入：加载收藏的题目
        // 注意：不设置 viewMode，让用户按正常学习模式学习（根据 mode 决定是否显示答案）
        // 默认使用练题模式（答题后显示解析）

        // 从 storage 读取收藏的题目ID列表
        const favoriteQuestionIds = uni.getStorageSync('favorite-question-ids')
        if (favoriteQuestionIds && favoriteQuestionIds.length > 0) {
          await loadFavoriteQuestions(favoriteQuestionIds, currentPage?.options?.bankName)
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
              answerTime: item.answerTime
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
        await loadQuestions(Number(bankId))
      }
    } else {
      // 正常进入刷题：加载题目数据
      await loadQuestions(Number(bankId))
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
