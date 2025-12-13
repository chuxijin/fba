/**
 * 答题卡组合式函数
 *
 * 管理答题卡的状态和数据
 */
import { ref, computed } from 'vue'

export type AnswerSheetStatus = 'selected' | 'unselected' | 'correct' | 'wrong'

export interface AnswerSheetItem {
  index: number
  status: AnswerSheetStatus
  isCurrent: boolean
}

export interface AnswerRecord {
  questionId: string
  answer: string
  isCorrect: boolean
  score: number
  answerTime?: number
}

export function useAnswerSheet() {
  // 答题卡可见性
  const isVisible = ref(false)

  /**
   * 构建答题卡数据
   */
  function buildItems(
    totalCount: number,
    currentIndex: number,
    answerRecords: Map<number, AnswerRecord>,
    isViewMode: boolean
  ): AnswerSheetItem[] {
    const items: AnswerSheetItem[] = []

    for (let i = 1; i <= totalCount; i++) {
      const record = answerRecords.get(i)
      let status: AnswerSheetStatus = 'unselected'

      if (record) {
        if (isViewMode) {
          // 查看模式：显示对错
          status = record.isCorrect ? 'correct' : 'wrong'
        } else {
          // 练习模式：只显示是否已答
          status = 'selected'
        }
      }

      items.push({
        index: i,
        status,
        isCurrent: i === currentIndex,
      })
    }

    return items
  }

  /**
   * 计算统计数据
   */
  function calculateStats(answerRecords: Map<number, AnswerRecord>, totalCount: number) {
    let correctCount = 0
    let wrongCount = 0
    const wrongQuestions: number[] = []

    answerRecords.forEach((record, questionIndex) => {
      if (record.isCorrect) {
        correctCount++
      } else {
        wrongCount++
        wrongQuestions.push(questionIndex)
      }
    })

    const completedCount = answerRecords.size
    const unansweredCount = totalCount - completedCount
    const accuracyRate = completedCount > 0
      ? Math.round((correctCount / completedCount) * 100)
      : 0

    return {
      totalCount,
      completedCount,
      correctCount,
      wrongCount,
      unansweredCount,
      accuracyRate,
      wrongQuestions: wrongQuestions.sort((a, b) => a - b),
    }
  }

  /**
   * 打开答题卡
   */
  function open() {
    isVisible.value = true
  }

  /**
   * 关闭答题卡
   */
  function close() {
    isVisible.value = false
  }

  /**
   * 切换答题卡
   */
  function toggle() {
    isVisible.value = !isVisible.value
  }

  return {
    isVisible,
    open,
    close,
    toggle,
    buildItems,
    calculateStats,
  }
}
