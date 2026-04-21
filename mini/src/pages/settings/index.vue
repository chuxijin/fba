<script lang="ts" setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { fbaApi } from '@/api/sdk'
import { useTokenStore, useUserStore } from '@/store'
import { getAppSettings, saveAppSettings } from '@/utils/appSettings'
import { clearQuestionMediaCache, getQuestionMediaCacheSummary } from '@/utils/questionMediaCache'
import { mergeCachedStudyPreference } from '@/utils/studyPreferenceCache'
import { toLoginPage } from '@/utils/toLoginPage'

defineOptions({
  name: 'SettingsPage',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '设置',
  },
})

const randomCountOptions = [10, 20, 30, 50, 100]
const randomYearRangeOptions = [
  { label: '不限', value: 'unlimited' },
  { label: '近3年', value: 'last_3_years' },
  { label: '近5年', value: 'last_5_years' },
] as const
const practiceModeOptions = [
  { value: 'practice', label: '刷题模式', tip: '做完一题看一题解析' },
  { value: 'exam', label: '考试模式', tip: '整套做完后统一交卷' },
  { value: 'memorize', label: '背题模式', tip: '答案解析默认可见' },
] as const
const masteryStreakOptions = [1, 2, 3, 5]

type PracticeMode = (typeof practiceModeOptions)[number]['value']
type RandomYearRange = (typeof randomYearRangeOptions)[number]['value']

const tokenStore = useTokenStore()
const userStore = useUserStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const randomPracticeCount = ref(20)
const randomPracticeYearRange = ref<RandomYearRange>('unlimited')
const darkThemeEnabled = ref(false)
const practiceMode = ref<PracticeMode>('practice')
const wrongMasteryStreak = ref(3)
const mediaCacheCount = ref(0)
const mediaCacheSize = ref(0)
const clearingMediaCache = ref(false)

const themeLabel = computed(() => darkThemeEnabled.value ? '暗色' : '明亮')
const randomPracticeCountLabel = computed(() => `${randomPracticeCount.value} 题`)
const randomPracticeYearRangeLabel = computed(() => {
  return randomYearRangeOptions.find(item => item.value === randomPracticeYearRange.value)?.label || '不限'
})
const practiceModeLabel = computed(() => practiceModeOptions.find(item => item.value === practiceMode.value)?.label || '刷题模式')
const masteryStreakLabel = computed(() => `连对 ${wrongMasteryStreak.value} 次`)
const mediaCacheSummaryLabel = computed(() => `${mediaCacheCount.value} 个文件 · ${formatCacheSize(mediaCacheSize.value)}`)

function loadSettings() {
  const settings = getAppSettings()
  randomPracticeCount.value = settings.randomPracticeCount
  randomPracticeYearRange.value = settings.randomPracticeYearRange as RandomYearRange
  darkThemeEnabled.value = settings.themeMode === 'dark'
  practiceMode.value = settings.practiceMode
  wrongMasteryStreak.value = settings.wrongMasteryStreak
  const summary = getQuestionMediaCacheSummary()
  mediaCacheCount.value = summary.count
  mediaCacheSize.value = summary.totalSize
}

function formatCacheSize(size: number) {
  if (size <= 0)
    return '0 KB'
  if (size < 1024 * 1024)
    return `${(size / 1024).toFixed(1).replace(/\.0$/, '')} KB`
  return `${(size / 1024 / 1024).toFixed(2).replace(/\.?0+$/, '')} MB`
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }

  uni.switchTab({ url: '/pages/mine/index' })
}

function openMyRenderBooks() {
  tokenStore.updateNowTime()
  if (!tokenStore.hasLogin) {
    uni.showToast({ title: '请先登录后查看我的题本', icon: 'none' })
    setTimeout(() => {
      toLoginPage()
    }, 300)
    return
  }

  uni.navigateTo({ url: '/pages/my-render-books/index' })
}

function updateRandomPracticeCount(count: number) {
  randomPracticeCount.value = count
  saveAppSettings({ randomPracticeCount: count })
  uni.showToast({ title: `已设为 ${count} 题`, icon: 'none' })
}

function chooseRandomPracticeCount() {
  uni.showActionSheet({
    itemList: randomCountOptions.map(count => `${count} 题`),
    success: (res) => {
      const count = randomCountOptions[Number(res.tapIndex)]
      if (count)
        updateRandomPracticeCount(count)
    },
  })
}

function updateRandomPracticeYearRange(range: RandomYearRange) {
  randomPracticeYearRange.value = range
  saveAppSettings({ randomPracticeYearRange: range })
  uni.showToast({ title: `已设为 ${randomPracticeYearRangeLabel.value}`, icon: 'none' })
}

function chooseRandomPracticeYearRange() {
  uni.showActionSheet({
    itemList: randomYearRangeOptions.map(item => item.label),
    success: (res) => {
      const picked = randomYearRangeOptions[Number(res.tapIndex)]?.value
      if (picked) {
        updateRandomPracticeYearRange(picked)
      }
    },
  })
}

