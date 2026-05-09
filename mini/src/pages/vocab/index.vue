<script lang="ts" setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { api } from '@/api/sdk'
import { useTokenStore } from '@/store'
import { setLoginRedirect } from '@/utils/toLoginPage'
import LoginModal from '@/components/LoginModal.vue'

defineOptions({ name: 'VocabIndex' })
definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '单词记忆',
  },
})

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const showLoginModal = ref(false)
const loading = ref(false)

// 今日打卡状态
const todayStatus = ref<any>(null)
// 学习统计
const studyStats = ref<any>(null)
// 连续打卡
const streakInfo = ref<any>(null)

const hasLogin = computed(() => tokenStore.hasLogin)
const newWords = computed(() => todayStatus.value?.new_words || 0)
const reviewWords = computed(() => todayStatus.value?.review_words || 0)
const dailyTarget = computed(() => todayStatus.value?.daily_target || 20)
const progressPercent = computed(() => todayStatus.value?.progress_percent || 0)
const streakDays = computed(() => streakInfo.value?.current_streak || todayStatus.value?.streak_days || 0)
const isCheckedIn = computed(() => todayStatus.value?.is_checked_in || false)
const durationMinutes = computed(() => Math.floor((todayStatus.value?.duration_seconds || 0) / 60))

const totalLearned = computed(() => studyStats.value?.total_learned || 0)
const totalMastered = computed(() => studyStats.value?.total_mastered || 0)
const todayDueCount = computed(() => studyStats.value?.today_due_count || 0)

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.switchTab({ url: '/pages/mine/index' })
}

function requireLogin(url: string) {
  if (!hasLogin.value) {
    setLoginRedirect(url)
    showLoginModal.value = true
    return
  }
  uni.navigateTo({ url })
}

function startStudy() {
  requireLogin('/pages/vocab/session/index')
}

function openBookSelect() {
  requireLogin('/pages/vocab/books/index')
}

function openCheckinCalendar() {
  requireLogin('/pages/vocab/checkin/index')
}

function openSettings() {
  requireLogin('/pages/vocab/settings/index')
}

async function loadData() {
  if (!hasLogin.value) return

  loading.value = true
  try {
    const [today, stats, streak] = await Promise.allSettled([
      api.getTodayStatus(),
      api.getStudyStats(),
      api.getStreakInfo(),
    ])
    if (today.status === 'fulfilled') todayStatus.value = (today.value as any)?.data
    if (stats.status === 'fulfilled') studyStats.value = (stats.value as any)?.data
    if (streak.status === 'fulfilled') streakInfo.value = (streak.value as any)?.data
  }
  catch (err) {
    console.error('加载单词数据失败:', err)
  }
  finally {
    loading.value = false
  }
}

async function handleLoginSuccess() {
  showLoginModal.value = false
  await loadData()
}

onShow(() => {
  tokenStore.updateNowTime()
  void loadData()
})
</script>

