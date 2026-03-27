<script lang="ts" setup>
import type { FeedbackType } from '@fba/api-sdk'
import { computed, ref } from 'vue'
import {
  createFeedbackPayload,
  FEEDBACK_MAX_CONTENT_LENGTH,
  FEEDBACK_MAX_IMAGES,
  FEEDBACK_TYPE_OPTIONS,
  getDefaultFeedbackType,
  submitFeedback,
  uploadFeedbackImage,
} from '@/utils/feedback'

const props = withDefaults(defineProps<{
  title?: string
  subtitle?: string
  submitText?: string
  cancelText?: string
  showCancel?: boolean
  feedbackType?: FeedbackType | null
  sourceApp?: string | null
  sourcePlatform?: string | null
  pagePath?: string | null
  targetType?: string | null
  targetId?: string | number | null
  targetText?: string | null
}>(), {
  title: '意见反馈',
  subtitle: '告诉我们你遇到的问题，我们会尽快处理',
  submitText: '提交反馈',
  cancelText: '取消',
  showCancel: false,
  feedbackType: null,
  sourceApp: null,
  sourcePlatform: null,
  pagePath: null,
  targetType: null,
  targetId: null,
  targetText: null,
})

const emit = defineEmits<{
  success: []
  cancel: []
}>()

const selectedType = ref<FeedbackType>(props.feedbackType || getDefaultFeedbackType())
const content = ref('')
const images = ref<string[]>([])
const submitting = ref(false)
const uploading = ref(false)

const remainingCount = computed(() => Math.max(0, FEEDBACK_MAX_CONTENT_LENGTH - content.value.length))
const hasTargetContext = computed(() => Boolean(props.targetText))
const feedbackTypeColumns = computed(() =>
  FEEDBACK_TYPE_OPTIONS.map(item => ({
    label: item.label,
    value: item.value,
  })),
)
const selectedTypeMeta = computed(() =>
  FEEDBACK_TYPE_OPTIONS.find(item => item.value === selectedType.value) || FEEDBACK_TYPE_OPTIONS[0],
)

const toneClassMap: Record<string, { chip: string, icon: string }> = {
  rose: {
    chip: 'border-[#FBCFE8] bg-[#FFF1F5] text-[#BE185D]',
    icon: 'bg-[#FFF1F5] text-[#E11D48]',
  },
  amber: {
    chip: 'border-[#FDE68A] bg-[#FFF7E8] text-[#B45309]',
    icon: 'bg-[#FFF7E8] text-[#D97706]',
  },
  sky: {
    chip: 'border-[#BFDBFE] bg-[#EEF6FF] text-[#1D4ED8]',
    icon: 'bg-[#EEF6FF] text-[#2563EB]',
  },
  violet: {
    chip: 'border-[#DDD6FE] bg-[#F5F3FF] text-[#7C3AED]',
    icon: 'bg-[#F5F3FF] text-[#8B5CF6]',
  },
  emerald: {
    chip: 'border-[#A7F3D0] bg-[#ECFDF5] text-[#047857]',
    icon: 'bg-[#ECFDF5] text-[#059669]',
  },
  slate: {
    chip: 'border-[#CBD5E1] bg-[#F8FAFC] text-[#475569]',
    icon: 'bg-[#F8FAFC] text-[#64748B]',
  },
}

function previewImage(current: string) {
  uni.previewImage({
    current,
    urls: images.value,
  })
}

function removeImage(index: number) {
  images.value.splice(index, 1)
}

