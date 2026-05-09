<script lang="ts" setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { api } from '@/api/sdk'
import { useTokenStore } from '@/store'

defineOptions({ name: 'RankListPage' })

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
  },
})

interface RankUser {
  user_id: number
  nickname: string
  avatar: string | null
}

interface RankItem {
  rank: number
  user: RankUser
  value: number | string
  is_current_user: boolean
}

interface RankData {
  rank_type: string
  current_user_rank: RankItem | null
  top_users: RankItem[]
}

type RankTab = 'practice_count' | 'streak_days'

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const activeTab = ref<RankTab>('practice_count')
const loading = ref(false)
const rankDataMap = ref<Record<string, RankData>>({})

const tabs: { key: RankTab, label: string }[] = [
  { key: 'practice_count', label: '刷题数量' },
  { key: 'streak_days', label: '坚持天数' },
]

const activeIndex = computed(() => tabs.findIndex(t => t.key === activeTab.value))

function getTabRankData(tab: RankTab) {
  return rankDataMap.value[tab] || null
}

function getTabPodium(tab: RankTab) {
  const topUsers = getTabRankData(tab)?.top_users || []
  const first = topUsers.find(u => u.rank === 1) || null
  const second = topUsers.find(u => u.rank === 2) || null
  const third = topUsers.find(u => u.rank === 3) || null
  return [second, first, third]
}

function getTabListUsers(tab: RankTab) {
  const topUsers = getTabRankData(tab)?.top_users || []
  return topUsers.filter(u => u.rank > 3)
}

function getTabUnit(tab: RankTab) {
  return tab === 'practice_count' ? '题' : '天'
}

function formatValue(value: number | string, tab: RankTab) {
  return `${Number(value || 0)} ${getTabUnit(tab)}`
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.switchTab({ url: '/pages/practice/index' })
}

async function switchTab(tab: RankTab) {
  activeTab.value = tab
  if (!rankDataMap.value[tab]) {
    await loadRank(tab)
  }
}

function onSwiperChange(e: any) {
  const index = e.detail.current
  if (index >= 0 && index < tabs.length) {
    switchTab(tabs[index].key)
  }
}

