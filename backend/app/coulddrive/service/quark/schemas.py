#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Optional, List, Dict, NamedTuple, Any
from collections import namedtuple


class QuarkFile(NamedTuple):
    """夸克网盘文件"""
    
    fid: str  # 文件ID
    file_name: str  # 文件名
    pdir_fid: str  # 父目录ID
    category: Optional[int] = None  # 文件分类
    file_type: Optional[int] = None  # 文件类型
    size: Optional[int] = None  # 文件大小
    format_type: Optional[str] = None  # 格式类型
    status: Optional[int] = None  # 状态
    tags: Optional[str] = None  # 标签
    created_at: Optional[int] = None  # 创建时间
    updated_at: Optional[int] = None  # 更新时间
    deleted_at: Optional[int] = None  # 删除时间
    dir: Optional[bool] = None  # 是否为目录
    file: Optional[bool] = None  # 是否为文件
    obj_category: Optional[str] = None  # 对象分类
    like: Optional[int] = None  # 点赞数
    md5: Optional[str] = None  # MD5值
    sha1: Optional[str] = None  # SHA1值
    duration: Optional[int] = None  # 时长（视频文件）
    thumbnail: Optional[str] = None  # 缩略图
    
    @staticmethod
    def from_(info) -> "QuarkFile":
        """从API响应创建QuarkFile对象"""
        return QuarkFile(
            fid=info.get("fid"),
            file_name=info.get("file_name"),
            pdir_fid=info.get("pdir_fid"),
            category=info.get("category"),
            file_type=info.get("file_type"),
            size=info.get("size"),
            format_type=info.get("format_type"),
            status=info.get("status"),
            tags=info.get("tags"),
            created_at=info.get("created_at"),
            updated_at=info.get("updated_at"),
            deleted_at=info.get("deleted_at"),
            dir=info.get("dir"),
            file=info.get("file"),
            obj_category=info.get("obj_category"),
            like=info.get("like"),
            md5=info.get("md5"),
            sha1=info.get("sha1"),
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
        )


class QuarkShare(NamedTuple):
    """夸克网盘分享"""
    
    share_id: str  # 分享ID
    title: str  # 分享标题
    share_url: str  # 分享链接
    pwd_id: Optional[str] = None  # 密码ID
    share_type: Optional[int] = None  # 分享类型
    url_type: Optional[int] = None  # URL类型
    expired_type: Optional[int] = None  # 过期类型
    expired_at: Optional[int] = None  # 过期时间
    created_at: Optional[int] = None  # 创建时间
    updated_at: Optional[int] = None  # 更新时间
    file_num: Optional[int] = None  # 文件数量
    click_pv: Optional[int] = None  # 点击量
    save_pv: Optional[int] = None  # 保存量
    download_pv: Optional[int] = None  # 下载量
    status: Optional[int] = None  # 状态
    first_fid: Optional[str] = None  # 首个文件ID
    
    @staticmethod
    def from_(info) -> "QuarkShare":
        """从API响应创建QuarkShare对象"""
        return QuarkShare(
            share_id=info.get("share_id"),
            title=info.get("title"),
            share_url=info.get("share_url"),
            pwd_id=info.get("pwd_id"),
            share_type=info.get("share_type"),
            url_type=info.get("url_type"),
            expired_type=info.get("expired_type"),
            expired_at=info.get("expired_at"),
            created_at=info.get("created_at"),
            updated_at=info.get("updated_at"),
            file_num=info.get("file_num"),
            click_pv=info.get("click_pv"),
            save_pv=info.get("save_pv"),
            download_pv=info.get("download_pv"),
            status=info.get("status"),
            first_fid=info.get("first_fid"),
        )


class QuarkTask(NamedTuple):
    """夸克网盘任务"""
    
    task_id: str  # 任务ID
    task_type: Optional[int] = None  # 任务类型
    task_title: Optional[str] = None  # 任务标题
    status: Optional[int] = None  # 状态
    created_at: Optional[int] = None  # 创建时间
    finished_at: Optional[int] = None  # 完成时间
    event_id: Optional[str] = None  # 事件ID
    share_id: Optional[str] = None  # 分享ID（分享任务）
    
    @staticmethod
    def from_(info) -> "QuarkTask":
        """从API响应创建QuarkTask对象"""
        return QuarkTask(
            task_id=info.get("task_id"),
            task_type=info.get("task_type"),
            task_title=info.get("task_title"),
            status=info.get("status"),
            created_at=info.get("created_at"),
            finished_at=info.get("finished_at"),
            event_id=info.get("event_id"),
            share_id=info.get("share_id"),
        )


