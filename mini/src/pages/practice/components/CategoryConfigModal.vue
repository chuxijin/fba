<script lang="ts" setup>
import { computed, nextTick, ref, watch } from 'vue'

defineOptions({
  name: 'CategoryConfigModal',
})

const props = defineProps<{
  modelValue: boolean
  categories: CategoryNode[]
  selectedTabs: SelectedTabItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'update:selectedTabs': [value: SelectedTabItem[]]
}>()

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

type AppTabCode = 'gongkao' | '考研'

interface SelectedTabItem {
  id: number
  name: string
  appCode: AppTabCode
}

interface TypeSection {
  key: string
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

const appTabs: Array<{ code: AppTabCode, title: string, hint: string }> = [
  { code: 'gongkao', title: '考公', hint: '行政编制 · 事业单位 · 公职类' },
  { code: '考研', title: '考研', hint: '统考专业课 · 初复试备考' },
]

const activeApp = ref<AppTabCode>('gongkao')
const tabsRef = ref<any>(null)
const selectedTabsState = ref<SelectedTabItem[]>([])
const expandedByApp = ref<Record<AppTabCode, number[]>>({
  gongkao: [],
  考研: [],
})
const collapsedSectionsByApp = ref<Record<AppTabCode, string[]>>({
  gongkao: [],
  考研: [],
})

const appTypeMap: Record<AppTabCode, string[]> = {
  gongkao: ['subject', 'knowledge_point'],
  考研: ['subject'],
}

const typeLabelMap: Record<string, string> = {
  subject: '科目方向',
  knowledge_point: '知识点',
  exam: '考试项目',
  resource: '资料资源',
  org: '机构来源',
  default: '分类体系',
}

const typeHintMap: Record<string, string> = {
  subject: '按科目或题型浏览刷题方向',
  knowledge_point: '按知识点脉络整理刷题分类',
  exam: '按考试场景组织练习入口',
  resource: '配套资料与学习材料分类',
  org: '按题源或机构维度整理',
  default: '当前应用下的分类树',
}

function formatTypeLabel(type?: string | null) {
  if (!type)
    return typeLabelMap.default
  return typeLabelMap[type] || type.replace(/_/g, ' ').replace(/\b\w/g, s => s.toUpperCase())
}

function formatTypeHint(type?: string | null) {
  if (!type)
    return typeHintMap.default
  return typeHintMap[type] || '分类树结构'
}

function countCategoryNodes(nodes: CategoryNode[] | null | undefined): number {
  let total = 0
  for (const node of nodes || []) {
    total += 1
    if (node.children?.length)
      total += countCategoryNodes(node.children)
  }
  return total
}

function normalizeValue(value?: string | null) {
  return String(value || '').trim()
}

function cloneCategoryTree(nodes: CategoryNode[] | null | undefined): CategoryNode[] {
  return (nodes || []).map(node => ({
    ...node,
    children: cloneCategoryTree(node.children),
  }))
}

function filterCategoryTreeByAppAndType(
  nodes: CategoryNode[] | null | undefined,
  appCode: AppTabCode,
  targetType: string,
) {
  const result: CategoryNode[] = []
  const normalizedAppCode = normalizeValue(appCode)
  const normalizedType = normalizeValue(targetType)

  for (const node of nodes || []) {
    const isCurrentMatch = normalizeValue(node.app_code) === normalizedAppCode
      && normalizeValue(node.type) === normalizedType

    if (isCurrentMatch) {
      result.push({
        ...node,
        children: cloneCategoryTree(node.children),
      })
      continue
    }

    const children = filterCategoryTreeByAppAndType(node.children, appCode, targetType)
    if (children.length)
      result.push(...children)
  }

  return result.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
}

function getSectionsForApp(appCode: AppTabCode): TypeSection[] {
  const allowedTypes = appTypeMap[appCode] || []

  return allowedTypes
    .map((type) => {
      const nodes = filterCategoryTreeByAppAndType(props.categories || [], appCode, type)
      if (!nodes.length)
        return null

      return {
        key: type,
        title: formatTypeLabel(type),
        hint: formatTypeHint(type),
        nodes,
        total: countCategoryNodes(nodes),
      }
    })
    .filter((section): section is TypeSection => Boolean(section))
}

const currentAppIndex = computed(() => {
  const index = appTabs.findIndex(item => item.code === activeApp.value)
  return index >= 0 ? index : 0
})

function buildVisibleItems(
  nodes: CategoryNode[] | null | undefined,
  expandedIds: number[],
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

    if (hasChildren && expandedIds.includes(node.id))
      result.push(...buildVisibleItems(node.children, expandedIds, depth + 1))
  }

