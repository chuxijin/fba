<template>
  <view class="analysis-panel">
    <!-- 答题统计区域 -->
    <view class="stats-section">
      <!-- 数据统计网格：做错时显示5格，做对/未做时显示4格 -->
      <view class="stats-grid" :class="{ 'stats-grid--wrong': !isCorrect }">
        <!-- 你的答案（仅做错时显示） -->
        <view v-if="!isCorrect" class="stat-card stat-card--user-answer">
          <view class="stat-card__content">
            <text class="stat-card__value stat-card__value--wrong">{{ displayUserAnswer }}</text>
            <text class="stat-card__label">你的答案</text>
          </view>
        </view>

        <!-- 正确答案 -->
        <view class="stat-card stat-card--correct-answer">
          <view class="stat-card__content">
            <text class="stat-card__value stat-card__value--correct">{{ displayCorrectAnswer }}</text>
            <text class="stat-card__label">正确答案</text>
          </view>
        </view>

        <!-- 全站正确率 -->
        <view class="stat-card">
          <view class="stat-card__content">
            <text class="stat-card__value">{{ correctRate }}%</text>
            <text class="stat-card__label">正确率</text>
          </view>
        </view>

        <!-- 用时 -->
        <view class="stat-card">
          <view class="stat-card__content">
            <text class="stat-card__value">{{ answerTime }}s</text>
            <text class="stat-card__label">用时</text>
          </view>
        </view>

        <!-- 易错项 -->
        <view class="stat-card stat-card--mistakes">
          <view class="stat-card__content">
            <view v-if="commonMistakes && commonMistakes.length > 0" class="stat-card__mistakes">
              <text
                v-for="(mistake, index) in commonMistakes"
                :key="index"
                class="stat-card__mistake-option"
              >
                {{ mistake.option }}
              </text>
            </view>
            <text v-else class="stat-card__value">-</text>
            <text class="stat-card__label">易错项</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 题目解析（折叠面板） -->
    <view class="analysis-section">
      <uni-collapse v-model="collapseValue">
        <uni-collapse-item :show-arrow="true" title-border="none" :border="false">
          <template v-slot:title>
            <view class="collapse-title">
              <text class="collapse-title__text">💡 题目解析</text>
              <view class="collapse-title__action" @tap.stop="handleCopyAnalysis">
                <text class="collapse-title__copy-icon">📋</text>
              </view>
            </view>
          </template>
          <view class="analysis-content">
            <mp-html v-if="analysis" class="analysis-text" :content="analysis || ''"></mp-html>
            <view v-else class="analysis-empty">
              <text class="analysis-empty__text">暂无解析</text>
            </view>
          </view>
        </uni-collapse-item>
      </uni-collapse>
    </view>

    <!-- 举一反三 -->
    <view v-if="similarQuestions && similarQuestions.length > 0" class="similar-section">
      <view class="section-title">🔗 举一反三</view>
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
          <mp-html class="similar-item__stem" :content="item.stem || ''"></mp-html>
        </view>
      </view>
    </view>

    <!-- 笔记区域 -->
    <view class="notes-section">
      <view class="section-title">✍️ 笔记</view>

      <!-- Tab 切换 -->
      <view class="notes-tabs">
        <view
          class="notes-tab"
          :class="{ 'notes-tab--active': activeTab === 'private' }"
          @tap="() => activeTab = 'private'"
        >
          <text class="notes-tab__text">我的笔记</text>
          <view v-if="activeTab === 'private'" class="notes-tab__indicator"></view>
        </view>
        <view
          class="notes-tab"
          :class="{ 'notes-tab--active': activeTab === 'public' }"
          @tap="() => activeTab = 'public'"
        >
          <text class="notes-tab__text">公开笔记</text>
          <view v-if="activeTab === 'public'" class="notes-tab__indicator"></view>
        </view>
      </view>

      <!-- 我的笔记 -->
      <view v-if="activeTab === 'private'" class="notes-content">
        <wd-textarea
          v-model="noteInputValue"
          placeholder="写下你的思考和总结..."
          :maxlength="1000"
          show-word-limit
          :auto-height="true"
          custom-style="background: var(--color-bg-elevated); padding: 24rpx; border-radius: 16rpx; min-height: 240rpx;"
        />

        <!-- 公开/私密切换 -->
        <view class="notes-switch-row">
          <view class="notes-switch-label">
            <text class="notes-switch-icon">{{ isPublicNote ? '🌐' : '🔒' }}</text>
            <text class="notes-switch-text">{{ isPublicNote ? '公开笔记' : '私密笔记' }}</text>
            <text class="notes-switch-desc">{{ isPublicNote ? '其他用户可见' : '仅自己可见' }}</text>
          </view>
          <wd-switch
            v-model="isPublicNote"
            size="24"
            active-color="#3b82f6"
            inactive-color="#94a3b8"
          />
        </view>

        <view class="notes-actions">
          <view class="notes-actions__btn notes-actions__btn--cancel" @tap="handleNoteCancel">
            取消
          </view>
          <view class="notes-actions__btn notes-actions__btn--save" @tap="handleNoteSave">
            保存
          </view>
        </view>
        <view v-if="noteSavedTime" class="notes-footer">
          <text class="notes-footer__text">已保存 · {{ noteSavedTime }}</text>
        </view>
      </view>

      <!-- 公开笔记 -->
      <view v-else class="notes-content">
        <view v-if="publicNotes && publicNotes.length > 0" class="public-notes-list">
          <view
            v-for="(note, index) in publicNotes"
            :key="note.id"
            class="public-note-item"
          >
            <view class="public-note-header">
              <view class="public-note-author">
                <!-- 头像 -->
                <image
                  v-if="note.avatar"
                  class="public-note-author__avatar"
                  :src="note.avatar"
                  mode="aspectFill"
                />
                <view v-else class="public-note-author__avatar public-note-author__avatar--default">
                  <text class="public-note-author__avatar-text">{{ note.author.charAt(0) }}</text>
                </view>
                <view class="public-note-author__info">
                  <text class="public-note-author__name">{{ note.author }}</text>
                  <text class="public-note-author__time">{{ note.time }}</text>
                </view>
              </view>
              <!-- 点赞按钮 -->
              <view
                class="public-note-likes"
                :class="{ 'public-note-likes--active': note.userVoted === 1 }"
                @tap.stop="() => handleVoteNote(note.id, note.userVoted)"
              >
                <text class="public-note-likes__icon">{{ note.userVoted === 1 ? '👍' : '👍🏻' }}</text>
                <text class="public-note-likes__count">{{ note.likes }}</text>
              </view>
            </view>
            <view class="public-note-content">
              <text>{{ note.content }}</text>
            </view>
          </view>
        </view>
        <view v-else class="notes-empty">
          <text class="notes-empty__icon">📝</text>
          <text class="notes-empty__text">暂无公开笔记</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { BaseQuestion } from './question-map'
