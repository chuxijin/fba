<script lang="ts" setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { api } from '@/api/sdk'
import { useTokenStore } from '@/store'

defineOptions({ name: 'VocabBooks' })
definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '选择词书',
  },
})

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const loading = ref(false)
const submitting = ref(false)
const books = ref<any[]>([])
const activeBookId = ref<number | null>(null)

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.navigateTo({ url: '/pages/vocab/index' })
}

async function loadBooks() {
  loading.value = true
  try {
    const [bookResult, myBooksResult] = await Promise.allSettled([
      api.browseBooks({ query: { page: 1, size: 50 } }),
      api.getMyBooks({ query: { page: 1, size: 50 } }),
    ])

    if (bookResult.status === 'fulfilled') {
      const data = (bookResult.value as any)?.data
      books.value = data?.items || []
    }

    if (myBooksResult.status === 'fulfilled') {
      const myData = (myBooksResult.value as any)?.data
      const myBooks = myData?.items || []
      const activeBook = myBooks.find((b: any) => b.is_active)
      activeBookId.value = activeBook?.book_id || null
    }
  }
  catch (err) {
    console.error('加载词书失败:', err)
  }
  finally {
    loading.value = false
  }
}

async function selectBook(bookId: number) {
  if (submitting.value || bookId === activeBookId.value) return

  submitting.value = true
  try {
    await api.startBook({ path: { pk: bookId } })
    activeBookId.value = bookId
    uni.showToast({ title: '已切换词书', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 800)
  }
  catch (err) {
    console.error('选择词书失败:', err)
    uni.showToast({ title: '选择失败', icon: 'none' })
  }
  finally {
    submitting.value = false
  }
}

function getCategoryIcon(category: string) {
  const map: Record<string, string> = {
    cet4: 'i-carbon-badge',
    cet6: 'i-carbon-certificate',
    kaoyan: 'i-carbon-education',
    ielts: 'i-carbon-earth',
    toefl: 'i-carbon-globe',
    gre: 'i-carbon-analytics',
    daily: 'i-carbon-chat',
  }
  return map[category] || 'i-carbon-book'
}

function getCategoryColor(category: string) {
  const map: Record<string, { text: string; bg: string }> = {
    cet4: { text: 'text-[#3B82F6]', bg: 'bg-[#EFF6FF]' },
    cet6: { text: 'text-[#8B5CF6]', bg: 'bg-[#F5F3FF]' },
    kaoyan: { text: 'text-[#F59E0B]', bg: 'bg-[#FFFBEB]' },
    ielts: { text: 'text-[#059669]', bg: 'bg-[#ECFDF5]' },
    toefl: { text: 'text-[#06B6D4]', bg: 'bg-[#ECFEFF]' },
    gre: { text: 'text-[#EC4899]', bg: 'bg-[#FDF2F8]' },
    daily: { text: 'text-[#EA580C]', bg: 'bg-[#FFF7ED]' },
  }
  return map[category] || { text: 'text-[#6366F1]', bg: 'bg-[#EEF2FF]' }
}

onShow(() => {
  tokenStore.updateNowTime()
  void loadBooks()
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
          选择词书
        </text>
      </view>
    </view>

    <view class="px-4 pb-8 pt-4">
      <!-- Loading -->
      <view v-if="loading" class="flex items-center justify-center pt-20">
        <view class="h-8 w-8 animate-spin rounded-full border-3 border-[#E2E8F0] border-t-[#6366F1]" />
      </view>

      <!-- 词书列表 -->
      <view v-else class="flex flex-col gap-3">
        <view
          v-for="book in books"
          :key="book.id"
          class="relative overflow-hidden rounded-xl bg-white p-4 shadow-sm active:scale-[0.99]"
          :class="activeBookId === book.id ? 'ring-2 ring-[#6366F1]' : ''"
          @click="selectBook(book.id)"
        >
          <!-- 当前学习标识 -->
          <view
            v-if="activeBookId === book.id"
            class="absolute right-0 top-0 rounded-bl-lg bg-[#6366F1] px-2.5 py-1 text-[10px] text-white font-bold"
          >
            当前学习
          </view>

          <view class="flex items-start gap-3">
            <!-- 图标 -->
            <view
              class="h-12 w-12 flex shrink-0 items-center justify-center rounded-xl"
              :class="[getCategoryColor(book.category).bg, getCategoryColor(book.category).text]"
            >
              <view :class="getCategoryIcon(book.category)" class="text-[24px]" />
            </view>

            <!-- 信息 -->
            <view class="min-w-0 flex-1">
              <view class="text-[15px] text-[#1E293B] font-bold">
                {{ book.name }}
              </view>
              <view v-if="book.description" class="mt-0.5 truncate text-[12px] text-[#94A3B8]">
                {{ book.description }}
              </view>
              <view class="mt-2 flex items-center gap-3 text-[11px] text-[#94A3B8]">
                <view class="flex items-center gap-1">
                  <view class="i-carbon-text-font text-[12px]" />
                  <text>{{ book.word_count || 0 }} 词</text>
                </view>
                <view v-if="book.is_official" class="flex items-center gap-1 text-[#6366F1]">
                  <view class="i-carbon-checkmark-filled text-[12px]" />
                  <text>官方</text>
                </view>
              </view>
            </view>

            <!-- 选择按钮 -->
            <view class="mt-1 shrink-0">
              <view
                v-if="activeBookId === book.id"
                class="h-7 w-7 flex items-center justify-center rounded-full bg-[#6366F1] text-white"
              >
                <view class="i-carbon-checkmark text-[14px]" />
              </view>
              <view
                v-else
                class="h-7 w-7 flex items-center justify-center rounded-full border-2 border-[#E2E8F0]"
              />
            </view>
          </view>
        </view>

        <!-- 空状态 -->
        <view v-if="!loading && books.length === 0" class="rounded-xl bg-white px-6 py-12 text-center shadow-sm">
          <view class="mx-auto mb-3 h-12 w-12 flex items-center justify-center rounded-2xl bg-[#F1F5F9] text-[#94A3B8]">
            <view class="i-carbon-book text-[24px]" />
          </view>
          <view class="text-[15px] text-[#1E293B] font-bold">
            暂无可选词书
          </view>
          <view class="mt-1 text-[12px] text-[#94A3B8]">
            管理员正在准备词书，请稍后再来
          </view>
        </view>
      </view>
    </view>
  </view>
</template>
