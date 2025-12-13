/**
 * 练习会话管理组合式函数
 *
 * 负责会话的创建、更新、保存进度等操作
 */
import { ref, computed } from 'vue'
import { practiceApi } from '@/api'
import type { SessionType, SessionDetail } from '@/api/business/practice'

export interface AnswerRecord {
  questionId: string
  answer: string
  isCorrect: boolean
  score: number
  answerTime?: number
}

export interface SessionStats {
  completedCount: number
  correctCount: number
  wrongCount: number
  totalTime: number
}

export function usePracticeSession() {
  // 会话状态
  const sessionId = ref<number | null>(null)
  const bankId = ref<number | null>(null)
  const chapterId = ref<number | null>(null)
  const practiceName = ref('加载中...')

  // 答题记录
  const answerRecords = ref<Map<number, AnswerRecord>>(new Map())

  // 计算统计数据
  const stats = computed<SessionStats>(() => {
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

    return { completedCount, correctCount, wrongCount, totalTime: 0 }
  })

  /**
   * 创建练习会话
   */
  async function createSession(params: {
    sessionType: SessionType
    bankId?: number
    chapterId?: number
    questionIds: number[]
    totalCount: number
  }): Promise<SessionDetail | null> {
    try {
      const session = await practiceApi.createSession({
        session_type: params.sessionType,
        bank_id: params.bankId,
        chapter_id: params.chapterId,
        question_ids: params.questionIds,
        total_count: params.totalCount,
      })

      sessionId.value = session.id
      bankId.value = params.bankId || null
      chapterId.value = params.chapterId || null

      console.log(`[练习会话] 已创建 session_id=${session.id}`)
      return session
    } catch (error) {
      console.error('[练习会话] 创建失败:', error)
      return null
    }
  }

  /**
   * 保存单条答题记录
   */
  async function saveRecord(record: AnswerRecord): Promise<boolean> {
    if (!sessionId.value) return false

    try {
      await practiceApi.createRecord({
        session_id: sessionId.value,
        bank_id: bankId.value || 0,
        question_id: Number(record.questionId),
        user_answer: record.answer,
        is_correct: record.isCorrect,
        answer_time: record.answerTime || 0,
      })
      return true
    } catch (error) {
      console.error('[答题记录] 保存失败:', error)
      return false
    }
  }

  /**
   * 更新会话统计
   */
  async function updateStats(totalTime: number): Promise<boolean> {
    if (!sessionId.value) return false

    try {
      const currentStats = stats.value
      await practiceApi.updateSession(sessionId.value, {
        completed_count: currentStats.completedCount,
        correct_count: currentStats.correctCount,
        wrong_count: currentStats.wrongCount,
        total_time: totalTime,
      })
      return true
    } catch (error) {
      console.error('[会话统计] 更新失败:', error)
      return false
    }
  }

  /**
   * 保存答题记录并更新统计（组合操作）
   */
  async function saveAnswerAndUpdateStats(record: AnswerRecord, totalTime: number) {
    // 先保存本地
    const index = answerRecords.value.size + 1
    answerRecords.value.set(index, record)

    // 异步保存到后端（不阻塞用户操作）
    Promise.all([
      saveRecord(record),
      updateStats(totalTime),
    ]).catch(error => {
      console.error('[答题] 后端同步失败:', error)
    })
  }

  /**
   * 提交会话
   */
  async function submitSession(score?: number): Promise<boolean> {
    if (!sessionId.value) return false

    try {
      await practiceApi.submitSession(sessionId.value, { score })
      console.log('[练习会话] 已提交')
      return true
    } catch (error) {
      console.error('[练习会话] 提交失败:', error)
      return false
    }
  }

  /**
   * 放弃会话
   */
  async function abandonSession(): Promise<boolean> {
    if (!sessionId.value) return false

    try {
      await practiceApi.abandonSession(sessionId.value)
      console.log('[练习会话] 已放弃')
      return true
    } catch (error) {
      console.error('[练习会话] 放弃失败:', error)
      return false
    }
  }

  /**
   * 重置状态
   */
  function reset() {
    sessionId.value = null
    bankId.value = null
    chapterId.value = null
    practiceName.value = '加载中...'
    answerRecords.value.clear()
  }

  /**
   * 从已有会话恢复状态
   */
  function restoreFromSession(session: SessionDetail) {
    sessionId.value = session.id
    bankId.value = session.bank_id || null
    chapterId.value = session.chapter_id || null
  }

  /**
   * 恢复答题记录
   */
  function restoreRecords(records: Array<{
    question_id: number
    user_answer: string | string[]
    is_correct: boolean
    answer_time?: number
  }>, questionIds: number[]) {
    answerRecords.value.clear()

    const recordMap = new Map<number, typeof records[0]>()
    records.forEach(r => recordMap.set(r.question_id, r))

    questionIds.forEach((qid, index) => {
      const record = recordMap.get(qid)
      if (record) {
        answerRecords.value.set(index + 1, {
          questionId: String(qid),
          answer: typeof record.user_answer === 'string'
            ? record.user_answer
            : record.user_answer.join(','),
          isCorrect: record.is_correct,
          score: record.is_correct ? 1 : 0,
          answerTime: record.answer_time || 0,
        })
      }
    })
  }

  return {
    // 状态
    sessionId,
    bankId,
    chapterId,
    practiceName,
    answerRecords,
    stats,

    // 方法
    createSession,
    saveRecord,
    updateStats,
    saveAnswerAndUpdateStats,
    submitSession,
    abandonSession,
    reset,
    restoreFromSession,
    restoreRecords,
  }
}