  return result
}

function ensureDefaultExpanded(appCode: AppTabCode) {
  if (expandedByApp.value[appCode]?.length)
    return

  const rootIds = getSectionsForApp(appCode)
    .flatMap(section => section.nodes)
    .filter(item => item.children?.length)
    .map(item => item.id)

  expandedByApp.value = {
    ...expandedByApp.value,
    [appCode]: rootIds,
  }
}

function getExpandedIds(appCode: AppTabCode) {
  return expandedByApp.value[appCode] || []
}

function isExpanded(appCode: AppTabCode, id: number) {
  return getExpandedIds(appCode).includes(id)
}

function getCollapsedSectionKeys(appCode: AppTabCode) {
  return collapsedSectionsByApp.value[appCode] || []
}

function isSectionExpanded(appCode: AppTabCode, sectionKey: string) {
  return !getCollapsedSectionKeys(appCode).includes(sectionKey)
}

function getSectionSummaryText(appCode: AppTabCode) {
  const sections = getSectionsForApp(appCode)
  if (!sections.length)
    return '当前应用下还没有可用分类'
  return `当前共 ${sections.length} 个 type 分组`
}

function getVisibleItemsBySection(appCode: AppTabCode, nodes: CategoryNode[]) {
  return buildVisibleItems(nodes, getExpandedIds(appCode))
}

function getItemKey(sectionKey: string, item: VisibleCategoryItem) {
  return `${sectionKey}-${item.node.id}-${item.depth}`
}

function getSectionItemKey(appCode: AppTabCode, sectionKey: string, item: VisibleCategoryItem) {
  return getItemKey(`${appCode}-${sectionKey}`, item)
}

function getSectionArrowStyle(appCode: AppTabCode, sectionKey: string) {
  return {
    transform: isSectionExpanded(appCode, sectionKey) ? 'rotate(180deg)' : 'rotate(0deg)',
  }
}

function getSectionToggleText(appCode: AppTabCode, sectionKey: string) {
  return isSectionExpanded(appCode, sectionKey) ? '收起' : '展开'
}

function getItemOffsetStyle(item: VisibleCategoryItem) {
  return {
    marginLeft: `${item.depth * 14}px`,
  }
}

function getNodeCardClass(appCode: AppTabCode, item: VisibleCategoryItem) {
  if (!item.hasChildren)
    return 'bg-[#F8FAFC] shadow-sm'

  if (isExpanded(appCode, item.node.id))
    return 'bg-[#F7FFFA] shadow-[0_10px_24px_rgba(16,185,129,0.10)] ring-1 ring-[#D1FAE5]'

  return 'bg-[#FCFFFD] shadow-sm active:scale-[0.99]'
}

function getNodeArrowStyle(appCode: AppTabCode, item: VisibleCategoryItem) {
  return {
    transform: isExpanded(appCode, item.node.id) ? 'rotate(180deg)' : 'rotate(0deg)',
  }
}

function toggleNode(appCode: AppTabCode, item: VisibleCategoryItem) {
  if (!item.hasChildren)
    return

  const current = [...getExpandedIds(appCode)]
  const index = current.indexOf(item.node.id)
  if (index >= 0)
    current.splice(index, 1)
  else
    current.push(item.node.id)

  expandedByApp.value = {
    ...expandedByApp.value,
    [appCode]: current,
  }
}

function toggleSection(appCode: AppTabCode, sectionKey: string) {
  const current = [...getCollapsedSectionKeys(appCode)]
  const index = current.indexOf(sectionKey)
  if (index >= 0)
    current.splice(index, 1)
  else
    current.push(sectionKey)

  collapsedSectionsByApp.value = {
    ...collapsedSectionsByApp.value,
    [appCode]: current,
  }
}

