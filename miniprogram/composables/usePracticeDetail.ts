/**
 * 练习详情页核心逻辑 composable
 *
 * 整合题目加载、答题判断、会话管理、收藏等功能
 */
import { ref, computed } from 'vue'
import { authApi, questionApiV2, practiceApi, favoriteApi, noteApi, setToken } from '@/api'
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

  // ============ 笔记状态 ============
  const questionNoteIds = ref<Map<number, number>>(new Map())
  const questionNoteIsPublic = ref<Map<number, boolean>>(new Map())

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

  // ============ 收藏与笔记管理 ============
  /**
   * 初始化收藏状态和笔记数据（并行调用）
   */
  async function initializeFavoriteStatus() {
    if (allQuestions.value.length === 0) return

    try {
      const questionIds = allQuestions.value.map(q => Number(q.id))

      // 🔥 并行调用收藏和笔记两个接口
      const [favoriteStatusMap, noteDataMap] = await Promise.all([
        favoriteApi.checkFavorited(questionIds),
        noteApi.batchGetMyNotes(questionIds)
      ])

      // 清空旧数据
      questionCollected.value.clear()
      questionNoteIds.value.clear()
      questionNotes.value.clear()
      questionNoteIsPublic.value.clear()

      // 设置收藏状态和笔记数据
      allQuestions.value.forEach((q, index) => {
        const questionId = Number(q.id)
        const questionIndex = index + 1

        // 收藏状态
        const isFavorited = favoriteStatusMap[questionId] || false
        questionCollected.value.set(questionIndex, isFavorited)

        // 笔记数据
        const noteData = noteDataMap[questionId]
        if (noteData) {
          questionNoteIds.value.set(questionIndex, noteData.id)
          questionNotes.value.set(questionIndex, noteData.content)
          questionNoteIsPublic.value.set(questionIndex, noteData.is_public)
        }
      })

      console.log('[初始化] 收藏状态和笔记数据加载完成')
    } catch (error) {
      console.error('[初始化] 收藏状态和笔记加载失败:', error)
    }
  }

  async function toggleCollect(questionIndex: number, questionId: string): Promise<boolean> {
    if (!questionId) {
      uni.showToast({ title: '题目信息不完整', icon: 'none' })
      return false
    }

    const currentCollected = questionCollected.value.get(questionIndex) || false

    try {
      const result = await favoriteApi.toggleFavorite(Number(questionId))

      const newCollected = result.action === 'add'
      questionCollected.value.set(questionIndex, newCollected)

      return true
    } catch (error) {
      console.error('[收藏操作] 失败:', error)
      uni.showToast({ title: '操作失败，请重试', icon: 'none', duration: 2000 })
      return false
    }
  }

  // ============ 会话管理 ============

  /**
   * 开始新的练习（核心链路）
   *
   * 流程：创建会话 → 会话返回题目列表 → 直接使用
   *
   * :param params: 创建会话参数
   */
  async function startPractice(params: {
    session_type: practiceApi.SessionType
    bank_id?: number
    chapter_id?: number
    limit?: number
    shuffle?: boolean
    includeAnswer?: boolean  // 🔥 是否包含答案和解析（背题模式）
  }): Promise<boolean> {
    try {
      loading.value = true

      if (!await ensureLoggedIn()) return false

      // 创建会话（后端直接返回题目列表）
      const session = await practiceApi.createSession({
        session_type: params.session_type,
        bank_id: params.bank_id,
        chapter_id: params.chapter_id,
        limit: params.limit,
        shuffle: params.shuffle
      })

      currentSessionId.value = session.id
      currentBankId.value = session.bank_id || null
      practiceName.value = (session as any).practice_name || '练习'

      // 直接使用会话返回的题目列表
      const questions = (session as any).questions || []

      if (!questions.length) {
        uni.showToast({ title: '该练习没有题目', icon: 'none', duration: 2000 })
        setTimeout(() => uni.navigateBack(), 2000)
        return false
      }

      // 🔥 转换题目格式（背题模式包含解析）
      const includeAnalysis = params.includeAnswer || false
      const frontendQuestions = adaptQuestionList(questions, includeAnalysis)
      allQuestions.value = adaptListToComponentFormat(frontendQuestions)

      // 初始化计时器和收藏状态
      options.onTimerReset?.()
      resetQuestionTiming()
      await initializeFavoriteStatus()

      return true
    } catch (error) {
      console.error('[开始练习] 失败:', error)
      uni.showToast({ title: '开始练习失败', icon: 'none', duration: 2000 })
      setTimeout(() => uni.navigateBack(), 2000)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载背题模式题目（不创建会话，直接获取带答案的题目列表）
   *
   * :param params: 加载参数
   */
  async function loadMemorizeQuestions(params: {
    bank_id?: number
    chapter_id?: number
    bank_name?: string  // 可选的题库名称
  }): Promise<boolean> {
    try {
      loading.value = true

      if (!await ensureLoggedIn()) return false

      // 设置题库信息
      if (params.bank_id) {
        currentBankId.value = params.bank_id
        practiceName.value = params.bank_name || '背题模式'
      }

      // 🔥 调用 queryQuestions API，传递 bank_id/chapter_id 和 include_answer=true
      const queryParams: any = {
        include_answer: true
      }

      if (params.bank_id) {
        queryParams.bank_id = params.bank_id
      }

      if (params.chapter_id) {
        queryParams.chapter_id = params.chapter_id
      }

      // 调用题目查询 API（include_answer=true）
      const questions = await questionApiV2.queryQuestions(queryParams)

      if (!questions || questions.length === 0) {
        uni.showToast({ title: '没有可用的题目', icon: 'none', duration: 2000 })
        setTimeout(() => uni.navigateBack(), 2000)
        return false
      }

      // 转换题目格式（包含解析）
      const frontendQuestions = adaptQuestionList(questions as any, true)
      allQuestions.value = adaptListToComponentFormat(frontendQuestions)

      // 初始化计时器和收藏状态
      options.onTimerReset?.()
      resetQuestionTiming()
      await initializeFavoriteStatus()

      // 🔥 背题模式不创建会话（无需提交）
      currentSessionId.value = null

      return true
    } catch (error) {
      console.error('[背题模式] 加载失败:', error)
      uni.showToast({ title: '加载题目失败', icon: 'none', duration: 2000 })
      setTimeout(() => uni.navigateBack(), 2000)
      return false
    } finally {
      loading.value = false
    }
  }

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
   * 保存答题记录
   *
   * :param record: 答题记录
   * :param viewMode: 查看模式（非 null 时不保存）
   */
  async function saveAnswerRecord(record: AnswerRecord, viewMode: string | null) {
    if (!currentSessionId.value || viewMode !== null) return

    try {
      await practiceApi.createRecords({
        session_id: currentSessionId.value,
        records: [{
          question_id: Number(record.questionId),
          user_answer: record.answer,
          // 🔥 不传 is_correct，submit 时后端统一判题
          answer_time: record.answerTime || 0
        }]
      })
    } catch (error) {
      console.error('[答题记录] 保存失败:', error)
      // 给用户明确的错误提示
      uni.showToast({
        title: '答题记录保存失败，请检查网络',
        icon: 'none',
        duration: 2000
      })
    }
  }

  /**
   * 保存当前进度（只保存 total_time，统计数据在提交时计算）
   */
  async function saveCurrentProgress() {
    if (!currentSessionId.value) return

    try {
      const totalTime = options.getElapsedSeconds?.() || 0
      await practiceApi.updateSession(currentSessionId.value, {
        total_time: totalTime
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

  // ============ 历史会话加载 ============
  async function loadHistorySession(
    sessionId: number,
    viewModeParam?: string,
    gotoIndex?: string
  ): Promise<{ viewMode: 'all' | 'wrong', startIndex: number } | null> {
    try {
      loading.value = true
      currentSessionId.value = sessionId

      // 🔥 直接从 API 加载会话详情（包含题目和答案解析）
      const session = await practiceApi.getSession(sessionId)
      currentBankId.value = session.bank_id || null
      const questionIds = session.question_ids || []
      const questions = (session as any).questions || []

      if (!questions.length) {
        uni.showToast({ title: '该会话没有题目数据', icon: 'none', duration: 2000 })
        setTimeout(() => uni.navigateBack(), 2000)
        return null
      }

      // 🔥 直接使用会话返回的题目列表（含答案解析）
      const frontendQuestions = adaptQuestionList(questions as any, true)
      allQuestions.value = adaptListToComponentFormat(frontendQuestions)
      practiceName.value = session.practice_name || '练习'

      const records = await practiceApi.getSessionRecords(sessionId)
      restoreAnswerRecords(records, questionIds)
      await initializeFavoriteStatus()

      return {
        viewMode: viewModeParam === 'wrong' ? 'wrong' : 'all',
        startIndex: gotoIndex ? Number(gotoIndex) : 1
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

      // 🔥 获取会话详情（包含题目和答案解析）
      const session = await practiceApi.getSession(sessionId)
      currentBankId.value = session.bank_id || null
      const questionIds = session.question_ids || []
      const questions = (session as any).questions || []

      if (!questions.length) {
        uni.showToast({ title: '该会话没有题目数据', icon: 'none', duration: 2000 })
        setTimeout(() => uni.navigateBack(), 2000)
        return null
      }

      // 🔥 直接使用会话返回的题目列表（含答案解析）
      const frontendQuestions = adaptQuestionList(questions as any, true)
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

  async function loadWrongQuestions(questionIds: number[], bankName?: string): Promise<boolean> {
    try {
      loading.value = true

      if (!await ensureLoggedIn()) return false

      practiceName.value = decodeURIComponent(bankName || '我的错题')

      const questionPromises = questionIds.map(id => questionApiV2.getQuestionDetail(id))
      const questionList = await Promise.all(questionPromises)

      if (!questionList?.length) {
        uni.showToast({ title: '没有找到错题', icon: 'none', duration: 2000 })
        setTimeout(() => uni.navigateBack(), 2000)
        return false
      }

      const frontendQuestions = adaptQuestionList(questionList as any, true)
      allQuestions.value = adaptListToComponentFormat(frontendQuestions)

      options.onTimerReset?.()
      resetQuestionTiming()

      // 错题模式：批量查询收藏状态
      await initializeFavoriteStatus()

      return true
    } catch (error) {
      console.error('[错题模式] 加载题目失败:', error)
      uni.showToast({ title: '加载错题失败', icon: 'none', duration: 2000 })
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
          answer: record.user_answer,  // 🔥 直接使用原始格式（字符串或数组）
          isCorrect: record.is_correct,
          score: record.is_correct ? 1 : 0,
          answerTime: record.answer_time || 0,
          submitted: true  // 历史记录和继续答题的记录都是已提交的
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
    questionNoteIds,
    questionNoteIsPublic,
    questionStartTime,
    questionStartPausedDuration,

    // 收藏
    initializeFavoriteStatus,
    toggleCollect,

    // 会话
    startPractice,
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
    loadHistorySession,
    resumeInProgressSession,
    loadFavoriteQuestions,
    loadWrongQuestions,
    loadMemorizeQuestions,  // 🔥 背题模式加载

    // 辅助
    reset,
  }
}
