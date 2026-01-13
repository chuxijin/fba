/**
 * 收藏相关 API
 */

import { get, post, put, del } from '../request'

/** ==================== 类型定义 ==================== */

/** 收藏项详情 */
export interface FavoriteItem {
  /** 收藏 ID */
  id: number
  /** 题目 ID */
  question_id: number
  /** 用户 ID */
  user_id: number
  /** 收藏夹名称 */
  folder_name: string | null
  /** 自定义标签 */
  tags: string[] | null
  /** 备注 */
  remark: string | null
  /** 是否置顶 */
  is_pinned: boolean
  /** 置顶时间 */
  pinned_time: string | null
  /** 收藏时间 */
  created_time: string

  /** 题目题干（关联查询） */
  question_stem: string | null
  /** 题型 */
  question_type: string | null
  /** 难度 */
  question_difficulty: string | null
  /** 题库 ID */
  bank_id?: number
  /** 题库名称 */
  bank_name: string | null
  /** 章节 ID */
  chapter_id?: number
  /** 章节名称 */
  chapter_name: string | null
}

/** 收藏列表响应 */
export interface FavoriteListResponse {
  /** 收藏列表 */
  items: FavoriteItem[]
  /** 总数 */
  total: number
  /** 当前页 */
  page: number
  /** 每页数量 */
  size: number
}

/** 创建收藏参数 */
export interface CreateFavoriteParams {
  /** 题目 ID */
  question_id: number
  /** 收藏夹名称（可选） */
  folder_name?: string
  /** 标签列表（可选） */
  tags?: string[]
  /** 备注（可选） */
  remark?: string
}

/** 更新收藏参数 */
export interface UpdateFavoriteParams {
  /** 收藏夹名称 */
  folder_name?: string
  /** 标签列表 */
  tags?: string[]
  /** 备注 */
  remark?: string
}

/** 获取收藏列表参数 */
export interface GetFavoriteListParams {
  /** 收藏夹名称（筛选） */
  folder_name?: string
  /** 是否置顶（筛选） */
  is_pinned?: boolean
  /** 页码 */
  page?: number
  /** 每页数量 */
  size?: number
}

/** 收藏夹信息 */
export interface FolderInfo {
  /** 收藏夹名称 */
  folder_name: string
  /** 收藏数量 */
  count: number
}

/** 收藏统计 */
export interface FavoriteStatistics {
  /** 总收藏数 */
  total_count: number
  /** 收藏夹数量 */
  folder_count: number
  /** 收藏夹列表 */
  folders: FolderInfo[]
}

/** ==================== API 函数 ==================== */

/**
 * 获取收藏夹列表
 */
export function getFolders(): Promise<string[]> {
  return get('/qbank/favorites/folders')
}

/**
 * 获取收藏列表
 */
export function getFavoriteList(params?: GetFavoriteListParams): Promise<FavoriteListResponse> {
  return get('/qbank/favorites', params)
}

/**
 * 获取收藏详情
 */
export function getFavoriteDetail(favoriteId: number): Promise<FavoriteItem> {
  return get(`/qbank/favorites/${favoriteId}`)
}

/**
 * 检查题目收藏状态（统一接口）
 *
 * @param questionIds 题目 ID 数组（单个或多个）
 * @returns 映射表 {questionId: isFavorited}
 */
export function checkFavorited(questionIds: number[]): Promise<Record<number, boolean>> {
  return get('/qbank/questions/favorites', { question_ids: questionIds.join(',') })
}

/**
 * 创建收藏
 */
export function createFavorite(data: CreateFavoriteParams): Promise<FavoriteItem> {
  return post('/qbank/favorites', data)
}

/**
 * 更新收藏
 */
export function updateFavorite(favoriteId: number, data: UpdateFavoriteParams): Promise<void> {
  return put(`/qbank/favorites/${favoriteId}`, data)
}

/**
 * 设置收藏置顶
 */
export function setFavoritePin(favoriteId: number, isPinned: boolean): Promise<void> {
  return put(`/qbank/favorites/${favoriteId}/pin`, { is_pinned: isPinned })
}

/**
 * 删除收藏
 */
export function deleteFavorite(favoriteId: number): Promise<void> {
  return del(`/qbank/favorites/${favoriteId}`)
}

/**
 * 批量删除收藏
 */
export function batchDeleteFavorites(favoriteIds: number[]): Promise<void> {
  return post('/qbank/favorites/batch-delete', { favorite_ids: favoriteIds })
}

/**
 * 清空收藏夹
 */
export function clearFolder(folderName: string): Promise<void> {
  return post('/qbank/favorites/folders/clear', { folder_name: folderName })
}

/**
 * 获取收藏统计
 */
export function getFavoriteStatistics(): Promise<FavoriteStatistics> {
  return get('/qbank/favorites/statistics')
}

/**
 * 智能收藏/取消收藏 (优化版)
 *
 * 自动判断题目是否已收藏,如果已收藏则取消收藏,否则创建收藏
 *
 * ✅ 性能优化：取消收藏只需1次API调用（通过 question_id 直接删除）
 */
export async function toggleFavorite(
  questionId: number,
  folderName?: string
): Promise<{ action: 'add' | 'remove' }> {
  // 批量检查收藏状态（传入单个 ID 的数组）
  const statusMap = await checkFavorited([questionId])
  const isFavorited = statusMap[questionId] || false

  if (isFavorited) {
    // 已收藏 → 直接通过 question_id 删除 ✅ 只需1次调用
    await del(`/qbank/favorites/questions/${questionId}`)
    return { action: 'remove' }
  } else {
    // 未收藏 → 创建新收藏
    await createFavorite({
      question_id: questionId,
      folder_name: folderName
    })
    return { action: 'add' }
  }
}