import CollectIcon from '../common/CollectIcon.vue'

// 🔥 手动导入 uni-collapse 组件（如果 easycom 不生效）
// @ts-ignore
import uniCollapse from '@/uni_modules/uni-collapse/components/uni-collapse/uni-collapse.vue'
// @ts-ignore
import uniCollapseItem from '@/uni_modules/uni-collapse/components/uni-collapse-item/uni-collapse-item.vue'

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

interface PublicNote {
  id: number  // 笔记 ID（用于点赞）
  author: string
  avatar?: string  // 用户头像
  time: string
  content: string
  likes: number
  userVoted?: number  // 当前用户的投票状态：1=点赞，-1=点踩，undefined=未投票
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
  noteIsPublic?: boolean  // 🔥 笔记是否公开
  publicNotes?: PublicNote[]
  correctAnswer?: string | string[]  // 🔥 正确答案（练题模式从 solution API 获取）
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
  noteText: '',
  noteIsPublic: false,
  publicNotes: () => []
})

const emit = defineEmits<{
  (event: 'toggleCollect'): void
  (event: 'toggleWrongBook'): void
  (event: 'addToSet'): void
  (event: 'updateNote', data: { note: string; isPublic: boolean }): void
  (event: 'goToQuestion', questionId: string): void
  (event: 'loadPublicNotes'): void  // 🔥 加载公开笔记
  (event: 'voteNote', noteId: number, voteValue: 1 | -1 | null): void  // 🔥 笔记点赞
}>()

