<template>
  <!-- 页面元数据：控制页面滚动 -->
  <page-meta :page-style="showTabManager || showSearch ? 'overflow: hidden' : ''"></page-meta>

  <view class="practice-page">
    <!-- 顶部标签页导航 - 使用 UView Plus Tabs -->
    <u-tabs
      :list="tabList"
      :current="activeTab"
      :scrollable="true"
      lineColor="#22c55e"
      :activeStyle="{ color: '#22c55e', fontWeight: 'bold' }"
      :inactiveStyle="{ color: '#94a3b8' }"
      @change="handleTabChange"
    >
      <template #right>
        <view class="tab-actions">
          <!-- 搜索按钮 -->
          <view class="tab-action-btn" @tap="handleOpenSearch">
            <u-icon name="search" :size="20" color="#22c55e"></u-icon>
          </view>

          <!-- 添加 Tab 按钮 -->
          <view class="tab-action-btn" @tap="handleTabClick(-1)">
            <u-icon name="plus" :size="20" color="#22c55e"></u-icon>
          </view>
        </view>
      </template>
    </u-tabs>

    <!-- 主要内容区域 - 支持左右滑动 -->
    <swiper
      class="content-swiper"
      :style="{ height: swiperHeight }"
      :current="activeTab"
      :duration="300"
      @change="handleSwiperChange"
    >
      <swiper-item v-for="(tab, index) in customTabs" :key="tab.id">
        <scroll-view
          class="main-content"
          scroll-y
          refresher-enabled
          :refresher-triggered="refreshing"
          @refresherrefresh="handleRefresh"
        >
          <!-- 学习进度列表 -->
          <view class="progress-section">
            <view v-if="loadingBanks" class="progress-loading">
              <text>正在加载题库...</text>
            </view>
            <view v-else-if="getTabBanks(index).length === 0" class="progress-empty">
              <text>该分类下暂无题库</text>
            </view>
            <!-- 使用虚拟列表（数据量大于5条时） -->
            <u-virtual-list
              v-else-if="getTabBanks(index).length > 5"
              :listData="getTabBanks(index)"
              :itemHeight="224"
              :gap="24"
            >
              <template #default="{ item }">
                <BankCard
                  :bank="item"
                  @click="handleBankClick"
                  @quick-start="handleQuickStart"
                />
              </template>
            </u-virtual-list>
            <!-- 普通列表（数据量少时） -->
            <BankCard
              v-else
              v-for="bank in getTabBanks(index)"
              :key="bank.id"
              :bank="bank"
              @click="handleBankClick"
              @quick-start="handleQuickStart"
            />
          </view>
        </scroll-view>
      </swiper-item>
    </swiper>

    <!-- Tab 管理弹窗 -->
    <TabManager
      :visible="showTabManager"
      :categories="flatCategories"
      :banks="allBanks"
      @close="handleCloseTabManager"
      @change="handleTabListChange"
    />

    <!-- 搜索弹窗 -->
    <SearchPanel
      :visible="showSearch"
      v-model="searchKeyword"
      :results="searchResults"
      @close="handleCloseSearch"
      @select="handleSelectSearchResult"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, computed, watch } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import categoryApi, { type CategoryDetail } from '@/api/business/category'
import bankApi, { type BankDetail } from '@/api/business/bank'
import type { BankProgressItem } from '@/api/business/practice'
import BankCard from '../../components/business/BankCard.vue'
import TabManager from '../../components/business/TabManager.vue'
import SearchPanel from '../../components/business/SearchPanel.vue'
import { useCustomTabs } from '../../composables/useCustomTabs'
import { useSystemInfo } from '../../composables/useSystemInfo'
import { useUserStore } from '../../stores/user'
import { usePracticeStore } from '../../stores/practice'

declare const uni: any

const userStore = useUserStore()
const practiceStore = usePracticeStore()

