<template>
  <view>
    <u-calendar
      :show="show"
      :default-date="defaultDate"
      mode="single"
      :max-date="maxDate"
      :min-date="minDate"
      :formatter="dateFormatter"
      :show-lunar="false"
      :show-title="true"
      :show-subtitle="true"
      :close-on-click-overlay="true"
      :round="20"
      @confirm="handleConfirm"
      @close="handleClose"
    >
      <!-- 底部统计信息插槽 -->
      <template #footer>
        <view class="calendar-stats">
          <view class="stat-item">
            <text class="stat-label">本月打卡</text>
            <text class="stat-value">{{ totalCheckInDays }}天</text>
          </view>
          <view class="stat-item">
            <text class="stat-label">连续打卡</text>
            <text class="stat-value">{{ checkInStreak }}天</text>
          </view>
        </view>
      </template>
    </u-calendar>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import * as homeApi from '@/api/business/home'

declare const uni: any

interface Props {
  show: boolean
  checkInStreak?: number
}

interface Emits {
  (e: 'update:show', value: boolean): void
}

const props = withDefaults(defineProps<Props>(), {
  checkInStreak: 0
})

const emit = defineEmits<Emits>()

// 日期范围设置
const defaultDate = ref<number[]>([])
const minDate = ref('')
const maxDate = ref('')

// 日历数据
const calendarData = ref<homeApi.CheckInCalendarData | null>(null)
const loading = ref(false)

const totalCheckInDays = computed(() => calendarData.value?.total_check_in_days || 0)

/**
 * 日期格式化函数（标记打卡日期）
 *
 * :param day: 日期对象
 */
function dateFormatter(day: any) {
  if (!calendarData.value) return day

  // 查找当前日期的打卡数据
  const dateStr = formatDateToString(new Date(day.date))
  const dayData = calendarData.value.days.find(d => d.date === dateStr)

  if (dayData && dayData.is_checked_in) {
    // 已打卡日期
    day.bottomInfo = `✓ ${dayData.practice_count}题`
    day.className = 'checked-day'
  } else {
    day.bottomInfo = ''
  }

  return day
}

/**
 * 格式化日期为字符串 YYYY-MM-DD
 *
 * :param date: 日期对象
 */
function formatDateToString(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * 加载打卡日历数据
 */
async function loadCalendarData() {
  try {
    loading.value = true

    const today = new Date()
    const year = today.getFullYear()
    const month = today.getMonth() + 1

    const data = await homeApi.getCheckInCalendar({
      year,
      month
    })

    calendarData.value = data

    // 设置默认选中今天
    const todayTimestamp = today.getTime()
    defaultDate.value = [todayTimestamp]

    // 设置日期范围（当前月份）
    const firstDay = new Date(year, month - 1, 1)
    const lastDay = new Date(year, month, 0)
    minDate.value = formatDateToString(firstDay)
    maxDate.value = formatDateToString(lastDay)

    console.log('[打卡日历] 数据加载成功:', data)
  } catch (error) {
    console.error('[打卡日历] 数据加载失败:', error)
    uni.showToast({
      title: '加载失败',
      icon: 'none'
    })
  } finally {
    loading.value = false
  }
}

/**
 * 日期确认事件（点击日期）
 */
function handleConfirm(value: any) {
  console.log('[打卡日历] 选中日期:', value)
  // 可以在这里处理日期点击事件，比如显示详情
}

/**
 * 关闭日历
 */
function handleClose() {
  emit('update:show', false)
}

// 监听 show 变化，打开时加载数据
watch(() => props.show, (newVal) => {
  if (newVal) {
    loadCalendarData()
  }
})
</script>

<style scoped lang="scss">
// 自定义打卡日期样式
::v-deep .checked-day {
  .u-calendar-month-day__text {
    color: #22c55e !important;
    font-weight: 600;
  }

  .u-calendar-month-day__bottom-info {
    color: #22c55e !important;
    font-size: 20rpx;
  }
}

// 统计信息样式
.calendar-stats {
  display: flex;
  gap: 16rpx;
  padding: 24rpx 32rpx 32rpx;
  border-top: 1rpx solid #e5e7eb;
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
  padding: 16rpx;
  background: #f8f9fa;
  border-radius: 12rpx;
}

.stat-label {
  font-size: 24rpx;
  color: #64748b;
}

.stat-value {
  font-size: 32rpx;
  font-weight: 600;
  color: #22c55e;
}
</style>
