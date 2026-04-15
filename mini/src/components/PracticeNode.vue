<script lang="ts" setup>
import { computed } from 'vue'
import PracticeNode from './PracticeNode.vue'

defineOptions({ name: 'PracticeNode' })

const props = withDefaults(
  defineProps<{
    node: any
    depth: number
    isFirstLeaf?: boolean
    isLastLeaf?: boolean
    parentShowProgress?: boolean
    parentShowContinue?: boolean
    selectMode?: boolean
    selectedKeys?: Set<string>
    onSelectChange?: (nodeId: string, selected: boolean) => void
    primaryColor?: string
    onGroupTap?: (node: any) => boolean | void
    onToggleTap?: (node: any) => void
    onLeafTap?: (node: any) => void
  }>(),
  {
    parentShowProgress: true,
    parentShowContinue: true,
    selectMode: false,
    primaryColor: '#3B82F6',
  },
)

const hasChildren = computed(() => {
  return props.node.children && props.node.children.length > 0
})

const nodeId = computed(() => {
  return `${props.node.bank_id ?? ''}_${props.node.id ?? ''}_${props.node.name}`
})

const isSelected = computed(() => {
  return props.selectedKeys?.has(nodeId.value) ?? false
})

function toggleSelect() {
  props.onSelectChange?.(nodeId.value, !isSelected.value)
}

const showProgress = computed(() => {
  if (props.parentShowProgress === false) return false
  if (props.node?.hideProgress === true) return false

  return true
})

const showContinueAllowed = computed(() => {
  if (props.parentShowContinue === false) return false
  if (props.node?.hideContinue === true) return false

  return true
})

const contentIndentPx = computed(() => {
  return 0
})

const wrongCount = computed(() => {
  const candidates = [
    props.node?.wrong,
    props.node?.wrong_count,
    props.node?.wrongCount,
    props.node?.error,
    props.node?.error_count,
    props.node?.errorCount,
  ]

  for (const c of candidates) {
    const n = Number(c)
    if (Number.isFinite(n) && n > 0) return n
  }

  return 0
})

const progressBar = computed(() => {
  const total = Math.max(0, Number(props.node?.total ?? 0))
  const done = Math.min(total, Math.max(0, Number(props.node?.progress ?? 0)))
  const wrong = Math.min(done, Math.max(0, wrongCount.value))
  const correct = Math.max(0, done - wrong)

  if (total <= 0) {
    return { correctWidth: '0%', wrongWidth: '0%', wrongLeft: '0%' }
  }

  const correctPct = Math.min(100, (correct / total) * 100)
  const wrongPct = Math.min(100 - correctPct, (wrong / total) * 100)

  return {
    correctWidth: `${correctPct}%`,
    wrongWidth: `${wrongPct}%`,
    wrongLeft: `${correctPct}%`,
  }
})

function handleToggleExpand() {
  if (!hasChildren.value) return

  if (props.onToggleTap) {
    props.onToggleTap(props.node)
    return
  }

  props.node.expanded = !props.node.expanded
}

function handleRowTap() {
  if (hasChildren.value) {
    const result = props.onGroupTap?.(props.node)
    if (result === false) return

    if (!props.onGroupTap) {
      props.node.expanded = !props.node.expanded
    }

    return
  }

  if (props.onLeafTap) {
    props.onLeafTap(props.node)
    return
  }

  uni.showToast({ title: '已进入练习: ' + props.node.name, icon: 'none' })
}

function checkIsFirstLeaf(child: any, idx: number) {
  if (child.children && child.children.length > 0) return false
  if (idx === 0) return true
  const prevChild = props.node.children[idx - 1]
  if (prevChild && prevChild.children && prevChild.children.length > 0) return true
  return false
}

function checkIsLastLeaf(child: any, idx: number) {
  if (child.children && child.children.length > 0) return false
  if (idx === props.node.children.length - 1) return true
  const nextChild = props.node.children[idx + 1]
  if (nextChild && nextChild.children && nextChild.children.length > 0) return true
  return false
}
</script>

