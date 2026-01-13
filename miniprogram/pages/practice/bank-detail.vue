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

      <!-- 基础信息 + 学习进度 -->
      <view class="section info-section">
        <text class="bank-title">{{ bank.name }}</text>

        <!-- 第一行：题目数量 + 已完成 + 练习人数 -->
        <view class="meta-row">
          <view class="meta-group">
            <view class="meta-item">
              <text class="meta-icon">📖</text>
              <text class="meta-text">{{ bank.q_count }}题</text>
            </view>
            <text class="meta-divider">|</text>
            <text class="meta-text-highlight">已完成 {{ progress }} 题</text>
          </view>
          <view class="meta-item">
            <text class="meta-icon">👥</text>
            <text class="meta-text">{{ practiceCount }}人在刷</text>
          </view>
        </view>

        <!-- 第二行：学习进度 + 百分比 + 正确率 -->
        <view class="progress-header">
          <view class="progress-title-group">
            <text class="progress-title">学习进度</text>
            <text class="progress-percent">{{ progressPercent }}%</text>
          </view>
          <text v-if="progress > 0" class="accuracy-text">正确率 {{ accuracy }}%</text>
        </view>

        <!-- 进度条 -->
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: progressPercent + '%' }"></view>
        </view>
      </view>

      <!-- 快捷功能 -->
      <view class="section action-section">
        <u-grid :col="5" :border="false">
          <u-grid-item @click="handleRandomPractice">
            <view class="action-content">
              <text class="action-icon">🎲</text>
              <text class="action-label">随机练习</text>
            </view>
          </u-grid-item>
          <u-grid-item @click="handleHistory">
            <view class="action-content">
              <text class="action-icon">📜</text>
              <text class="action-label">练习历史</text>
            </view>
          </u-grid-item>
          <u-grid-item @click="handleWrongQuestions">
            <view class="action-content">
              <text class="action-icon">❌</text>
              <text class="action-label">错题集</text>
            </view>
          </u-grid-item>
          <u-grid-item @click="handleFavorites">
            <view class="action-content">
              <text class="action-icon">⭐</text>
              <text class="action-label">我的收藏</text>
            </view>
          </u-grid-item>
          <u-grid-item @click="handleNotes">
            <view class="action-content">
              <text class="action-icon">📝</text>
              <text class="action-label">我的笔记</text>
            </view>
          </u-grid-item>
        </u-grid>
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
      <view class="section chapter-section">
        <view class="section-header">
          <text class="section-title">章节练习</text>
        </view>

        <view v-if="chapters.length === 0" class="chapter-empty">
          <text>暂无章节</text>
        </view>

        <!-- 多层级：显示 Tab + 子章节 -->
        <view v-else-if="isMultiLevel" class="chapter-multi-level">
          <!-- 🔥 添加 v-if 保护 + key 强制重渲染，避免 rect undefined 错误 -->
          <u-tabs
            v-if="topLevelTabs.length > 0"
            :key="'tabs-' + topLevelTabs.length"
            :list="topLevelTabs"
            :current="currentTabIndex"
            @change="handleTabChange"
            lineColor="#3b82f6"
            :activeStyle="{
              color: '#3b82f6',
              fontWeight: 'bold',
              fontSize: '30rpx'
            }"
            :inactiveStyle="{
              color: '#6b7280',
              fontSize: '28rpx'
            }"
          ></u-tabs>

          <view class="chapter-list">
            <view
              v-for="chapter in currentTabChildren"
              :key="chapter.id"
              class="chapter-item"
              @tap="handleChapterClick(chapter)"
            >
              <view class="chapter-main">
                <!-- 第一行：章节名称 + 所有统计信息 -->
                <view class="chapter-info-row">
                  <text class="chapter-name">{{ chapter.name }}</text>
                  <text v-if="chapter.is_trial" class="trial-badge">试用</text>
                  <text class="stats-divider">·</text>
                  <text class="chapter-count">{{ chapter.q_count }}题</text>
                  <text class="stats-divider">·</text>
                  <text class="chapter-progress">
                    已练{{ getChapterProgress(chapter.id) }}题({{ getChapterProgressPercent(chapter.id) }}%)
                  </text>
                  <template v-if="getChapterProgress(chapter.id) > 0">
                    <text class="stats-divider">·</text>
                    <text class="chapter-accuracy">
                      正确率{{ getChapterAccuracy(chapter.id) }}%
                    </text>
                  </template>
                </view>
                <!-- 第二行：进度条 -->
                <view class="chapter-progress-bar">
                  <view
                    class="chapter-progress-fill"
                    :style="{ width: getChapterProgressPercent(chapter.id) + '%' }"
                  ></view>
                </view>
              </view>
              <!-- 右侧图标：锁或箭头 -->
              <view class="chapter-arrow">
                <up-icon
                  v-if="!chapter.is_trial && !hasAccess"
                  name="lock-fill"
                  size="16"
                  color="#9ca3af"
                ></up-icon>
                <up-icon
                  v-else
                  name="arrow-right"
                  size="16"
                  color="#d1d5db"
                ></up-icon>
              </view>
            </view>
          </view>
        </view>

        <!-- 单层级：直接显示章节列表 -->
        <view v-else class="chapter-list">
          <view
            v-for="chapter in flattenChapters"
            :key="chapter.id"
            class="chapter-item"
            @tap="handleChapterClick(chapter)"
          >
            <view class="chapter-main">
              <!-- 第一行：章节名称 + 所有统计信息 -->
              <view class="chapter-info-row">
                <text class="chapter-name">{{ chapter.name }}</text>
                <text v-if="chapter.is_trial" class="trial-badge">试用</text>
                <text class="stats-divider">·</text>
                <text class="chapter-count">{{ chapter.q_count }}题</text>
                <text class="stats-divider">·</text>
                <text class="chapter-progress">
                  已练{{ getChapterProgress(chapter.id) }}题({{ getChapterProgressPercent(chapter.id) }}%)
                </text>
                <template v-if="getChapterProgress(chapter.id) > 0">
                  <text class="stats-divider">·</text>
                  <text class="chapter-accuracy">
                    正确率{{ getChapterAccuracy(chapter.id) }}%
                  </text>
                </template>
              </view>
              <!-- 第二行：进度条 -->
              <view class="chapter-progress-bar">
                <view
                  class="chapter-progress-fill"
                  :style="{ width: getChapterProgressPercent(chapter.id) + '%' }"
                ></view>
              </view>
            </view>
            <!-- 右侧图标：锁或箭头 -->
            <view class="chapter-arrow">
              <up-icon
                v-if="!chapter.is_trial && !hasAccess"
                name="lock-fill"
                size="16"
                color="#9ca3af"
              ></up-icon>
              <up-icon
                v-else
                name="arrow-right"
                size="16"
                color="#d1d5db"
              ></up-icon>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- 错误提示 -->
    <view v-else class="error-container">
      <text>加载失败</text>
    </view>

    <!-- 登录模态框 -->
    <LoginModal v-model:visible="showLoginModal" @success="handleLoginSuccess" />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import bankApi, { type BankDetail, type ChapterTreeNode } from '@/api/business/bank'
