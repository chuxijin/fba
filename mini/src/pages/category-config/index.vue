<script lang="ts" setup>
import type { AppPracticeMode } from '@/utils/appSettings'
import { onShow } from '@dcloudio/uni-app'
import { computed, ref, watch } from 'vue'
import { api } from '@/api/sdk'
import LoginModal from '@/components/LoginModal.vue'
import { useTokenStore, useUserStore } from '@/store'
import { getAppSettings, saveAppSettings } from '@/utils/appSettings'
import { getCachedStudyPreference, mergeCachedStudyPreference, setCachedStudyPreference } from '@/utils/studyPreferenceCache'
import { getStudyDomainOption, type StudyDomainCode } from '@/utils/studyDomain'
import { getStudyDomainCategoryRoots } from '@/utils/studyDomainQuestionScope'

defineOptions({
  name: 'CategoryConfig',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    disableScroll: true,
  },
})

interface CategoryNode {
  id: number
  name: string
  app_code?: string
  type?: string
  code?: string | null
  description?: string | null
  color?: string | null
  sort_order?: number
  children?: CategoryNode[] | null
}

interface SelectedTabItem {
  id: number
  name: string
}

interface StudyPreferenceCustomTab {
  id: string
  name: string
  category_id: number
  category_name: string
  bank_id?: number | null
  bank_name?: string | null
  is_fixed: boolean
  order: number
}

interface TypeSection {
  key: 'product_catalog' | 'knowledge_point'
  title: string
  hint: string
  nodes: CategoryNode[]
  total: number
}

interface VisibleCategoryItem {
  node: CategoryNode
  depth: number
  hasChildren: boolean
}

const tokenStore = useTokenStore()
const userStore = useUserStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const showLoginModal = ref(false)
const loading = ref(false)
const saving = ref(false)
const pendingSave = ref(false)
const currentDomain = ref<StudyDomainCode>(getAppSettings().currentDomain)
const categoryTree = ref<CategoryNode[]>([])
const selectedTabsState = ref<SelectedTabItem[]>([])
const expandedIds = ref<number[]>([])
const collapsedSectionKeys = ref<string[]>([])
const previewActiveIndex = ref(0)
const initialized = ref(false)

const allowedTypes: Array<'product_catalog' | 'knowledge_point'> = ['product_catalog', 'knowledge_point']
const typeLabelMap: Record<string, string> = {
  product_catalog: '题库目录',
  knowledge_point: '知识点',
  default: '分类体系',
}
const typeHintMap: Record<string, string> = {
  product_catalog: '按题库目录挑选首页展示的刷题分类',
  knowledge_point: '按知识点脉络整理刷题分类',
  default: '当前领域下的分类树',
}

const currentDomainOption = computed(() => getStudyDomainOption(currentDomain.value))
const selectedCountText = computed(() => `${selectedTabsState.value.length} 个`)

const sections = computed<TypeSection[]>(() => {
  return allowedTypes
    .map((type) => {
      const nodes = filterCategoryTreeByType(categoryTree.value, type)
      if (!nodes.length) {
        return null
      }

      return {
        key: type,
        title: formatTypeLabel(type),
        hint: formatTypeHint(type),
        nodes,
        total: countCategoryNodes(nodes),
      }
    })
    .filter((section): section is TypeSection => Boolean(section))
})

function normalizeValue(value?: string | null) {
  return String(value || '').trim().toLowerCase()
}

