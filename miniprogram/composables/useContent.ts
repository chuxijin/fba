import { ref, computed } from 'vue'
import * as contentApi from '@/api/business/content'

declare const uni: any

// 全局轮播图列表（按场景缓存）
const bannersByScene = ref<Map<string, contentApi.Banner[]>>(new Map())
const bannersLoading = ref(false)

// 全局通知列表（按场景缓存）
const noticesByScene = ref<Map<string, contentApi.Notice[]>>(new Map())
const noticesLoading = ref(false)

// 当前场景的数据（默认 home）
const currentScene = ref('home')
const banners = computed(() => bannersByScene.value.get(currentScene.value) || [])
const notices = computed(() => noticesByScene.value.get(currentScene.value) || [])

/**
 * 加载轮播图数据
 *
 * :param scene: 展示场景（默认 home）
 * :param force: 是否强制刷新
 */
async function loadBanners(scene = 'home', force = false) {
  currentScene.value = scene

  if (bannersByScene.value.has(scene) && !force) {
    return bannersByScene.value.get(scene)
  }

  try {
    bannersLoading.value = true
    const data = await contentApi.getActiveBanners(scene)
    bannersByScene.value.set(scene, data)
    return data
  } catch (error) {
    console.error('[Content] 加载轮播图失败:', error)
    return []
  } finally {
    bannersLoading.value = false
  }
}

/**
 * 加载通知数据
 *
 * :param scene: 展示场景（默认 home）
 * :param force: 是否强制刷新
 */
async function loadNotices(scene = 'home', force = false) {
  currentScene.value = scene

  if (noticesByScene.value.has(scene) && !force) {
    return noticesByScene.value.get(scene)
  }

  try {
    noticesLoading.value = true
    const data = await contentApi.getActiveNotices(scene)
    noticesByScene.value.set(scene, data)
    return data
  } catch (error) {
    console.error('[Content] 加载通知失败:', error)
    return []
  } finally {
    noticesLoading.value = false
  }
}

/**
 * 记录轮播图点击
 */
async function handleBannerClick(banner: contentApi.Banner, index: number) {
  // 记录点击统计
  try {
    await contentApi.clickBanner(banner.id)
  } catch (error) {
    console.error('[Content] 记录轮播图点击失败:', error)
  }

  // 处理跳转
  if (banner.link_type === 'url' && banner.link_url) {
    // H5 页面跳转
    uni.navigateTo({
      url: `/pages/webview/index?url=${encodeURIComponent(banner.link_url)}`,
    })
  } else if (banner.link_type === 'miniprogram' && banner.link_url) {
    // 小程序内部页面跳转
    uni.navigateTo({
      url: banner.link_url,
    })
  }
  // link_type === 'none' 不跳转
}

/**
 * 处理通知点击
 */
function handleNoticeClick(notice: contentApi.Notice) {
  if (notice.link_url) {
    // 如果有跳转链接，则跳转
    if (notice.link_url.startsWith('http')) {
      // H5 页面
      uni.navigateTo({
        url: `/pages/webview/index?url=${encodeURIComponent(notice.link_url)}`,
      })
    } else {
      // 小程序内部页面
      uni.navigateTo({
        url: notice.link_url,
      })
    }
  }
}

/**
 * 内容管理 Composable
 */
export function useContent() {
  // UView Swiper 需要的数据格式（图片 URL 数组）
  const bannerImages = computed(() => banners.value.map(b => b.image_url))

  // 第一条通知（用于单条显示）
  const firstNotice = computed(() => notices.value[0] || null)

  // 通知栏文本（用于单条显示）
  const noticeText = computed(() => firstNotice.value?.content || '')

  // 通知栏颜色配置
  const noticeColor = computed(() => {
    const type = firstNotice.value?.notice_type || 'info'
    const colorMap = {
      info: { color: '#92400e', bgColor: '#fffbeb' },
      warning: { color: '#9a3412', bgColor: '#fef3c7' },
      success: { color: '#065f46', bgColor: '#d1fae5' },
    }
    return colorMap[type]
  })

  return {
    // 数据
    banners,
    bannersLoading,
    notices,
    noticesLoading,

    // 加载方法
    loadBanners,
    loadNotices,

    // 事件处理
    handleBannerClick,
    handleNoticeClick,

    // 计算属性（便于使用）
    bannerImages,
    firstNotice,
    noticeText,
    noticeColor,
  }
}
