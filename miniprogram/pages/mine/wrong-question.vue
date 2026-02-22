<template>
  <view class="wrong-question-page">
    <!-- 顶部 Tab：分类筛选 -->
    <u-tabs
      :list="categoryTabs"
      :current="currentCategoryIndex"
      lineColor="#22c55e"
      :activeStyle="{ color: '#22c55e', fontWeight: 'bold' }"
      :inactiveStyle="{ color: '#94a3b8' }"
      @change="handleCategoryChange"
    />

    <!-- 筛选栏：是否显示已掌握 -->
    <view class="filter-bar">
      <view class="filter-item">
        <text class="filter-label">显示已掌握</text>
        <u-switch
          v-model="showMastered"
          size="24"
          activeColor="#22c55e"
          @change="handleFilterChange"
        />
      </view>
      <view class="stats-info">
        <text class="stats-text">未掌握: {{ unmasteredCount }}题</text>
        <text class="stats-divider">|</text>
        <text class="stats-text">已掌握: {{ masteredCount }}题</text>
      </view>
    </view>

    <!-- 主要内容区域 -->
    <scroll-view class="content-scroll" scroll-y>
      <!-- 加载中状态 -->
      <view v-if="loading" class="loading-state">
        <text class="loading-text">加载中...</text>
      </view>

      <!-- 空状态 -->
      <view v-else-if="groupedBanks.length === 0" class="empty-state">
        <text class="empty-icon">✅</text>
        <text class="empty-text">{{ emptyStateText }}</text>
        <text class="empty-hint">{{ emptyStateHint }}</text>
      </view>

      <!-- 题库列表 -->
      <view v-else class="bank-list">
        <up-collapse>
          <up-collapse-item
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
                  <view class="chapter-stats">
                    <text class="chapter-count">{{ chapter.question_count }}题</text>
                    <text class="chapter-avg" v-if="chapter.avg_wrong_count > 0">
                      平均错{{ chapter.avg_wrong_count.toFixed(1) }}次
                    </text>
                  </view>
                  <text class="chapter-arrow">→</text>
                </view>
              </view>
            </view>
          </up-collapse-item>
        </up-collapse>
      </view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import * as wrongQuestionApi from '@/api/business/wrong-question'
import * as categoryApi from '@/api/business/category'
import type { WrongQuestionItem } from '@/api/business/wrong-question'
import type { CategoryDetail } from '@/api/business/category'

declare const uni: any

/** 章节信息 */
interface ChapterInfo {
  chapter_id: number
  chapter_name: string
  question_count: number
  avg_wrong_count: number
  questions: WrongQuestionItem[]
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
const wrongQuestionList = ref<WrongQuestionItem[]>([])
const categories = ref<CategoryDetail[]>([])
const currentCategoryIndex = ref(0)
const showMastered = ref(false)

/** 当前选中的分类 ID */
const currentCategoryId = computed(() => {
  if (currentCategoryIndex.value === 0) return null // 全部
  const category = categories.value[currentCategoryIndex.value - 1]
  return category?.id || null
})

/** Tab 数据 */
const categoryTabs = computed(() => {
  const tabs = [{ name: '全部' }]
  // 🔥 将树形结构扁平化为 Tab 列表（包括父分类和子分类）
  const flattenCategories = (cats: CategoryDetail[]) => {
    cats.forEach(cat => {
      tabs.push({ name: cat.name })
      if (cat.children && cat.children.length > 0) {
        flattenCategories(cat.children)
      }
    })
  }
  flattenCategories(categories.value)
  return tabs
})

/** 扁平化分类列表（用于 ID 查找） */
const flatCategories = computed(() => {
  const result: CategoryDetail[] = []
  const flatten = (cats: CategoryDetail[]) => {
    cats.forEach(cat => {
      result.push(cat)
      if (cat.children && cat.children.length > 0) {
        flatten(cat.children)
      }
    })
  }
  flatten(categories.value)
  return result
})

// ============ 统计数据（基于当前分类过滤后的数据）============
const currentCategoryQuestions = computed(() => {
  if (currentCategoryId.value === null) {
    return wrongQuestionList.value // 全部
  }
  // 根据分类ID过滤错题
  return wrongQuestionList.value.filter(item => item.cat_id === currentCategoryId.value)
})

const unmasteredCount = computed(() => {
  return currentCategoryQuestions.value.filter(item => !item.is_mastered).length
})

const masteredCount = computed(() => {
  return currentCategoryQuestions.value.filter(item => item.is_mastered).length
})

// ============ 过滤后的错题列表 ============
const filteredWrongQuestions = computed(() => {
  // 1️⃣ 先按分类过滤
  let questions = currentCategoryQuestions.value

  // 2️⃣ 再按掌握状态过滤
  if (!showMastered.value) {
    questions = questions.filter(item => !item.is_mastered)
  }

  return questions
})

// ============ 空状态文案 ============
const emptyStateText = computed(() => {
  // 如果所有错题列表都为空
  if (wrongQuestionList.value.length === 0) {
    return '还没有错题记录'
  }

  // 如果当前分类下没有错题
  if (currentCategoryQuestions.value.length === 0) {
    const categoryName = currentCategoryIndex.value === 0
      ? '全部'
      : flatCategories.value[currentCategoryIndex.value - 1]?.name || '当前分类'
    return `${categoryName} 暂无错题`
  }

  // 如果过滤后为空（被"显示已掌握"开关过滤了）
  return '暂无未掌握的错题'
})

const emptyStateHint = computed(() => {
  if (wrongQuestionList.value.length === 0) {
    return '答错的题目会自动加入错题本'
  }

  if (currentCategoryQuestions.value.length === 0) {
    return '切换到"全部"查看所有错题'
  }

  return '打开"显示已掌握"开关即可查看'
})

// ============ 按题库和章节分组的数据 ============
const groupedBanks = computed<BankGroup[]>(() => {
  if (filteredWrongQuestions.value.length === 0) return []

  // 按题库分组
  const bankMap = new Map<number, BankGroup>()

  filteredWrongQuestions.value.forEach(item => {
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
        avg_wrong_count: 0,
        questions: []
      }
      bankGroup.chapters.push(chapter)
    }

    // 添加题目到章节
    chapter.questions.push(item)
    chapter.question_count++
    bankGroup.total_count++
  })

