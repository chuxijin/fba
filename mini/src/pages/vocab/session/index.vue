<script lang="ts" setup>
import { computed, reactive, ref } from 'vue'
import { onHide, onShow } from '@dcloudio/uni-app'
import { api } from '@/api/sdk'
import { useTokenStore } from '@/store'

defineOptions({ name: 'VocabSession' })
definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '学习中',
  },
})

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

type CardPhase = 'front' | 'back'
type Rating = 1 | 2 | 3 | 4
interface StudyWord {
  word_id: number
  word: string
  phonetic_us?: string
  phonetic_uk?: string
  definitions: Array<{ part_of_speech?: string; meaning: string }>
  examples: Array<{ sentence_en: string; sentence_zh?: string }>
  is_new?: boolean
  is_starred?: boolean
}

const loading = ref(false)
const submitting = ref(false)
const phase = ref<CardPhase>('front')
const currentIndex = ref(0)
const wordQueue = ref<StudyWord[]>([])
const startedAt = ref(Date.now())

// 会话统计
const sessionStats = reactive({
  newCount: 0,
  reviewCount: 0,
  correctCount: 0,
  totalCount: 0,
})

const currentWord = computed(() => wordQueue.value[currentIndex.value] || null)
const isFinished = computed(() => wordQueue.value.length > 0 && currentIndex.value >= wordQueue.value.length)
const progress = computed(() => {
  if (wordQueue.value.length === 0) return 0
  return Math.round((currentIndex.value / wordQueue.value.length) * 100)
})
const durationMinutes = computed(() => Math.max(1, Math.round((Date.now() - startedAt.value) / 60000)))

const ratingOptions: Array<{ rating: Rating; label: string; sub: string; color: string; bg: string }> = [
  { rating: 1, label: '忘了', sub: '重新学习', color: 'text-[#EF4444]', bg: 'bg-[#FEF2F2]' },
  { rating: 2, label: '模糊', sub: '稍后复习', color: 'text-[#F59E0B]', bg: 'bg-[#FFFBEB]' },
  { rating: 3, label: '记得', sub: '正常间隔', color: 'text-[#059669]', bg: 'bg-[#ECFDF5]' },
  { rating: 4, label: '简单', sub: '延长间隔', color: 'text-[#3B82F6]', bg: 'bg-[#EFF6FF]' },
]

function goBack() {
  if (sessionStats.totalCount > 0) {
    uni.showModal({
      title: '结束学习？',
      content: `本次已学 ${sessionStats.totalCount} 个单词，退出后进度已保存。`,
      confirmText: '退出',
      cancelText: '继续',
      success: (res) => {
        if (res.confirm) uni.navigateBack()
      },
    })
    return
  }
  uni.navigateBack()
}

function showFront() {
  phase.value = 'front'
}

function revealAnswer() {
  phase.value = 'back'
}

async function submitRating(rating: Rating) {
  if (!currentWord.value || submitting.value) return

  submitting.value = true
  try {
    const elapsed = Date.now() - startedAt.value
    await api.submitReview({
      body: {
        word_id: currentWord.value.word_id,
        rating,
        duration_ms: Math.min(elapsed, 60000),
      },
    })

    sessionStats.totalCount++
    if (currentWord.value.is_new) {
      sessionStats.newCount++
    }
    else {
      sessionStats.reviewCount++
    }
    if (rating >= 3) {
      sessionStats.correctCount++
    }

    // 如果评分是"忘了"，把当前单词移到队列后面再来一次
    if (rating === 1 && currentIndex.value < wordQueue.value.length) {
      const word = { ...currentWord.value, is_new: false }
      wordQueue.value.push(word)
    }

    currentIndex.value++
    phase.value = 'front'
    startedAt.value = Date.now()
  }
  catch (err) {
    console.error('提交复习失败:', err)
    uni.showToast({ title: '提交失败', icon: 'none' })
  }
  finally {
    submitting.value = false
  }
}

async function toggleStar() {
  if (!currentWord.value) return
  const newState = !currentWord.value.is_starred
  currentWord.value.is_starred = newState
  try {
    await api.toggleStar({
      body: {
        word_id: currentWord.value.word_id,
        is_starred: newState,
      },
    })
  }
  catch {
    currentWord.value.is_starred = !newState
  }
}

function finishAndReturn() {
  uni.navigateBack()
}

