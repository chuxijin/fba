import { defineStore } from 'pinia'
import type { BaseQuestion } from '../components/practice/question-map'
import type { UserStatistics, BankProgressItem } from '@/api/business/practice'
import * as practiceApi from '@/api/business/practice'

/**
 * 缓存配置
 */
const CACHE_CONFIG = {
  defaultTTL: 5 * 60 * 1000,       // 默认缓存 5 分钟
  maxTTL: 30 * 60 * 1000,          // 最大缓存 30 分钟
  minRefreshInterval: 3000,         // 最小刷新间隔 3 秒（防抖）
}

/**
 * 缓存元数据
 */
interface CacheMetadata {
  data: UserStatistics
  timestamp: number  // 缓存时间戳
  ttl: number        // 有效期（毫秒）
}

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
    errorMessage: '',

    // 用户学习统计（按分类缓存，key: catId，0 表示全部）
    statisticsByCategory: new Map<number, CacheMetadata>(),
    statisticsLoading: false,
    lastRefreshTime: 0  // 最后一次刷新时间（用于防抖）
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
    },

    /**
     * 题库进度 Map（方便快速查找）
     *
     * :param catId: 分类 ID（可选，默认返回所有分类的数据）
     */
    bankProgressMap(): (catId?: number) => Map<number, BankProgressItem> {
      return (catId?: number) => {
        const map = new Map<number, BankProgressItem>()

        // 如果指定了分类，只返回该分类的数据
        if (catId !== undefined) {
          const cacheEntry = this.statisticsByCategory.get(catId || 0)
          if (cacheEntry?.data?.banks) {
            cacheEntry.data.banks.forEach(bank => {
              map.set(bank.bank_id, bank)
            })
          }
          return map
        }

        // 否则返回所有分类的数据
        this.statisticsByCategory.forEach(cacheEntry => {
          if (cacheEntry?.data?.banks) {
            cacheEntry.data.banks.forEach(bank => {
              map.set(bank.bank_id, bank)
            })
          }
        })
        return map
      }
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
    },

    /**
     * 检查缓存是否过期
     *
     * :param catId: 分类 ID（可选，0 或 undefined 表示全部）
     * :return: true 表示缓存过期或不存在
     */
    isCacheExpired(catId?: number): boolean {
      const cacheKey = catId || 0
      const cacheEntry = this.statisticsByCategory.get(cacheKey)

      if (!cacheEntry) return true

      const now = Date.now()
      const age = now - cacheEntry.timestamp
      return age > cacheEntry.ttl
    },

    /**
     * 加载用户学习统计（按分类缓存，带时效检测）
     *
     * :param catId: 分类 ID（可选，0 或 undefined 表示全部）
     * :param forceRefresh: 是否强制刷新（忽略缓存）
     */
    async loadUserStatistics(catId?: number, forceRefresh = false) {
      const cacheKey = catId || 0

      // 防抖：避免短时间内重复请求
      const now = Date.now()
      if (!forceRefresh && (now - this.lastRefreshTime) < CACHE_CONFIG.minRefreshInterval) {
        console.log('[PracticeStore] 刷新间隔过短，跳过请求')
        return this.statisticsByCategory.get(cacheKey)?.data
      }

      // 如果已有该分类的数据且未过期且不强制刷新，直接返回
      if (!forceRefresh && !this.isCacheExpired(catId)) {
        console.log('[PracticeStore] 缓存未过期，直接返回')
        return this.statisticsByCategory.get(cacheKey)?.data
      }

      // 避免并发请求
      if (this.statisticsLoading) {
        console.log('[PracticeStore] 正在加载中，跳过重复请求')
        return this.statisticsByCategory.get(cacheKey)?.data
      }

      try {
        this.statisticsLoading = true
        this.lastRefreshTime = now

        // 根据 catId 加载对应分类的统计数据
        const params = catId && catId !== 0 ? { cat_id: catId } : undefined
        const data = await practiceApi.getUserStatistics(params)

        // 缓存到 Map，带时间戳和 TTL
        const cacheEntry: CacheMetadata = {
          data,
          timestamp: Date.now(),
          ttl: CACHE_CONFIG.defaultTTL
        }
        this.statisticsByCategory.set(cacheKey, cacheEntry)

        console.log('[PracticeStore] 用户统计数据加载成功:', {
          catId: cacheKey,
          banksCount: data.banks.length,
          cached: true,
          expiresIn: CACHE_CONFIG.defaultTTL / 1000 + '秒'
        })
        return data
      } catch (error: any) {
        // 401 是正常情况（未登录），静默失败不打印错误
        if (error.code === 401 || error.statusCode === 401) {
          console.log('[PracticeStore] 未登录，无法获取学习统计')
        } else {
          // 其他错误才打印
          console.error('[PracticeStore] 加载用户统计失败:', error)
        }
        return null
      } finally {
        this.statisticsLoading = false
      }
    },

    /**
     * 获取指定题库的统计数据
     *
     * :param bankId: 题库 ID
     * :return: 题库统计数据
     */
    getBankStatistics(bankId: number): practiceApi.BankStatistics {
      // 从所有分类的缓存中查找该题库
      const allProgress = this.bankProgressMap()
      const bankProgress = allProgress.get(bankId)

      if (!bankProgress) {
        return {
          bank_id: bankId,
          total_questions: 0,
          practiced_count: 0,
          correct_count: 0,
          accuracy_rate: 0,
          total_time: 0,
          chapter_statistics: []
        }
      }

      return {
        bank_id: bankProgress.bank_id,
        total_questions: bankProgress.total_count,
        practiced_count: bankProgress.practiced_count,
        correct_count: bankProgress.correct_count,
        accuracy_rate: bankProgress.accuracy_rate,
        total_time: bankProgress.total_time,
        chapter_statistics: bankProgress.chapters.map(ch => ({
          chapter_id: ch.chapter_id,
          chapter_name: ch.chapter_name,
          total_questions: ch.total_count,
          practiced_count: ch.practiced_count,
          correct_count: ch.correct_count,
          accuracy_rate: ch.accuracy_rate
        }))
      }
    },

    /**
     * 刷新指定分类的统计数据（答题完成后调用）
     *
     * :param catId: 分类 ID（可选）
     */
    async refreshStatistics(catId?: number) {
      console.log('[PracticeStore] 刷新统计数据, catId:', catId)

      if (catId !== undefined) {
        // 刷新指定分类
        return this.loadUserStatistics(catId, true)
      }

      // 刷新所有已加载的分类
      const refreshPromises = Array.from(this.statisticsByCategory.keys()).map(key =>
        this.loadUserStatistics(key, true)
      )
      await Promise.all(refreshPromises)
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
