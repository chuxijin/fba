#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import { defineStore } from 'pinia'
import type { BaseQuestion } from '../components/practice/question-map'

/**
 * 答题记录
 */
interface AnswerRecord {
  questionId: number
  answer: string
  isCorrect: boolean
  score: number
  answerTime: number
}

/**
 * 答题会话状态
 */
interface PracticeSession {
  // 题库信息
  bankId: number
  bankName: string
  mode: 'practice' | 'exercise' | 'memorize'

  // 题目数据
  questions: BaseQuestion[]
  answers: Map<number, AnswerRecord>

  // 时间记录
  startTime: number
  endTime: number | null

  // 提交结果
  result: {
    totalScore: number
    totalCount: number
    correctCount: number
    wrongCount: number
    wrongQuestions: number[]
  } | null
}

/**
 * 答题状态管理 Store
 */
export const usePracticeStore = defineStore('practice', {
  state: () => ({
    // 当前答题会话
    currentSession: null as PracticeSession | null,

    // 查看模式
    reviewMode: null as 'all' | 'wrong' | null,

    // UI状态
    loadingState: 'idle' as 'idle' | 'loading' | 'success' | 'error',
    errorMessage: ''
  }),

  getters: {
    /**
     * 是否有活动会话
     */
    hasActiveSession(): boolean {
      return this.currentSession !== null
    },

    /**
     * 获取答题记录数组
     */
    answersArray(): Array<{ index: number } & AnswerRecord> {
      if (!this.currentSession) return []

      return Array.from(this.currentSession.answers.entries()).map(([index, record]) => ({
        index,
        ...record
      }))
    },

    /**
     * 获取错题列表
     */
    wrongQuestionIndexes(): number[] {
      if (!this.currentSession?.result) return []
      return this.currentSession.result.wrongQuestions
    },

    /**
     * 是否在查看模式
     */
    isReviewMode(): boolean {
      return this.reviewMode !== null
    }
  },

  actions: {
    /**
     * 开始新的答题会话
     *
     * :param bankId: 题库ID
     * :param bankName: 题库名称
     * :param mode: 答题模式
     */
    startSession(bankId: number, bankName: string, mode: 'practice' | 'exercise' | 'memorize') {
      this.currentSession = {
        bankId,
        bankName,
        mode,
        questions: [],
        answers: new Map(),
        startTime: Date.now(),
        endTime: null,
        result: null
      }
      this.reviewMode = null
      this.loadingState = 'idle'
      this.errorMessage = ''

      console.log('🎯 开始答题会话:', { bankId, bankName, mode })
    },

    /**
     * 设置题目数据
     *
     * :param questions: 题目列表
     */
    setQuestions(questions: BaseQuestion[]) {
      if (!this.currentSession) {
        console.warn('⚠️ 没有活动会话，无法设置题目')
        return
      }

      this.currentSession.questions = questions
      this.loadingState = 'success'

      console.log('📝 设置题目:', questions.length, '道')
    },

    /**
     * 保存答题记录
     *
     * :param index: 题目索引
     * :param record: 答题记录
     */
    saveAnswer(index: number, record: AnswerRecord) {
      if (!this.currentSession) {
        console.warn('⚠️ 没有活动会话，无法保存答案')
        return
      }

      this.currentSession.answers.set(index, record)
    },

    /**
     * 提交答案并保存结果
     *
     * :param result: 提交结果
     */
    submitResult(result: {
      totalScore: number
      totalCount: number
      correctCount: number
      wrongCount: number
      wrongQuestions: number[]
    }) {
      if (!this.currentSession) {
        console.warn('⚠️ 没有活动会话，无法提交结果')
        return
      }

      this.currentSession.endTime = Date.now()
      this.currentSession.result = result

      console.log('✅ 提交结果:', result)
    },

    /**
     * 进入查看模式
     *
     * :param mode: 查看模式
     */
    enterReviewMode(mode: 'all' | 'wrong') {
      if (!this.currentSession) {
        console.warn('⚠️ 没有活动会话，无法进入查看模式')
        return false
      }

      if (!this.currentSession.result) {
        console.warn('⚠️ 没有提交结果，无法进入查看模式')
        return false
      }

      this.reviewMode = mode
      console.log(`📖 进入查看模式: ${mode}`)
      return true
    },

    /**
     * 退出查看模式
     */
    exitReviewMode() {
      this.reviewMode = null
      console.log('👋 退出查看模式')
    },

    /**
     * 清除会话
     */
    clearSession() {
      this.currentSession = null
      this.reviewMode = null
      this.loadingState = 'idle'
      this.errorMessage = ''

      console.log('🧹 清除会话')
    },

    /**
     * 设置加载状态
     *
     * :param state: 加载状态
     */
    setLoadingState(state: 'idle' | 'loading' | 'success' | 'error', errorMessage = '') {
      this.loadingState = state
      this.errorMessage = errorMessage
    }
  },

  // 持久化配置
  persist: {
    enabled: true,
    strategies: [
      {
        key: 'practice-session',
        storage: {
          getItem: (key: string) => {
            // 使用 uni.getStorageSync
            if (typeof uni !== 'undefined') {
              const value = uni.getStorageSync(key)
              return value ? JSON.stringify(value) : null
            }
            return null
          },
          setItem: (key: string, value: string) => {
            // 使用 uni.setStorageSync
            if (typeof uni !== 'undefined') {
              const parsedValue = JSON.parse(value)

              // 恢复 Map 结构
              if (parsedValue.currentSession?.answers) {
                parsedValue.currentSession.answers = new Map(
                  Object.entries(parsedValue.currentSession.answers)
                )
              }

              uni.setStorageSync(key, parsedValue)
            }
          }
        }
      }
    ]
  }
})