async function loadSession() {
  if (!tokenStore.hasLogin) return

  loading.value = true
  try {
    const result = await api.getStudySession() as any
    const data = result?.data
    wordQueue.value = (data?.words || []).map((w: any) => ({
      word_id: w.word_id || w.id,
      word: w.word,
      phonetic_us: w.phonetic_us,
      phonetic_uk: w.phonetic_uk,
      definitions: w.definitions || [],
      examples: w.examples || [],
      is_new: w.is_new ?? true,
      is_starred: w.is_starred ?? false,
    }))
    currentIndex.value = 0
    phase.value = 'front'
    startedAt.value = Date.now()
  }
  catch (err) {
    console.error('加载学习会话失败:', err)
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

onShow(() => {
  tokenStore.updateNowTime()
  if (wordQueue.value.length === 0) {
    void loadSession()
  }
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
        <text class="text-[15px] text-[#475569] font-medium">
          {{ currentIndex + 1 }} / {{ wordQueue.length }}
        </text>
        <view class="absolute right-4 flex items-center gap-2">
          <view
            v-if="currentWord"
            class="h-8 w-8 flex items-center justify-center rounded-full bg-white shadow-sm active:scale-95"
            @click="toggleStar"
          >
            <view
              class="text-lg"
              :class="currentWord.is_starred ? 'i-carbon-star-filled text-[#F59E0B]' : 'i-carbon-star text-[#94A3B8]'"
            />
          </view>
        </view>
      </view>
    </view>

    <!-- 进度条 -->
    <view class="mx-4 mt-1 h-1.5 overflow-hidden rounded-full bg-[#E2E8F0]">
      <view
        class="h-full rounded-full bg-gradient-to-r from-[#6366F1] to-[#8B5CF6] transition-all duration-300"
        :style="{ width: `${progress}%` }"
      />
    </view>

    <!-- Loading -->
    <view v-if="loading" class="flex-1 flex items-center justify-center pt-32">
      <view class="flex flex-col items-center gap-3">
        <view class="h-10 w-10 animate-spin rounded-full border-3 border-[#E2E8F0] border-t-[#6366F1]" />
        <text class="text-[13px] text-[#94A3B8]">正在加载学习任务...</text>
      </view>
    </view>

    <!-- 空状态 -->
    <view v-else-if="wordQueue.length === 0 && !loading" class="px-4 pt-20">
      <view class="rounded-2xl bg-white px-6 py-12 text-center shadow-sm">
        <view class="mx-auto mb-4 h-16 w-16 flex items-center justify-center rounded-2xl bg-[#ECFDF5] text-[#059669]">
          <view class="i-carbon-checkmark-filled text-[32px]" />
        </view>
        <view class="text-[18px] text-[#1E293B] font-bold">
          暂无学习任务
        </view>
        <view class="mt-2 text-[13px] text-[#94A3B8] leading-relaxed">
          请先选择一本词书开始学习，<br>或等待已有词书的复习时间到来。
        </view>
        <view
          class="mx-auto mt-6 inline-flex rounded-xl bg-[#6366F1] px-6 py-3 text-[14px] text-white font-bold active:scale-95"
          @click="uni.navigateTo({ url: '/pages/vocab/books/index' })"
        >
          选择词书
        </view>
      </view>
    </view>

    <!-- 完成状态 -->
    <view v-else-if="isFinished" class="px-4 pt-10">
      <view class="overflow-hidden rounded-2xl bg-gradient-to-br from-[#059669] to-[#10B981] p-6 text-white shadow-lg">
        <view class="text-center">
          <view class="text-[40px]">
            🎉
          </view>
          <view class="mt-2 text-[22px] font-black">
            本次学习完成！
          </view>
          <view class="mt-1 text-[13px] text-white/70">
            坚持就是胜利，明天继续加油
          </view>
        </view>
        <view class="mt-6 grid grid-cols-3 gap-3">
          <view class="rounded-xl bg-white/15 py-3 text-center backdrop-blur-sm">
            <view class="text-[24px] font-black">
              {{ sessionStats.newCount }}
            </view>
            <view class="text-[10px] text-white/60">
              新词
            </view>
          </view>
          <view class="rounded-xl bg-white/15 py-3 text-center backdrop-blur-sm">
            <view class="text-[24px] font-black">
              {{ sessionStats.reviewCount }}
            </view>
            <view class="text-[10px] text-white/60">
              复习
            </view>
          </view>
          <view class="rounded-xl bg-white/15 py-3 text-center backdrop-blur-sm">
            <view class="text-[24px] font-black">
              {{ durationMinutes }}
            </view>
            <view class="text-[10px] text-white/60">
              分钟
            </view>
          </view>
        </view>
      </view>

      <view
        class="mt-4 rounded-xl bg-white py-4 text-center text-[15px] text-[#475569] font-bold shadow-sm active:scale-[0.98]"
        @click="finishAndReturn"
      >
        返回首页
      </view>
    </view>

    <!-- 单词卡片 -->
    <view v-else-if="currentWord" class="px-4 pt-6">
      <!-- 标签 -->
      <view class="mb-3 flex items-center gap-2">
        <view
          v-if="currentWord.is_new"
          class="rounded-md bg-[#EEF2FF] px-2 py-0.5 text-[10px] text-[#4F46E5] font-bold"
        >
          新词
        </view>
        <view
          v-else
          class="rounded-md bg-[#FEF3C7] px-2 py-0.5 text-[10px] text-[#D97706] font-bold"
        >
          复习
        </view>
      </view>

      <!-- 卡片正面 -->
      <view class="overflow-hidden rounded-2xl bg-white shadow-[0_4px_24px_-8px_rgba(0,0,0,0.08)]">
        <!-- 单词区域 -->
        <view class="px-6 pb-4 pt-8 text-center">
          <view class="text-[32px] text-[#1E293B] font-black tracking-wide">
            {{ currentWord.word }}
          </view>
          <view v-if="currentWord.phonetic_us || currentWord.phonetic_uk" class="mt-2 flex items-center justify-center gap-4 text-[12px] text-[#94A3B8]">
            <view v-if="currentWord.phonetic_us" class="flex items-center gap-1">
              <text>美</text>
              <text class="text-[#64748B]">{{ currentWord.phonetic_us }}</text>
            </view>
            <view v-if="currentWord.phonetic_uk" class="flex items-center gap-1">
              <text>英</text>
              <text class="text-[#64748B]">{{ currentWord.phonetic_uk }}</text>
            </view>
          </view>
        </view>

        <!-- 点击显示释义 -->
        <view v-if="phase === 'front'" class="px-6 pb-8">
          <view
            class="mx-auto flex items-center justify-center gap-2 rounded-xl bg-[#F1F5F9] py-10 text-[#94A3B8] active:bg-[#E2E8F0]"
            @click="revealAnswer"
          >
            <view class="i-carbon-view text-[20px]" />
            <text class="text-[14px] font-medium">点击查看释义</text>
          </view>
        </view>

        <!-- 卡片背面 - 释义 + 例句 -->
        <view v-else class="px-6 pb-6">
          <!-- 释义列表 -->
          <view class="border-t border-[#F1F5F9] pt-4">
            <view
              v-for="(def, di) in currentWord.definitions"
              :key="di"
              class="mb-2.5 flex items-start gap-2"
            >
              <view v-if="def.part_of_speech" class="mt-0.5 shrink-0 rounded bg-[#EEF2FF] px-1.5 py-0.5 text-[10px] text-[#4F46E5] font-bold">
                {{ def.part_of_speech }}
              </view>
              <text class="text-[15px] text-[#334155] leading-relaxed">{{ def.meaning }}</text>
            </view>
          </view>

          <!-- 例句 -->
          <view v-if="currentWord.examples.length > 0" class="mt-3 border-t border-[#F1F5F9] pt-4">
            <view
              v-for="(ex, ei) in currentWord.examples.slice(0, 2)"
              :key="ei"
              class="mb-3"
            >
              <view class="text-[13px] text-[#475569] leading-relaxed">
                {{ ex.sentence_en }}
              </view>
              <view v-if="ex.sentence_zh" class="mt-0.5 text-[12px] text-[#94A3B8]">
                {{ ex.sentence_zh }}
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- 评分按钮 -->
      <view v-if="phase === 'back'" class="mt-5 grid grid-cols-4 gap-2.5">
        <view
          v-for="opt in ratingOptions"
          :key="opt.rating"
          class="flex flex-col items-center rounded-xl py-3 shadow-sm active:scale-95"
          :class="[opt.bg, submitting ? 'opacity-60' : '']"
          @click="submitRating(opt.rating)"
        >
          <text class="text-[15px] font-black" :class="opt.color">
            {{ opt.label }}
          </text>
          <text class="mt-0.5 text-[10px] text-[#94A3B8]">
            {{ opt.sub }}
          </text>
        </view>
      </view>
    </view>
  </view>
</template>
