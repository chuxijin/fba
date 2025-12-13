<template>
  <view class="result-page">
    <scroll-view class="result-content" scroll-y enhanced show-scrollbar>
      <!-- 头部统计 -->
      <view class="result-header">
        <view class="result-score">
          <view class="result-score__circle">
            <view class="result-score__progress" :style="progressStyle"></view>
            <view class="result-score__inner">
              <text class="result-score__value">{{ accuracy }}%</text>
              <text class="result-score__label">本次正确率</text>
            </view>
          </view>
        </view>

        <view class="result-meta">
          <view class="result-meta__item">
            <text class="result-meta__icon">📊</text>
            <text class="result-meta__text">{{ practiceName }}</text>
          </view>
          <view class="result-meta__item">
            <text class="result-meta__icon">⏱</text>
            <text class="result-meta__text">用时 {{ duration }}</text>
          </view>
        </view>
      </view>

      <!-- 统计数据卡片 -->
      <view class="result-stats">
        <view class="result-stats__item">
          <text class="result-stats__value result-stats__value--primary">{{ totalCount }}</text>
          <text class="result-stats__label">题目总数</text>
        </view>
        <view class="result-stats__item">
          <text class="result-stats__value result-stats__value--success">{{ correctCount }}</text>
          <text class="result-stats__label">答对</text>
        </view>
        <view class="result-stats__item">
          <text class="result-stats__value result-stats__value--error">{{ wrongCount }}</text>
          <text class="result-stats__label">答错</text>
        </view>
        <view class="result-stats__item">
          <text class="result-stats__value result-stats__value--gray">{{ unansweredCount }}</text>
          <text class="result-stats__label">未答</text>
        </view>
      </view>

      <!-- 答题卡 - 使用统一组件 -->
      <AnswerSheetGrid
        :items="answerItems"
        mode="result"
        @select-item="handleSelectItem"
      />
    </scroll-view>

    <!-- 操作按钮 - 固定在底部 -->
    <view class="result-actions">
      <view class="result-actions__btn result-actions__btn--secondary" @tap="handleViewAll">
        查看全部解析
      </view>
      <view class="result-actions__btn result-actions__btn--primary" @tap="handleViewWrong">
        仅看错题
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AnswerSheetGrid from './modules/AnswerSheetGrid.vue'
import * as practiceApi from '../../api/business/practice'
import type { SessionSummaryData } from '../../api/business/practice'

declare const uni: any

interface AnswerItem {
  index: number
  question_id?: number
  status: 'correct' | 'wrong' | 'unanswered'
}

const practiceName = ref('')
const totalCount = ref(0)
const correctCount = ref(0)
const wrongCount = ref(0)
const unansweredCount = ref(0)
const duration = ref('')
const answerItems = ref<AnswerItem[]>([])

// 保存题库信息用于返回
const sessionId = ref<number | null>(null)  // 🔥 添加 sessionId
const bankId = ref<number | null>(null)
const practiceMode = ref<string>('practice')
const wrongQuestions = ref<number[]>([])

const accuracy = computed(() => {
  if (totalCount.value === 0) return 0
  return Math.round((correctCount.value / totalCount.value) * 100)
})

const progressStyle = computed(() => {
  const percentage = totalCount.value > 0 ? (correctCount.value / totalCount.value) * 100 : 0
  const degree = (percentage / 100) * 360
  return {
    background: `conic-gradient(
      #3b82f6 0deg,
      #3b82f6 ${degree}deg,
      rgba(148, 163, 184, 0.15) ${degree}deg,
      rgba(148, 163, 184, 0.15) 360deg
    )`
  }
})

function handleSelectItem(index: number) {
  // 返回到刷题页面，定位到指定题目（默认进入查看全部解析模式）
  if (!bankId.value) {
    uni.showToast({
      title: '题库信息丢失',
      icon: 'none'
    })
    return
  }

  // 🔥 如果有 sessionId，传递给刷题页面（查看历史模式）
  const sessionParam = sessionId.value ? `&sessionId=${sessionId.value}` : ''

  uni.navigateTo({
    url: `/pages/practice/detail?bankId=${bankId.value}&mode=${practiceMode.value}&viewMode=all&gotoIndex=${index}${sessionParam}`
  })
}

