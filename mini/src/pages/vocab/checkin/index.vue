<script lang="ts" setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { api } from '@/api/sdk'
import { useTokenStore } from '@/store'

defineOptions({ name: 'VocabCheckin' })
definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '打卡记录',
  },
})

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const loading = ref(false)
const streakInfo = ref<any>(null)
const checkinList = ref<any[]>([])

const now = new Date()
const currentYear = ref(now.getFullYear())
const currentMonth = ref(now.getMonth() + 1)

const currentStreak = computed(() => streakInfo.value?.current_streak || 0)
const totalCheckins = computed(() => streakInfo.value?.total_checkins || 0)

const monthLabel = computed(() => `${currentYear.value}年${currentMonth.value}月`)

// 生成日历网格
const calendarDays = computed(() => {
  const year = currentYear.value
  const month = currentMonth.value
  const firstDay = new Date(year, month - 1, 1)
  const lastDay = new Date(year, month, 0)
  const startDayOfWeek = firstDay.getDay() // 0=日 1=一 ...
  const daysInMonth = lastDay.getDate()

  // 打卡日期集合
  const checkedDates = new Set(
    checkinList.value
      .filter(c => c.streak_days > 0)
      .map(c => {
        const d = new Date(c.checkin_date)
        return d.getDate()
      }),
  )

  const days: Array<{ day: number; isChecked: boolean; isToday: boolean; isEmpty: boolean }> = []

  // 填充空白
  for (let i = 0; i < startDayOfWeek; i++) {
    days.push({ day: 0, isChecked: false, isToday: false, isEmpty: true })
  }

  const today = new Date()
  const isCurrentMonth = year === today.getFullYear() && month === today.getMonth() + 1

  for (let d = 1; d <= daysInMonth; d++) {
    days.push({
      day: d,
      isChecked: checkedDates.has(d),
      isToday: isCurrentMonth && d === today.getDate(),
      isEmpty: false,
    })
  }

  return days
})

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.navigateTo({ url: '/pages/vocab/index' })
}

function prevMonth() {
  if (currentMonth.value === 1) {
    currentMonth.value = 12
    currentYear.value--
  }
  else {
    currentMonth.value--
  }
  void loadHistory()
}

function nextMonth() {
  const now = new Date()
  if (currentYear.value >= now.getFullYear() && currentMonth.value >= now.getMonth() + 1) return
  if (currentMonth.value === 12) {
    currentMonth.value = 1
    currentYear.value++
  }
  else {
    currentMonth.value++
  }
  void loadHistory()
}

async function loadHistory() {
  if (!tokenStore.hasLogin) return

  loading.value = true
  try {
    const [streakResult, historyResult] = await Promise.allSettled([
      api.getStreakInfo(),
      api.getCheckinHistory({
        query: {
          year: currentYear.value,
          month: currentMonth.value,
          page: 1,
          size: 31,
        },
      }),
    ])

    if (streakResult.status === 'fulfilled') {
      streakInfo.value = (streakResult.value as any)?.data
    }

    if (historyResult.status === 'fulfilled') {
      const data = (historyResult.value as any)?.data
      checkinList.value = data?.items || []
    }
  }
  catch (err) {
    console.error('加载打卡记录失败:', err)
  }
  finally {
    loading.value = false
  }
}

onShow(() => {
  tokenStore.updateNowTime()
  void loadHistory()
})
</script>

<template>
  <view class="min-h-screen bg-[#F6F8FA] text-[#111827]">
    <view class="relative z-10 w-full bg-[#F6F8FA]" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view
          class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white text-[#475569] shadow-sm active:scale-95"
          @click="goBack"
        >
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="text-lg font-bold tracking-widest">
          打卡记录
        </text>
      </view>
    </view>

    <view class="px-4 pb-8 pt-4">
      <!-- 打卡概览 -->
      <view class="overflow-hidden rounded-2xl bg-gradient-to-br from-[#F59E0B] to-[#D97706] p-5 text-white shadow-lg">
        <view class="flex items-center justify-between">
          <view>
            <view class="text-[13px] text-white/60">
              连续打卡
            </view>
            <view class="mt-1 flex items-baseline gap-1">
              <text class="text-[36px] font-black leading-none">{{ currentStreak }}</text>
              <text class="text-[14px] text-white/70">天</text>
            </view>
          </view>
          <view class="flex flex-col items-center rounded-xl bg-white/15 px-5 py-3 backdrop-blur-sm">
            <view class="text-[22px] font-black">
              {{ totalCheckins }}
            </view>
            <view class="text-[10px] text-white/60">
              累计打卡
            </view>
          </view>
        </view>
      </view>

      <!-- 日历 -->
      <view class="mt-4 rounded-2xl bg-white p-4 shadow-sm">
        <!-- 月份切换 -->
        <view class="mb-4 flex items-center justify-between">
          <view class="h-8 w-8 flex items-center justify-center rounded-full bg-[#F1F5F9] active:bg-[#E2E8F0]" @click="prevMonth">
            <view class="i-carbon-chevron-left text-[16px] text-[#475569]" />
          </view>
          <text class="text-[15px] text-[#1E293B] font-bold">{{ monthLabel }}</text>
          <view class="h-8 w-8 flex items-center justify-center rounded-full bg-[#F1F5F9] active:bg-[#E2E8F0]" @click="nextMonth">
            <view class="i-carbon-chevron-right text-[16px] text-[#475569]" />
          </view>
        </view>

        <!-- 星期头 -->
        <view class="mb-2 grid grid-cols-7 text-center text-[11px] text-[#94A3B8] font-medium">
          <text>日</text>
          <text>一</text>
          <text>二</text>
          <text>三</text>
          <text>四</text>
          <text>五</text>
          <text>六</text>
        </view>

        <!-- 日期格 -->
        <view class="grid grid-cols-7 gap-y-1.5">
          <view
            v-for="(day, index) in calendarDays"
            :key="index"
            class="flex items-center justify-center"
          >
            <view
              v-if="!day.isEmpty"
              class="h-9 w-9 flex items-center justify-center rounded-full text-[13px] font-medium"
              :class="[
                day.isChecked ? 'bg-[#059669] text-white font-bold' : '',
                day.isToday && !day.isChecked ? 'ring-2 ring-[#6366F1] text-[#6366F1] font-bold' : '',
                !day.isChecked && !day.isToday ? 'text-[#475569]' : '',
              ]"
            >
              {{ day.day }}
            </view>
          </view>
        </view>
      </view>

      <!-- 本月明细 -->
      <view v-if="checkinList.length > 0" class="mt-4 rounded-2xl bg-white p-4 shadow-sm">
        <view class="mb-3 text-[13px] text-[#475569] font-bold">
          本月学习明细
        </view>
        <view class="flex flex-col gap-2.5">
          <view
            v-for="record in checkinList.filter(c => c.streak_days > 0).slice(0, 10)"
            :key="record.id"
            class="flex items-center justify-between rounded-lg bg-[#F8FAFC] px-3 py-2.5"
          >
            <view class="flex items-center gap-2">
              <view class="h-6 w-6 flex items-center justify-center rounded-full bg-[#ECFDF5] text-[#059669]">
                <view class="i-carbon-checkmark text-[12px]" />
              </view>
              <text class="text-[13px] text-[#475569]">{{ record.checkin_date }}</text>
            </view>
            <view class="flex items-center gap-3 text-[11px] text-[#94A3B8]">
              <text>新词 {{ record.new_words }}</text>
              <text>复习 {{ record.review_words }}</text>
              <text>{{ Math.floor((record.duration_seconds || 0) / 60) }}分钟</text>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>
