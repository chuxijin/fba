<script lang="ts" setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { api } from '@/api/sdk'
import { useTokenStore } from '@/store'

defineOptions({ name: 'VocabSettings' })
definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '学习设置',
  },
})

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const loading = ref(false)
const saving = ref(false)

const dailyNewTarget = ref(20)
const dailyReviewLimit = ref(200)
const autoPlayAudio = ref(false)
const preferPhonetic = ref<'us' | 'uk'>('us')

const dailyNewOptions = [5, 10, 15, 20, 30, 50]

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.navigateTo({ url: '/pages/vocab/index' })
}

async function loadSettings() {
  if (!tokenStore.hasLogin) return

  loading.value = true
  try {
    const result = await api.getSetting() as any
    const data = result?.data
    if (data) {
      dailyNewTarget.value = data.daily_new_target || 20
      dailyReviewLimit.value = data.daily_review_limit || 200
      autoPlayAudio.value = data.auto_play_audio || false
      preferPhonetic.value = data.prefer_phonetic || 'us'
    }
  }
  catch (err) {
    console.error('加载学习设置失败:', err)
  }
  finally {
    loading.value = false
  }
}

async function saveSetting(field: string, value: unknown) {
  if (saving.value) return
  saving.value = true
  try {
    await api.updateSetting({ body: { [field]: value } as any })
    uni.showToast({ title: '已保存', icon: 'none', duration: 1000 })
  }
  catch (err) {
    console.error('保存设置失败:', err)
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
  finally {
    saving.value = false
  }
}

function selectDailyNew() {
  uni.showActionSheet({
    itemList: dailyNewOptions.map(n => `每天 ${n} 个新词`),
    success: (res) => {
      const value = dailyNewOptions[res.tapIndex]
      dailyNewTarget.value = value
      void saveSetting('daily_new_target', value)
    },
  })
}

function selectReviewLimit() {
  const options = [50, 100, 150, 200, 300, 500]
  uni.showActionSheet({
    itemList: options.map(n => `每天最多复习 ${n} 个`),
    success: (res) => {
      const value = options[res.tapIndex]
      dailyReviewLimit.value = value
      void saveSetting('daily_review_limit', value)
    },
  })
}

function toggleAudio() {
  autoPlayAudio.value = !autoPlayAudio.value
  void saveSetting('auto_play_audio', autoPlayAudio.value)
}

function selectPhonetic() {
  uni.showActionSheet({
    itemList: ['美式发音', '英式发音'],
    success: (res) => {
      const value = res.tapIndex === 0 ? 'us' : 'uk'
      preferPhonetic.value = value
      void saveSetting('prefer_phonetic', value)
    },
  })
}

onShow(() => {
  tokenStore.updateNowTime()
  void loadSettings()
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
          学习设置
        </text>
      </view>
    </view>

    <view class="px-4 pb-8 pt-4">
      <!-- 学习计划 -->
      <view class="rounded-2xl bg-white shadow-sm">
        <view class="px-4 pb-1 pt-4 text-[13px] text-[#94A3B8] font-medium">
          学习计划
        </view>

        <view class="flex items-center justify-between px-4 py-3.5 active:bg-[#F8FAFC]" @click="selectDailyNew">
          <view class="flex items-center gap-3">
            <view class="h-9 w-9 flex items-center justify-center rounded-xl bg-[#EEF2FF] text-[#4F46E5]">
              <view class="i-carbon-add-filled text-[18px]" />
            </view>
            <view>
              <view class="text-[14px] text-[#1E293B] font-medium">
                每日新词目标
              </view>
              <view class="mt-0.5 text-[11px] text-[#94A3B8]">
                建议初学者从 10-15 个开始
              </view>
            </view>
          </view>
          <view class="flex items-center gap-1">
            <text class="text-[14px] text-[#6366F1] font-bold">{{ dailyNewTarget }}</text>
            <view class="i-carbon-chevron-right text-[16px] text-[#CBD5E1]" />
          </view>
        </view>

        <view class="mx-4 h-px bg-[#F1F5F9]" />

        <view class="flex items-center justify-between px-4 py-3.5 active:bg-[#F8FAFC]" @click="selectReviewLimit">
          <view class="flex items-center gap-3">
            <view class="h-9 w-9 flex items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669]">
              <view class="i-carbon-renew text-[18px]" />
            </view>
            <view>
              <view class="text-[14px] text-[#1E293B] font-medium">
                每日复习上限
              </view>
              <view class="mt-0.5 text-[11px] text-[#94A3B8]">
                防止一次复习量过大
              </view>
            </view>
          </view>
          <view class="flex items-center gap-1">
            <text class="text-[14px] text-[#059669] font-bold">{{ dailyReviewLimit }}</text>
            <view class="i-carbon-chevron-right text-[16px] text-[#CBD5E1]" />
          </view>
        </view>
      </view>

      <!-- 发音设置 -->
      <view class="mt-4 rounded-2xl bg-white shadow-sm">
        <view class="px-4 pb-1 pt-4 text-[13px] text-[#94A3B8] font-medium">
          发音设置
        </view>

        <view class="flex items-center justify-between px-4 py-3.5 active:bg-[#F8FAFC]" @click="toggleAudio">
          <view class="flex items-center gap-3">
            <view class="h-9 w-9 flex items-center justify-center rounded-xl bg-[#FEF3C7] text-[#D97706]">
              <view class="i-carbon-volume-up text-[18px]" />
            </view>
            <view>
              <view class="text-[14px] text-[#1E293B] font-medium">
                自动播放发音
              </view>
              <view class="mt-0.5 text-[11px] text-[#94A3B8]">
                翻看单词时自动朗读
              </view>
            </view>
          </view>
          <switch
            :checked="autoPlayAudio"
            color="#6366F1"
            style="transform: scale(0.8);"
            @change="toggleAudio"
          />
        </view>

        <view class="mx-4 h-px bg-[#F1F5F9]" />

        <view class="flex items-center justify-between px-4 py-3.5 active:bg-[#F8FAFC]" @click="selectPhonetic">
          <view class="flex items-center gap-3">
            <view class="h-9 w-9 flex items-center justify-center rounded-xl bg-[#F5F3FF] text-[#8B5CF6]">
              <view class="i-carbon-language text-[18px]" />
            </view>
            <view>
              <view class="text-[14px] text-[#1E293B] font-medium">
                音标偏好
              </view>
              <view class="mt-0.5 text-[11px] text-[#94A3B8]">
                选择默认展示的音标体系
              </view>
            </view>
          </view>
          <view class="flex items-center gap-1">
            <text class="text-[14px] text-[#8B5CF6] font-bold">{{ preferPhonetic === 'us' ? '美式' : '英式' }}</text>
            <view class="i-carbon-chevron-right text-[16px] text-[#CBD5E1]" />
          </view>
        </view>
      </view>

      <!-- 关于 FSRS -->
      <view class="mt-4 rounded-2xl bg-white p-4 shadow-sm">
        <view class="flex items-center gap-2">
          <view class="h-6 w-6 flex items-center justify-center rounded-lg bg-[#EEF2FF] text-[#6366F1]">
            <view class="i-carbon-machine-learning text-[14px]" />
          </view>
          <text class="text-[13px] text-[#475569] font-bold">关于 FSRS 算法</text>
        </view>
        <view class="mt-2 text-[12px] text-[#94A3B8] leading-relaxed">
          FSRS (Free Spaced Repetition Scheduler) 是新一代间隔重复算法，相比传统 SM-2 算法，能更精准地预测你的记忆状态，在最佳时间点安排复习，让你花更少时间记住更多单词。
        </view>
      </view>
    </view>
  </view>
</template>
