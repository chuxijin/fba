/**
 * Banner & Notice 相关 API
 */

import { get, post } from '../request'

/** ==================== 类型定义 ==================== */

/** 轮播图 */
export interface Banner {
  /** 轮播图 ID */
  id: number
  /** 标题 */
  title: string
  /** 图片 URL */
  image_url: string
  /** 链接类型 */
  link_type: 'none' | 'url' | 'miniprogram'
  /** 跳转链接 */
  link_url: string | null
}

/** 通知栏 */
export interface Notice {
  /** 通知 ID */
  id: number
  /** 通知内容 */
  content: string
  /** 通知类型 */
  notice_type: 'info' | 'warning' | 'success'
  /** 跳转链接 */
  link_url: string | null
  /** 是否滚动 */
  is_scrollable: boolean
}

/** ==================== API 函数 ==================== */

/**
 * 获取启用的轮播图列表
 *
 * :param scene: 展示场景（home/practice/study 等）
 */
export function getActiveBanners(scene?: string): Promise<Banner[]> {
  return get('/qbank/banners', scene ? { scene } : undefined, {
    needToken: false,
  })
}

/**
 * 获取启用的通知列表
 *
 * :param scene: 展示场景（home/practice/study 等）
 */
export function getActiveNotices(scene?: string): Promise<Notice[]> {
  return get('/qbank/notices', scene ? { scene } : undefined, {
    needToken: false,
  })
}

/**
 * 记录轮播图点击
 *
 * :param bannerId: 轮播图 ID
 */
export function clickBanner(bannerId: number): Promise<void> {
  return post(`/qbank/banners/${bannerId}/click`, undefined, {
    needToken: false,
  })
}
