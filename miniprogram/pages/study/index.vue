<template>
  <view class="study-page">
    <!-- Tab 切换区域 - 使用 Wot Design Uni Tabs -->
    <wd-tabs
      v-model="activeTabIndex"
      :scrollable="false"
      line-color="#22c55e"
      @change="handleTabChange"
    >
      <wd-tab v-for="(tab, index) in tabList" :key="index" :title="tab.name" />
    </wd-tabs>

    <!-- 主要内容区域 - 支持左右滑动 -->
    <swiper
      class="content-swiper"
      :style="{ height: swiperHeight }"
      :current="activeTabIndex"
      :duration="300"
      @change="handleSwiperChange"
    >
      <swiper-item v-for="tab in tabs" :key="tab.id">
        <scroll-view class="main-content" scroll-y>
          <!-- 资料库 -->
          <MaterialsTab v-if="tab.id === 'materials'" />

          <!-- 知识库 -->
          <KnowledgeTab v-if="tab.id === 'knowledge'" />
        </scroll-view>
      </swiper-item>
    </swiper>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useSystemInfo } from '@/composables/useSystemInfo'
import MaterialsTab from './modules/MaterialsTab.vue'
import KnowledgeTab from './modules/KnowledgeTab.vue'

declare const uni: any

interface Tab {
  id: string
  label: string
}

const tabs: Tab[] = [
  { id: 'materials', label: '资料库' },
  { id: 'knowledge', label: '知识库' }
]

// UView Tabs 需要的数据格式
const tabList = computed(() => tabs.map(tab => ({ name: tab.label })))

// 当前选中的 tab 索引
const activeTabIndex = ref(0)

// Swiper 动态高度
const swiperHeight = ref('500px')

// 使用系统信息
const { calculateSwiperHeight } = useSystemInfo()

/**
 * Tab 切换
 *
 * :param options: wd-tabs change 事件参数
 */
function handleTabChange(options: { name: number }) {
  activeTabIndex.value = options.name
}

/**
 * Swiper 滑动切换处理
 */
function handleSwiperChange(e: any) {
  activeTabIndex.value = e.detail.current
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
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';
@import '@/styles/mixins.scss';

.study-page {
  background: #f8f9fa;
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
