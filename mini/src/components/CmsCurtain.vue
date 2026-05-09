<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/sdk'

const props = defineProps<{
  /** 触发场景，如 app_launch / home */
  scene: string
}>()

interface SlotItem {
  id: number
  code: string
  slot_type: string
  title: string | null
  image_url: string | null
  jump_type: string
  jump_target: string | null
  jump_extra: Record<string, any> | null
  can_close: boolean
  extra: Record<string, any> | null
}

const showCurtain = ref(false)
const curtainData = ref<SlotItem | null>(null)

const curtainWidth = computed(() => curtainData.value?.extra?.width ?? 280)
const closePosition = computed(() => curtainData.value?.extra?.close_position ?? 'bottom')

async function fetchCurtain() {
  console.log('[CmsCurtain] fetchCurtain called, scene =', props.scene)
  try {
    const { data: slotsData } = await api.getActiveSlots({ query: { scene: props.scene } }) as any
    const slots = slotsData as SlotItem[]
    console.log('[CmsCurtain] slots response:', JSON.stringify(slots))
    const list = Array.isArray(slots) ? slots : []
    // 找第一个 curtain 类型且有图片的运营位
    const curtain = list.find((s) => s.slot_type === 'curtain' && s.image_url)
    console.log('[CmsCurtain] matched curtain:', curtain)
    if (curtain) {
      curtainData.value = curtain
      showCurtain.value = true
      reportAction(curtain.id, 0)
    }
  }
  catch (err) {
    console.error('[CmsCurtain] fetchCurtain error:', err)
  }
}

async function reportAction(slotId: number, action: number) {
  try {
    await api.reportAction({
      path: { pk: slotId },
      body: { action, scene: props.scene },
    })
  }
  catch {
    // 静默
  }
}

function handleClick() {
  if (!curtainData.value) return
  reportAction(curtainData.value.id, 1)

  const { jump_type, jump_target, jump_extra } = curtainData.value
  if (!jump_target) return

  if (jump_type === 'url') {
    uni.navigateTo({ url: jump_target })
  }
  else if (jump_type === 'miniprogram') {
    uni.navigateToMiniProgram({
      appId: jump_extra?.appId ?? '',
      path: jump_target,
      ...jump_extra,
    })
  }
  else if (jump_type === 'quest') {
    uni.navigateTo({ url: `/pages/quest-list/index?id=${jump_target}` })
  }
}

function handleClose() {
  if (curtainData.value) {
    reportAction(curtainData.value.id, 2)
  }
  showCurtain.value = false
}

onMounted(() => {
  fetchCurtain()
})
</script>

<template>
  <wd-curtain
    v-if="curtainData"
    v-model="showCurtain"
    :src="curtainData.image_url!"
    :width="curtainWidth"
    :close-position="closePosition"
    close-on-click-modal
    @click="handleClick"
    @close="handleClose"
  />
</template>
