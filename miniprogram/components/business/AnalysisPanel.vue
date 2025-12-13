<template>
  <view class="analysis-panel">
    <!-- 答题统计区域 -->
    <view class="stats-section">
      <view class="stats-header">
        <text class="stats-header__icon">📊</text>
        <text class="stats-header__title">答题统计</text>
      </view>

      <!-- 答案对比 -->
      <view class="answer-compare">
        <view class="answer-item" :class="{ 'answer-item--correct': isCorrect, 'answer-item--wrong': !isCorrect }">
          <view class="answer-item__label">
            <text class="answer-item__icon">{{ isCorrect ? '✓' : '✗' }}</text>
            <text>我的答案</text>
          </view>
          <text class="answer-item__value">{{ displayUserAnswer }}</text>
        </view>

        <view class="answer-item answer-item--standard">
          <view class="answer-item__label">
            <text class="answer-item__icon">★</text>
            <text>正确答案</text>
          </view>
          <text class="answer-item__value">{{ displayCorrectAnswer }}</text>
        </view>
      </view>

      <!-- 数据统计网格 -->
      <view class="stats-grid">
        <view class="stat-card">
          <text class="stat-card__icon">⏱</text>
          <view class="stat-card__content">
            <text class="stat-card__value">{{ answerTime }}s</text>
            <text class="stat-card__label">答题时间</text>
          </view>
        </view>

        <view class="stat-card">
          <text class="stat-card__icon">📝</text>
          <view class="stat-card__content">
            <text class="stat-card__value">{{ totalAttempts }}</text>
            <text class="stat-card__label">全站次数</text>
          </view>
        </view>

        <view class="stat-card">
          <text class="stat-card__icon">🎯</text>
          <view class="stat-card__content">
            <text class="stat-card__value">{{ correctRate }}%</text>
            <text class="stat-card__label">正确率</text>
          </view>
        </view>

        <!-- 易错选项 -->
        <view v-if="commonMistakes && commonMistakes.length > 0" class="stat-card stat-card--mistakes">
          <text class="stat-card__icon">⚠️</text>
          <view class="stat-card__content">
            <view class="stat-card__mistakes">
              <text
                v-for="(mistake, index) in commonMistakes"
                :key="index"
                class="stat-card__mistake-option"
              >
                {{ mistake.option }}
              </text>
            </view>
            <text class="stat-card__label">易错选项</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 解析部分 -->
    <view v-if="analysis" class="analysis-section">
      <view class="section-header">
        <text class="section-header__icon">💡</text>
        <text class="section-header__title">题目解析</text>
      </view>
      <view class="section-content">
        <up-markdown class="analysis-text" :content="analysis || ''"></up-markdown>
      </view>
    </view>

    <!-- 举一反三部分 -->
    <view v-if="similarQuestions && similarQuestions.length > 0" class="similar-section">
      <view class="section-header">
        <text class="section-header__icon">🔗</text>
        <text class="section-header__title">举一反三</text>
      </view>
      <view class="similar-list">
        <view
          v-for="(item, index) in similarQuestions"
          :key="index"
          class="similar-item"
          @tap="() => emit('goToQuestion', item.id)"
        >
          <view class="similar-item__header">
            <text class="similar-item__tag">{{ item.typeLabel }}</text>
            <text class="similar-item__similarity">相似度 {{ item.similarity }}%</text>
          </view>
          <up-markdown class="similar-item__stem" :content="item.stem || ''"></up-markdown>
        </view>
      </view>
    </view>

    <!-- 题目整理 -->
    <view class="organize-section">
      <view class="section-header">
        <text class="section-header__icon">📂</text>
        <text class="section-header__title">题目整理</text>
      </view>
      <view class="organize-actions">
        <view
          class="organize-btn"
          :class="{ 'organize-btn--active': isCollected }"
          @tap="() => emit('toggleCollect')"
        >
          <CollectIcon :is-active="isCollected" size="small" @click.stop />
          <text class="organize-btn__text">{{ isCollected ? '已收藏' : '收藏' }}</text>
        </view>

        <view
          class="organize-btn"
          :class="{ 'organize-btn--active': isMarkedWrong }"
          @tap="() => emit('toggleWrongBook')"
        >
          <text class="organize-btn__icon">📕</text>
          <text class="organize-btn__text">{{ isMarkedWrong ? '已加入错题本' : '加入错题本' }}</text>
        </view>

        <view class="organize-btn" @tap="() => emit('addToSet')">
          <text class="organize-btn__icon">📚</text>
          <text class="organize-btn__text">加入题集</text>
        </view>
      </view>
    </view>

    <!-- 笔记书写 -->
    <view class="notes-section">
      <view class="section-header">
        <text class="section-header__icon">✍️</text>
        <text class="section-header__title">我的笔记</text>
      </view>
      <view class="notes-content">
        <textarea
          class="notes-textarea"
          :value="noteText"
          placeholder="写下你的思考和总结..."
          placeholder-class="notes-placeholder"
          @input="handleNoteInput"
          @blur="handleNoteSave"
        />
        <view v-if="noteSavedTime" class="notes-footer">
          <text class="notes-footer__text">已保存 · {{ noteSavedTime }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { BaseQuestion } from './question-map'
import CollectIcon from '../common/CollectIcon.vue'

declare const uni: any

interface CommonMistake {
  option: string
  description: string
}

interface SimilarQuestion {
  id: string
  typeLabel: string
  stem: string
  similarity: number
}

interface AnalysisPanelProps {
  question: BaseQuestion
  userAnswer: string | string[]
  isCorrect: boolean
  answerTime?: number
  totalAttempts?: number
  correctRate?: number
  commonMistakes?: CommonMistake[]
  analysis?: string
  similarQuestions?: SimilarQuestion[]
  isCollected?: boolean
  isMarkedWrong?: boolean
  noteText?: string
}

const props = withDefaults(defineProps<AnalysisPanelProps>(), {
  answerTime: 0,
  totalAttempts: 0,
  correctRate: 0,
  commonMistakes: () => [],
  analysis: '',
  similarQuestions: () => [],
  isCollected: false,
  isMarkedWrong: false,
  noteText: ''
})

const emit = defineEmits<{
  (event: 'toggleCollect'): void
  (event: 'toggleWrongBook'): void
  (event: 'addToSet'): void
  (event: 'updateNote', note: string): void
  (event: 'goToQuestion', questionId: string): void
}>()

// ============ 答案格式化 ============
const displayUserAnswer = computed(() => {
  if (!props.userAnswer) return '未作答'
  if (Array.isArray(props.userAnswer)) {
    return props.userAnswer.join(', ')
  }
  try {
    const parsed = JSON.parse(props.userAnswer)
    if (Array.isArray(parsed)) {
      return parsed.join(', ')
    }
    return props.userAnswer
  } catch {
    return props.userAnswer
  }
})

const displayCorrectAnswer = computed(() => {
  const answer = props.question.answer
  if (!answer) return '暂无答案'
  if (Array.isArray(answer)) {
    return answer.join(', ')
  }
  return answer
})

// ============ 笔记处理 ============
const noteSavedTime = ref('')
const noteInputValue = ref(props.noteText)

function handleNoteInput(e: any) {
  noteInputValue.value = e.detail.value
}

function handleNoteSave() {
  if (noteInputValue.value !== props.noteText) {
    emit('updateNote', noteInputValue.value)
    const now = new Date()
    const hours = now.getHours().toString().padStart(2, '0')
    const minutes = now.getMinutes().toString().padStart(2, '0')
    noteSavedTime.value = `${hours}:${minutes}`
  }
}
</script>

<style scoped lang="scss">
.analysis-panel {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 24rpx;
  padding: 24rpx 0;
  box-sizing: border-box;
}

/* ============ 答题统计区域 ============ */
.stats-section {
  background: var(--color-bg-card);
  border-radius: 24rpx;
  padding: 32rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
}

.stats-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 24rpx;
}

