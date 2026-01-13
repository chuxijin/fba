/**
 * 做题模式设置 composable
 *
 * 从本地存储读取用户设置的默认做题模式
 */
import { ref, onMounted } from 'vue'
import type { PracticeMode } from '@/components/business/question-map'

declare const uni: any

export function usePracticeModeSettings() {
  const practiceMode = ref<PracticeMode>('practice')

  /**
   * 获取用户设置的做题模式
   */
  function getPracticeMode(): PracticeMode {
    const savedMode = uni.getStorageSync('practice_mode') as PracticeMode
    if (savedMode && ['practice', 'exercise', 'memorize'].includes(savedMode)) {
      return savedMode
    }
    // 默认返回刷题模式
    return 'practice'
  }

  /**
   * 设置做题模式
   */
  function setPracticeMode(mode: PracticeMode) {
    practiceMode.value = mode
    uni.setStorageSync('practice_mode', mode)
  }

  /**
   * 初始化时加载
   */
  onMounted(() => {
    practiceMode.value = getPracticeMode()
  })

  return {
    practiceMode,
    getPracticeMode,
    setPracticeMode
  }
}
