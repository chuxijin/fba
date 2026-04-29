<script lang="ts" setup>
defineOptions({
  name: 'ThinkingTraining',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '思维能力训练',
  },
})

interface TrainingGroup {
  title: string
  items: string[]
}

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const trainingGroups: TrainingGroup[] = [
  {
    title: '找数能力',
    items: ['舒尔特方格', '滚动舒尔特', '文字找茬'],
  },
  {
    title: '推理能力',
    items: ['数独', '猜数字', '24点'],
  },
  {
    title: '工作记忆',
    items: ['瞬间记忆', '闪电心算'],
  },
  {
    title: '注意力',
    items: ['斯特鲁普', '图形旋转'],
  },
]

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.navigateTo({ url: '/pages/ability-practice/index' })
}

function openTrainingItem(name: string) {
  uni.showToast({ title: `${name} 正在接入中`, icon: 'none' })
}
</script>

<template>
  <view class="min-h-screen bg-[#F5F1EA] text-[#111827]">
    <view class="relative z-10 w-full bg-[#F5F1EA]" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white/90 text-[#475569] shadow-sm active:scale-95" @click="goBack">
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="text-lg font-bold tracking-widest">
          思维能力训练
        </text>
      </view>
    </view>

    <view class="px-5 pb-8 pt-5">
      <view class="mb-7 text-[24px] font-black tracking-wide">
        思维能力训练
      </view>

      <view v-for="group in trainingGroups" :key="group.title" class="mb-6">
        <view class="mb-3 flex items-center">
          <view class="mr-2 h-7 w-[3px] rounded-full bg-[#F59E0B]" />
          <text class="text-[16px] font-black">
            {{ group.title }}
          </text>
        </view>

        <view class="grid grid-cols-3 gap-2">
          <view
            v-for="item in group.items"
            :key="item"
            class="h-[58px] flex items-center justify-center rounded-md bg-[#E8EDF5] px-2 text-center text-[15px] text-[#1F2937] font-black leading-tight shadow-[0_2px_10px_-9px_rgba(31,41,55,0.4)] active:scale-[0.98]"
            @click="openTrainingItem(item)"
          >
            {{ item }}
          </view>
        </view>
      </view>
    </view>
  </view>
</template>
