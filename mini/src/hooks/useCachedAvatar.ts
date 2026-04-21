import { computed, ref, watch, type Ref } from 'vue'

type AvatarCacheRecord = {
  savedFilePath: string
  size: number
  updatedAt: number
}

type AvatarCacheMap = Record<string, AvatarCacheRecord>

const STORAGE_KEY = 'avatar_cache_v1'
const DEFAULT_AVATAR = '/static/images/default-avatar.png'
const CACHE_MAX_AGE = 1000 * 60 * 60 * 24 * 30
const pendingMap = new Map<string, Promise<string>>()
let memCacheMap: AvatarCacheMap | null = null

function getWxFileSystemManager() {
  // #ifdef MP-WEIXIN
  if (typeof wx !== 'undefined' && typeof wx.getFileSystemManager === 'function') {
    return wx.getFileSystemManager()
  }
  // #endif
  return null
}

function getUserDataPath() {
  // #ifdef MP-WEIXIN
  if (typeof wx !== 'undefined' && wx.env?.USER_DATA_PATH) {
    return wx.env.USER_DATA_PATH
  }
  // #endif
  return ''
}

function isSupported() {
  return typeof uni !== 'undefined'
    && typeof uni.downloadFile === 'function'
    && (
      (typeof uni.saveFile === 'function' && typeof uni.getSavedFileInfo === 'function')
      || !!getWxFileSystemManager()
    )
}

function isRemoteUrl(url: string) {
  return /^https?:\/\//i.test(url)
}

function normalizeAvatarUrl(url: string | null | undefined, fallback: string) {
  const value = String(url || '').trim()
  return value || fallback
}

function getFileExtension(url: string) {
  const cleanUrl = String(url || '').split('?')[0].split('#')[0]
  const matched = cleanUrl.match(/\.([a-zA-Z0-9]+)$/)
  return matched ? `.${matched[1].toLowerCase()}` : '.jpg'
}

function hashString(value: string) {
  let hash = 5381
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) + hash) ^ value.charCodeAt(index)
  }
  return Math.abs(hash).toString(36)
}

function loadCacheMap(): AvatarCacheMap {
  if (memCacheMap)
    return memCacheMap

  try {
    const raw = uni.getStorageSync(STORAGE_KEY)
    if (!raw) {
      memCacheMap = {}
      return memCacheMap
    }

    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    memCacheMap = parsed && typeof parsed === 'object' ? parsed as AvatarCacheMap : {}
    return memCacheMap
  }
  catch {
    memCacheMap = {}
    return memCacheMap
  }
}

function saveCacheMap(cacheMap: AvatarCacheMap) {
  memCacheMap = cacheMap
  uni.setStorageSync(STORAGE_KEY, JSON.stringify(cacheMap))
}

function getSavedFileInfo(filePath: string) {
  const fs = getWxFileSystemManager()
  if (fs) {
    return new Promise<{ size?: number }>((resolve, reject) => {
      fs.getFileInfo({
        filePath,
        success: resolve,
        fail: reject,
      })
    })
  }

  return new Promise<{ size?: number }>((resolve, reject) => {
    uni.getSavedFileInfo({
      filePath,
      success: resolve as any,
      fail: reject,
    })
  })
}

function removeSavedFile(filePath: string) {
  const fs = getWxFileSystemManager()
  if (fs) {
    return new Promise<void>((resolve) => {
      fs.unlink({
        filePath,
        success: () => resolve(),
        fail: () => resolve(),
      })
    })
  }

  return new Promise<void>((resolve) => {
    uni.removeSavedFile({
      filePath,
      success: () => resolve(),
      fail: () => resolve(),
    })
  })
}

function downloadFile(url: string) {
  return new Promise<string>((resolve, reject) => {
    uni.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.tempFilePath) {
          resolve(res.tempFilePath)
          return
        }

        reject(new Error(`download avatar failed: ${res.statusCode}`))
      },
      fail: reject,
    })
  })
}

function saveFile(tempFilePath: string, sourceUrl: string) {
  const fs = getWxFileSystemManager()
  const userDataPath = getUserDataPath()

  if (fs && userDataPath) {
    const savedFilePath = `${userDataPath}/avatar-cache-${hashString(sourceUrl)}${getFileExtension(sourceUrl)}`
    return new Promise<string>((resolve, reject) => {
      fs.saveFile({
        tempFilePath,
        filePath: savedFilePath,
        success: res => resolve(res.savedFilePath || savedFilePath),
        fail: reject,
      })
    })
  }

  return new Promise<string>((resolve, reject) => {
    uni.saveFile({
      tempFilePath,
      success: res => resolve(res.savedFilePath),
      fail: reject,
    })
  })
}

function getCachedAvatarUrlSync(url: string) {
  if (!isSupported() || !isRemoteUrl(url))
    return url

  const cached = loadCacheMap()[url]
  if (!cached?.savedFilePath)
    return url

  if (Date.now() - Number(cached.updatedAt || 0) > CACHE_MAX_AGE)
    return url

  return cached.savedFilePath
}

async function ensureCachedAvatar(url: string) {
  const cacheMap = loadCacheMap()
  const cached = cacheMap[url]

  if (cached?.savedFilePath && Date.now() - Number(cached.updatedAt || 0) <= CACHE_MAX_AGE) {
    try {
      const info = await getSavedFileInfo(cached.savedFilePath)
      cacheMap[url] = {
        savedFilePath: cached.savedFilePath,
        size: Number(info.size || cached.size || 0),
        updatedAt: Date.now(),
      }
      saveCacheMap(cacheMap)
      return cached.savedFilePath
    }
    catch {
      delete cacheMap[url]
      saveCacheMap(cacheMap)
    }
  }

  if (cached?.savedFilePath) {
    await removeSavedFile(cached.savedFilePath)
  }

  const tempFilePath = await downloadFile(url)
  const savedFilePath = await saveFile(tempFilePath, url)
  const info = await getSavedFileInfo(savedFilePath)

  cacheMap[url] = {
    savedFilePath,
    size: Number(info.size || 0),
    updatedAt: Date.now(),
  }
  saveCacheMap(cacheMap)

  return savedFilePath
}

async function resolveCachedAvatarUrl(url: string) {
  if (!isSupported() || !isRemoteUrl(url))
    return url

  if (!pendingMap.has(url)) {
    pendingMap.set(url, ensureCachedAvatar(url)
      .catch(() => url)
      .finally(() => {
        pendingMap.delete(url)
      }))
  }

  return pendingMap.get(url)!
}

export function useCachedAvatar(source: Ref<string | null | undefined>, fallback = DEFAULT_AVATAR) {
  const displayAvatar = ref(fallback)
  let version = 0

  async function refreshAvatar(url: string | null | undefined) {
    const currentVersion = version + 1
    version = currentVersion

    const sourceUrl = normalizeAvatarUrl(url, fallback)
    displayAvatar.value = getCachedAvatarUrlSync(sourceUrl)

    const cachedUrl = await resolveCachedAvatarUrl(sourceUrl)
    if (currentVersion !== version)
      return

    displayAvatar.value = cachedUrl || sourceUrl
  }

  watch(source, url => void refreshAvatar(url), { immediate: true })

  return computed(() => displayAvatar.value || fallback)
}

export async function clearAvatarCache() {
  const cacheMap = loadCacheMap()
  const records = Object.values(cacheMap)

  await Promise.all(records.map(item => removeSavedFile(item.savedFilePath)))
  memCacheMap = null
  uni.removeStorageSync(STORAGE_KEY)
}
