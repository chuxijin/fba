<template>
  <div id="gk-floating-widget-wrapper">
    <!-- 展开态：精致微型卡片 -->
    <div v-if="!isCollapsed" class="gk-float-card">
      <button class="gk-float-close" title="收起悬浮窗" @click="isCollapsed = true">&times;</button>

      <!-- 试卷感知状态小标签 -->
      <div v-if="isReady" class="gk-float-status" :title="paperTitle">
        <span class="gk-status-dot"></span>
        <span class="gk-status-text">{{ questionCount > 0 ? `${questionCount} 题就绪` : '试卷已就绪' }}</span>
      </div>

      <div class="gk-float-btn-group">
        <!-- 主按钮 1: 开始排版 -->
        <button class="gk-float-btn-main" @click="$emit('startReformat')">
          开始排版
        </button>

        <!-- 副按钮 2: 快速打印 -->
        <button class="gk-float-btn-main" @click="$emit('quickPrint')">
          快速打印
        </button>

        <!-- 辅助按钮: 建议反馈 -->
        <button class="gk-float-btn-ghost" @click="$emit('feedback')">
          💬 建议反馈
        </button>
      </div>

      <!-- 底部品牌与版本 -->
      <div class="gk-float-footer">
        <div class="gk-brand-row">
          <img v-if="logoUrl" :src="logoUrl" class="gk-brand-logo" alt="Logo" />
          <span class="gk-brand-name">有岸 · 公考排版</span>
        </div>
        <div class="gk-brand-ver">V 1.0.0</div>
      </div>
    </div>

    <!-- 收起态：贴边小图标 -->
    <div
      v-else
      class="gk-float-collapsed-badge"
      title="点击展开公考内容排版"
      @click="isCollapsed = false"
    >
      <img v-if="logoUrl" :src="logoUrl" class="gk-badge-logo" alt="Logo" />
      <span v-else class="gk-badge-icon">📑</span>
      <span v-if="isReady" class="gk-badge-dot"></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  paperTitle: string
  questionCount: number
}>()

defineEmits<{
  (e: 'startReformat'): void
  (e: 'quickPrint'): void
  (e: 'feedback'): void
}>()

const isCollapsed = ref(false)
const isReady = computed(() => props.questionCount > 0 || Boolean(props.paperTitle))
const logoUrl = typeof chrome !== 'undefined' && chrome.runtime?.getURL ? chrome.runtime.getURL('icons/icon48.png') : ''
</script>