<template>
  <view class="min-h-screen bg-[#F6F8FA] text-[#111827]">
    <!-- 顶部导航 -->
    <view class="relative z-10 w-full bg-[#F6F8FA]" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view
          class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white text-[#475569] shadow-sm active:scale-95"
          @click="goBack"
        >
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="text-lg font-bold tracking-widest">
          单词记忆
        </text>
      </view>
    </view>

    <view class="px-4 pb-8 pt-3">
      <!-- 今日进度卡片 -->
      <view class="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] p-5 text-white shadow-[0_8px_32px_-12px_rgba(99,102,241,0.5)]">
        <view class="pointer-events-none absolute h-32 w-32 rounded-full bg-white/10 -right-6 -top-6" />
        <view class="pointer-events-none absolute bottom-0 h-20 w-20 rounded-full bg-white/5 -left-4" />

        <view class="relative z-10">
          <view class="flex items-center justify-between">
            <view>
              <view class="text-[20px] font-black tracking-wide">
                今日目标
              </view>
              <view class="mt-0.5 text-[12px] text-white/60">
                {{ isCheckedIn ? '🎉 今日已打卡' : '坚持学习，提升词汇量' }}
              </view>
            </view>
            <!-- 连续打卡徽章 -->
            <view v-if="streakDays > 0" class="flex flex-col items-center rounded-xl bg-white/15 px-3 py-2 backdrop-blur-sm">
              <view class="text-[22px] font-black leading-none">
                {{ streakDays }}
              </view>
              <view class="text-[10px] text-white/70">
                连续天
              </view>
            </view>
          </view>

          <!-- 进度条 -->
          <view class="mt-4">
            <view class="flex items-center justify-between text-[11px] text-white/60">
              <text>新词 {{ newWords }}/{{ dailyTarget }}</text>
              <text>{{ progressPercent }}%</text>
            </view>
            <view class="mt-1.5 h-2 overflow-hidden rounded-full bg-white/20">
              <view
                class="h-full rounded-full bg-gradient-to-r from-[#FDE68A] to-[#FBBF24] transition-all duration-500"
                :style="{ width: `${Math.min(100, progressPercent)}%` }"
              />
            </view>
          </view>

          <!-- 数据行 -->
          <view class="mt-4 flex items-end justify-between">
            <view class="flex gap-5">
              <view>
                <view class="text-[24px] font-black leading-none">
                  {{ newWords }}
                </view>
                <view class="mt-1 text-[10px] text-white/50">
                  今日新词
                </view>
              </view>
              <view>
                <view class="text-[24px] font-black leading-none">
                  {{ reviewWords }}
                </view>
                <view class="mt-1 text-[10px] text-white/50">
                  今日复习
                </view>
              </view>
              <view>
                <view class="text-[24px] font-black leading-none">
                  {{ durationMinutes }}
                </view>
                <view class="mt-1 text-[10px] text-white/50">
                  学习(分)
                </view>
              </view>
            </view>
            <view
              class="rounded-xl bg-white px-5 py-2.5 text-[14px] text-[#6366F1] font-bold shadow-lg active:scale-95"
              @click="startStudy"
            >
              {{ todayDueCount > 0 ? '开始复习' : '开始学习' }}
            </view>
          </view>
        </view>
      </view>

      <!-- 学习概览 -->
      <view class="mt-4 grid grid-cols-3 gap-3">
        <view class="rounded-xl bg-white py-4 text-center shadow-sm">
          <view class="text-[22px] text-[#6366F1] font-black">
            {{ totalLearned }}
          </view>
          <view class="mt-0.5 text-[11px] text-[#94A3B8]">
            已学单词
          </view>
        </view>
        <view class="rounded-xl bg-white py-4 text-center shadow-sm">
          <view class="text-[22px] text-[#059669] font-black">
            {{ totalMastered }}
          </view>
          <view class="mt-0.5 text-[11px] text-[#94A3B8]">
            已掌握
          </view>
        </view>
        <view class="rounded-xl bg-white py-4 text-center shadow-sm">
          <view class="text-[22px] text-[#EA580C] font-black">
            {{ todayDueCount }}
          </view>
          <view class="mt-0.5 text-[11px] text-[#94A3B8]">
            待复习
          </view>
        </view>
      </view>

      <!-- 功能入口 -->
      <view class="mt-4 grid grid-cols-4 gap-3">
        <view class="flex flex-col items-center rounded-xl bg-white py-4 shadow-sm active:scale-95" @click="openBookSelect">
          <view class="mb-2 h-10 w-10 flex items-center justify-center rounded-xl bg-[#EEF2FF] text-[#4F46E5]">
            <view class="i-carbon-book text-[20px]" />
          </view>
          <text class="text-[11px] text-[#64748B] font-medium">选择词书</text>
        </view>
        <view class="flex flex-col items-center rounded-xl bg-white py-4 shadow-sm active:scale-95" @click="startStudy">
          <view class="mb-2 h-10 w-10 flex items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669]">
            <view class="i-carbon-play-filled-alt text-[20px]" />
          </view>
          <text class="text-[11px] text-[#64748B] font-medium">快速学习</text>
        </view>
        <view class="flex flex-col items-center rounded-xl bg-white py-4 shadow-sm active:scale-95" @click="openCheckinCalendar">
          <view class="mb-2 h-10 w-10 flex items-center justify-center rounded-xl bg-[#FEF3C7] text-[#D97706]">
            <view class="i-carbon-calendar text-[20px]" />
          </view>
          <text class="text-[11px] text-[#64748B] font-medium">打卡记录</text>
        </view>
        <view class="flex flex-col items-center rounded-xl bg-white py-4 shadow-sm active:scale-95" @click="openSettings">
          <view class="mb-2 h-10 w-10 flex items-center justify-center rounded-xl bg-[#F5F3FF] text-[#8B5CF6]">
            <view class="i-carbon-settings text-[20px]" />
          </view>
          <text class="text-[11px] text-[#64748B] font-medium">学习设置</text>
        </view>
      </view>

      <!-- 学习建议 -->
      <view class="mt-4 rounded-xl bg-white p-4 shadow-sm">
        <view class="flex items-center gap-2">
          <view class="h-6 w-6 flex items-center justify-center rounded-lg bg-[#FEF3C7] text-[#D97706]">
            <view class="i-carbon-idea text-[14px]" />
          </view>
          <text class="text-[13px] text-[#475569] font-bold">学习小贴士</text>
        </view>
        <view class="mt-2.5 text-[12px] text-[#94A3B8] leading-relaxed">
          FSRS 算法会根据你的记忆表现智能安排复习时间，每天坚持学习效果最佳。建议先完成待复习的单词，再学习新词。
        </view>
      </view>
    </view>

    <LoginModal v-model="showLoginModal" @success="handleLoginSuccess" />
  </view>
</template>
