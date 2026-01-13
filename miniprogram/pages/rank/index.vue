<template>
  <view class="rank-page">
    <!-- Tab 切换区域 - 使用 UView Plus Tabs -->
    <u-tabs
      :list="tabList"
      :current="activeTabIndex"
      :scrollable="false"
      lineColor="#ffffff"
      :activeStyle="{ color: '#ffffff', fontWeight: 'bold', fontSize: '36rpx' }"
      :inactiveStyle="{ color: 'rgba(255, 255, 255, 0.7)', fontSize: '32rpx' }"
      bgColor="transparent"
      @change="handleTabChange"
    ></u-tabs>

    <!-- 主要内容区域 - 支持左右滑动 -->
    <swiper
      class="content-swiper"
      :style="{ height: swiperHeight }"
      :current="activeTabIndex"
      :duration="300"
      @change="handleSwiperChange"
    >
      <swiper-item v-for="tab in tabs" :key="tab.type">
        <scroll-view class="main-content" scroll-y>
          <RankContent :loading="loading" :rank-data="rankData" :current-tab="tab.type" />
        </scroll-view>
      </swiper-item>
    </swiper>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import * as homeApi from '@/api/business/home'
import { useSystemInfo } from '@/composables/useSystemInfo'
import RankContent from './components/RankContent.vue'

declare const uni: any

interface Tab {
  type: 'practice_count' | 'accuracy_rate' | 'streak_days'
  label: string
}

const tabs: Tab[] = [
  { type: 'practice_count', label: '刷题数量' },
  { type: 'accuracy_rate', label: '正确率' },
  { type: 'streak_days', label: '坚持天数' }
]

// UView Tabs 需要的数据格式
const tabList = computed(() => tabs.map(tab => ({ name: tab.label })))

// 当前选中的 tab 索引
const activeTabIndex = ref(0)
const loading = ref(false)
const rankData = ref<homeApi.RankListData | null>(null)

// Swiper 动态高度
const swiperHeight = ref('500px')

// 使用系统信息
const { calculateSwiperHeight } = useSystemInfo()

const currentTab = computed(() => tabs[activeTabIndex.value].type)

/**
 * Tab 切换
 */
function handleTabChange(item: { index: number }) {
  activeTabIndex.value = item.index
}

/**
 * Swiper 滑动切换处理
 */
function handleSwiperChange(e: any) {
  activeTabIndex.value = e.detail.current
}

/**
 * 加载排行榜数据
 */
async function loadRankData() {
  try {
    loading.value = true

    const data = await homeApi.getRankList({
      rank_type: currentTab.value,
      limit: 100
    })

    rankData.value = data
    console.log('[排行榜] 数据加载成功:', data)
  } catch (error) {
    console.error('[排行榜] 数据加载失败:', error)
    uni.showToast({
      title: '加载失败',
      icon: 'none'
    })
  } finally {
    loading.value = false
  }
}

/**
 * 组件挂载时计算 Swiper 高度
 */
onMounted(() => {
  nextTick(() => {
    calculateSwiperHeight('.content-swiper', (height) => {
      swiperHeight.value = height
    })
  })
})

// 监听 Tab 切换，加载对应数据
watch(currentTab, () => {
  loadRankData()
}, { immediate: true })
</script>

<style scoped lang="scss">
.rank-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #ff6b35 0%, #f5f7fa 400rpx);
}

/* ==================== 主要内容区域 ==================== */
.content-swiper {
  /* 高度通过 JS 动态计算并绑定到 :style */
  min-height: 500px; /* 默认最小高度，防止计算前闪烁 */
}

.main-content {
  height: 100%;
  overflow: hidden;
}
</style>
