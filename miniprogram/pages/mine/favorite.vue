<template>
  <view class="favorite-page">
    <!-- 顶部 Tab：收藏夹筛选 -->
    <wd-tabs
      v-model="currentFolderIndex"
      @change="handleFolderChange"
      line-color="#22c55e"
    >
      <wd-tab v-for="(tab, index) in folderTabs" :key="index" :title="tab.name" />
    </wd-tabs>

    <!-- 主要内容区域 -->
    <scroll-view class="content-scroll" scroll-y>
      <!-- 加载中状态 -->
      <view v-if="loading" class="loading-state">
        <text class="loading-text">加载中...</text>
      </view>

      <!-- 空状态 -->
      <view v-else-if="groupedBanks.length === 0" class="empty-state">
        <text class="empty-icon">📚</text>
        <text class="empty-text">还没有收藏题目</text>
        <text class="empty-hint">在刷题时点击收藏按钮即可收藏题目</text>
      </view>

      <!-- 题库列表 -->
      <view v-else class="bank-list">
        <wd-collapse>
          <wd-collapse-item
            v-for="bank in groupedBanks"
            :key="bank.bank_id"
            :name="bank.bank_id"
            class="bank-collapse-item"
          >
            <!-- 自定义题库头部 -->
            <template #title>
              <view class="bank-info">
                <text class="bank-icon">📚</text>
                <text class="bank-name">{{ bank.bank_name }}</text>
                <text class="bank-count">({{ bank.total_count }}题)</text>
              </view>
            </template>

            <!-- 章节列表内容 -->
            <view class="chapter-list">
              <view
                v-for="chapter in bank.chapters"
                :key="chapter.chapter_id"
                class="chapter-item"
                @tap="handleChapterClick(bank, chapter)"
              >
                <view class="chapter-info">
                  <text class="chapter-icon">📖</text>
                  <text class="chapter-name">{{ chapter.chapter_name }}</text>
                </view>
                <view class="chapter-right">
                  <text class="chapter-count">{{ chapter.question_count }}题</text>
                  <text class="chapter-arrow">→</text>
                </view>
              </view>
            </view>
          </wd-collapse-item>
        </wd-collapse>
      </view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import * as favoriteApi from '@/api/business/favorite'
import type { FavoriteItem } from '@/api/business/favorite'

declare const uni: any

/** 章节信息 */
interface ChapterInfo {
  chapter_id: number
  chapter_name: string
  question_count: number
  questions: FavoriteItem[]
}

/** 题库分组信息 */
interface BankGroup {
  bank_id: number
  bank_name: string
  total_count: number
  chapters: ChapterInfo[]
}

// ============ 数据状态 ============
const loading = ref(false)
const folders = ref<string[]>([])
const currentFolderIndex = ref(0)
const favoriteList = ref<FavoriteItem[]>([])

// ============ 计算属性 ============

/** 当前选中的收藏夹名称 */
const currentFolder = computed(() => {
  if (currentFolderIndex.value === 0) return null // 全部
  return folders.value[currentFolderIndex.value - 1]
})

/** Tab 数据 */
const folderTabs = computed(() => {
  const tabs = [{ name: `全部` }]
  folders.value.forEach(folderName => {
    tabs.push({ name: folderName })
  })
  return tabs
})

/** 按题库和章节分组的数据 */
const groupedBanks = computed<BankGroup[]>(() => {
  if (favoriteList.value.length === 0) return []

  // 按题库分组
  const bankMap = new Map<number, BankGroup>()

  favoriteList.value.forEach(item => {
    const bankId = item.bank_id || 0
    const bankName = item.bank_name || '未分类'
    const chapterId = item.chapter_id || 0
    const chapterName = item.chapter_name || '未分类'

    // 初始化题库分组
    if (!bankMap.has(bankId)) {
      bankMap.set(bankId, {
        bank_id: bankId,
        bank_name: bankName,
        total_count: 0,
        chapters: []
      })
    }

    const bankGroup = bankMap.get(bankId)!

    // 查找或创建章节
    let chapter = bankGroup.chapters.find(c => c.chapter_id === chapterId)
    if (!chapter) {
      chapter = {
        chapter_id: chapterId,
        chapter_name: chapterName,
        question_count: 0,
        questions: []
      }
      bankGroup.chapters.push(chapter)
    }

    // 添加题目到章节
    chapter.questions.push(item)
    chapter.question_count++
    bankGroup.total_count++
  })

  // 转换为数组并排序
  return Array.from(bankMap.values()).sort((a, b) => b.total_count - a.total_count)
})

// ============ 生命周期 ============

