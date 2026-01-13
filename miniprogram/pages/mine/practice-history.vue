<template>
  <view class="practice-history-page">
    <!-- 内容区域 -->
    <scroll-view class="content" scroll-y enable-flex>
      <!-- 加载状态 -->
      <view v-if="loading" class="loading-wrapper">
        <text class="loading-icon">⏳</text>
        <text class="loading-text">加载中...</text>
      </view>

      <!-- 空状态 -->
      <view v-else-if="sessions.length === 0" class="empty-state">
        <text class="empty-icon">📚</text>
        <text class="empty-text">暂无练习历史</text>
        <text class="empty-hint">完成练习后，历史记录会显示在这里</text>
      </view>

      <!-- 历史记录列表 -->
      <view v-else class="history-list" @tap="closeSwipeActions">
        <up-swipe-action ref="swipeActionRef">
          <up-swipe-action-item
            v-for="session in sessions"
            :key="session.id"
            :options="swipeOptions"
            @click="handleSwipeClick($event, session)"
          >
            <view
              class="history-card"
              @tap.stop="() => handleCardClick(session)"
            >
              <!-- 第一行：名称 + 时间 -->
              <view class="card-row">
                <view class="row-left">
                  <text class="session-type-icon">{{ getTypeIcon(session.session_type) }}</text>
                  <text class="session-title">{{ getTitle(session) }}</text>
                  <up-tag
                    v-if="session.status === 'in_progress'"
                    text="未完成"
                    type="warning"
                    plain
                    size="mini"
                    class="status-tag"
                  />
                  <up-tag
                    v-else-if="session.status === 'abandoned'"
                    text="已放弃"
                    type="info"
                    plain
                    size="mini"
                    class="status-tag"
                  />
                </view>
                <text class="session-time">{{ formatTimeWithMinute(session.updated_time) }}</text>
              </view>

              <!-- 第二行：答题情况 + 用时 -->
              <view class="card-row card-row--secondary">
                <view class="row-left">
                  <text class="stat-text">
                    <text class="stat-correct">{{ session.correct_count }}</text>
                    <text class="stat-separator">/</text>
                    <text class="stat-total">{{ session.total_count }}</text>
                    <text class="stat-label">题</text>
                    <text v-if="session.status === 'completed'" class="stat-accuracy">
                      · {{ session.accuracy_rate }}%
                    </text>
                  </text>
                </view>
                <text v-if="session.total_time > 0" class="duration-text">
                  ⏱ {{ formatDuration(session.total_time) }}
                </text>
              </view>
            </view>
          </up-swipe-action-item>
        </up-swipe-action>

        <!-- 加载更多 -->
        <view v-if="hasMore" class="load-more" @tap="loadMore">
          <text v-if="loadingMore" class="loading-more-icon">⏳</text>
          <text v-if="loadingMore" class="loading-more-text">加载中...</text>
          <text v-else class="load-more-text">加载更多</text>
        </view>

        <!-- 没有更多 -->
        <view v-else-if="sessions.length > 0" class="no-more">
          <text class="no-more-text">没有更多了</text>
        </view>
      </view>
    </scroll-view>

    <!-- 删除确认对话框 -->
    <up-modal
      :show="showDeleteConfirm"
      title="确认删除"
      content="删除后将无法恢复，确定要删除这条练习记录吗？"
      show-cancel-button
      confirm-color="#f56c6c"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import * as practiceApi from '../../api/business/practice'
import type { SessionListItem } from '../../api/business/practice'
import { formatDuration } from '../../utils/format'

declare const uni: any

const loading = ref(true)
const loadingMore = ref(false)
const sessions = ref<SessionListItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const hasMore = ref(true)
const isFirstLoad = ref(true)

// 删除确认对话框状态
const showDeleteConfirm = ref(false)
const sessionToDelete = ref<SessionListItem | null>(null)

// 🔥 页面显示时刷新数据（包括首次加载和从答题页返回）
onShow(() => {
  if (isFirstLoad.value) {
    // 首次加载
    isFirstLoad.value = false
    loadSessions()
  } else {
    // 从其他页面返回，静默刷新数据
    console.log('[练习历史] 页面返回，刷新数据')
    refreshSessions()
  }
})

// 滑动组件 ref
const swipeActionRef = ref<any>(null)

/**
 * 关闭所有滑动菜单
 */
function closeSwipeActions() {
  swipeActionRef.value?.closeAll?.()
}

// 滑动删除配置
const swipeOptions = [
  {
    text: '删除',
    style: {
      backgroundColor: '#f56c6c'
    }
  }
]

/**
 * 加载练习历史（带 loading 状态）
 */
