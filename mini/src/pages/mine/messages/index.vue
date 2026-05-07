<script lang="ts" setup>
import type { PageData } from '@fba/api-sdk'
import { computed, ref } from 'vue'
import { onPullDownRefresh, onReachBottom, onShow } from '@dcloudio/uni-app'
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'
import { formatDateTime, stripRichText } from '@/utils/mine'
import { toLoginPage } from '@/utils/toLoginPage'

defineOptions({
  name: 'MyMessages',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '我的消息',
  },
})

interface UserMessageItem {
  id: number
  target_type: 'all' | 'user'
  title: string
  content: string
  message_type: string
  link_url?: string | null
  payload?: Record<string, any> | null
  publish_time?: string | null
  expire_time?: string | null
  read_time?: string | null
  created_time?: string | null
  is_read: boolean
}

const PAGE_SIZE = 20
const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const loading = ref(false)
const loadingMore = ref(false)
const messages = ref<UserMessageItem[]>([])
const total = ref(0)
const page = ref(1)
const unreadOnly = ref(false)

const hasMore = computed(() => messages.value.length < total.value)

function ensureLogin() {
  tokenStore.updateNowTime()
  if (tokenStore.hasLogin) {
    return true
  }

  uni.showToast({ title: '请先登录后查看消息', icon: 'none' })
  setTimeout(() => {
    toLoginPage()
  }, 300)
  return false
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.switchTab({ url: '/pages/mine/index' })
}

function messageTypeLabel(type: string) {
  const labelMap: Record<string, string> = {
    system: '系统',
    update: '上新',
    maintenance: '维护',
    personal: '个人',
  }
  return labelMap[type] || '消息'
}

function messageTypeClass(type: string) {
  const classMap: Record<string, string> = {
    system: 'bg-[#EEF2FF] text-[#4F46E5]',
    update: 'bg-[#ECFDF5] text-[#16A34A]',
    maintenance: 'bg-[#FFF7ED] text-[#EA580C]',
    personal: 'bg-[#EFF6FF] text-[#2563EB]',
  }
  return classMap[type] || 'bg-[#F8FAFC] text-[#64748B]'
}