// ============ Tab 状态 ============
const activeTab = ref<'private' | 'public'>('private')

// 🔥 监听 tab 切换，当切换到公开笔记时触发加载
watch(activeTab, (newTab) => {
  if (newTab === 'public') {
    emit('loadPublicNotes')
  }
})

// ============ 折叠面板状态 ============
// v-model 绑定数组，['0'] 表示第一个面板默认展开
const collapseValue = ref<string[]>(['0'])

// ============ 笔记公开状态 ============
const isPublicNote = ref(props.noteIsPublic)

// 🔥 监听 props.noteIsPublic 变化，同步到本地状态
watch(() => props.noteIsPublic, (newValue) => {
  isPublicNote.value = newValue
})

// ============ 点赞逻辑 ============
function handleVoteNote(noteId: number, currentVoteStatus?: number) {
  if (currentVoteStatus === 1) {
    // 已点赞 → 取消点赞
    emit('voteNote', noteId, null)
  } else {
    // 未点赞或点踩 → 点赞
    emit('voteNote', noteId, 1)
  }
}

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
  // 🔥 优先使用传入的 correctAnswer（练题模式从 solution API 获取）
  const answer = props.correctAnswer || props.question.answer
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
    emit('updateNote', {
      note: noteInputValue.value,
      isPublic: isPublicNote.value
    })
    const now = new Date()
    const hours = now.getHours().toString().padStart(2, '0')
    const minutes = now.getMinutes().toString().padStart(2, '0')
    noteSavedTime.value = `${hours}:${minutes}`
  }
}

function handleNoteCancel() {
  noteInputValue.value = props.noteText
}

/**
 * 复制解析内容到剪贴板
 */
function handleCopyAnalysis() {
  if (!props.analysis) {
    uni.showToast({
      title: '暂无解析内容',
      icon: 'none',
      duration: 1500
    })
    return
  }

  // 去除 HTML 标签，提取纯文本
  const plainText = props.analysis
    .replace(/<[^>]*>/g, '')  // 去除 HTML 标签
    .replace(/&nbsp;/g, ' ')  // 替换空格实体
    .replace(/&lt;/g, '<')    // 替换小于号实体
    .replace(/&gt;/g, '>')    // 替换大于号实体
    .replace(/&amp;/g, '&')   // 替换 & 实体
    .trim()

  uni.setClipboardData({
    data: plainText,
    success: () => {
      uni.showToast({
        title: '解析已复制',
        icon: 'success',
        duration: 1500
      })
    },
    fail: () => {
      uni.showToast({
        title: '复制失败',
        icon: 'none',
        duration: 1500
      })
    }
  })
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

/* 统计网格：做对/未做显示4格，做错显示5格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
}

.stats-grid--wrong {
  grid-template-columns: repeat(5, 1fr);
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24rpx 12rpx;
  background: var(--color-bg-elevated);
  border-radius: 16rpx;
  min-width: 0;
}

.stat-card__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
  width: 100%;
}

.stat-card__value {
  font-size: 28rpx;
  font-weight: 700;
  color: #3b82f6;
  word-break: break-all;
  text-align: center;
}

.stat-card__value--wrong {
  color: #ef4444;
}

.stat-card__value--correct {
  color: #10b981;
}

.stat-card__label {
  font-size: 22rpx;
  color: var(--color-text-tertiary);
  white-space: nowrap;
}

/* 你的答案卡片 */
.stat-card--user-answer {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.05) 100%);
}

