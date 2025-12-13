/**
 * 计时器组合式函数
 *
 * 用于练习页面的计时功能，支持暂停、继续、重置
 */
import { ref, onBeforeUnmount } from 'vue'

export interface TimerOptions {
  /** 初始时间（秒），用于恢复未完成的会话 */
  initialSeconds?: number
  /** 更新间隔（毫秒） */
  interval?: number
}

export function useTimer(options: TimerOptions = {}) {
  const { initialSeconds = 0, interval = 1000 } = options

  // 状态
  const startTime = ref(Date.now() - initialSeconds * 1000)
  const pausedDuration = ref(0)
  const pauseStartTime = ref(0)
  const isPaused = ref(false)
  const timeText = ref(formatTime(initialSeconds * 1000))

  // 计时器句柄
  let timerHandle: ReturnType<typeof setTimeout> | null = null

  /**
   * 格式化毫秒为 MM:SS
   */
  function formatTime(ms: number): string {
    const totalSeconds = Math.floor(ms / 1000)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }

  /**
   * 获取已用时间（毫秒）
   */
  function getElapsedMs(): number {
    if (isPaused.value) {
      return pauseStartTime.value - startTime.value - pausedDuration.value
    }
    return Date.now() - startTime.value - pausedDuration.value
  }

  /**
   * 获取已用时间（秒）
   */
  function getElapsedSeconds(): number {
    return Math.floor(getElapsedMs() / 1000)
  }

  /**
   * 获取当前累计暂停时长（毫秒）
   *
   * 包含正在进行的暂停时间
   */
  function getCurrentPausedDuration(): number {
    if (isPaused.value) {
      return pausedDuration.value + (Date.now() - pauseStartTime.value)
    }
    return pausedDuration.value
  }

  /**
   * 更新显示时间
   */
  function updateDisplay() {
    if (!isPaused.value) {
      timeText.value = formatTime(getElapsedMs())
    }
    timerHandle = setTimeout(updateDisplay, interval)
  }

  /**
   * 切换暂停状态
   */
  function togglePause() {
    if (isPaused.value) {
      // 继续：累加暂停时长
      pausedDuration.value += Date.now() - pauseStartTime.value
      isPaused.value = false
    } else {
      // 暂停：记录暂停开始时间
      pauseStartTime.value = Date.now()
      isPaused.value = true
    }
  }

  /**
   * 重置计时器
   */
  function reset(newInitialSeconds = 0) {
    startTime.value = Date.now() - newInitialSeconds * 1000
    pausedDuration.value = 0
    pauseStartTime.value = 0
    isPaused.value = false
    timeText.value = formatTime(newInitialSeconds * 1000)
  }

  /**
   * 启动计时器
   */
  function start() {
    if (!timerHandle) {
      updateDisplay()
    }
  }

  /**
   * 停止计时器
   */
  function stop() {
    if (timerHandle) {
      clearTimeout(timerHandle)
      timerHandle = null
    }
  }

  // 组件卸载时清理
  onBeforeUnmount(() => {
    stop()
  })

  return {
    // 状态
    timeText,
    isPaused,
    startTime,
    pausedDuration,
    pauseStartTime,

    // 方法
    start,
    stop,
    reset,
    togglePause,
    getElapsedMs,
    getElapsedSeconds,
    getCurrentPausedDuration,
    formatTime,
  }
}