function toNumber(value: unknown) {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

function cloneCategoryTree(nodes: CategoryNode[] | null | undefined): CategoryNode[] {
  return (nodes || []).map(node => ({
    ...node,
    children: cloneCategoryTree(node.children),
  }))
}

function countCategoryNodes(nodes: CategoryNode[] | null | undefined): number {
  let total = 0
  for (const node of nodes || []) {
    total += 1
    if (node.children?.length) {
      total += countCategoryNodes(node.children)
    }
  }
  return total
}

function formatTypeLabel(type?: string | null) {
  if (!type) {
    return typeLabelMap.default
  }

  return typeLabelMap[type] || type.replace(/_/g, ' ')
}

function formatTypeHint(type?: string | null) {
  if (!type) {
    return typeHintMap.default
  }

  return typeHintMap[type] || typeHintMap.default
}

function filterCategoryTreeByType(nodes: CategoryNode[] | null | undefined, targetType: string) {
  const result: CategoryNode[] = []
  const normalizedType = normalizeValue(targetType)

  for (const node of nodes || []) {
    const isMatchedNode = normalizeValue(node.type) === normalizedType

    if (isMatchedNode) {
      result.push({
        ...node,
        children: cloneCategoryTree(node.children),
      })
      continue
    }

    const children = filterCategoryTreeByType(node.children, targetType)
    if (children.length) {
      result.push(...children)
    }
  }

  return result.sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0))
}

function buildVisibleItems(
  nodes: CategoryNode[] | null | undefined,
  depth = 0,
): VisibleCategoryItem[] {
  const result: VisibleCategoryItem[] = []

  for (const node of nodes || []) {
    const hasChildren = Boolean(node.children?.length)
    result.push({
      node,
      depth,
      hasChildren,
    })

    if (hasChildren && expandedIds.value.includes(node.id)) {
      result.push(...buildVisibleItems(node.children, depth + 1))
    }
  }

  return result
}

function ensureDefaultExpanded() {
  if (expandedIds.value.length) {
    return
  }

  expandedIds.value = sections.value
    .flatMap(section => section.nodes)
    .filter(item => item.children?.length)
    .map(item => item.id)
}

function isSectionExpanded(sectionKey: string) {
  return !collapsedSectionKeys.value.includes(sectionKey)
}

function isNodeExpanded(id: number) {
  return expandedIds.value.includes(id)
}

function toggleSection(sectionKey: string) {
  const current = [...collapsedSectionKeys.value]
  const index = current.indexOf(sectionKey)

  if (index >= 0) {
    current.splice(index, 1)
  }
  else {
    current.push(sectionKey)
  }

  collapsedSectionKeys.value = current
}

function toggleNode(item: VisibleCategoryItem) {
  if (!item.hasChildren) {
    return
  }

  const current = [...expandedIds.value]
  const index = current.indexOf(item.node.id)

  if (index >= 0) {
    current.splice(index, 1)
  }
  else {
    current.push(item.node.id)
  }

  expandedIds.value = current
}

function getVisibleItemsBySection(nodes: CategoryNode[]) {
  return buildVisibleItems(nodes)
}

function isTabSelected(id: number) {
  return selectedTabsState.value.some(item => item.id === id)
}

function addSelectedTab(item: VisibleCategoryItem) {
  if (isTabSelected(item.node.id)) {
    uni.showToast({ title: '这个首页 Tab 已经添加了', icon: 'none' })
    return
  }

  selectedTabsState.value = [
    ...selectedTabsState.value,
    {
      id: item.node.id,
      name: item.node.name,
    },
  ]
  previewActiveIndex.value = selectedTabsState.value.length - 1
  saveStudyPreference()
}

function removeSelectedTab(id: number | undefined) {
  if (!id) {
    return
  }

  selectedTabsState.value = selectedTabsState.value.filter(item => item.id !== id)
  if (previewActiveIndex.value >= selectedTabsState.value.length) {
    previewActiveIndex.value = Math.max(0, selectedTabsState.value.length - 1)
  }
  saveStudyPreference()
}

function moveSelectedTab(id: number | undefined, direction: 'up' | 'down') {
  if (!id) {
    return
  }

  const current = [...selectedTabsState.value]
  const currentIndex = current.findIndex(item => item.id === id)
  if (currentIndex < 0) {
    return
  }

  const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1
  if (targetIndex < 0 || targetIndex >= current.length) {
    return
  }

  const temp = current[currentIndex]
  current[currentIndex] = current[targetIndex]
  current[targetIndex] = temp
  selectedTabsState.value = current
  previewActiveIndex.value = targetIndex
  saveStudyPreference()
}

