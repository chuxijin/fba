<script lang="ts" setup>
import type { FeedbackType } from '@fba/api-sdk'
import FeedbackPanel from '@/components/FeedbackPanel.vue'

const props = withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  subtitle?: string
  submitText?: string
  feedbackType?: FeedbackType | null
  sourceApp?: string | null
  sourcePlatform?: string | null
  pagePath?: string | null
  targetType?: string | null
  targetId?: string | number | null
  targetText?: string | null
}>(), {
  title: '快速反馈',
  subtitle: '随时把问题告诉我们',
  submitText: '提交反馈',
  feedbackType: null,
  sourceApp: null,
  sourcePlatform: null,
  pagePath: null,
  targetType: null,
  targetId: null,
  targetText: null,
})

const emit = defineEmits<{
  'update:modelValue': [boolean]
  success: []
}>()

function closePopup() {
  emit('update:modelValue', false)
}

function handleSuccess() {
  closePopup()
  emit('success')
}
</script>

<template>
  <wd-popup
    :model-value="modelValue"
    position="bottom"
    custom-class="rounded-t-[20px] overflow-hidden bg-[#FAFAFA]"
    :safe-area-inset-bottom="true"
    :z-index="999999"
    custom-style="height:auto;max-height:88vh;"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <view class="box-border relative w-full overflow-x-hidden px-4 pb-5 pt-6">
      <view
        class="absolute right-4 top-4 z-20 h-8 w-8 flex items-center justify-center rounded-full bg-slate-100/70 text-slate-400 active:scale-90"
        @click="closePopup"
      >
        <view class="i-carbon-close text-lg" />
      </view>

      <scroll-view scroll-y class="box-border max-h-[78vh] w-full overflow-hidden pr-0.5">
        <FeedbackPanel
          v-if="modelValue"
          :title="title"
          :subtitle="subtitle"
          :submit-text="submitText"
          :show-cancel="true"
          :feedback-type="feedbackType"
          :source-app="sourceApp"
          :source-platform="sourcePlatform"
          :page-path="pagePath"
          :target-type="targetType"
          :target-id="targetId"
          :target-text="targetText"
          @cancel="closePopup"
          @success="handleSuccess"
        />
        <view class="h-safe-area-bottom w-full" />
      </scroll-view>
    </view>
  </wd-popup>
</template>
