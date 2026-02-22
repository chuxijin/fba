/**
 * 认证相关 API
 */

import { get, post } from '../request'
import type { PageData, PageParams } from '../types'

/** ==================== 类型定义 ==================== */

/** 微信登录参数 */
export interface WxLoginParams {
  /** 微信登录 code */
  code: string
  /** 平台类型 */
  platform: 'miniapp' | 'h5'
  /** 昵称（可选） */
  nickname?: string
  /** 头像（可选） */
  avatar?: string
}

/** 测试登录参数 */
export interface TestLoginParams {
  /** 用户名 */
  username?: string
  /** 昵称 */
  nickname?: string
}

/** 用户信息 */
export interface UserInfo {
  /** 用户 ID */
  id: string
  /** 用户名 */
  username: string
  /** 昵称 */
  nickname: string
  /** 头像 */
  avatar?: string
}

/** 登录响应 */
export interface LoginResponse {
  /** 访问令牌 */
  access_token: string
  /** 用户信息 */
  user_info: UserInfo
}

/** ==================== API 方法 ==================== */

/**
 * 微信登录
 */
export function wxLogin(params: WxLoginParams) {
  return post<LoginResponse>('/qbank/auth/wx-login', params, {
    needToken: false,
    showLoading: true,
    loadingText: '登录中...',
  })
}

/**
 * 测试登录（开发环境使用）
 */
export function testLogin(params: TestLoginParams = {}) {
  return post<LoginResponse>('/qbank/auth/test-login', params, {
    needToken: false,
    showLoading: true,
    loadingText: '登录中...',
  })
}

/**
 * 获取当前用户信息
 */
export function getCurrentUser() {
  return get<UserInfo>('/qbank/auth/me')
}

/** 导出为默认对象 */
export default {
  wxLogin,
  testLogin,
  getCurrentUser,
}