async function updatePracticeMode(nextMode: PracticeMode) {
  practiceMode.value = nextMode
  saveAppSettings({ practiceMode: nextMode })

  if (tokenStore.updateNowTime().hasLogin) {
    try {
      await fbaApi.qbank.settings.updateStudyPreference({
        practice_mode: nextMode,
      } as any)
      mergeCachedStudyPreference(Number(userStore.userInfo?.id || 0), {
        practice_mode: nextMode,
      })
    }
    catch (error) {
      console.error('保存默认刷题模式失败:', error)
    }
  }

  uni.showToast({ title: `已切换为${practiceModeLabel.value}`, icon: 'none' })
}

function choosePracticeMode() {
  uni.showActionSheet({
    itemList: practiceModeOptions.map(item => `${item.label} · ${item.tip}`),
    success: async (res) => {
      const nextMode = practiceModeOptions[Number(res.tapIndex)]?.value
      if (nextMode) {
        await updatePracticeMode(nextMode)
      }
    },
  })
}

function chooseMasteryStreak() {
  uni.showActionSheet({
    itemList: masteryStreakOptions.map(n => `连续答对 ${n} 次`),
    success: async (res) => {
      const streak = masteryStreakOptions[Number(res.tapIndex)]
      if (streak) {
        wrongMasteryStreak.value = streak
        saveAppSettings({ wrongMasteryStreak: streak })

        if (tokenStore.updateNowTime().hasLogin) {
          try {
            await fbaApi.qbank.settings.updateStudyPreference({
              mastery_threshold: streak,
            } as any)
            mergeCachedStudyPreference(Number(userStore.userInfo?.id || 0), {
              mastery_threshold: streak,
            })
          }
          catch (error) {
            console.error('保存错题掌握阈值失败:', error)
          }
        }

        uni.showToast({ title: `已设为连对 ${streak} 次`, icon: 'none' })
      }
    },
  })
}

function handleThemeChange(event: { value: boolean }) {
  const nextValue = Boolean(event?.value)
  darkThemeEnabled.value = nextValue
  saveAppSettings({ themeMode: nextValue ? 'dark' : 'light' })
  uni.showToast({ title: nextValue ? '已切换暗色主题' : '已切换明亮主题', icon: 'none' })
}

async function handleClearMediaCache() {
  if (clearingMediaCache.value)
    return

  const confirmed = await new Promise<boolean>((resolve) => {
    uni.showModal({
      title: '清空题目缓存',
      content: '会删除题目里的图片和视频本地缓存，下次打开会重新下载，确认继续吗？',
      confirmText: '清空',
      confirmColor: '#DC2626',
      cancelText: '取消',
      success: res => resolve(Boolean(res.confirm)),
      fail: () => resolve(false),
    })
  })

  if (!confirmed)
    return

  clearingMediaCache.value = true
  try {
    await clearQuestionMediaCache()
    const summary = getQuestionMediaCacheSummary()
    mediaCacheCount.value = summary.count
    mediaCacheSize.value = summary.totalSize
    uni.showToast({ title: '题目缓存已清空', icon: 'success' })
  }
  catch (error) {
    console.error('清空题目缓存失败:', error)
    uni.showToast({ title: '清空题目缓存失败', icon: 'none' })
  }
  finally {
    clearingMediaCache.value = false
  }
}

function handleOpenProtocol(name: string) {
  uni.showToast({ title: `${name} 系统接入中...`, icon: 'none' })
}

onShow(() => {
  loadSettings()
})
</script>

