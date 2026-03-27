<script lang="ts" setup>
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'
import { toLoginPage } from '@/utils/toLoginPage'

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

type GroupMode = 'knowledge_point' | 'bank'

interface TreeNode {
  id: number | null
  name: string
  count: number
  children: TreeNode[]
  bank_id?: number | null
}

const tokenStore = useTokenStore()
const { statusBarHeight } = uni.getSystemInfoSync()

const loading = ref(false)
const groupMode = ref<GroupMode>('knowledge_point')
const groups = ref<TreeNode[]>([])
const statistics = ref<any>({
  total_count: 0,
  folder_count: 0,
})

const groupModes: Array<{ key: GroupMode, label: string }> = [
  { key: 'knowledge_point', label: '按知识点' },
  { key: 'bank', label: '按题库' },
]

function ensureLogin() {
  if (tokenStore.updateNowTime().hasLogin)
    return true

  uni.showToast({ title: '请先登录后查看收藏', icon: 'none' })
  setTimeout(() => {
    toLoginPage()
  }, 300)
  return false
}

async function loadData() {
  if (!ensureLogin())
    return

  loading.value = true
  try {
    const data = await fbaApi.qbank.favorite.getStatistics(groupMode.value) as any
    statistics.value = data
    groups.value = data?.groups || []
  }
  catch (error) {
    console.error('加载收藏数据失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

function switchGroupMode(mode: GroupMode) {
  if (groupMode.value === mode)
    return
  groupMode.value = mode
  loadData()
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.switchTab({ url: '/pages/mine/index' })
}

// 展开/收缩状态
const expandedKeys = ref<Set<string>>(new Set())

function getNodeKey(node: TreeNode): string {
  return `${node.id ?? ''}_${node.name}`
}

function onGroupClick(node: TreeNode) {
  if (node.children && node.children.length > 0) {
    const key = getNodeKey(node)
    if (expandedKeys.value.has(key))
      expandedKeys.value.delete(key)
    else
      expandedKeys.value.add(key)
    return
  }

  startPractice(node)
}

async function startPractice(node: TreeNode) {
  const params: Record<string, any> = {
    session_type: 'favorite',
    practice_name: node.name,
  }
  if (groupMode.value === 'bank') {
    if (node.bank_id) {
      params.bank_id = node.bank_id
      if (node.id) params.chapter_id = node.id
    }
    else if (node.id) {
      params.bank_id = node.id
    }
  }
  if (groupMode.value === 'knowledge_point')
    params.knowledge_point = [node.name]

  uni.showLoading({ title: '创建会话...' })
  try {
    const session = await fbaApi.qbank.session.create(params as any)
    uni.navigateTo({
      url: `/pages/practice/session/index?sessionId=${session.id}&mode=practice`,
    })
  }
  catch (error: any) {
    console.error('创建收藏练习失败:', error)
    uni.showToast({ title: error?.message || '创建失败', icon: 'none' })
  }
  finally {
    uni.hideLoading()
  }
}

interface FlatNode extends TreeNode {
  level: number
  hasChildren: boolean
  expanded: boolean
}

function flattenTree(nodes: TreeNode[], level = 0): FlatNode[] {
  const result: FlatNode[] = []
  for (const node of nodes) {
    const hasChildren = (node.children?.length || 0) > 0
    const expanded = hasChildren && expandedKeys.value.has(getNodeKey(node))
    result.push({ ...node, level, hasChildren, expanded })
    if (hasChildren && expanded)
      result.push(...flattenTree(node.children, level + 1))
  }
  return result
}

const flatGroups = computed(() => flattenTree(groups.value))
const totalCount = computed(() => statistics.value.total_count || 0)

onShow(() => {
  loadData()
})

onPullDownRefresh(async () => {
  await loadData()
  uni.stopPullDownRefresh()
})
</script>

<template>
  <view class="relative min-h-screen from-[#FFFBEB] via-[#FFFDF8] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">我的收藏</text>
      </view>
    </view>

    <view class="mt-4 px-4 pb-24">
      <!-- 统计卡片 -->
      <view class="mb-5 border border-white/60 rounded-2xl bg-white/85 p-5 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)] backdrop-blur-md">
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
      </view>

      <!-- 分组模式切换 -->
      <view class="mb-4 flex items-center gap-0 rounded-full bg-white/80 p-1 shadow-sm backdrop-blur-md">
        <view
          v-for="m in groupModes"
          :key="m.key"
          class="flex flex-1 items-center justify-center rounded-full py-2 text-[13px] font-bold transition-all"
          :class="groupMode === m.key ? 'bg-[#D97706] text-white shadow-sm' : 'text-[#64748B]'"
          @click="switchGroupMode(m.key)"
        >
          {{ m.label }}
        </view>
      </view>

      <!-- 列表标题 -->
      <view class="mb-3 flex items-center justify-between pl-1">
        <text class="text-[13px] text-[#475569] font-bold">收藏列表</text>
        <text class="text-[11px] text-[#94A3B8]">共 {{ totalCount }} 题</text>
      </view>

      <!-- loading -->
      <view v-if="loading && flatGroups.length === 0" class="py-18 text-center text-[13px] text-[#94A3B8]">
        收藏列表加载中...
      </view>

      <!-- 分组列表（树形拍平） -->
      <view v-else-if="flatGroups.length > 0" class="border border-white/60 rounded-2xl bg-white/85 shadow-[0_2px_12px_-6px_rgba(0,0,0,0.06)] backdrop-blur-md overflow-hidden">
        <view
          v-for="(node, index) in flatGroups"
          :key="`${node.id}-${node.name}-${node.level}`"
          class="flex items-center justify-between py-3 active:bg-[#F8FAFC]"
          :class="index < flatGroups.length - 1 ? 'border-b border-[#F1F5F9]' : ''"
          :style="{ paddingLeft: `${16 + node.level * 20}px`, paddingRight: '16px' }"
          @click="onGroupClick(node)"
        >
          <view class="flex items-center gap-2.5 min-w-0 flex-1">
            <view v-if="node.hasChildren" class="h-6 w-6 flex shrink-0 items-center justify-center rounded-md bg-[#D97706]/10">
              <view class="i-carbon-folder text-[13px] text-[#D97706]" />
            </view>
            <view v-else class="h-6 w-6 flex shrink-0 items-center justify-center rounded-md" :class="groupMode === 'bank' ? 'bg-[#EFF6FF]' : 'bg-[#FEF3C7]'">
              <view :class="groupMode === 'bank' ? 'i-carbon-document text-[13px] text-[#3B82F6]' : 'i-carbon-star-filled text-[13px] text-[#F59E0B]'" />
            </view>
            <text class="text-[13px] font-medium truncate" :class="node.hasChildren ? 'text-[#1E293B]' : 'text-[#475569]'">{{ node.name }}</text>
          </view>
          <view class="flex items-center gap-1.5 shrink-0 ml-2">
            <text class="text-[12px] font-bold" :class="node.hasChildren ? 'text-[#94A3B8]' : 'text-[#D97706]'">{{ node.count }}题</text>
            <view v-if="node.hasChildren" class="text-[13px] text-[#94A3B8] transition-transform" :class="node.expanded ? 'i-carbon-chevron-down' : 'i-carbon-chevron-right'" />
            <view v-else class="i-carbon-chevron-right text-[13px] text-[#94A3B8]" />
          </view>
        </view>
      </view>

      <!-- 空状态 -->
      <view v-else class="flex flex-col items-center justify-center py-20">
        <view class="i-carbon-star mb-4 text-6xl text-[#CBD5E1]" />
        <text class="text-[14px] text-[#94A3B8]">还没有收藏内容，遇到好题记得先收下。</text>
      </view>
    </view>
  </view>
</template>