import * as practiceApi from '@/api/business/practice'
import type { BankStatistics } from '@/api/business/practice'
import { useUserStore } from '@/stores/user'
import { usePracticeStore } from '@/stores/practice'
import LoginModal from '@/components/auth/LoginModal.vue'

declare const uni: any

const userStore = useUserStore()
const practiceStore = usePracticeStore()

const loading = ref(true)
const bank = ref<BankDetail | null>(null)
const chapters = ref<ChapterTreeNode[]>([])
const bankStatistics = ref<BankStatistics | null>(null)
const currentTabIndex = ref(0)  // 当前选中的顶级章节 tab 索引
const showLoginModal = ref(false)  // 登录模态框显示状态

// 公告数据（TODO: 从API获取）
const announcements = ref([
  { content: '新增100道精选习题，快来挑战吧！' },
  { content: '学习打卡活动进行中，每日刷题赢奖励' },
])

/**
 * 判断是否为多层级结构
 */
const isMultiLevel = computed(() => {
  return chapters.value.some(chapter =>
    chapter.children && chapter.children.length > 0
  )
})

/**
 * 顶级章节列表（API 返回的就是树形结构，直接使用）
 */
const topLevelChapters = computed(() => {
  return chapters.value
})

/**
 * 转换为 u-tabs 组件需要的格式
 */