function emitSelectedTabs() {
  emit('update:selectedTabs', [...selectedTabsState.value])
}

function getSelectedTabsByApp(appCode: AppTabCode) {
  return selectedTabsState.value.filter(item => item.appCode === appCode)
}

function getSelectedTabKey(appCode: AppTabCode, id: number) {
  return `${appCode}-${id}`
}

function isTabSelected(appCode: AppTabCode, id: number) {
  return selectedTabsState.value.some(item => item.appCode === appCode && item.id === id)
}

function addSelectedTab(appCode: AppTabCode, item: VisibleCategoryItem) {
  if (isTabSelected(appCode, item.node.id)) {
    uni.showToast({ title: '这个首页Tab已经添加了', icon: 'none' })
    return
  }

  selectedTabsState.value = [
    ...selectedTabsState.value,
    {
      id: item.node.id,
      name: item.node.name,
      appCode,
    },
  ]
  emitSelectedTabs()
}

function removeSelectedTab(id: number) {
  selectedTabsState.value = selectedTabsState.value.filter(item => item.id !== id)
  emitSelectedTabs()
}

function moveSelectedTab(appCode: AppTabCode, id: number, direction: 'up' | 'down') {
  const currentList = [...selectedTabsState.value]
  const appIndexes = currentList
    .map((item, index) => item.appCode === appCode ? index : -1)
    .filter(index => index >= 0)

  const currentIndex = appIndexes.findIndex(index => currentList[index]?.id === id)
  if (currentIndex < 0)
    return

  const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1
  if (targetIndex < 0 || targetIndex >= appIndexes.length)
    return

  const from = appIndexes[currentIndex]
  const to = appIndexes[targetIndex]
  const temp = currentList[from]
  currentList[from] = currentList[to]
  currentList[to] = temp

  selectedTabsState.value = currentList
  emitSelectedTabs()
}

function closeModal() {
  emit('update:modelValue', false)
}

function updateTabsLine() {
  nextTick(() => {
    tabsRef.value?.updateLineStyle?.(false)
  })
}

function handlePopupAfterEnter() {
  ensureDefaultExpanded(activeApp.value)
  updateTabsLine()
}

function handleAppChange() {
  ensureDefaultExpanded(activeApp.value)
  updateTabsLine()
}

function handleSwiperChange(e: any) {
  const nextIndex = e?.detail?.current ?? 0
  activeApp.value = appTabs[nextIndex]?.code || appTabs[0].code
  ensureDefaultExpanded(activeApp.value)
  updateTabsLine()
}

watch(() => props.modelValue, (visible) => {
  if (visible) {
    ensureDefaultExpanded(activeApp.value)
    updateTabsLine()
  }
})

watch(() => props.selectedTabs, (value) => {
  selectedTabsState.value = [...(value || [])]
}, { immediate: true, deep: true })

watch(() => props.categories, () => {
  ensureDefaultExpanded(activeApp.value)
})
</script>

