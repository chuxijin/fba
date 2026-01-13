/**
 * 笔记相关 API
 */

import { get, post, put, del } from '../request'

/** ==================== 类型定义 ==================== */

/** 笔记详情 */
export interface QuestionNote {
  /** 笔记 ID */
  id: number
  /** 用户 ID */
  user_id: number
  /** 题目 ID */
  question_id: number
  /** 笔记内容（Markdown 格式） */
  content: string
  /** 是否公开 */
  is_public: boolean
  /** 点赞数 */
  like_count: number
  /** 点踩数 */
  dislike_count: number
  /** 浏览次数 */
  view_count: number
  /** 质量分 */
  quality_score: number
  /** 是否精选 */
  is_featured: boolean
  /** 精选时间 */
  featured_time: string | null
  /** 创建时间 */
  created_time: string
  /** 更新时间 */
  updated_time: string
}

/** 笔记列表项 */
export interface QuestionNoteListItem {
  /** 笔记 ID */
  id: number
  /** 用户 ID */
  user_id: number
  /** 题目 ID */
  question_id: number
  /** 笔记内容（预览） */
  content: string
  /** 是否公开 */
  is_public: boolean
  /** 点赞数 */
  like_count: number
  /** 点踩数 */
  dislike_count: number
  /** 质量分 */
  quality_score: number
  /** 是否精选 */
  is_featured: boolean
  /** 更新时间 */
  updated_time: string
  /** 用户昵称 */
  user_nickname?: string | null
  /** 用户头像 */
  user_avatar?: string | null
}

/** 创建笔记参数 */
export interface CreateQuestionNoteParams {
  /** 题目 ID */
  question_id: number
  /** 笔记内容 */
  content: string
  /** 是否公开 */
  is_public?: boolean
}

/** 更新笔记参数 */
export interface UpdateQuestionNoteParams {
  /** 笔记内容 */
  content: string
  /** 是否公开 */
  is_public?: boolean
}

/** 用户投票详情 */
export interface UserNoteVote {
  /** 用户 ID */
  user_id: number
  /** 笔记 ID */
  note_id: number
  /** 投票值：1=点赞，-1=点踩 */
  vote_value: number
  /** 投票时间 */
  created_time: string
  /** 更新时间 */
  updated_time: string
}

/** 投票统计 */
export interface NoteVoteStatistics {
  /** 点赞数 */
  like_count: number
  /** 点踩数 */
  dislike_count: number
  /** 质量分 */
  quality_score: number
}

/** ==================== API 函数 ==================== */

/**
 * 获取我的笔记（单个题目）
 *
 * @param questionId 题目 ID
 */
export function getMyNote(questionId: number): Promise<QuestionNote | null> {
  return get('/qbank/notes', {
    question_id: questionId,
    my_notes: true,
    page: 1,
    size: 1
  }).then((res: any) => {
    // 返回分页数据中的第一项
    if (res.items && res.items.length > 0) {
      return res.items[0]
    }
    return null
  })
}

/**
 * 批量获取我的笔记（多个题目）
 *
 * @param questionIds 题目 ID 数组
 * @returns 映射表 {questionId: QuestionNote | null}
 */
export function batchGetMyNotes(questionIds: number[]): Promise<Record<number, QuestionNote | null>> {
  return get('/qbank/questions/notes', { question_ids: questionIds.join(',') })
}

/**
 * 获取题目的公开笔记列表
 */
export function getPublicNotes(questionId: number, isFeatured?: boolean): Promise<QuestionNoteListItem[]> {
  const params: any = {}
  if (isFeatured !== undefined) {
    params.is_featured = isFeatured
  }
  return get(`/qbank/notes/questions/${questionId}/public`, params)
}

/**
 * 获取笔记详情
 */
export function getNoteDetail(noteId: number): Promise<QuestionNote> {
  return get(`/qbank/notes/${noteId}`)
}

/**
 * 创建笔记
 */
export function createNote(data: CreateQuestionNoteParams): Promise<QuestionNote> {
  return post('/qbank/notes', data)
}

/**
 * 更新笔记
 */
export function updateNote(noteId: number, data: UpdateQuestionNoteParams): Promise<void> {
  return put(`/qbank/notes/${noteId}`, data)
}

/**
 * 删除笔记
 */
export function deleteNote(noteId: number): Promise<void> {
  return del(`/qbank/notes/${noteId}`)
}

/**
 * 对笔记投票（点赞/点踩）
 */
export function voteNote(noteId: number, voteValue: 1 | -1): Promise<void> {
  return post(`/qbank/notes/${noteId}/vote`, { vote_value: voteValue })
}

/**
 * 取消投票
 */
export function cancelVote(noteId: number): Promise<void> {
  return del(`/qbank/notes/${noteId}/vote`)
}

/**
 * 获取我的投票状态
 */
export function getMyVote(noteId: number): Promise<UserNoteVote> {
  return get(`/qbank/notes/${noteId}/vote/my`)
}

/**
 * 获取笔记投票统计
 */
export function getVoteStatistics(noteId: number): Promise<NoteVoteStatistics> {
  return get(`/qbank/notes/${noteId}/vote/statistics`)
}

/**
 * 创建或更新我的笔记（智能判断）
 *
 * 如果该题目已有笔记则更新，否则创建新笔记
 */
export async function createOrUpdateMyNote(
  questionId: number,
  content: string,
  isPublic: boolean = false
): Promise<QuestionNote> {
  // 先查询是否已有笔记
  const existingNote = await getMyNote(questionId)

  if (existingNote) {
    // 已有笔记 → 更新
    await updateNote(existingNote.id, {
      content,
      is_public: isPublic
    })
    // 返回更新后的笔记详情
    return getNoteDetail(existingNote.id)
  } else {
    // 没有笔记 → 创建
    return createNote({
      question_id: questionId,
      content,
      is_public: isPublic
    })
  }
}