  // 计算每个章节的平均错误次数
  bankMap.forEach(bank => {
    bank.chapters.forEach(chapter => {
      const totalWrongCount = chapter.questions.reduce((sum, q) => sum + q.wrong_count, 0)
      chapter.avg_wrong_count = totalWrongCount / chapter.question_count
    })
  })

  // 转换为数组并排序（未掌握题目多的排在前面）
  return Array.from(bankMap.values()).sort((a, b) => b.total_count - a.total_count)
})

// ============ 生命周期 ============

onMounted(async () => {
  await Promise.all([
    loadWrongQuestions(),
    loadCategories()
  ])
})

// ============ 方法 ============

/**
 * 加载分类列表
 */
async function loadCategories() {
  try {
    const result = await categoryApi.getCategoryTree({
      status: true
    })
    categories.value = result
    console.log('[我的错题] 加载分类成功，共', categories.value.length, '个')
  } catch (error) {
    console.error('[我的错题] 加载分类失败:', error)
    // 分类加载失败不影响错题显示，仅在控制台提示
  }
}

/**
 * 加载错题列表
 */
async function loadWrongQuestions() {
  try {
    loading.value = true

    const params: any = {
      page: 1,
      size: 200 // 后端限制最大为 200
    }

    const result = await wrongQuestionApi.getWrongQuestionList(params)
    wrongQuestionList.value = result.items

    console.log('[我的错题] 加载成功，共', result.total, '题')
  } catch (error) {
    console.error('[我的错题] 加载错题列表失败:', error)
    uni.showToast({
      title: '加载错题失败',
      icon: 'none'
    })
  } finally {
    loading.value = false
  }
}

/**
 * 切换分类 Tab
 */
function handleCategoryChange(item: { index: number }) {
  currentCategoryIndex.value = item.index
  const categoryName = currentCategoryIndex.value === 0
    ? '全部'
    : flatCategories.value[currentCategoryIndex.value - 1]?.name || '未知分类'
  console.log('[我的错题] 切换到分类:', categoryName)
}

/**
 * 切换"显示已掌握"开关
 */
function handleFilterChange() {
  console.log('[我的错题] 显示已掌握:', showMastered.value)
}

/**
 * 点击章节，进入刷题页面
 */
function handleChapterClick(bank: BankGroup, chapter: ChapterInfo) {
  console.log('[我的错题] 进入章节:', bank.bank_name, chapter.chapter_name)

  // 将题目ID列表存储到 storage（供 detail.vue 使用）
  const questionIds = chapter.questions.map(q => q.question_id)
  uni.setStorageSync('wrong-question-ids', questionIds)

  // 同时存储题目基本信息（避免重新请求）
  uni.setStorageSync('wrong-questions-info', chapter.questions)

  // 跳转到刷题页面（错题模式）
  uni.navigateTo({
    url: `/pages/practice/detail?viewMode=wrong-practice&bankId=${bank.bank_id}&bankName=${encodeURIComponent(bank.bank_name)}`
  })
}
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';

.wrong-question-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8f9fa;
}

/* ==================== 筛选栏 ==================== */
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 32rpx;
  background: #ffffff;
  border-bottom: 1rpx solid #f0f0f0;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.filter-label {
  font-size: $font-size-base;
  color: $color-text-primary;
  font-weight: $font-weight-medium;
}

.stats-info {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.stats-text {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

.stats-divider {
  font-size: $font-size-sm;
  color: $color-text-muted;
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

/* uview-plus Collapse 样式定制 */
.bank-collapse-item {
  margin-bottom: 24rpx;
  background: #ffffff;
  border-radius: 16rpx;
  overflow: hidden;
  box-shadow: 0 2rpx 16rpx rgba(0, 0, 0, 0.06);

  /* 覆盖 uview-plus 默认样式 */
  :deep(.up-collapse-item) {
    border: none !important;
  }

  :deep(.up-collapse-item__title) {
    padding: 32rpx 24rpx !important;
    background: #ffffff !important;
  }

  :deep(.up-collapse-item__title__text) {
    flex: 1 !important;
  }

  :deep(.up-collapse-item__content) {
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

.chapter-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4rpx;
}

.chapter-count {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

.chapter-avg {
  font-size: 22rpx;
  color: #ef4444;
  font-weight: $font-weight-medium;
}

.chapter-arrow {
  font-size: 32rpx;
  color: $color-text-muted;
  font-weight: $font-weight-light;
}
</style>
