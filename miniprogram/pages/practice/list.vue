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
      @show-sheet="openAnswerSheet"
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
              v-if="showAnalysis && answerRecords.has(item.originalIndex)"
              :question="item.question"
              :user-answer="getQuestionAnswer(item.originalIndex)"
              :is-correct="answerRecords.get(item.originalIndex)?.isCorrect || false"
              :answer-time="answerRecords.get(item.originalIndex)?.answerTime || 0"
              :total-attempts="Math.floor(Math.random() * 2000) + 500"
              :correct-rate="Math.floor(Math.random() * 40) + 50"
              :common-mistakes="mockCommonMistakes"
              :analysis="item.question.analysis"
              :similar-questions="mockSimilarQuestions"
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

      <view v-else class="loading-container">
        <text>加载题目中...</text>
      </view>
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
    <ConfirmDialog
      :visible="showConfirmDialog"
      :message="confirmDialogMessage"
      @confirm="handleConfirmSubmit"
      @cancel="handleCancelSubmit"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import AnswerSheet from './modules/AnswerSheet.vue'
import HeaderPanel from '../../components/business/HeaderPanel.vue'
import QuestionCard from '../../components/business/QuestionCard.vue'
import AnalysisPanel from '../../components/business/AnalysisPanel.vue'
import ConfirmDialog from '../../components/common/ConfirmDialog.vue'
import type { BaseQuestion, PracticeMode } from '../../components/business/question-map'
import { adaptQuestionList, adaptListToComponentFormat } from '../../utils/question-adapter-v2'
import { authApi, bankApi, questionApiV2, setToken } from '@/api'
import type { FrontendQuestion } from '@/api/types/question-v2'
import { formatDuration as formatDurationUtil } from '../../utils/format'

declare const uni: any

declare const document: Document & {
  body?: HTMLElement & { getAttribute: (qualifiedName: string) => string | null }
}

type AnswerSheetStatus = 'selected' | 'unselected' | 'correct' | 'wrong'

interface AnswerSheetItem {
  index: number
  status: AnswerSheetStatus
  isCurrent: boolean
}

interface AnswerRecord {
  questionId: string
  answer: string
  isCorrect: boolean
  score: number
  answerTime?: number
}

// ============ 基础状态 ============
const practiceName = ref('加载中...')
const loading = ref(true)
const allQuestions = ref<BaseQuestion[]>([])
const currentStep = ref(1)
const totalSteps = computed(() => displayQuestions.value.length)
const timeText = '12:00'
const startTime = ref(Date.now())

// 保存题库 ID（用于结算页返回）
const currentBankId = ref<number | null>(null)

// ============ 模式相关 ============
const mode = ref<PracticeMode>('practice')
const currentAnswer = ref('')

// 是否显示解析（根据模式和答题状态自动计算）
const showAnalysis = computed(() => {
  // 背题模式：始终显示
  if (mode.value === 'memorize') return true

  // 查看模式：始终显示
  if (viewMode.value !== null) return true

  // 练题模式：答题后显示
  if (mode.value === 'exercise') {
    return hasAnswered.value
  }

  // 刷题模式：不显示
  return false
})

// 查看模式（用于结算页返回）
const viewMode = ref<'all' | 'wrong' | null>(null)
// 保存原始模式（进入查看模式前的模式）
const originalMode = ref<PracticeMode>('practice')

// 答题记录
const answerRecords = ref<Map<number, AnswerRecord>>(new Map())

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
const isSheetVisible = ref(false)

// 确认对话框状态
const showConfirmDialog = ref(false)
const confirmDialogMessage = ref('')
const unansweredCountForDialog = ref(0)

// 解析面板相关状态
const questionCollected = ref<Map<number, boolean>>(new Map())
const questionMarkedWrong = ref<Map<number, boolean>>(new Map())
const questionNotes = ref<Map<number, string>>(new Map())
const questionStartTime = ref<Map<number, number>>(new Map())

// 触摸事件状态（用于检测在最后一题上的左滑手势）
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

// 模拟数据（后续可以从后端获取）
const mockSimilarQuestions = computed(() => {
  if (!question.value) return []
  return [
    {
      id: 'similar-1',
      typeLabel: question.value.typeLabel || '单选题',
      stem: '这是一道相似的题目，考察相同的知识点...',
      similarity: 85
    },
    {
      id: 'similar-2',
      typeLabel: question.value.typeLabel || '单选题',
      stem: '这道题目与当前题目有类似的解题思路...',
      similarity: 72
    }
  ]
})

const mockCommonMistakes = computed(() => {
  if (!question.value || question.value.type === 'fill') return []
  return [
    { option: 'B', description: '容易混淆知识点 A 和 B 的区别' },
    { option: 'D', description: '忽略了题干中的关键限定条件' }
  ]
})

