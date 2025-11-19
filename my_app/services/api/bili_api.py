#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 站 API 服务封装"""
import httpx
from bilibili_api import user, video, article, Credential
from bilibili_api.exceptions import ResponseCodeException


class BiliAPIService:
    """B 站 API 服务类"""

    def __init__(self):
        """初始化"""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_user_info(self, uid: int) -> dict | None:
        """
        获取用户信息

        :param uid: B 站用户 UID
        :return: 用户信息字典
        """
        try:
            u = user.User(uid=uid)
            info = await u.get_user_info()
            return {
                'uid': uid,
                'name': info.get('name', ''),
                'face': info.get('face', ''),
                'sign': info.get('sign', ''),
                'level': info.get('level', 0),
                'follower': info.get('follower', 0),
                'following': info.get('following', 0),
            }
        except ResponseCodeException as e:
            print(f'获取用户信息失败: {e}')
            return None
        except Exception as e:
            print(f'获取用户信息异常: {e}')
            return None

    async def get_user_videos(self, uid: int, page: int = 1, page_size: int = 20) -> list[dict]:
        """
        获取用户投稿视频列表

        :param uid: B 站用户 UID
        :param page: 页码
        :param page_size: 每页数量
        :return: 视频列表
        """
        try:
            u = user.User(uid=uid)
            videos_data = await u.get_videos(pn=page, ps=page_size)
            videos = videos_data.get('list', {}).get('vlist', [])

            result = []
            for v in videos:
                result.append({
                    'bvid': v.get('bvid', ''),
                    'title': v.get('title', ''),
                    'description': v.get('description', ''),
                    'play': v.get('play', 0),
                    'comment': v.get('comment', 0),
                    'created': v.get('created', 0),
                })
            return result
        except Exception as e:
            print(f'获取用户视频失败: {e}')
            return []

    async def get_video_stat(self, bvid: str) -> dict | None:
        """
        获取视频统计数据

        :param bvid: 视频 BV 号
        :return: 统计数据
        """
        try:
            v = video.Video(bvid=bvid)
            info = await v.get_info()
            stat = info.get('stat', {})

            return {
                'bvid': bvid,
                'view': stat.get('view', 0),
                'like': stat.get('like', 0),
                'coin': stat.get('coin', 0),
                'favorite': stat.get('favorite', 0),
                'share': stat.get('share', 0),
                'danmaku': stat.get('danmaku', 0),
                'reply': stat.get('reply', 0),
            }
        except Exception as e:
            print(f'获取视频统计失败: {e}')
            return None

    async def search_user(self, keyword: str, page: int = 1) -> list[dict]:
        """
        搜索用户

        :param keyword: 搜索关键词
        :param page: 页码
        :return: 用户列表
        """
        try:
            url = 'https://api.bilibili.com/x/web-interface/search/type'
            params = {
                'search_type': 'bili_user',
                'keyword': keyword,
                'page': page,
            }
            response = await self.client.get(url, params=params)
            data = response.json()

            if data.get('code') == 0:
                result_list = data.get('data', {}).get('result', [])
                users = []
                for item in result_list:
                    users.append({
                        'mid': item.get('mid', 0),
                        'uname': item.get('uname', ''),
                        'usign': item.get('usign', ''),
                        'fans': item.get('fans', 0),
                        'videos': item.get('videos', 0),
                    })
                return users
            return []
        except Exception as e:
            print(f'搜索用户失败: {e}')
            return []

    async def get_current_ip(self) -> str | None:
        """获取当前公网 IP 地址"""
        try:
            # 使用多个 IP 查询服务，提高成功率
            urls = [
                'https://api.ipify.org?format=json',
                'https://api.ip.sb/ip',
                'https://ifconfig.me/ip',
            ]

            for url in urls:
                try:
                    response = await self.client.get(url, timeout=5.0)
                    if response.status_code == 200:
                        if 'json' in url:
                            return response.json().get('ip')
                        else:
                            return response.text.strip()
                except Exception:
                    continue
            return None
        except Exception as e:
            print(f'获取 IP 地址失败: {e}')
            return None

    async def get_user_info_by_cookie(self, cookie: str) -> dict | None:
        """
        通过 Cookie 获取当前登录用户信息

        :param cookie: Cookie 字符串
        :return: 用户信息字典（包含 mid、name 等）
        """
        try:
            # 解析 cookie 字符串
            cookie_dict = {}
            for item in cookie.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookie_dict[key.strip()] = value.strip()

            # 获取必要的 cookie 字段
            sessdata = cookie_dict.get('SESSDATA', '')
            bili_jct = cookie_dict.get('bili_jct', '')
            buvid3 = cookie_dict.get('buvid3', '')

            if not sessdata:
                print('Cookie 中缺少 SESSDATA')
                return None

            # 创建凭证
            credential = Credential(sessdata=sessdata, bili_jct=bili_jct, buvid3=buvid3)

            # 获取当前用户信息
            my_info = await user.get_self_info(credential)

            if my_info:
                return {
                    'mid': my_info.get('mid', ''),
                    'name': my_info.get('name', ''),
                    'face': my_info.get('face', ''),
                    'sign': my_info.get('sign', ''),
                    'level': my_info.get('level_info', {}).get('current_level', 0),
                }
            return None
        except Exception as e:
            print(f'通过 Cookie 获取用户信息失败: {e}')
            return None

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


# 全局实例
bili_api_service = BiliAPIService()
