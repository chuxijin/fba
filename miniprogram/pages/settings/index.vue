<template>
  <view class="settings-page">
    <!-- 设置项列表 -->
    <view class="settings-content">
      <!-- 做题模式 -->
      <view class="section">
        <view class="section-title">学习设置</view>
        <u-cell-group :border="false">
          <u-cell
            title="做题模式"
            :isLink="true"
            @click="showPracticeModeSelector = true"
          >
            <template #icon>
              <text class="setting-icon">📝</text>
            </template>
            <template #value>
              <text class="setting-value">{{ practiceModeLabel }}</text>
            </template>
          </u-cell>
        </u-cell-group>
      </view>

      <!-- 其他设置（预留） -->
      <!-- <view class="section">
        <view class="section-title">通用设置</view>
        <u-cell-group :border="false">
          <u-cell title="主题模式" :isLink="true">
            <template #icon>
              <text class="setting-icon">🌙</text>
            </template>
            <template #value>
              <text class="setting-value">跟随系统</text>
            </template>
          </u-cell>
        </u-cell-group>
      </view> -->
    </view>

    <!-- 做题模式选择器 -->
    <u-action-sheet
      :show="showPracticeModeSelector"
      :actions="practiceModeActions"
      title="选择做题模式"
      @close="showPracticeModeSelector = false"
      @select="handlePracticeModeSelect"
    ></u-action-sheet>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { PracticeMode } from '@/components/business/question-map'
import { getStudyPreference, updateStudyPreference } from '@/api/business/user-settings'

declare const uni: any

interface ActionItem {
  name: string
  value: PracticeMode
  subname?: string
}

// 当前选择的做题模式
const currentPracticeMode = ref<PracticeMode>('practice')
const showPracticeModeSelector = ref(false)
const isLoading = ref(false)

// 做题模式选项
const practiceModeActions = ref<ActionItem[]>([
  {
    name: '刷题模式',
    value: 'practice',
    subname: '快速刷题，答完自动跳转，最后查看总分和错题'
  },
  {
    name: '练题模式',
    value: 'exercise',
    subname: '深度练习，答题后立即显示解析'
  },
  {
    name: '背题模式',
    value: 'memorize',
    subname: '直接查看题目和答案，适合考前记忆'
  }
])

// 当前模式的中文标签
const practiceModeLabel = computed(() => {
  const modeMap: Record<PracticeMode, string> = {
    practice: '刷题模式',
    exercise: '练题模式',
    memorize: '背题模式'
  }
  return modeMap[currentPracticeMode.value] || '刷题模式'
})

// 页面加载时从后端读取
onMounted(async () => {
  try {
    isLoading.value = true
    const response = await getStudyPreference()
    currentPracticeMode.value = response.practice_mode || 'practice'
    // 同步到本地存储，用于离线访问
    uni.setStorageSync('practice_mode', currentPracticeMode.value)
    console.log('[设置] 从后端读取到做题模式:', currentPracticeMode.value)
  } catch (error) {
    console.error('[设置] 读取做题模式失败:', error)
    // 失败时从本地存储读取
    const savedMode = uni.getStorageSync('practice_mode') as PracticeMode
    if (savedMode) {
      currentPracticeMode.value = savedMode
    } else {
      currentPracticeMode.value = 'practice'
    }
  } finally {
    isLoading.value = false
  }
})

// 选择做题模式
async function handlePracticeModeSelect(item: ActionItem) {
  // 🔥 立即更新本地状态和本地存储，确保立即生效
  currentPracticeMode.value = item.value
  uni.setStorageSync('practice_mode', item.value)
  console.log('[设置] 已保存做题模式到本地存储:', item.value)

  try {
    // 然后同步到后端
    await updateStudyPreference({ practice_mode: item.value })
    console.log('[设置] 已同步做题模式到后端:', item.value)

    uni.showToast({
      title: `已切换到${item.name}`,
      icon: 'success',
      duration: 1500
    })
  } catch (error) {
    console.error('[设置] 同步到后端失败:', error)
    uni.showToast({
      title: `已切换到${item.name}（离线模式）`,
      icon: 'success',
      duration: 1500
    })
  } finally {
    showPracticeModeSelector.value = false
  }
}
</script>

<style scoped lang="scss">
.settings-page {
  min-height: 100vh;
  background: #f8f9fa;
}

.settings-content {
  padding: 0 0 32rpx;
}

.section {
  margin-top: 32rpx;
}

.section-title {
  padding: 0 32rpx 16rpx;
  font-size: 26rpx;
  font-weight: 600;
  color: #94a3b8;
}

.setting-icon {
  font-size: 36rpx;
  margin-right: 16rpx;
}

.setting-value {
  font-size: 28rpx;
  color: #64748b;
  margin-right: 8rpx;
}
</style>
