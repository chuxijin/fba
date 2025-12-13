<template>
  <view class="bank-detail-page">
    <!-- 加载中 -->
    <view v-if="loading" class="loading-container">
      <text>加载中...</text>
    </view>

    <!-- 详情内容 -->
    <scroll-view v-else-if="bank" class="detail-content" scroll-y>
      <!-- 16:9 封面图 -->
      <view v-if="bank.cover_url" class="cover-section">
        <image class="cover-image" :src="bank.cover_url" mode="aspectFill" />
      </view>

      <!-- 基础信息（一行） -->
      <view class="info-header">
        <text class="bank-title">{{ bank.name }}</text>
        <view class="meta-row">
          <view class="meta-item">
            <text class="meta-icon">📖</text>
            <text class="meta-text">{{ bank.q_count }}题</text>
          </view>
          <view class="meta-item">
            <text class="meta-icon">👥</text>
            <text class="meta-text">{{ practiceCount }}人在刷</text>
          </view>
        </view>
      </view>

      <!-- 学习进度 -->
      <view class="progress-section">
        <view class="progress-header">
          <text class="progress-title">学习进度</text>
          <text class="progress-percent">{{ progressPercent }}%</text>
        </view>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: progressPercent + '%' }"></view>
        </view>
        <view class="progress-stats">
          <text class="stats-text">已完成 {{ progress }} 题</text>
          <text v-if="progress > 0" class="stats-text">正确率 {{ accuracy }}%</text>
        </view>
      </view>

      <!-- 功能按钮区（5个） -->
      <view class="action-grid">
        <view class="action-btn" @tap="handleRandomPractice">
          <text class="action-icon">🎲</text>
          <text class="action-text">随机练习</text>
        </view>
        <view class="action-btn" @tap="handleHistory">
          <text class="action-icon">📜</text>
          <text class="action-text">练习历史</text>
        </view>
        <view class="action-btn" @tap="handleWrongQuestions">
          <text class="action-icon">❌</text>
          <text class="action-text">错题集</text>
        </view>
        <view class="action-btn" @tap="handleFavorites">
          <text class="action-icon">⭐</text>
          <text class="action-text">我的收藏</text>
        </view>
        <view class="action-btn" @tap="handleNotes">
          <text class="action-icon">📝</text>
          <text class="action-text">我的笔记</text>
        </view>
      </view>

      <!-- 公告通知栏 -->
      <view v-if="announcements.length > 0" class="announcement-section">
        <u-notice-bar
          :text="announcementText"
          mode="link"
          direction="row"
          :speed="80"
          icon="volume"
          color="#92400e"
          bgColor="#fffbeb"
        ></u-notice-bar>
      </view>

      <!-- 章节列表 -->
      <view class="chapter-section">
        <view class="section-header">
          <text class="section-title">章节练习</text>
        </view>

        <view v-if="loadingChapters" class="chapter-loading">
          <text>加载章节中...</text>
        </view>

        <view v-else-if="chapters.length === 0" class="chapter-empty">
          <text>暂无章节</text>
        </view>

        <view v-else class="chapter-list">
          <view
            v-for="chapter in chapters"
            :key="chapter.id"
            class="chapter-item"
            @tap="handleChapterClick(chapter)"
          >
            <view class="chapter-main">
              <view class="chapter-title-row">
                <text class="chapter-name">{{ chapter.name }}</text>
                <text v-if="chapter.is_trial" class="trial-badge">试用</text>
              </view>
              <view class="chapter-stats">
                <text class="chapter-count">{{ chapter.q_count }}题</text>
                <text v-if="getChapterProgress(chapter.id) > 0" class="chapter-accuracy">
                  正确率 {{ getChapterAccuracy(chapter.id) }}%
                </text>
              </view>
            </view>
            <view class="chapter-arrow">
              <text>›</text>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- 错误提示 -->
    <view v-else class="error-container">
      <text>加载失败</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import bankApi, { type BankDetail } from '@/api/business/bank'
import chapterApi, { type ChapterDetail } from '@/api/business/chapter'
import { useUserStore } from '@/stores/user'