class QuarkMember(NamedTuple):
    """夸克网盘会员信息"""
    
    member_type: Optional[str] = None  # 会员类型
    member_name: Optional[str] = None  # 会员名称
    member_time: Optional[int] = None  # 会员时间
    is_vip: Optional[bool] = None  # 是否VIP
    capacity: Optional[int] = None  # 容量
    used_capacity: Optional[int] = None  # 已用容量
    
    @staticmethod
    def from_(info) -> "QuarkMember":
        """从API响应创建QuarkMember对象"""
        return QuarkMember(
            member_type=info.get("member_type"),
            member_name=info.get("member_name"),
            member_time=info.get("member_time"),
            is_vip=info.get("is_vip"),
            capacity=info.get("capacity"),
            used_capacity=info.get("used_capacity"),
        )


class QuarkAccount(NamedTuple):
    """夸克网盘账户信息"""
    
    user_id: Optional[str] = None  # 用户ID
    nickname: Optional[str] = None  # 昵称
    avatar: Optional[str] = None  # 头像
    phone: Optional[str] = None  # 手机号
    email: Optional[str] = None  # 邮箱
    
    @staticmethod
    def from_(info) -> "QuarkAccount":
        """从API响应创建QuarkAccount对象"""
        return QuarkAccount(
            user_id=info.get("user_id"),
            nickname=info.get("nickname"),
            avatar=info.get("avatar"),
            phone=info.get("phone"),
            email=info.get("email"),
        )


# 常用的命名元组
FromTo = namedtuple("FromTo", ["from_", "to_"])
FileOperation = namedtuple("FileOperation", ["action", "fids", "target"])


class QuarkShareToken(NamedTuple):
    """夸克网盘分享token"""
    
    stoken: str  # 分享token
    share_type: Optional[int] = None  # 分享类型
    url_type: Optional[int] = None  # URL类型
    expired_type: Optional[int] = None  # 过期类型
    expired_at: Optional[int] = None  # 过期时间
    title: Optional[str] = None  # 分享标题
    subscribed: Optional[bool] = None  # 是否订阅
    author: Optional[Dict[str, Any]] = None  # 作者信息
    
    @staticmethod
    def from_(info) -> "QuarkShareToken":
        """从API响应创建QuarkShareToken对象"""
        return QuarkShareToken(
            stoken=info.get("stoken"),
            share_type=info.get("share_type"),
            url_type=info.get("url_type"),
            expired_type=info.get("expired_type"),
            expired_at=info.get("expired_at"),
            title=info.get("title"),
            subscribed=info.get("subscribed"),
            author=info.get("author"),
        )


class QuarkAuthor(NamedTuple):
    """夸克网盘分享作者信息"""
    
    member_type: Optional[str] = None  # 会员类型
    avatar_url: Optional[str] = None  # 头像URL
    nick_name: Optional[str] = None  # 昵称
    
    @staticmethod
    def from_(info) -> "QuarkAuthor":
        """从API响应创建QuarkAuthor对象"""
        return QuarkAuthor(
            member_type=info.get("member_type"),
            avatar_url=info.get("avatar_url"),
            nick_name=info.get("nick_name"),
        )


class QuarkShareDetail(NamedTuple):
    """夸克网盘分享详情"""
    
    is_owner: Optional[int] = None  # 是否为所有者
    share: Optional[Dict[str, Any]] = None  # 分享信息
    list: Optional[List[Dict[str, Any]]] = None  # 文件列表
    
    @staticmethod
    def from_(info) -> "QuarkShareDetail":
        """从API响应创建QuarkShareDetail对象"""
        return QuarkShareDetail(
            is_owner=info.get("is_owner"),
            share=info.get("share"),
            list=info.get("list"),
        )


class QuarkSaveTask(NamedTuple):
    """夸克网盘保存任务"""
    
    task_id: str  # 任务ID
    task_type: Optional[int] = None  # 任务类型
    task_title: Optional[str] = None  # 任务标题
    status: Optional[int] = None  # 状态
    created_at: Optional[int] = None  # 创建时间
    finished_at: Optional[int] = None  # 完成时间
    event_id: Optional[str] = None  # 事件ID
    save_as: Optional[Dict[str, Any]] = None  # 保存信息
    
    @staticmethod
    def from_(info) -> "QuarkSaveTask":
        """从API响应创建QuarkSaveTask对象"""
        return QuarkSaveTask(
            task_id=info.get("task_id"),
            task_type=info.get("task_type"),
            task_title=info.get("task_title"),
            status=info.get("status"),
            created_at=info.get("created_at"),
            finished_at=info.get("finished_at"),
            event_id=info.get("event_id"),
            save_as=info.get("save_as"),
        )
