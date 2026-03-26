type QuestionMediaCacheRecord = {
  savedFilePath: string
  size: number
  updatedAt: number
}

type QuestionMediaCacheMap = Record<string, QuestionMediaCacheRecord>

type QuestionMediaCacheSummary = {
  count: number
  totalSize: number
}

const STORAGE_KEY = 'question_media_cache_v1'
const pendingMap = new Map<string, Promise<string>>()

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

function isRemoteMediaUrl(url: string) {
  return /^https?:\/\//i.test(url)
}

function getFileExtension(url: string) {
  const cleanUrl = String(url || '').split('?')[0].split('#')[0]
  const matched = cleanUrl.match(/\.([a-zA-Z0-9]+)$/)
  return matched ? `.${matched[1].toLowerCase()}` : ''
}

function hashString(value: string) {
  let hash = 5381
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) + hash) ^ value.charCodeAt(index)
  }
  return Math.abs(hash).toString(36)
}

function extractHtmlMediaUrls(html: string | null | undefined) {
  const content = String(html || '')
  const srcPattern = /\bsrc\s*=\s*(['"])([^'"]+)\1/gi
  const urls = new Set<string>()
  let matched = srcPattern.exec(content)

  while (matched) {
    const url = matched[2]
    if (isRemoteMediaUrl(url))
      urls.add(url)
    matched = srcPattern.exec(content)
  }

  return Array.from(urls)
}

function loadCacheMap(): QuestionMediaCacheMap {
  try {
    const raw = uni.getStorageSync(STORAGE_KEY)
    if (!raw)
      return {}

    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    return parsed && typeof parsed === 'object' ? parsed as QuestionMediaCacheMap : {}
  }
  catch {
    return {}
  }
}

function saveCacheMap(cacheMap: QuestionMediaCacheMap) {
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
    return new Promise<void>((resolve, reject) => {
      fs.unlink({
        filePath,
        success: () => resolve(),
        fail: reject,
      })
    })
  }

  return new Promise<void>((resolve, reject) => {
    uni.removeSavedFile({
      filePath,
      success: () => resolve(),
      fail: reject,
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

        reject(new Error(`download failed: ${res.statusCode}`))
      },
      fail: reject,
    })
  })
}

function saveFile(tempFilePath: string, sourceUrl: string) {
  const fs = getWxFileSystemManager()
  const userDataPath = getUserDataPath()

  if (fs && userDataPath) {
    const extension = getFileExtension(sourceUrl) || getFileExtension(tempFilePath) || '.bin'
    const savedFilePath = `${userDataPath}/question-cache-${hashString(sourceUrl)}${extension}`

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

function appendInlineStyle(tagHtml: string, styleText: string) {
  if (/style\s*=/i.test(tagHtml)) {
    return tagHtml.replace(/style\s*=\s*(['"])(.*?)\1/i, (_match, quote, styleValue) => {
      const mergedStyle = `${styleValue};${styleText}`.replace(/;;+/g, ';')
      return `style=${quote}${mergedStyle}${quote}`
    })
  }

  return tagHtml.replace(/<([a-zA-Z0-9-]+)/, `<$1 style="${styleText}"`)
}

function normalizeHtmlMediaLayout(html: string | null | undefined) {
  const content = String(html || '')
  if (!content) {
    return ''
  }

  return content
    .replace(/<img\b[^>]*>/gi, tag => appendInlineStyle(tag, 'max-width:100%!important;width:100%!important;height:auto!important;display:block;box-sizing:border-box;object-fit:contain;'))
    .replace(/<video\b[^>]*>/gi, tag => appendInlineStyle(tag, 'max-width:100%!important;width:100%!important;height:auto!important;display:block;box-sizing:border-box;'))
    .replace(/<table\b[^>]*>/gi, tag => appendInlineStyle(tag, 'max-width:100%!important;width:100%!important;table-layout:fixed;box-sizing:border-box;'))
}

async function ensureCachedFile(url: string) {
  const cacheMap = loadCacheMap()
  const cached = cacheMap[url]

  if (cached?.savedFilePath) {
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

async function getLocalMediaUrl(url: string) {
  if (!isSupported() || !isRemoteMediaUrl(url))
    return url

  if (!pendingMap.has(url)) {
    pendingMap.set(url, ensureCachedFile(url)
      .catch(() => url)
      .finally(() => {
        pendingMap.delete(url)
      }))
  }

  return pendingMap.get(url)!
}

export async function cacheQuestionHtmlMedia(html: string | null | undefined) {
  const normalizedHtml = normalizeHtmlMediaLayout(html)
  if (!normalizedHtml || !isSupported())
    return normalizedHtml

  const urls = new Set(extractHtmlMediaUrls(normalizedHtml))

  if (!urls.size)
    return normalizedHtml

  const entries = await Promise.all(Array.from(urls).map(async (url) => {
    const localUrl = await getLocalMediaUrl(url)
    return [url, localUrl] as const
  }))

  let nextHtml = normalizedHtml
  entries.forEach(([url, localUrl]) => {
    if (localUrl && localUrl !== url)
      nextHtml = nextHtml.split(url).join(localUrl)
  })

  return nextHtml
}

export async function warmupQuestionMediaCache(htmlList: Array<string | null | undefined>) {
  if (!isSupported() || !htmlList.length)
    return

  const urls = new Set<string>()
  htmlList.forEach((html) => {
    extractHtmlMediaUrls(html).forEach(url => urls.add(url))
  })

  if (!urls.size)
    return

  await Promise.all(Array.from(urls).map(async (url) => {
    try {
      await getLocalMediaUrl(url)
    }
    catch (error) {
      console.warn('预热题目资源缓存失败:', url, error)
    }
  }))
}

export function getQuestionMediaCacheSummary(): QuestionMediaCacheSummary {
  const cacheMap = loadCacheMap()
  const records = Object.values(cacheMap)
  return {
    count: records.length,
    totalSize: records.reduce((sum, item) => sum + Number(item.size || 0), 0),
  }
}

export async function clearQuestionMediaCache() {
  const cacheMap = loadCacheMap()
  const records = Object.values(cacheMap)

  await Promise.all(records.map(async (item) => {
    if (!item.savedFilePath)
      return
    try {
      await removeSavedFile(item.savedFilePath)
    }
    catch {}
  }))

  uni.removeStorageSync(STORAGE_KEY)
}