<template>
  <view class="relative min-h-screen overflow-hidden from-[#F3E8FF] via-[#F8F5FB] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="pointer-events-none absolute h-80 w-80 rounded-full bg-[#E9D5FF]/40 blur-[40px] -right-8 -top-12" />
    <view class="pointer-events-none absolute top-20 h-60 w-60 rounded-full bg-[#FBCFE8]/20 blur-[40px] -left-16" />

    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="h-11 flex items-center justify-between px-4">
        <view class="w-20 flex items-center active:opacity-60" @tap="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">设置</text>
        <view class="w-20" />
      </view>
    </view>

    <view class="relative z-10 mt-6 px-4 pb-24 space-y-4">
      <view class="overflow-hidden border border-white/60 rounded-2xl bg-white/80 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="h-14 flex items-center justify-between px-4 active:opacity-80" @tap="openMyRenderBooks">
          <view class="flex items-center gap-2">
            <view class="i-carbon-book text-[18px] text-[#EA580C]" />
            <text class="text-[15px] text-[#1E293B] font-bold">我的题本</text>
          </view>
          <view class="flex items-center text-[#64748B]">
            <text class="text-[14px]">查看导出记录</text>
            <view class="i-carbon-chevron-right ml-1 text-lg" />
          </view>
        </view>
      </view>

      <view class="overflow-hidden border border-white/60 rounded-2xl bg-white/80 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="h-14 flex items-center justify-between px-4 active:opacity-80" @tap="chooseRandomPracticeCount">
          <text class="text-[15px] text-[#1E293B] font-bold">随机练习题目数</text>
          <view class="flex items-center text-[#64748B]">
            <text class="text-[14px]">{{ randomPracticeCountLabel }}</text>
            <view class="i-carbon-chevron-right ml-1 text-lg" />
          </view>
        </view>

        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4 active:opacity-80" @tap="chooseRandomPracticeYearRange">
          <text class="text-[15px] text-[#1E293B] font-bold">随机练习范围</text>
          <view class="flex items-center text-[#64748B]">
            <text class="text-[14px]">{{ randomPracticeYearRangeLabel }}</text>
            <view class="i-carbon-chevron-right ml-1 text-lg" />
          </view>
        </view>

        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4 active:opacity-80" @tap="choosePracticeMode">
          <text class="text-[15px] text-[#1E293B] font-bold">默认刷题模式</text>
          <view class="flex items-center text-[#64748B]">
            <text class="text-[14px]">{{ practiceModeLabel }}</text>
            <view class="i-carbon-chevron-right ml-1 text-lg" />
          </view>
        </view>

        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4 active:opacity-80" @tap="chooseMasteryStreak">
          <text class="text-[15px] text-[#1E293B] font-bold">错题掌握连对次数</text>
          <view class="flex items-center text-[#64748B]">
            <text class="text-[14px]">{{ masteryStreakLabel }}</text>
            <view class="i-carbon-chevron-right ml-1 text-lg" />
          </view>
        </view>

        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4">
          <text class="text-[15px] text-[#1E293B] font-bold">明暗主题</text>
          <view class="flex items-center gap-3">
            <text class="text-[14px] text-[#64748B]">{{ themeLabel }}</text>
            <wd-switch
              v-model="darkThemeEnabled"
              size="28px"
              active-color="#10B981"
              inactive-color="#E5E7EB"
              @change="handleThemeChange"
            />
          </view>
        </view>
      </view>

      <view class="overflow-hidden border border-white/60 rounded-2xl bg-white/80 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="h-14 flex items-center justify-between px-4">
          <text class="text-[15px] text-[#1E293B] font-bold">题目资源缓存</text>
          <text class="text-[14px] text-[#64748B]">{{ mediaCacheSummaryLabel }}</text>
        </view>

        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4 active:opacity-80" @tap="handleClearMediaCache">
          <text class="text-[15px] text-[#1E293B] font-bold">清空题目缓存</text>
          <view class="flex items-center text-[#64748B]">
            <text class="text-[14px] text-[#DC2626]">{{ clearingMediaCache ? '清理中...' : '立即清空' }}</text>
            <view class="i-carbon-chevron-right ml-1 text-lg" />
          </view>
        </view>
      </view>

      <!-- 协议与清单 -->
      <view class="overflow-hidden border border-white/60 rounded-2xl bg-white/80 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.04)] backdrop-blur-md">
        <view class="bg-[#F8FAFC]/50 px-4 pt-4 pb-2 border-b border-transparent">
          <text class="text-[12px] text-[#94A3B8] font-bold">协议与清单</text>
        </view>

        <view class="h-14 flex items-center justify-between px-4 active:opacity-80" @tap="handleOpenProtocol('用户协议')">
          <text class="text-[15px] text-[#1E293B] font-bold">用户协议</text>
          <view class="i-carbon-chevron-right text-lg text-[#64748B]" />
        </view>

        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4 active:opacity-80" @tap="handleOpenProtocol('隐私政策')">
          <text class="text-[15px] text-[#1E293B] font-bold">隐私政策</text>
          <view class="i-carbon-chevron-right text-lg text-[#64748B]" />
        </view>
        
        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4 active:opacity-80" @tap="handleOpenProtocol('个人信息收集清单')">
          <text class="text-[15px] text-[#1E293B] font-bold">个人信息收集清单</text>
          <view class="i-carbon-chevron-right text-lg text-[#64748B]" />
        </view>

        <view class="ml-4 h-[1px] bg-[#F1E8FB]" />

        <view class="h-14 flex items-center justify-between px-4 active:opacity-80" @tap="handleOpenProtocol('第三方信息数据共享')">
          <text class="text-[15px] text-[#1E293B] font-bold">第三方信息数据共享</text>
          <view class="i-carbon-chevron-right text-lg text-[#64748B]" />
        </view>
      </view>

      <view class="px-1">
        <view class="text-[12px] leading-[1.8] text-[#94A3B8]">
          随机练习题目数与范围会用于知识点刷题的默认出题数量与年份筛选。
        </view>
        <view class="mt-1 text-[12px] leading-[1.8] text-[#94A3B8]">
          默认刷题模式会影响首页开始刷题时的判题和解析展示方式。
        </view>
        <view class="mt-1 text-[12px] leading-[1.8] text-[#94A3B8]">
          错题掌握连对次数决定错题连续做对几次后自动标记为已掌握。
        </view>
        <view class="mt-1 text-[12px] leading-[1.8] text-[#94A3B8]">
          题目缓存会保存刷题页里已经加载过的图片和视频资源，减少重复回源。
        </view>
      </view>
    </view>
  </view>
</template>