async function loadMessages(targetPage = 1) {
  if (!ensureLogin()) {
    return
  }

  if (targetPage === 1) {
    loading.value = true
  }
  else {
    loadingMore.value = true
  }

  try {
    const data = await fbaApi.qbank.request.get<PageData<UserMessageItem>>('/messages', {
      params: {
        page: targetPage,
        size: PAGE_SIZE,
        unread_only: unreadOnly.value,
      },
    })
    const pageItems = data?.items || []
    total.value = Number(data?.total || 0)
    page.value = targetPage
    if (targetPage === 1) {
      messages.value = pageItems
      return
    }
    messages.value = [...messages.value, ...pageItems]
  }
  catch (error) {
    console.error('加载我的消息失败:', error)
    messages.value = []
    total.value = 0
    uni.showToast({ title: '加载消息失败', icon: 'none' })
  }
  finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function markMessageRead(item: UserMessageItem) {
  if (item.is_read) {
    return
  }

  try {
    await fbaApi.qbank.request.put(`/messages/${item.id}/read`)
    item.is_read = true
    item.read_time = new Date().toISOString()
  }
  catch (error) {
    console.error('标记消息已读失败:', error)
  }
}

async function openMessage(item: UserMessageItem) {
  await markMessageRead(item)
  if (item.link_url) {
    uni.navigateTo({ url: item.link_url })
    return
  }

  uni.showModal({
    title: item.title,
    content: stripRichText(item.content) || '暂无内容',
    showCancel: false,
  })
}

async function markAllRead() {
  if (!messages.value.some(item => !item.is_read)) {
    uni.showToast({ title: '暂无未读消息', icon: 'none' })
    return
  }

  try {
    await fbaApi.qbank.request.put('/messages/read-all')
    messages.value = messages.value.map(item => ({
      ...item,
      is_read: true,
      read_time: item.read_time || new Date().toISOString(),
    }))
    uni.showToast({ title: '已全部标记为已读', icon: 'success' })
  }
  catch (error) {
    console.error('全部已读失败:', error)
    uni.showToast({ title: '操作失败', icon: 'none' })
  }
}

function toggleUnreadOnly() {
  unreadOnly.value = !unreadOnly.value
  loadMessages()
}

onShow(() => {
  loadMessages()
})

onPullDownRefresh(async () => {
  await loadMessages()
  uni.stopPullDownRefresh()
})

onReachBottom(() => {
  if (loading.value || loadingMore.value || !hasMore.value) {
    return
  }
  loadMessages(page.value + 1)
})
</script>

<template>
  <view class="relative min-h-screen from-[#EEF2FF] via-[#F8FCF9] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">我的消息</text>
        <view class="absolute right-4 text-[12px] text-[#4F46E5] font-bold" @click="markAllRead">
          全部已读
        </view>
      </view>
    </view>

    <view class="mt-4 px-4 pb-24">
      <view class="mb-4 flex items-center justify-between">
        <view>
          <view class="text-[18px] text-[#1E293B] font-black">
            消息中心
          </view>
          <view class="mt-1 text-[12px] text-[#64748B]">
            上新通知、站点维护和个人提醒都会在这里
          </view>
        </view>
        <view
          class="rounded-full px-3 py-1.5 text-[12px] font-bold"
          :class="unreadOnly ? 'bg-[#4F46E5] text-white' : 'bg-white/80 text-[#4F46E5]'"
          @click="toggleUnreadOnly"
        >
          {{ unreadOnly ? '仅未读' : '全部消息' }}
        </view>
      </view>

      <view v-if="loading && messages.length === 0" class="py-20 text-center text-[13px] text-[#94A3B8]">
        消息加载中...
      </view>

      <view v-else-if="messages.length === 0" class="rounded-[24px] bg-white/80 px-5 py-16 text-center shadow-sm">
        <view class="mx-auto mb-4 h-14 w-14 flex items-center justify-center rounded-2xl bg-[#EEF2FF] text-[#4F46E5]">
          <view class="i-carbon-notification-off text-[28px]" />
        </view>
        <view class="text-[15px] text-[#1E293B] font-bold">
          暂无消息
        </view>
        <view class="mt-2 text-[12px] text-[#94A3B8]">
          有新通知时会第一时间出现在这里
        </view>
      </view>

      <view v-else class="flex flex-col gap-3">
        <view
          v-for="item in messages"
          :key="item.id"
          class="border rounded-[22px] bg-white/90 px-4 py-4 shadow-[0_2px_14px_-8px_rgba(15,23,42,0.18)] active:scale-[0.99]"
          :class="item.is_read ? 'border-white/70 opacity-78' : 'border-[#C7D2FE]'"
          @click="openMessage(item)"
        >
          <view class="flex items-start justify-between gap-3">
            <view class="min-w-0 flex-1">
              <view class="mb-2 flex items-center gap-2">
                <view
                  class="rounded-full px-2.5 py-1 text-[10px] font-black"
                  :class="messageTypeClass(item.message_type)"
                >
                  {{ messageTypeLabel(item.message_type) }}
                </view>
                <view v-if="!item.is_read" class="h-2 w-2 rounded-full bg-[#EF4444]" />
              </view>
              <view class="line-clamp-1 text-[15px] text-[#1E293B] font-black">
                {{ item.title }}
              </view>
              <view class="line-clamp-2 mt-2 text-[12px] text-[#64748B] leading-5">
                {{ stripRichText(item.content) || '暂无内容' }}
              </view>
              <view class="mt-3 text-[11px] text-[#94A3B8]">
                {{ formatDateTime(item.publish_time || item.created_time, 'YYYY-MM-DD HH:mm') }}
              </view>
            </view>
            <view class="mt-1 h-8 w-8 flex items-center justify-center rounded-full bg-[#F8FAFC] text-[#CBD5E1]">
              <view class="i-carbon-chevron-right text-[18px]" />
            </view>
          </view>
        </view>

        <view v-if="loadingMore" class="py-4 text-center text-[12px] text-[#94A3B8]">
          正在加载更多...
        </view>
        <view v-else-if="!hasMore" class="py-4 text-center text-[12px] text-[#CBD5E1]">
          没有更多消息了
        </view>
      </view>
    </view>
  </view>
</template>