.stats-header__icon {
  font-size: 36rpx;
}

.stats-header__title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--color-text-primary);
}

/* 答案对比 */
.answer-compare {
  display: flex;
  flex-direction: row;
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.answer-item {
  flex: 1;
  padding: 20rpx;
  border-radius: 16rpx;
  border: 2rpx solid transparent;
  background: var(--color-bg-elevated);
  min-width: 0;
}

.answer-item--correct {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.05) 100%);
  border-color: #10b981;
}

.answer-item--wrong {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.05) 100%);
  border-color: #ef4444;
}

.answer-item--standard {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.05) 100%);
  border-color: #3b82f6;
}

.answer-item__label {
  display: flex;
  align-items: center;
  gap: 6rpx;
  margin-bottom: 8rpx;
  font-size: 22rpx;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.answer-item__icon {
  font-size: 24rpx;
}

.answer-item__value {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--color-text-primary);
  word-break: break-all;
}

/* 统计网格 */
.stats-grid {
  display: flex;
  flex-wrap: nowrap;
  gap: 8rpx;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
  padding: 16rpx 8rpx;
  background: var(--color-bg-elevated);
  border-radius: 12rpx;
  flex: 1;
  min-width: 0;
}

.stat-card__icon {
  font-size: 32rpx;
}