const topLevelTabs = computed(() => {
  return topLevelChapters.value.map(chapter => ({
    name: chapter.name,
    id: chapter.id
  }))
})

/**
 * 当前选中 tab 的子章节
 */
const currentTabChildren = computed(() => {
  const currentChapter = topLevelChapters.value[currentTabIndex.value]
  if (!currentChapter) {
    return []
  }
  return currentChapter.children || []
})

/**
 * 扁平化所有章节（用于单层级显示）
 */
const flattenChapters = computed(() => {
  const result: ChapterTreeNode[] = []
  const flatten = (chapterList: ChapterTreeNode[]) => {
    chapterList.forEach(chapter => {
      result.push(chapter)
      if (chapter.children && chapter.children.length > 0) {
        flatten(chapter.children)
      }
    })
  }
  flatten(chapters.value)
  return result
})

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
  const practicedCount = bankStatistics.value?.practiced_count || 0
  return Math.round((practicedCount / bank.value.q_count) * 100)
})

/**
 * 已完成题目数
 */
const progress = computed(() => {
  return bankStatistics.value?.practiced_count || 0
})

/**
 * 总体正确率
 */
const accuracy = computed(() => {
  return bankStatistics.value?.accuracy_rate || 0
})

/**
 * 公告文本（多条公告拼接）
 */
const announcementText = computed(() => {
  return announcements.value.map(item => item.content).join('   ')
})

/**
 * 获取章节进度
 *
 * :param chapterId: 章节 ID
 * :return: 已练习题数
 */
function getChapterProgress(chapterId: number): number {
  if (!bankStatistics.value) return 0
  const chapterStat = bankStatistics.value.chapter_statistics.find(
    stat => stat.chapter_id === chapterId
  )
  return chapterStat?.practiced_count || 0
}

/**
 * 获取章节正确率
 *
 * :param chapterId: 章节 ID
 * :return: 正确率（0-100）
 */
function getChapterAccuracy(chapterId: number): number {
  if (!bankStatistics.value) return 0
  const chapterStat = bankStatistics.value.chapter_statistics.find(
    stat => stat.chapter_id === chapterId
  )
  return chapterStat?.accuracy_rate || 0
}

/**
 * 获取章节进度百分比
 *
 * :param chapterId: 章节 ID
 * :return: 进度百分比（0-100）
 */
function getChapterProgressPercent(chapterId: number): number {
  const chapter = flattenChapters.value.find(ch => ch.id === chapterId)
  if (!chapter || chapter.q_count === 0) return 0

  const practiced = getChapterProgress(chapterId)
  return Math.round((practiced / chapter.q_count) * 100)
}

/**
 * 切换顶级章节 Tab
 *
 * :param item: uView Plus tabs 传递的对象 { index, name }
 */
function handleTabChange(item: { index: number; name: string }) {
  currentTabIndex.value = item.index
}

/**
 * 随机练习
 */