/* 正确答案卡片 */
.stat-card--correct-answer {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.05) 100%);
}

/* 易错选项卡片 */
.stat-card--mistakes {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%);
}

.stat-card__mistakes {
  display: flex;
  align-items: center;
  gap: 6rpx;
  flex-wrap: wrap;
  justify-content: center;
}

.stat-card__mistake-option {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36rpx;
  height: 36rpx;
  padding: 0 8rpx;
  background: rgba(251, 191, 36, 0.15);
  border: 2rpx solid #f59e0b;
  border-radius: 8rpx;
  font-size: 22rpx;
  font-weight: 700;
  color: #f59e0b;
}

/* ============ 折叠面板样式 ============ */
/* 保持组件默认样式，不做过多覆盖 */
:deep(.uni-collapse) {
  background: transparent;
  border: none;
}

:deep(.uni-collapse-item) {
  border: none;
  margin-bottom: 0;
}

:deep(.uni-collapse-item__wrap-content) {
  padding: 16rpx 0 0;
}

.collapse-content {
  width: 100%;
}

/* 自定义折叠面板标题 */
.collapse-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 48rpx; /* 为箭头留出空间 */
}

.collapse-title__text {
  font-size: 30rpx;
  font-weight: 600;
  color: var(--color-text-primary);
}

.collapse-title__action {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8rpx 16rpx;
  background: rgba(59, 130, 246, 0.08);
  border-radius: 12rpx;
  transition: all 0.2s ease;
}

.collapse-title__action:active {
  background: rgba(59, 130, 246, 0.15);
  transform: scale(0.95);
}

.collapse-title__copy-icon {
  font-size: 28rpx;
}

/* ============ 解析部分 ============ */
.analysis-text {
  font-size: 28rpx;
  color: var(--color-text-primary);
  line-height: 1.8;
}

/* mp-html 富文本样式 */
.analysis-text :deep(p) {
  margin: 0;
  padding: 0;
  line-height: 1.8;
}

.analysis-text :deep(p + p) {
  margin-top: 12rpx;
}

.analysis-text :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 16rpx 0;
  border-radius: 8rpx;
}

.analysis-text :deep(strong) {
  font-weight: 700;
  color: var(--color-text-primary);
}

.analysis-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60rpx 0;
}

.analysis-empty__text {
  font-size: 26rpx;
  color: var(--color-text-tertiary);
}

/* ============ 通用区块标题 ============ */
.section-title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 20rpx;
  padding: 0;
}

/* 解析区域 - 卡片样式 */
.analysis-section {
  background: var(--color-bg-card);
  border-radius: 24rpx;
  padding: 32rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
  margin-top: 24rpx;
}

.analysis-content {
  padding: 0;
}

.similar-section,
.notes-section {
  background: var(--color-bg-card);
  border-radius: 24rpx;
  padding: 32rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
  margin-top: 24rpx;
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
  transition: all 0.2s ease;
}

.similar-item:active {
  background: rgba(59, 130, 246, 0.05);
  transform: scale(0.98);
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

/* 举一反三题干富文本样式 */
.similar-item__stem :deep(p) {
  margin: 0;
  padding: 0;
  line-height: 1.6;
}

.similar-item__stem :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  border-radius: 6rpx;
}

/* ============ 笔记区域 ============ */
.notes-tabs {
  display: flex;
  gap: 4rpx;
  margin-bottom: 20rpx;
  background: var(--color-bg-elevated);
  padding: 6rpx;
  border-radius: 16rpx;
}

.notes-tab {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16rpx 0;
  cursor: pointer;
  transition: all 0.2s ease;
}

.notes-tab__text {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--color-text-secondary);
  transition: color 0.2s ease;
}

.notes-tab--active .notes-tab__text {
  color: var(--color-text-primary);
}

