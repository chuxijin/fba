<script lang="ts" setup>
import { fbaApi } from '@/api/sdk'
import MembershipModal from '@/components/MembershipModal.vue'
import { useTokenStore } from '@/store'
import { isMembershipAccessError } from '@/utils/membershipAccess'
import { toLoginPage } from '@/utils/toLoginPage'

defineOptions({
  name: 'MyNotes',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '我的笔记',
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
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const groupMode = ref<GroupMode>('knowledge_point')
const activeModeIndex = ref(0)
const showMembershipModal = ref(false)
const modeTouchStartX = ref(0)
const modeTouchStartY = ref(0)
const groupsMap = ref<Record<GroupMode, TreeNode[]>>({
  knowledge_point: [],
  bank: [],
})
const loadingMap = ref<Record<GroupMode, boolean>>({
  knowledge_point: false,
  bank: false,
})
const statisticsMap = ref<Record<GroupMode, { total: number, publicCount: number, featuredCount: number }>>({
  knowledge_point: {
    total: 0,
    publicCount: 0,
    featuredCount: 0,
  },
  bank: {
    total: 0,
    publicCount: 0,
    featuredCount: 0,
  },
})

const groupModes: Array<{ key: GroupMode, label: string }> = [
  { key: 'knowledge_point', label: '按知识点' },
  { key: 'bank', label: '按题库' },
]

function ensureLogin() {
  if (tokenStore.updateNowTime().hasLogin)
    return true

  uni.showToast({ title: '请先登录后查看笔记', icon: 'none' })
  setTimeout(() => {
    toLoginPage()
  }, 300)
  return false
}

async function loadData(mode: GroupMode = groupMode.value) {
  if (!ensureLogin())
    return

  loadingMap.value[mode] = true
  try {
    const data = await fbaApi.qbank.note.getStatistics(mode) as any
    statisticsMap.value[mode] = {
      total: data?.total_count || 0,
      publicCount: data?.public_count || 0,
      featuredCount: data?.featured_count || 0,
    }
    groupsMap.value[mode] = data?.groups || []
  }
  catch (error) {
    console.error('加载笔记数据失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
  finally {
    loadingMap.value[mode] = false
  }
}

function switchGroupMode(mode: GroupMode) {
  const nextIndex = groupModes.findIndex(item => item.key === mode)
  if (nextIndex >= 0)
    activeModeIndex.value = nextIndex

  if (groupMode.value === mode)
    return

  groupMode.value = mode
  if (!groupsMap.value[mode].length) {
    void loadData(mode)
  }
}

function onModeSwiperChange(event: any) {
  const nextIndex = Number(event?.detail?.current || 0)
  const nextMode = groupModes[nextIndex]?.key
  activeModeIndex.value = nextIndex

  if (!nextMode || nextMode === groupMode.value) {
    return
  }

  groupMode.value = nextMode
  if (!groupsMap.value[nextMode].length) {
    void loadData(nextMode)
  }
}

function handleModeTouchStart(event: any) {
  const touch = event?.changedTouches?.[0] || event?.touches?.[0]
  if (!touch) {
    return
  }

  modeTouchStartX.value = Number(touch.clientX || 0)
  modeTouchStartY.value = Number(touch.clientY || 0)
}

function handleModeTouchEnd(event: any) {
  const touch = event?.changedTouches?.[0]
  if (!touch) {
    return
  }

  const deltaX = Number(touch.clientX || 0) - modeTouchStartX.value
  const deltaY = Number(touch.clientY || 0) - modeTouchStartY.value

  if (Math.abs(deltaX) < 42 || Math.abs(deltaX) <= Math.abs(deltaY)) {
    return
  }

  if (deltaX < 0 && activeModeIndex.value < groupModes.length - 1) {
    activeModeIndex.value += 1
    return
  }

  if (deltaX > 0 && activeModeIndex.value > 0) {
    activeModeIndex.value -= 1
  }
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
const expandedKeysMap = ref<Record<GroupMode, Set<string>>>({
  knowledge_point: new Set(),
  bank: new Set(),
})

function getNodeKey(node: TreeNode, mode: GroupMode): string {
  return `${mode}_${node.id ?? ''}_${node.name}`
}

function onGroupClick(node: TreeNode, mode: GroupMode) {
  if (node.children && node.children.length > 0) {
    const key = getNodeKey(node, mode)
    const nextSet = new Set(expandedKeysMap.value[mode])
    if (nextSet.has(key))
      nextSet.delete(key)
    else
      nextSet.add(key)
    expandedKeysMap.value[mode] = nextSet
    return
  }

  startPractice(node, mode)
}

async function startPractice(node: TreeNode, mode: GroupMode) {
  const params: Record<string, any> = {
    session_type: 'note',
    practice_name: node.name,
  }
  if (mode === 'bank') {
    if (node.bank_id) {
      params.bank_id = node.bank_id
      if (node.id) params.chapter_id = node.id
    }
    else if (node.id) {
      params.bank_id = node.id
    }
  }
  if (mode === 'knowledge_point')
    params.knowledge_point = [node.name]

  uni.showLoading({ title: '创建会话...' })
  try {
    const session = await fbaApi.qbank.session.create(params as any)
    uni.navigateTo({
      url: `/pages/practice/session/index?sessionId=${session.id}&mode=practice`,
    })
  }
  catch (error: any) {
    if (isMembershipAccessError(error)) {
      showMembershipModal.value = true
      return
    }

    console.error('创建笔记练习失败:', error)
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

function flattenTree(nodes: TreeNode[], mode: GroupMode, level = 0): FlatNode[] {
  const result: FlatNode[] = []
  const expandedKeys = expandedKeysMap.value[mode]
  for (const node of nodes) {
    const hasChildren = (node.children?.length || 0) > 0
    const expanded = hasChildren && expandedKeys.has(getNodeKey(node, mode))
    result.push({ ...node, level, hasChildren, expanded })
    if (hasChildren && expanded)
      result.push(...flattenTree(node.children, mode, level + 1))
  }
  return result
}

function getFlatGroups(mode: GroupMode) {
  return flattenTree(groupsMap.value[mode] || [], mode)
}

function getModeStatistics(mode: GroupMode) {
  return statisticsMap.value[mode]
}

function getModeTotalCount(mode: GroupMode) {
  return Number(getModeStatistics(mode)?.total || 0)
}

onShow(() => {
  void loadData(groupMode.value)
})

onPullDownRefresh(async () => {
  await loadData(groupMode.value)
  uni.stopPullDownRefresh()
})
</script>

<template>
  <view class="relative min-h-screen from-[#EFF6FF] via-[#F8FBFF] to-[#FAFAFA] bg-gradient-to-b text-[#334155]">
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">我的笔记</text>
      </view>
    </view>

    <view class="mt-4 px-4 pb-24">
      <!-- 统计卡片 -->
      <view class="mb-5 border border-white/60 rounded-2xl bg-white/85 p-5 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)] backdrop-blur-md">
        <view class="grid grid-cols-3 gap-3">
          <view class="flex flex-col items-center rounded-xl bg-[#EFF6FF] py-3">
            <text class="text-[22px] text-[#2563EB] font-black">{{ getModeStatistics(groupMode).total }}</text>
            <text class="mt-1 text-[11px] text-[#94A3B8]">全部笔记</text>
          </view>
          <view class="flex flex-col items-center rounded-xl bg-[#ECFEFF] py-3">
            <text class="text-[22px] text-[#0891B2] font-black">{{ getModeStatistics(groupMode).publicCount }}</text>
            <text class="mt-1 text-[11px] text-[#94A3B8]">公开笔记</text>
          </view>
          <view class="flex flex-col items-center rounded-xl bg-[#F5F3FF] py-3">
            <text class="text-[22px] text-[#7C3AED] font-black">{{ getModeStatistics(groupMode).featuredCount }}</text>
            <text class="mt-1 text-[11px] text-[#94A3B8]">精选笔记</text>
          </view>
        </view>
      </view>

      <!-- 分组模式切换 -->
      <view class="mb-3">
        <view
          class="relative flex w-full items-center rounded-[18px] bg-white/78 p-1.5 shadow-[0_10px_28px_-18px_rgba(15,23,42,0.35)]"
        >
          <view
            class="absolute bottom-1.5 top-1.5 rounded-[14px] bg-[#2563EB] shadow-sm transition-all duration-300"
            :style="{
              width: 'calc(50% - 6px)',
              left: activeModeIndex === 0 ? '6px' : 'calc(50% + 0px)',
            }"
          />
          <view
            v-for="m in groupModes"
            :key="m.key"
            class="relative z-10 flex-1 text-center rounded-[14px] px-4 py-2 text-[13px] transition-all duration-200"
            :class="groupMode === m.key ? 'text-white font-bold' : 'text-[#64748B]'"
            @tap="switchGroupMode(m.key)"
          >
            {{ m.label }}
          </view>
        </view>
      </view>

      <swiper
        class="mode-swiper"
        :current="activeModeIndex"
        :duration="280"
        :disable-touch="false"
        @change="onModeSwiperChange"
        @touchstart="handleModeTouchStart"
        @touchend="handleModeTouchEnd"
      >
        <swiper-item v-for="modeItem in groupModes" :key="modeItem.key">
          <view class="mode-panel">
            <view class="mb-3 flex items-center justify-between pl-1">
              <text class="text-[13px] text-[#475569] font-bold">笔记列表</text>
              <text class="text-[11px] text-[#94A3B8]">共 {{ getModeTotalCount(modeItem.key) }} 题</text>
            </view>

            <view
              v-if="loadingMap[modeItem.key] && getFlatGroups(modeItem.key).length === 0"
              class="py-18 text-center text-[13px] text-[#94A3B8]"
            >
              笔记列表加载中...
            </view>

            <view
              v-else-if="getFlatGroups(modeItem.key).length > 0"
              class="border border-white/60 rounded-2xl bg-white/85 shadow-[0_2px_12px_-6px_rgba(0,0,0,0.06)] backdrop-blur-md overflow-hidden"
            >
              <view
                v-for="(node, index) in getFlatGroups(modeItem.key)"
                :key="`${modeItem.key}-${node.id}-${node.name}-${node.level}`"
                class="flex items-center justify-between py-3 active:bg-[#F8FAFC]"
                :class="index < getFlatGroups(modeItem.key).length - 1 ? 'border-b border-[#F1F5F9]' : ''"
                :style="{ paddingLeft: `${16 + node.level * 20}px`, paddingRight: '16px' }"
                @click="onGroupClick(node, modeItem.key)"
              >
                <view class="flex items-center gap-2.5 min-w-0 flex-1">
                  <view v-if="node.hasChildren" class="h-6 w-6 flex shrink-0 items-center justify-center rounded-md bg-[#2563EB]/10">
                    <view class="i-carbon-folder text-[13px] text-[#2563EB]" />
                  </view>
                  <view v-else class="h-6 w-6 flex shrink-0 items-center justify-center rounded-md" :class="modeItem.key === 'bank' ? 'bg-[#EFF6FF]' : 'bg-[#DBEAFE]'">
                    <view :class="modeItem.key === 'bank' ? 'i-carbon-document text-[13px] text-[#3B82F6]' : 'i-carbon-notebook text-[13px] text-[#2563EB]'" />
                  </view>
                  <text class="text-[13px] font-medium truncate" :class="node.hasChildren ? 'text-[#1E293B]' : 'text-[#475569]'">{{ node.name }}</text>
                </view>
                <view class="flex items-center gap-1.5 shrink-0 ml-2">
                  <text class="text-[12px] font-bold" :class="node.hasChildren ? 'text-[#94A3B8]' : 'text-[#2563EB]'">{{ node.count }}题</text>
                  <view v-if="node.hasChildren" class="text-[13px] text-[#94A3B8] transition-transform" :class="node.expanded ? 'i-carbon-chevron-down' : 'i-carbon-chevron-right'" />
                  <view v-else class="i-carbon-chevron-right text-[13px] text-[#94A3B8]" />
                </view>
              </view>
            </view>

            <view v-else class="flex flex-col items-center justify-center py-20">
              <view class="i-carbon-notebook-reference mb-4 text-6xl text-[#CBD5E1]" />
              <text class="text-[14px] text-[#94A3B8]">还没有写过笔记，刷题时记得沉淀思路。</text>
            </view>
          </view>
        </swiper-item>
      </swiper>

      <MembershipModal v-model="showMembershipModal" />
    </view>
  </view>
</template>

<style scoped>
.mode-swiper {
  width: 100%;
  min-height: 520px;
}

.mode-panel {
  min-height: 520px;
}
</style>