<template>
  <view class="w-full">
    <!-- 如果是目录节点 -->
      <view 
        v-if="hasChildren" 
        class="py-4 border-[#F4F4F4] active:bg-gray-50 transition-colors"
        :class="{ 'border-b': depth > 0 }"
        :style="{ paddingLeft: '20px', paddingRight: '20px' }"
        @click="handleRowTap"
      >
      <view class="flex items-start justify-between">
        <view class="min-w-0 flex flex-1 items-start">
          <!-- 指示器不随层级缩进 -->
          <view class="mt-[2px] w-[20px] h-[20px] flex items-center justify-center shrink-0" @click.stop="handleToggleExpand">
            <!-- 层级 0：强调态指示器 -->
            <template v-if="depth === 0">
              <view class="h-[16px] w-[16px] rounded-full bg-[#3B82F6] flex items-center justify-center">
                <view
                  class="i-carbon-chevron-down text-[12px] text-white transition-transform duration-300"
                  style="transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1)"
                  :style="{ transform: node.expanded ? 'rotate(180deg)' : 'rotate(0deg)' }"
                />
               </view>
            </template>
            <!-- 层级 1：次级指示器 -->
            <template v-else-if="depth === 1">
              <view class="h-[16px] w-[16px] rounded-full bg-[#E5E7EB] flex items-center justify-center">
                <view
                  class="i-carbon-chevron-down text-[12px] text-white transition-transform duration-300"
                  style="transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1)"
                  :style="{ transform: node.expanded ? 'rotate(180deg)' : 'rotate(0deg)' }"
                />
              </view>
            </template>
            <!-- 层级 2+：极简线形箭头 -->
            <template v-else>
              <view
                class="i-carbon-chevron-down text-[16px] text-[#A3A3A3] transition-transform duration-300"
                style="transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1)"
                :style="{ transform: node.expanded ? 'rotate(180deg)' : 'rotate(0deg)' }"
              />
            </template>
          </view>

          <!-- 内容不随层级缩进，和进度条左边界对齐 -->
          <view :style="{ marginLeft: (12 + contentIndentPx) + 'px' }">
            <text class="line-clamp-2 text-[15px] text-[#222] leading-snug tracking-wide" :class="depth === 0 ? 'font-bold' : 'font-medium'">{{ node.name }}</text>
          </view>
        </view>
        <view class="shrink-0 whitespace-nowrap">
          <template v-if="selectMode">
            <view
              class="h-[18px] w-[18px] flex items-center justify-center rounded transition-all duration-200"
              :style="{
                border: `1.5px solid ${isSelected ? primaryColor : '#94A3B8'}`,
                backgroundColor: isSelected ? primaryColor : 'transparent',
              }"
              @click.stop="toggleSelect"
            >
              <view v-if="isSelected" class="i-carbon-checkmark text-[12px] text-white" />
            </view>
          </template>
          <template v-else>
            <slot name="right" :node="node" :depth="depth" :has-children="hasChildren" :show-continue="showContinueAllowed">
              <view class="i-carbon-chevron-right text-lg text-[#D1D5DB]" />
            </slot>
          </template>
        </view>
      </view>
      
      <slot name="meta" :node="node" :depth="depth" :has-children="hasChildren" :show-progress="showProgress">
        <!-- 进度条区域：不随层级缩进，并且和标题对齐 -->
        <view v-if="showProgress" class="mt-2 flex items-center gap-3 text-[12px] text-[#A3A3A3]" :style="{ paddingLeft: (32 + contentIndentPx) + 'px' }">
          <view class="w-1/2 h-[5px] bg-[#E2E8F0] rounded-full overflow-hidden shrink-0 relative">
            <view
              class="absolute left-0 top-0 h-full bg-[#3B82F6] transition-all duration-300"
              :style="{ width: progressBar.correctWidth }"
            />
            <view
              class="absolute top-0 h-full bg-[#EF4444] transition-all duration-300"
              :style="{ left: progressBar.wrongLeft, width: progressBar.wrongWidth, minWidth: wrongCount > 0 ? '2px' : '0' }"
            />
          </view>
          <text class="tracking-wider">{{ node.progress }}/{{ node.total }}</text>
        </view>
        <view v-else-if="node.desc" class="mt-1 pl-[32px] text-[11px] text-[#94A3B8]">
          {{ node.desc }}
        </view>
      </slot>
    </view>

    <!-- 叶子节点 -->
    <view 
      v-else
      class="relative py-4 bg-[#F8FAFC] active:bg-[#F1F5F9] transition-colors"
      :class="[
        isFirstLeaf ? 'rounded-t-[16px] mt-2' : '',
        isLastLeaf ? 'rounded-b-[16px] mb-2 border-none' : 'border-b border-[#F1F5F9]'
      ]"
      :style="{ paddingLeft: '20px', paddingRight: '20px' }"
      @click="handleRowTap"
    >
        <view class="flex items-start justify-between">
          <view class="min-w-0 flex flex-1 items-start">
            <view class="w-[20px] h-[20px] flex items-center justify-center shrink-0">
              <view class="h-1.5 w-1.5 rounded-full bg-[#CBD5E1]" />
            </view>
            <view :style="{ marginLeft: (12 + contentIndentPx) + 'px' }">
              <text class="line-clamp-2 text-[14px] text-[#222] font-medium leading-snug tracking-wide">{{ node.name }}</text>
            </view>
          </view>
          <view class="shrink-0 whitespace-nowrap">
            <template v-if="selectMode">
              <view
                class="h-[18px] w-[18px] flex items-center justify-center rounded transition-all duration-200"
                :style="{
                  border: `1.5px solid ${isSelected ? primaryColor : '#94A3B8'}`,
                  backgroundColor: isSelected ? primaryColor : 'transparent',
                }"
                @click.stop="toggleSelect"
              >
                <view v-if="isSelected" class="i-carbon-checkmark text-[12px] text-white" />
              </view>
            </template>
            <template v-else>
              <slot name="right" :node="node" :depth="depth" :has-children="hasChildren" :show-continue="showContinueAllowed">
                <view class="i-carbon-chevron-right text-lg text-[#D1D5DB]" />
              </slot>
            </template>
          </view>
        </view>

        <slot name="meta" :node="node" :depth="depth" :has-children="hasChildren" :show-progress="showProgress">
          <!-- 进度条区域：不随层级缩进，并且和标题对齐 -->
          <view v-if="showProgress" class="mt-2 flex items-center gap-3 text-[12px] text-[#A3A3A3]" :style="{ paddingLeft: (32 + contentIndentPx) + 'px' }">
            <view class="w-1/2 h-[5px] bg-[#E2E8F0] rounded-full overflow-hidden shrink-0 relative">
              <view
                class="absolute left-0 top-0 h-full bg-[#3B82F6] transition-all duration-300"
                :style="{ width: progressBar.correctWidth }"
              />
              <view
                class="absolute top-0 h-full bg-[#EF4444] transition-all duration-300"
                :style="{ left: progressBar.wrongLeft, width: progressBar.wrongWidth, minWidth: wrongCount > 0 ? '2px' : '0' }"
              />
            </view>
            <text class="tracking-wider">{{ node.progress }}/{{ node.total }}</text>
          </view>
          <view v-else-if="node.desc" class="mt-1 pl-[32px] text-[11px] text-[#94A3B8]">
            {{ node.desc }}
          </view>
        </slot>
    </view>

    <!-- 子容器 (带高度过渡动画) -->
    <view 
      v-if="hasChildren" 
      class="accordion-wrapper" 
      :class="node.expanded ? 'expanded' : 'collapsed'"
    >
      <view class="accordion-inner">
        <PracticeNode 
          v-for="(child, idx) in node.children" 
          :key="child.id" 
          :node="child" 
          :depth="depth + 1"
          :parent-show-progress="showProgress"
          :parent-show-continue="showContinueAllowed"
          :select-mode="selectMode"
          :selected-keys="selectedKeys"
          :on-select-change="onSelectChange"
          :primary-color="primaryColor"
          :on-group-tap="onGroupTap"
          :on-toggle-tap="onToggleTap"
          :on-leaf-tap="onLeafTap"
          :is-first-leaf="checkIsFirstLeaf(child, idx)"
          :is-last-leaf="checkIsLastLeaf(child, idx)"
        />
      </view>
    </view>

  </view>
</template>

<style scoped>
.accordion-wrapper {
  overflow: hidden;
  max-height: 0;
}
.accordion-wrapper.expanded {
  transition: max-height 0.42s cubic-bezier(0.25, 1, 0.5, 1);
  max-height: 3000px;
}
.accordion-wrapper.collapsed {
  transition: max-height 0.28s cubic-bezier(0.4, 0, 1, 1);
  max-height: 0;
}
.accordion-inner {
  transition:
    opacity 0.18s ease,
    transform 0.28s ease;
  opacity: 0;
  transform: translateY(-6px);
}
.accordion-wrapper.expanded .accordion-inner {
  opacity: 1;
  transform: translateY(0);
}
</style>