<template>
  <wd-popup
    :model-value="modelValue"
    position="bottom"
    transition="slide-up"
    :safe-area-inset-bottom="true"
    :lock-scroll="false"
    :z-index="999999"
    custom-class="category-config-popup"
    custom-style="height: 78vh; border-radius: 32rpx 32rpx 0 0; overflow: hidden; background: #F6FBF8;"
    @update:model-value="$emit('update:modelValue', $event)"
    @after-enter="handlePopupAfterEnter"
  >
    <view class="h-full flex flex-col overflow-hidden">
      <view class="shrink-0 border-b border-white/70 from-[#E7F8EF] to-[#F6FBF8] bg-gradient-to-b px-5 pb-2 pt-4">
        <view class="flex items-start justify-between gap-3">
          <view class="min-w-0">
            <view class="text-[19px] text-[#166534] font-black tracking-[0.5px]">
              分类配置
            </view>
            <view class="mt-1 text-[12px] text-[#648172]">
              先按应用查看分类体系，后面我们继续接首页 tab 的自定义逻辑
            </view>
          </view>
          <view
            class="h-8 w-8 flex shrink-0 items-center justify-center rounded-full bg-white/85 text-[#6B7280] shadow-sm transition-transform active:scale-95"
            @click="closeModal"
          >
            <view class="i-carbon-close text-[18px]" />
          </view>
        </view>

        <view class="mt-3 rounded-[20px] bg-white/80 px-3 pt-2 shadow-[0_8px_24px_rgba(15,118,110,0.08)] backdrop-blur-sm">
          <wd-tabs
            ref="tabsRef"
            v-model="activeApp"
            animated
            auto-line-width
            color="#166534"
            inactive-color="#64748B"
            @change="handleAppChange"
          >
            <wd-tab
              v-for="app in appTabs"
              :key="app.code"
              :title="app.title"
              :name="app.code"
            >
              <view class="pb-1" />
            </wd-tab>
          </wd-tabs>
        </view>
      </view>

      <swiper
        class="flex-1"
        :current="currentAppIndex"
        :duration="280"
        @change="handleSwiperChange"
      >
        <swiper-item v-for="app in appTabs" :key="app.code">
          <scroll-view
            scroll-y
            class="box-border h-full min-h-0 px-5 pb-2 pt-2"
            style="height: 100%;"
            :show-scrollbar="false"
          >
            <view class="overflow-hidden border border-white/70 rounded-[22px] bg-white/88 shadow-[0_10px_28px_rgba(148,163,184,0.10)]">
              <view class="border-b border-[#ECFDF5] from-[#F6FFFA] to-[#F8FAFC] bg-gradient-to-r px-4 pb-3 pt-4">
                <view class="flex items-center justify-between gap-3">
                  <view>
                    <view class="text-[15px] text-[#14532D] font-bold">
                      已添加首页Tab
                    </view>
                    <view class="mt-1 text-[11px] text-[#6B7280]">
                      {{ getSelectedTabsByApp(app.code).length ? '可以上移下移调整首页顺序' : '先从下方分类里添加想展示的Tab' }}
                    </view>
                  </view>
                  <view class="shrink-0 rounded-full bg-[#ECFDF5] px-2.5 py-1 text-[11px] text-[#059669] font-semibold">
                    {{ getSelectedTabsByApp(app.code).length }} 个
                  </view>
                </view>
              </view>

              <view v-if="getSelectedTabsByApp(app.code).length" class="flex flex-col gap-2.5 px-3 py-3">
                <view
                  v-for="(selected, index) in getSelectedTabsByApp(app.code)"
                  :key="getSelectedTabKey(app.code, selected.id)"
                  class="flex items-center gap-3 border border-white/70 rounded-2xl bg-[#FCFFFD] px-4 py-3 shadow-sm"
                >
                  <view class="h-9 w-9 flex shrink-0 items-center justify-center rounded-xl bg-[#ECFDF5] text-[#10B981] shadow-inner">
                    <view class="i-carbon-book text-[18px]" />
                  </view>
                  <view class="min-w-0 flex-1">
                    <view class="truncate text-[14px] text-[#1E293B] font-bold">
                      {{ selected.name }}
                    </view>
                    <view class="mt-0.5 text-[11px] text-[#94A3B8]">
                      首页第 {{ index + 1 }} 个Tab
                    </view>
                  </view>
                  <view class="flex shrink-0 items-center gap-2">
                    <view
                      class="h-7 w-7 flex items-center justify-center border border-[#E2E8F0] rounded-full bg-white text-[#64748B]"
                      @click="moveSelectedTab(app.code, selected.id, 'up')"
                    >
                      <view class="i-carbon-arrow-up text-[15px]" />
                    </view>
                    <view
                      class="h-7 w-7 flex items-center justify-center border border-[#E2E8F0] rounded-full bg-white text-[#64748B]"
                      @click="moveSelectedTab(app.code, selected.id, 'down')"
                    >
                      <view class="i-carbon-arrow-down text-[15px]" />
                    </view>
                    <view
                      class="h-7 w-7 flex items-center justify-center rounded-full bg-[#FEF2F2] text-[#EF4444]"
                      @click="removeSelectedTab(selected.id)"
                    >
                      <view class="i-carbon-close text-[15px]" />
                    </view>
                  </view>
                </view>
              </view>

              <view v-else class="px-4 py-6 text-center text-[12px] text-[#94A3B8]">
                还没有添加首页Tab
              </view>
            </view>

            <view v-if="loading" class="mt-4 rounded-2xl bg-white/85 px-5 py-10 text-center shadow-sm">
              <view class="text-[15px] text-[#1E293B] font-semibold">
                分类数据加载中...
              </view>
              <view class="mt-1 text-[12px] text-[#94A3B8]">
                正在从真实后端读取应用分类树
              </view>
            </view>

            <template v-else-if="getSectionsForApp(app.code).length">
              <view
                v-for="section in getSectionsForApp(app.code)"
                :key="section.key"
                class="mt-4 overflow-hidden border border-white/70 rounded-[24px] bg-white/88 shadow-[0_10px_30px_rgba(148,163,184,0.10)] backdrop-blur-sm"
              >
                <view
                  class="from-[#F6FFFA] to-[#F8FAFC] bg-gradient-to-r px-4 pb-3 pt-4"
                  :class="isSectionExpanded(app.code, section.key) ? 'border-b border-[#ECFDF5]' : ''"
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
                      @click.stop="toggleSection(app.code, section.key)"
                    >
                      <view class="text-[11px] text-[#059669] font-semibold">
                        {{ getSectionToggleText(app.code, section.key) }}
                      </view>
                      <view class="rounded-full bg-[#ECFDF5] px-2.5 py-1 text-[11px] text-[#059669] font-semibold">
                        {{ section.total }} 项
                      </view>
                      <view
                        class="i-carbon-chevron-down text-[18px] text-[#94A3B8] transition-transform duration-300"
                        :style="getSectionArrowStyle(app.code, section.key)"
                      />
                    </view>
                  </view>
                </view>

                <view v-show="isSectionExpanded(app.code, section.key)" class="flex flex-col gap-2.5 px-3 py-3">
                  <view
                    v-for="item in getVisibleItemsBySection(app.code, section.nodes)"
                    :key="getSectionItemKey(app.code, section.key, item)"
                    class="relative transition-all duration-200"
                    :style="getItemOffsetStyle(item)"
                  >
                    <view
                      v-if="item.depth > 0"
                      class="absolute bottom-3.5 left-[-9px] top-3.5 w-[2px] rounded-full from-[#BBF7D0] to-[#E2E8F0] bg-gradient-to-b"
                    />

                    <view
                      class="border border-white/70 rounded-2xl px-4 py-3 transition-all duration-200"
                      :class="getNodeCardClass(app.code, item)"
                      @click="toggleNode(app.code, item)"
                    >
                      <view class="flex items-center gap-3">
                        <view class="min-w-0 flex-1">
                          <view class="truncate text-[14px] text-[#1E293B] font-bold">
                            {{ item.node.name }}
                          </view>
                        </view>

                        <view
                          class="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold"
                          :class="isTabSelected(app.code, item.node.id) ? 'bg-[#ECFDF5] text-[#059669]' : 'bg-[#F0F9FF] text-[#0284C7]'"
                          @click.stop="addSelectedTab(app.code, item)"
                        >
                          {{ isTabSelected(app.code, item.node.id) ? '已添加' : '添加' }}
                        </view>

                        <view
                          v-if="item.hasChildren"
                          class="i-carbon-chevron-down shrink-0 text-[18px] text-[#94A3B8] transition-transform duration-300"
                          :style="getNodeArrowStyle(app.code, item)"
                        />
                      </view>
                    </view>
                  </view>
                </view>
              </view>
            </template>

            <view v-else class="mt-4 rounded-2xl bg-white/85 px-5 py-10 text-center shadow-sm">
              <view class="text-[15px] text-[#1E293B] font-semibold">
                这个应用下还没有分类
              </view>
              <view class="mt-1 text-[12px] text-[#94A3B8]">
                可以先在后台补充对应 app_code 的分类数据
              </view>
            </view>
          </scroll-view>
        </swiper-item>
      </swiper>
    </view>
  </wd-popup>
</template>

<style scoped>
:deep(.category-config-popup) {
  border-radius: 32rpx 32rpx 0 0;
}
</style>