async function chooseImages() {
  if (uploading.value) {
    return
  }

  const remainCount = FEEDBACK_MAX_IMAGES - images.value.length
  if (remainCount <= 0) {
    uni.showToast({
      title: `最多上传 ${FEEDBACK_MAX_IMAGES} 张截图`,
      icon: 'none',
    })
    return
  }

  try {
    const result = await new Promise<UniApp.ChooseMediaSuccessCallbackResult>((resolve, reject) => {
      uni.chooseMedia({
        count: remainCount,
        mediaType: ['image'],
        sourceType: ['album', 'camera'],
        success: resolve,
        fail: reject,
      })
    })

    const filePaths = (result.tempFiles || [])
      .map((item: any) => item.tempFilePath || item.path || '')
      .filter(Boolean)

    if (!filePaths.length) {
      return
    }

    uploading.value = true
    for (const filePath of filePaths) {
      const imageUrl = await uploadFeedbackImage(filePath)
      images.value.push(imageUrl)
    }

    uni.showToast({
      title: '截图上传成功',
      icon: 'success',
    })
  }
  catch (error: any) {
    if (error?.errMsg?.includes('cancel')) {
      return
    }

    if (error?.message === 'FEEDBACK_UPLOAD_LOGIN_REQUIRED') {
      uni.showToast({
        title: '登录后可上传截图',
        icon: 'none',
      })
      return
    }

    console.error('Feedback image upload error:', error)
    uni.showToast({
      title: '截图上传失败，请重试',
      icon: 'none',
    })
  }
  finally {
    uploading.value = false
  }
}

async function handleSubmit() {
  const trimmedContent = content.value.trim()
  if (!trimmedContent) {
    uni.showToast({
      title: '请先填写反馈内容',
      icon: 'none',
    })
    return
  }

  if (submitting.value || uploading.value) {
    return
  }

  submitting.value = true
  try {
    const payload = createFeedbackPayload(
      {
        feedbackType: selectedType.value,
        content: trimmedContent,
        images: images.value,
      },
      {
        sourceApp: props.sourceApp,
        sourcePlatform: props.sourcePlatform,
        pagePath: props.pagePath,
        targetType: props.targetType,
        targetId: props.targetId,
        targetText: props.targetText,
      },
    )

    await submitFeedback(payload)
    uni.showToast({
      title: '反馈已提交，感谢支持',
      icon: 'success',
    })
    emit('success')
  }
  catch (error) {
    console.error('Submit feedback error:', error)
    uni.showToast({
      title: '提交失败，请稍后重试',
      icon: 'none',
    })
  }
  finally {
    submitting.value = false
  }
}
</script>