function handleRandomPractice() {
  if (!bank.value) return

  if (!hasAccess.value) {
    // 区分未登录和已登录无权限
    if (!userStore.isLoggedIn) {
      // 打开登录模态框
      showLoginModal.value = true
    } else {
      uni.showToast({ title: '需要购买后才能练习', icon: 'none', duration: 2000 })
    }
    return
  }

  uni.navigateTo({
    url: `/pages/practice/detail?bankId=${bank.value.id}&catId=${bank.value.cat_id}&random=true`
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

  // 错题集需要登录
  if (!userStore.isLoggedIn) {
    showLoginModal.value = true
    return
  }

  uni.navigateTo({
    url: `/pages/practice/detail?bankId=${bank.value.id}&viewMode=wrong`
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
 * 检查是否有进行中的会话，有则继续，没有则开始新练习
 */
async function handleChapterClick(chapter: ChapterTreeNode) {
  if (!bank.value) return

  // 检查权限（试用章节除外）
  if (!chapter.is_trial && !hasAccess.value) {
    // 区分未登录和已登录无权限两种情况
    if (!userStore.isLoggedIn) {
      // 未登录：打开登录模态框
      showLoginModal.value = true
    } else {
      // 已登录但无权限：TODO
      uni.showToast({ title: '需要购买后才能练习', icon: 'none', duration: 2000 })
    }
    return
  }

  const bankId = bank.value.id
  const chapterId = chapter.id
  const catId = bank.value.cat_id

  try {
    // 检查是否有进行中的会话
    const latestSession = await practiceApi.getLatestSession({
      bank_id: bankId,
      chapter_id: chapterId
    })

    if (latestSession && latestSession.status === 'in_progress') {
      // 有进行中的会话，继续答题
      uni.navigateTo({
        url: `/pages/practice/detail?sessionId=${latestSession.id}&resume=true&catId=${catId}`
      })
    } else {
      // 没有进行中的会话，开始新练习
      uni.navigateTo({
        url: `/pages/practice/detail?bankId=${bankId}&chapterId=${chapterId}&catId=${catId}`
      })
    }
  } catch {
    // 获取会话失败（可能是没有会话），直接开始新练习
    uni.navigateTo({
      url: `/pages/practice/detail?bankId=${bankId}&chapterId=${chapterId}&catId=${catId}`
    })
  }
}

/**
 * 登录成功回调
 */
async function handleLoginSuccess() {
  console.log('[题库详情] 登录成功，刷新用户信息和统计数据')

  // 刷新用户信息
  await userStore.fetchUserInfo(true)

  // 刷新题库统计数据
  if (bank.value) {
    await loadBankStatistics(bank.value.id)
  }

  uni.showToast({
    title: '登录成功',
    icon: 'success',
    duration: 1500
  })
}

/**
 * 加载题库详情（含章节树）
 */
async function loadBankDetail(bankId: number) {
  try {
    loading.value = true
    const data = await bankApi.getBankDetail(bankId)
    bank.value = data
    // 章节树直接从题库详情中获取
    chapters.value = data.chapters || []
  } catch (error) {
    console.error('[题库详情] 加载失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

/**
 * 加载题库统计数据（从 Store 读取，避免重复请求）
 */
async function loadBankStatistics(bankId: number) {
  try {
    // 尝试加载用户统计（未登录时会静默失败）
    await practiceStore.loadUserStatistics()

    // 从 Store 获取指定题库的统计（未登录时返回空对象）
    bankStatistics.value = practiceStore.getBankStatistics(bankId)
  } catch (error) {
    console.error('[题库统计] 加载失败:', error)
    // 统计数据加载失败时，设置为空对象
    bankStatistics.value = {
      bank_id: bankId,
      total_questions: 0,
      practiced_count: 0,
      correct_count: 0,
      accuracy_rate: 0,
      total_time: 0,
      chapter_statistics: []
    }
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

  // 并行加载题库（含章节）和统计数据
  Promise.all([
    loadBankDetail(bankId),
    loadBankStatistics(bankId)
  ])
})
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';
@import '@/styles/mixins.scss';

.bank-detail-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 100%);
}

.detail-content {
  height: 100vh;
  padding-bottom: calc(32rpx + env(safe-area-inset-bottom));
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

/* ============ 统一的 Section 样式 ============ */
.section {
  margin: 0 32rpx 24rpx;
  background: #ffffff;
  border-radius: $radius-lg;
  box-shadow: 0 2rpx 16rpx rgba(0, 0, 0, 0.06);
}

/* 章节卡片需要 overflow hidden，其他不需要 */
.chapter-section {
  overflow: hidden;
}

/* ============ 基础信息 + 学习进度 ============ */
.info-section {
  padding: 32rpx;
}

.bank-title {
  @include text($font-size-2xl, $font-weight-bold, $color-text-primary);
  display: block;
  margin-bottom: 20rpx;
  line-height: $line-height-tight;
}

.meta-row {
  @include flex-between;
  margin-bottom: 24rpx;
}

.meta-group {
  display: flex;
  align-items: center;
  gap: 12rpx;
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
  @include text($font-size-base, $font-weight-normal, $color-text-secondary);
}

.meta-divider {
  @include text($font-size-base, $font-weight-normal, $color-text-muted);
  margin: 0 4rpx;
}

.meta-text-highlight {
  @include text($font-size-base, $font-weight-semibold, $color-primary);
}

.progress-header {
  @include flex-between;
  margin-bottom: 16rpx;
}

.progress-title-group {
  display: flex;
  align-items: baseline;
  gap: 12rpx;
}

.progress-title {
  @include text($font-size-base, $font-weight-semibold, $color-text-primary);
}

.progress-percent {
  @include text($font-size-xl, $font-weight-bold, $color-primary);
}

.accuracy-text {
  @include text($font-size-sm, $font-weight-normal, $color-success);
}

.progress-bar {
  height: 16rpx;
  background: $color-bg-page;
  border-radius: $radius-full;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, $color-primary-light 0%, $color-primary 100%);
  border-radius: $radius-full;
  transition: width $duration-base $ease-out;
}

/* ============ 快捷功能 ============ */
.action-section {
  padding: 16rpx 0;

  ::v-deep .u-grid {
    background: transparent;
  }

  ::v-deep .u-grid-item {
    padding: 0;
  }
}

.action-content {
  @include flex-column;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx 0;
  @include tap-feedback;
}

.action-icon {
  font-size: 48rpx;
}

.action-label {
  @include text($font-size-xs, $font-weight-normal, $color-text-secondary);
  text-align: center;
  white-space: nowrap;
}

/* ============ 公告轮播 ============ */
.announcement-section {
  padding: 0 32rpx;
  margin-bottom: 24rpx;
}

/* ============ 章节列表 ============ */
.chapter-section {
  padding: 32rpx;
}

.section-header {
  margin-bottom: 24rpx;
}

.section-title {
  @include text($font-size-lg, $font-weight-semibold, $color-text-primary);
}

/* ============ 多层级布局 ============ */
.chapter-multi-level {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.chapter-empty {
  padding: 80rpx 0;
  text-align: center;

  text {
    @include text($font-size-base, $font-weight-normal, $color-text-muted);
  }
}

.chapter-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.chapter-item {
  @include flex-between;
  @include tap-feedback;
  padding: 20rpx 24rpx;
  background: $color-bg-page;
  border-radius: $radius-base;
}

.chapter-main {
  @include flex-column;
  flex: 1;
  gap: 8rpx;
}

/* 章节信息行：名称 + 所有统计信息 */
.chapter-info-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-wrap: wrap;
}

.chapter-name {
  @include text($font-size-base, $font-weight-medium, $color-text-primary);
}

.trial-badge {
  padding: 4rpx 12rpx;
  background: rgba(34, 197, 94, 0.1);
  color: $color-success;
  font-size: 20rpx;
  font-weight: $font-weight-semibold;
  border-radius: 8rpx;
}

.chapter-count {
  @include text($font-size-sm, $font-weight-normal, $color-text-secondary);
}

.stats-divider {
  @include text($font-size-sm, $font-weight-normal, $color-text-muted);
}

.chapter-progress {
  @include text($font-size-sm, $font-weight-medium, $color-primary);
}

.chapter-accuracy {
  @include text($font-size-sm, $font-weight-normal, $color-success);
}

/* 章节进度条 */
.chapter-progress-bar {
  margin-top: 8rpx;
  height: 12rpx;
  background: #e5e7eb;  /* 更明显的灰色背景 */
  border-radius: $radius-full;
  overflow: hidden;
}

.chapter-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, $color-primary-light 0%, $color-primary 100%);
  border-radius: $radius-full;
  transition: width $duration-base $ease-out;
}

.chapter-arrow {
  @include flex-center;
  margin-left: 16rpx;
}
</style>