async function loadRank(rankType: RankTab = activeTab.value) {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }

  loading.value = true
  try {
    const { data } = await api.homeRankList({ query: { rank_type: rankType, limit: 100 } }) as any
    rankDataMap.value[rankType] = data
  }
  catch (error) {
    console.error('加载排行榜失败:', error)
    uni.showToast({ title: '加载排行榜失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

function avatarUrl(user: RankUser | null | undefined) {
  return user?.avatar || ''
}

function displayName(user: RankUser | null | undefined) {
  return user?.nickname || '匿名用户'
}

onShow(() => {
  loadRank()
})
</script>

<template>
  <view class="relative min-h-screen from-[#FFF7ED] via-[#FFFBF5] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <!-- 导航栏 -->
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">排行榜</text>
      </view>
    </view>

    <!-- Tab 切换 -->
    <view class="mt-2 flex items-center justify-center gap-8 px-4 pb-3">
      <view
        v-for="tab in tabs"
        :key="tab.key"
        class="relative cursor-pointer pb-2 text-[16px] font-bold transition-colors"
        :class="activeTab === tab.key ? 'text-[#EA580C]' : 'text-[#94A3B8]'"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
        <view
          v-if="activeTab === tab.key"
          class="absolute bottom-0 left-1/2 h-[3px] w-6 rounded-full bg-[#EA580C] -translate-x-1/2"
        />
      </view>
    </view>

    <!-- Swiper 内容区 -->
    <swiper
      class="flex-1"
      :current="activeIndex"
      :style="{ height: '100vh' }"
      @change="onSwiperChange"
    >
      <swiper-item v-for="tab in tabs" :key="tab.key">
        <scroll-view scroll-y class="h-full">
          <!-- 加载中 -->
          <view v-if="loading && !getTabRankData(tab.key)" class="py-20 text-center text-[14px] text-[#94A3B8]">
            排行榜加载中...
          </view>

          <template v-else-if="getTabRankData(tab.key)">
            <!-- 领奖台 -->
            <view class="mx-4 mt-2 overflow-hidden rounded-3xl from-[#F97316] to-[#EA580C] bg-gradient-to-br px-4 pb-6 pt-5 shadow-[0_12px_32px_rgba(234,88,12,0.2)]">
              <view class="flex items-end justify-center gap-2">
                <!-- 第 2 名 -->
                <view class="flex flex-col items-center" style="width: 30%;">
                  <view class="relative mb-1">
                    <text class="absolute z-10 -left-1.5 -top-1.5 text-[18px]">🥈</text>
                    <image
                      v-if="avatarUrl(getTabPodium(tab.key)[0]?.user)"
                      class="h-14 w-14 rounded-full border-2 border-white/50 bg-white/20"
                      :src="avatarUrl(getTabPodium(tab.key)[0]?.user)"
                      mode="aspectFill"
                    />
                    <view v-else class="h-14 w-14 flex items-center justify-center rounded-full border-2 border-white/50 bg-white/20">
                      <view class="i-carbon-user text-2xl text-white/60" />
                    </view>
                  </view>
                  <text class="max-w-full truncate text-center text-[12px] text-white/90">{{ displayName(getTabPodium(tab.key)[0]?.user) }}</text>
                  <text class="mt-0.5 text-[13px] text-[#FEF3C7] font-black">{{ getTabPodium(tab.key)[0] ? formatValue(getTabPodium(tab.key)[0]!.value, tab.key) : '--' }}</text>
                </view>

                <!-- 第 1 名 -->
                <view class="flex flex-col items-center -mt-2" style="width: 34%;">
                  <view class="i-carbon-trophy mb-1 text-3xl text-[#FDE68A]" />
                  <view class="relative mb-1">
                    <image
                      v-if="avatarUrl(getTabPodium(tab.key)[1]?.user)"
                      class="h-[72px] w-[72px] rounded-full border-3 border-[#FDE68A] bg-white/20 shadow-[0_0_20px_rgba(253,230,138,0.4)]"
                      :src="avatarUrl(getTabPodium(tab.key)[1]?.user)"
                      mode="aspectFill"
                    />
                    <view v-else class="h-[72px] w-[72px] flex items-center justify-center rounded-full border-3 border-[#FDE68A] bg-white/20">
                      <view class="i-carbon-user text-3xl text-white/60" />
                    </view>
                  </view>
                  <text class="max-w-full truncate text-center text-[13px] text-white font-bold">{{ displayName(getTabPodium(tab.key)[1]?.user) }}</text>
                  <text class="mt-0.5 text-[15px] text-[#FDE68A] font-black">{{ getTabPodium(tab.key)[1] ? formatValue(getTabPodium(tab.key)[1]!.value, tab.key) : '--' }}</text>
                </view>

                <!-- 第 3 名 -->
                <view class="flex flex-col items-center" style="width: 30%;">
                  <view class="relative mb-1">
                    <text class="absolute z-10 -left-1.5 -top-1.5 text-[18px]">🥉</text>
                    <image
                      v-if="avatarUrl(getTabPodium(tab.key)[2]?.user)"
                      class="h-14 w-14 rounded-full border-2 border-white/50 bg-white/20"
                      :src="avatarUrl(getTabPodium(tab.key)[2]?.user)"
                      mode="aspectFill"
                    />
                    <view v-else class="h-14 w-14 flex items-center justify-center rounded-full border-2 border-white/50 bg-white/20">
                      <view class="i-carbon-user text-2xl text-white/60" />
                    </view>
                  </view>
                  <text class="max-w-full truncate text-center text-[12px] text-white/90">{{ displayName(getTabPodium(tab.key)[2]?.user) }}</text>
                  <text class="mt-0.5 text-[13px] text-[#FEF3C7] font-black">{{ getTabPodium(tab.key)[2] ? formatValue(getTabPodium(tab.key)[2]!.value, tab.key) : '--' }}</text>
                </view>
              </view>
            </view>

            <!-- 我的排名 -->
            <view v-if="getTabRankData(tab.key)?.current_user_rank" class="mx-4 mt-4 flex items-center rounded-2xl border border-[#FED7AA] bg-[#FFFBF5] px-4 py-3.5 shadow-sm">
              <view class="mr-3 flex flex-col items-center">
                <text class="text-[14px] text-[#EA580C] font-black">我</text>
                <text class="text-[11px] text-[#94A3B8]">第{{ getTabRankData(tab.key)!.current_user_rank!.rank }}名</text>
              </view>
              <image
                v-if="avatarUrl(getTabRankData(tab.key)!.current_user_rank!.user)"
                class="mr-3 h-10 w-10 shrink-0 rounded-full bg-[#F1F5F9]"
                :src="avatarUrl(getTabRankData(tab.key)!.current_user_rank!.user)"
                mode="aspectFill"
              />
              <view v-else class="mr-3 h-10 w-10 flex shrink-0 items-center justify-center rounded-full bg-[#F1F5F9]">
                <view class="i-carbon-user text-lg text-[#94A3B8]" />
              </view>
              <text class="min-w-0 flex-1 truncate text-[14px] text-[#1E293B] font-bold">{{ displayName(getTabRankData(tab.key)!.current_user_rank!.user) }}</text>
              <text class="ml-2 shrink-0 text-[14px] text-[#EA580C] font-black">{{ formatValue(getTabRankData(tab.key)!.current_user_rank!.value, tab.key) }}</text>
            </view>

            <!-- 排行列表 -->
            <view class="mx-4 mt-4 overflow-hidden rounded-2xl border border-white/60 bg-white/90 shadow-sm backdrop-blur-sm">
              <view v-if="getTabListUsers(tab.key).length">
                <view
                  v-for="item in getTabListUsers(tab.key)"
                  :key="item.rank"
                  class="flex items-center border-b border-[#F1F5F9] px-4 py-3.5 last:border-none"
                  :class="{ 'bg-[#FFFBF5]': item.is_current_user }"
                >
                  <text class="w-8 shrink-0 text-center text-[14px] text-[#94A3B8] font-bold">{{ item.rank }}</text>
                  <image
                    v-if="avatarUrl(item.user)"
                    class="mx-3 h-10 w-10 shrink-0 rounded-full bg-[#F1F5F9]"
                    :src="avatarUrl(item.user)"
                    mode="aspectFill"
                  />
                  <view v-else class="mx-3 h-10 w-10 flex shrink-0 items-center justify-center rounded-full bg-[#F1F5F9]">
                    <view class="i-carbon-user text-lg text-[#CBD5E1]" />
                  </view>
                  <text class="min-w-0 flex-1 truncate text-[14px] text-[#334155] font-medium">{{ displayName(item.user) }}</text>
                  <text class="ml-2 shrink-0 text-[14px] text-[#475569] font-bold">{{ formatValue(item.value, tab.key) }}</text>
                </view>
              </view>

              <view v-else-if="!loading" class="py-12 text-center text-[14px] text-[#94A3B8]">
                暂无排行数据
              </view>
            </view>

            <view class="h-20" />
          </template>

          <view v-else class="py-20 text-center text-[14px] text-[#94A3B8]">
            暂无排行数据
          </view>
        </scroll-view>
      </swiper-item>
    </swiper>
  </view>
</template>
