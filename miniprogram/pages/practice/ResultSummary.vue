<template>
  <view class="result-page">
    <scroll-view class="result-content" scroll-y enhanced show-scrollbar>
      <!-- 头部统计 -->
      <view class="result-header">
        <view class="result-score">
          <!-- 圆形进度条 -->
          <l-progress-circle
            index="result"
            :percent="accuracy"
            :strokeWidth="10"
            bg-color="#e5e7eb"
            progress-color="#3b82f6"
            width="280rpx"
            height="140rpx"
          >
            <view class="circle-progress__inner">
              <text class="circle-progress__value">{{ accuracy }}%</text>
              <text class="circle-progress__label">正确率</text>
            </view>
          </l-progress-circle>
        </view>

        <view class="result-meta">
          <view class="result-meta__item">
            <text class="result-meta__icon">📊</text>
            <text class="result-meta__text">{{ practiceName }}</text>
          </view>
          <view class="result-meta__item">
            <text class="result-meta__icon">⏱</text>
            <text class="result-meta__text">{{ duration }}</text>
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
import LProgressCircle from '@/components/myUI/l-progress-circle/components/l-progress-circle/l-progress-circle.vue'
import { getSessionReport, getSessionSolution, type SessionReport, type SessionSolution } from '../../api/business/practice'
import { formatDuration } from '../../utils/format'

declare const uni: any

interface AnswerItem {
  index: number
  questionId?: number  // 统一使用驼峰命名
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
const solutionData = ref<SessionSolution | null>(null)  // 🔥 存储解析数据

const accuracy = computed(() => {
  if (totalCount.value === 0) return 0
  return Math.round((correctCount.value / totalCount.value) * 100)
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
  // 从 URL 参数获取 sessionId
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1]
  const options = (currentPage as any).options || {}
  const urlSessionId = options.sessionId

  if (urlSessionId) {
    loadSessionReport(parseInt(urlSessionId))
  } else {
    uni.showToast({ title: '缺少会话参数', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 1500)
  }
})

/**
 * 从 API 加载会话报告和解析数据
 */
async function loadSessionReport(loadSessionId: number) {
  try {
    uni.showLoading({ title: '加载中...', mask: true })

    // 🔥 优先使用缓存的 solution 数据（提交时已预取）
    let cachedSolution = uni.getStorageSync('practice-solution')
    let solutionResult: any = null

    if (cachedSolution && cachedSolution.session_id === loadSessionId) {
      console.log('[结算页] 使用缓存的 solution 数据')
      solutionResult = cachedSolution
    } else {
      console.log('[结算页] 缓存未命中，请求 solution 数据')
      solutionResult = await getSessionSolution(loadSessionId)
      // 缓存新获取的数据
      uni.setStorageSync('practice-solution', solutionResult)
    }

    // 🔥 并行请求 report 数据（report 数据较小，每次请求）
    const reportData = await getSessionReport(loadSessionId)

    // 保存 sessionId
    sessionId.value = loadSessionId

    // 填充报告数据
    practiceName.value = reportData.practice_name || '练习'
    totalCount.value = reportData.total_count
    correctCount.value = reportData.correct_count
    wrongCount.value = reportData.wrong_count
    unansweredCount.value = reportData.unanswered_count
    duration.value = formatDuration(reportData.total_time)

    // 转换 answer_items 为驼峰命名
    answerItems.value = reportData.answer_items.map(item => ({
      index: item.index,
      questionId: item.question_id,
      status: item.status
    }))

    bankId.value = reportData.bank_id || null
    practiceMode.value = reportData.session_type
    wrongQuestions.value = reportData.wrong_question_ids

    // 🔥 保存解析数据
    solutionData.value = solutionResult

    // 🔥 缓存解析数据到 storage，供 detail 页面使用
    uni.setStorageSync('practice-solution', solutionResult)

    uni.hideLoading()
  } catch (error: any) {
    uni.hideLoading()
    console.error('❌ 加载会话报告失败:', error)
    uni.showToast({
      title: '加载失败',
      icon: 'none',
      duration: 2000
    })
    setTimeout(() => uni.navigateBack(), 2000)
  }
}</script>

<style scoped lang="scss">
.result-page {
  width: 100%;
  height: 100vh;
  background: var(--color-bg-page);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: hidden;  /* 🔥 防止页面整体滚动 */
}

.result-content {
  flex: 1;
  width: 100%;
  height: 0;  /* 🔥 配合 flex: 1 确保正确的高度计算 */
  padding: 40rpx 32rpx;
  padding-bottom: calc(144rpx + env(safe-area-inset-bottom));  /* 🔥 为底部按钮留出足够空间 */
  box-sizing: border-box;
}

/* ============ 头部统计 ============ */
.result-header {
  background: var(--color-bg-card);
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
  margin-bottom: 32rpx;
}

.result-score {
  display: flex;
  justify-content: center;
  margin-bottom: 40rpx;
}

/* 圆形进度条内容 */
.circle-progress__inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.circle-progress__value {
  font-size: 44rpx;
  font-weight: 700;
  color: #3b82f6;
  line-height: 1;
  margin-bottom: 4rpx;
}

.circle-progress__label {
  font-size: 22rpx;
  color: var(--color-text-secondary);
}

.result-meta {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
}

.result-meta__item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  padding: 20rpx 16rpx;
  background: var(--color-bg-elevated);
  border-radius: 16rpx;
}

.result-meta__item:first-child {
  margin-right: 16rpx;
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
  margin-bottom: 32rpx;
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