<template>
  <view class="w-full overflow-x-hidden space-y-4">
    <view class="overflow-hidden rounded-[28px] from-[#F4E8FF] via-[#F9F3FF] to-[#FFFFFF] bg-gradient-to-b px-5 py-5 shadow-[0_12px_40px_-24px_rgba(139,92,246,0.45)]">
      <view class="flex items-start justify-between gap-4">
        <view class="min-w-0 flex-1">
          <view class="text-[20px] text-[#1E293B] font-black tracking-wide">
            {{ title }}
          </view>
          <view class="mt-1 break-words text-[12px] text-[#64748B] leading-5">
            {{ subtitle }}
          </view>
        </view>

        <view class="h-11 w-11 shrink-0 flex items-center justify-center rounded-2xl bg-white text-[#8B5CF6] shadow-sm">
          <view class="i-carbon-idea text-[22px]" />
        </view>
      </view>
    </view>

    <view class="overflow-hidden rounded-[28px] border border-white/70 bg-white/92 p-5 shadow-[0_10px_30px_-18px_rgba(15,23,42,0.18)] backdrop-blur-md">
      <view class="text-[13px] text-[#475569] font-bold tracking-wide">
        反馈类型
      </view>
      <wd-select-picker
        v-model="selectedType"
        class="mt-3 block"
        :columns="feedbackTypeColumns"
        type="radio"
        title="选择反馈类型"
        placeholder="请选择反馈类型"
        :show-confirm="false"
        use-default-slot
      >
        <view
          class="flex items-center gap-3 rounded-3xl border px-4 py-4 transition-transform active:scale-[0.98]"
          :class="toneClassMap[selectedTypeMeta.tone]?.chip"
        >
          <view
            class="h-10 w-10 shrink-0 flex items-center justify-center rounded-2xl"
            :class="toneClassMap[selectedTypeMeta.tone]?.icon"
          >
            <view class="i-carbon-dot-mark text-base" />
          </view>
          <view class="min-w-0 flex-1">
            <view class="text-[14px] font-black">
              {{ selectedTypeMeta.label }}
            </view>
            <view class="mt-1 break-words text-[11px] opacity-80 leading-4">
              {{ selectedTypeMeta.hint }}
            </view>
          </view>
          <view class="h-8 w-8 shrink-0 flex items-center justify-center rounded-full bg-white/85 text-current">
            <view class="i-carbon-chevron-down text-base" />
          </view>
        </view>
      </wd-select-picker>
    </view>

    <view v-if="hasTargetContext" class="overflow-hidden rounded-[28px] border border-white/70 bg-white/92 p-5 shadow-[0_10px_30px_-18px_rgba(15,23,42,0.16)]">
      <view class="text-[13px] text-[#475569] font-bold tracking-wide">
        当前反馈位置
      </view>
      <view class="mt-3 space-y-3 text-[12px] text-[#64748B]">
        <view v-if="targetText" class="rounded-2xl bg-[#F8FAFC] px-3.5 py-3">
          <view class="text-[11px] text-[#94A3B8]">关联内容</view>
          <view class="mt-1 break-words text-[#334155] leading-5">
            {{ targetText }}
          </view>
        </view>
      </view>
    </view>

    <view class="overflow-hidden rounded-[28px] border border-white/70 bg-white/92 p-5 shadow-[0_10px_30px_-18px_rgba(15,23,42,0.16)]">
      <view class="flex items-center justify-between">
        <view class="text-[13px] text-[#475569] font-bold tracking-wide">
          详细描述
        </view>
        <view class="text-[11px]" :class="remainingCount < 40 ? 'text-[#DC2626]' : 'text-[#94A3B8]'">
          还可输入 {{ remainingCount }} 字
        </view>
      </view>

      <view class="mt-3 rounded-3xl bg-[#F8FAFC] px-4 py-4">
        <textarea
          v-model="content"
          class="box-border block h-38 max-w-full w-full text-[14px] text-[#334155] leading-6"
          :maxlength="FEEDBACK_MAX_CONTENT_LENGTH"
          placeholder="请尽量描述清楚问题现象、出现步骤、期望结果。若是题目问题，也可以说明是题干、答案还是解析有误。"
          placeholder-class="text-[#94A3B8]"
        />
      </view>

      <view class="mt-4 flex items-center justify-between">
        <view class="text-[13px] text-[#475569] font-bold tracking-wide">
          截图附件
        </view>
        <view class="text-[11px] text-[#94A3B8]">
          最多 {{ FEEDBACK_MAX_IMAGES }} 张，登录后可上传
        </view>
      </view>

      <view class="mt-3 flex flex-wrap gap-3">
        <view
          v-for="(item, index) in images"
          :key="item"
          class="relative h-22 w-22 overflow-hidden rounded-3xl bg-[#F8FAFC]"
        >
          <image class="h-full w-full" :src="item" mode="aspectFill" @click="previewImage(item)" />
          <view
            class="absolute right-2 top-2 h-6 w-6 flex items-center justify-center rounded-full bg-black/55 text-white"
            @click.stop="removeImage(index)"
          >
            <view class="i-carbon-close text-xs" />
          </view>
        </view>

        <view
          v-if="images.length < FEEDBACK_MAX_IMAGES"
          class="h-22 w-22 flex flex-col items-center justify-center rounded-3xl border border-dashed border-[#D8B4FE] bg-[#FAF5FF] text-[#8B5CF6] transition-transform active:scale-[0.98]"
          @click="chooseImages"
        >
          <view class="i-carbon-add text-2xl" />
          <view class="mt-1 text-[11px] font-bold">
            {{ uploading ? '上传中...' : '添加截图' }}
          </view>
        </view>
      </view>
    </view>

    <view class="flex gap-3">
      <view
        v-if="showCancel"
        class="h-12 flex-1 flex items-center justify-center rounded-full border border-[#E2E8F0] bg-white text-[15px] text-[#475569] font-bold active:scale-[0.98]"
        @click="emit('cancel')"
      >
        {{ cancelText }}
      </view>

      <view
        class="h-12 flex flex-1 items-center justify-center rounded-full from-[#A855F7] to-[#7C3AED] bg-gradient-to-r text-[15px] text-white font-black shadow-[0_12px_28px_-18px_rgba(124,58,237,0.75)] active:scale-[0.98]"
        @click="handleSubmit"
      >
        {{ submitting ? '提交中...' : submitText }}
      </view>
    </view>
  </view>
</template>
