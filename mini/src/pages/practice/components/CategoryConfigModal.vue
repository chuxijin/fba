<script lang="ts" setup>
import { computed, ref, watch } from 'vue'
import {
  getStudyDomainOption,
  type StudyDomainCode,
} from '@/utils/studyDomain'

defineOptions({
  name: 'CategoryConfigModal',
})

const props = defineProps<{
  modelValue: boolean
  currentDomain: StudyDomainCode
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

interface SelectedTabItem {
  id: number
  name: string
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

const selectedTabsState = ref<SelectedTabItem[]>([])
const expandedIds = ref<number[]>([])
const collapsedSectionKeys = ref<string[]>([])

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

const currentDomainOption = computed(() => getStudyDomainOption(props.currentDomain))

function normalizeValue(value?: string | null) {
  return String(value || '').trim().toLowerCase()
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

const sections = computed<TypeSection[]>(() => {
  return allowedTypes
    .map((type) => {
      const nodes = filterCategoryTreeByType(props.categories || [], type)
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

function emitSelectedTabs() {
  emit('update:selectedTabs', [...selectedTabsState.value])
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
  emitSelectedTabs()
}

function removeSelectedTab(id: number) {
  selectedTabsState.value = selectedTabsState.value.filter(item => item.id !== id)
  emitSelectedTabs()
}

function moveSelectedTab(id: number, direction: 'up' | 'down') {
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
  emitSelectedTabs()
}

function closeModal() {
  emit('update:modelValue', false)
}

function getNodeCardClass(item: VisibleCategoryItem) {
  if (!item.hasChildren) {
    return 'bg-[#F8FAFC] shadow-sm'
  }

  if (isNodeExpanded(item.node.id)) {
    return 'bg-[#F7FFFA] shadow-[0_10px_24px_rgba(16,185,129,0.10)] ring-1 ring-[#D1FAE5]'
  }

  return 'bg-[#FCFFFD] shadow-sm active:scale-[0.99]'
}

watch(() => props.modelValue, (visible) => {
  if (visible) {
    ensureDefaultExpanded()
  }
})

watch(() => props.selectedTabs, (value) => {
  selectedTabsState.value = [...(value || [])]
}, { immediate: true, deep: true })

watch(() => [props.currentDomain, props.categories], () => {
  expandedIds.value = []
  collapsedSectionKeys.value = []
  ensureDefaultExpanded()
}, { deep: true })
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
  >
    <view class="h-full flex flex-col overflow-hidden">
      <view class="shrink-0 border-b border-white/70 from-[#E7F8EF] to-[#F6FBF8] bg-gradient-to-b px-5 pb-2 pt-4">
        <view class="flex items-start justify-between gap-3">
          <view class="min-w-0">
            <view class="text-[19px] text-[#166534] font-black tracking-[0.5px]">
              分类配置
            </view>
            <view class="mt-1 text-[12px] text-[#648172]">
              当前领域：{{ currentDomainOption.label }}，从分类树里挑选首页展示的刷题 Tab
            </view>
          </view>
          <view
            class="h-8 w-8 flex shrink-0 items-center justify-center rounded-full bg-white/85 text-[#6B7280] shadow-sm transition-transform active:scale-95"
            @tap="closeModal"
          >
            <view class="i-carbon-close text-[18px]" />
          </view>
        </view>

        <view class="mt-3 overflow-hidden border border-white/70 rounded-2xl bg-white/88 shadow-[0_10px_28px_rgba(148,163,184,0.10)]">
          <view class="border-b border-[#ECFDF5] from-[#F6FFFA] to-[#F8FAFC] bg-gradient-to-r px-4 pb-3 pt-4">
            <view class="flex items-center justify-between gap-3">
              <view>
                <view class="text-[15px] text-[#14532D] font-bold">
                  已添加首页 Tab
                </view>
                <view class="mt-1 text-[11px] text-[#6B7280]">
                  {{ selectedTabsState.length ? '这里可以直接调整首页全局顺序' : '先从下方分类里添加想展示的 Tab' }}
                </view>
              </view>
              <view class="shrink-0 rounded-full bg-[#ECFDF5] px-2.5 py-1 text-[11px] text-[#059669] font-semibold">
                {{ selectedTabsState.length }} 个
              </view>
            </view>
          </view>

          <scroll-view v-if="selectedTabsState.length" scroll-y :show-scrollbar="false" class="box-border max-h-[160px] w-full">
            <view class="flex flex-col gap-2.5 px-3 py-3">
              <view
                v-for="(selected, index) in selectedTabsState"
                :key="selected.id"
                class="border border-white/70 rounded-xl bg-[#FCFFFD] px-3.5 py-3 shadow-sm"
              >
                <view class="flex items-center gap-3">
                  <view class="min-w-0 flex-1">
                    <view class="truncate text-[14px] text-[#1E293B] font-semibold leading-[20px]">
                      {{ selected.name }}
                    </view>
                  </view>

                  <view class="flex shrink-0 items-center gap-1.5">
                    <view
                      class="h-8 w-8 flex items-center justify-center rounded-full bg-[#F8FAFC] text-[#64748B] transition-transform active:scale-95"
                      :class="index === 0 ? 'opacity-35' : ''"
                      @tap.stop="moveSelectedTab(selected.id, 'up')"
                    >
                      <view class="i-carbon-chevron-up text-[16px]" />
                    </view>
                    <view
                      class="h-8 w-8 flex items-center justify-center rounded-full bg-[#F8FAFC] text-[#64748B] transition-transform active:scale-95"
                      :class="index === selectedTabsState.length - 1 ? 'opacity-35' : ''"
                      @tap.stop="moveSelectedTab(selected.id, 'down')"
                    >
                      <view class="i-carbon-chevron-down text-[16px]" />
                    </view>
                    <view
                      class="h-8 w-8 flex items-center justify-center rounded-full bg-[#FEF2F2] text-[#EF4444] transition-transform active:scale-95"
                      @tap.stop="removeSelectedTab(selected.id)"
                    >
                      <view class="i-carbon-close text-[15px]" />
                    </view>
                  </view>
                </view>
              </view>
            </view>
          </scroll-view>

          <view v-else class="px-4 py-6 text-center text-[12px] text-[#94A3B8]">
            还没有添加首页 Tab
          </view>
        </view>
      </view>

      <scroll-view
        scroll-y
        class="box-border h-full min-h-0 px-5 pb-2 pt-2"
        style="height: 100%;"
        :show-scrollbar="false"
      >
        <view v-if="loading" class="mt-4 rounded-2xl bg-white/85 px-5 py-10 text-center shadow-sm">
          <view class="text-[15px] text-[#1E293B] font-semibold">
            分类数据加载中...
          </view>
          <view class="mt-1 text-[12px] text-[#94A3B8]">
            正在从真实后端读取当前领域分类树
          </view>
        </view>

        <template v-else-if="sections.length">
          <view
            v-for="section in sections"
            :key="section.key"
            class="mt-4 overflow-hidden border border-white/70 rounded-2xl bg-white/88 shadow-[0_10px_30px_rgba(148,163,184,0.10)] backdrop-blur-sm"
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

            <view v-show="isSectionExpanded(section.key)" class="flex flex-col gap-2.5 px-3 py-3">
              <view
                v-for="item in getVisibleItemsBySection(section.nodes)"
                :key="`${section.key}-${item.node.id}-${item.depth}`"
                class="relative transition-all duration-200"
                :style="{ marginLeft: `${item.depth * 14}px` }"
              >
                <view
                  v-if="item.depth > 0"
                  class="absolute bottom-3.5 left-[-9px] top-3.5 w-[2px] rounded-full from-[#BBF7D0] to-[#E2E8F0] bg-gradient-to-b"
                />

                <view
                  class="border border-white/70 rounded-xl px-4 py-3 transition-all duration-200"
                  :class="getNodeCardClass(item)"
                  @click="toggleNode(item)"
                >
                  <view class="flex items-center gap-3">
                    <view class="min-w-0 flex-1">
                      <view class="truncate text-[14px] text-[#1E293B] font-bold">
                        {{ item.node.name }}
                      </view>
                    </view>

                    <view
                      class="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold"
                      :class="isTabSelected(item.node.id) ? 'bg-[#ECFDF5] text-[#059669]' : 'bg-[#F0F9FF] text-[#0284C7]'"
                      @click.stop="addSelectedTab(item)"
                    >
                      {{ isTabSelected(item.node.id) ? '已添加' : '添加' }}
                    </view>

                    <view
                      v-if="item.hasChildren"
                      class="i-carbon-chevron-down shrink-0 text-[18px] text-[#94A3B8] transition-transform duration-300"
                      :style="{ transform: isNodeExpanded(item.node.id) ? 'rotate(180deg)' : 'rotate(0deg)' }"
                    />
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
  </wd-popup>
</template>

<style scoped>
:deep(.category-config-popup) {
  border-radius: 32rpx 32rpx 0 0;
}
</style>
