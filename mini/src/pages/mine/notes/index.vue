<script lang="ts" setup>
import { api } from '@/api/sdk'
import GroupedListPage from '@/components/GroupedListPage.vue'
import { useGroupedListPage } from '@/hooks/useGroupedListPage'
import type { GroupedListPageConfig } from '@/hooks/useGroupedListPage'

defineOptions({
  name: 'MyNotes',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '我的笔记',
  },
})

const config: GroupedListPageConfig = {
  pageTitle: '我的笔记',
  sessionType: 'note',
  sourceType: 'note',
  exportTitleSuffix: '笔记题本',
  loginPrompt: '请先登录后查看笔记',
  listTitle: '笔记列表',
  loadingText: '笔记列表加载中...',
  errorLogPrefix: '加载笔记数据失败',
  emptyIcon: 'i-carbon-notebook-reference',
  emptyText: '还没有写过笔记，刷题时记得沉淀思路。',
  primaryColor: '#2563EB',
  gradientFrom: '#EFF6FF',
  gradientVia: '#F8FBFF',
  exportBorderColor: '#BFDBFE',
  exportActiveBg: '#EFF6FF',
  fetchStatistics: (mode, studyDomain) => api.qbankNoteStatistics({
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
        <view class="flex flex-col items-center rounded-xl bg-[#EFF6FF] py-3">
          <text class="text-[22px] text-[#2563EB] font-black">{{ statistics.total_count }}</text>
          <text class="mt-1 text-[11px] text-[#94A3B8]">全部笔记</text>
        </view>
        <view class="flex flex-col items-center rounded-xl bg-[#ECFEFF] py-3">
          <text class="text-[22px] text-[#0891B2] font-black">{{ statistics.public_count }}</text>
          <text class="mt-1 text-[11px] text-[#94A3B8]">公开笔记</text>
        </view>
        <view class="flex flex-col items-center rounded-xl bg-[#F5F3FF] py-3">
          <text class="text-[22px] text-[#7C3AED] font-black">{{ statistics.featured_count }}</text>
          <text class="mt-1 text-[11px] text-[#94A3B8]">精选笔记</text>
        </view>
      </view>
    </template>
  </GroupedListPage>
</template>