onMounted(async () => {
  await loadFolders()
  await loadFavorites()
})

// ============ 方法 ============

/**
 * 加载收藏夹列表
 */
async function loadFolders() {
  try {
    const folderList = await favoriteApi.getFolders()
    folders.value = folderList
  } catch (error) {
    console.error('[我的收藏] 加载收藏夹列表失败:', error)
    uni.showToast({
      title: '加载收藏夹失败',
      icon: 'none'
    })
  }
}

/**
 * 加载收藏列表
 */
async function loadFavorites() {
  try {
    loading.value = true

    const params: any = {
      page: 1,
      size: 200 // 后端限制最大为 200
    }

    if (currentFolder.value) {
      params.folder_name = currentFolder.value
    }

    const result = await favoriteApi.getFavoriteList(params)
    favoriteList.value = result.items

    console.log('[我的收藏] 加载成功，共', result.total, '题')
  } catch (error) {
    console.error('[我的收藏] 加载收藏列表失败:', error)
    uni.showToast({
      title: '加载收藏失败',
      icon: 'none'
    })
  } finally {
    loading.value = false
  }
}

/**
 * 切换收藏夹 Tab
 */
function handleFolderChange(detail: { value: number; index: number }) {
  currentFolderIndex.value = detail.index
  loadFavorites()
}

/**
 * 点击章节，进入刷题页面
 */
function handleChapterClick(bank: BankGroup, chapter: ChapterInfo) {
  console.log('[我的收藏] 进入章节:', bank.bank_name, chapter.chapter_name)

  // 将题目ID列表存储到 storage（供 detail.vue 使用）
  const questionIds = chapter.questions.map(q => q.question_id)
  uni.setStorageSync('favorite-question-ids', questionIds)

  // 同时存储题目基本信息（避免重新请求）
  uni.setStorageSync('favorite-questions-info', chapter.questions)

  // 跳转到刷题页面（查看收藏模式）
  uni.navigateTo({
    url: `/pages/practice/detail?viewMode=favorite&bankId=${bank.bank_id}&bankName=${encodeURIComponent(bank.bank_name)}`
  })
}
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';

.favorite-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8f9fa;
}

/* ==================== 内容区域 ==================== */
.content-scroll {
  flex: 1;
  overflow-y: auto;
}

/* ==================== 加载状态 ==================== */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 200rpx 0;
  gap: 24rpx;
}

.loading-text {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

/* ==================== 空状态 ==================== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 200rpx 48rpx;
  gap: 24rpx;
}

.empty-icon {
  font-size: 120rpx;
  opacity: 0.5;
}

.empty-text {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
  color: $color-text-primary;
}

.empty-hint {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  text-align: center;
}

/* ==================== 题库列表 ==================== */
.bank-list {
  padding: 24rpx 32rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
}

/* wot-design-uni Collapse 样式定制 */
.bank-collapse-item {
  margin-bottom: 24rpx;
  background: #ffffff;
  border-radius: 16rpx;
  overflow: hidden;
  box-shadow: 0 2rpx 16rpx rgba(0, 0, 0, 0.06);

  /* 覆盖 wot-design-uni 默认样式 */
  :deep(.wd-collapse-item) {
    border: none !important;
  }

  :deep(.wd-collapse-item__header) {
    padding: 32rpx 24rpx !important;
    background: #ffffff !important;
  }

  :deep(.wd-collapse-item__wrapper) {
    padding: 0 !important;
    border-top: 1rpx solid #f0f0f0;
  }
}

/* 题库信息 */
.bank-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12rpx;
  min-width: 0;
}

.bank-icon {
  font-size: 40rpx;
  flex-shrink: 0;
}

.bank-name {
  flex: 1;
  font-size: $font-size-md;
  font-weight: $font-weight-semibold;
  color: $color-text-primary;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bank-count {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  flex-shrink: 0;
}

/* 章节列表 */

.chapter-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 24rpx 24rpx 56rpx;
  border-bottom: 1rpx solid #f8f9fa;
  transition: background-color 0.2s ease;

  &:last-child {
    border-bottom: none;
  }

  &:active {
    background-color: #f8f9fa;
  }
}

.chapter-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12rpx;
  min-width: 0;
}

.chapter-icon {
  font-size: 32rpx;
  flex-shrink: 0;
}

.chapter-name {
  flex: 1;
  font-size: $font-size-base;
  color: $color-text-primary;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chapter-right {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-shrink: 0;
}

.chapter-count {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

.chapter-arrow {
  font-size: 32rpx;
  color: $color-text-muted;
  font-weight: $font-weight-light;
}
</style>