async function loadSessions() {
  try {
    loading.value = true
    console.log('[练习历史] 开始加载, page:', page.value, 'size:', pageSize.value)

    const result = await practiceApi.getSessionList({
      page: page.value,
      size: pageSize.value
    })

    sessions.value = result.items
    hasMore.value = page.value < result.total_pages

    console.log('[练习历史] 加载成功, sessions 数量:', sessions.value.length)
  } catch (error: any) {
    console.error('[练习历史] 加载失败:', error)
    uni.showToast({
      title: '加载失败',
      icon: 'none'
    })
  } finally {
    loading.value = false
  }
}

/**
 * 静默刷新练习历史（不显示 loading，返回页面时使用）
 */
async function refreshSessions() {
  try {
    page.value = 1
    const result = await practiceApi.getSessionList({
      page: 1,
      size: pageSize.value
    })

    sessions.value = result.items
    hasMore.value = 1 < result.total_pages

    console.log('[练习历史] 静默刷新成功, sessions 数量:', sessions.value.length)
  } catch (error: any) {
    console.error('[练习历史] 静默刷新失败:', error)
    // 静默刷新失败不提示用户
  }
}

/**
 * 加载更多
 */
async function loadMore() {
  if (loadingMore.value || !hasMore.value) return

  try {
    loadingMore.value = true
    page.value++

    const result = await practiceApi.getSessionList({
      page: page.value,
      size: pageSize.value
    })

    sessions.value.push(...result.items)
    hasMore.value = page.value < result.total_pages

    console.log('[练习历史] 加载更多成功:', result)
  } catch (error) {
    console.error('[练习历史] 加载更多失败:', error)
    page.value--
    uni.showToast({
      title: '加载失败',
      icon: 'none'
    })
  } finally {
    loadingMore.value = false
  }
}

/**
 * 获取练习类型图标
 */
function getTypeIcon(type: string): string {
  const iconMap: Record<string, string> = {
    chapter: '📖',
    bank: '📚',
    random: '🎲',
    exam: '📝',
    wrong: '❌',
    favorite: '⭐'
  }
  return iconMap[type] || '📚'
}

/**
 * 获取标题
 */
function getTitle(session: SessionListItem): string {
  // 优先显示练习名称
  if (session.practice_name) {
    return session.practice_name
  }

  // 如果没有练习名称，使用类型名称
  const typeMap: Record<string, string> = {
    chapter: '章节练习',
    bank: '题库练习',
    random: '随机练习',
    exam: '模拟考试',
    wrong: '错题练习',
    favorite: '收藏练习'
  }
  return typeMap[session.session_type] || '练习'
}

/**
 * 格式化时间（精确到分钟）
 */