function findCategoryNodeById(nodes: CategoryNode[] | null | undefined, targetId: number): CategoryNode | null {
  for (const node of nodes || []) {
    if (node.id === targetId) {
      return node
    }

    const child = findCategoryNodeById(node.children, targetId)
    if (child) {
      return child
    }
  }
  return null
}

function mapPreferenceToSelectedTabs(customTabs: StudyPreferenceCustomTab[] | null | undefined) {
  return (customTabs || [])
    .slice()
    .sort((first, second) => toNumber(first.order) - toNumber(second.order))
    .map((item) => {
      const categoryId = toNumber(item.category_id)
      const categoryNode = findCategoryNodeById(categoryTree.value, categoryId)
      if (!categoryId || !categoryNode) {
        return null
      }

      return {
        id: categoryId,
        name: item.category_name || item.name,
      }
    })
    .filter((item): item is SelectedTabItem => Boolean(item))
}

function buildPreferencePayload() {
  return selectedTabsState.value.map((item, index) => ({
    id: String(item.id),
    name: item.name,
    category_id: item.id,
    category_name: item.name,
    bank_id: null,
    bank_name: null,
    is_fixed: false,
    order: index,
  }))
}

function getNodeContentIndent(item: VisibleCategoryItem) {
  return 12 + item.depth * 22
}

function getNodeTitleClass(item: VisibleCategoryItem) {
  if (!item.hasChildren) {
    return 'text-[14px] font-medium'
  }

  return item.depth === 0 ? 'text-[15px] font-bold' : 'text-[14px] font-medium'
}

function getNodeIndicatorClass(item: VisibleCategoryItem) {
  if (!item.hasChildren) {
    return 'h-1.5 w-1.5 rounded-full bg-[#CBD5E1]'
  }

  if (item.depth === 0) {
    return 'h-[16px] w-[16px] rounded-full bg-[#10B981]'
  }

  if (item.depth === 1) {
    return 'h-[16px] w-[16px] rounded-full bg-[#D1D5DB]'
  }

  return ''
}

function ensureLogin() {
  if (!tokenStore.updateNowTime().hasLogin) {
    showLoginModal.value = true
    return false
  }
  return true
}

function goBack() {
  uni.navigateBack()
}

async function loadCategories() {
  const categoryRoots = await getStudyDomainCategoryRoots(
    currentDomain.value,
    ['product_catalog', 'knowledge_point'],
  ) as CategoryNode[]

  categoryTree.value = categoryRoots || []
  expandedIds.value = []
  collapsedSectionKeys.value = []
  ensureDefaultExpanded()
}

function applyStudyPreference(data: any) {
  const nextPracticeMode: AppPracticeMode = data?.practice_mode === 'exam' || data?.practice_mode === 'memorize'
    ? data.practice_mode
    : 'practice'

  saveAppSettings({ practiceMode: nextPracticeMode })
  selectedTabsState.value = mapPreferenceToSelectedTabs(data?.custom_tabs)
  previewActiveIndex.value = 0
}

async function loadStudyPreference() {
  const userId = Number(userStore.userInfo?.id || 0)
  const cached = getCachedStudyPreference(userId)
  const remoteResponse = cached ? null : await api.qbankGetStudyPreference()
  const data = cached || (remoteResponse as any)?.data
  const nextDomain = data?.current_domain
    ? getStudyDomainOption(data.current_domain).code
    : currentDomain.value

  if (nextDomain !== currentDomain.value) {
    currentDomain.value = nextDomain
    saveAppSettings({ currentDomain: nextDomain })
    await loadCategories()
  }

  if (!cached) {
    setCachedStudyPreference(userId, data)
  }
  applyStudyPreference(data)
}

