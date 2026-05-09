<script lang="ts" setup>
import { api } from '@/api/sdk'
import GroupedListPage from '@/components/GroupedListPage.vue'
import { useGroupedListPage } from '@/hooks/useGroupedListPage'
import type { GroupedListPageConfig } from '@/hooks/useGroupedListPage'

defineOptions({
  name: 'MyWrongQuestions',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '我的错题',
  },
})

const config: GroupedListPageConfig = {
  pageTitle: '我的错题',
  sessionType: 'wrong',
  sourceType: 'wrong',
  exportTitleSuffix: '错题本',
  autoDestroySession: true,
  loginPrompt: '请先登录后查看错题',
  listTitle: '错题列表',
  loadingText: '错题列表加载中...',
  errorLogPrefix: '加载错题数据失败',
  emptyIcon: 'i-carbon-notebook-reference',
  emptyText: '暂时没有错题，继续保持！',
  primaryColor: '#DC2626',
  gradientFrom: '#FEF2F2',
  gradientVia: '#FFF8F8',
  exportBorderColor: '#FECACA',
  exportActiveBg: '#FEF2F2',
  fetchStatistics: (mode, studyDomain) => api.qbankWrongQuestionStatistics({
    query: {
      group_by: mode,
      study_domain: studyDomain,
    } as any,
  }).then(res => res.data),
}

const ctx = useGroupedListPage(config)

onShow(() => void ctx.loadData())

onPullDownRefresh(async () => {
  await ctx.loadData()
  uni.stopPullDownRefresh()
})
</script>

<template>
  <GroupedListPage :ctx="ctx">
    <template #stats="{ statistics }">
      <view class="grid grid-cols-3 gap-3">
        <view class="flex flex-col items-center rounded-xl bg-[#FEF2F2] py-3">
          <text class="text-[22px] text-[#DC2626] font-black">{{ statistics.total_count }}</text>
          <text class="mt-1 text-[11px] text-[#94A3B8]">错题总数</text>
        </view>
        <view class="flex flex-col items-center rounded-xl bg-[#FFF7ED] py-3">
          <text class="text-[22px] text-[#EA580C] font-black">{{ statistics.unmastered_count }}</text>
          <text class="mt-1 text-[11px] text-[#94A3B8]">待攻克</text>
        </view>
        <view class="flex flex-col items-center rounded-xl bg-[#ECFDF5] py-3">
          <text class="text-[22px] text-[#16A34A] font-black">{{ statistics.mastered_count }}</text>
          <text class="mt-1 text-[11px] text-[#94A3B8]">已掌握</text>
        </view>
      </view>
    </template>
  </GroupedListPage>
</template>