function handleViewAll() {
  // 返回到刷题页面，查看全部解析
  if (!bankId.value) {
    uni.showToast({
      title: '题库信息丢失',
      icon: 'none'
    })
    return
  }

  // 🔥 如果有 sessionId，传递给刷题页面（查看历史模式）
  const sessionParam = sessionId.value ? `&sessionId=${sessionId.value}` : ''

  const url = `/pages/practice/detail?bankId=${bankId.value}&mode=${practiceMode.value}&viewMode=all${sessionParam}`
  console.log('🔗 跳转 URL:', url)

  uni.navigateTo({
    url,
    fail: (err: any) => {
      console.error('❌ 跳转失败:', err)
      uni.showToast({
        title: '跳转失败: ' + JSON.stringify(err),
        icon: 'none',
        duration: 3000
      })
    },
    success: () => {
      console.log('✅ 跳转成功')
    }
  })
}

function handleViewWrong() {
  // 返回到刷题页面，只看错题
  if (!bankId.value) {
    uni.showToast({
      title: '题库信息丢失',
      icon: 'none'
    })
    return
  }

  // 保存错题列表到 storage
  uni.setStorageSync('practice-wrong-questions', wrongQuestions.value)

  // 🔥 如果有 sessionId，传递给刷题页面（查看历史模式）
  const sessionParam = sessionId.value ? `&sessionId=${sessionId.value}` : ''

  const url = `/pages/practice/detail?bankId=${bankId.value}&mode=${practiceMode.value}&viewMode=wrong${sessionParam}`
  console.log('🔗 跳转 URL:', url)

  uni.navigateTo({
    url,
    fail: (err: any) => {
      console.error('❌ 跳转失败:', err)
      uni.showToast({
        title: '跳转失败: ' + JSON.stringify(err),
        icon: 'none',
        duration: 3000
      })
    },
    success: () => {
      console.log('✅ 跳转成功')
    }
  })
}

onMounted(() => {
  // 从 URL 参数获取 sessionId（查看历史记录时）
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1]
  const options = (currentPage as any).options || {}
  const sessionId = options.sessionId

  if (sessionId) {
    // 从 API 加载历史数据
    loadSessionData(parseInt(sessionId))
  } else {
    // 从 storage 读取刚完成的练习数据
    loadStorageData()
  }
})

/**
 * 从 API 加载历史会话数据
 */
async function loadSessionData(loadSessionId: number) {
  try {
    console.log('📦 从 API 加载会话数据, sessionId:', loadSessionId)

    const data: SessionSummaryData = await practiceApi.getSessionSummary(loadSessionId)
    console.log('✅ 会话数据加载成功:', data)

    // 🔥 保存 sessionId
    sessionId.value = loadSessionId

    // 设置数据
    practiceName.value = data.practice_name || '练习'
    totalCount.value = data.total_count
    correctCount.value = data.correct_count
    wrongCount.value = data.wrong_count
    unansweredCount.value = data.unanswered_count
    duration.value = formatDuration(data.total_time)
    answerItems.value = data.answer_items
    bankId.value = data.bank_id || null
    practiceMode.value = data.session_type
    wrongQuestions.value = data.wrong_question_ids

    // 🔥 优化：缓存结算数据，供刷题页使用（减少 API 请求）
    uni.setStorageSync('history-session-summary', {
      sessionId: loadSessionId,
      bankId: data.bank_id,
      practiceName: data.practice_name,
      questionIds: data.answer_items.map(item => item.question_id),
      answerItems: data.answer_items,
      wrongQuestionIds: data.wrong_question_ids,
      timestamp: Date.now()
    })
  } catch (error: any) {
    console.error('❌ 加载会话数据失败:', error)
    uni.showToast({
      title: '加载失败: ' + (error.message || '未知错误'),
      icon: 'none',
      duration: 2000
    })
    setTimeout(() => {
      uni.navigateBack()
    }, 2000)
  }
}

/**
 * 从 storage 加载刚完成的练习数据
 */