// ============ 答题卡相关 ============
// 答题卡状态完全由 answerRecords 计算得出，无需单独维护
const answerSheetItems = computed<AnswerSheetItem[]>(() => {
  return Array.from({ length: totalSteps.value }, (_, idx) => {
    const index = idx + 1
    const record = answerRecords.value.get(index)
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
      index,
      status,
      isCurrent: index === currentStep.value
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
  const durationText = formatDuration(Date.now() - startTime.value)
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

  console.log(`${viewModeType === 'all' ? '📖' : '❌'} ${title}模式`)
}

// 同步题目切换后的状态
function syncQuestionState() {
  currentAnswer.value = answerRecords.value.get(currentOriginalIndex.value)?.answer || ''
}

// ============ 答题逻辑 ============
function checkAnswer(userAnswer: string, correctAnswer: string | string[] | undefined): boolean {
  if (!correctAnswer) return false

  // 尝试解析用户答案（可能是 JSON 字符串）
  let userAnswerArray: string[]
  try {
    const parsed = JSON.parse(userAnswer)
    userAnswerArray = Array.isArray(parsed) ? parsed : [userAnswer]
  } catch {
    userAnswerArray = [userAnswer]
  }

  // 处理正确答案
  let correctAnswerArray: string[]
  if (Array.isArray(correctAnswer)) {
    correctAnswerArray = correctAnswer
  } else {
    correctAnswerArray = [correctAnswer]
  }

  // 多选题/填空题多个答案：比较排序后的数组
  if (userAnswerArray.length > 1 || correctAnswerArray.length > 1) {
    const userSorted = userAnswerArray.map(v => v.trim()).sort()
    const correctSorted = correctAnswerArray.map(v => v.trim()).sort()
    return JSON.stringify(userSorted) === JSON.stringify(correctSorted)
  }

  // 单选题/判断题/单个填空：直接比较
  return userAnswerArray[0]?.trim() === correctAnswerArray[0]?.trim()
}

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

  const isCorrect = checkAnswer(currentAnswer.value, question.value.answer)
  const questionScore = 1

  // 计算答题时长
  const startTime = questionStartTime.value.get(currentOriginalIndex.value) || Date.now()
  const answerTime = Math.floor((Date.now() - startTime) / 1000)

  const record: AnswerRecord = {
    questionId: question.value.id,
    answer: currentAnswer.value,
    isCorrect,
    score: isCorrect ? questionScore : 0,
    answerTime
  }
  answerRecords.value.set(currentOriginalIndex.value, record)

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

function handleRetry() {
  answerRecords.value.clear()
  currentStep.value = 1
  currentAnswer.value = ''
  startTime.value = Date.now()
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
      console.log('自动登录成功')
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

    // 重置开始时间
    startTime.value = Date.now()

    // 记录第一题的开始时间
    questionStartTime.value.clear()
    questionStartTime.value.set(1, Date.now())
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

  // 记录题目开始时间（如果还没记录）
  if (!questionStartTime.value.has(currentOriginalIndex.value)) {
    questionStartTime.value.set(currentOriginalIndex.value, Date.now())
  }
}

function handlePrevQuestion() {
  if (currentStep.value > 1) {
    currentStep.value--
    syncQuestionState()
  }
}

function handleNextQuestion() {
  if (currentStep.value < totalSteps.value) {
    currentStep.value++
    syncQuestionState()
  }
}

function toggleCollect() {
  const currentCollected = questionCollected.value.get(currentOriginalIndex.value) || false
  questionCollected.value.set(currentOriginalIndex.value, !currentCollected)
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
  console.log('笔记已保存:', note)
}

function handleGoToSimilarQuestion(questionId: string) {
  uni.showToast({
    title: '跳转到题目: ' + questionId,
    icon: 'none'
  })
  // TODO: 实现跳转逻辑
}

function handleSelectSheetItem(index: number) {
  handleGoToQuestion(index - 1)
  closeAnswerSheet()
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

function openAnswerSheet() {
  isSheetVisible.value = true
}

function closeAnswerSheet() {
  isSheetVisible.value = false
}

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
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const bankId = currentPage?.options?.bankId
  const modeParam = currentPage?.options?.mode
  const viewModeParam = currentPage?.options?.viewMode
  const gotoIndex = currentPage?.options?.gotoIndex

  if (modeParam && ['practice', 'exercise', 'memorize'].includes(modeParam)) {
    mode.value = modeParam as PracticeMode
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

onBeforeUnmount(() => {
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

/* 原生 swiper 容器 - 最简单的配置 */
.swiper-container {
  flex: 1;
  width: 100%;
  overflow: hidden;
}

.question-swiper {
  width: 100%;
  height: 100%;
}

.swiper-item-content {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 32rpx;
  box-sizing: border-box;
}

.loading-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
