<script lang="ts" setup>
import { fbaApi } from '@/api/sdk'
import GroupedListPage from '@/components/GroupedListPage.vue'
import { useGroupedListPage } from '@/hooks/useGroupedListPage'
import type { GroupedListPageConfig } from '@/hooks/useGroupedListPage'

defineOptions({
  name: 'MyFavorites',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '我的收藏',
  },
})

const config: GroupedListPageConfig = {
  pageTitle: '我的收藏',
  sessionType: 'favorite',
  sourceType: 'favorite',
  exportTitleSuffix: '收藏题本',
  loginPrompt: '请先登录后查看收藏',
  listTitle: '收藏列表',
  loadingText: '收藏列表加载中...',
  errorLogPrefix: '加载收藏数据失败',
  emptyIcon: 'i-carbon-star',
  emptyText: '还没有收藏内容，遇到好题记得先收下。',
  primaryColor: '#D97706',
  gradientFrom: '#FFFBEB',
  gradientVia: '#FFFDF8',
  exportBorderColor: '#FDE68A',
  exportActiveBg: '#FFFBEB',
  fetchStatistics: (mode, studyDomain) => fbaApi.qbank.favorite.getStatistics({
    group_by: mode,
    study_domain: studyDomain,
  }),
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
      <view class="grid grid-cols-2 gap-3">
        <view class="flex flex-col items-center rounded-xl bg-[#FFFBEB] py-3">
          <text class="text-[22px] text-[#D97706] font-black">{{ statistics.total_count }}</text>
          <text class="mt-1 text-[11px] text-[#94A3B8]">总收藏</text>
        </view>
        <view class="flex flex-col items-center rounded-xl bg-[#F8FAFC] py-3">
          <text class="text-[22px] text-[#475569] font-black">{{ statistics.folder_count || 0 }}</text>
          <text class="mt-1 text-[11px] text-[#94A3B8]">收藏夹</text>
        </view>
      </view>
    </template>
  </GroupedListPage>
</template>