.stat-card__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rpx;
}

.stat-card__value {
  font-size: 24rpx;
  font-weight: 700;
  color: #3b82f6;
}

.stat-card__label {
  font-size: 20rpx;
  color: var(--color-text-tertiary);
  white-space: nowrap;
}

/* 易错选项卡片 */
.stat-card--mistakes {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%);
}

.stat-card--mistakes .stat-card__icon {
  color: #f59e0b;
}

.stat-card__mistakes {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-wrap: wrap;
  justify-content: center;
}

.stat-card__mistake-option {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36rpx;
  height: 36rpx;
  background: rgba(251, 191, 36, 0.15);
  border: 2rpx solid #f59e0b;
  border-radius: 8rpx;
  font-size: 24rpx;
  font-weight: 700;
  color: #f59e0b;
}

/* ============ 通用区块样式 ============ */
.analysis-section,
.similar-section,
.organize-section,
.notes-section {
  background: var(--color-bg-card);
  border-radius: 24rpx;
  padding: 32rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.section-header__icon {
  font-size: 36rpx;
}

.section-header__title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--color-text-primary);
}

.section-content {
  padding: 24rpx;
  background: var(--color-bg-elevated);
  border-radius: 16rpx;
}

/* ============ 解析部分 ============ */
.analysis-text {
  font-size: 28rpx;
  color: var(--color-text-primary);
  line-height: 1.8;
}

/* ============ 举一反三 ============ */
.similar-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.similar-item {
  padding: 24rpx;
  background: var(--color-bg-elevated);
  border-radius: 16rpx;
  border: 2rpx solid transparent;
  transition: all 0.2s ease;
}

.similar-item:active {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.05);
}

.similar-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.similar-item__tag {
  padding: 6rpx 16rpx;
  background: rgba(59, 130, 246, 0.12);
  color: #3b82f6;
  font-size: 22rpx;
  font-weight: 600;
  border-radius: 12rpx;
}

.similar-item__similarity {
  font-size: 22rpx;
  color: #10b981;
  font-weight: 600;
}

.similar-item__stem {
  font-size: 26rpx;
  color: var(--color-text-primary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

/* ============ 题目整理 ============ */
.organize-actions {
  display: flex;
  gap: 12rpx;
}

.organize-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  padding: 24rpx 16rpx;
  background: var(--color-bg-elevated);
  border: 2rpx solid rgba(148, 163, 184, 0.2);
  border-radius: 16rpx;
  transition: all 0.2s ease;
}

.organize-btn:active {
  transform: scale(0.97);
}

.organize-btn--active {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.12) 0%, rgba(245, 158, 11, 0.08) 100%);
  border-color: rgba(251, 191, 36, 0.4);
}

.organize-btn__icon {
  font-size: 32rpx;
}

.organize-btn__text {
  font-size: 24rpx;
  font-weight: 600;
  color: var(--color-text-primary);
}

/* ============ 笔记书写 ============ */
.notes-content {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.notes-textarea {
  width: 100%;
  min-height: 240rpx;
  padding: 24rpx;
  background: var(--color-bg-elevated);
  border: 2rpx solid rgba(148, 163, 184, 0.2);
  border-radius: 16rpx;
  font-size: 28rpx;
  color: var(--color-text-primary);
  line-height: 1.8;
  box-sizing: border-box;
}

.notes-placeholder {
  color: var(--color-text-tertiary);
}

.notes-footer {
  padding: 0 8rpx;
}

.notes-footer__text {
  font-size: 22rpx;
  color: var(--color-text-tertiary);
}

/* ============ 深色模式适配 ============ */
@media (prefers-color-scheme: dark) {
  .stats-section,
  .analysis-section,
  .similar-section,
  .organize-section,
  .notes-section {
    box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.2);
  }

  .notes-textarea {
    border-color: rgba(148, 163, 184, 0.15);
  }
}
</style>