// 进度题库数据（扩展自 BankDetail）
interface ProgressBank extends BankDetail {
  // 学习进度（已练习题目数，包含未判题）
  progress: number
  // 已判题题目数（is_correct 不为空）
  completed_count?: number
  // 正确率
  accuracy: number
  // 练习人数（显示用）
  practiceCount: string
  // 权限相关
  hasAccess: boolean
  accessReason: string
  endTime?: string
  remainingDays?: number
  // 未完成会话相关（来自用户统计 API）
  inProgressSessionId?: number | null
  inProgressCount?: number
}

// 状态数据
const activeTab = ref(0)
const tabScrollLeft = ref(0)
const showTabManager = ref(false)
const showSearch = ref(false)
const searchKeyword = ref('')
const refreshing = ref(false)  // 下拉刷新状态

// ✅ Swiper 动态高度
const swiperHeight = ref('500px')

// 使用自定义 Tab
const { tabs: customTabs } = useCustomTabs()

// 使用系统信息（统一管理）
const { calculateSwiperHeight } = useSystemInfo()

// UView Tabs 需要的数据格式
const tabList = computed(() => customTabs.value.map(tab => ({ name: tab.name })))

// 分类数据（从API加载）
const categories = ref<CategoryDetail[]>([])

//题库数据（从API加载）
const allBanks = ref<ProgressBank[]>([])

const loadingCategories = ref(false)
const loadingBanks = ref(false)

// 扁平化的所有二级分类（用于构建可选项）
const flatCategories = computed(() => {
  const result: CategoryDetail[] = []
  categories.value.forEach(cat => {
    if (cat.children && cat.children.length > 0) {
      result.push(...cat.children)
    }
  })
  return result
})

/**
 * 加载分类数据
 */
async function loadCategories() {
  try {
    loadingCategories.value = true
    const data = await categoryApi.getCategoryTree({ cat_type: 1, is_active: true })
    categories.value = data
    console.log('[练习页面] 分类数据加载成功:', data)
  } catch (error) {
    console.error('[练习页面] 加载分类失败:', error)
    uni.showToast({
      title: '加载分类失败',
      icon: 'none'
    })
  } finally {
    loadingCategories.value = false
  }
}

/**
 * 加载用户学习统计数据（使用 Store 管理，按分类缓存）
 *
 * :param catId: 分类 ID（可选，筛选指定分类下的题库）
 * :param forceRefresh: 是否强制刷新
 */
async function loadUserStatistics(catId?: number, forceRefresh = false) {
  try {
    await practiceStore.loadUserStatistics(catId, forceRefresh)
    console.log('[练习页面] 用户统计数据加载成功, cat_id:', catId)
  } catch (error) {
    console.error('[练习页面] 加载用户统计失败:', error)
    // 统计数据加载失败不影响页面显示，静默失败
  }
}

/**
 * 加载题库数据
 */
