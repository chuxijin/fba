<script lang="ts" setup>
export type AnswerSheetStatus = 'active' | 'correct' | 'wrong' | 'answered' | 'unanswered' | 'default'

export interface AnswerSheetItem {
  id: number | string
  seq_no: number
  status: AnswerSheetStatus
}

export interface AnswerSheetGroup {
  title: string
  items: AnswerSheetItem[]
}

const props = withDefaults(defineProps<{
  groups: AnswerSheetGroup[]
  cols?: number
}>(), {
  cols: 7,
})

const emit = defineEmits<{
  select: [item: AnswerSheetItem]
}>()

const toneMap: Record<AnswerSheetStatus, string> = {
  active: 'bg-[#059669] text-white',
  correct: 'bg-[#DCFCE7] text-[#15803D]',
  wrong: 'bg-[#FFEDD5] text-[#EA580C]',
  answered: 'bg-[#FEF3C7] text-[#B45309]',
  unanswered: 'bg-[#F1F5F9] text-[#94A3B8]',
  default: 'bg-[#E2E8F0] text-[#475569]',
}

function getTone(status: AnswerSheetStatus) {
  return toneMap[status] || toneMap.default
}
</script>

<template>
  <view v-for="(group, gi) in props.groups" :key="gi" class="pb-3">
    <view
      v-if="group.title"
      class="mb-2 mt-1 text-[12px] text-[#94A3B8]"
      :class="gi > 0 ? 'border-t border-[#E2E8F0] pt-3' : ''"
    >
      {{ group.title }}
    </view>
    <view class="grid gap-2" :style="{ gridTemplateColumns: `repeat(${props.cols}, minmax(0, 1fr))` }">
      <view
        v-for="item in group.items"
        :key="item.id"
        class="h-9 flex items-center justify-center rounded-xl text-[13px] font-bold active:scale-95"
        :class="getTone(item.status)"
        @click="emit('select', item)"
      >
        {{ item.seq_no }}
      </view>
    </view>
  </view>
</template>
