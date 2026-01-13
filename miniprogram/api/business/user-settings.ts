/**
 * 用户设置相关 API
 */

import { get, put } from '../request'
import type { PracticeMode } from '@/components/business/question-map'
import type { CustomTab } from '@/composables/useCustomTabs'

/** ==================== 类型定义 ==================== */

/** 学习偏好设置 */
export interface StudyPreferenceSettings {
  /** 做题模式 */
  practice_mode: PracticeMode
  /** 自定义 Tab 列表 */
  custom_tabs: CustomTab[]
}

/** 更新学习偏好参数 */
export interface UpdateStudyPreferenceParams {
  /** 做题模式 */
  practice_mode?: PracticeMode
  /** 自定义 Tab 列表 */
  custom_tabs?: CustomTab[]
}

/** 获取学习偏好响应 */
export interface GetStudyPreferenceResponse {
  /** 做题模式 */
  practice_mode: PracticeMode
  /** 自定义 Tab 列表 */
  custom_tabs: CustomTab[]
}

/** ==================== API 函数 ==================== */

/**
 * 获取学习偏好设置
 */
export function getStudyPreference(): Promise<GetStudyPreferenceResponse> {
  return get('/qbank/settings/study-preference')
}

/**
 * 更新学习偏好设置
 */
export function updateStudyPreference(params: UpdateStudyPreferenceParams): Promise<void> {
  return put('/qbank/settings/study-preference', params)
}
