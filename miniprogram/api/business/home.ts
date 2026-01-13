/**
 * 首页相关 API
 */

import { get, post } from '../request'

/** ==================== 类型定义 ==================== */

/** 每日练习明细 */
export interface DailyPractice {
  /** 日期 */
  date: string
  /** 做题数量 */
  count: number
  /** 答对数量 */
  correct_count: number
  /** 练习时长（秒） */
  duration: number
}

/** 本周刷题统计 */
export interface WeekPracticeStats {
  /** 本周做题总数 */
  total_count: number
  /** 本周答对数 */
  correct_count: number
  /** 本周正确率（0-100） */
  accuracy_rate: number
  /** 本周总时长（秒） */
  total_duration: number
  /** 每日明细 */
  daily_breakdown: DailyPractice[]
}

/** 打卡信息 */
export interface CheckInInfo {
  /** 连续打卡天数 */
  check_in_streak: number
  /** 累计打卡天数 */
  total_check_in_days: number
  /** 今日是否已打卡 */
  is_checked_in_today: boolean
  /** 今日做题数 */
  today_practice_count: number
}

/** 用户排名信息 */
export interface UserRankInfo {
  /** 击败用户百分比（0-100） */
  beat_percentage: number
  /** 当前排名 */
  current_rank: number
  /** 总用户数 */
  total_users: number
  /** 昨日排名 */
  yesterday_rank: number | null
  /** 排名变化（正数=上升，负数=下降） */
  rank_change: number | null
}

/** 首页Dashboard数据 */
export interface HomeDashboardData {
  /** 打卡信息 */
  check_in: CheckInInfo
  /** 本周刷题统计 */
  week_stats: WeekPracticeStats
  /** 排名信息 */
  rank: UserRankInfo
  /** 累计做题数 */
  total_questions: number
  /** 累计答对数 */
  total_correct: number
  /** 总体正确率（0-100） */
  overall_accuracy: number
}

/** 打卡参数 */
export interface CheckInParam {
  /** 当日做题数 */
  practice_count: number
  /** 当日练习时长（秒） */
  practice_duration: number
}

/** 打卡日历单日数据 */
export interface CheckInCalendarDay {
  /** 日期 */
  date: string
  /** 是否已打卡 */
  is_checked_in: boolean
  /** 做题数量 */
  practice_count: number
}

/** 打卡日历数据 */
export interface CheckInCalendarData {
  /** 年份 */
  year: number
  /** 月份 */
  month: number
  /** 每日打卡数据 */
  days: CheckInCalendarDay[]
  /** 本月打卡天数 */
  total_check_in_days: number
}

/** 排行榜用户信息 */
export interface RankUserInfo {
  /** 用户 ID */
  user_id: number
  /** 昵称 */
  nickname: string
  /** 头像 URL */
  avatar: string | null
}

/** 排行榜条目 */
export interface RankItem {
  /** 排名 */
  rank: number
  /** 用户信息 */
  user: RankUserInfo
  /** 统计值（刷题数/正确率/坚持天数） */
  value: number
  /** 是否为当前用户 */
  is_current_user: boolean
}

/** 排行榜列表数据 */
export interface RankListData {
  /** 排行榜类型（practice_count/accuracy_rate/streak_days） */
  rank_type: string
  /** 当前用户排名（可能不在前100） */
  current_user_rank: RankItem | null
  /** 排行榜用户列表 */
  top_users: RankItem[]
}

/** ==================== API 函数 ==================== */

/**
 * 获取首页Dashboard数据
 */
export async function getHomeDashboard(): Promise<HomeDashboardData> {
  return get('/qbank/home/dashboard')
}

/**
 * 用户打卡
 */
export async function checkIn(params: CheckInParam): Promise<void> {
  return post('/qbank/home/check-in', params)
}

/**
 * 获取打卡日历
 */
export async function getCheckInCalendar(params?: {
  year?: number
  month?: number
}): Promise<CheckInCalendarData> {
  return get('/qbank/home/check-in-calendar', params)
}

/**
 * 获取排行榜列表
 */
export async function getRankList(params?: {
  rank_type?: 'practice_count' | 'accuracy_rate' | 'streak_days'
  limit?: number
}): Promise<RankListData> {
  return get('/qbank/home/rank', params)
}
