/**
 * 练习详情页核心逻辑 composable
 *
 * 整合题目加载、答题判断、会话管理、收藏等功能
 */
import { ref, computed } from 'vue'
import { authApi, bankApi, questionApiV2, practiceApi, favoriteApi, setToken } from '@/api'
import { adaptQuestionList, adaptListToComponentFormat } from '../utils/question-adapter-v2'
import type { BaseQuestion, PracticeMode } from '../components/business/question-map'
import type { AnswerRecord } from './useAnswerSheet'

declare const uni: any

export interface PracticeDetailOptions {
  onTimerReset?: () => void
  getElapsedSeconds?: () => number
  getCurrentPausedDuration?: () => number
}

export function usePracticeDetail(options: PracticeDetailOptions = {}) {
  // ============ 基础状态 ============
  const practiceName = ref('加载中...')
  const loading = ref(true)
  const allQuestions = ref<BaseQuestion[]>([])
  const currentBankId = ref<number | null>(null)
  const currentSessionId = ref<number | null>(null)

  // ============ 答题记录 ============
  const answerRecords = ref<Map<number, AnswerRecord>>(new Map())

  // ============ 收藏状态 ============
  const questionCollected = ref<Map<number, boolean>>(new Map())
  const questionMarkedWrong = ref<Map<number, boolean>>(new Map())
  const questionNotes = ref<Map<number, string>>(new Map())

  // ============ 题目计时 ============
  const questionStartTime = ref<Map<number, number>>(new Map())
  const questionStartPausedDuration = ref<Map<number, number>>(new Map())

  // ============ 用户登录 ============
  async function ensureLoggedIn(): Promise<boolean> {
    try {
      await authApi.getCurrentUser()
      return true
    } catch {
      try {
        const res = await authApi.testLogin({
          username: 'test_user',
          nickname: '测试用户'
        })
        setToken(res.access_token)
        return true
      } catch {
        uni.showToast({ title: '登录失败，请稍后重试', icon: 'none' })
        return false
      }
    }
  }

  // ============ 收藏管理 ============
  async function initializeFavoriteStatus() {
    if (allQuestions.value.length === 0) return

    try {
      const questionIds = allQuestions.value.map(q => Number(q.id))
      const statusMap = await favoriteApi.checkFavorited(questionIds)

      questionCollected.value.clear()
      allQuestions.value.forEach((q, index) => {
        const isFavorited = statusMap[Number(q.id)] || false
        questionCollected.value.set(index + 1, isFavorited)
      })
    } catch (error) {
      console.error('[收藏状态] 初始化失败:', error)
    }
  }

  async function toggleCollect(questionIndex: number, questionId: string): Promise<boolean> {
    if (!questionId) {
      uni.showToast({ title: '题目信息不完整', icon: 'none' })
      return false
    }

    const currentCollected = questionCollected.value.get(questionIndex) || false

    try {
      uni.showLoading({
        title: currentCollected ? '取消收藏中...' : '收藏中...',
        mask: true
      })

      const result = await favoriteApi.toggleFavorite(Number(questionId))
      uni.hideLoading()

      const newCollected = result.action === 'add'
      questionCollected.value.set(questionIndex, newCollected)

      uni.showToast({
        title: result.action === 'add' ? '已收藏' : '取消收藏',
        icon: 'success',
        duration: 1500
      })

      return true
    } catch (error) {
      uni.hideLoading()
      console.error('[收藏操作] 失败:', error)
      uni.showToast({ title: '操作失败，请重试', icon: 'none', duration: 2000 })
      return false
    }
  }

  // ============ 会话管理 ============
  async function createPracticeSession(
    bankId: number | null,
    chapterId: number | null,
    sessionType: practiceApi.SessionType,
    totalCount: number
  ) {
    try {
      const questionIds = allQuestions.value.map(q => Number(q.id))
      const session = await practiceApi.createSession({
        session_type: sessionType,
        bank_id: bankId || undefined,
        chapter_id: chapterId || undefined,
        question_ids: questionIds,
        total_count: totalCount
      })
      currentSessionId.value = session.id
    } catch (error) {
      console.error('[练习会话] 创建失败:', error)
      currentSessionId.value = null
    }
  }

  function calculateCurrentStats() {
    let completedCount = 0
    let correctCount = 0
    let wrongCount = 0

    answerRecords.value.forEach((record) => {
      completedCount++
      if (record.isCorrect) {
        correctCount++
      } else {
        wrongCount++
      }
    })

    const totalTime = options.getElapsedSeconds?.() || 0
    return { completedCount, correctCount, wrongCount, totalTime }
  }

  /**
   * 保存答题记录并更新会话统计
   *
   * 注意：答题时创建临时记录，提交时会删除旧记录并批量创建最终记录
   *
   * :param record: 答题记录
   * :param viewMode: 查看模式（非 null 时不保存）
   */
  async function saveAnswerRecord(record: AnswerRecord, viewMode: string | null) {
    if (!currentSessionId.value || viewMode !== null) return

    try {
      // 创建答题记录（临时，提交时会被删除并重新创建）
      await practiceApi.createRecord({
        session_id: currentSessionId.value,
        bank_id: currentBankId.value || 0,
        question_id: Number(record.questionId),
        user_answer: record.answer,
        is_correct: record.isCorrect,
        answer_time: record.answerTime || 0
      })

      // 更新会话统计
      const stats = calculateCurrentStats()
      await practiceApi.updateSession(currentSessionId.value, {
        completed_count: stats.completedCount,
        correct_count: stats.correctCount,
        wrong_count: stats.wrongCount,
        total_time: stats.totalTime
      })
    } catch (error) {
      console.error('[答题记录] 保存失败:', error)
    }
  }

  async function saveCurrentProgress() {
    if (!currentSessionId.value) return

    try {
      const stats = calculateCurrentStats()
      await practiceApi.updateSession(currentSessionId.value, {
        completed_count: stats.completedCount,
        correct_count: stats.correctCount,
        wrong_count: stats.wrongCount,
        total_time: stats.totalTime
      })
    } catch (error) {
      console.error('[答题页] 保存进度失败:', error)
    }
  }

  // ============ 答题逻辑 ============
  function checkAnswer(userAnswer: string, correctAnswer: string | string[] | undefined): boolean {
    if (!correctAnswer) return false

    let userAnswerArray: string[]
    try {
      const parsed = JSON.parse(userAnswer)
      userAnswerArray = Array.isArray(parsed) ? parsed : [userAnswer]
    } catch {
      userAnswerArray = [userAnswer]
    }

    let correctAnswerArray: string[]
    if (Array.isArray(correctAnswer)) {
      correctAnswerArray = correctAnswer
    } else {
      correctAnswerArray = [correctAnswer]
    }

    if (userAnswerArray.length > 1 || correctAnswerArray.length > 1) {
      const userSorted = userAnswerArray.map(v => v.trim()).sort()
      const correctSorted = correctAnswerArray.map(v => v.trim()).sort()
      return JSON.stringify(userSorted) === JSON.stringify(correctSorted)
    }

    return userAnswerArray[0]?.trim() === correctAnswerArray[0]?.trim()
  }

  function recordQuestionStart(questionIndex: number, currentPausedDuration: number) {
    if (!questionStartTime.value.has(questionIndex)) {
      questionStartTime.value.set(questionIndex, Date.now())
      questionStartPausedDuration.value.set(questionIndex, currentPausedDuration)
    }
  }

  function calculateAnswerTime(questionIndex: number): number {
    const questionStartTimeValue = questionStartTime.value.get(questionIndex) || Date.now()
    const questionStartPausedValue = questionStartPausedDuration.value.get(questionIndex) || 0
    const currentPausedTotal = options.getCurrentPausedDuration?.() || 0
    const actualElapsed = Date.now() - questionStartTimeValue - (currentPausedTotal - questionStartPausedValue)
    return Math.floor(actualElapsed / 1000)
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

    return {
      score: totalScore,
      totalCount: allQuestions.value.length,
      correctCount,
      wrongCount,
      wrongQuestions: wrongQuestions.sort((a, b) => a - b)
    }
  }

  // ============ 题目加载 ============
  async function loadQuestions(bankId: number): Promise<boolean> {
    try {
      loading.value = true
      currentBankId.value = bankId

      if (!await ensureLoggedIn()) return false

      const bankInfo = await bankApi.getBankDetail(bankId)
      practiceName.value = bankInfo.name

      const questionList = await questionApiV2.getBankPracticeQuestions(bankId)

      if (!questionList?.length) {
        uni.showToast({ title: '该题库暂无题目', icon: 'none', duration: 2000 })
        setTimeout(() => uni.navigateBack(), 2000)
        return false
      }

      const frontendQuestions = adaptQuestionList(questionList as any, false)
      allQuestions.value = adaptListToComponentFormat(frontendQuestions)

      options.onTimerReset?.()
      resetQuestionTiming()

      await createPracticeSession(bankId, null, 'bank', allQuestions.value.length)
      await initializeFavoriteStatus()

      return true
    } catch (error) {
      console.error('加载题目失败:', error)
      uni.showToast({ title: '加载题目失败', icon: 'none', duration: 2000 })
      setTimeout(() => uni.navigateBack(), 2000)
      return false
    } finally {
      loading.value = false
    }
  }

  async function loadHistorySession(
    sessionId: number,
    viewModeParam?: string,
    gotoIndex?: string
  ): Promise<{ viewMode: 'all' | 'wrong', startIndex: number } | null> {
    try {
      loading.value = true
      currentSessionId.value = sessionId

      const cachedSummary = uni.getStorageSync('history-session-summary')
      const CACHE_TTL = 5 * 60 * 1000

      let questionIds: number[]
      let practiceNameStr: string | null = null
      let answerItemsFromCache: any[] = []

      if (cachedSummary?.sessionId === sessionId && (Date.now() - cachedSummary.timestamp) < CACHE_TTL) {
        questionIds = cachedSummary.questionIds
        practiceNameStr = cachedSummary.practiceName
        currentBankId.value = cachedSummary.bankId || null
        answerItemsFromCache = cachedSummary.answerItems || []
      } else {
        const session = await practiceApi.getSession(sessionId)
        currentBankId.value = session.bank_id || null
        questionIds = session.question_ids || []
        practiceNameStr = session.practice_name || '练习'
      }

      if (!questionIds?.length) {
        uni.showToast({ title: '该会话没有题目数据', icon: 'none', duration: 2000 })
        setTimeout(() => uni.navigateBack(), 2000)
        return null
      }

      const questionList = await questionApiV2.getQuestions({ ids: questionIds.join(',') })
      const frontendQuestions = adaptQuestionList(questionList as any, false)
      allQuestions.value = adaptListToComponentFormat(frontendQuestions)
      practiceName.value = practiceNameStr || '练习'

      let records: any[]
      if (answerItemsFromCache.length > 0) {
        records = answerItemsFromCache.map(item => ({
          question_id: item.question_id,
          is_correct: item.status === 'correct',
          user_answer: '',
          answer_time: 0
        }))
      } else {
        records = await practiceApi.getSessionRecords(sessionId)
      }

      restoreAnswerRecords(records, questionIds)
      await initializeFavoriteStatus()

      return {
        viewMode: viewModeParam === 'wrong' ? 'wrong' : 'all',
        startIndex: gotoIndex ? Number(gotoIndex) : 1  // gotoIndex 已经是 1-based，不需要 +1
      }
    } catch (error) {
      console.error('[查看历史] 加载失败:', error)
      uni.showToast({ title: '加载历史失败', icon: 'none', duration: 2000 })
      setTimeout(() => uni.navigateBack(), 2000)
      return null
    } finally {
      loading.value = false
    }
  }

  async function resumeInProgressSession(sessionId: number): Promise<number | null> {
    try {
      loading.value = true
      currentSessionId.value = sessionId

      const session = await practiceApi.getSession(sessionId)
      currentBankId.value = session.bank_id || null
      const questionIds = session.question_ids || []

      if (!questionIds?.length) {
        uni.showToast({ title: '该会话没有题目数据', icon: 'none', duration: 2000 })
        setTimeout(() => uni.navigateBack(), 2000)
        return null
      }

      const questionList = await questionApiV2.getQuestions({ ids: questionIds.join(',') })
      const frontendQuestions = adaptQuestionList(questionList as any, false)
      allQuestions.value = adaptListToComponentFormat(frontendQuestions)
      practiceName.value = session.practice_name || '练习'

      const records = await practiceApi.getSessionRecords(sessionId)
      restoreAnswerRecords(records, questionIds)

      // 找第一道未答题
      let firstUnansweredIndex = 1
      for (let i = 1; i <= questionIds.length; i++) {
        if (!answerRecords.value.has(i)) {
          firstUnansweredIndex = i
          break
        }
      }

      const previousTotalTime = session.total_time || 0
      options.onTimerReset?.()

      questionStartTime.value.clear()
      questionStartPausedDuration.value.clear()
      questionStartTime.value.set(firstUnansweredIndex, Date.now())
      questionStartPausedDuration.value.set(firstUnansweredIndex, 0)

      await initializeFavoriteStatus()

      return firstUnansweredIndex
    } catch (error) {
      console.error('[继续答题] 恢复失败:', error)
      uni.showToast({ title: '恢复练习失败', icon: 'none', duration: 2000 })
      setTimeout(() => uni.navigateBack(), 2000)
      return null
    } finally {
      loading.value = false
    }
  }

  async function loadFavoriteQuestions(questionIds: number[], bankName?: string): Promise<boolean> {
    try {
      loading.value = true

      if (!await ensureLoggedIn()) return false

      practiceName.value = decodeURIComponent(bankName || '我的收藏')

      const questionPromises = questionIds.map(id => questionApiV2.getQuestionDetail(id))
      const questionList = await Promise.all(questionPromises)

      if (!questionList?.length) {
        uni.showToast({ title: '没有找到收藏的题目', icon: 'none', duration: 2000 })
        setTimeout(() => uni.navigateBack(), 2000)
        return false
      }

      const frontendQuestions = adaptQuestionList(questionList as any, true)
      allQuestions.value = adaptListToComponentFormat(frontendQuestions)

      options.onTimerReset?.()
      resetQuestionTiming()

      // 收藏模式：所有题目标记为已收藏
      questionCollected.value.clear()
      allQuestions.value.forEach((_, index) => {
        questionCollected.value.set(index + 1, true)
      })

      return true
    } catch (error) {
      console.error('[收藏模式] 加载题目失败:', error)
      uni.showToast({ title: '加载收藏题目失败', icon: 'none', duration: 2000 })
      setTimeout(() => uni.navigateBack(), 2000)
      return false
    } finally {
      loading.value = false
    }
  }

  // ============ 辅助函数 ============
  function restoreAnswerRecords(records: any[], questionIds: number[]) {
    const recordMap = new Map<number, any>()
    records.forEach(record => recordMap.set(record.question_id, record))

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
  }

  function resetQuestionTiming() {
    questionStartTime.value.clear()
    questionStartPausedDuration.value.clear()
    questionStartTime.value.set(1, Date.now())
    questionStartPausedDuration.value.set(1, 0)
  }

  function reset() {
    answerRecords.value.clear()
    questionCollected.value.clear()
    questionMarkedWrong.value.clear()
    questionNotes.value.clear()
    questionStartTime.value.clear()
    questionStartPausedDuration.value.clear()
  }

  return {
    // 状态
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

    // 收藏
    initializeFavoriteStatus,
    toggleCollect,

    // 会话
    createPracticeSession,
    calculateCurrentStats,
    saveAnswerRecord,
    saveCurrentProgress,

    // 答题
    checkAnswer,
    recordQuestionStart,
    calculateAnswerTime,
    calculateResult,

    // 加载
    loadQuestions,
    loadHistorySession,
    resumeInProgressSession,
    loadFavoriteQuestions,

    // 辅助
    reset,
  }
}