async function saveStudyPreference() {
  if (!tokenStore.updateNowTime().hasLogin) {
    return
  }

  if (saving.value) {
    pendingSave.value = true
    return
  }

  saving.value = true
  try {
    do {
      pendingSave.value = false
      const settings = getAppSettings()
      const payload = {
        current_domain: currentDomain.value,
        practice_mode: settings.practiceMode,
        custom_tabs: buildPreferencePayload(),
      } as any

      mergeCachedStudyPreference(Number(userStore.userInfo?.id || 0), payload)
      await api.qbankUpdateStudyPreference({ body: payload })
    } while (pendingSave.value)

    uni.showToast({ title: '已保存首页分类', icon: 'none' })
  }
  catch (error) {
    console.error('保存首页分类失败:', error)
    uni.showToast({ title: '保存首页分类失败', icon: 'none' })
  }
  finally {
    saving.value = false
  }
}

async function loadData() {
  if (!ensureLogin()) {
    return
  }

  loading.value = true
  try {
    currentDomain.value = getAppSettings().currentDomain
    await loadCategories()
    await loadStudyPreference()
  }
  catch (error) {
    console.error('加载分类配置失败:', error)
    categoryTree.value = []
    selectedTabsState.value = []
    uni.showToast({ title: '加载分类配置失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

async function handleLoginSuccess() {
  tokenStore.updateNowTime()
  showLoginModal.value = false
  await loadData()
}

watch(sections, () => {
  ensureDefaultExpanded()
})

onShow(() => {
  if (initialized.value) {
    return
  }

  initialized.value = true
  void loadData()
})
</script>

<template>
  <view class="relative h-screen overflow-hidden from-[#DAF0E4] via-[#F0F8F4] to-[#F8FCF9] bg-gradient-to-b text-[#334155]">
    <view class="relative z-10 w-full shrink-0" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white/80 text-[#475569] shadow-sm active:scale-95" @click="goBack">
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">
          分类配置
        </text>
        <view class="absolute right-4 rounded-full bg-white/80 px-3 py-1 text-[12px] text-[#059669] font-bold shadow-sm">
          {{ saving ? '保存中' : selectedCountText }}
        </view>
      </view>
    </view>

    <view class="box-border flex flex-col overflow-hidden px-4 pb-0" :style="{ height: `calc(100vh - ${statusBarHeight + 44}px)` }">
      <view class="shrink-0 pt-3">
        <view class="overflow-hidden rounded-2xl border border-white/70 bg-white/88 shadow-[0_10px_28px_rgba(148,163,184,0.10)]">
          <view class="border-b border-[#ECFDF5] from-[#F6FFFA] to-[#F8FAFC] bg-gradient-to-r px-4 pb-3 pt-4">
            <view class="flex items-center justify-between gap-3">
              <view class="min-w-0">
                <view class="text-[15px] text-[#14532D] font-bold">
                  已添加首页 Tab
                </view>
                <view class="mt-1 truncate text-[11px] text-[#6B7280]">
                  当前领域：{{ currentDomainOption.label }}
                </view>
              </view>
              <view class="shrink-0 rounded-full bg-[#ECFDF5] px-2.5 py-1 text-[11px] text-[#059669] font-semibold">
                {{ selectedCountText }}
              </view>
            </view>
          </view>

          <view v-if="selectedTabsState.length" class="relative border-b border-[#ECFDF5] bg-[#F8FCFA]">
            <scroll-view
              scroll-x
              class="whitespace-nowrap px-4 py-4"
              style="width: calc(100% - 64px);"
              :show-scrollbar="false"
              :scroll-into-view="`preview-tab-${previewActiveIndex}`"
              scroll-with-animation
            >
              <view
                v-for="(selected, index) in selectedTabsState"
                :id="`preview-tab-${index}`"
                :key="selected.id"
                class="relative mr-6 inline-block text-[17px] transition-all"
                :class="previewActiveIndex === index ? 'font-black text-[#059669]' : 'font-medium text-[#64748B]'"
                @click="previewActiveIndex = index"
              >
                {{ selected.name }}
                <view
                  v-if="previewActiveIndex === index"
                  class="absolute left-1/2 h-1 w-4 rounded-full bg-[#10B981] shadow-[0_2px_8px_rgba(16,185,129,0.5)] -bottom-2.5 -translate-x-1/2"
                />
              </view>

              <view class="inline-block w-8" />
            </scroll-view>

            <view class="absolute bottom-0 right-0 top-0 w-20 flex items-center justify-end from-[#F8FCFA] via-[#F8FCFA]/90 to-transparent bg-gradient-to-l pr-3">
              <view class="h-8 w-8 flex items-center justify-center rounded-full bg-white/90 text-[#475569] shadow-sm">
                <view class="i-carbon-menu text-lg" />
              </view>
            </view>
          </view>

          <view v-if="selectedTabsState.length" class="flex items-center justify-between gap-3 bg-white/70 px-4 py-3">
            <view class="min-w-0 flex-1">
              <view class="truncate text-[13px] text-[#1E293B] font-bold">
                {{ selectedTabsState[previewActiveIndex]?.name }}
              </view>
              <view class="mt-0.5 text-[11px] text-[#94A3B8]">
                预览效果与刷题首页顶部 Tab 保持一致
              </view>
            </view>

            <view class="flex shrink-0 items-center gap-1.5">
              <view
                class="h-8 w-8 flex items-center justify-center rounded-full bg-[#F8FAFC] text-[#64748B] active:scale-95"
                :class="previewActiveIndex === 0 ? 'opacity-35' : ''"
                @tap.stop="moveSelectedTab(selectedTabsState[previewActiveIndex]?.id, 'up')"
              >
                <view class="i-carbon-chevron-up text-[16px]" />
              </view>
              <view
                class="h-8 w-8 flex items-center justify-center rounded-full bg-[#F8FAFC] text-[#64748B] active:scale-95"
                :class="previewActiveIndex === selectedTabsState.length - 1 ? 'opacity-35' : ''"
                @tap.stop="moveSelectedTab(selectedTabsState[previewActiveIndex]?.id, 'down')"
              >
                <view class="i-carbon-chevron-down text-[16px]" />
              </view>
              <view
                class="h-8 w-8 flex items-center justify-center rounded-full bg-[#FEF2F2] text-[#EF4444] active:scale-95"
                @tap.stop="removeSelectedTab(selectedTabsState[previewActiveIndex]?.id)"
              >
                <view class="i-carbon-close text-[15px]" />
              </view>
            </view>
          </view>

          <view v-else class="px-4 py-6 text-center text-[12px] text-[#94A3B8]">
            未添加时首页展示当前领域的默认分类
          </view>
        </view>
      </view>

      <scroll-view
        scroll-y
        class="box-border min-h-0 flex-1 pb-6 pt-2"
        :show-scrollbar="false"
      >
        <view v-if="loading" class="mt-4 rounded-2xl bg-white/85 px-5 py-10 text-center shadow-sm">
          <view class="text-[15px] text-[#1E293B] font-semibold">
            分类数据加载中...
          </view>
          <view class="mt-1 text-[12px] text-[#94A3B8]">
            正在读取当前领域分类树
          </view>
        </view>

        <template v-else-if="sections.length">
          <view
            v-for="section in sections"
            :key="section.key"
            class="mt-4 overflow-hidden rounded-2xl border border-white/70 bg-white/88 shadow-[0_10px_30px_rgba(148,163,184,0.10)]"
          >
            <view
              class="from-[#F6FFFA] to-[#F8FAFC] bg-gradient-to-r px-4 pb-3 pt-4"
              :class="isSectionExpanded(section.key) ? 'border-b border-[#ECFDF5]' : ''"
            >
              <view class="flex items-start justify-between gap-3">
                <view class="min-w-0">
                  <view class="text-[15px] text-[#14532D] font-bold">
                    {{ section.title }}
                  </view>
                  <view class="mt-1 text-[11px] text-[#6B7280]">
                    {{ section.hint }}
                  </view>
                </view>
                <view
                  class="flex shrink-0 items-center gap-2 rounded-full bg-[#F0FDF4] px-2 py-1"
                  @click.stop="toggleSection(section.key)"
                >
                  <view class="text-[11px] text-[#059669] font-semibold">
                    {{ isSectionExpanded(section.key) ? '收起' : '展开' }}
                  </view>
                  <view class="rounded-full bg-[#ECFDF5] px-2.5 py-1 text-[11px] text-[#059669] font-semibold">
                    {{ section.total }} 项
                  </view>
                  <view
                    class="i-carbon-chevron-down text-[18px] text-[#94A3B8] transition-transform duration-300"
                    :style="{ transform: isSectionExpanded(section.key) ? 'rotate(180deg)' : 'rotate(0deg)' }"
                  />
                </view>
              </view>
            </view>

            <view v-show="isSectionExpanded(section.key)" class="bg-white/70">
              <view
                v-for="item in getVisibleItemsBySection(section.nodes)"
                :key="`${section.key}-${item.node.id}-${item.depth}`"
                class="relative border-b border-[#F4F4F4] px-5 py-4 transition-colors active:bg-[#F8FAFC]"
                @click="toggleNode(item)"
              >
                <view class="flex items-start justify-between">
                  <view class="min-w-0 flex flex-1 items-start">
                    <view class="mt-[2px] h-[20px] w-[20px] flex shrink-0 items-center justify-center">
                      <template v-if="item.hasChildren">
                        <view class="flex items-center justify-center" :class="getNodeIndicatorClass(item)">
                          <view
                            v-if="item.depth <= 1"
                            class="i-carbon-chevron-down text-[12px] text-white transition-transform duration-300"
                            style="transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1)"
                            :style="{ transform: isNodeExpanded(item.node.id) ? 'rotate(180deg)' : 'rotate(0deg)' }"
                          />
                          <view
                            v-else
                            class="i-carbon-chevron-down text-[16px] text-[#A3A3A3] transition-transform duration-300"
                            style="transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1)"
                            :style="{ transform: isNodeExpanded(item.node.id) ? 'rotate(180deg)' : 'rotate(0deg)' }"
                          />
                        </view>
                      </template>
                      <view v-else :class="getNodeIndicatorClass(item)" />
                    </view>

                    <view class="min-w-0 flex-1" :style="{ marginLeft: `${getNodeContentIndent(item)}px` }">
                      <view class="line-clamp-2 text-[#222] leading-snug tracking-wide" :class="getNodeTitleClass(item)">
                        {{ item.node.name }}
                      </view>
                    </view>
                  </view>

                  <view
                    class="ml-3 shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold"
                    :class="isTabSelected(item.node.id) ? 'bg-[#ECFDF5] text-[#059669]' : 'bg-[#F0F9FF] text-[#0284C7]'"
                    @click.stop="addSelectedTab(item)"
                  >
                    {{ isTabSelected(item.node.id) ? '已添加' : '添加' }}
                  </view>
                </view>
              </view>
            </view>
          </view>
        </template>

        <view v-else class="mt-4 rounded-2xl bg-white/85 px-5 py-10 text-center shadow-sm">
          <view class="text-[15px] text-[#1E293B] font-semibold">
            当前领域还没有可用的刷题分类
          </view>
          <view class="mt-1 text-[12px] text-[#94A3B8]">
            可以先在后台补充 {{ currentDomainOption.label }} 对应的题库目录或知识点分类
          </view>
        </view>
      </scroll-view>
    </view>

    <LoginModal v-model="showLoginModal" @success="handleLoginSuccess" />
  </view>
</template>
