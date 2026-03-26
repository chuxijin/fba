const STORAGE_KEY = 'qbank_study_preference_cache'

type StudyPreferenceCacheMap = Record<string, any>

let memoryCache: StudyPreferenceCacheMap | null = null

function normalizeUserKey(userId: unknown) {
  const id = Number(userId)
  return Number.isFinite(id) && id > 0 ? String(id) : ''
}

function loadCacheMap(): StudyPreferenceCacheMap {
  if (memoryCache)
    return memoryCache

  try {
    const raw = uni.getStorageSync(STORAGE_KEY)
    if (!raw) {
      memoryCache = {}
      return memoryCache
    }

    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    memoryCache = parsed && typeof parsed === 'object' ? parsed : {}
    return memoryCache
  }
  catch {
    memoryCache = {}
    return memoryCache
  }
}

function persistCacheMap(cacheMap: StudyPreferenceCacheMap) {
  memoryCache = cacheMap
  uni.setStorageSync(STORAGE_KEY, JSON.stringify(cacheMap))
}

export function getCachedStudyPreference(userId: unknown) {
  const key = normalizeUserKey(userId)
  if (!key)
    return null

  return loadCacheMap()[key] || null
}

export function setCachedStudyPreference(userId: unknown, value: any) {
  const key = normalizeUserKey(userId)
  if (!key)
    return value

  const cacheMap = loadCacheMap()
  cacheMap[key] = value
  persistCacheMap({ ...cacheMap })
  return value
}

export function mergeCachedStudyPreference(userId: unknown, partialValue: Record<string, any>) {
  const current = getCachedStudyPreference(userId) || {}
  return setCachedStudyPreference(userId, {
    ...current,
    ...partialValue,
  })
}

export function clearCachedStudyPreference(userId?: unknown) {
  const key = normalizeUserKey(userId)

  if (!key) {
    persistCacheMap({})
    return
  }

  const cacheMap = loadCacheMap()
  delete cacheMap[key]
  persistCacheMap({ ...cacheMap })
}