function loadStorageData() {
  // 从存储中读取结算数据
  const resultData = uni.getStorageSync('practice-result')
  console.log('📦 结算数据:', resultData)

  if (resultData) {
    practiceName.value = resultData.practiceName || ''
    totalCount.value = resultData.totalCount || 0
    correctCount.value = resultData.correctCount || 0
    wrongCount.value = resultData.wrongCount || 0
    unansweredCount.value = resultData.unansweredCount || 0
    duration.value = resultData.duration || '0分0秒'
    answerItems.value = resultData.answerItems || []
    bankId.value = resultData.bankId || null
    practiceMode.value = resultData.mode || 'practice'
    wrongQuestions.value = resultData.wrongQuestions || []

    console.log('✅ 数据加载成功 - bankId:', bankId.value, 'mode:', practiceMode.value)

    // 读取后清除数据
    uni.removeStorageSync('practice-result')
  } else {
    console.error('❌ 没有找到结算数据')
    // 如果没有数据，返回上一页
    uni.showToast({
      title: '数据加载失败',
      icon: 'none'
    })
    setTimeout(() => {
      uni.navigateBack()
    }, 1500)
  }
}

/**
 * 格式化时长
 */
function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}秒`
  }
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (minutes < 60) {
    return secs > 0 ? `${minutes}分${secs}秒` : `${minutes}分钟`
  }
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return mins > 0 ? `${hours}小时${mins}分钟` : `${hours}小时`
}
</script>

<style scoped lang="scss">
.result-page {
  width: 100%;
  height: 100vh;
  background: var(--color-bg-page);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.result-content {
  flex: 1;
  width: 100%;
  padding: 40rpx 32rpx;
  padding-bottom: 144rpx;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 32rpx;
}

/* ============ 头部统计 ============ */
.result-header {
  background: var(--color-bg-card);
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
}

.result-score {
  display: flex;
  justify-content: center;
  margin-bottom: 40rpx;
}

.result-score__circle {
  position: relative;
  width: 320rpx;
  height: 320rpx;
}

.result-score__progress {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  transform: rotate(-90deg);
  filter: drop-shadow(0 4rpx 16rpx rgba(59, 130, 246, 0.25));
}

.result-score__inner {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 240rpx;
  height: 240rpx;
  background: var(--color-bg-card);
  border-radius: 50%;
}

.result-score__value {
  font-size: 88rpx;
  font-weight: 700;
  color: #3b82f6;
  line-height: 1;
  margin-bottom: 12rpx;
}

.result-score__label {
  font-size: 26rpx;
  color: var(--color-text-secondary);
}

.result-meta {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.result-meta__item {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 20rpx 24rpx;
  background: var(--color-bg-elevated);
  border-radius: 16rpx;
}

.result-meta__icon {
  font-size: 32rpx;
}

.result-meta__text {
  font-size: 26rpx;
  color: var(--color-text-secondary);
}

/* ============ 统计数据 ============ */
.result-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20rpx;
  background: var(--color-bg-card);
  border-radius: 24rpx;
  padding: 40rpx 20rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
}

.result-stats__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
}

.result-stats__value {
  font-size: 48rpx;
  font-weight: 700;
  line-height: 1;
}

.result-stats__value--primary {
  color: #3b82f6;
}

.result-stats__value--success {
  color: #10b981;
}

.result-stats__value--error {
  color: #ef4444;
}

.result-stats__value--gray {
  color: #94a3b8;
}

.result-stats__label {
  font-size: 24rpx;
  color: var(--color-text-secondary);
}

/* ============ 操作按钮 ============ */
.result-actions {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16rpx;
  padding: 24rpx 32rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
  background: var(--color-bg-page);
  border-top: 1rpx solid rgba(148, 163, 184, 0.15);
  box-shadow: 0 -4rpx 12rpx rgba(0, 0, 0, 0.05);
  z-index: 100;
}

.result-actions__btn {
  height: 96rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 48rpx;
  font-size: 32rpx;
  font-weight: 700;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.result-actions__btn--primary {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #ffffff;
  box-shadow: 0 8rpx 24rpx rgba(59, 130, 246, 0.35);
}

.result-actions__btn--secondary {
  background: var(--color-bg-card);
  color: #3b82f6;
  border: 2rpx solid #3b82f6;
}

.result-actions__btn:active {
  transform: scale(0.97);
}
</style>