function formatTimeWithMinute(timeStr: string): string {
  try {
    // iOS 兼容性：将 "2025-12-11 19:34:10" 转换为 "2025-12-11T19:34:10"
    const isoTimeStr = timeStr.replace(' ', 'T')
    const date = new Date(isoTimeStr)

    // 检查日期是否有效
    if (isNaN(date.getTime())) {
      return timeStr
    }

    const now = new Date()
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    const timepart = `${hours}:${minutes}`

    // 今天
    if (date.toDateString() === now.toDateString()) {
      return `今天 ${timepart}`
    }

    // 昨天
    const yesterday = new Date(now)
    yesterday.setDate(yesterday.getDate() - 1)
    if (date.toDateString() === yesterday.toDateString()) {
      return `昨天 ${timepart}`
    }

    // 本年
    if (date.getFullYear() === now.getFullYear()) {
      return `${date.getMonth() + 1}-${date.getDate()} ${timepart}`
    }

    // 其他年份
    return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`
  } catch (error) {
    console.error('[时间格式化] 失败:', error, timeStr)
    return timeStr
  }
}

/**
 * 点击卡片 - 根据状态跳转
 */
function handleCardClick(session: SessionListItem) {
  // 先关闭滑动菜单
  closeSwipeActions()

  console.log('[练习历史] 点击卡片:', session)

  // 🔥 优化：缓存基本信息，减少后续 API 请求
  uni.setStorageSync('history-session-cache', {
    sessionId: session.id,
    bankId: session.bank_id,
    practiceName: session.practice_name,
    timestamp: Date.now()
  })

  // 根据状态跳转不同页面
  if (session.status === 'in_progress') {
    // 未完成 → 继续答题页面
    uni.navigateTo({
      url: `/pages/practice/detail?sessionId=${session.id}&resume=true`
    })
  } else {
    // 已完成/已放弃 → 结算页面
    uni.navigateTo({
      url: `/pages/practice/ResultSummary?sessionId=${session.id}`
    })
  }
}

/**
 * 滑动按钮点击事件
 *
 * :param indexOrEvent: 按钮索引对象 {index: 0, name: ""}
 * :param session: 会话数据
 */
function handleSwipeClick(indexOrEvent: any, session: SessionListItem) {
  // indexOrEvent 是一个对象 {index: 0, name: ""}
  const index = typeof indexOrEvent === 'object' && indexOrEvent.index !== undefined
    ? indexOrEvent.index
    : indexOrEvent

  // index 0 是删除按钮
  if (index === 0) {
    // 保存要删除的会话，显示确认对话框
    sessionToDelete.value = session
    showDeleteConfirm.value = true
  }
}

/**
 * 确认删除
 */
async function confirmDelete() {
  showDeleteConfirm.value = false
  if (sessionToDelete.value) {
    await deleteSession(sessionToDelete.value)
    sessionToDelete.value = null
  }
}

/**
 * 取消删除
 */
function cancelDelete() {
  showDeleteConfirm.value = false
  sessionToDelete.value = null
  closeSwipeActions()
}

/**
 * 删除会话
 */
async function deleteSession(session: SessionListItem) {
  try {
    uni.showLoading({ title: '删除中...', mask: true })

    await practiceApi.deleteSession(session.id)

    // 从列表中移除
    sessions.value = sessions.value.filter(s => s.id !== session.id)

    // 关闭滑动菜单
    closeSwipeActions()

    uni.hideLoading()
    uni.showToast({
      title: '删除成功',
      icon: 'success'
    })
  } catch (error: any) {
    uni.hideLoading()
    console.error('[练习历史] 删除失败:', error)
    uni.showToast({
      title: error.message || '删除失败',
      icon: 'none'
    })
  }
}
</script>

<style scoped lang="scss">
.practice-history-page {
  width: 100%;
  min-height: 100vh;
  background: var(--color-bg);
  display: flex;
  flex-direction: column;
}

.content {
  flex: 1;
  width: 100%;
  overflow-y: auto;
}

/* ============ 加载状态 ============ */
.loading-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120rpx 0;
  gap: 24rpx;
}

.loading-icon {
  font-size: 72rpx;
  animation: rotate 1.5s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
  font-size: 26rpx;
  color: var(--color-text-secondary);
}

/* ============ 空状态 ============ */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 160rpx 48rpx;
  gap: 16rpx;
}

.empty-icon {
  font-size: 120rpx;
  opacity: 0.5;
}

.empty-text {
  font-size: 32rpx;
  font-weight: 600;
  color: var(--color-text-primary);
}

.empty-hint {
  font-size: 26rpx;
  color: var(--color-text-tertiary);
}

/* ============ 历史记录列表 ============ */
.history-list {
  padding: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

/* ============ 历史卡片 ============ */
.history-card {
  background: var(--color-bg-card);
  border-radius: 16rpx;
  padding: 24rpx;
  border: 1rpx solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
  transition: all 0.2s ease;
}

.history-card:active {
  transform: scale(0.98);
  background: var(--color-bg-elevated);
  border-color: rgba(0, 0, 0, 0.1);
}

/* 卡片行 */
.card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-row--secondary {
  margin-top: 12rpx;
}

.row-left {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex: 1;
  min-width: 0;
}

/* 类型图标 */
.session-type-icon {
  font-size: 32rpx;
  flex-shrink: 0;
}

/* 标题 */
.session-title {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 状态标签 */
.status-tag {
  flex-shrink: 0;
  margin-left: 8rpx;
}

/* 时间 */
.session-time {
  font-size: 24rpx;
  color: var(--color-text-tertiary);
  flex-shrink: 0;
  margin-left: 16rpx;
}

/* 统计文本 */
.stat-text {
  font-size: 26rpx;
  color: var(--color-text-secondary);
}

.stat-correct {
  color: #10b981;
  font-weight: 600;
}

.stat-separator {
  color: var(--color-text-tertiary);
  margin: 0 2rpx;
}

.stat-total {
  color: var(--color-text-secondary);
}

.stat-label {
  color: var(--color-text-tertiary);
  margin-left: 4rpx;
}

.stat-accuracy {
  color: #3b82f6;
  font-weight: 500;
}

/* 用时文本 */
.duration-text {
  font-size: 24rpx;
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}

/* ============ 加载更多 ============ */
.load-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48rpx 0;
  gap: 12rpx;
}

.loading-more-icon {
  font-size: 32rpx;
  animation: rotate 1.5s linear infinite;
}

.loading-more-text {
  font-size: 26rpx;
  color: var(--color-text-secondary);
}

.load-more-text {
  font-size: 26rpx;
  color: #3b82f6;
}

.no-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48rpx 0;
}

.no-more-text {
  font-size: 24rpx;
  color: var(--color-text-tertiary);
}

/* ============ 深色模式适配 ============ */
@media (prefers-color-scheme: dark) {
  .history-card {
    border-color: rgba(255, 255, 255, 0.08);
    box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.3);
  }

  .history-card:active {
    border-color: rgba(255, 255, 255, 0.12);
  }
}
</style>