.notes-tab__indicator {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 40rpx;
  height: 6rpx;
  background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
  border-radius: 3rpx;
}

.notes-content {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  max-height: 600rpx;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch; /* iOS 平滑滚动 */
}

/* 公开/私密切换行 */
.notes-switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 24rpx;
  background: var(--color-bg-elevated);
  border-radius: 16rpx;
  margin-bottom: 16rpx;
}

.notes-switch-label {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex: 1;
}

.notes-switch-icon {
  font-size: 32rpx;
}

.notes-switch-text {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--color-text-primary);
}

.notes-switch-desc {
  font-size: 22rpx;
  color: var(--color-text-tertiary);
  margin-left: 8rpx;
}

.notes-actions {
  display: flex;
  gap: 16rpx;
  justify-content: flex-end;
}

.notes-actions__btn {
  padding: 16rpx 40rpx;
  border-radius: 12rpx;
  font-size: 28rpx;
  font-weight: 600;
  transition: all 0.2s ease;
  cursor: pointer;
}

.notes-actions__btn--cancel {
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  border: 2rpx solid rgba(148, 163, 184, 0.2);
}

.notes-actions__btn--cancel:active {
  background: rgba(148, 163, 184, 0.1);
}

.notes-actions__btn--save {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #ffffff;
  box-shadow: 0 4rpx 12rpx rgba(59, 130, 246, 0.3);
}

.notes-actions__btn--save:active {
  transform: scale(0.97);
  box-shadow: 0 2rpx 8rpx rgba(59, 130, 246, 0.3);
}

.notes-footer {
  padding: 0 8rpx;
}

.notes-footer__text {
  font-size: 22rpx;
  color: var(--color-text-tertiary);
}

/* 公开笔记列表 */
.public-notes-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.public-note-item {
  padding: 24rpx;
  background: var(--color-bg-elevated);
  border-radius: 16rpx;
  border: 2rpx solid rgba(148, 163, 184, 0.1);
}

.public-note-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}

.public-note-author {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.public-note-author__avatar {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  flex-shrink: 0;
}

.public-note-author__avatar--default {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.public-note-author__avatar-text {
  font-size: 28rpx;
  font-weight: 600;
  color: #ffffff;
}

.public-note-author__info {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.public-note-author__name {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--color-text-primary);
}

.public-note-author__time {
  font-size: 22rpx;
  color: var(--color-text-tertiary);
}

.public-note-likes {
  display: flex;
  align-items: center;
  gap: 6rpx;
  padding: 10rpx 16rpx;
  border-radius: 20rpx;
  background: var(--color-bg-elevated);
  cursor: pointer;
  transition: all 0.2s ease;
}

.public-note-likes:hover {
  background: var(--color-bg-secondary);
}

.public-note-likes--active {
  background: rgba(59, 130, 246, 0.1);
}

.public-note-likes--active .public-note-likes__icon {
  filter: grayscale(0);
}

.public-note-likes__icon {
  font-size: 28rpx;
  filter: grayscale(0.3);
  transition: filter 0.2s ease;
}

.public-note-likes__count {
  font-size: 24rpx;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.public-note-content {
  font-size: 28rpx;
  color: var(--color-text-primary);
  line-height: 1.8;
}

/* 空状态 */
.notes-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  padding: 80rpx 0;
}

.notes-empty__icon {
  font-size: 80rpx;
  opacity: 0.3;
}

.notes-empty__text {
  font-size: 26rpx;
  color: var(--color-text-tertiary);
}

/* ============ 深色模式适配 ============ */
@media (prefers-color-scheme: dark) {
  .stats-section {
    box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.2);
  }

  :deep(.wd-collapse-item) {
    border-color: rgba(148, 163, 184, 0.25);
  }

  :deep(.wd-collapse-item:hover) {
    border-color: rgba(59, 130, 246, 0.5);
  }

  .public-note-item {
    border-color: rgba(148, 163, 184, 0.08);
  }
}
</style>