declare const uni: any

const userStore = useUserStore()

const loading = ref(true)
const loadingChapters = ref(false)
const bank = ref<BankDetail | null>(null)
const chapters = ref<ChapterDetail[]>([])
const progress = ref(0)  // TODO: 从用户学习记录API获取
const accuracy = ref(0)  // TODO: 从用户学习记录API获取

// 公告数据（TODO: 从API获取）
const announcements = ref([
  { content: '新增100道精选习题，快来挑战吧！' },
  { content: '学习打卡活动进行中，每日刷题赢奖励' },
])

const hasAccess = computed(() => {
  if (!bank.value) return false
  const access = userStore.checkBankAccess(bank.value.id, bank.value.cat_id, bank.value.scope)
  return access.hasAccess
})

const practiceCount = computed(() => {
  if (!bank.value) return '0'
  const count = bank.value.buy_count
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万`
  }
  return String(count)
})

const progressPercent = computed(() => {
  if (!bank.value || bank.value.q_count === 0) return 0
  return Math.round((progress.value / bank.value.q_count) * 100)
})

/**
 * 公告文本（多条公告拼接）
 */
const announcementText = computed(() => {
  return announcements.value.map(item => item.content).join('   ')
})

/**
 * 获取章节进度（TODO: 从API获取）
 */
function getChapterProgress(chapterId: number): number {
  return 0
}

/**
 * 获取章节正确率（TODO: 从API获取）
 */
function getChapterAccuracy(chapterId: number): number {
  return 0
}

/**
 * 随机练习
 */
function handleRandomPractice() {
  if (!bank.value) return

  if (!hasAccess.value) {
    uni.showToast({ title: '暂无权限', icon: 'none' })
    return
  }

  uni.navigateTo({
    url: `/pages/practice/detail?bankId=${bank.value.id}&mode=practice&random=true`
  })
}

/**
 * 练习历史
 */
function handleHistory() {
  uni.showToast({ title: '功能开发中', icon: 'none' })
}

/**
 * 错题集
 */
function handleWrongQuestions() {
  if (!bank.value) return

  uni.navigateTo({
    url: `/pages/practice/detail?bankId=${bank.value.id}&mode=practice&viewMode=wrong`
  })
}

/**
 * 我的收藏
 */
function handleFavorites() {
  uni.showToast({ title: '功能开发中', icon: 'none' })
}

/**
 * 我的笔记
 */
function handleNotes() {
  uni.showToast({ title: '功能开发中', icon: 'none' })
}

/**
 * 章节点击
 */
function handleChapterClick(chapter: ChapterDetail) {
  // 试用章节直接进入
  if (chapter.is_trial) {
    uni.navigateTo({
      url: `/pages/practice/detail?chapterId=${chapter.id}&mode=practice`
    })
    return
  }

  // 检查权限
  if (!hasAccess.value) {
    uni.showToast({ title: '暂无权限', icon: 'none' })
    return
  }

  uni.navigateTo({
    url: `/pages/practice/detail?chapterId=${chapter.id}&mode=practice`
  })
}

/**
 * 加载题库详情
 */
async function loadBankDetail(bankId: number) {
  try {
    loading.value = true
    const data = await bankApi.getBankDetail(bankId)
    bank.value = data

    // TODO: 加载用户学习进度
    // const userProgress = await userApi.getBankProgress(bankId)
    // progress.value = userProgress.completed_count
    // accuracy.value = userProgress.accuracy
  } catch (error) {
    console.error('[题库详情] 加载失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

/**
 * 加载章节列表
 */
async function loadChapters(bankId: number) {
  try {
    loadingChapters.value = true
    const data = await chapterApi.getChapterTree(bankId)
    chapters.value = data
  } catch (error) {
    console.error('[章节列表] 加载失败:', error)
  } finally {
    loadingChapters.value = false
  }
}

onMounted(() => {
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const options = currentPage.options || currentPage.$page?.options || {}
  const bankId = Number(options.bankId)

  if (!bankId) {
    uni.showToast({ title: '参数错误', icon: 'none' })
    setTimeout(() => {
      uni.navigateBack()
    }, 1500)
    return
  }

  // 并行加载题库和章节
  Promise.all([
    loadBankDetail(bankId),
    loadChapters(bankId)
  ])
})
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';

.bank-detail-page {
  min-height: 100vh;
  background: $color-bg-page;
}

.detail-content {
  height: 100vh;
}

.loading-container,
.error-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 80rpx 32rpx;

  text {
    font-size: $font-size-base;
    color: $color-text-muted;
  }
}

/* ============ 16:9 封面图 ============ */
.cover-section {
  width: 100%;
  padding-top: 56.25%; /* 16:9 */
  position: relative;
  overflow: hidden;
}

.cover-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

/* ============ 基础信息 ============ */
.info-header {
  padding: 32rpx;
  background: $color-bg-card;
}

.bank-title {
  display: block;
  font-size: $font-size-2xl;
  font-weight: $font-weight-bold;
  color: $color-text-primary;
  margin-bottom: 16rpx;
  line-height: $line-height-tight;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 32rpx;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.meta-icon {
  font-size: 28rpx;
}

.meta-text {
  font-size: $font-size-base;
  color: $color-text-secondary;
}

/* ============ 学习进度 ============ */
.progress-section {
  padding: 32rpx;
  background: $color-bg-card;
  margin-top: 16rpx;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.progress-title {
  font-size: $font-size-base;
  font-weight: $font-weight-semibold;
  color: $color-text-primary;
}

.progress-percent {
  font-size: $font-size-xl;
  font-weight: $font-weight-bold;
  color: $color-primary;
}

.progress-bar {
  height: 16rpx;
  background: $color-bg-page;
  border-radius: $radius-full;
  overflow: hidden;
  margin-bottom: 16rpx;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, $color-primary-light 0%, $color-primary 100%);
  border-radius: $radius-full;
  transition: width $duration-base $ease-out;
}

.progress-stats {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-text {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

/* ============ 功能按钮区 ============ */
.action-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16rpx;
  padding: 32rpx;
  background: $color-bg-card;
  margin-top: 16rpx;
}

.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  padding: 20rpx 0;
  border-radius: $radius-base;
  background: $color-bg-page;
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.95);
    background: rgba(59, 130, 246, 0.1);
  }
}

.action-icon {
  font-size: 48rpx;
}

.action-text {
  font-size: 20rpx;
  color: $color-text-secondary;
  white-space: nowrap;
}

/* ============ 公告轮播 ============ */
.announcement-section {
  padding: 0 32rpx;
  margin-top: 16rpx;
}

/* ============ 章节列表 ============ */
.chapter-section {
  padding: 32rpx;
  background: $color-bg-card;
  margin-top: 16rpx;
}

.section-header {
  margin-bottom: 24rpx;
}

.section-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
  color: $color-text-primary;
}

.chapter-loading,
.chapter-empty {
  padding: 80rpx 0;
  text-align: center;

  text {
    font-size: $font-size-base;
    color: $color-text-muted;
  }
}

.chapter-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.chapter-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx;
  background: $color-bg-page;
  border-radius: $radius-base;
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.98);
    background: rgba(59, 130, 246, 0.05);
  }
}

.chapter-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.chapter-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.chapter-name {
  font-size: $font-size-base;
  font-weight: $font-weight-medium;
  color: $color-text-primary;
}

.trial-badge {
  padding: 4rpx 12rpx;
  background: rgba(34, 197, 94, 0.1);
  color: $color-success;
  font-size: 20rpx;
  font-weight: $font-weight-semibold;
  border-radius: 8rpx;
}

.chapter-stats {
  display: flex;
  align-items: center;
  gap: 24rpx;
}

.chapter-count,
.chapter-accuracy {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

.chapter-arrow {
  display: flex;
  align-items: center;
  justify-content: center;

  text {
    font-size: 56rpx;
    color: $color-text-muted;
    font-weight: $font-weight-light;
    line-height: 1;
  }
}
</style>
