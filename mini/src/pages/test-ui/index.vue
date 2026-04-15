<script lang="ts" setup>
import { ref } from 'vue'
import PracticeNode from '@/components/PracticeNode.vue'

defineOptions({ name: 'FenbiTestUI' })
definePage({
  style: {
    navigationBarTitleText: 'UI测试 - 粉笔风格',
    navigationBarBackgroundColor: '#FFFFFF',
    navigationStyle: 'custom',
  },
})

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

function goBack() {
  uni.navigateBack()
}

// 模拟完整嵌套树的数据
const mockTree = ref([
  {
    id: 1,
    name: '政治理论',
    hideProgress: true,
    progress: 137,
    total: 1400,
    bananas: 2,
    expanded: true,
    children: [
      {
        id: 11,
        name: '马克思主义',
        progress: 109,
        total: 265,
        bananas: 2,
        expanded: true,
        children: [
          {
            id: 111,
            name: '马克思主义哲学',
            progress: 106,
            total: 254,
            bananas: 3,
            expanded: true,
            children: [
              { id: 1111, name: '总论', progress: 1, total: 4, bananas: 1 },
              { id: 1112, name: '唯物论', progress: 45, total: 74, bananas: 4 },
              { id: 1113, name: '辩证法', progress: 60, total: 176, bananas: 5 },
            ]
          },
          {
            id: 112,
            name: '马克思主义政治经济学',
            progress: 3,
            total: 11,
            bananas: 1,
            expanded: false,
            children: [
              { id: 1121, name: '资本主义的形成及其本质', progress: 3, total: 11, bananas: 4 }
            ]
          }
        ]
      },
      {
        id: 12,
        name: '毛泽东思想',
        progress: 28,
        total: 1135,
        bananas: 1,
        expanded: false,
        children: [
          { id: 121, name: '毛泽东思想及其历史地位', progress: 28, total: 200, bananas: 1 }
        ]
      }
    ]
  },
  {
    id: 2,
    name: '行测职业能力测验',
    progress: 450,
    total: 3200,
    bananas: 3,
    expanded: false,
    children: [
      {
        id: 21,
        name: '言语理解与表达',
        progress: 120,
        total: 580,
        bananas: 4,
        expanded: true,
        children: [
          {
            id: 211,
            name: '逻辑填空',
            progress: 80,
            total: 200,
            bananas: 3,
            expanded: true,
            children: [
              { id: 2111, name: '实词辨析', progress: 40, total: 100, bananas: 4 },
              { id: 2112, name: '成语辨析', progress: 40, total: 100, bananas: 2 }
            ]
          },
          {
            id: 212,
            name: '片段阅读',
            progress: 40,
            total: 380,
            bananas: 2,
            expanded: false,
            children: [
              { id: 2121, name: '中心理解题', progress: 20, total: 180, bananas: 3 },
              { id: 2122, name: '细节判断题', progress: 20, total: 200, bananas: 2 }
            ]
          }
        ]
      }
    ]
  }
])
</script>

<template>
  <view class="min-h-screen bg-white">
    <!-- 顶部状态栏及导航栏 -->
    <view class="w-full bg-white relative z-50">
      <view :style="{ height: `${statusBarHeight}px` }" />
      <view class="h-11 flex items-center px-4 relative">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:bg-gray-100 rounded-full transition-colors" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#333]" />
        </view>
        <view class="flex-1 text-center text-[17px] font-medium text-[#333]">刷题树状浏览</view>
      </view>
    </view>

    <!-- 列表区 -->
    <view class="px-5 pt-2 pb-12">
      <!-- 渲染根节点群：顶部/底部/模块间的浅分割线 -->
      <view class="border-y border-[#F1F5F9]">
        <view
          v-for="(node, idx) in mockTree"
          :key="node.id"
          :class="idx < mockTree.length - 1 ? 'border-b border-[#F1F5F9]' : ''"
        >
          <PracticeNode :node="node" :depth="0" />
        </view>
      </view>
    </view>

  </view>
</template>

<style scoped>
</style>