async function loadBanks() {
  try {
    loadingBanks.value = true
    const data = await bankApi.getBankList({ status: 1 })

    // 获取当前分类的进度映射
    const currentCatId = getCurrentCategoryId()
    const progressMap = practiceStore.bankProgressMap(currentCatId)

    // 扁平化树形结构：将父题库和子题库都提取出来
    const flattenedBanks: ProgressBank[] = []

    data.forEach(bank => {
      // ✅ 使用 userStore 计算权限
      const access = userStore.checkBankAccess(bank.id, bank.cat_id, bank.scope)
      // ✅ 从用户统计数据获取进度
      const progressItem = progressMap.get(bank.id)

      // 🔍 调试日志：输出权限判断结果
      console.log(`[练习页面] 题库权限判断: ${bank.name}`, {
        bankId: bank.id,
        catId: bank.cat_id,
        scope: bank.scope,
        scopeDesc: bank.scope === 1 ? '免费' : '付费',
        hasAccess: access.hasAccess,
        reason: access.reason,
        reasonDesc: {
          'free': '✅ 免费题库',
          'vip_all': '✅ 全站会员',
          'vip_category': '✅ 分类会员',
          'purchased': '✅ 单独购买',
          'need_login': '🔒 需要登录',
          'need_purchase': '🔒 需要购买'
        }[access.reason]
      })

      // 添加父题库
      flattenedBanks.push({
        ...bank,
        progress: progressItem?.practiced_count || 0,
        completed_count: progressItem?.completed_count || 0,
        accuracy: progressItem?.accuracy_rate || 0,
        practiceCount: formatPracticeCount(bank.buy_count),
        hasAccess: access.hasAccess,
        accessReason: access.reason,
        endTime: access.endTime,
        remainingDays: access.remainingDays,
        inProgressSessionId: progressItem?.in_progress_session_id || null,
        inProgressCount: progressItem?.in_progress_count || 0
      })

      // 添加子题库（如果有）
      if (bank.children && bank.children.length > 0) {
        bank.children.forEach(childBank => {
          const childAccess = userStore.checkBankAccess(
            childBank.id,
            childBank.cat_id,
            childBank.scope
          )
          const childProgressItem = progressMap.get(childBank.id)

          flattenedBanks.push({
            ...childBank,
            progress: childProgressItem?.practiced_count || 0,
            completed_count: childProgressItem?.completed_count || 0,
            accuracy: childProgressItem?.accuracy_rate || 0,
            practiceCount: formatPracticeCount(childBank.buy_count),
            hasAccess: childAccess.hasAccess,
            accessReason: childAccess.reason,
            endTime: childAccess.endTime,
            remainingDays: childAccess.remainingDays,
            inProgressSessionId: childProgressItem?.in_progress_session_id || null,
            inProgressCount: childProgressItem?.in_progress_count || 0
          })
        })
      }
    })

    allBanks.value = flattenedBanks

    console.log('[练习页面] 题库数据加载成功:', allBanks.value)
    console.log('[练习页面] 题库数量统计:')
    console.log('  - 总题库数:', allBanks.value.length)
    console.log('  - 根题库数:', allBanks.value.filter(b => !b.parent_id).length)
    console.log('  - 子题库数:', allBanks.value.filter(b => b.parent_id).length)
  } catch (error) {
    console.error('[练习页面] 加载题库失败:', error)
    uni.showToast({
      title: '加载题库失败',
      icon: 'none'
    })
  } finally {
    loadingBanks.value = false
  }
}

/**
 * 格式化练习人数
 *
 * :param count: 购买数量
 * :return: 格式化后的字符串
 */
function formatPracticeCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万`
  }
  return String(count)
}

/**
 * 获取指定 Tab 下的题库列表
 *
 * :param tabIndex: Tab 索引
 * :return: 子题库列表
 */
function getTabBanks(tabIndex: number): ProgressBank[] {
  const tab = customTabs.value[tabIndex]
  if (!tab) return []

  // 全部 Tab
  if (tab.categoryId === 0 && tab.bankId === null) {
    return allBanks.value.filter(bank => bank.parent_id !== null)
  }

  // 指定分类 + 指定题库
  if (tab.bankId !== null) {
    return allBanks.value.filter(bank => bank.parent_id === tab.bankId)
  }

  // 指定分类 + 全部题库
  const categoryBanks = allBanks.value.filter(bank => bank.cat_id === tab.categoryId)
  return categoryBanks.filter(bank => bank.parent_id !== null)
}

/**
 * Tab 点击处理
 *
 * :param index: 标签索引
 */
function handleTabClick(index: number) {
  if (index === -1) {
    // 点击加号，打开管理弹窗
    showTabManager.value = true
    return
  }

  activeTab.value = index
}

/**
 * UView Tabs change 事件
 *
 * :param item: tab 项数据
 */
function handleTabChange(item: { index: number }) {
  activeTab.value = item.index
}

/**
 * 关闭 Tab 管理弹窗
 */
function handleCloseTabManager() {
  showTabManager.value = false
}

/**
 * Tab 列表变更后的处理
 */
function handleTabListChange() {
  // Tab 列表变更后，如果当前激活的 Tab 索引超出范围，重置为 0
  if (activeTab.value >= customTabs.value.length) {
    activeTab.value = 0
  }
}

/**
 * 打开搜索
 */
function handleOpenSearch() {
  showSearch.value = true
}

/**
 * 关闭搜索
 */
function handleCloseSearch() {
  showSearch.value = false
  searchKeyword.value = ''
}

/**
 * 搜索题库
 */
const searchResults = computed(() => {
  if (!searchKeyword.value.trim()) {
    return allBanks.value.filter(bank => bank.parent_id !== null)
  }

  const keyword = searchKeyword.value.toLowerCase()
  return allBanks.value.filter(bank => {
    if (bank.parent_id === null) return false
    return bank.name.toLowerCase().includes(keyword)
  })
})

/**
 * 选择搜索结果
 */
function handleSelectSearchResult(bank: BankDetail) {
  handleCloseSearch()
  handleBankClick(bank)
}

/**
 * 滑动切换处理
 */
function handleSwiperChange(e: any) {
  activeTab.value = e.detail.current
  updateTabScrollPosition(e.detail.current)
}

/**
 * 更新标签滚动位置
 */
function updateTabScrollPosition(index: number) {
  nextTick(() => {
    const tabWidth = 200
    const screenWidth = 750
    const scrollPosition = Math.max(0, index * tabWidth - screenWidth / 2 + tabWidth / 2)
    tabScrollLeft.value = scrollPosition
  })
}

/**
 * 题库卡片点击 - 进入详情页
 */
function handleBankClick(bank: ProgressBank) {
  uni.navigateTo({ url: `/pages/practice/bank-detail?bankId=${bank.id}` })
}

/**
 * 快速开始 - 直接进入刷题页
 *
 * 使用已加载的用户统计数据判断是否有未完成会话
 * 避免额外的 API 请求
 */
function handleQuickStart(bank: ProgressBank) {
  if (!bank.hasAccess) {
    uni.showToast({
      title: '暂无权限',
      icon: 'none'
    })
    return
  }

  // ✅ 直接使用已加载的统计数据判断
  if (bank.inProgressSessionId) {
    // 有进行中的会话，继续答题
    uni.navigateTo({
      url: `/pages/practice/detail?sessionId=${bank.inProgressSessionId}&resume=true&catId=${bank.cat_id}`
    })
  } else {
    // 没有进行中的会话，开始新练习
    uni.navigateTo({
      url: `/pages/practice/detail?bankId=${bank.id}&catId=${bank.cat_id}`
    })
  }
}

/**
 * 获取当前 Tab 的分类 ID
 */
function getCurrentCategoryId(): number {
  const tab = customTabs.value[activeTab.value]
  return tab?.categoryId || 0
}

/**
 * 更新题库的进度数据
 *
 * 当用户统计数据更新后，刷新 allBanks 中的进度信息
 */
function updateBankProgress() {
  // 获取当前分类的进度数据
  const currentCatId = getCurrentCategoryId()
  const progressMap = practiceStore.bankProgressMap(currentCatId)

  allBanks.value = allBanks.value.map(bank => {
    const progressItem = progressMap.get(bank.id)
    return {
      ...bank,
      progress: progressItem?.practiced_count || 0,
      completed_count: progressItem?.completed_count || 0,
      accuracy: progressItem?.accuracy_rate || 0,
      inProgressSessionId: progressItem?.in_progress_session_id || null,
      inProgressCount: progressItem?.in_progress_count || 0
    }
  })
}

/**
 * 下拉刷新处理
 */
async function handleRefresh() {
  console.log('[练习页面] 用户触发下拉刷新')
  refreshing.value = true

  try {
    const catId = getCurrentCategoryId()

    // 强制刷新当前分类的统计数据
    await practiceStore.refreshStatistics(catId)

    // 更新题库的进度数据
    updateBankProgress()

    uni.showToast({
      title: '刷新成功',
      icon: 'success',
      duration: 1500
    })
  } catch (error) {
    console.error('[练习页面] 刷新失败:', error)
    uni.showToast({
      title: '刷新失败',
      icon: 'none',
      duration: 1500
    })
  } finally {
    // 延迟结束刷新状态，确保动画完成
    setTimeout(() => {
      refreshing.value = false
    }, 500)
  }
}

// Tab 切换防抖定时器
let tabChangeDebounceTimer: ReturnType<typeof setTimeout> | null = null

/**
 * 监听 Tab 切换
 *
 * 当用户切换 Tab 时，加载对应分类的统计数据（带缓存，不会重复请求）
 */
watch(activeTab, (newTab, oldTab) => {
  // 清除之前的定时器
  if (tabChangeDebounceTimer) {
    clearTimeout(tabChangeDebounceTimer)
  }

  // 防抖处理：300ms 后加载新分类的统计数据
  tabChangeDebounceTimer = setTimeout(async () => {
    const catId = getCurrentCategoryId()
    console.log('[练习页面] Tab 切换:', oldTab, '->', newTab, ', cat_id:', catId)

    // 加载该分类的统计数据（如果已缓存则直接返回）
    await loadUserStatistics(catId)

    // 更新题库的进度数据
    updateBankProgress()
  }, 300)
})

/**
 * 组件挂载时加载数据
 */
onMounted(async () => {
  console.log('[练习页面] 组件挂载，开始加载数据')

  // ✅ 第一阶段：并行加载分类和用户信息
  await Promise.all([
    loadCategories(),
    userStore.fetchUserInfo()  // 带缓存，可能不发请求
  ])

  // ✅ 第二阶段：加载用户统计（根据初始 Tab 的分类 ID，带缓存）
  const initialCatId = getCurrentCategoryId()
  await loadUserStatistics(initialCatId)

  // ✅ 第三阶段：加载题库（依赖 bankProgressMap，需要在统计数据加载后）
  await loadBanks()

  console.log('[练习页面] 数据加载完成')
  console.log('- 分类数量:', categories.value.length)
  console.log('- Tab数量:', customTabs.value.length)
  console.log('- 题库数量:', allBanks.value.length)
  console.log('- 已缓存的分类数:', practiceStore.statisticsByCategory.size)
  console.log('- 当前分类有进度的题库数:', practiceStore.bankProgressMap(initialCatId).size)

  // ✅ 动态计算 Swiper 高度
  nextTick(() => {
    calculateSwiperHeight('.content-swiper', (height) => {
      swiperHeight.value = height
      console.log('[练习页面] Swiper 高度计算完成:', swiperHeight.value)
    })
  })
})

/**
 * 页面显示时检查缓存并刷新（从答题页返回时触发）
 */
onShow(() => {
  console.log('[练习页面] onShow 触发')

  const catId = getCurrentCategoryId()

  // 检查缓存是否过期（过期则静默刷新）
  if (practiceStore.isCacheExpired(catId)) {
    console.log('[练习页面] 缓存已过期，静默刷新')
    practiceStore.loadUserStatistics(catId, true).then(() => {
      updateBankProgress()
    })
  } else {
    console.log('[练习页面] 缓存未过期，跳过刷新')
  }
})
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';

.practice-page {
  background: $color-bg-page;
}

/* ============ 右侧操作按钮 ============ */

.tab-actions {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding-right: 16rpx;
}

.tab-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8rpx;
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.85);
    opacity: 0.6;
  }
}

/* ============ 主要内容区域 ============ */

.content-swiper {
  /* ✅ 高度通过 JS 动态计算并绑定到 :style */
  min-height: 500px; /* 默认最小高度，防止计算前闪烁 */
}

.main-content {
  height: 100%;
  overflow: hidden;
}

/* ============ 学习进度列表 ============ */

.progress-section {
  padding: 32rpx;
  padding-bottom: calc(32rpx + env(safe-area-inset-bottom));
}

.progress-loading,
.progress-empty {
  padding: 80rpx 32rpx;
  text-align: center;

  text {
    font-size: $font-size-base;
    color: $color-text-muted;
  }
}

.progress-item {
  background: $color-bg-card;
  border-radius: $radius-lg;
  margin-bottom: 24rpx;
  box-shadow: $shadow-sm;

  &:last-child {
    margin-bottom: 0;
  }
}
</style>
