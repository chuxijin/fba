import {
  DEFAULT_STUDY_DOMAIN,
  normalizeStudyDomainCode,
  type StudyDomainCode,
} from './studyDomain'

export type AppThemeMode = 'light' | 'dark'
export type AppPracticeMode = 'practice' | 'exam' | 'memorize'
export type RandomPracticeYearRange = 'unlimited' | 'last_3_years' | 'last_5_years'

export type AppSettings = {
  currentDomain: StudyDomainCode
  randomPracticeCount: number
  randomPracticeYearRange: RandomPracticeYearRange
  themeMode: AppThemeMode
  practiceMode: AppPracticeMode
  wrongMasteryStreak: number
}

const STORAGE_KEY = 'app_settings'
const DEFAULT_RANDOM_PRACTICE_COUNT = 20
const DEFAULT_RANDOM_PRACTICE_YEAR_RANGE: RandomPracticeYearRange = 'unlimited'
const DEFAULT_WRONG_MASTERY_STREAK = 3
const VALID_MASTERY_STREAKS = [1, 2, 3, 5]

function normalizeRandomPracticeCount(value: unknown) {
  const count = Number(value)
  if (!Number.isFinite(count))
    return DEFAULT_RANDOM_PRACTICE_COUNT

  return Math.min(100, Math.max(10, Math.round(count / 10) * 10))
}

function normalizeThemeMode(value: unknown): AppThemeMode {
  return value === 'dark' ? 'dark' : 'light'
}

function normalizePracticeMode(value: unknown): AppPracticeMode {
  return value === 'exam' || value === 'memorize' ? value : 'practice'
}

function normalizeRandomPracticeYearRange(value: unknown): RandomPracticeYearRange {
  if (value === 'last_3_years' || value === 'last_5_years') {
    return value
  }
  return 'unlimited'
}

function normalizeWrongMasteryStreak(value: unknown): number {
  const num = Number(value)
  if (!Number.isFinite(num) || !VALID_MASTERY_STREAKS.includes(num))
    return DEFAULT_WRONG_MASTERY_STREAK
  return num
}

export function getDefaultAppSettings(): AppSettings {
  return {
    currentDomain: DEFAULT_STUDY_DOMAIN,
    randomPracticeCount: DEFAULT_RANDOM_PRACTICE_COUNT,
    randomPracticeYearRange: DEFAULT_RANDOM_PRACTICE_YEAR_RANGE,
    themeMode: 'light',
    practiceMode: 'practice',
    wrongMasteryStreak: DEFAULT_WRONG_MASTERY_STREAK,
  }
}

export function getAppSettings(): AppSettings {
  const fallback = getDefaultAppSettings()

  try {
    const raw = uni.getStorageSync(STORAGE_KEY)
    if (!raw)
      return fallback

    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    return {
      currentDomain: normalizeStudyDomainCode(parsed?.currentDomain),
      randomPracticeCount: normalizeRandomPracticeCount(parsed?.randomPracticeCount),
      randomPracticeYearRange: normalizeRandomPracticeYearRange(parsed?.randomPracticeYearRange),
      themeMode: normalizeThemeMode(parsed?.themeMode),
      practiceMode: normalizePracticeMode(parsed?.practiceMode),
      wrongMasteryStreak: normalizeWrongMasteryStreak(parsed?.wrongMasteryStreak),
    }
  }
  catch {
    return fallback
  }
}

export function applyThemeMode(themeMode: AppThemeMode) {
  const isDark = themeMode === 'dark'
  const backgroundColor = isDark ? '#0F172A' : '#F8FCF9'
  const frontColor = isDark ? '#ffffff' : '#000000'

  try {
    uni.setNavigationBarColor({
      frontColor,
      backgroundColor,
      animation: {
        duration: 180,
        timingFunc: 'easeIn',
      },
    })
  }
  catch {}

  try {
    uni.setBackgroundColor({
      backgroundColor,
      backgroundColorTop: backgroundColor,
      backgroundColorBottom: backgroundColor,
    })
  }
  catch {}

  // #ifdef H5
  try {
    document.documentElement.dataset.theme = themeMode
    document.documentElement.style.setProperty('--wot-color-theme', isDark ? '#34D399' : '#018d71')
    document.body.style.backgroundColor = backgroundColor
  }
  catch {}
  // #endif
}

export function saveAppSettings(nextSettings: Partial<AppSettings>) {
  const merged = {
    ...getAppSettings(),
    ...nextSettings,
  }

  const normalized: AppSettings = {
    currentDomain: normalizeStudyDomainCode(merged.currentDomain),
    randomPracticeCount: normalizeRandomPracticeCount(merged.randomPracticeCount),
    randomPracticeYearRange: normalizeRandomPracticeYearRange(merged.randomPracticeYearRange),
    themeMode: normalizeThemeMode(merged.themeMode),
    practiceMode: normalizePracticeMode(merged.practiceMode),
    wrongMasteryStreak: normalizeWrongMasteryStreak(merged.wrongMasteryStreak),
  }

  uni.setStorageSync(STORAGE_KEY, JSON.stringify(normalized))
  applyThemeMode(normalized.themeMode)
  return normalized
}
